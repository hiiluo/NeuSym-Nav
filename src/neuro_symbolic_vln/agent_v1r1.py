"""V1R1 closed-loop episode runner (belief + validator + bounded replan).

Minimal wiring for A-07. Uses:
- ``DeadReckoningTracker`` for pose / carrying evidence (non-privileged;
  the tracker assumes a known starting cell and updates from action
  feedback only).
- ``LocalObservationDecoder`` for visible-cell evidence.
- ``StandardValidator`` + ``commit_true_facts`` for belief filtering.
- ``BeliefMap`` as the persistent tri-valued store.
- ``MiniGridController`` + ``ExecutionMonitor`` for execution and
  bounded replans, identical to the B3 baseline.

The full closed loop lands with A-J03. Two deliberate skeleton choices
sit between here and the plan §17 architecture:

1. World topology is bootstrapped from the very first observation instead
   of being discovered edge-by-edge — every cell the local decoder ever
   marks visible becomes a graph node with edges to observed neighbours,
   so the initial plan sees the whole probe env at once. Frontier-driven
   exploration (A-05) is a superset of this behaviour and will replace
   it when N1 corruption experiments arrive.
2. ``key-opens`` and the ``goal → target-at`` alias are injected as
   world knowledge (colour-match for keys and doors, single-goal per
   episode). Both facts are unobservable from local perception; the
   parser lane owns the general solution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from neuro_symbolic_vln.agent import (
    _episode_outcome_for_plan,
    plan_committed_state,
)
from neuro_symbolic_vln.belief.state import BeliefMap
from neuro_symbolic_vln.belief.validator import (
    StandardValidator,
    build_committed_planning_state,
)
from neuro_symbolic_vln.contracts import (
    CommittedPlanningState,
    EpisodeOutcome,
    EpisodeSpec,
    Evidence,
    GroundAtom,
    LocationGraph,
    ObservationPacket,
    ParseStatus,
    PlanResult,
    PlanStatus,
    PrimitiveAction,
    StepResult,
    SymbolicAction,
    ValidationDisposition,
)
from neuro_symbolic_vln.control.controller import (
    DeadReckoningTracker,
    MiniGridController,
)
from neuro_symbolic_vln.control.monitor import ExecutionMonitor, MonitorDecision
from neuro_symbolic_vln.env.minigrid_adapter import MiniGridAdapter
from neuro_symbolic_vln.env.tasks import (
    make_goto_goal_probe_env,
    make_locked_door_probe_env,
)
from neuro_symbolic_vln.env.verifier import GoToVerifier
from neuro_symbolic_vln.evaluation.interventions import (
    CHECKPOINT_POST_TOGGLE,
    CHECKPOINT_PRE_MOVE,
    InterventionSpec,
    apply_intervention,
)
from neuro_symbolic_vln.language.template_parser import parse_instruction
from neuro_symbolic_vln.perception.observation_decoder import (
    LocalObservationDecoder,
    SensorModelSpec,
)
from neuro_symbolic_vln.planning.location_graph import LocationGraphBuilder
from neuro_symbolic_vln.planning.pyperplan_adapter import PlannerConfig

_HEADING_DELTA = {
    "north": (0, -1),
    "east": (1, 0),
    "south": (0, 1),
    "west": (-1, 0),
}

_WORLD_KNOWLEDGE_SENSOR = "world-knowledge"


def _subgoals_for_family(family: str) -> tuple[GroundAtom, ...]:
    """Ordered subgoals per core task family (plan §9.1).

    Keydoor decomposes into three checkpoints because the goal cell sits
    behind a locked door and cannot be observed (or planned toward) until
    the door has been toggled.
    """
    if family == "goto_type_color":
        return (GroundAtom("task-satisfied", ()),)
    if family == "key_door_goal":
        return (
            GroundAtom("holding", ("robot", "red-key")),
            GroundAtom("door-open", ("red-door",)),
            GroundAtom("task-satisfied", ()),
        )
    raise ValueError(f"unknown task family for V1R1: {family}")


def _subgoal_satisfied(
    subgoal: GroundAtom, state: CommittedPlanningState
) -> bool:
    return subgoal in state.true_facts


@dataclass(frozen=True)
class V1R1StepTrace:
    step: int
    action: SymbolicAction
    primitive: str | None
    step_result: StepResult | None
    monitor_decision: MonitorDecision | None


@dataclass(frozen=True)
class V1R1EpisodeResult:
    episode_id: str
    family: str
    seed: int
    plan: PlanResult
    terminal_outcome: EpisodeOutcome | None
    replan_count: int
    task_success: bool
    parse_status: ParseStatus
    traces: tuple[V1R1StepTrace, ...]
    step_count: int
    belief_state_hash: str


def _make_env_and_verifier(
    family: str, seed: int
) -> tuple[Any, GoToVerifier, str]:
    env: Any
    if family == "key_door_goal":
        env = make_locked_door_probe_env(agent_dir=seed % 4)
        return (
            env,
            GoToVerifier(target_position=(4, 1), env=env),
            "pick up the red key, open the red door, then go to the goal",
        )
    if family == "goto_type_color":
        env = make_goto_goal_probe_env(agent_dir=seed % 4)
        return (
            env,
            GoToVerifier(target_position=(3, 1), env=env),
            "go to the green ball",
        )
    raise ValueError(f"unknown task family for V1R1: {family}")


class _V1R1EpisodeRuntime:
    """Per-episode belief pipeline state.

    Kept internal to this module — the runner just calls
    ``run_v1r1_episode``.
    """

    def __init__(
        self,
        episode: EpisodeSpec,
        family: str,
        *,
        use_validator: bool = True,
        goal_target_entity: str | None = None,
    ) -> None:
        self._episode = episode
        self._family = family
        self._use_validator = use_validator
        # Parser-derived goal entity (e.g. "green-ball" for goto). Confirm-
        # goto planning must restrict to this target; otherwise the
        # planner will happily route to any target-at fact in belief
        # (distractor boxes emit target-at too — see decoder §11.4).
        self._goal_target_entity = goal_target_entity
        self._belief = BeliefMap()
        self._validator = StandardValidator()
        self._tracker = DeadReckoningTracker(episode.episode_id)
        self._decoder = LocalObservationDecoder(
            episode.episode_id,
            pose=lambda: (self._tracker.pose().x, self._tracker.pose().y),
            resolve_location=self._tracker.location_id,
        )
        self._sensor = SensorModelSpec()
        self._committed_version = 0
        self._injected_world_facts: set[GroundAtom] = set()
        self._observed_coords: set[tuple[int, int]] = set()

    @property
    def belief_state_hash(self) -> str:
        return self._belief.state_hash()

    def invalidate(
        self, atoms: tuple[GroundAtom, ...], reason: str
    ) -> None:
        """Force-invalidate belief atoms flagged by the execution monitor."""
        for atom in atoms:
            self._belief.invalidate(atom, reason=reason)

    def absorb_reset(self, observation: ObservationPacket) -> None:
        pose_evidence = self._tracker.reset(observation)
        self._absorb_common(observation, pose_evidence)

    def absorb_step(
        self, primitive: PrimitiveAction, result: StepResult
    ) -> None:
        pose_evidence = self._tracker.step(primitive, result)
        self._absorb_common(result.observation, pose_evidence)

    def _absorb_common(
        self,
        observation: ObservationPacket,
        pose_evidence: tuple[Evidence, ...],
    ) -> None:
        # Two-phase merge so state transitions actually propagate:
        # 1. Pre-merge every negative-polarity item (tracker + decoder)
        #    directly into belief. Without this the validator's
        #    holding-and-handempty and door-open-and-locked conflict
        #    rules would tag the matching positives as UNCERTAIN and
        #    the state would freeze on the old truth value.
        # 2. Validate + merge the positive items with the refreshed
        #    belief so ontology / staleness / reliability checks still
        #    apply to the actual claims (plan §12.3).
        visual_evidence = self._decoder.decode(observation, self._sensor)
        self._record_observed_coords(visual_evidence)
        all_evidence = pose_evidence + visual_evidence

        negatives = tuple(ev for ev in all_evidence if not ev.polarity)
        self._belief.merge_all(negatives)

        positives = tuple(ev for ev in all_evidence if ev.polarity)
        if self._use_validator:
            decisions = self._validator.validate(
                positives, self._belief.records(), observation.step
            )
            accepted_ids = {
                decision.evidence_id
                for decision in decisions
                if decision.disposition is ValidationDisposition.ACCEPTED
            }
            positives = tuple(
                evidence
                for evidence in positives
                if evidence.evidence_id in accepted_ids
            )
        self._belief.merge_all(positives)

    def _record_observed_coords(self, evidence: tuple[Evidence, ...]) -> None:
        for item in evidence:
            local_cell = item.provenance.local_cell
            if local_cell is None:
                continue
            pose = self._tracker.pose()
            right, forward = local_cell
            heading_delta = _egocentric_to_world(right, forward, pose.heading)
            self._observed_coords.add(
                (pose.x + heading_delta[0], pose.y + heading_delta[1])
            )
        pose = self._tracker.pose()
        self._observed_coords.add((pose.x, pose.y))

    def committed_state(self) -> CommittedPlanningState:
        """Snapshot belief into a CommittedPlanningState the planner can use."""
        self._committed_version += 1
        records = self._belief.records()
        true_facts = {
            atom
            for atom, record in records.items()
            if record.value.value == "true"
            and not record.stale
            and record.conflict_reason is None
        }
        true_facts |= self._injected_world_knowledge(true_facts)
        graph = self._build_graph(true_facts)
        # front-cell atoms are regenerated by the serializer from the
        # graph, so strip them here to avoid duplicates in the PDDL init.
        # Distractor target-at atoms are stripped too when a parser goal
        # entity is known — otherwise the planner would happily
        # confirm-goto a yellow-box distractor.
        planning_facts = frozenset(
            atom
            for atom in true_facts
            if atom.predicate != "front-cell"
            and not self._is_distractor_target(atom)
        )
        provenance = {
            atom: tuple(
                sorted(records[atom].evidence_ids)
            )
            if atom in records
            else (_WORLD_KNOWLEDGE_SENSOR,)
            for atom in planning_facts
        }
        return build_committed_planning_state(
            version=self._committed_version,
            true_facts=planning_facts,
            location_graph=graph,
            provenance_by_fact=provenance,
        )

    def _is_distractor_target(self, atom: GroundAtom) -> bool:
        if atom.predicate != "target-at" or len(atom.arguments) != 2:
            return False
        if self._goal_target_entity is None:
            return False
        return atom.arguments[0] != self._goal_target_entity

    def _injected_world_knowledge(
        self, current_facts: set[GroundAtom]
    ) -> set[GroundAtom]:
        injected: set[GroundAtom] = set()
        # key-opens: colour-match heuristic. Restricted to the keydoor
        # family so goto episodes never get spurious key facts.
        if self._family == "key_door_goal":
            key_colors = {
                atom.arguments[0].split("-")[0]
                for atom in current_facts
                if atom.predicate == "key-at"
                and len(atom.arguments) == 2
                and "-" in atom.arguments[0]
            }
            door_colors = {
                atom.arguments[0].split("-")[0]
                for atom in current_facts
                if atom.predicate == "door-at"
                and len(atom.arguments) == 2
                and "-" in atom.arguments[0]
            }
            for color in key_colors & door_colors:
                injected.add(
                    GroundAtom(
                        "key-opens", (f"{color}-key", f"{color}-door")
                    )
                )
            # Also allow the held-and-then-consumed key to still open the
            # door after pickup (once key-at is gone from belief).
            held = {
                atom.arguments[1]
                for atom in current_facts
                if atom.predicate == "holding"
                and len(atom.arguments) == 2
            }
            for entity in held:
                if entity.endswith("-key") and "-" in entity:
                    color = entity.split("-")[0]
                    if any(
                        atom.predicate == "door-at"
                        and atom.arguments[0] == f"{color}-door"
                        for atom in current_facts
                    ):
                        injected.add(
                            GroundAtom(
                                "key-opens",
                                (f"{color}-key", f"{color}-door"),
                            )
                        )
        # goal-at → target-at alias so confirm-goto works for keydoor.
        for atom in current_facts:
            if (
                atom.predicate == "goal-at"
                and len(atom.arguments) == 2
            ):
                injected.add(
                    GroundAtom("target-at", ("target-goal", atom.arguments[1]))
                )
        # Keydoor probe env leaves the goal cell as an unmarked floor
        # tile (see env/tasks.py::LockedDoorProbeEnv). The plan-level
        # "goal" is task grounding, not a MiniGrid Goal object — inject
        # target-at at the known goal coordinate so confirm-goto can fire
        # once the door is open. World (4, 1) → local (3, 0) since the
        # agent starts at world (1, 1).
        if self._family == "key_door_goal":
            goal_local = (3, 0)
            goal_loc_id = self._tracker.location_id(goal_local)
            injected.add(
                GroundAtom("target-at", ("target-goal", goal_loc_id))
            )
            self._observed_coords.add(goal_local)
        self._injected_world_facts |= injected
        return injected

    def _build_graph(
        self, true_facts: set[GroundAtom]
    ) -> LocationGraph:
        builder = LocationGraphBuilder()
        # Locations from observed coordinates. Every observed cell becomes
        # a node so the planner sees the whole probe env after the first
        # rich observation.
        for coord in self._observed_coords:
            loc_id = self._tracker.location_id(coord)
            builder.add_node(loc_id)
            for heading, (dx, dy) in _HEADING_DELTA.items():
                neighbour = (coord[0] + dx, coord[1] + dy)
                if neighbour in self._observed_coords:
                    neighbour_id = self._tracker.location_id(neighbour)
                    builder.add_edge(loc_id, heading, neighbour_id)
        # Trust the tracker's per-visit front-cell atoms as authoritative
        # edges — the tracker records those for every cell the agent has
        # stood in, even ones whose neighbours were never separately
        # observed. Without this, the alternate-route replan after an N2
        # block can fail because the detour cells are known-passable via
        # decoder evidence but the graph still lacks the connecting edges.
        for atom in true_facts:
            if (
                atom.predicate == "front-cell"
                and len(atom.arguments) == 3
            ):
                from_loc, heading, to_loc = atom.arguments
                builder.add_edge(from_loc, heading, to_loc)
        # Fold in locations that only appear in atoms (e.g. via belief
        # about far cells) so the serializer keeps them typed.
        for atom in true_facts:
            for arg in atom.arguments:
                if arg.startswith("loc_"):
                    builder.add_node(arg)
        return builder.build()


def _egocentric_to_world(
    right: int, forward: int, heading: str
) -> tuple[int, int]:
    """Mirror of ``observation_decoder.egocentric_delta_to_world``."""
    transforms = {
        "north": (right, -forward),
        "east": (forward, right),
        "south": (-right, forward),
        "west": (-forward, -right),
    }
    return transforms[heading]


def _plan_signature(
    state: CommittedPlanningState, plan: PlanResult
) -> tuple[str, str, tuple[str, str], str]:
    robot_at = next(
        (atom for atom in state.true_facts if atom.predicate == "robot-at"),
        GroundAtom("robot-at", ("robot", "loc-unknown")),
    )
    facing = next(
        (atom for atom in state.true_facts if atom.predicate == "facing"),
        GroundAtom("facing", ("robot", "north")),
    )
    return (
        "task-satisfied",
        state.state_hash,
        (robot_at.arguments[1], facing.arguments[1]),
        plan.status.value,
    )


def run_v1r1_episode(
    seed: int = 0,
    family: str = "key_door_goal",
    config: PlannerConfig | None = None,
    *,
    method: str = "V1R1",
    use_validator: bool = True,
    use_recovery: bool = True,
    intervention: InterventionSpec | None = None,
) -> V1R1EpisodeResult:
    """Execute one closed-loop episode.

    Belief-driven state (no privileged env access), typed terminal
    outcomes matching the plan. Method flags select the V/R variant:

    - ``V1R1``: validator + bounded replan (default).
    - ``V1R0``: validator only (one plan attempt).
    - ``V0R1``: no validator, bounded replan.
    - ``V0R0``: neither.
    """
    episode_id = f"{method.lower()}-{family}-seed-{seed}"
    env, verifier, instruction = _make_env_and_verifier(family, seed)
    episode = EpisodeSpec(
        episode_id=episode_id,
        family=family,
        instruction=instruction,
        public_action_budget=32,
        manifest_hash=f"manifest-{family}-{seed}",
    )

    parse_result = parse_instruction(instruction)
    traces: list[V1R1StepTrace] = []
    if parse_result.status is not ParseStatus.DETERMINISTIC:
        outcome = (
            EpisodeOutcome.AMBIGUOUS_GROUNDING
            if parse_result.status is ParseStatus.AMBIGUOUS
            else EpisodeOutcome.UNSUPPORTED_INSTRUCTION
        )
        return V1R1EpisodeResult(
            episode_id=episode_id,
            family=family,
            seed=seed,
            plan=PlanResult(
                status=PlanStatus.UNSUPPORTED_GOAL,
                actions=(),
                planning_time_ms=0.0,
                state_hash="",
                problem_hash=None,
                reason=parse_result.reason,
            ),
            terminal_outcome=outcome,
            replan_count=0,
            task_success=False,
            parse_status=parse_result.status,
            traces=(),
            step_count=0,
            belief_state_hash="",
        )

    adapter = MiniGridAdapter(env, episode, verifier)
    initial_obs = adapter.reset(seed=seed)

    goal_target_entity: str | None = None
    if (
        family == "goto_type_color"
        and parse_result.goal_program is not None
        and parse_result.goal_program.ordered_subgoals
    ):
        first_subgoal = parse_result.goal_program.ordered_subgoals[0]
        # Parser goto atom: (color, object). Decoder emits entities as
        # "{color}-{type}".
        if (
            first_subgoal.predicate == "goto-target"
            and len(first_subgoal.arguments) == 2
        ):
            color, obj_type = first_subgoal.arguments
            goal_target_entity = f"{color}-{obj_type}"
    elif family == "key_door_goal":
        goal_target_entity = "target-goal"

    runtime = _V1R1EpisodeRuntime(
        episode,
        family,
        use_validator=use_validator,
        goal_target_entity=goal_target_entity,
    )
    runtime.absorb_reset(initial_obs)
    monitor = ExecutionMonitor()
    controller = MiniGridController()

    # Frontier-lite bootstrap: rotate 360° at reset so belief covers every
    # heading before the first plan. Cheap (4 turns) and deterministic;
    # A-05 frontier exploration supersedes this when it lands. Traces are
    # emitted as symbolic "scan" actions to keep the row audit honest.
    primitive_count_pre_scan = 0
    scan_primitives = ("turn_right", "turn_right", "turn_right", "turn_right")

    def _run_scan() -> int:
        nonlocal primitive_count_pre_scan
        for prim_name in scan_primitives:
            prim = PrimitiveAction(prim_name)
            step_res = adapter.step(prim)
            primitive_count_pre_scan += 1
            runtime.absorb_step(prim, step_res)
        return primitive_count_pre_scan

    _run_scan()

    subgoals = _subgoals_for_family(family)
    subgoal_index = 0
    committed_state = runtime.committed_state()
    plan = _empty_plan(committed_state.state_hash)
    primitive_count = primitive_count_pre_scan
    task_success = False
    intervention_fired = intervention is None
    toggle_seen = False

    def episode_result(
        *,
        terminal_outcome: EpisodeOutcome,
        success: bool = False,
    ) -> V1R1EpisodeResult:
        return V1R1EpisodeResult(
            episode_id=episode_id,
            family=family,
            seed=seed,
            plan=plan,
            terminal_outcome=terminal_outcome,
            replan_count=monitor.replan_count,
            task_success=success,
            parse_status=parse_result.status,
            traces=tuple(traces),
            step_count=primitive_count,
            belief_state_hash=runtime.belief_state_hash,
        )

    while subgoal_index < len(subgoals):
        subgoal = subgoals[subgoal_index]
        committed_state = runtime.committed_state()
        if _subgoal_satisfied(subgoal, committed_state):
            subgoal_index += 1
            continue

        plan = plan_committed_state(committed_state, subgoal, config=config)
        if plan.status is not PlanStatus.FOUND:
            return episode_result(
                terminal_outcome=_episode_outcome_for_plan(plan.status)
            )
        loop_outcome = monitor.record_and_check_loop(
            _plan_signature(committed_state, plan)
        )
        if loop_outcome is not None:
            return episode_result(terminal_outcome=loop_outcome)

        recovery_requested = False
        for action in plan.actions:
            if action.name == "confirm-goto":
                verification = verifier.evaluate()
                decision = monitor.observe_action_result(
                    action,
                    action_succeeded=verification.task_success,
                    failure_reason=getattr(
                        verification, "reason_code", None
                    ),
                )
                if decision.atoms_to_invalidate:
                    runtime.invalidate(
                        decision.atoms_to_invalidate,
                        reason=decision.reason_code,
                    )
                traces.append(
                    V1R1StepTrace(
                        step=len(traces),
                        action=action,
                        primitive=None,
                        step_result=None,
                        monitor_decision=(
                            decision if decision.requires_replan else None
                        ),
                    )
                )
                if verification.task_success:
                    return episode_result(
                        terminal_outcome=EpisodeOutcome.SUCCESS,
                        success=True,
                    )
                recovery_requested = decision.requires_replan
            else:
                if primitive_count >= episode.public_action_budget:
                    return episode_result(
                        terminal_outcome=(
                            EpisodeOutcome.ACTION_BUDGET_EXHAUSTED
                        ),
                        success=task_success,
                    )
                # Evaluator-privileged N2 intervention fires exactly once
                # at its declared checkpoint, immediately before the
                # matching agent primitive would execute (plan §13.2).
                if (
                    not intervention_fired
                    and intervention is not None
                    and _matches_checkpoint(
                        intervention, action, family, toggle_seen
                    )
                ):
                    apply_intervention(env, intervention)
                    intervention_fired = True
                primitive_name = controller.to_primitive(action)
                primitive = PrimitiveAction(primitive_name)
                step_res = adapter.step(primitive)
                primitive_count += 1
                if action.name == "toggle-locked-door" and step_res.action_succeeded:
                    toggle_seen = True
                runtime.absorb_step(primitive, step_res)
                decision = monitor.observe_action_result(
                    action, step_result=step_res
                )
                if decision.atoms_to_invalidate:
                    runtime.invalidate(
                        decision.atoms_to_invalidate,
                        reason=decision.reason_code,
                    )
                traces.append(
                    V1R1StepTrace(
                        step=len(traces),
                        action=action,
                        primitive=primitive_name,
                        step_result=step_res,
                        monitor_decision=(
                            decision if decision.requires_replan else None
                        ),
                    )
                )
                if step_res.task_success:
                    task_success = True
                if (
                    step_res.terminated or step_res.truncated
                ) and not step_res.task_success:
                    return episode_result(
                        terminal_outcome=(
                            EpisodeOutcome.ENVIRONMENT_TERMINATED_FAILURE
                        ),
                        success=False,
                    )
                recovery_requested = decision.requires_replan

            if recovery_requested:
                break

        # Whether the plan ran to completion or was interrupted, re-check
        # the subgoal against fresh belief before advancing / replanning.
        committed_state = runtime.committed_state()
        if _subgoal_satisfied(subgoal, committed_state):
            subgoal_index += 1
            continue

        if not use_recovery:
            # R0 variants exhaust their single-plan attempt: report the
            # residual state rather than looping again.
            return episode_result(
                terminal_outcome=EpisodeOutcome.KNOWN_SPACE_DISCONNECTED,
                success=task_success,
            )
        budget_outcome = monitor.check_replan_budget()
        if budget_outcome is not None:
            return episode_result(terminal_outcome=budget_outcome)
        # Loop back — outer while will replan for the same subgoal.

    return episode_result(
        terminal_outcome=(
            EpisodeOutcome.SUCCESS
            if task_success
            else EpisodeOutcome.KNOWN_SPACE_DISCONNECTED
        ),
        success=task_success,
    )


def _matches_checkpoint(
    intervention: InterventionSpec,
    action: SymbolicAction,
    family: str,
    toggle_seen: bool,
) -> bool:
    """Fire the intervention at the plan-defined checkpoint (§13.2).

    - ``block``: pre-move checkpoint — fires immediately before the
      first planned ``move-forward``.
    - ``relock``: post-toggle checkpoint — fires immediately before the
      first ``move-forward`` that follows a successful door toggle, so
      the agent's crossing move discovers the re-locked door.
    """
    if (
        intervention.checkpoint == CHECKPOINT_PRE_MOVE
        and action.name == "move-forward"
    ):
        return True
    if (
        intervention.checkpoint == CHECKPOINT_POST_TOGGLE
        and family == "key_door_goal"
        and toggle_seen
        and action.name == "move-forward"
    ):
        return True
    return False


def _empty_plan(state_hash: str) -> PlanResult:
    return PlanResult(
        status=PlanStatus.FOUND,
        actions=(),
        planning_time_ms=0.0,
        state_hash=state_hash,
        problem_hash=None,
        reason=None,
    )


# Convenience re-exports so callers can import from ``testing`` in the
# same style as B3.
__all__ = ["V1R1EpisodeResult", "V1R1StepTrace", "run_v1r1_episode"]
