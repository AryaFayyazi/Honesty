#!/bin/bash
# v70 development (prereg docs/preregistration_v70.md): none arm on development real-context sites with shadow gate scores; calibration.
# Usage (via slurm/run.sh): bash slurm/v70dev.sh <actor>
set -uo pipefail
A=$1; PORT=$((8200 + ${SLURM_JOB_ID:-0} % 700)); export V65_PORT=$PORT V65_ACTOR=$A
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True TAU2_DATA_DIR=/data/models/cape_ws/datasets/tau2-bench/data LITELLM_LOCAL_MODEL_COST_MAP=True
export LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
T2=/data/models/cape_ws/envs/tau2/bin/python; O=outputs/v70; mkdir -p $O; [ -e $O/server_dev_$A.jsonl ] && mv $O/server_dev_$A.jsonl $O/server_dev_${A}_partial_$(date +%s).jsonl
python scripts/174_vllm_steer.py stage=serve actor=$A port=$PORT log=$O/server_dev_$A.jsonl shadow=true &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v70dev: SERVER DIED"; exit 0; }; sleep 5; done
timeout 6h $T2 scripts/187_v70_real_context.py run none dev dev_${A}_none || echo "v70dev run error"
curl -sf http://127.0.0.1:$PORT/flush; kill $SRV; wait $SRV 2>/dev/null
python scripts/188_v70_analysis.py stage=calibrate actor=$A || echo "v70 calibration FAILED"
exit 0
