from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass

from neuro_symbolic_vln.contracts import EpisodeOutcome, LocationGraph

_HEADINGS = ("north", "east", "south", "west")


@dataclass(frozen=True)
class FrontierCandidate:
    location_id: str
    plan_length: int
    discovered_step: int


def select_frontier(
    candidates: tuple[FrontierCandidate, ...],
) -> FrontierCandidate:
    """Deterministic frontier tie-break (plan §12.2):

    1. shortest known primitive plan;
    2. earliest discovery step;
    3. lexicographic LocationId.
    """
    if not candidates:
        raise ValueError("frontier set is empty")
    return min(
        candidates,
        key=lambda item: (item.plan_length, item.discovered_step, item.location_id),
    )


@dataclass(frozen=True)
class Frontier:
    """A known traversable location with unobserved neighbouring headings."""

    location_id: str
    unobserved_headings: frozenset[str]


def extract_frontiers(
    graph: LocationGraph,
    traversable: frozenset[str],
) -> dict[str, frozenset[str]]:
    """Frontier extraction (plan §12.1): every known traversable node with
    at least one heading whose front-cell edge is absent from the graph.

    The internal map convention: nodes and edges only exist for locations
    that have actually been observed, so a missing edge means the
    neighbour is unknown.
    """
    edges = {(source, heading) for source, heading, _ in graph.directed_edges}
    frontiers: dict[str, frozenset[str]] = {}
    for location in sorted(traversable):
        unobserved = frozenset(
            heading for heading in _HEADINGS if (location, heading) not in edges
        )
        if unobserved:
            frontiers[location] = unobserved
    return frontiers


class FrontierExplorer:
    """Deterministic frontier selection with one-sweep-per-visit memory."""

    def __init__(self) -> None:
        self._discovered_step: dict[str, int] = {}
        self._swept_headings: dict[str, frozenset[str]] = {}

    def register(self, location_id: str, step: int) -> None:
        """Record when a location entered the known map (idempotent)."""
        if location_id not in self._discovered_step:
            self._discovered_step[location_id] = step

    def next_frontier(
        self,
        traversable: frozenset[str],
        unobserved_headings: Mapping[str, frozenset[str]],
        plan_lengths: Mapping[str, int],
        step: int,
    ) -> tuple[Frontier | None, EpisodeOutcome | None]:
        """Return the next frontier to explore, or typed exhaustion."""
        for location_id in traversable:
            self.register(location_id, step)
        candidates = tuple(
            FrontierCandidate(
                # Need further checking because 0 may mean no plan,
                # but we want to include it in the candidates. Really?
                location_id=location_id,
                plan_length=plan_lengths.get(location_id, 0),
                discovered_step=self._discovered_step[location_id],
            )
            for location_id in traversable
            if unobserved_headings.get(location_id, frozenset())
        )
        if not candidates:
            return None, EpisodeOutcome.FRONTIER_EXHAUSTED
        chosen = select_frontier(candidates)
        return (
            Frontier(
                location_id=chosen.location_id,
                unobserved_headings=frozenset(
                    unobserved_headings[chosen.location_id]
                ),
            ),
            None,
        )

    def sweep_headings(self, frontier: Frontier) -> tuple[str, ...]:
        """Heading bins to observe at this frontier, in a fixed order.

        Returns empty when this visit has nothing new: a sweep is never
        repeated unless new unobserved headings appeared (state change).
        """
        already = self._swept_headings.get(frontier.location_id, frozenset())
        return tuple(
            heading
            for heading in sorted(frontier.unobserved_headings)
            if heading not in already
        )

    def mark_swept(self, location_id: str, headings: Collection[str]) -> None:
        """Record a completed heading sweep at a visited frontier."""
        already = self._swept_headings.get(location_id, frozenset())
        self._swept_headings[location_id] = already | frozenset(headings)
