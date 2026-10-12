#!/bin/bash
# v76 confirmation (prereg v76): one arm per job/GPU; gate arm = in-domain refit readout + development tau + FROZEN CAPE steering.
# Server log: gate -> server_conf_<A>.jsonl (read by scripts/192), none -> server_conf_<A>_ref.jsonl. Only if the v76 go rule passed.
# Usage: bash slurm/v76conf_shard.sh <actor> <none|gate> <i/n>   (v76 Addendum 2: one arm sharded over GPUs; shard files merged by scripts/198)
set -uo pipefail
A=$1; ARM=$2; SH=$3; export V74_SHARD=$SH; PORT=$((8200 + ${SLURM_JOB_ID:-0} % 700)); export V65_PORT=$PORT V65_ACTOR=$A V74_OUT=$PWD/outputs/v76 V74_RES=$PWD/results/prereg_v76 V74_CONC=64
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
AD=/data/models/cape_ws/envs/agentdojo/bin/python; O=outputs/v76
vpy() { if [ "$A" = museglimmer ]; then ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src VLLM_CACHE_ROOT=/data/models/cape_ws/cache/vllm030 TRITON_CACHE_DIR=/data/models/cape_ws/cache/triton030; python "$@" ); else python "$@"; fi; }
python -c "import json,sys; c=json.load(open('results/prereg_v76/calibration_$A.json')); sys.exit(0 if c['go'] else 1)" || { echo "v76conf_arm $A $ARM: go rule not met; not run (preregistered)"; exit 0; }
LOG=$O/server_conf_${A}$([ $ARM = none ] && echo _ref)_s${SH%%/*}.jsonl
vpy scripts/174_vllm_steer.py stage=serve actor=$A port=$PORT log=$LOG gate_refit=$O/gate_refit_$A.npz tau_file=$O/tau_$A.json shadow=true &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v76conf_arm: SERVER DIED"; exit 0; }; sleep 5; done
timeout 10h $AD -I scripts/191_v74_agentdojo.py run $ARM conf attack conf_${A}_${ARM}_attack 1 || echo "v76conf_arm $ARM attack run error"
timeout 4h $AD -I scripts/191_v74_agentdojo.py run $ARM conf benign conf_${A}_${ARM}_benign 3 || echo "v76conf_arm $ARM benign run error"
kill $SRV; wait $SRV 2>/dev/null
exit 0
