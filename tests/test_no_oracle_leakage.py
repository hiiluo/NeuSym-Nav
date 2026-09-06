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
