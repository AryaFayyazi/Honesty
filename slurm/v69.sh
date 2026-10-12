#!/bin/bash
# v69 (prereg docs/preregistration_v69.md): reader gate (Qwen reads frontier τ² transcripts); score on GPU, then analyze.
set -uo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
python scripts/186_v69_reader_gate.py score || echo "v69 score FAILED"
python scripts/186_v69_reader_gate.py analyze || echo "v69 analysis FAILED"
exit 0
