#!/bin/bash
# v66 selected cell, confirmation (prereg v66): 30 confirmation tasks x 4 trials (tau2 seed 662, same in both arms), one arm per job;
# runs only if this cell's tagged calibration exists and its informed development rate is >= 0.05. The gate job labels, waits for
# the none arm's labels, and analyses (V1 = informed-violation episodes).
# Usage (via slurm/run.sh): bash slurm/v66cell_conf.sh <actor> <P0_orc|P0_orc_enf> <none|gate>
set -uo pipefail
A=$1; C=$2; ARM=$3; TAG=_v66_${A}_$C
PORT=$((8200 + ${SLURM_JOB_ID:-0} % 700)); export V65_PORT=$PORT
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True TAU2_DATA_DIR=/data/models/cape_ws/datasets/tau2-bench/data LITELLM_LOCAL_MODEL_COST_MAP=True V65_ACTOR=$A V65_COND=$C
export LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
T2=/data/models/cape_ws/envs/tau2/bin/python; O=outputs/v65; N=v66_conf_${A}_${C}_$ARM
python -c "import json,sys; c=json.load(open('results/prereg_v65/calibration$TAG.json')); sys.exit(0 if c['dev_runs']=='v66_dev_${A}_$C' and c['positive']=='informed' and c['episodes_with_violation_dev']>=0.05 else 1)" || { echo "v66cell_conf: no matching calibration or informed development rate < 0.05; not run (preregistered)"; exit 0; }
REFIT=$(python -c "import json;print('gate_refit=outputs/v65/gate_refit$TAG.npz' if json.load(open('outputs/v65/tau$TAG.json'))['mode']=='refit' else '')")
SD=$TAU2_DATA_DIR/simulations/$N; [ -e $SD ] && mv $SD ${SD}_partial_$(date +%s)
python scripts/174_vllm_steer.py stage=serve actor=$A port=$PORT log=$O/server_$N.jsonl tau_file=$O/tau$TAG.json $REFIT shadow=false &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v66cell_conf: SERVER DIED"; exit 0; }; sleep 5; done
timeout 23h $T2 scripts/172_v65_tau2_run.py run $ARM conf 4 $N 32 662 || echo "v66cell_conf $ARM run error"
kill $SRV; wait $SRV 2>/dev/null
$T2 scripts/172_v65_tau2_run.py label $N
if [ "$ARM" = gate ]; then
  for i in $(seq 1 720); do [ -f $O/episodes_v66_conf_${A}_${C}_none.csv ] && break; sleep 60; done
  python scripts/173_v65_analysis.py stage=analyze conf_none=v66_conf_${A}_${C}_none conf_gate=$N conf_log=$O/server_$N.jsonl tag=$TAG positive=informed || echo "v66cell analysis FAILED"
fi
exit 0
