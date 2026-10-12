#!/bin/bash
set -uo pipefail
for a in gptoss20b gemma4; do
  python scripts/20_server_rollouts.py actor=$a split=v2fresh out_name=x_${a}_v2fresh_minus "seeds=[0,1,2,3]" || echo "FULL FAILED $a"
done
