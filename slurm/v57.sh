#!/bin/bash
# v57 fresh decision-time features (scripts/56 restricted to the v55 confirmation episodes), then the zero-shot monitor.
# Run via slurm/run.sh. Muse extraction uses the vLLM-0.30 env.
set -euo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
X="python scripts/56_xm_replay_extract.py episodes=outputs/v57/conf_episodes.parquet"
muse_py() { ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src; python "$@" ); }
for A in gemma4 gptoss20b; do
  MT=""; [ "$A" = gptoss20b ] && MT="max_tokens=10000"     # gpt-oss: HF attention memory is quadratic (64 heads x n^2); episodes > 10k tokens (dev max 9k) OOM (skipped; counted in the analysis)
  [ -f outputs/xm_feats/xm_${A}_core24b_minus6789.npz ] || $X actor=$A $MT bench=core24b "sets=[xm_${A}_core24b_minus6789]"
  [ -f outputs/xm_feats/xm_${A}_core24b_minus10111213.npz ] || $X actor=$A $MT bench=core24b "sets=[xm_${A}_core24b_minus10111213]"
  [ -f outputs/xm_feats/xm_${A}_core24b_reasoning_minus6789.npz ] || $X actor=$A $MT bench=core24b_reasoning "sets=[xm_${A}_core24b_reasoning_minus6789]"
  [ -f outputs/xm_feats/xm_${A}_core24b_obfuscate_minus10111213.npz ] || $X actor=$A $MT bench=core24b_obfuscate "sets=[xm_${A}_core24b_obfuscate_minus10111213]"
done
[ -f outputs/xm_feats/xm_qwen38_core24b_minus2345.npz ] || $X actor=qwen38 bench=core24b out_prefix=xm_qwen38_ "sets=[core24b_minus2345]"
[ -f outputs/xm_feats/xm_qwen38_core24b_reasoning_minus0123.npz ] || $X actor=qwen38 bench=core24b_reasoning out_prefix=xm_qwen38_ "sets=[core24b_reasoning_minus0123]"
[ -f outputs/xm_feats/xm_qwen38_core24b_obfuscate_minus0123.npz ] || $X actor=qwen38 bench=core24b_obfuscate out_prefix=xm_qwen38_ "sets=[core24b_obfuscate_minus0123]"
for s_ in 89 1011 1213 1415; do
  [ -f outputs/xm_feats/xm_museglimmer_core24b_minus$s_.npz ] || muse_py scripts/56_xm_replay_extract.py episodes=outputs/v57/conf_episodes.parquet actor=museglimmer bench=core24b "sets=[xm_museglimmer_core24b_minus$s_]"
done
python scripts/156_v57_monitor.py
