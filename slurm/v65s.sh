#!/bin/bash
# v65 screen (prereg v65 Addenda 9-10): does an open agent violate the tau2-airline policy? Usage: bash slurm/v65s.sh <actor> [P1|P0_enf]
# 1) vLLM hook validation vs HF on CAPE v54 sites (once per model); 2) none arm, 20 development tasks x 1 trial; labels.
set -uo pipefail
A=$1; C=${2:-P1}
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True TAU2_DATA_DIR=/data/models/cape_ws/datasets/tau2-bench/data LITELLM_LOCAL_MODEL_COST_MAP=True V65_ACTOR=$A V65_COND=$C
export LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
T2=/data/models/cape_ws/envs/tau2/bin/python; O=outputs/v65; N=v65_screen_${A}_$C
if [ "$A" = museglimmer ]; then   # Muse: vLLM 0.30 env (as v54/v57/v60)
  vpy() { ( source /data/models/cape_ws/envs/v030/bin/activate; export PYTHONPATH=$PWD/src VLLM_CACHE_ROOT=/data/models/cape_ws/cache/vllm030 TRITON_CACHE_DIR=/data/models/cape_ws/cache/triton030; python "$@" ); }
else
  vpy() { python "$@"; }
fi
VF=results/prereg_v65/vllm_validation_$A.json; [ "$A" = qwen38 ] && VF=results/prereg_v65/vllm_validation.json
[ -f $VF ] || vpy scripts/174_vllm_steer.py stage=validate actor=$A || echo "v65s $A: validation FAILED (screen still runs; no gated use without a passing validation)"
SD=$TAU2_DATA_DIR/simulations/$N; [ -e $SD ] && mv $SD ${SD}_partial_$(date +%s)
vpy scripts/174_vllm_steer.py stage=serve actor=$A port=8124 log=$O/server_screen_${A}_$C.jsonl save_feats=$O/feats_screen_${A}_$C.npz &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:8124/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v65s $A $C: SERVER DIED"; exit 0; }; sleep 5; done
timeout 10h $T2 scripts/172_v65_tau2_run.py run none dev 1 $N 32 || echo "v65s $A $C run error"
curl -sf http://127.0.0.1:8124/flush; kill $SRV; wait $SRV 2>/dev/null
$T2 scripts/172_v65_tau2_run.py label $N
exit 0
