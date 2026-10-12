#!/bin/bash
# usage (inside slurm/run.sh): bash slurm/tau2_run.sh <trials> <name_prefix> <conds comma-sep> [task_ids comma-sep]
# Starts a local vLLM OpenAI server for Qwen3.8-27B (127.0.0.1 only), runs each condition through tau2, stops the server.
set -uo pipefail
TRIALS=$1; PREFIX=$2; CONDS=$3; TASKS=${4:-}
M=/data/models/models--Qwen--Qwen3.8-27B/snapshots/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0
export LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
python -m vllm.entrypoints.openai.api_server --model $M --served-model-name qwen38 --host 127.0.0.1 --port 8124 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3 --max-model-len 32768 \
  --gpu-memory-utilization 0.9 --language-model-only --gdn-prefill-backend triton --enable-prefix-caching --max-num-seqs 256 &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:8124/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "SERVER DIED"; exit 1; }; sleep 5; done
echo "server ready $(date)"
export TAU2_DATA_DIR=/data/models/cape_ws/datasets/tau2-bench/data LITELLM_LOCAL_MODEL_COST_MAP=True
for c in ${CONDS//,/ }; do
  /data/models/cape_ws/envs/tau2/bin/python scripts/47_tau2_port.py run $c $TRIALS ${PREFIX}_$c $TASKS || echo "TAU2 FAILED $c"
  echo "done $c $(date)"
done
kill $SRV; wait $SRV 2>/dev/null; echo "server stopped"
