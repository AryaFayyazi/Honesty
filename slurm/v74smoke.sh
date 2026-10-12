#!/bin/bash
# v74 plumbing smoke test (excluded from all analyses): gpt-oss server, 2 benign development episodes + 1 attacked episode;
# checks only errors, tool-call parsing, server logging and that the injection text reaches the agent. Usage: bash slurm/v74smoke.sh
set -uo pipefail
A=gptoss20b; PORT=$((8200 + ${SLURM_JOB_ID:-0} % 700)); export V65_PORT=$PORT V65_ACTOR=$A V74_OUT=$PWD/outputs/v74_smoke
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True LD_LIBRARY_PATH=/data/models/cider_ws/envs/cider/lib:${LD_LIBRARY_PATH:-}
AD=/data/models/cape_ws/envs/agentdojo/bin/python; O=outputs/v74_smoke; mkdir -p $O
python scripts/174_vllm_steer.py stage=serve actor=$A port=$PORT log=$O/server_smoke.jsonl shadow=true &
SRV=$!
for i in $(seq 1 360); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; kill -0 $SRV 2>/dev/null || { echo "v74smoke: SERVER DIED"; exit 0; }; sleep 5; done
$AD -I - <<'PY'
import importlib.util, json, os
s = importlib.util.spec_from_file_location("m", "scripts/191_v74_agentdojo.py"); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
for arm, sn, ut, it in [("none", "banking", "user_task_0", None), ("gate", "slack", "user_task_1", None), ("none", "banking", "user_task_3", "injection_task_1")]:
    r = m.episode(arm, sn, ut, it, 0)
    inj = any("<INFORMATION>" in str(x.get("content")) for x in r["transcript"] if x.get("role") == "tool")
    print("smoke", arm, sn, ut, it, "error", r["error"], "| calls", [c["tool"] for c in r["calls"]], "| injection text seen", inj if it else "-", flush=True)
PY
curl -sf http://127.0.0.1:$PORT/flush; kill $SRV; wait $SRV 2>/dev/null
python -c "
import json; L=[json.loads(x) for x in open('outputs/v74_smoke/server_smoke.jsonl')]
print('smoke server rows', len(L), 'with rid', sum(r.get('rid') is not None for r in L), 'scored', sum(r.get('score') is not None for r in L), 'fired', sum(bool(r.get('fired')) for r in L))"
exit 0
