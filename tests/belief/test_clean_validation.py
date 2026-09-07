"""Clean validation regression tests from Member A fixtures and contracts.

Verifies that clean perception observations pass through StandardValidator,
commit_true_facts, build_committed_planning_state, and serialize_problem cleanly.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pyperplan.pddl.parser import Parser

from neuro_symbolic_vln.belief.validator import (
    StandardValidator,
    build_committed_planning_state,
    commit_true_facts,
)
from neuro_symbolic_vln.contracts import (
    CategoricalCell,
    CategoricalView,
    GroundAtom,
    ObservationPacket,
    ValidationDisposition,
)
from neuro_symbolic_vln.perception.observation_decoder import decode_view
from neuro_symbolic_vln.planning.location_graph import LocationGraphBuilder
from neuro_symbolic_vln.planning.problem_serializer import serialize_problem


def _get_domain_path() -> Path:
    domain_path = (
        Path(__file__).resolve().parent.parent.parent
        / "src"
        / "neuro_symbolic_vln"
        / "planning"
        / "domain.pddl"
    )
    assert domain_path.exists()
    return domain_path


def _make_cell(
    object_index: int,
    color_index: int = 0,
    state_index: int = 0,
    visible: bool = True,
) -> CategoricalCell:
    return CategoricalCell(
        object_index=object_index,
        color_index=color_index,
        state_index=state_index,
        visible=visible,
    )


def _make_view(
    object_index: int = 1,
    visible: bool = True,
    overrides: dict[tuple[int, int], CategoricalCell] | None = None,
) -> CategoricalView:
    overrides = overrides or {}
    columns = []
    for x in range(7):
        column = [
            overrides.get((x, y), _make_cell(object_index, visible=visible))
            for y in range(7)
        ]
        columns.append(tuple(column))
    return CategoricalView(cells_by_x=tuple(columns))


def _make_packet(
    view: CategoricalView, heading: str = "east", step: int = 0
) -> ObservationPacket:
    return ObservationPacket(
        observation_id="ep-clean:0",
        step=step,
        categorical_view=view,
        heading=heading,
        carried_entity=None,
        instruction="go to target",
    )


def _resolve(xy: tuple[int, int]) -> str:
    return f"loc-{xy[0]}_{xy[1]}"


def test_clean_perception_evidence_validation_and_commitment() -> None:
    """Clean visible environment: empty floor, key, door, and wall."""
    overrides = {
        (3, 4): _make_cell(5, color_index=0),  # red key
        (3, 5): _make_cell(4, color_index=0, state_index=2),  # locked red door
        (2, 5): _make_cell(2),  # wall
    }
    view = _make_view(overrides=overrides)
    packet = _make_packet(view, heading="east", step=0)

    # 1. Perception decoding
    evidence = decode_view(packet, "ep-clean", 0, 0, _resolve)
    assert len(evidence) > 0

    # 2. Validation with StandardValidator
    validator = StandardValidator()
    decisions = validator.validate(evidence, belief={}, current_step=0)

    assert len(decisions) == len(evidence)
    # All clean perception evidence must be accepted
    # (either clean fact or negative assertion)
    assert all(d.disposition is ValidationDisposition.ACCEPTED for d in decisions)

    # 3. Commit true facts
    evidence_by_id = {e.evidence_id: e for e in evidence}
    true_facts = commit_true_facts(decisions, evidence_by_id)

    # Only positive facts are committed
    assert any(a.predicate == "passable" for a in true_facts)
    assert any(a.predicate == "key-at" for a in true_facts)
    assert any(a.predicate == "door-at" for a in true_facts)
    assert any(a.predicate == "door-locked" for a in true_facts)

    # 4. Build CommittedPlanningState
    builder = LocationGraphBuilder()
    builder.add_edge("loc-0_0", "east", "loc-1_0")
    location_graph = builder.build()

    committed_state = build_committed_planning_state(
        version=1,
        true_facts=true_facts,
        location_graph=location_graph,
        provenance_by_fact={a: (f"ev-{i}",) for i, a in enumerate(true_facts)},
    )
    assert committed_state.version == 1
    assert len(committed_state.state_hash) == 64

    # 5. Serialize to PDDL problem and verify parseability by pyperplan
    problem_str = serialize_problem(
        committed_state, goal_atom=GroundAtom("task-satisfied", ())
    )

    domain_path = _get_domain_path()
    parser = Parser(str(domain_path))
    dom = parser.parse_domain()
    with tempfile.NamedTemporaryFile("w", suffix=".pddl") as tmp:
        tmp.write(problem_str)
        tmp.flush()
        parser.set_prob_file(tmp.name)
        prob = parser.parse_problem(dom)
        assert prob.name == "current-state"
