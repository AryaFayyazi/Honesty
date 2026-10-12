#!/bin/bash
# v18 after the base core run: seed rule (base only), then base seed extension if the rule fires (resumable per cell)
set -uo pipefail
python scripts/33_authority_eval.py stage=power ckpt=base || { echo "POWER FAILED"; exit 1; }
python scripts/33_authority_eval.py stage=rollout ckpt=base tier=core || echo "BASE EXTENSION FAILED"
