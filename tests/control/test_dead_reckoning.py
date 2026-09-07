from neuro_symbolic_vln.contracts import (
    CategoricalView,
    EpisodeSpec,
    GroundAtom,
    ObservationPacket,
    PrimitiveAction,
    StepResult,
)
from neuro_symbolic_vln.control.controller import (
    DeadReckoningTracker,
    LocalPose,
)
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
        observation_id="ep-1:1",
        step=step,
        categorical_view=CategoricalView(cells_by_x=()),
        heading=heading,
        carried_entity=carried,
        instruction="go",
    )


def _make_result(
    observation: ObservationPacket, action_succeeded: bool
) -> StepResult:
    return StepResult(
        observation=observation,
        action_succeeded=action_succeeded,
        failure_reason=None if action_succeeded else "blocked",
        task_success=False,
        terminated=False,
        truncated=False,
    )


def test_reset_establishes_local_origin() -> None:
    tracker = DeadReckoningTracker(episode_id="ep-1")

    evidence = tracker.reset(_make_packet(heading="east"))

    assert tracker.pose() == LocalPose(0, 0, "east", "loc_0")
    atoms = {(e.atom, e.polarity) for e in evidence}
    assert (GroundAtom("robot-at", ("robot", "loc_0")), True) in atoms
    assert (GroundAtom("facing", ("robot", "east")), True) in atoms
    assert (GroundAtom("handempty", ("robot",)), True) in atoms


def test_successful_move_advances_pose_once() -> None:
    tracker = DeadReckoningTracker(episode_id="ep-1")
    tracker.reset(_make_packet(heading="east"))
    target_id = tracker.location_id((1, 0))

    evidence = tracker.step(
        PrimitiveAction("move_forward"),
        _make_result(_make_packet(step=1), action_succeeded=True),
    )

    assert tracker.pose() == LocalPose(1, 0, "east", target_id)
    atoms = {(e.atom, e.polarity) for e in evidence}
    assert (GroundAtom("robot-at", ("robot", "loc_0")), False) in atoms
    assert (GroundAtom("robot-at", ("robot", target_id)), True) in atoms


def test_blocked_move_leaves_pose_unchanged() -> None:
    tracker = DeadReckoningTracker(episode_id="ep-1")
    tracker.reset(_make_packet(heading="east"))

    evidence = tracker.step(
        PrimitiveAction("move_forward"),
        _make_result(_make_packet(step=1), action_succeeded=False),
    )

    assert tracker.pose() == LocalPose(0, 0, "east", "loc_0")
    assert all(e.atom.predicate != "robot-at" for e in evidence)


def test_turn_updates_heading_only() -> None:
    tracker = DeadReckoningTracker(episode_id="ep-1")
    tracker.reset(_make_packet(heading="east"))

    evidence = tracker.step(
        PrimitiveAction("turn_left"),
        _make_result(_make_packet(heading="north", step=1), action_succeeded=True),
    )

    assert tracker.pose() == LocalPose(0, 0, "north", "loc_0")
    atoms = {(e.atom, e.polarity) for e in evidence}
    assert (GroundAtom("facing", ("robot", "east")), False) in atoms
    assert (GroundAtom("facing", ("robot", "north")), True) in atoms


def test_pickup_and_drop_feedback_maps() -> None:
    tracker = DeadReckoningTracker(episode_id="ep-1")
    tracker.reset(_make_packet())

    pickup = tracker.step(
        PrimitiveAction("pickup"),
        _make_result(_make_packet(carried="red:key", step=1), action_succeeded=True),
    )
    atoms = {(e.atom, e.polarity) for e in pickup}
    assert (GroundAtom("handempty", ("robot",)), False) in atoms
    assert (GroundAtom("holding", ("robot", "red-key")), True) in atoms

    drop = tracker.step(
        PrimitiveAction("drop"),
        _make_result(_make_packet(carried=None, step=2), action_succeeded=True),
    )
    atoms = {(e.atom, e.polarity) for e in drop}
    assert (GroundAtom("holding", ("robot", "red-key")), False) in atoms
    assert (GroundAtom("handempty", ("robot",)), True) in atoms


def test_location_ids_are_stable() -> None:
    tracker = DeadReckoningTracker(episode_id="ep-1")
    tracker.reset(_make_packet())

    assert tracker.location_id((0, 0)) == "loc_0"
    first = tracker.location_id((1, 0))
    assert first.startswith("loc_")
    assert tracker.location_id((1, 0)) == first


def test_integration_blocked_then_successful_move() -> None:
    episode = EpisodeSpec(
        episode_id="integration",
        family="probe",
        instruction="open the door",
        public_action_budget=32,
        manifest_hash="test",
    )
    env = make_locked_door_probe_env()
    adapter = MiniGridAdapter(
        env,
        episode,
        GoToVerifier(target_position=(4, 1), env=env),
    )
    tracker = DeadReckoningTracker(episode_id=episode.episode_id)

    tracker.reset(adapter.reset(seed=0))

    # A key on the ground blocks forward movement in MiniGrid 3.1.0.
    blocked = adapter.step(PrimitiveAction("move_forward"))
    tracker.step(PrimitiveAction("move_forward"), blocked)
    assert not blocked.action_succeeded
    assert tracker.pose().location_id == "loc_0"

    picked = adapter.step(PrimitiveAction("pickup"))
    tracker.step(PrimitiveAction("pickup"), picked)
    assert picked.action_succeeded

    moved = adapter.step(PrimitiveAction("move_forward"))
    tracker.step(PrimitiveAction("move_forward"), moved)
    assert moved.action_succeeded
    assert tracker.pose().location_id != "loc_0"

    # The decoder turns the fresh view into door evidence, with locations
    # resolved through the same registry the tracker owns.
    view_evidence = decode_view(
        moved.observation,
        episode.episode_id,
        tracker.pose().x,
        tracker.pose().y,
        tracker.location_id,
    )
    door_loc = tracker.location_id((2, 0))
    door_at = [
        e
        for e in view_evidence
        if e.atom.predicate == "door-at"
        and e.atom.arguments == ("red-door", door_loc)
        and e.polarity
    ]
    assert door_at
    assert any(
        e.atom.predicate == "door-locked" and e.polarity
        for e in view_evidence
    )
