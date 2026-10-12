#!/bin/bash
# Phase-2 infrastructure smoke test: LoRA train (8 longest successful episodes) -> merge -> vLLM load + generate.
set -euo pipefail
python scripts/17_ei_sft.py stage=train round=1 smoke=true
python scripts/17_ei_sft.py stage=merge round=1 smoke=true
python - <<'PY'
from vllm import LLM, SamplingParams
llm = LLM(model="/data/models/cape_ws/ckpt/ei_r1_smoke", dtype="bfloat16", max_model_len=4096, language_model_only=True,
          gdn_prefill_backend="triton", gpu_memory_utilization=0.85)
print("VLLM_OK", llm.generate(["Say hello."], SamplingParams(max_tokens=16))[0].outputs[0].text)
PY
rm -rf /data/models/cape_ws/ckpt/ei_r1_smoke
