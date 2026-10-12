#!/bin/bash
# v74 development (prereg docs/preregistration_v74.md): AgentDojo v1.2.2 development user tasks, none arm with shadow frozen-gate
# scores; benign (3 trials) then important_instructions attacks; calibration and go rule. Usage (via slurm/run.sh): bash slurm/v74dev.sh <actor>
set -uo pipefail
A=$1; PORT=$((8200 + ${SLURM_JOB_ID:-0} % 700)); export V65_PORT=$PORT V65_ACTOR=$A V74_OUT=$PWD/outputs/v74
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
AD=/data/models/cape_ws/envs/agentdojo/bin/python; O=outputs/v74; mkdir -p $O
python scripts/174_vllm_steer.py stage=serve actor=$A port=$PORT log=$O/server_dev_$A.jsonl shadow=true &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v74dev: SERVER DIED"; exit 0; }; sleep 5; done
timeout 4h $AD -I scripts/191_v74_agentdojo.py run none dev benign dev_${A}_benign 3 || echo "v74dev benign run error"
timeout 8h $AD -I scripts/191_v74_agentdojo.py run none dev attack dev_${A}_attack 1 || echo "v74dev attack run error"
curl -sf http://127.0.0.1:$PORT/flush; kill $SRV; wait $SRV 2>/dev/null
python scripts/192_v74_analysis.py calibrate $A || echo "v74 calibration FAILED"
exit 0
