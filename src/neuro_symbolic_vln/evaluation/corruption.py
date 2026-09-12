from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Sequence

import numpy as np

from neuro_symbolic_vln.contracts import Evidence, GroundAtom

CORRUPTION_MODEL_VERSION = "1.0"

# Predicates eligible for N1 corruption under Section 13.1:
# - visible occupancy/traversability: passable
# - visible door state: door-open, door-locked
# - visible object type/color: target-at, key-at, door-at, goal-at
ELIGIBLE_PREDICATES = frozenset(
    {
        "passable",
        "door-open",
        "door-locked",
        "door-at",
        "key-at",
        "target-at",
        "goal-at",
    }
)

VALID_COLORS: tuple[str, ...] = ("red", "green", "blue", "purple", "yellow", "grey")
VALID_OBJECTS: tuple[str, ...] = ("key", "ball", "box", "door")


def drop_evidence[T](
    evidence: Sequence[T],
    rate: float = 0.15,
    seed: int = 42,
) -> tuple[T, ...]:
    """Deterministically drop a fraction of evidence without mutating input.

    Corresponds to condition 'N1-DROP-15'.
    Dropped records are omitted from the returned tuple, leading their
    corresponding belief state to remain UNKNOWN.
    """
    if not evidence or rate <= 0.0:
        return tuple(evidence)

    n_total = len(evidence)
    n_drop = round(n_total * rate)
    if n_drop <= 0:
        return tuple(evidence)
    if n_drop >= n_total:
        return ()

    rng = np.random.default_rng(seed)
    drop_indices = set(rng.choice(n_total, size=n_drop, replace=False))

    return tuple(ev for idx, ev in enumerate(evidence) if idx not in drop_indices)


def reliability_score(*, correct: bool, rng: np.random.Generator) -> float:
    """Compute synthetic reliability score using overlapping Beta distributions.

    - correct=True (retained): Beta(8, 2), expected value ~0.80.
    - correct=False (corrupted/flipped): Beta(3, 5), expected value ~0.375.
    - Clipped to [0.05, 0.99] to prevent degenerate boundary probabilities.
    """
    alpha, beta = (8.0, 2.0) if correct else (3.0, 5.0)
    return float(np.clip(rng.beta(alpha, beta), 0.05, 0.99))


def substitute_entity(
    entity: str,
    rng: np.random.Generator,
    colors: tuple[str, ...] = VALID_COLORS,
    objects: tuple[str, ...] = VALID_OBJECTS,
) -> str:
    """Perform typed attribute substitution on '{color}-{object_name}'.

    Produces a valid MiniGrid entity distinct from the original entity.
    """
    parts = entity.split("-", maxsplit=1)
    if len(parts) != 2:
        alt_colors = [c for c in colors if c != entity]
        return str(rng.choice(alt_colors)) if alt_colors else f"alt-{entity}"

    curr_color, curr_obj = parts[0], parts[1]
    flip_color = bool(rng.integers(0, 2))

    if flip_color:
        alt_colors = [c for c in colors if c != curr_color]
        new_color = str(rng.choice(alt_colors)) if alt_colors else curr_color
        return f"{new_color}-{curr_obj}"

    alt_objs = [o for o in objects if o != curr_obj]
    if not alt_objs:
        alt_colors = [c for c in colors if c != curr_color]
        new_color = str(rng.choice(alt_colors)) if alt_colors else curr_color
        return f"{new_color}-{curr_obj}"
    new_obj = str(rng.choice(alt_objs))
    return f"{curr_color}-{new_obj}"


def apply_n1_flip(
    evidence: Sequence[Evidence],
    rate: float = 0.10,
    seed: int = 42,
) -> tuple[tuple[Evidence, ...], dict[str, bool]]:
    """Apply N1-FLIP corruption to eligible visible evidence.

    Returns:
      - corrupted_evidence: Tuple of Evidence items with synthetic reliability scores.
        Publicly exposed to the agent; contains NO hidden correctness labels.
      - hidden_labels: Mapping from evidence_id to bool (True if correct/unflipped).
        Must ONLY be stored in the evaluator-private sidecar.
    """
    rng = np.random.default_rng(seed)

    eligible_indices = [
        idx
        for idx, ev in enumerate(evidence)
        if ev.atom.predicate in ELIGIBLE_PREDICATES
    ]

    n_flip = round(len(eligible_indices) * rate)
    if n_flip > 0 and len(eligible_indices) > 0:
        n_flip = min(n_flip, len(eligible_indices))
        chosen = rng.choice(eligible_indices, size=n_flip, replace=False)
        flip_indices = set(int(idx) for idx in chosen)
    else:
        flip_indices = set()

    corrupted_list: list[Evidence] = []
    hidden_labels: dict[str, bool] = {}

    for idx, ev in enumerate(evidence):
        is_flipped = idx in flip_indices
        is_correct = not is_flipped
        hidden_labels[ev.evidence_id] = is_correct

        score = reliability_score(correct=is_correct, rng=rng)

        atom = ev.atom
        polarity = ev.polarity

        if is_flipped:
            if atom.predicate in ("passable", "door-open", "door-locked"):
                polarity = not polarity
            elif atom.predicate in ("target-at", "key-at", "door-at", "goal-at"):
                new_args = list(atom.arguments)
                if len(new_args) > 0:
                    new_args[0] = substitute_entity(new_args[0], rng)
                    atom = GroundAtom(atom.predicate, tuple(new_args))

        prov = dataclasses.replace(ev.provenance, corruption_channel="N1-FLIP-10")

        corrupted_list.append(
            dataclasses.replace(
                ev,
                atom=atom,
                polarity=polarity,
                reliability=score,
                provenance=prov,
            )
        )

    return tuple(corrupted_list), hidden_labels


def compute_evidence_hash(evidence: Sequence[Evidence]) -> str:
    """Compute deterministic SHA-256 hash for a sequence of evidence items."""
    canonical_items = [
        {
            "evidence_id": ev.evidence_id,
            "predicate": ev.atom.predicate,
            "arguments": list(ev.atom.arguments),
            "polarity": ev.polarity,
            "reliability": round(ev.reliability, 6),
            "observed_step": ev.observed_step,
            "source": ev.source,
        }
        for ev in sorted(evidence, key=lambda e: e.evidence_id)
    ]
    payload = json.dumps(canonical_items, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def apply_corruption(
    evidence: Sequence[Evidence],
    condition: str = "clean",
    seed: int = 42,
) -> tuple[tuple[Evidence, ...], dict[str, bool]]:
    """Dispatch corruption based on condition ('clean', 'N1-DROP-15', 'N1-FLIP-10').

    Returns (corrupted_evidence, hidden_labels).
    """
    if condition == "clean":
        hidden_labels = {ev.evidence_id: True for ev in evidence}
        return tuple(evidence), hidden_labels

    if condition == "N1-DROP-15":
        dropped = drop_evidence(evidence, rate=0.15, seed=seed)
        hidden_labels = {ev.evidence_id: True for ev in dropped}
        return dropped, hidden_labels

    if condition == "N1-FLIP-10":
        return apply_n1_flip(evidence, rate=0.10, seed=seed)

    raise ValueError(f"unsupported corruption condition: {condition}")
