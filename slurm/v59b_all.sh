#!/bin/bash
# v59b all-model replication for one actor: gate-always vs none_hf, 100 x- + 200 x+ sites, K=12. Run via slurm/run.sh.
set -uo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
A=$1
GA=$(python -c "import json;print(json.load(open('results/prereg_v54/gate_alpha_$A.json')).get('gate_alpha') or '')" 2>/dev/null)
[ -n "$GA" ] || { echo "v59b $A: no gate alpha; skipped"; exit 0; }
[ -f outputs/v54/gatefeat_v54conf_$A.npz ] || { echo "v59b $A: no confirmation gate features; skipped"; exit 0; }
if [ "$A" = museglimmer ]; then exec bash slurm/v61.sh museglimmer; fi   # v61 (prereg) contains the v59b Muse design and replaces it
if [ "$A" = museglimmer ]; then
  ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src; timeout 8h python scripts/160_v59b_gate_always.py actor=$A tag=_all K=12 n_per_world=200 n_minus=100 stage=run ) || true
else
  timeout 8h python scripts/160_v59b_gate_always.py actor=$A tag=_all K=12 n_per_world=200 n_minus=100 stage=run || true
fi
python scripts/160_v59b_gate_always.py actor=$A tag=_all K=12 stage=analyze_tag || echo "v59b analysis failed for $A"
exit 0
