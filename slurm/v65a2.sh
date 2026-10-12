#!/bin/bash
# v65a, attempt 2 (prereg v65 Addendum 2): development run with real server batching (3 s gather, up to 32 per batch,
# 200k-token chunks with OOM halving), 32 concurrent simulations, 3 trials; labels; calibration. Smoke already passed.
set -uo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True TAU2_DATA_DIR=/data/models/cape_ws/datasets/tau2-bench/data LITELLM_LOCAL_MODEL_COST_MAP=True
T2=/data/models/cape_ws/envs/tau2/bin/python; O=outputs/v65
python scripts/171_tau2_steer_server.py actor=qwen38 port=8124 log=$O/server_dev2.jsonl save_feats=$O/feats_dev2.npz batch_wait=3 max_batch=32 max_batch_tokens=200000 &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:8124/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v65a2: SERVER DIED"; exit 0; }; sleep 5; done
START=$(date +%s)
$T2 scripts/172_v65_tau2_run.py run none dev 3 v65_dev2_none 32 || echo "v65a2 dev run error"
echo "dev run took $(( $(date +%s) - START )) s"
curl -sf http://127.0.0.1:8124/flush; kill $SRV; wait $SRV 2>/dev/null
$T2 scripts/172_v65_tau2_run.py label v65_dev2_none
python scripts/173_v65_analysis.py stage=calibrate || echo "v65a2 calibration FAILED"
exit 0
