#!/usr/bin/env bash
set -u

# A-J04 operator harness. Run this only from a fresh checkout of a committed
# candidate; it deliberately refuses a dirty worktree and records every
# command's output/status for the evidence packet.

output_dir="${1:-}"
candidate_sha="$(git rev-parse HEAD 2>/dev/null || true)"
if [[ -z "${candidate_sha}" ]]; then
    echo "not a git checkout" >&2
    exit 2
fi

if [[ -n "$(git status --porcelain)" ]]; then
    echo "worktree is not clean; use a fresh checkout" >&2
    exit 2
fi

if [[ -z "${output_dir}" ]]; then
    output_dir="/tmp/neusym-nav-a-j04-${candidate_sha}"
fi
mkdir -p "${output_dir}"

python_command="python3"
if command -v python >/dev/null 2>&1; then
    python_command="python"
fi

uv_bin="uv"
if [[ -x "${HOME}/.local/bin/uv" ]]; then
    uv_bin="${HOME}/.local/bin/uv"
fi

{
    echo "candidate_sha=${candidate_sha}"
    echo "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "os=$(uname -a)"
    echo "python=$(${python_command} --version 2>&1 || true)"
    echo "uv=$(${uv_bin} --version 2>&1 || true)"
    echo "git=$(git --version 2>&1)"
    sha256sum uv.lock
    sha256sum configs/manifests.yaml configs/smoke.yaml configs/b3_test.yaml configs/rq1_test.yaml configs/rq2_test.yaml configs/v1r1_clean.yaml reports/expected_rows.yaml
} >"${output_dir}/environment.txt"

failed=0
run_step() {
    name="$1"
    shift
    log_path="${output_dir}/${name}.log"
    {
        echo "command: $*"
        echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    } >"${log_path}"
    "$@" >>"${log_path}" 2>&1
    status=$?
    {
        echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "exit_status=${status}"
    } >>"${log_path}"
    if [[ "${status}" -ne 0 ]]; then
        failed=1
    fi
}

run_step 01_sync ${uv_bin} sync --all-groups
run_step 02_ruff ${uv_bin} run ruff check .
run_step 03_mypy ${uv_bin} run mypy src
run_step 04_pytest ${uv_bin} run pytest -q
run_step 05_manifests ${uv_bin} run ns-vln generate-manifests --config configs/manifests.yaml
{
    echo "generated_manifest_hashes:"
    sha256sum data/manifests/*.jsonl data/manifests/manifest_hashes.json
} >>"${output_dir}/environment.txt"
run_step 06_smoke ${uv_bin} run ns-vln evaluate --config configs/smoke.yaml
run_step 07_b3 ${uv_bin} run ns-vln evaluate --config configs/b3_test.yaml
run_step 08_rq1 ${uv_bin} run ns-vln evaluate --config configs/rq1_test.yaml
run_step 09_rq2 ${uv_bin} run ns-vln evaluate --config configs/rq2_test.yaml
run_step 10_v1r1_clean ${uv_bin} run ns-vln evaluate --config configs/v1r1_clean.yaml
run_step 11_validate_results ${uv_bin} run ns-vln validate-results --runs runs/final --expected-config reports/expected_rows.yaml
run_step 12_validate_traces ${uv_bin} run ns-vln validate-traces --runs runs/final
run_step 13_audit ${uv_bin} run ns-vln audit --runs runs/final
run_step 14_summarize ${uv_bin} run ns-vln summarize --runs runs/final --output reports/month1/
run_step 15_audit_portability ${uv_bin} run ns-vln audit-portability --src src/neuro_symbolic_vln
run_step 16_validate_report ${uv_bin} run ns-vln validate-report --report reports/month1/
run_step 17_validate_habitat_decision ${uv_bin} run ns-vln validate-habitat-decision --report reports/month1/habitat_decision.yaml

echo "candidate_sha=${candidate_sha}"
echo "evidence_dir=${output_dir}"
if [[ "${failed}" -ne 0 ]]; then
    echo "A-J04 reproduction: FAILED (see per-command logs)" >&2
    exit 1
fi
echo "A-J04 reproduction: PASS"
