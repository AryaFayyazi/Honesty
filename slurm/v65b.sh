#!/bin/bash
# v65b (prereg docs/preregistration_v65.md, Addenda 4 and 6; vLLM steering server): confirmation tasks, one arm per job (none | gate), 4 trials each;
# the gate job also labels both arms and runs the analysis. Runs only if v65a calibration exists and the development
# violation rate is >= 0.05 (preregistered). Run via slurm/run.sh:  bash slurm/v65b.sh none|gate
set -uo pipefail
ARM=$1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True TAU2_DATA_DIR=/data/models/cape_ws/datasets/tau2-bench/data LITELLM_LOCAL_MODEL_COST_MAP=True
T2=/data/models/cape_ws/envs/tau2/bin/python; O=outputs/v65
[ -f results/prereg_v65/calibration.json ] || { echo "v65b: no calibration; not run"; exit 0; }
python -c "import json,sys; c=json.load(open('results/prereg_v65/calibration.json')); sys.exit(0 if c['episodes_with_violation_dev'] >= 0.05 else 1)" || { echo "v65b: development violation rate < 0.05; not run (preregistered)"; exit 0; }
REFIT=$(python -c "import json;print('gate_refit=outputs/v65/gate_refit.npz' if json.load(open('outputs/v65/tau.json'))['mode']=='refit' else '')")
export LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
python scripts/174_vllm_steer.py stage=serve actor=qwen38 port=8124 log=$O/server_conf.jsonl tau_file=$O/tau.json $REFIT shadow=false &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:8124/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v65b: SERVER DIED"; exit 0; }; sleep 5; done
timeout 23h $T2 scripts/172_v65_tau2_run.py run $ARM conf 4 v65_conf_$ARM 32 || echo "v65b $ARM run error"
kill $SRV; wait $SRV 2>/dev/null
$T2 scripts/172_v65_tau2_run.py label v65_conf_$ARM
if [ "$ARM" = gate ]; then python scripts/173_v65_analysis.py stage=analyze || echo "v65b analysis FAILED"; fi
exit 0
