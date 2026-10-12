#!/bin/bash
# v76 development (prereg docs/preregistration_v76.md): undefended AgentDojo development episodes (as v74, arm none, shadow scores)
# with the pre-action features saved for the in-domain readout fit. One part per job; attacks may be sharded over GPUs.
# Usage (via slurm/run.sh): bash slurm/v76dev_part.sh <actor> <benign|attack> [i/n]
set -uo pipefail
A=$1; PART=$2; SH=${3:-}; PORT=$((8200 + ${SLURM_JOB_ID:-0} % 700)); export V65_PORT=$PORT V65_ACTOR=$A V74_OUT=$PWD/outputs/v76 V74_RES=$PWD/results/prereg_v76
[ -n "$SH" ] && export V74_SHARD=$SH
SUF=${PART}$([ -n "$SH" ] && echo "_s${SH%%/*}")
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
AD=/data/models/cape_ws/envs/agentdojo/bin/python; O=outputs/v76; mkdir -p $O
vpy() { if [ "$A" = museglimmer ]; then ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src VLLM_CACHE_ROOT=/data/models/cape_ws/cache/vllm030 TRITON_CACHE_DIR=/data/models/cape_ws/cache/triton030; python "$@" ); else python "$@"; fi; }
vpy scripts/174_vllm_steer.py stage=serve actor=$A port=$PORT log=$O/server_dev_${A}_${SUF}.jsonl shadow=true save_feats=$O/feats_dev_${A}_${SUF}.npz &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v76dev: SERVER DIED"; exit 0; }; sleep 5; done
TR=$([ $PART = benign ] && echo 3 || echo 1)
timeout 8h $AD -I scripts/191_v74_agentdojo.py run none dev $PART dev_${A}_${PART} $TR || echo "v76dev $PART run error"
curl -sf http://127.0.0.1:$PORT/flush; kill $SRV; wait $SRV 2>/dev/null
exit 0
