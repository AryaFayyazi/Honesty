#!/bin/bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=160G
#SBATCH --time=24:00:00
#SBATCH --output=/data/models/cape_ws/outputs/slurm_logs/%x-%j.out
# Like slurm/run.sh but with the separate vLLM 0.30 environment (models unsupported by vLLM 0.26, e.g. Muse-Glimmer).
set -euo pipefail
cd /home/arya/new_safety/cape
source /data/models/cape_ws/envs/v030/bin/activate
export PYTHONPATH=/home/arya/new_safety/cape/src HF_HUB_CACHE=/data/models HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false PYTHONUNBUFFERED=1 VLLM_WORKER_MULTIPROC_METHOD=spawn
export VLLM_CACHE_ROOT=/data/models/cape_ws/cache/vllm030 TRITON_CACHE_DIR=/data/models/cape_ws/cache/triton030 XDG_CACHE_HOME=/data/models/cape_ws/cache
echo "job $SLURM_JOB_ID on $(hostname) start $(date)"; nvidia-smi --query-gpu=name,memory.total --format=csv
"$@"
echo "end $(date)"
