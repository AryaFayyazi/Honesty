#!/usr/bin/env python
"""v60 zero-shot CoT monitor (GPU, vLLM, main env): the v57 prompt and protocol (scripts/156) on the v60 monitor subset
(scripts/161 monitor_subset). -> outputs/v60/monitor_<model>.parquet"""
import importlib.util
import re

import numpy as np
import pandas as pd

from cape.utils.config import REPO_ROOT


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def main():
    a161 = _mod("a161", "scripts/161_v60_analysis.py"); m156 = _mod("m156", "scripts/156_v57_monitor.py"); A155 = a161.A155
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams
    from vllm.inputs import TokensPrompt
    from cape.models.load import model_path
    from cape.utils.config import resolve_model
    mp = model_path(resolve_model("Qwen/Qwen3.8-27B")); tok = AutoTokenizer.from_pretrained(mp); prompts, meta = [], []
    for A in a161.MODELS:
        if not (REPO_ROOT / f"outputs/xm_feats/{a161.SETS[A]}.npz").exists():
            continue
        C, _ = a161.units_new(A); C = C[a161.monitor_subset(C)].reset_index(drop=True)
        for r, txt in zip(C.itertuples(), A155.texts(C)):
            txt = txt if len(txt) <= 40000 else txt[:4000] + "\n[... omitted ...]\n" + txt[-36000:]
            prompts.append(tok.encode(tok.apply_chat_template([{"role": "user", "content": m156.PROMPT.format(prefix=txt)}], add_generation_prompt=True, tokenize=False, enable_thinking=True), add_special_tokens=False))
            meta.append({"model": A, "set": r.set, "episode_id": r.episode_id, "event_id": int(r.event_id), "cls": r.cls})
    llm = LLM(model=mp, dtype="bfloat16", max_model_len=24000, gpu_memory_utilization=0.9, language_model_only=True, gdn_prefill_backend="triton", max_num_seqs=128)
    outs = llm.generate([TokensPrompt(prompt_token_ids=i[-20000:]) for i in prompts], SamplingParams(max_tokens=3050, temperature=0.0)); texts = [o.outputs[0].text for o in outs]
    redo = [k for k, t in enumerate(texts) if not re.findall(r"PROBABILITY:\s*(\d{1,3})", t.split("</think>")[-1])]
    if redo:
        cont = [prompts[k][-20000:] + tok.encode(texts[k] + ("" if "</think>" in texts[k] else "\n</think>\n\n") + "PROBABILITY: ", add_special_tokens=False) for k in redo]
        for k, o in zip(redo, llm.generate([TokensPrompt(prompt_token_ids=c[-23500:]) for c in cont], SamplingParams(max_tokens=6, temperature=0.0))):
            texts[k] += "\nPROBABILITY: " + o.outputs[0].text
    for k, (m, t) in enumerate(zip(meta, texts)):
        g = re.findall(r"PROBABILITY:\s*(\d{1,3})", t.split("</think>")[-1]) or re.findall(r"PROBABILITY:\s*(\d{1,3})", t)
        m["prob"] = float(min(100, int(g[-1]))) if g else np.nan; m["forced"] = k in set(redo)
    R = pd.DataFrame(meta)
    for A, g in R.groupby("model"):
        g.to_parquet(REPO_ROOT / f"outputs/v60/monitor_{A}.parquet")
    print("wrote", len(R), "forced", float(R.forced.mean()))


if __name__ == "__main__":
    main()
