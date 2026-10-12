#!/bin/bash
# v61 end-to-end (prereg docs/preregistration_v61.md): none / gate-every-action / gate + honesty report steering, Muse.
# Replaces the separate v59b Muse job (same sites, policy, comparator, K; D1/D2' computed in the analysis). Run via slurm/run.sh.
set -uo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
A=${1:-museglimmer}
GA=$(python -c "import json;print(json.load(open('results/prereg_v54/gate_alpha_$A.json')).get('gate_alpha') or '')" 2>/dev/null)
[ -n "$GA" ] || { echo "v61 $A: no gate alpha from v54; v61 not run (preregistered)"; exit 0; }
[ -f outputs/v54/gatefeat_v54conf_$A.npz ] || { echo "v61 $A: no confirmation gate features; skipped"; exit 0; }
muse_py() { ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src; python "$@" ); }
# smoke: 3 x-, 2 x+, 2 turns; must produce reports
muse_py scripts/165_v61_e2e.py actor=$A tag=_smoke n_minus=3 n_plus=2 K=2 stage=run || { echo "v61 smoke FAILED"; exit 0; }
python - <<PY || { echo "v61 smoke: reports missing; full run NOT started"; exit 0; }
import pandas as pd; W = pd.read_parquet("outputs/v61/e2e_smoke_$A.parquet"); share = (W.report.str.len() > 0).mean(); print("smoke report share", share, W.arm.value_counts().to_dict())
assert share >= 0.5 and set(W.arm) == {"none_hf", "gate_always", "gate_honest"}
tools = W["hist"].map(lambda h: any(c in ("VIOLATE", "CRITICAL", "ESCALATE", "OTHER") for c in list(h))).mean(); print("episodes with a parsed tool step", tools); assert tools >= 0.5
PY
muse_py scripts/165_v61_e2e.py actor=$A stage=run K=12 n_minus=200 n_plus=200 || { echo "v61 run FAILED"; exit 0; }
python scripts/97_rubric_timeline.py revised=outputs/v61/revised_$A.parquet || { echo "v61 judge FAILED"; exit 0; }
python scripts/165_v61_e2e.py actor=$A stage=analyze || echo "v61 analysis FAILED"
exit 0
