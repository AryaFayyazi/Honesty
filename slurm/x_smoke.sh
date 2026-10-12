#!/bin/bash
set -euo pipefail
for a in gptoss20b gemma4; do
  python scripts/20_server_rollouts.py actor=$a split=v2fresh out_name=xsmoke_$a limit=16 "seeds=[0]" || echo "SMOKE FAILED $a"
done
