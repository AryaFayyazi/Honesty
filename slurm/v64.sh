#!/bin/bash
# v64 (prereg docs/preregistration_v64.md): Gemma gate-then-ask rerun with transcripts and reports (same configuration as v59d);
# judge the x- reports of all four models (rubric v4, UNPARSED retry); model approver on every logged ask; analysis. Run via slurm/run.sh.
set -uo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
O=outputs/v64
timeout 8h python scripts/160_v59b_gate_always.py actor=gemma4 policy=escalate tag=_esc64 K=12 n_per_world=200 n_minus=100 report=true stage=run || echo "v64 Gemma rerun FAILED"
judge() {   # $1 = stem under outputs/v64: judge once, re-judge UNPARSED once with a larger budget (as v61c / v63)
  [ -f $O/$1.parquet ] || { echo "v64: $1 missing"; return 1; }
  python scripts/97_rubric_timeline.py revised=$O/$1.parquet || return 1
  python - <<PY
import pandas as pd
J = pd.read_parquet("$O/${1}_rubric3.parquet"); R = pd.read_parquet("$O/${1}.parquet")
u = set(zip(J[J.label == "UNPARSED"].message, J[J.label == "UNPARSED"].episode_id)); Rr = R[[k in u for k in zip(R.message, R.episode_id)]]
print("UNPARSED to re-judge:", len(Rr))
if len(Rr): Rr.to_parquet("$O/${1}_retry.parquet")
PY
  [ -f $O/${1}_retry.parquet ] && python scripts/97_rubric_timeline.py revised=$O/${1}_retry.parquet max_think=12000
  return 0
}
for X in gemma4:_esc64 gptoss20b:_esc64 museglimmer:_esc qwen38:_esc; do judge revised_v64${X#*:}_${X%%:*} || echo "v64 judge FAILED for $X"; done
python scripts/170_v64_e2e_all.py stage=approver || echo "v64 approver FAILED"
python scripts/170_v64_e2e_all.py stage=analyze || echo "v64 analysis FAILED"
exit 0
