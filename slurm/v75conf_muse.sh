#!/bin/bash
# v75 confirmation (prereg v75; arms spot vs spotgate): AgentDojo confirmation user tasks; none and gate arms run concurrently through one server (frozen
# CAPE readout and steering, development tau); attacks then benign (3 trials). Only if the go rule passed. Usage: bash slurm/v75conf.sh <actor>
set -uo pipefail
# v74 Addendum 1: Muse, served in the vLLM-0.30 env (as v54/v57/v60/v65s); otherwise identical to slurm/v75conf.sh
vpy() { ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src VLLM_CACHE_ROOT=/data/models/cape_ws/cache/vllm030 TRITON_CACHE_DIR=/data/models/cape_ws/cache/triton030; python "$@" ); }
A=museglimmer; PORT=$((8200 + ${SLURM_JOB_ID:-0} % 700)); export V65_PORT=$PORT V65_ACTOR=$A V74_OUT=$PWD/outputs/v75 V74_RES=$PWD/results/prereg_v75 V74_CONC=32
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
AD=/data/models/cape_ws/envs/agentdojo/bin/python; O=outputs/v75
python -c "import json,sys; c=json.load(open('results/prereg_v75/calibration_${A}_spot.json')); sys.exit(0 if c['go'] else 1)" || { echo "v75conf $A: go rule not met; not run (preregistered)"; exit 0; }
vpy scripts/174_vllm_steer.py stage=serve actor=$A port=$PORT log=$O/server_conf_${A}_spot.jsonl tau_file=$O/tau_${A}_spot.json shadow=true &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v75conf: SERVER DIED"; exit 0; }; sleep 5; done
P=(); for ARM in spot spotgate; do (timeout 10h $AD -I scripts/191_v74_agentdojo.py run $ARM conf attack conf_${A}_${ARM}_attack 1 || echo "v75conf $ARM attack run error") & P+=($!); done; wait "${P[@]}"
P=(); for ARM in spot spotgate; do (timeout 4h $AD -I scripts/191_v74_agentdojo.py run $ARM conf benign conf_${A}_${ARM}_benign 3 || echo "v75conf $ARM benign run error") & P+=($!); done; wait "${P[@]}"
kill $SRV; wait $SRV 2>/dev/null
python scripts/192_v74_analysis.py analyze _spot || echo "v75 analysis FAILED"
exit 0
