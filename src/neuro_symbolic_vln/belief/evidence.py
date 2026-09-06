from __future__ import annotations

from collections.abc import Sequence

from neuro_symbolic_vln.contracts import Evidence


class EvidenceStore:
    """Linear, append-only store preserving all observed evidence without loss."""

    def __init__(self) -> None:
        self._items: list[Evidence] = []

    def append(self, evidence: Sequence[Evidence]) -> None:
        """Append a sequence of Evidence items to the store."""
        self._items.extend(evidence)

    def snapshot(self) -> tuple[Evidence, ...]:
        """Return an immutable snapshot of all recorded evidence."""
        return tuple(self._items)

    def __len__(self) -> int:
        return len(self._items)
