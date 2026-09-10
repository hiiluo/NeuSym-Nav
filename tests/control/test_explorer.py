import pytest

from neuro_symbolic_vln.contracts import EpisodeOutcome
from neuro_symbolic_vln.control.explorer import (
    Frontier,
    FrontierCandidate,
    FrontierExplorer,
    select_frontier,
)


def test_select_frontier_prefers_shorter_plan() -> None:
    candidates = (
        FrontierCandidate("loc-b", plan_length=4, discovered_step=1),
        FrontierCandidate("loc-a", plan_length=2, discovered_step=9),
    )
    assert select_frontier(candidates).location_id == "loc-a"


def test_select_frontier_breaks_ties_by_earliest_discovery() -> None:
    candidates = (
        FrontierCandidate("loc-b", plan_length=2, discovered_step=9),
        FrontierCandidate("loc-a", plan_length=2, discovered_step=3),
    )
    assert select_frontier(candidates).location_id == "loc-a"


def test_select_frontier_breaks_remaining_ties_lexicographically() -> None:
    candidates = (
        FrontierCandidate("loc-z", plan_length=1, discovered_step=5),
        FrontierCandidate("loc-a", plan_length=1, discovered_step=5),
    )
    assert select_frontier(candidates).location_id == "loc-a"


def test_select_frontier_rejects_empty_set() -> None:
    with pytest.raises(ValueError, match="empty"):
        select_frontier(())


def test_exhaustion_returns_typed_outcome() -> None:
    explorer = FrontierExplorer()

    frontier, outcome = explorer.next_frontier(
        traversable=frozenset({"loc-0"}),
        unobserved_headings={},
        plan_lengths={},
        step=0,
    )

    assert frontier is None
    assert outcome is EpisodeOutcome.FRONTIER_EXHAUSTED


def test_one_sweep_per_frontier_visit() -> None:
    explorer = FrontierExplorer()
    frontier = Frontier(
        location_id="loc-1",
        unobserved_headings=frozenset({"north", "east"}),
    )

    assert explorer.sweep_headings(frontier) == ("east", "north")
    explorer.mark_swept("loc-1", ("east", "north"))
    assert explorer.sweep_headings(frontier) == ()

    # A state change (new unobserved heading) permits exactly one new sweep.
    changed = Frontier(
        location_id="loc-1",
        unobserved_headings=frozenset({"north", "east", "south"}),
    )
    assert explorer.sweep_headings(changed) == ("south",)


def test_discovery_step_is_stable_across_calls() -> None:
    explorer = FrontierExplorer()
    explorer.register("loc-1", 4)
    explorer.register("loc-1", 99)

    assert explorer._discovered_step["loc-1"] == 4


def test_initially_unseen_target_becomes_known_after_sweep() -> None:
    """Integration-shaped case: the target location is behind a frontier.

    The explorer sees only the internal map; "observation" in this test
    is the controller feeding new map facts after each sweep.
    """
    explorer = FrontierExplorer()
    traversable = frozenset({"loc-0", "loc-1"})
    unobserved = {"loc-1": frozenset({"east"})}
    plan_lengths = {"loc-1": 2}

    frontier, outcome = explorer.next_frontier(
        traversable, unobserved, plan_lengths, step=0
    )
    assert outcome is None
    assert frontier is not None
    assert frontier.location_id == "loc-1"
    assert explorer.sweep_headings(frontier) == ("east",)
    explorer.mark_swept("loc-1", ("east",))

    # The sweep observes the target location: it enters the known map.
    traversable = traversable | {"loc-2"}
    explorer.register("loc-2", 1)
    unobserved = {"loc-2": frozenset({"east"})}

    frontier, _ = explorer.next_frontier(
        traversable, unobserved, {"loc-2": 1}, step=1
    )
    assert frontier is not None
    assert frontier.location_id == "loc-2"
    assert explorer._discovered_step["loc-2"] == 1

    # After everything is observed, exploration ends with a typed outcome.
    frontier, outcome = explorer.next_frontier(
        traversable, {}, {}, step=2
    )
    assert frontier is None
    assert outcome is EpisodeOutcome.FRONTIER_EXHAUSTED
