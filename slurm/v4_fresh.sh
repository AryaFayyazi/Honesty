#!/bin/bash
# v4 confirmation set D2 (docs/preregistration_v4.md): fresh seed-11 scenarios, unaware, x- seeds 0-15, + features.
set -euo pipefail
n=v4fresh_minus
python scripts/02_collect_rollouts.py model=Qwen/Qwen3.8-27B split=v4fresh out_name=$n \
  "seeds=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]" "cf_values=[unsafe]"
python scripts/03_extract_activations.py model=Qwen/Qwen3.8-27B trajectories=outputs/rollouts/$n.parquet \
  "layers=[46]" pooling=pre_action_last out=outputs/activations/$n/L46 check_episodes=4
python scripts/05b_observer_states.py trajectories=outputs/rollouts/$n.parquet observer=Qwen/Qwen3-8B \
  "layers=[27]" scenarios=outputs/capebench/v4fresh/scenarios.jsonl "variants=[cotpre]"
python scripts/05b_observer_states.py trajectories=outputs/rollouts/$n.parquet observer=meta-llama/Llama-3.1-8B-Instruct \
  "layers=[24]" scenarios=outputs/capebench/v4fresh/scenarios.jsonl "variants=[cotpre]"
