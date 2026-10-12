#!/bin/bash
set -uo pipefail
for s in core24_minus core24_plus; do
  python scripts/03_extract_activations.py model=Qwen/Qwen3.8-27B trajectories=outputs/rollouts/$s.parquet "layers=[30,38,46,54,62]" pooling=pre_action_last check_episodes=2 || echo "C24 EXT FAILED $s"
done
