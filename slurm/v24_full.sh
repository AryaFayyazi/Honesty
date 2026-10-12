#!/bin/bash
# usage: bash slurm/v24_full.sh <actor> [splits...]   (skips the actor if it failed the pre-registered health gate)
set -uo pipefail
a=$1; shift; splits=${@:-v2fresh v10enf}
python scripts/v24_health.py $a | grep -q '"pass": true' || { echo "V24 HEALTH GATE FAILED $a - skipped"; exit 0; }
for sp in $splits; do
  python scripts/20_server_rollouts.py actor=$a split=$sp out_name=x_${a}_${sp}_minus "seeds=[0,1,2,3]" || echo "V24 FAILED $a $sp"
done
