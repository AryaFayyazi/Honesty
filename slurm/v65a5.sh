#!/bin/bash
# v65a, attempt 4 (prereg v65 Addendum 8; typed tool arguments): development run to completion with the validated vLLM steering server
# (scripts/174 serve; shadow scores + features), 20 tasks x 3 trials; labels; calibration. Run via slurm/run.sh.
set -uo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True TAU2_DATA_DIR=/data/models/cape_ws/datasets/tau2-bench/data LITELLM_LOCAL_MODEL_COST_MAP=True
export LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
T2=/data/models/cape_ws/envs/tau2/bin/python; O=outputs/v65
SD=$TAU2_DATA_DIR/simulations/v65_dev5_none   # restart safety (yield guard requeue): a partial earlier attempt is moved aside, never resumed
[ -e $SD ] && mv $SD ${SD}_partial_$(date +%s) && echo "moved aside partial $SD"
[ -e $O/server_dev5.jsonl ] && mv $O/server_dev5.jsonl $O/server_dev5_partial_$(date +%s).jsonl
python scripts/174_vllm_steer.py stage=serve actor=qwen38 port=8124 log=$O/server_dev5.jsonl save_feats=$O/feats_dev5.npz &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:8124/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v65a3: SERVER DIED"; exit 0; }; sleep 5; done
echo "server ready $(date)"; START=$(date +%s)
timeout 20h $T2 scripts/172_v65_tau2_run.py run none dev 3 v65_dev5_none 32 || echo "v65a3 run error"
echo "dev run took $(( $(date +%s) - START )) s"
curl -sf http://127.0.0.1:8124/flush; kill $SRV; wait $SRV 2>/dev/null
$T2 scripts/172_v65_tau2_run.py label v65_dev5_none
python scripts/173_v65_analysis.py stage=calibrate || echo "v65a3 calibration FAILED"
exit 0
