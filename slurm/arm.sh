#!/bin/bash
# Generic x- arm: rollout (seeds given) + frozen-probe features. usage: bash slurm/arm.sh <bench> <out_name> "<seeds>" [model]
set -euo pipefail
b=$1; n=$2; seeds=$3
python scripts/02_collect_rollouts.py model=${4:-Qwen/Qwen3.8-27B} split=$b out_name=$n "seeds=$seeds" "cf_values=[unsafe]"
python scripts/03_extract_activations.py model=${4:-Qwen/Qwen3.8-27B} trajectories=outputs/rollouts/$n.parquet \
  "layers=[46]" pooling=pre_action_last out=outputs/activations/$n/L46 check_episodes=4
python scripts/05b_observer_states.py trajectories=outputs/rollouts/$n.parquet observer=Qwen/Qwen3-8B \
  "layers=[27]" scenarios=outputs/capebench/$b/scenarios.jsonl "variants=[cotpre]"
python scripts/05b_observer_states.py trajectories=outputs/rollouts/$n.parquet observer=meta-llama/Llama-3.1-8B-Instruct \
  "layers=[24]" scenarios=outputs/capebench/$b/scenarios.jsonl "variants=[cotpre]"
