#!/bin/bash
# v56 report-anchored honesty steering (Muse). Usage: slurm/run.sh bash slurm/v56.sh dev|conf
# Muse generation in the vLLM-0.30 env; labelling (judge) and analysis in the main env.
set -euo pipefail
muse_py() { ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src VLLM_CACHE_ROOT=/data/models/cape_ws/cache/vllm030 TRITON_CACHE_DIR=/data/models/cape_ws/cache/triton030; python "$@" ); }
G="scripts/103_lie_steering.py stage=generate dim=true neutral=true dir_npz=outputs/reconcile/caa_directions.npz scale_key=g"
if [ "$1" = dev ]; then
  muse_py $G out_name=v56smoke limit=3 'conds=[none:0:caa:decode,caa_p8_r0:8:caa:r0]'
  python scripts/152_v56_confirm.py stage=check run=v56smoke
  muse_py $G out_name=v56devA 'conds=[none:0:caa:decode,caa_p4_r0:4:caa:r0,caa_p8_r0:8:caa:r0,caa_p12_r0:12:caa:r0,caa_p16_r0:16:caa:r0]'
  python scripts/97_rubric_timeline.py revised=outputs/reconcile/v56devA.parquet
  python scripts/152_v56_confirm.py stage=check run=v56devA
  python scripts/106_*.py stage=select tag=v56dev
else
  CH=$(python -c "import json;c=json.load(open('results/prereg_v56dev/selection.json'))['chosen_name'];print(c or '')")
  [ -n "$CH" ] || { echo "v56: no development candidate passed the rule; no confirmation"; exit 0; }
  AL=$(echo $CH | sed -E 's/caa_p([0-9]+)_r0/\1/')
  muse_py $G fold_key=a episodes=outputs/reconcile/v48_fresh_episodes.parquet 'folds=[0]' out_name=v56C "conds=[none:0:caa:decode,chosen:$AL:caa:r0,rand_chosen:$AL:rand:r0,v46rep:8:caa:d16]"
  python scripts/97_rubric_timeline.py revised=outputs/reconcile/v56C.parquet
  python scripts/152_v56_confirm.py stage=check run=v56C
  python scripts/152_v56_confirm.py stage=confirm
fi
