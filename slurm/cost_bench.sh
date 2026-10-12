#!/bin/bash
# Measured latency for the cost table (scripts/182): agent turns + our gate's scoring call (Qwen, gpt-oss, Gemma), then the CoT monitor
# (Qwen3.8-27B, thinking). Low priority: submitted with --nice so it never delays the preregistered jobs. Run via slurm/run.sh.
set -uo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
for A in qwen38 gptoss20b gemma4; do timeout 50m python scripts/182_cost_bench.py stage=agent actor=$A || echo "cost bench agent $A FAILED"; done
timeout 80m python scripts/182_cost_bench.py stage=monitor || echo "cost bench monitor FAILED"
exit 0
