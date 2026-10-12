#!/bin/bash
# v75 development (prereg docs/preregistration_v75.md; spotlighting defense in place, arm 'spot'): AgentDojo v1.2.2 development user tasks, none arm with shadow frozen-gate
# scores; benign (3 trials) then important_instructions attacks; calibration and go rule. Usage (via slurm/run.sh): bash slurm/v75dev.sh <actor>
set -uo pipefail
# v74 Addendum 1: Muse, served in the vLLM-0.30 env (as v54/v57/v60/v65s); otherwise identical to slurm/v75dev.sh
vpy() { ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src VLLM_CACHE_ROOT=/data/models/cape_ws/cache/vllm030 TRITON_CACHE_DIR=/data/models/cape_ws/cache/triton030; python "$@" ); }
A=museglimmer; PORT=$((8200 + ${SLURM_JOB_ID:-0} % 700)); export V65_PORT=$PORT V65_ACTOR=$A V74_OUT=$PWD/outputs/v75 V74_RES=$PWD/results/prereg_v75
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
AD=/data/models/cape_ws/envs/agentdojo/bin/python; O=outputs/v75; mkdir -p $O
vpy scripts/174_vllm_steer.py stage=serve actor=$A port=$PORT log=$O/server_dev_${A}_spot.jsonl shadow=true &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v75dev: SERVER DIED"; exit 0; }; sleep 5; done
timeout 4h $AD -I scripts/191_v74_agentdojo.py run spot dev benign dev_${A}_spot_benign 3 || echo "v75dev benign run error"
timeout 8h $AD -I scripts/191_v74_agentdojo.py run spot dev attack dev_${A}_spot_attack 1 || echo "v75dev attack run error"
curl -sf http://127.0.0.1:$PORT/flush; kill $SRV; wait $SRV 2>/dev/null
python scripts/192_v74_analysis.py calibrate $A _spot || echo "v75 calibration FAILED"
exit 0
