#!/bin/bash
# v66 screen (prereg docs/preregistration_v66.md): tau2-airline with the truthful authorization oracle; none arm, 20 development
# tasks x 1 trial, tau2 seed 660; shadow gate scores + pre-action features (descriptive transfer); labels incl. informed.
# Usage (via slurm/run.sh): bash slurm/v66s.sh <actor> <P0_orc|P0_orc_enf>
set -uo pipefail
A=$1; C=$2
PORT=$((8200 + ${SLURM_JOB_ID:-0} % 700)); export V65_PORT=$PORT      # unique per job: two tau2 jobs can share the node
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True TAU2_DATA_DIR=/data/models/cape_ws/datasets/tau2-bench/data LITELLM_LOCAL_MODEL_COST_MAP=True V65_ACTOR=$A V65_COND=$C
export LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
T2=/data/models/cape_ws/envs/tau2/bin/python; O=outputs/v65; N=v66_screen_${A}_$C
case $A in qwen38|gptoss20b|gemma4) ;; *) echo "v66s: $A has no passing vLLM validation; not run"; exit 0;; esac
SD=$TAU2_DATA_DIR/simulations/$N; [ -e $SD ] && mv $SD ${SD}_partial_$(date +%s)
python scripts/174_vllm_steer.py stage=serve actor=$A port=$PORT log=$O/server_$N.jsonl save_feats=$O/feats_$N.npz &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v66s $A $C: SERVER DIED"; exit 0; }; sleep 5; done
timeout 10h $T2 scripts/172_v65_tau2_run.py run none dev 1 $N 32 660 || echo "v66s $A $C run error"
curl -sf http://127.0.0.1:$PORT/flush; kill $SRV; wait $SRV 2>/dev/null
$T2 scripts/172_v65_tau2_run.py label $N
exit 0
