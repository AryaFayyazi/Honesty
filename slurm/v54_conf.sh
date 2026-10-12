#!/bin/bash
# v54 confirmation for one actor whose development stage is complete (Addendum 5). Run via slurm/run.sh.
set -euo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
A=$1; O=outputs/v54
gpu_py() {
  if [ "$A" = museglimmer ]; then
    ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src VLLM_CACHE_ROOT=/data/models/cape_ws/cache/vllm030 TRITON_CACHE_DIR=/data/models/cape_ws/cache/triton030; python "$@" )
  else python "$@"; fi
}
python scripts/146_v54_analysis.py stage=select actor=$A
[ -f $O/gatefeat_v54dev_$A.npz ] || gpu_py scripts/154_v54_gate.py stage=extract actor=$A
python scripts/154_v54_gate.py stage=select_alpha actor=$A
CH=$(python -c "import json;print(json.load(open('results/prereg_v54/select_$A.json'))['chosen'] or '')")
GA=$(python -c "import json;print(json.load(open('results/prereg_v54/gate_alpha_$A.json'))['gate_alpha'] or '')")
ARMS="none"
if [ -n "$CH" ]; then al=${CH#caa:}; ARMS="$ARMS,caa:$al,rand:$al,targeted:$al"; fi
if [ -n "$GA" ] && [ "caa:$GA" != "$CH" ]; then ARMS="$ARMS,caa:$GA"; fi
if [ "$ARMS" = "none" ]; then echo "v54 $A: neither a blanket alpha nor a gate alpha qualified on development; no confirmation"; exit 0; fi
python -c "import joblib, numpy as np; F=joblib.load('$O/forecaster_$A.joblib'); np.savez('$O/forecaster_$A.npz', layer_index=F['layer_index'], w=F['w'], b=F['b'], tau=F['tau'])"   # numpy copy for the Muse env
gpu_py scripts/144_v54_steer.py actor=$A batch=24 max_batch_tokens=24000 max_new=1536 split=conf limit=200 "arms=[$ARMS]" dir_npz=$O/dir_$A.npz fold_key=a forecaster=$O/forecaster_$A.npz out_name=v54conf_$A
[ -n "$CH" ] && python scripts/146_v54_analysis.py stage=confirm actor=$A
gpu_py scripts/154_v54_gate.py stage=extract actor=$A
[ -n "$GA" ] && python scripts/154_v54_gate.py stage=analyze actor=$A split=conf alpha=$GA B=10000
# v59 (prevented vs postponed; lost vs delayed): continue every confirmation episode after the decision turn
[ -n "$GA" ] && bash slurm/v59.sh $A
exit 0
