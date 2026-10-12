#!/bin/bash
# v72 confirmation (prereg v72): exact-pair gate requests on confirmation sites with the refit readout; only if the go rule passed.
# Usage (via slurm/run.sh): bash slurm/v72conf.sh <actor>
set -uo pipefail
A=$1; PORT=$((8200 + ${SLURM_JOB_ID:-0} % 700)); export V65_PORT=$PORT V65_ACTOR=$A V70_OUT=$PWD/outputs/v72 V70_SALT=v72
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True TAU2_DATA_DIR=/data/models/cape_ws/datasets/tau2-bench/data LITELLM_LOCAL_MODEL_COST_MAP=True
export LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
T2=/data/models/cape_ws/envs/tau2/bin/python; O=outputs/v72
python -c "import json,sys; c=json.load(open('results/prereg_v72/fit_$A.json')); sys.exit(0 if c['go'] else 1)" || { echo "v72conf $A: go rule not met; not run (preregistered)"; exit 0; }
LOG=$O/server_pair_$A.jsonl; [ -e $LOG ] && mv $LOG ${LOG%.jsonl}_partial_$(date +%s).jsonl; export V70_SERVER_LOG=$LOG
python scripts/174_vllm_steer.py stage=serve actor=$A port=$PORT log=$LOG tau_file=$O/tau_$A.json gate_refit=$O/gate_refit_$A.npz shadow=false &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v72conf: SERVER DIED"; exit 0; }; sleep 5; done
timeout 6h $T2 scripts/187_v70_real_context.py run pair conf pair_$A || echo "v72conf run error"
kill $SRV; wait $SRV 2>/dev/null
python scripts/188_v70_analysis.py stage=analyze_pair out=outputs/v72 res=results/prereg_v72 'actors=[gptoss20b,gemma4]' || echo "v72 analysis FAILED"
exit 0
