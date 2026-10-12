#!/bin/bash
# v55 decision states for the main-env actors (run via slurm/run.sh). Muse runs separately via slurm/run_v030.sh.
set -euo pipefail
for A in gemma4 gptoss20b qwen38; do
  [ -f outputs/v55/decision_$A.npz ] || python scripts/148_v55_extract.py actor=$A
done
