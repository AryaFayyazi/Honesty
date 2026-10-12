#!/bin/bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=160G
#SBATCH --time=24:00:00
#SBATCH --output=/data/models/cape_ws/outputs/slurm_logs/%x-%j.out
# Usage: sbatch -J <name> slurm/run.sh <python-or-pytest args...>
#   e.g. sbatch -J smoke slurm/run.sh python scripts/00_smoke_model.py model=Qwen/Qwen3.8-27B dtype=bfloat16
set -euo pipefail
cd /home/arya/new_safety/cape
source .venv/bin/activate
export PATH=$PATH:/data/models/cider_ws/envs/cider/bin
export HF_HUB_CACHE=/data/models HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONUNBUFFERED=1 VLLM_WORKER_MULTIPROC_METHOD=spawn
export VLLM_CACHE_ROOT=/data/models/cape_ws/cache/vllm TRITON_CACHE_DIR=/data/models/cape_ws/cache/triton TORCHINDUCTOR_CACHE_DIR=/data/models/cape_ws/cache/inductor XDG_CACHE_HOME=/data/models/cape_ws/cache
echo "job $SLURM_JOB_ID on $(hostname) gpu=$CUDA_VISIBLE_DEVICES start $(date)"
nvidia-smi --query-gpu=name,memory.total --format=csv
"$@"
echo "end $(date)"
