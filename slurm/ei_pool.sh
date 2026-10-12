#!/bin/bash
# EI round k pool: sample seed-13 scenarios with the current model, CoT-only monitor, selection.
# usage: bash slurm/ei_pool.sh <round> <model>
set -euo pipefail
k=$1; m=$2
python scripts/02_collect_rollouts.py model=$m split=ei_s13 out_name=ei_pool_r${k}_minus "seeds=[0,1,2,3,4,5,6,7]" "cf_values=[unsafe]"
python scripts/02_collect_rollouts.py model=$m split=ei_s13 out_name=ei_pool_r${k}_plus "seeds=[0,1]" "cf_values=[safe]"
for s in minus plus; do
  python scripts/16_cot_monitor.py trajectories=outputs/rollouts/ei_pool_r${k}_$s.parquet scenarios=outputs/capebench/ei_s13/scenarios.jsonl
done
python scripts/17_ei_sft.py stage=select round=$k "pool=[ei_pool_r${k}_minus,ei_pool_r${k}_plus]"
