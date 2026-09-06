from __future__ import annotations

from neuro_symbolic_vln.belief.evidence import EvidenceStore
from neuro_symbolic_vln.contracts import Evidence, GroundAtom, Provenance


def _make_evidence(
    evidence_id: str,
    predicate: str = "passable",
    args: tuple[str, ...] = ("loc_0",),
    polarity: bool = True,
    reliability: float = 1.0,
    observed_step: int = 0,
    stale_after_steps: int | None = None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        atom=GroundAtom(predicate, args),
        polarity=polarity,
        reliability=reliability,
        observed_step=observed_step,
        stale_after_steps=stale_after_steps,
        source="test_source",
        provenance=Provenance(
            episode_id="ep-1",
            observation_id=f"obs-{observed_step}",
            sensor_model_id="test_sensor",
            local_cell=None,
            corruption_channel=None,
        ),
    )


def test_evidence_store_init_is_empty() -> None:
    store = EvidenceStore()
    assert store.snapshot() == ()
    assert len(store) == 0


def test_evidence_store_append_and_snapshot() -> None:
    store = EvidenceStore()
    ev1 = _make_evidence("ev-1", observed_step=0)
    ev2 = _make_evidence("ev-2", observed_step=1)

    store.append((ev1, ev2))

    snap = store.snapshot()
    assert len(snap) == 2
    assert snap[0] == ev1
    assert snap[1] == ev2
    assert len(store) == 2


def test_evidence_store_preserves_order_and_no_loss() -> None:
    store = EvidenceStore()
    evidences = tuple(
        _make_evidence(f"ev-{i}", observed_step=i) for i in range(10)
    )

    # Append in two separate batches
    store.append(evidences[:5])
    store.append(evidences[5:])

    snap = store.snapshot()
    assert snap == evidences
    assert len(snap) == 10


def test_evidence_store_snapshot_immutability() -> None:
    store = EvidenceStore()
    ev1 = _make_evidence("ev-1")
    store.append((ev1,))

    snap1 = store.snapshot()
    assert len(snap1) == 1

    # Appending more evidence does not alter previously taken snapshot
    ev2 = _make_evidence("ev-2")
    store.append((ev2,))

    assert len(snap1) == 1
    snap2 = store.snapshot()
    assert len(snap2) == 2
    assert snap2[0] == ev1
    assert snap2[1] == ev2
