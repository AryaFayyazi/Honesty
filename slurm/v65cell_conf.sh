#!/bin/bash
# v65 selected cell, confirmation (prereg v65 Addenda 4, 6, 10, 11): 30 confirmation tasks x 4 trials, one arm per job; the gate job
# labels and analyses. Runs only if the cell's calibration exists and its adjudicated development rate is >= 0.05.
# Usage: bash slurm/v65cell_conf.sh <actor> <P1|P0_enf> <none|gate>
set -uo pipefail
A=$1; C=$2; ARM=$3
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True TAU2_DATA_DIR=/data/models/cape_ws/datasets/tau2-bench/data LITELLM_LOCAL_MODEL_COST_MAP=True V65_ACTOR=$A V65_COND=$C
export LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
T2=/data/models/cape_ws/envs/tau2/bin/python; O=outputs/v65; N=v65_conf_${A}_${C}_$ARM
PORT=$([ "$ARM" = gate ] && echo 8125 || echo 8124); export V65_PORT=$PORT   # the two arms can run in parallel on the two GPUs; the gate job waits at most 6 h for the none arm's labels
if [ "$A" = museglimmer ]; then vpy() { ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src VLLM_CACHE_ROOT=/data/models/cape_ws/cache/vllm030 TRITON_CACHE_DIR=/data/models/cape_ws/cache/triton030; python "$@" ); }; else vpy() { python "$@"; }; fi
python -c "import json,sys; c=json.load(open('results/prereg_v65/calibration.json')); sys.exit(0 if c['dev_runs']=='v65_dev_${A}_$C' and c['episodes_with_violation_dev']>=0.05 else 1)" || { echo "v65cell_conf: no matching calibration or development rate < 0.05; not run (preregistered)"; exit 0; }
REFIT=$(python -c "import json;print('gate_refit=outputs/v65/gate_refit.npz' if json.load(open('outputs/v65/tau.json'))['mode']=='refit' else '')")
SD=$TAU2_DATA_DIR/simulations/$N; [ -e $SD ] && mv $SD ${SD}_partial_$(date +%s)
vpy scripts/174_vllm_steer.py stage=serve actor=$A port=$PORT log=$O/server_conf_${A}_${C}_$ARM.jsonl tau_file=$O/tau.json $REFIT shadow=false &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v65cell_conf: SERVER DIED"; exit 0; }; sleep 5; done
timeout 23h $T2 scripts/172_v65_tau2_run.py run $ARM conf 4 $N 32 || echo "v65cell_conf $ARM run error"
kill $SRV; wait $SRV 2>/dev/null
$T2 scripts/172_v65_tau2_run.py label $N
if [ "$ARM" = gate ]; then for i in $(seq 1 360); do [ -f $O/episodes_v65_conf_${A}_${C}_none.csv ] && break; sleep 60; done; python scripts/173_v65_analysis.py stage=analyze conf_none=v65_conf_${A}_${C}_none conf_gate=v65_conf_${A}_${C}_gate conf_log=$O/server_conf_${A}_${C}_gate.jsonl || echo "v65cell analysis FAILED"; fi
exit 0
