#!/bin/bash
# v73 development (prereg docs/preregistration_v73.md): real τ² decision points + the truthful oracle's answer about the very write;
# none arm with shadow frozen-gate scores; calibration and go rule. Usage (via slurm/run.sh): bash slurm/v73dev.sh <actor>
set -uo pipefail
A=$1; PORT=$((8200 + ${SLURM_JOB_ID:-0} % 700)); export V65_PORT=$PORT V65_ACTOR=$A V70_OUT=$PWD/outputs/v73 V70_ORACLE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True TAU2_DATA_DIR=/data/models/cape_ws/datasets/tau2-bench/data LITELLM_LOCAL_MODEL_COST_MAP=True
export LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
T2=/data/models/cape_ws/envs/tau2/bin/python; O=outputs/v73; mkdir -p $O
python scripts/174_vllm_steer.py stage=serve actor=$A port=$PORT log=$O/server_dev_$A.jsonl shadow=true &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v73dev: SERVER DIED"; exit 0; }; sleep 5; done
timeout 6h $T2 scripts/187_v70_real_context.py run none dev dev_${A}_none || echo "v73dev run error"
curl -sf http://127.0.0.1:$PORT/flush; kill $SRV; wait $SRV 2>/dev/null
python scripts/188_v70_analysis.py stage=calibrate actor=$A out=outputs/v73 res=results/prereg_v73 || echo "v73 calibration FAILED"
exit 0
