#!/bin/bash
# usage: bash slurm/xm_rollouts_bench.sh <actor> <bench>
set -uo pipefail
a=$1; b=$2
python scripts/20_server_rollouts.py actor=$a split=$b out_name=xm_${a}_${b}_minus "seeds=[0,1,2,3]" "cf_values=[unsafe]" || echo "XM FAILED $a $b minus"
python scripts/20_server_rollouts.py actor=$a split=$b out_name=xm_${a}_${b}_plus "seeds=[0,1]" "cf_values=[safe]" || echo "XM FAILED $a $b plus"
