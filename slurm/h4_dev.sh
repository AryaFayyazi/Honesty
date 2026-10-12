#!/bin/bash
# v49 H4 development chain for one actor: CAA extraction -> direction -> smoke -> sweep. (run via slurm/run.sh)
set -euo pipefail
A=$1
[ -f outputs/reconcile/caa_${A}_acts.npz ] || python scripts/126_caa_multi.py stage=extract actor=$A
python scripts/126_caa_multi.py stage=direction actor=$A
python - <<PY
import pandas as pd; E=pd.read_parquet("outputs/reconcile/h4_${A}_dev_episodes.parquet"); E.head(6).to_parquet("outputs/reconcile/h4_${A}_smoke_episodes.parquet")
PY
python scripts/127_steer_multi.py actor=$A episodes=outputs/reconcile/h4_${A}_smoke_episodes.parquet out_name=h4smoke_$A 'conds=[none:0:caa:d16,caa_p2_d16:2:caa:d16]'
python - <<PY
import pandas as pd; R=pd.read_parquet("outputs/reconcile/h4smoke_${A}.parquet"); share=(~R.revised_has_tool_call).mean(); print("smoke report share", share)
assert share >= 0.5, "smoke: too few reports extracted; check final_report() for this actor"
PY
python scripts/127_steer_multi.py actor=$A episodes=outputs/reconcile/h4_${A}_dev_episodes.parquet out_name=h4dev_$A 'conds=[none:0:caa:d16,caa_p2_d16:2:caa:d16,caa_p4_d16:4:caa:d16,caa_p8_d16:8:caa:d16,caa_p12_d16:12:caa:d16,rand_p8_d16:8:rand:d16]'
python scripts/97_rubric_timeline.py revised=outputs/reconcile/h4dev_$A.parquet
