#!/bin/bash
# v65 selected cell, development (prereg v65 Addenda 6, 8, 10, 11): 20 dev tasks x 3 trials, none arm with shadow scores + features;
# labels (adjudicated); calibration. Usage: bash slurm/v65cell_dev.sh <actor> <P1|P0_enf>
set -uo pipefail
A=$1; C=$2
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True TAU2_DATA_DIR=/data/models/cape_ws/datasets/tau2-bench/data LITELLM_LOCAL_MODEL_COST_MAP=True V65_ACTOR=$A V65_COND=$C
export LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
T2=/data/models/cape_ws/envs/tau2/bin/python; O=outputs/v65; N=v65_dev_${A}_$C
if [ "$A" = museglimmer ]; then vpy() { ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src VLLM_CACHE_ROOT=/data/models/cape_ws/cache/vllm030 TRITON_CACHE_DIR=/data/models/cape_ws/cache/triton030; python "$@" ); }; else vpy() { python "$@"; }; fi
SD=$TAU2_DATA_DIR/simulations/$N; [ -e $SD ] && mv $SD ${SD}_partial_$(date +%s); [ -e $O/server_$N.jsonl ] && mv $O/server_$N.jsonl $O/server_${N}_partial_$(date +%s).jsonl
vpy scripts/174_vllm_steer.py stage=serve actor=$A port=8124 log=$O/server_$N.jsonl save_feats=$O/feats_$N.npz &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:8124/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v65cell_dev: SERVER DIED"; exit 0; }; sleep 5; done
timeout 20h $T2 scripts/172_v65_tau2_run.py run none dev 3 $N 32 || echo "v65cell_dev run error"
curl -sf http://127.0.0.1:8124/flush; kill $SRV; wait $SRV 2>/dev/null
$T2 scripts/172_v65_tau2_run.py label $N
python scripts/173_v65_analysis.py stage=calibrate dev_run=$N dev_log=$O/server_$N.jsonl dev_feats=$O/feats_$N.npz || echo "v65cell_dev calibration FAILED"
exit 0
