#!/bin/bash
# v61b (prereg docs/preregistration_v61.md, v61b section): honesty lever on all violations, no gate, Muse. Run via slurm/run.sh.
set -uo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
A=museglimmer
muse_py() { ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src; python "$@" ); }
muse_py scripts/165_v61_e2e.py actor=$A mode=v61b tag=_b n_minus=200 n_plus=0 K=12 stage=run || { echo "v61b run FAILED"; exit 0; }
python scripts/97_rubric_timeline.py revised=outputs/v61/revised_b_$A.parquet || { echo "v61b judge FAILED"; exit 0; }
python scripts/165_v61_e2e.py actor=$A tag=_b stage=analyze_b || echo "v61b analysis FAILED"
exit 0
