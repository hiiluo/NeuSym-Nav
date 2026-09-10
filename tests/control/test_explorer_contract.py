"""Contract tests: the explorer consumes only the internal map and never
the simulator, the oracle, or any target-position input (plan §12 + B
cross-validation requirement)."""

import inspect
import subprocess
import sys

from neuro_symbolic_vln.contracts import EpisodeOutcome
from neuro_symbolic_vln.control.explorer import (
    FrontierExplorer,
    extract_frontiers,
)
from neuro_symbolic_vln.planning.location_graph import LocationGraphBuilder


def test_extract_frontiers_from_known_nodes_adjacent_to_unknown() -> None:
    builder = LocationGraphBuilder()
    builder.add_node("loc-a")
    builder.add_node("loc-b")
    builder.add_edge("loc-a", "east", "loc-b")
    builder.add_edge("loc-b", "west", "loc-a")
    graph = builder.build()

    frontiers = extract_frontiers(
        graph, traversable=frozenset({"loc-a", "loc-b"})
    )

    assert frontiers["loc-a"] == frozenset({"north", "south", "west"})
    assert frontiers["loc-b"] == frozenset({"north", "east", "south"})


def test_fully_connected_nodes_are_not_frontiers() -> None:
    builder = LocationGraphBuilder()
    for heading, target in (
        ("north", "loc-n"),
        ("east", "loc-e"),
        ("south", "loc-s"),
        ("west", "loc-w"),
    ):
        builder.add_edge("loc-c", heading, target)
        builder.add_edge(target, "east", "loc-c")
    graph = builder.build()

    frontiers = extract_frontiers(graph, traversable=frozenset({"loc-c"}))

    assert frontiers == {}


def test_explorer_module_does_not_import_evaluation() -> None:
    code = (
        "import sys\n"
        "import neuro_symbolic_vln.control.explorer\n"
        "bad = [\n"
        "    name for name in sys.modules\n"
        "    if name.startswith('neuro_symbolic_vln.evaluation')\n"
        "]\n"
        "assert not bad, f'leaked evaluation modules: {bad}'\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_next_frontier_signature_has_no_target_or_distance_input() -> None:
    parameters = inspect.signature(
        FrontierExplorer.next_frontier
    ).parameters

    assert set(parameters) == {
        "self",
        "traversable",
        "unobserved_headings",
        "plan_lengths",
        "step",
    }


def test_exhausted_outcome_is_typed() -> None:
    explorer = FrontierExplorer()

    _, outcome = explorer.next_frontier(
        traversable=frozenset(),
        unobserved_headings={},
        plan_lengths={},
        step=0,
    )

    assert outcome is EpisodeOutcome.FRONTIER_EXHAUSTED
