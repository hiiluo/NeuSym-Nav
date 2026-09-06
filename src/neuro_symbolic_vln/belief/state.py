from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from neuro_symbolic_vln.contracts import (
    BeliefRecord,
    Evidence,
    GroundAtom,
    TriValue,
)


class BeliefMap:
    """Tri-valued belief state tracking ground atoms, staleness, conflicts,
    and provenance.
    """

    def __init__(self) -> None:
        self._records: dict[GroundAtom, BeliefRecord] = {}
        self._stale_limits: dict[GroundAtom, int | None] = {}

    def get(self, atom: GroundAtom) -> BeliefRecord:
        """Return BeliefRecord of an atom, defaulting to UNKNOWN if unseen."""
        return self._records.get(
            atom,
            BeliefRecord(
                value=TriValue.UNKNOWN,
                reliability=None,
                last_observed_step=None,
                stale=False,
                evidence_ids=(),
                conflict_reason=None,
            ),
        )

    def records(self) -> dict[GroundAtom, BeliefRecord]:
        """Return a snapshot of all currently tracked records."""
        return dict(self._records)

    def merge(self, evidence: Evidence) -> None:
        """Merge a new evidence item into the belief map."""
        current = self.get(evidence.atom)
        new_val = TriValue.TRUE if evidence.polarity else TriValue.FALSE

        if evidence.stale_after_steps is not None:
            self._stale_limits[evidence.atom] = evidence.stale_after_steps

        # Check for contradiction:
        # Same-step contradictory polarities represent an irreconcilable conflict.
        is_same_step = (
            current.last_observed_step is not None
            and current.last_observed_step == evidence.observed_step
        )
        is_contradiction = (
            is_same_step
            and current.value in (TriValue.TRUE, TriValue.FALSE)
            and current.value != new_val
        ) or (
            is_same_step
            and current.conflict_reason == "contradictory_polarity"
        )

        if is_contradiction:
            merged_ids = tuple(
                sorted(set(current.evidence_ids + (evidence.evidence_id,)))
            )
            prior_rel = (
                current.reliability if current.reliability is not None else 1.0
            )
            self._records[evidence.atom] = BeliefRecord(
                value=TriValue.UNKNOWN,
                reliability=min(prior_rel, evidence.reliability),
                last_observed_step=evidence.observed_step,
                stale=False,
                evidence_ids=merged_ids,
                conflict_reason="contradictory_polarity",
            )
            return

        # Not a contradiction:
        # Transitioning to a different truth value at a newer step resets
        # the supporting evidence to the new observation.
        if (
            current.value in (TriValue.TRUE, TriValue.FALSE)
            and current.value != new_val
            and current.last_observed_step is not None
            and evidence.observed_step > current.last_observed_step
        ):
            merged_ids = (evidence.evidence_id,)
        else:
            merged_ids = tuple(
                sorted(set(current.evidence_ids + (evidence.evidence_id,)))
            )

        self._records[evidence.atom] = BeliefRecord(
            value=new_val,
            reliability=evidence.reliability,
            last_observed_step=evidence.observed_step,
            stale=False,
            evidence_ids=merged_ids,
            conflict_reason=None,
        )

    def merge_all(self, evidences: Sequence[Evidence]) -> None:
        """Merge a sequence of evidence items."""
        for ev in evidences:
            self.merge(ev)

    def update_staleness(self, current_step: int) -> None:
        """Mark dynamic facts whose age exceeds their declared limit as stale."""
        for atom, record in list(self._records.items()):
            limit = self._stale_limits.get(atom)
            if limit is not None and record.last_observed_step is not None:
                if current_step - record.last_observed_step >= limit:
                    self._records[atom] = BeliefRecord(
                        value=record.value,
                        reliability=record.reliability,
                        last_observed_step=record.last_observed_step,
                        stale=True,
                        evidence_ids=record.evidence_ids,
                        conflict_reason=record.conflict_reason,
                    )

    def invalidate(
        self,
        atom: GroundAtom,
        reason: str = "action_feedback_failure",
    ) -> None:
        """Invalidate an affected fact (e.g. upon action failure) to UNKNOWN."""
        current = self.get(atom)
        self._records[atom] = BeliefRecord(
            value=TriValue.UNKNOWN,
            reliability=current.reliability,
            last_observed_step=current.last_observed_step,
            stale=current.stale,
            evidence_ids=current.evidence_ids,
            conflict_reason=reason,
        )

    def state_hash(self) -> str:
        """Compute a deterministic SHA-256 hash of the current belief state."""
        items = []
        for atom in sorted(self._records.keys()):
            rec = self._records[atom]
            items.append((
                atom.predicate,
                atom.arguments,
                rec.value.value,
                rec.stale,
                rec.conflict_reason or "",
                sorted(rec.evidence_ids),
            ))
        payload = json.dumps(items, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def __contains__(self, atom: GroundAtom) -> bool:
        return atom in self._records

    def __len__(self) -> int:
        return len(self._records)
