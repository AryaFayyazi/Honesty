#!/bin/bash
# v66 selected cell, development (prereg v66): 20 development tasks x 3 trials (tau2 seed 661), none arm with shadow scores and
# features; labels; calibration with informed violations as positives, written to tagged files only (never the v65 files).
# Usage (via slurm/run.sh): bash slurm/v66cell_dev.sh <actor> <P0_orc|P0_orc_enf>
set -uo pipefail
A=$1; C=$2; TAG=_v66_${A}_$C
PORT=$((8200 + ${SLURM_JOB_ID:-0} % 700)); export V65_PORT=$PORT
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True TAU2_DATA_DIR=/data/models/cape_ws/datasets/tau2-bench/data LITELLM_LOCAL_MODEL_COST_MAP=True V65_ACTOR=$A V65_COND=$C
export LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
T2=/data/models/cape_ws/envs/tau2/bin/python; O=outputs/v65; N=v66_dev_${A}_$C
SD=$TAU2_DATA_DIR/simulations/$N; [ -e $SD ] && mv $SD ${SD}_partial_$(date +%s); [ -e $O/server_$N.jsonl ] && mv $O/server_$N.jsonl $O/server_${N}_partial_$(date +%s).jsonl
python scripts/174_vllm_steer.py stage=serve actor=$A port=$PORT log=$O/server_$N.jsonl save_feats=$O/feats_$N.npz &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v66cell_dev: SERVER DIED"; exit 0; }; sleep 5; done
timeout 20h $T2 scripts/172_v65_tau2_run.py run none dev 3 $N 32 661 || echo "v66cell_dev run error"
curl -sf http://127.0.0.1:$PORT/flush; kill $SRV; wait $SRV 2>/dev/null
$T2 scripts/172_v65_tau2_run.py label $N
python scripts/173_v65_analysis.py stage=calibrate dev_run=$N dev_log=$O/server_$N.jsonl dev_feats=$O/feats_$N.npz tag=$TAG positive=informed || echo "v66cell_dev calibration FAILED"
exit 0
