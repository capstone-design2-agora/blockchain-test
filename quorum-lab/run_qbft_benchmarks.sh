#!/usr/bin/env bash
# Run phased QBFT benchmarks at multiple TPS targets and organize reports.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(realpath "${SCRIPT_DIR}/..")"
TEST_RESULT_DIR="${PROJECT_ROOT}/test_result"
QBFT_DIR="${TEST_RESULT_DIR}/qbft"

TPS_VALUES=(50 100 250 500)
RUNS_PER_TPS=5
PHASE_COUNT=1000
BASE_CMD=(
  python3 "${SCRIPT_DIR}/benchmark.py"
  --poa
  --rpc-url http://localhost:8545
  --consensus qbft
  --phase-labels alwaysburst
  --receipt-workers 20
  --timeout 240
  --skip-unlock
)

mkdir -p "${QBFT_DIR}"

run_benchmark() {
  local phase_spec="$1"
  local output
  # shellcheck disable=SC2068 # intentional word splitting for BASE_CMD
  output=$("${BASE_CMD[@]}" --phase "${phase_spec}" 2>&1)
  echo "$output" >&2  # Print to stderr so it's visible but doesn't interfere with return value
  
  local report_path
  report_path=$(echo "$output" | grep 'Markdown report written to' | awk '{print $NF}')
  
  if [[ -z "${report_path}" ]]; then
    echo "Failed to capture report path for phase ${phase_spec}" >&2
    exit 1
  fi
  
  if [[ ! -f "${report_path}" ]]; then
    echo "Report file does not exist: ${report_path}" >&2
    exit 1
  fi
  
  echo "${report_path}"
}

for tps in "${TPS_VALUES[@]}"; do
  phase_spec="${PHASE_COUNT}@${tps}tps"
  tps_dir="${QBFT_DIR}/${tps}"
  mkdir -p "${tps_dir}"
  echo "=== Running ${phase_spec} benchmarks (5 iterations) ==="
  for run_id in $(seq 1 "${RUNS_PER_TPS}"); do
    echo "--- Iteration ${run_id} for ${phase_spec} ---"
    report_path="$(run_benchmark "${phase_spec}")"
    base_name="$(basename "${report_path}")"
    date_prefix="${base_name%%_*}"
    dest_path="${tps_dir}/${date_prefix}_qbft_phase_${tps}_${run_id}.md"
    mv "${report_path}" "${dest_path}"
    echo "Stored report: ${dest_path}"
  done
done
