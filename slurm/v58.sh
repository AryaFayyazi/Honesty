#!/bin/bash
# v58: replication of +8 d16 honesty steering and the reasoning-only arm on the 196 fresh v48 episodes (Muse). Run via slurm/run.sh.
set -euo pipefail
muse_py() { ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src VLLM_CACHE_ROOT=/data/models/cape_ws/cache/vllm030 TRITON_CACHE_DIR=/data/models/cape_ws/cache/triton030; python "$@" ); }
G="scripts/103_lie_steering.py stage=generate dim=true neutral=true dir_npz=outputs/reconcile/caa_directions.npz scale_key=g"
muse_py $G out_name=v58smoke limit=3 'conds=[none:0:caa:decode,q16:8:caa:q16]'
muse_py $G fold_key=a episodes=outputs/reconcile/v48_fresh_episodes.parquet 'folds=[0]' out_name=v58C 'conds=[none:0:caa:decode,d16:8:caa:d16,rand_d16:8:rand:d16,q16:8:caa:q16]'
python scripts/97_rubric_timeline.py revised=outputs/reconcile/v58C.parquet
python scripts/157_v58_confirm.py
