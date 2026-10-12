#!/bin/bash
set -uo pipefail
for a in gptoss20b gemma4; do
  python scripts/20_server_rollouts.py actor=$a split=v10enf out_name=x_${a}_v10enf_minus "seeds=[0,1,2,3]" || echo "V22 FAILED $a"
done
