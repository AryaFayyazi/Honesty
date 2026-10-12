#!/bin/bash
# Features for the monitor-aware exploration pilot: actor L46 (frozen probe layer) + matched-info observers.
set -euo pipefail
for st in reasoning internal; do
  python scripts/03_extract_activations.py model=Qwen/Qwen3.8-27B trajectories=outputs/rollouts/aware_explore_$st.parquet \
    "layers=[46]" pooling=pre_action_last out=outputs/activations/aware_explore_$st/L46 check_episodes=4
  python scripts/05b_observer_states.py trajectories=outputs/rollouts/aware_explore_$st.parquet observer=Qwen/Qwen3-8B \
    "layers=[27]" scenarios=outputs/capebench/aware_explore_$st/scenarios.jsonl "variants=[cotpre]"
  python scripts/05b_observer_states.py trajectories=outputs/rollouts/aware_explore_$st.parquet \
    observer=meta-llama/Llama-3.1-8B-Instruct "layers=[24]" scenarios=outputs/capebench/aware_explore_$st/scenarios.jsonl "variants=[cotpre]"
done
