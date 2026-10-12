#!/bin/bash
# v54 violation-prevention steering chain for one actor (run via slurm/run.sh; prereg docs/preregistration_v54.md + clarifications).
# samples (vLLM) -> teacher-forced residuals + decision states (HF) -> direction, forecaster (CPU) -> smoke -> dev sweep -> selection
# -> (if an alpha passes the rule) fresh confirmation with none / caa / rand / targeted -> confirmation analysis.
set -euo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
A=$1
gpu_py() {   # Muse needs the vLLM 0.30 env for its GPU steps; CPU steps (sklearn/scipy) stay in the main env
  if [ "$A" = museglimmer ]; then
    ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src VLLM_CACHE_ROOT=/data/models/cape_ws/cache/vllm030 TRITON_CACHE_DIR=/data/models/cape_ws/cache/triton030; python "$@" )
  else python "$@"; fi
}
O=outputs/v54
[ -f $O/samples_$A.parquet ] || gpu_py scripts/145_v54_direction.py stage=sample actor=$A
[ -f $O/samples_${A}_genmean.npz ] || gpu_py scripts/145_v54_direction.py stage=extract actor=$A
python scripts/145_v54_direction.py stage=direction actor=$A
python scripts/146_v54_analysis.py stage=forecaster actor=$A
gpu_py scripts/144_v54_steer.py actor=$A max_new=1536 split=dev limit=3 'arms=[none,caa:2]' dir_npz=$O/dir_$A.npz out_name=v54smoke2_$A
python - <<PY
import pandas as pd; R=pd.read_parquet("$O/v54smoke2_$A.parquet"); print(R.groupby("arm").category.value_counts().to_dict())
assert (R.category=="PARSE").mean() <= 0.5, "smoke: too many unparseable turns; check parse_call for this actor"
assert (R.category.isin(["FINAL", "PARSE"])).mean() < 0.8, "smoke: almost no tool calls parsed; check parse_call/TEXT_MARK for this actor"
PY
gpu_py scripts/144_v54_steer.py actor=$A batch=24 max_batch_tokens=24000 max_new=1536 split=dev limit=80 'arms=[none,caa:1,caa:2,caa:4,rand:2]' dir_npz=$O/dir_$A.npz out_name=v54dev_$A
# Addendum 6: if every steered dose fails the parse guard, extend the development grid downward and select again
python scripts/146_v54_analysis.py stage=select actor=$A || true
EXT=$(python -c "import json;j=json.load(open('results/prereg_v54/select_$A.json'));c=j['checks'];print('1' if j['chosen'] is None and c and all(not v['parse_ok'] for v in c.values()) else '')")
if [ -n "$EXT" ]; then
  gpu_py scripts/144_v54_steer.py actor=$A batch=24 max_batch_tokens=24000 max_new=1536 split=dev limit=80 'arms=[caa:0.25,caa:0.5,rand:0.5]' dir_npz=$O/dir_$A.npz out_name=v54dev_$A
fi
bash slurm/v54_conf.sh $A
