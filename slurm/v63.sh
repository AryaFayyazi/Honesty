#!/bin/bash
# v63 (prereg docs/preregistration_v63.md): honesty direction built on continued episodes; runs only if v61c H did not pass. Run via slurm/run.sh.
set -uo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
A=museglimmer; O=outputs/v63
C=results/prereg_v61/e2e_c_$A.json
[ -f $C ] || { echo "v63: v61c result missing; not run"; exit 0; }
P=$(python -c "import json;print(json.load(open('$C'))['H_primary_lie_given_violation']['p_one_sided'])")
python -c "import sys; sys.exit(0 if float('$P') < 0.05 else 1)" && { echo "v63: v61c passed (p=$P); not needed (preregistered)"; exit 0; }
muse_py() { ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src; python "$@" ); }
judge() {   # $1 = stem under outputs/v63 (e.g. samples): judge once, re-judge UNPARSED once with a larger budget
  python scripts/97_rubric_timeline.py revised=$O/${1}_rev.parquet || return 1
  python - <<PY
import pandas as pd
J = pd.read_parquet("$O/${1}_rev_rubric3.parquet"); R = pd.read_parquet("$O/${1}_rev.parquet")
u = set(zip(J[J.label == "UNPARSED"].message, J[J.label == "UNPARSED"].episode_id)); Rr = R[[k in u for k in zip(R.message, R.episode_id)]]
print("UNPARSED to re-judge:", len(Rr))
if len(Rr): Rr.to_parquet("$O/${1}_retry.parquet")
PY
  [ -f $O/${1}_retry.parquet ] && python scripts/97_rubric_timeline.py revised=$O/${1}_retry.parquet max_think=12000
  return 0
}
muse_py scripts/165_v61_e2e.py actor=$A mode=v61c split=dev gen_turn0=true tag=_dev63 n_minus=300 n_plus=0 K=12 stage=run || { echo "v63 dev trajectories FAILED"; exit 0; }
muse_py scripts/169_v63_honesty_dir.py stage=sample || { echo "v63 sample FAILED"; exit 0; }
judge samples || { echo "v63 sample judge FAILED"; exit 0; }
muse_py scripts/169_v63_honesty_dir.py stage=extract || { echo "v63 extract FAILED"; exit 0; }
python scripts/169_v63_honesty_dir.py stage=direction || { echo "v63 direction FAILED"; exit 0; }
muse_py scripts/169_v63_honesty_dir.py stage=sweep || { echo "v63 sweep FAILED"; exit 0; }
judge sweep || { echo "v63 sweep judge FAILED"; exit 0; }
python scripts/169_v63_honesty_dir.py stage=choose
muse_py scripts/169_v63_honesty_dir.py stage=fresh || { echo "v63 fresh FAILED"; exit 0; }
[ -f $O/fresh.parquet ] && judge fresh && python scripts/169_v63_honesty_dir.py stage=analyze
exit 0
