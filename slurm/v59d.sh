#!/bin/bash
# v59d gate-escalate vs none_hf (100 x- + 200 x+, K=12). Run via slurm/run.sh; Muse in the v030 env. report=true (v64 addendum): transcripts, asks and x- reports are saved; trajectories unchanged.
set -uo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
A=$1
GA=$(python -c "import json;print(json.load(open('results/prereg_v54/gate_alpha_$A.json')).get('gate_alpha') or '')" 2>/dev/null)
[ -n "$GA" ] || { echo "v59d $A: no gate alpha; skipped"; exit 0; }
if [ "$A" = museglimmer ]; then
  ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src; timeout 8h python scripts/160_v59b_gate_always.py actor=$A policy=escalate tag=_esc K=12 n_per_world=200 n_minus=100 report=true stage=run ) || true
else
  timeout 8h python scripts/160_v59b_gate_always.py actor=$A policy=escalate tag=_esc K=12 n_per_world=200 n_minus=100 report=true stage=run || true
fi
python scripts/160_v59b_gate_always.py actor=$A tag=_esc K=12 stage=analyze_tag || echo "v59d analysis failed for $A"
exit 0
