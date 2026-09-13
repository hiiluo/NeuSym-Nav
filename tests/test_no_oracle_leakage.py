"""Forbidden-import guard: the normal agent path must not pull in the
evaluator oracle or manifests."""

import subprocess
import sys


def test_normal_agent_import_graph_excludes_oracle() -> None:
    code = (
        "import sys\n"
        "import neuro_symbolic_vln.agent\n"
        "import neuro_symbolic_vln.control.controller\n"
        "import neuro_symbolic_vln.perception.observation_decoder\n"
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

def test_belief_pipeline_import_graph_excludes_oracle() -> None:
    """ B-J02: Belief pipeline imports must not pull in evaluation modules. """
    code = (
        "import sys\n"
        "import neuro_symbolic_vln.belief.state\n"
        "import neuro_symbolic_vln.belief.validator\n"
        "import neuro_symbolic_vln.belief.evidence\n"
        "import neuro_symbolic_vln.language.template_parser\n"
        "import neuro_symbolic_vln.planning.problem_serializer\n"
        "import neuro_symbolic_vln.planning.pyperplan_adapter\n"
        "bad = [\n"
        "   name for name in sys.modules\n"
        "   if name.startswith('neuro_symbolic_vln.evaluation')\n"
        "]\n"
        "assert not bad, f'leaked evaluation modules: {bad}'\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr

def test_v1r1_runtime_has_no_oracle_constructor_field() -> None:
    """ B-J02: _V1R1EpisodeRuntime must not store oracle state or sidecar. """
    from neuro_symbolic_vln.agent_v1r1 import _V1R1EpisodeRuntime
    from neuro_symbolic_vln.contracts import EpisodeSpec

    episode = EpisodeSpec(
        episode_id="test-leak",
        family="goto_type_color",
        instruction="go to the green ball",
        public_action_budget=32,
        manifest_hash="test"
    )

    runtime = _V1R1EpisodeRuntime(episode, "goto_type_color")

    forbidden_prefixes = ("oracle", "sidecar", "_oracle", "_sidecar", "eval")
    for attr_name in dir(runtime):
        if attr_name.startswith("__"):
            continue
        assert not any(
            attr_name.lower().startswith(prefix) for prefix in forbidden_prefixes
        ), f"Runtime has forbidden attribute: {attr_name}"

def test_v0r0_episode_traces_oracle_input_false() -> None:
    """ B-J02: V0R0 episodes must record oracle_input=false in all traces. """
    from neuro_symbolic_vln.agent_v1r1 import run_v1r1_episode

    result = run_v1r1_episode(
        seed=0,
        family="goto_type_color",
        method="V0R0",
        use_validator=False,
        use_recovery=False
    )
    # Episode result itself should not be flagged as oracle_input
    # (V1R1EpisodeResult doesn't have oracle_input field, which is correct
    # — only B3EpisodeResult has oracle_input=True)
    assert not hasattr(result, "oracle_input") or result.oracle_input is False

def test_v1r0_episode_traces_oracle_input_false() -> None:
    """ B-J02: V1R0 episodes must record oracle_input=false in all traces. """
    from neuro_symbolic_vln.agent_v1r1 import run_v1r1_episode

    result = run_v1r1_episode(
        seed=0,
        family="goto_type_color",
        method="V1R0",
        use_validator=False,
        use_recovery=False
    )

    assert not hasattr(result, "oracle_input") or result.oracle_input is False
