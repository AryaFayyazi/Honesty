#!/bin/bash
# v79 per-model honesty-steering confirmation (docs/preregistration_v79.md): K samples per fresh episode and condition.
# usage (via slurm/run.sh): bash slurm/h4_conf.sh <actor> <K>
set -euo pipefail
A=$1; K=$2
C=$(python -c "import json;print(json.load(open('results/prereg_v49_h4/selection_$A.json'))['chosen'])")
M=$(echo $C | sed -E 's/caa_p([0-9.]+)_d16/\1/'); R=rand_p${M}_d16
EXTRA=""; [ "$A" = "gptoss20b" ] && EXTRA="max_attn_gb=6"
python scripts/203_h4_confirm.py stage=episodes actor=$A K=$K
python scripts/127_steer_multi.py actor=$A episodes=outputs/reconcile/h4conf_${A}_episodes.parquet out_name=h4conf_$A fold_key=a $EXTRA "conds=[none:0:caa:d16,$C:$M:caa:d16,$R:$M:rand:d16]"
python scripts/97_rubric_timeline.py revised=outputs/reconcile/h4conf_$A.parquet
python scripts/203_h4_confirm.py stage=analyze actor=$A
python scripts/203_h4_confirm.py stage=holm
