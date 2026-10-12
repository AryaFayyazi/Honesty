#!/bin/bash
# Mechanism-1 agent-level fix (prereg v21). Usage:
#   sbatch -J m1data  slurm/run.sh bash slurm/m1fix.sh data    # vLLM: sample + verify + pairs + contamination check
#   sbatch -J m1train --time=48:00:00 slurm/run.sh bash slurm/m1fix.sh train   # HF: smoke step, DPO, merge
set -euo pipefail
case "$1" in
  data)
    sha256sum -c <(grep sites.parquet results/v21_prereg.sha256)   # locked sites, used as-is
    python scripts/36_m1_pref_data.py stage=data
    python scripts/33_authority_eval.py stage=contam train=outputs/m1pref/pairs.parquet | tee outputs/m1pref/contam_m1pref.txt
    python scripts/33_authority_eval.py stage=contam train=outputs/m1pref/pairs_noinv.parquet | tee outputs/m1pref/contam_m1pref_noinv.txt
    ;;
  train)
    test -s outputs/m1pref/pairs.parquet || { echo "no pairs: data job failed"; exit 1; }
    grep -q '"clean": true' outputs/m1pref/contam_m1pref.txt || { echo "contamination check missing/failed"; exit 1; }
    python scripts/37_m1_dpo.py stage=train smoke=true      # fails fast on OOM / shape problems
    python scripts/37_m1_dpo.py stage=train arm=m1pref data=pairs
    python scripts/37_m1_dpo.py stage=merge arm=m1pref
    ;;
esac
