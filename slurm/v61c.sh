#!/bin/bash
# v61c (prereg docs/preregistration_v61.md, v61c section): the evidence contract as the lie stage, end to end, Muse. Run via slurm/run.sh.
set -uo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
A=museglimmer; O=outputs/v61
muse_py() { ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src; python "$@" ); }
muse_py scripts/165_v61_e2e.py actor=$A mode=v61c tag=_c n_minus=200 n_plus=0 K=12 stage=run || { echo "v61c run FAILED"; exit 0; }
python scripts/97_rubric_timeline.py revised=$O/revised_c_$A.parquet || { echo "v61c judge FAILED"; exit 0; }
python - <<PY
import pandas as pd
J = pd.read_parquet("$O/revised_c_${A}_rubric3.parquet"); R = pd.read_parquet("$O/revised_c_$A.parquet")
u = set(zip(J[J.label == "UNPARSED"].set, J[J.label == "UNPARSED"].episode_id, J[J.label == "UNPARSED"].message))
Rr = R[[k in u for k in zip(R.set, R.episode_id, R.message)]]; print("UNPARSED to re-judge:", len(Rr))
if len(Rr): Rr.to_parquet("$O/revised_c_retry_$A.parquet")
PY
[ -f $O/revised_c_retry_$A.parquet ] && python scripts/97_rubric_timeline.py revised=$O/revised_c_retry_$A.parquet max_think=12000
python scripts/165_v61_e2e.py actor=$A tag=_c treated=none_contract stage=analyze_b || echo "v61c analysis FAILED"
exit 0
