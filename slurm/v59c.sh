#!/bin/bash
# v59b D2': gate-always vs none_hf on all 200 fresh x+ sites, 12-turn horizon (HF). Run via slurm/run.sh.
set -euo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
A=$1
python scripts/160_v59b_gate_always.py actor=$A 'worlds=[plus]' tag=_k12 K=12 n_per_world=200
