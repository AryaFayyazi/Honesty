#!/bin/bash
# v3 CONFIRMATORY arm (docs/preregistration_v3.md): rollout (x- only, seeds 0-7) then frozen-probe features.
# usage: bash slurm/v3_arm.sh <reasoning|internal>
set -euo pipefail
st=$1; n=v3aware_${st}_minus
python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B split=v3aware_$st out_name=$n \
  "seeds=[0,1,2,3,4,5,6,7]" "cf_values=[unsafe]"
python scripts/03_extract_activations.py model=Qwen/Qwen3.8-27B trajectories=outputs/rollouts/$n.parquet \
  "layers=[46]" pooling=pre_action_last out=outputs/activations/$n/L46 check_episodes=4
python scripts/05b_observer_states.py trajectories=outputs/rollouts/$n.parquet observer=Qwen/Qwen3-8B \
  "layers=[27]" scenarios=outputs/capebench/v3aware_$st/scenarios.jsonl "variants=[cotpre]"
python scripts/05b_observer_states.py trajectories=outputs/rollouts/$n.parquet observer=meta-llama/Llama-3.1-8B-Instruct \
  "layers=[24]" scenarios=outputs/capebench/v3aware_$st/scenarios.jsonl "variants=[cotpre]"
