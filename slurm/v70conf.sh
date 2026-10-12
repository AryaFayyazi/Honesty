#!/bin/bash
# v70 confirmation (prereg v70): none and gate arms on confirmation real-context sites (same server, tau from development), only if
# the development go rule passed for this actor. Usage (via slurm/run.sh): bash slurm/v70conf.sh <actor>
set -uo pipefail
A=$1; PORT=$((8200 + ${SLURM_JOB_ID:-0} % 700)); export V65_PORT=$PORT V65_ACTOR=$A
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True TAU2_DATA_DIR=/data/models/cape_ws/datasets/tau2-bench/data LITELLM_LOCAL_MODEL_COST_MAP=True
export LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
T2=/data/models/cape_ws/envs/tau2/bin/python; O=outputs/v70
python -c "import json,sys; c=json.load(open('results/prereg_v70/calibration_$A.json')); sys.exit(0 if c['go'] else 1)" || { echo "v70conf $A: go rule not met; not run (preregistered)"; exit 0; }
python scripts/174_vllm_steer.py stage=serve actor=$A port=$PORT log=$O/server_conf_$A.jsonl tau_file=$O/tau_$A.json shadow=false &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v70conf: SERVER DIED"; exit 0; }; sleep 5; done
timeout 6h $T2 scripts/187_v70_real_context.py run none conf conf_${A}_none || echo "v70conf none error"
timeout 6h $T2 scripts/187_v70_real_context.py run gate conf conf_${A}_gate || echo "v70conf gate error"
kill $SRV; wait $SRV 2>/dev/null
python scripts/188_v70_analysis.py stage=analyze || echo "v70 analysis FAILED"
exit 0
