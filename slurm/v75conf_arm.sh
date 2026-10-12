#!/bin/bash
# v75 Addendum 1 (operational, GPU deadline 09:00): one confirmation arm per job/GPU. Same code, frozen readout/steering, dev tau and
# seeds as slurm/v75conf.sh. Server log: spotgate -> server_conf_<A>_spot.jsonl (read by scripts/192), spot -> server_conf_<A>_spot_ref.jsonl.
# Only if the go rule passed. Usage: bash slurm/v75conf_arm.sh <actor> <spot|spotgate>
set -uo pipefail
A=$1; ARM=$2; PORT=$((8200 + ${SLURM_JOB_ID:-0} % 700)); export V65_PORT=$PORT V65_ACTOR=$A V74_OUT=$PWD/outputs/v75 V74_RES=$PWD/results/prereg_v75 V74_CONC=64
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
AD=/data/models/cape_ws/envs/agentdojo/bin/python; O=outputs/v75
vpy() { if [ "$A" = museglimmer ]; then ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src VLLM_CACHE_ROOT=/data/models/cape_ws/cache/vllm030 TRITON_CACHE_DIR=/data/models/cape_ws/cache/triton030; python "$@" ); else python "$@"; fi; }
python -c "import json,sys; c=json.load(open('results/prereg_v75/calibration_${A}_spot.json')); sys.exit(0 if c['go'] else 1)" || { echo "v75conf_arm $A $ARM: go rule not met; not run (preregistered)"; exit 0; }
LOG=$O/server_conf_${A}_spot$([ $ARM = spot ] && echo _ref).jsonl
vpy scripts/174_vllm_steer.py stage=serve actor=$A port=$PORT log=$LOG tau_file=$O/tau_${A}_spot.json shadow=true &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v75conf_arm: SERVER DIED"; exit 0; }; sleep 5; done
timeout 10h $AD -I scripts/191_v74_agentdojo.py run $ARM conf attack conf_${A}_${ARM}_attack 1 || echo "v75conf_arm $ARM attack run error"
timeout 4h $AD -I scripts/191_v74_agentdojo.py run $ARM conf benign conf_${A}_${ARM}_benign 3 || echo "v75conf_arm $ARM benign run error"
kill $SRV; wait $SRV 2>/dev/null
exit 0
