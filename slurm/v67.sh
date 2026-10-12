#!/bin/bash
# v67 (prereg docs/preregistration_v67.md): model approver with escalation on the logged gate-then-ask asks (Qwen _esc64 = confirmatory).
# Runs after the Qwen rerun (3534) has written its asks. Run via slurm/run.sh.
set -uo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
[ -f outputs/v59/asks_esc64_qwen38.parquet ] || echo "v67: Qwen _esc64 asks missing; scoring the descriptive set only (no confirmatory claim possible)"
python scripts/184_v67_approver.py stage=score || echo "v67 score FAILED"
python scripts/184_v67_approver.py stage=analyze || echo "v67 analysis FAILED"
exit 0
