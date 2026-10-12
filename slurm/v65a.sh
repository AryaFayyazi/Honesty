#!/bin/bash
# v65a (prereg docs/preregistration_v65.md): tau2-bench airline, Qwen3.8 agent; smoke check, development run (none arm,
# shadow gate scores + features), labels, calibration. Run via slurm/run.sh.
set -uo pipefail
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True TAU2_DATA_DIR=/data/models/cape_ws/datasets/tau2-bench/data LITELLM_LOCAL_MODEL_COST_MAP=True
T2=/data/models/cape_ws/envs/tau2/bin/python; O=outputs/v65; mkdir -p $O
python scripts/171_tau2_steer_server.py actor=qwen38 port=8124 log=$O/server_dev.jsonl save_feats=$O/feats_dev.npz &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:8124/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v65a: SERVER DIED"; exit 0; }; sleep 5; done
echo "server ready $(date)"
$T2 scripts/172_v65_tau2_run.py run none smoke 1 v65_smoke_none || echo "v65a smoke run error"
$T2 scripts/172_v65_tau2_run.py label v65_smoke_none
python - <<'PY' || { echo "v65a: SMOKE FAILED - stopping"; kill $SRV; exit 0; }
import json, sys
d = json.load(open("/data/models/cape_ws/datasets/tau2-bench/data/simulations/v65_smoke_none/results.json"))["simulations"]
calls = sum(len(m.get("tool_calls") or []) for s in d for m in s["messages"] if m.get("role") == "assistant")
leak = sum("<think>" in str(m.get("content") or "") or "<tool_call>" in str(m.get("content") or "") for s in d for m in s["messages"] if m.get("role") == "assistant")
rew = sum(s.get("reward_info") is not None for s in d); n = len(d)
log = [json.loads(l) for l in open("outputs/v65/server_dev.jsonl")]; scored = sum(r["score"] is not None for r in log if r["call_id"])
print(f"smoke: sims={n} tool_calls={calls} markup_leaks={leak} rewards={rew}/{n} scored_calls={scored}/{sum(1 for r in log if r['call_id'])}")
sys.exit(0 if n >= 3 and calls > 0 and leak == 0 and rew == n and scored > 0 else 1)
PY
START=$(date +%s)
$T2 scripts/172_v65_tau2_run.py run none dev 4 v65_dev_none || echo "v65a dev run error"
echo "dev run took $(( $(date +%s) - START )) s"
curl -sf http://127.0.0.1:8124/flush; kill $SRV; wait $SRV 2>/dev/null
$T2 scripts/172_v65_tau2_run.py label v65_dev_none
python scripts/173_v65_analysis.py stage=calibrate || echo "v65a calibration FAILED"
exit 0
