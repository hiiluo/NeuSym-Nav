"""Agent orchestration for Neuro-Symbolic VLN."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from neuro_symbolic_vln.contracts import (
    CommittedPlanningState,
    EpisodeOutcome,
    EpisodeSpec,
    GoalProgram,
    GroundAtom,
    PlanResult,
    PlanStatus,
    PrimitiveAction,
    StepResult,
    SymbolicAction,
)
from neuro_symbolic_vln.control.controller import MiniGridController
from neuro_symbolic_vln.control.monitor import ExecutionMonitor, MonitorDecision
from neuro_symbolic_vln.env.base import TaskVerifier
from neuro_symbolic_vln.env.minigrid_adapter import MiniGridAdapter
from neuro_symbolic_vln.env.tasks import (
    make_goto_goal_probe_env,
    make_locked_door_probe_env,
)
from neuro_symbolic_vln.env.verifier import GoToVerifier
from neuro_symbolic_vln.planning.location_graph import LocationGraphBuilder
from neuro_symbolic_vln.planning.problem_serializer import serialize_problem
from neuro_symbolic_vln.planning.pyperplan_adapter import (
    PlannerConfig,
    plan_with_timeout,
)

_DEFAULT_DOMAIN_PATH = str(Path(__file__).parent / "planning" / "domain.pddl")

_DIRECTION_TO_HEADING = {
    0: "east",
    1: "south",
    2: "west",
    3: "north",
}


@dataclass(frozen=True)
class B3StepTrace:
    step: int
    action: SymbolicAction
    primitive: str | None
    step_result: StepResult | None
    monitor_decision: MonitorDecision | None
    oracle_input: bool = True


@dataclass(frozen=True)
class B3EpisodeResult:
    episode_id: str
    family: str
    seed: int
    plan: PlanResult
    terminal_outcome: EpisodeOutcome | None
    replan_count: int
    task_success: bool
    untyped_failures: bool
    oracle_input: bool
    traces: tuple[B3StepTrace, ...]
    step_count: int


def plan_committed_state(
    state: CommittedPlanningState,
    goal: GroundAtom | GoalProgram,
    domain_path: str = _DEFAULT_DOMAIN_PATH,
    config: PlannerConfig | None = None,
) -> PlanResult:
    """Serializes a committed state to PDDL and computes a bounded plan."""
    if isinstance(goal, GoalProgram):
        if not goal.ordered_subgoals:
            raise ValueError("GoalProgram must contain at least one subgoal.")
        # In classical planning, the terminal subgoal represents the ultimate objective.
        goal_atom = goal.ordered_subgoals[-1]
    else:
        goal_atom = goal

    pddl_problem_str = serialize_problem(state, goal_atom)

    plan_result = plan_with_timeout(
        state=state,
        domain_path=domain_path,
        problem_string=pddl_problem_str,
        config=config or PlannerConfig(timeout_seconds=2.0, search="bfs"),
    )

    return plan_result


def _episode_outcome_for_plan(status: PlanStatus) -> EpisodeOutcome:
    if status is PlanStatus.TIMEOUT:
        return EpisodeOutcome.PLANNER_TIMEOUT
    if status in (PlanStatus.PLANNER_ERROR, PlanStatus.SERIALIZATION_ERROR):
        return EpisodeOutcome.PLANNER_ERROR
    return EpisodeOutcome.KNOWN_SPACE_DISCONNECTED


def extract_oracle_committed_state(
    env: Any,
    verifier: TaskVerifier | None = None,
    *,
    version: int = 1,
) -> CommittedPlanningState:
    """Privileged extractor for B3 baseline only: constructs CommittedPlanningState
    directly from true env state.
    """
    unwrapped: Any = env.unwrapped
    width, height = unwrapped.width, unwrapped.height
    agent_pos = unwrapped.agent_pos
    agent_dir = int(unwrapped.agent_dir)
    heading = _DIRECTION_TO_HEADING[agent_dir]

    builder = LocationGraphBuilder()
    for x in range(1, width - 1):
        for y in range(1, height - 1):
            obj = unwrapped.grid.get(x, y)
            if obj is not None and obj.type == "wall":
                continue
            builder.add_node(f"loc-{x}-{y}")

    for x in range(1, width - 1):
        for y in range(1, height - 1):
            loc_id = f"loc-{x}-{y}"
            if loc_id not in builder._nodes:
                continue
            for h_name, (dx, dy) in (
                ("east", (1, 0)),
                ("south", (0, 1)),
                ("west", (-1, 0)),
                ("north", (0, -1)),
            ):
                nx, ny = x + dx, y + dy
                neighbor_id = f"loc-{nx}-{ny}"
                if neighbor_id in builder._nodes:
                    builder.add_edge(loc_id, h_name, neighbor_id)

    graph = builder.build()

    true_facts: set[GroundAtom] = set()
    robot_loc = f"loc-{agent_pos[0]}-{agent_pos[1]}"
    true_facts.add(GroundAtom("robot-at", ("robot", robot_loc)))
    true_facts.add(GroundAtom("facing", ("robot", heading)))

    if unwrapped.carrying is None:
        true_facts.add(GroundAtom("handempty", ("robot",)))
    else:
        c = unwrapped.carrying
        true_facts.add(GroundAtom("holding", ("robot", f"{c.color}-{c.type}")))

    for x in range(1, width - 1):
        for y in range(1, height - 1):
            loc_id = f"loc-{x}-{y}"
            if loc_id not in graph.nodes:
                continue
            obj = unwrapped.grid.get(x, y)
            if obj is None or obj.type == "floor":
                true_facts.add(GroundAtom("passable", (loc_id,)))
            elif obj.type == "key":
                k_id = f"{obj.color}-key"
                true_facts.add(GroundAtom("key-at", (k_id, loc_id)))
                true_facts.add(GroundAtom("passable", (loc_id,)))
            elif obj.type == "door":
                d_id = f"{obj.color}-door"
                k_id = f"{obj.color}-key"
                true_facts.add(GroundAtom("door-at", (d_id, loc_id)))
                true_facts.add(GroundAtom("key-opens", (k_id, d_id)))
                if obj.is_locked:
                    true_facts.add(GroundAtom("door-locked", (d_id,)))
                elif obj.is_open:
                    true_facts.add(GroundAtom("door-open", (d_id,)))
                    true_facts.add(GroundAtom("passable", (loc_id,)))
                else:
                    true_facts.add(GroundAtom("passable", (loc_id,)))
            elif obj.type in ("ball", "box"):
                t_id = f"{obj.color}-{obj.type}"
                true_facts.add(GroundAtom("target-at", (t_id, loc_id)))
            elif obj.type == "goal":
                true_facts.add(GroundAtom("target-at", ("target-goal", loc_id)))
                true_facts.add(GroundAtom("passable", (loc_id,)))

    if verifier is not None and hasattr(verifier, "target_position"):
        tx, ty = verifier.target_position
        target_loc = f"loc-{tx}-{ty}"
        target_obj = unwrapped.grid.get(tx, ty)
        if target_obj is not None:
            t_name = f"{target_obj.color}-{target_obj.type}"
        else:
            t_name = "target-1"
        true_facts.add(GroundAtom("target-at", (t_name, target_loc)))

    fact_payload = "\n".join(
        f"{atom.predicate}({','.join(atom.arguments)})" for atom in sorted(true_facts)
    )
    state_bytes = f"{agent_pos}:{agent_dir}\n{fact_payload}".encode()
    state_hash = hashlib.sha256(state_bytes).hexdigest()

    return CommittedPlanningState(
        version=version,
        state_hash=state_hash,
        true_facts=frozenset(true_facts),
        unresolved_required_facts=frozenset(),
        provenance_by_fact={},
        location_graph=graph,
    )


def run_b3_episode(
    seed: int = 0,
    family: str = "key_door_goal",
    config: PlannerConfig | None = None,
) -> B3EpisodeResult:
    """Executes a single B3 episode using oracle state and symbolic planning."""
    episode_id = f"b3-{family}-seed-{seed}"

    # 1. Instantiate environment and verifier by family
    env: Any
    if family == "key_door_goal":
        env = make_locked_door_probe_env(agent_dir=seed % 4)
        verifier = GoToVerifier(target_position=(4, 1), env=env)
        instruction = "pick up the red key, open the red door, then go to the goal"
    elif family == "goto_type_color":
        env = make_goto_goal_probe_env(agent_dir=seed % 4)
        verifier = GoToVerifier(target_position=(3, 1), env=env)
        instruction = "go to the green ball."
    else:
        raise ValueError(f"Unknown task family for B3: {family}")

    episode = EpisodeSpec(
        episode_id=episode_id,
        family=family,
        instruction=instruction,
        public_action_budget=32,
        manifest_hash=f"manifest-{family}-{seed}",
    )

    adapter = MiniGridAdapter(env, episode, verifier)
    adapter.reset(seed=seed)
    monitor = ExecutionMonitor()

    # 2. Extract oracle committed state (B3 privileged baseline exception).
    # Recovery deliberately repeats this extractor; it never enters the normal
    # belief pipeline.
    oracle_state = extract_oracle_committed_state(env, verifier, version=1)

    # 3. Plan using positive STRIPS.
    goal_atom = GroundAtom("task-satisfied", ())
    plan = plan_committed_state(oracle_state, goal_atom, config=config)
    primitive_count = 0

    def episode_result(
        *,
        terminal_outcome: EpisodeOutcome,
        task_success: bool = False,
    ) -> B3EpisodeResult:
        return B3EpisodeResult(
            episode_id=episode_id,
            family=family,
            seed=seed,
            plan=plan,
            terminal_outcome=terminal_outcome,
            replan_count=monitor.replan_count,
            task_success=task_success,
            untyped_failures=False,
            oracle_input=True,
            traces=tuple(traces),
            step_count=primitive_count,
        )

    if plan.status != PlanStatus.FOUND:
        traces: list[B3StepTrace] = []
        return episode_result(terminal_outcome=_episode_outcome_for_plan(plan.status))

    def plan_pose(state: CommittedPlanningState) -> tuple[str, str]:
        robot_at = next(
            atom for atom in state.true_facts if atom.predicate == "robot-at"
        )
        facing = next(atom for atom in state.true_facts if atom.predicate == "facing")
        return robot_at.arguments[1], facing.arguments[1]

    def plan_signature(
        state: CommittedPlanningState, current_plan: PlanResult
    ) -> tuple[str, str, tuple[str, str], str]:
        return (
            "task-satisfied",
            state.state_hash,
            plan_pose(state),
            current_plan.status.value,
        )

    # The initial signature is part of loop detection. Replans append their
    # signatures to the same monitor history, so a third identical state is a
    # loop rather than an unbounded retry.
    traces = []
    initial_loop_outcome = monitor.record_and_check_loop(
        plan_signature(oracle_state, plan)
    )
    if initial_loop_outcome is not None:
        return episode_result(terminal_outcome=initial_loop_outcome)

    # 4. Execute the active plan with a bounded recovery loop.
    controller = MiniGridController()
    task_success = False
    while True:
        recovery_requested = False
        for action in plan.actions:
            if action.name == "confirm-goto":
                # Confirmation is authoritative but emits no primitive.
                verification = verifier.evaluate()
                decision = monitor.observe_action_result(
                    action,
                    action_succeeded=verification.task_success,
                    failure_reason=getattr(verification, "reason_code", None),
                )
                traces.append(
                    B3StepTrace(
                        step=len(traces),
                        action=action,
                        primitive=None,
                        step_result=None,
                        monitor_decision=(
                            decision if decision.requires_replan else None
                        ),
                        oracle_input=True,
                    )
                )
                if verification.task_success:
                    task_success = True
                    return episode_result(
                        terminal_outcome=EpisodeOutcome.SUCCESS,
                        task_success=True,
                    )
                recovery_requested = decision.requires_replan
            else:
                if primitive_count >= episode.public_action_budget:
                    return episode_result(
                        terminal_outcome=EpisodeOutcome.ACTION_BUDGET_EXHAUSTED,
                        task_success=task_success,
                    )

                primitive_name = controller.to_primitive(action)
                step_res = adapter.step(PrimitiveAction(primitive_name))
                primitive_count += 1
                decision = monitor.observe_action_result(action, step_result=step_res)
                traces.append(
                    B3StepTrace(
                        step=len(traces),
                        action=action,
                        primitive=primitive_name,
                        step_result=step_res,
                        monitor_decision=(
                            decision if decision.requires_replan else None
                        ),
                        oracle_input=True,
                    )
                )

                if step_res.task_success:
                    # A successful primitive advances the plan cursor. The
                    # confirmation action remains authoritative and is kept as
                    # the final no-primitive trace in normal B3 episodes.
                    task_success = True
                if (
                    step_res.terminated or step_res.truncated
                ) and not step_res.task_success:
                    return episode_result(
                        terminal_outcome=EpisodeOutcome.ENVIRONMENT_TERMINATED_FAILURE,
                        task_success=False,
                    )
                recovery_requested = decision.requires_replan

            if recovery_requested:
                break

        if not recovery_requested:
            return episode_result(
                terminal_outcome=(
                    EpisodeOutcome.SUCCESS
                    if task_success
                    else EpisodeOutcome.KNOWN_SPACE_DISCONNECTED
                ),
                task_success=task_success,
            )

        budget_outcome = monitor.check_replan_budget()
        if budget_outcome is not None:
            return episode_result(terminal_outcome=budget_outcome)

        # Recovery invariant: re-observe through the privileged extractor,
        # incrementing its semantic version, then plan from that committed state.
        oracle_state = extract_oracle_committed_state(
            env, verifier, version=oracle_state.version + 1
        )
        plan = plan_committed_state(oracle_state, goal_atom, config=config)
        if plan.status != PlanStatus.FOUND:
            return episode_result(
                terminal_outcome=_episode_outcome_for_plan(plan.status)
            )

        loop_outcome = monitor.record_and_check_loop(plan_signature(oracle_state, plan))
        if loop_outcome is not None:
            return episode_result(terminal_outcome=loop_outcome)
        # The outer loop restarts at cursor zero with the new plan.
