#!/bin/bash
# v54 Addendum 6 extension for an actor whose whole grid failed the parse guard: lower doses, then the confirmation script.
set -euo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
A=$1; O=outputs/v54
gpu_py() {
  if [ "$A" = museglimmer ]; then ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src; python "$@" ); else python "$@"; fi
}
gpu_py scripts/144_v54_steer.py actor=$A batch=24 max_batch_tokens=24000 max_new=1536 split=dev limit=80 'arms=[caa:0.25,caa:0.5,rand:0.5]' dir_npz=$O/dir_$A.npz out_name=v54dev_$A
rm -f $O/gatefeat_v54dev_$A.npz        # gate features are re-extracted for the 'none' turns (unchanged) inside v54_conf.sh
bash slurm/v54_conf.sh $A
