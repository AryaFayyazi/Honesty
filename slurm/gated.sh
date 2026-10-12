#!/bin/bash
# v9 closed-loop gate runs. usage: bash slurm/gated.sh <arm>
set -uo pipefail
a=$1
python scripts/21_gated_rollouts.py model=Qwen/Qwen3.8-27B arm=$a split=v2fresh "cf_values=[unsafe]" "seeds=[0,1,2,3,4,5,6,7]" out_name=gated_${a}_v2fresh_minus || echo "GATED FAILED $a minus"
python scripts/21_gated_rollouts.py model=Qwen/Qwen3.8-27B arm=$a split=v2fresh "cf_values=[safe]" "seeds=[0,1]" out_name=gated_${a}_v2fresh_plus || echo "GATED FAILED $a plus"
