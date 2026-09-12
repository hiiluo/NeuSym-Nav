from neuro_symbolic_vln.evaluation.statistics import paired_delta

def test_paired_delta_uses_matching_episode_ids() -> None:
    treatment = {"ep-1": 1.0, "ep-2": 0.5}
    control = {"ep-1": 0.5, "ep-2": 0.0}
    assert paired_delta(treatment, control) == 0.5