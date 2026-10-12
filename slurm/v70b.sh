#!/bin/bash
# v70 Addendum 1 (exact pairing): one gate-mode request per confirmation site (fresh seed, request id); the server logs the first
# (unsteered) and final generation of the same request; both are labelled. Usage (via slurm/run.sh): bash slurm/v70b.sh <actor>
set -uo pipefail
A=$1; PORT=$((8200 + ${SLURM_JOB_ID:-0} % 700)); export V65_PORT=$PORT V65_ACTOR=$A
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True TAU2_DATA_DIR=/data/models/cape_ws/datasets/tau2-bench/data LITELLM_LOCAL_MODEL_COST_MAP=True
export LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
T2=/data/models/cape_ws/envs/tau2/bin/python; O=outputs/v70; LOG=$O/server_pair_$A.jsonl; [ -e $LOG ] && mv $LOG ${LOG%.jsonl}_partial_$(date +%s).jsonl
export V70_SERVER_LOG=$LOG
python scripts/174_vllm_steer.py stage=serve actor=$A port=$PORT log=$LOG tau_file=$O/tau_$A.json shadow=false &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v70b: SERVER DIED"; exit 0; }; sleep 5; done
timeout 6h $T2 scripts/187_v70_real_context.py run pair conf pair_$A || echo "v70b run error"
kill $SRV; wait $SRV 2>/dev/null
python scripts/188_v70_analysis.py stage=analyze_pair || echo "v70b analysis FAILED"
exit 0
