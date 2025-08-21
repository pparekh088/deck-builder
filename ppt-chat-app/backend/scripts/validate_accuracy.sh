#!/usr/bin/env bash
set -euo pipefail

# Change to backend directory
cd "$(dirname "$0")/.."

# Set PYTHONPATH
export PYTHONPATH="${PWD}:${PYTHONPATH:-}"

export HYBRID_VISION_ENABLED=true
export ACCURATE_SOLVER_ENABLED=true
export RENDER_MEASURE_ENABLED=true
export ARCHETYPE_ALIGNMENT_ENABLED=true
export SAFETY_MAP_ENABLED=true

echo "== Step 1: Verbose solver tests =="
python3 -m pytest -q -vv tests/accuracy/test_solver_edge_cases_verbose.py

echo "== Step 2: Full accuracy suite (may skip LO-dependent test if missing) =="
python3 -m pytest -q tests/accuracy

echo "== Step 3: Perf benchmark (non-strict by default) =="
python3 -m pytest -q -m performance tests/perf/test_perf_accuracy_solver.py

echo "== Step 4: Strict perf gate (optional) =="
export PERF_STRICT=${PERF_STRICT:-false}
if [ "$PERF_STRICT" = "true" ]; then
  python3 -m pytest -q -m performance tests/perf/test_perf_accuracy_solver.py
fi

echo "== Step 5: Legacy fallback still works =="
export ACCURATE_SOLVER_ENABLED=false
python3 -m pytest -q tests/accuracy/test_feature_flags_fallback.py

echo "All validation + perf checks completed ✅"