#!/bin/bash
# Cross-model rollouts on v2fresh for white-box gate tests. usage: bash slurm/xm_rollouts.sh <actor>
set -uo pipefail
a=$1
python scripts/20_server_rollouts.py actor=$a split=v2fresh out_name=xm_${a}_v2fresh_minus "seeds=[0,1,2,3]" "cf_values=[unsafe]" || echo "XM FAILED $a minus"
python scripts/20_server_rollouts.py actor=$a split=v2fresh out_name=xm_${a}_v2fresh_plus "seeds=[0,1]" "cf_values=[safe]" || echo "XM FAILED $a plus"
