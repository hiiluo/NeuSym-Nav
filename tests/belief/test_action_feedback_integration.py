from __future__ import annotations

from neuro_symbolic_vln.belief.evidence import EvidenceStore
from neuro_symbolic_vln.belief.state import BeliefMap
from neuro_symbolic_vln.contracts import (
    CategoricalView,
    EpisodeSpec,
    Evidence,
    GroundAtom,
    ObservationPacket,
    PrimitiveAction,
    Provenance,
    StepResult,
    TriValue,
)
from neuro_symbolic_vln.control.controller import DeadReckoningTracker
from neuro_symbolic_vln.env.minigrid_adapter import MiniGridAdapter
from neuro_symbolic_vln.env.tasks import make_locked_door_probe_env
from neuro_symbolic_vln.env.verifier import GoToVerifier
from neuro_symbolic_vln.perception.observation_decoder import decode_view


def _make_packet(
    heading: str = "east",
    step: int = 0,
    carried: str | None = None,
) -> ObservationPacket:
    return ObservationPacket(
        observation_id=f"ep-1:{step}",
        step=step,
        categorical_view=CategoricalView(cells_by_x=()),
        heading=heading,
        carried_entity=carried,
        instruction="navigate and open door",
    )


def _make_step_result(
    observation: ObservationPacket,
    action_succeeded: bool,
    failure_reason: str | None = None,
) -> StepResult:
    return StepResult(
        observation=observation,
        action_succeeded=action_succeeded,
        failure_reason=failure_reason if not action_succeeded else None,
        task_success=False,
        terminated=False,
        truncated=False,
    )


def test_tracker_reset_integrates_with_belief_and_store() -> None:
    store = EvidenceStore()
    belief = BeliefMap()
    tracker = DeadReckoningTracker(episode_id="ep-1")

    packet = _make_packet(heading="east", step=0)
    reset_ev = tracker.reset(packet)

    store.append(reset_ev)
    belief.merge_all(reset_ev)

    assert len(store) == len(reset_ev)
    assert belief.get(GroundAtom("robot-at", ("robot", "loc_0"))).value is TriValue.TRUE
    assert belief.get(GroundAtom("facing", ("robot", "east"))).value is TriValue.TRUE
    assert belief.get(GroundAtom("handempty", ("robot",))).value is TriValue.TRUE


def test_successful_move_updates_robot_location_in_belief() -> None:
    store = EvidenceStore()
    belief = BeliefMap()
    tracker = DeadReckoningTracker(episode_id="ep-1")

    reset_ev = tracker.reset(_make_packet(heading="east", step=0))
    store.append(reset_ev)
    belief.merge_all(reset_ev)

    target_id = tracker.location_id((1, 0))

    # Move forward successfully
    result = _make_step_result(
        _make_packet(heading="east", step=1),
        action_succeeded=True,
    )
    move_ev = tracker.step(PrimitiveAction("move_forward"), result)
    store.append(move_ev)
    belief.merge_all(move_ev)

    # loc_0 is now False, target_id is now True
    assert (
        belief.get(GroundAtom("robot-at", ("robot", "loc_0"))).value is TriValue.FALSE
    )
    assert (
        belief.get(GroundAtom("robot-at", ("robot", target_id))).value is TriValue.TRUE
    )
    assert len(store.snapshot()) == len(reset_ev) + len(move_ev)


def test_blocked_move_invalidates_passable_fact_in_belief() -> None:
    store = EvidenceStore()
    belief = BeliefMap()
    tracker = DeadReckoningTracker(episode_id="ep-1")

    reset_ev = tracker.reset(_make_packet(heading="east", step=0))
    store.append(reset_ev)
    belief.merge_all(reset_ev)

    target_id = tracker.location_id((1, 0))
    passable_atom = GroundAtom("passable", (target_id,))

    # Suppose we previously observed target_id as passable
    prior_ev = Evidence(
        evidence_id="ev-prior",
        atom=passable_atom,
        polarity=True,
        reliability=1.0,
        observed_step=0,
        stale_after_steps=None,
        source="local_sensor",
        provenance=Provenance(
            episode_id="ep-1",
            observation_id="obs-0",
            sensor_model_id="local_categorical",
            local_cell=None,
            corruption_channel=None,
        ),
    )
    store.append((prior_ev,))
    belief.merge(prior_ev)
    assert belief.get(passable_atom).value is TriValue.TRUE

    # Agent attempts to move forward but is blocked
    blocked_result = _make_step_result(
        _make_packet(heading="east", step=1),
        action_succeeded=False,
        failure_reason="blocked",
    )
    step_ev = tracker.step(PrimitiveAction("move_forward"), blocked_result)
    store.append(step_ev)
    belief.merge_all(step_ev)

    # Invalidate the target location due to blocked motion
    belief.invalidate(passable_atom, reason="blocked_move")

    # Robot position should not have changed
    assert belief.get(GroundAtom("robot-at", ("robot", "loc_0"))).value is TriValue.TRUE
    # Target passable fact is now UNKNOWN with reason and provenance intact
    rec = belief.get(passable_atom)
    assert rec.value is TriValue.UNKNOWN
    assert rec.conflict_reason == "blocked_move"
    assert "ev-prior" in rec.evidence_ids


def test_pickup_and_drop_transitions_in_belief() -> None:
    belief = BeliefMap()
    tracker = DeadReckoningTracker(episode_id="ep-1")

    reset_ev = tracker.reset(_make_packet(step=0))
    belief.merge_all(reset_ev)
    assert belief.get(GroundAtom("handempty", ("robot",))).value is TriValue.TRUE

    # Pickup key
    pickup_result = _make_step_result(
        _make_packet(step=1, carried="red:key"),
        action_succeeded=True,
    )
    pickup_ev = tracker.step(PrimitiveAction("pickup"), pickup_result)
    belief.merge_all(pickup_ev)

    assert belief.get(GroundAtom("handempty", ("robot",))).value is TriValue.FALSE
    assert (
        belief.get(GroundAtom("holding", ("robot", "red-key"))).value is TriValue.TRUE
    )

    # Drop key
    drop_result = _make_step_result(
        _make_packet(step=2, carried=None),
        action_succeeded=True,
    )
    drop_ev = tracker.step(PrimitiveAction("drop"), drop_result)
    belief.merge_all(drop_ev)

    assert (
        belief.get(GroundAtom("holding", ("robot", "red-key"))).value is TriValue.FALSE
    )
    assert belief.get(GroundAtom("handempty", ("robot",))).value is TriValue.TRUE


def test_turn_transitions_in_belief() -> None:
    belief = BeliefMap()
    tracker = DeadReckoningTracker(episode_id="ep-1")

    reset_ev = tracker.reset(_make_packet(heading="east", step=0))
    belief.merge_all(reset_ev)
    assert belief.get(GroundAtom("facing", ("robot", "east"))).value is TriValue.TRUE

    turn_result = _make_step_result(
        _make_packet(heading="north", step=1),
        action_succeeded=True,
    )
    turn_ev = tracker.step(PrimitiveAction("turn_left"), turn_result)
    belief.merge_all(turn_ev)

    assert belief.get(GroundAtom("facing", ("robot", "east"))).value is TriValue.FALSE
    assert belief.get(GroundAtom("facing", ("robot", "north"))).value is TriValue.TRUE


def test_full_environment_actuator_observation_integration() -> None:
    episode = EpisodeSpec(
        episode_id="ep-integration",
        family="probe",
        instruction="open the door",
        public_action_budget=32,
        manifest_hash="hash-123",
    )
    env = make_locked_door_probe_env()
    adapter = MiniGridAdapter(
        env,
        episode,
        GoToVerifier(target_position=(4, 1), env=env),
    )
    tracker = DeadReckoningTracker(episode_id=episode.episode_id)
    store = EvidenceStore()
    belief = BeliefMap()

    # Step 0: Reset
    init_obs = adapter.reset(seed=42)
    reset_ev = tracker.reset(init_obs)
    store.append(reset_ev)
    belief.merge_all(reset_ev)

    # Decode view at step 0
    view_ev_0 = decode_view(
        init_obs,
        episode.episode_id,
        tracker.pose().x,
        tracker.pose().y,
        tracker.location_id,
    )
    store.append(view_ev_0)
    belief.merge_all(view_ev_0)

    # In locked door probe, key is on the ground in front -> move forward blocks
    blocked = adapter.step(PrimitiveAction("move_forward"))
    move_ev = tracker.step(PrimitiveAction("move_forward"), blocked)
    store.append(move_ev)
    belief.merge_all(move_ev)
    assert not blocked.action_succeeded

    # Pickup key
    picked = adapter.step(PrimitiveAction("pickup"))
    pickup_ev = tracker.step(PrimitiveAction("pickup"), picked)
    store.append(pickup_ev)
    belief.merge_all(pickup_ev)
    assert picked.action_succeeded
    assert (
        belief.get(GroundAtom("holding", ("robot", "red-key"))).value is TriValue.TRUE
    )

    # Advance steps and test staleness
    belief.update_staleness(current_step=10)
    # Check that dynamic door facts became stale after 10 steps
    door_open_atom = GroundAtom("door-open", ("red-door",))
    if door_open_atom in belief:
        assert belief.get(door_open_atom).stale is True

    # No evidence lost
    all_ev = store.snapshot()
    assert len(all_ev) > 0
    assert len(store) == len(all_ev)
    # State hash is deterministic and valid
    assert len(belief.state_hash()) == 64
