#!/bin/bash
# v72 development (prereg docs/preregistration_v72.md): none arm on development sites with saved pre-action features; refit.
# Usage (via slurm/run.sh): bash slurm/v72dev.sh <actor>
set -uo pipefail
A=$1; PORT=$((8200 + ${SLURM_JOB_ID:-0} % 700)); export V65_PORT=$PORT V65_ACTOR=$A V70_OUT=$PWD/outputs/v72
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True TAU2_DATA_DIR=/data/models/cape_ws/datasets/tau2-bench/data LITELLM_LOCAL_MODEL_COST_MAP=True
export LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
T2=/data/models/cape_ws/envs/tau2/bin/python; O=outputs/v72; mkdir -p $O
python scripts/174_vllm_steer.py stage=serve actor=$A port=$PORT log=$O/server_dev_$A.jsonl shadow=true save_feats=$O/feats_dev_$A.npz &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v72dev: SERVER DIED"; exit 0; }; sleep 5; done
timeout 6h $T2 scripts/187_v70_real_context.py run none dev dev_${A}_none || echo "v72dev run error"
curl -sf http://127.0.0.1:$PORT/flush; kill $SRV; wait $SRV 2>/dev/null
python scripts/190_v72_refit.py $A || echo "v72 refit FAILED"
exit 0
