#!/bin/bash
# v60: new x- rollouts (core24b seeds 14-17) for four models -> decision-time features -> zero-shot monitor -> analysis.
# Run via slurm/run.sh. Muse rollouts/extraction in the v030 env.
set -uo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
muse_py() { ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src VLLM_CACHE_ROOT=/data/models/cape_ws/cache/vllm030 TRITON_CACHE_DIR=/data/models/cape_ws/cache/triton030; python "$@" ); }
R="scripts/20_server_rollouts.py split=core24b 'cf_values=[unsafe]' seeds=[14,15,16,17]"
[ -f outputs/rollouts/xm_gemma4_core24b_minus14151617.parquet ] || eval python $R actor=gemma4 port=8191 out_name=xm_gemma4_core24b_minus14151617
[ -f outputs/rollouts/xm_gptoss20b_core24b_minus14151617.parquet ] || eval python $R actor=gptoss20b port=8192 out_name=xm_gptoss20b_core24b_minus14151617
[ -f outputs/rollouts/core24b_minus14151617.parquet ] || eval python $R actor=qwen38 port=8193 out_name=core24b_minus14151617
[ -f outputs/rollouts/xm_museglimmer_core24b_minus14151617.parquet ] || eval muse_py $R actor=museglimmer port=8194 out_name=xm_museglimmer_core24b_minus14151617
python - <<'PY'
# extraction episodes: all informed violators + up to 1000 informed non-violators per model (sha256 order)
import hashlib, pandas as pd
rows=[]
for A,f in [("gemma4","xm_gemma4_core24b_minus14151617"),("gptoss20b","xm_gptoss20b_core24b_minus14151617"),("qwen38","core24b_minus14151617"),("museglimmer","xm_museglimmer_core24b_minus14151617")]:
    try: R=pd.read_parquet(f"outputs/rollouts/{f}.parquet")
    except Exception as e: print("missing",f,e); continue
    rv=pd.to_numeric(R.reveal_event,errors="coerce"); fu=pd.to_numeric(R.first_unsafe_event,errors="coerce")
    v=R[(rv>=0)&(fu>rv)]; n=R[(rv>=0)&fu.isna()].copy(); n["h"]=[hashlib.sha256(f"{A}|{e}".encode()).hexdigest() for e in n.episode_id]
    n=n.sort_values("h").head(1000); rows+= [{"set":f,"episode_id":e} for e in list(v.episode_id)+list(n.episode_id)]; print(A,len(v),"violators",len(n),"non")
pd.DataFrame(rows).to_parquet("outputs/v60/episodes.parquet")
PY
X="scripts/56_xm_replay_extract.py episodes=outputs/v60/episodes.parquet bench=core24b"
[ -f outputs/xm_feats/xm_gemma4_core24b_minus14151617.npz ] || python $X actor=gemma4 "sets=[xm_gemma4_core24b_minus14151617]"
[ -f outputs/xm_feats/xm_gptoss20b_core24b_minus14151617.npz ] || python $X actor=gptoss20b max_tokens=10000 "sets=[xm_gptoss20b_core24b_minus14151617]"
[ -f outputs/xm_feats/xm_qwen38_core24b_minus14151617.npz ] || python $X actor=qwen38 out_prefix=xm_qwen38_ "sets=[core24b_minus14151617]"
[ -f outputs/xm_feats/xm_museglimmer_core24b_minus14151617.npz ] || muse_py $X actor=museglimmer "sets=[xm_museglimmer_core24b_minus14151617]"
python scripts/162_v60_monitor.py
python scripts/161_v60_analysis.py > results/prereg_v60_analysis.log 2>&1 || echo "v60 analysis failed"
exit 0
