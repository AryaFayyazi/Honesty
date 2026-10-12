#!/bin/bash
# v75 Addendum 1 (operational, GPU deadline 09:00): the v75 development run split into its two parts on two GPUs; this part: attack.
# Same server code, model, arm (spot), seeds and episodes as slurm/v75dev.sh; shadow scores do not depend on tau. Own server log;
# scripts/192 calibrate merges server_dev_<A>_spot.jsonl and server_dev_<A>_spot_atk.jsonl. Usage: bash slurm/v75dev_attack.sh <actor>
set -uo pipefail
A=$1; PORT=$((8200 + ${SLURM_JOB_ID:-0} % 700)); export V65_PORT=$PORT V65_ACTOR=$A V74_OUT=$PWD/outputs/v75 V74_RES=$PWD/results/prereg_v75
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
AD=/data/models/cape_ws/envs/agentdojo/bin/python; O=outputs/v75; mkdir -p $O
vpy() { if [ "$A" = museglimmer ]; then ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src VLLM_CACHE_ROOT=/data/models/cape_ws/cache/vllm030 TRITON_CACHE_DIR=/data/models/cape_ws/cache/triton030; python "$@" ); else python "$@"; fi; }
vpy scripts/174_vllm_steer.py stage=serve actor=$A port=$PORT log=$O/server_dev_${A}_spot_atk.jsonl shadow=true &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v75dev_attack: SERVER DIED"; exit 0; }; sleep 5; done
timeout 8h $AD -I scripts/191_v74_agentdojo.py run spot dev attack dev_${A}_spot_attack 1 || echo "v75dev_attack run error"
curl -sf http://127.0.0.1:$PORT/flush; kill $SRV; wait $SRV 2>/dev/null
exit 0
