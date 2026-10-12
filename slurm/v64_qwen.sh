#!/bin/bash
# v64 addendum 2: Qwen gate-then-ask rerun with transcripts and reports (tag _esc64, identical configuration and seeds; the
# v59d _esc run hit its 8 h timeout during step 12). Then judge Qwen's x- reports, rerun the approver and the analysis.
# Run via slurm/run.sh.
set -uo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
O=outputs/v64
timeout 13h python scripts/160_v59b_gate_always.py actor=qwen38 policy=escalate tag=_esc64 K=12 n_per_world=200 n_minus=100 report=true stage=run || echo "v64 Qwen rerun FAILED"
python scripts/160_v59b_gate_always.py actor=qwen38 tag=_esc64 K=12 stage=analyze_tag || echo "v64 Qwen D1/D2' analysis FAILED"
S=revised_v64_esc64_qwen38
if [ -f $O/$S.parquet ]; then
  python scripts/97_rubric_timeline.py revised=$O/$S.parquet || echo "v64 Qwen judge FAILED"
  python - <<PY
import pandas as pd
J = pd.read_parquet("$O/${S}_rubric3.parquet"); R = pd.read_parquet("$O/${S}.parquet")
u = set(zip(J[J.label == "UNPARSED"].message, J[J.label == "UNPARSED"].episode_id)); Rr = R[[k in u for k in zip(R.message, R.episode_id)]]
print("UNPARSED to re-judge:", len(Rr))
if len(Rr): Rr.to_parquet("$O/${S}_retry.parquet")
PY
  [ -f $O/${S}_retry.parquet ] && python scripts/97_rubric_timeline.py revised=$O/${S}_retry.parquet max_think=12000
else
  echo "v64: $S missing"
fi
python scripts/170_v64_e2e_all.py stage=approver || echo "v64 approver FAILED"
python scripts/170_v64_e2e_all.py stage=analyze || echo "v64 analysis FAILED"
exit 0
