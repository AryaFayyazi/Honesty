#!/bin/bash
# v18 checkpoint eval of m1pref (resumable per cell: a second invocation continues where a time-limited one stopped)
set -uo pipefail
CK=/data/models/cape_ws/ckpt/m1pref
[ -f "$CK/config.json" ] || { echo "NO M1PREF CHECKPOINT at $CK - skipping"; exit 0; }
python scripts/33_authority_eval.py stage=rollout ckpt=m1pref path=$CK tier=core || echo "M1PREF EVAL FAILED"
