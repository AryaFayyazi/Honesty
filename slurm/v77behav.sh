#!/bin/bash
# v77 secondary (descriptive): the third-party injection shown to the agent (behaviour), development pairs, frozen-readout shadow scores.
# Usage (via slurm/run.sh): bash slurm/v77behav.sh <actor>
set -uo pipefail
A=$1; PORT=$((8200 + ${SLURM_JOB_ID:-0} % 700)); export V65_PORT=$PORT V65_ACTOR=$A V74_OUT=$PWD/outputs/v77 V74_ATTACK=thirdparty
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
AD=/data/models/cape_ws/envs/agentdojo/bin/python; O=outputs/v77; mkdir -p $O
vpy() { if [ "$A" = museglimmer ]; then ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src VLLM_CACHE_ROOT=/data/models/cape_ws/cache/vllm030 TRITON_CACHE_DIR=/data/models/cape_ws/cache/triton030; python "$@" ); else python "$@"; fi; }
vpy scripts/174_vllm_steer.py stage=serve actor=$A port=$PORT log=$O/server_behav_$A.jsonl shadow=true &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v77behav: SERVER DIED"; exit 0; }; sleep 5; done
timeout 6h $AD -I scripts/191_v74_agentdojo.py run none dev attack dev_${A}_thirdparty_attack 1 || echo "v77behav run error"
kill $SRV; wait $SRV 2>/dev/null
exit 0
