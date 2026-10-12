#!/bin/bash
set -uo pipefail
for a in qwen3_4b qwen3_8b qwen3_14b qwen3_32b llama33_70b; do
  python scripts/20_server_rollouts.py actor=$a split=v2fresh out_name=v24smoke_$a limit=16 "seeds=[0]" || echo "V24 SMOKE FAILED $a"
done
