import tempfile
from pathlib import Path

from pyperplan.pddl.parser import Parser

from neuro_symbolic_vln.contracts import (
    CommittedPlanningState,
    GroundAtom,
    LocationGraph,
)
from neuro_symbolic_vln.planning.location_graph import LocationGraphBuilder
from neuro_symbolic_vln.planning.problem_serializer import serialize_problem


def get_domain_path() -> Path:
    domain_path = (
        Path(__file__).resolve().parent.parent.parent
        / "src"
        / "neuro_symbolic_vln"
        / "planning"
        / "domain.pddl"
    )
    return domain_path


def test_serializer_does_not_emit_unknown_as_passable() -> None:
    """Handbook Step 1 regression test: unknowns must never be serialized."""
    state = CommittedPlanningState(
        version=1,
        state_hash="state-1",
        true_facts=frozenset({GroundAtom("robot-at", ("robot", "loc-1"))}),
        unresolved_required_facts=frozenset({GroundAtom("passable", ("loc-2",))}),
        provenance_by_fact={},
        location_graph=LocationGraph(
            nodes=frozenset({"loc-1"}),
            directed_edges=frozenset(),
            frontier_nodes=frozenset({"loc-1"}),
        ),
    )
    problem = serialize_problem(state, goal_atom=GroundAtom("task-satisfied", ()))
    assert "(passable loc-2)" not in problem


def test_serializer_emits_valid_pddl_problem_parseable_by_pyperplan() -> None:
    builder = LocationGraphBuilder()
    builder.add_edge("loc-1", "east", "loc-2")
    graph = builder.build()

    state = CommittedPlanningState(
        version=1,
        state_hash="state-valid",
        true_facts=frozenset(
            {
                GroundAtom("robot-at", ("robot", "loc-1")),
                GroundAtom("facing", ("robot", "east")),
                GroundAtom("passable", ("loc-2",)),
                GroundAtom("handempty", ("robot",)),
            }
        ),
        unresolved_required_facts=frozenset(),
        provenance_by_fact={},
        location_graph=graph,
    )

    problem_str = serialize_problem(
        state, goal_atom=GroundAtom("robot-at", ("robot", "loc-2"))
    )

    assert "(define (problem current-state)" in problem_str
    assert "(:domain vln-minigrid)" in problem_str
    assert "(robot-at robot loc-1)" in problem_str
    assert "(front-cell loc-1 east loc-2)" in problem_str
    assert "(turn-right-of north east)" in problem_str
    assert "(:goal" in problem_str
    assert "(robot-at robot loc-2)" in problem_str

    # Validate with pyperplan Parser
    domain_path = get_domain_path()
    parser = Parser(str(domain_path))
    dom = parser.parse_domain()

    with tempfile.NamedTemporaryFile("w", suffix=".pddl") as tmp:
        tmp.write(problem_str)
        tmp.flush()
        parser.set_prob_file(tmp.name)
        prob = parser.parse_problem(dom)
        assert prob.name == "current-state"


def test_serializer_filters_non_domain_facts_and_normalizes_aliases() -> None:
    builder = LocationGraphBuilder()
    builder.add_edge("loc-1", "east", "loc-2")
    graph = builder.build()

    state = CommittedPlanningState(
        version=1,
        state_hash="state-filter",
        true_facts=frozenset(
            {
                GroundAtom("at", ("robot", "loc-1")),  # alias for robot-at
                GroundAtom("free", ("loc-2",)),  # alias for passable
                GroundAtom("wall", ("loc-9",)),  # non-domain predicate
            }
        ),
        unresolved_required_facts=frozenset(),
        provenance_by_fact={},
        location_graph=graph,
    )

    problem_str = serialize_problem(state, goal_atom=GroundAtom("task-satisfied", ()))

    assert "(robot-at robot loc-1)" in problem_str
    assert "(passable loc-2)" in problem_str
    assert "wall" not in problem_str
    assert "(at " not in problem_str
    assert "(free " not in problem_str

    domain_path = get_domain_path()
    parser = Parser(str(domain_path))
    dom = parser.parse_domain()
    with tempfile.NamedTemporaryFile("w", suffix=".pddl") as tmp:
        tmp.write(problem_str)
        tmp.flush()
        parser.set_prob_file(tmp.name)
        prob = parser.parse_problem(dom)
        assert prob.name == "current-state"
