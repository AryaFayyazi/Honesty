#!/bin/bash
# v59b gate-always continuation for one actor (HF). Run via slurm/run.sh; Muse in the v030 env.
set -euo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
A=$1
if [ "$A" = museglimmer ]; then
  ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src; python scripts/160_v59b_gate_always.py actor=$A stage=run ) || true
  python scripts/160_v59b_gate_always.py actor=$A stage=analyze
else
  python scripts/160_v59b_gate_always.py actor=$A
fi
