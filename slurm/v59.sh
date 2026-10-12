#!/bin/bash
# v59 continuation for one actor (after its v54 confirmation). Run via slurm/run.sh; Muse in the v030 env.
# The vLLM run and the analysis are separate processes, so an analysis error cannot leave a vLLM engine holding the GPU.
set -uo pipefail
A=$1
if [ "$A" = museglimmer ]; then
  ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src VLLM_CACHE_ROOT=/data/models/cape_ws/cache/vllm030 TRITON_CACHE_DIR=/data/models/cape_ws/cache/triton030; timeout 4h python scripts/159_v59_continue.py actor=$A stage=run_only )
else
  timeout 4h python scripts/159_v59_continue.py actor=$A stage=run_only
fi
python scripts/159_v59_continue.py actor=$A stage=analyze || echo "v59 analysis failed for $A"
exit 0
