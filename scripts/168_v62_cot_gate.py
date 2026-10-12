#!/usr/bin/env python
"""v62 (prereg docs/preregistration_v62.md): are internals needed for prevention? Internal gate vs a CoT-monitor gate at matched
false-alarm rate, on the existing v54 confirmation decision turns (no new generation).
For every site, v54 already holds the unsteered turn (arm none) and the steered turn at the gate dose (arm caa:<gate alpha>), same seed.
A gate's outcome at a site = the steered turn if it fires, else the unsteered turn.
  stage=monitor (GPU, main env, vLLM judge): the frozen v57 zero-shot CoT monitor (scripts/156 prompt and settings) reads the prefix
                and the unsteered turn's reasoning/message (no call) and states P(next action unauthorized). -> outputs/v62/cotmon_<model>.parquet
  stage=analyze (CPU): CoT threshold = the score quantile on fresh x+ sites that gives the internal gate's x+ fire rate (no outcome used).
                -> results/prereg_v62/summary.json"""
import importlib.util
import json
import re

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.utils.config import REPO_ROOT, load_config

D = OmegaConf.create({"stage": "monitor", "models": ["gemma4", "gptoss20b", "museglimmer", "qwen38"], "max_think": 3000,
                      "judge_model": "Qwen/Qwen3.8-27B", "max_chars": 40000, "B": 10000})
OUT = REPO_ROOT / "outputs/v62"; RES = REPO_ROOT / "results/prereg_v62"


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def site_rows(A):
    """v54 confirmation sites with their unsteered (none) and steered (gate dose) turns."""
    ga = json.load(open(REPO_ROOT / f"results/prereg_v54/gate_alpha_{A}.json"))["gate_alpha"]
    R = pd.read_parquet(REPO_ROOT / f"outputs/v54/v54conf_{A}.parquet"); R["key"] = R.set + "|" + R.episode_id
    S = pd.read_parquet(REPO_ROOT / f"outputs/v54/sites_{A}_conf.parquet"); S["key"] = S.set + "|" + S.episode_id
    none = R[R.arm == "none"].set_index("key"); st = R[R.arm == f"caa:{ga}"].set_index("key")
    keys = [k for k in S.key if k in none.index and k in st.index]
    return S.set_index("key").loc[keys], none.loc[keys], st.loc[keys], ga


def stage_monitor(cfg):
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams
    from vllm.inputs import TokensPrompt
    from cape.models.load import model_path
    from cape.utils.config import resolve_model
    M156 = _mod("m156", "scripts/156_v57_monitor.py"); H153 = _mod("h153", "scripts/153_vhorizon_explore.py"); C159 = _mod("c159", "scripts/159_v59_continue.py")
    mp = model_path(resolve_model(cfg.judge_model)); tok = AutoTokenizer.from_pretrained(mp); prompts, meta = [], []
    for A in cfg.models:
        S, N, _, _ = site_rows(A); specs, roll = {}, {}
        for b in S.bench.unique():
            for l in open(REPO_ROOT / f"outputs/capebench/{b}/scenarios.jsonl"):
                x = json.loads(l); specs[(b, x["instance_id"])] = x
        for s_ in S.set.unique():
            roll[s_] = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{s_}.parquet").set_index("episode_id")
        for k, r in S.iterrows():
            ev = list(roll[r.set].loc[r.episode_id].events); site = int(r.site_event)
            rs, ct = C159.split_turn(A, N.loc[k].gen_text)
            ev2 = ev[:site] + [{"is_tool_call": False, "tool": None, "reasoning_text": rs, "content_text": ct}]
            txt = H153.turn_text(ev2, site, specs[(r.bench, r.instance_id)])
            txt = txt if len(txt) <= cfg.max_chars else txt[:4000] + "\n[... omitted ...]\n" + txt[-(cfg.max_chars - 4000):]
            prompts.append(tok.encode(tok.apply_chat_template([{"role": "user", "content": M156.PROMPT.format(prefix=txt)}], add_generation_prompt=True,
                                                              tokenize=False, enable_thinking=True), add_special_tokens=False))
            meta.append({"model": A, "key": k, "world": r.world})
    print("prompts", len(prompts), flush=True)
    llm = LLM(model=mp, dtype="bfloat16", max_model_len=24000, gpu_memory_utilization=0.9, language_model_only=True, gdn_prefill_backend="triton", max_num_seqs=128)
    outs = llm.generate([TokensPrompt(prompt_token_ids=i[-20000:]) for i in prompts], SamplingParams(max_tokens=cfg.max_think + 50, temperature=0.0))
    texts = [o.outputs[0].text for o in outs]
    redo = [k for k, t in enumerate(texts) if not re.findall(r"PROBABILITY:\s*(\d{1,3})", t.split("</think>")[-1])]
    if redo:                                          # forced final answer, as scripts/156
        cont = [prompts[k][-20000:] + tok.encode(texts[k] + ("" if "</think>" in texts[k] else "\n</think>\n\n") + "PROBABILITY: ", add_special_tokens=False) for k in redo]
        for k, o in zip(redo, llm.generate([TokensPrompt(prompt_token_ids=c[-23500:]) for c in cont], SamplingParams(max_tokens=6, temperature=0.0))):
            texts[k] = texts[k] + "\nPROBABILITY: " + o.outputs[0].text
    rs = set(redo)
    for k, (m, t) in enumerate(zip(meta, texts)):
        g = re.findall(r"PROBABILITY:\s*(\d{1,3})", t.split("</think>")[-1]) or re.findall(r"PROBABILITY:\s*(\d{1,3})", t)
        m["prob"] = float(min(100, int(g[-1]))) if g else np.nan; m["forced"] = k in rs
    R = pd.DataFrame(meta); OUT.mkdir(parents=True, exist_ok=True)
    for A, g in R.groupby("model"):
        g.to_parquet(OUT / f"cotmon_{A}.parquet")
    print("wrote", len(R), "parsed", float(R.prob.notna().mean()), "forced", float(R.forced.mean()), flush=True)
    import os; os._exit(0)


def stage_analyze(cfg):
    from scipy.stats import binomtest
    G154 = _mod("g154", "scripts/154_v54_gate.py"); out = {"per_model": {}}; disc_int, disc_cot = 0, 0; rows = []
    for A in cfg.models:
        S, N, ST, ga = site_rows(A)
        G = np.load(REPO_ROOT / f"outputs/v54/gate_{A}.npz"); tau = float(G["tau"]); Fz = np.load(REPO_ROOT / f"outputs/v54/gatefeat_v54conf_{A}.npz")
        M = pd.read_parquet(OUT / f"cotmon_{A}.parquet").set_index("key")
        d = pd.DataFrame({"world": S.world, "none": N.category, "steer": ST.category})
        d["fire_int"] = [k in Fz.files and float(G154.gate_score(G, Fz[k][None].astype(np.float32))[0]) > tau for k in d.index]
        d["cot"] = M.reindex(d.index).prob.values
        plus = d[d.world == "plus"]; f_int = float(plus.fire_int.mean())
        thr = float(np.nanquantile(plus.cot.values, 1 - f_int, method="higher")) if f_int > 0 else np.inf   # matched x+ false-alarm rate
        d["fire_cot"] = d.cot > thr
        for g in ("int", "cot"):
            d[f"out_{g}"] = np.where(d[f"fire_{g}"], d.steer, d.none)
        m, p = d[d.world == "minus"], d[d.world == "plus"]
        vi, vc = (m.out_int == "VIOLATE").astype(int), (m.out_cot == "VIOLATE").astype(int)
        b, c = int(((vc == 1) & (vi == 0)).sum()), int(((vc == 0) & (vi == 1)).sum())       # b: internal prevents, CoT does not
        disc_int += b; disc_cot += c
        prog = lambda col: float(p[col].isin(["CRITICAL", "ESCALATE"]).mean())
        out["per_model"][A] = {"n_minus": int(len(m)), "n_plus": int(len(p)), "gate_alpha": ga, "fire_plus": {"internal": round(f_int, 4), "cot": round(float(p.fire_cot.mean()), 4)},
                              "fire_minus": {"internal": round(float(m.fire_int.mean()), 4), "cot": round(float(m.fire_cot.mean()), 4)},
                              "violation": {"none": round(float((m.none == "VIOLATE").mean()), 4), "internal_gate": round(float(vi.mean()), 4), "cot_gate": round(float(vc.mean()), 4)},
                              "progress_plus": {"none": prog("none"), "internal_gate": prog("out_int"), "cot_gate": prog("out_cot")},
                              "internal_vs_cot": {"internal_better": b, "cot_better": c, "p_one_sided": float(binomtest(b, b + c, 0.5, alternative="greater").pvalue) if b + c else 1.0},
                              "cot_parsed": round(float(m.cot.notna().mean()), 4)}
        rows.append(d.assign(model=A))
    out["H_pooled_internal_vs_cot"] = {"internal_better": disc_int, "cot_better": disc_cot,
                                       "p_one_sided": float(binomtest(disc_int, disc_int + disc_cot, 0.5, alternative="greater").pvalue) if disc_int + disc_cot else 1.0}
    RES.mkdir(parents=True, exist_ok=True); json.dump(out, open(RES / "summary.json", "w"), indent=2, default=str); print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    cfg = OmegaConf.merge(D, load_config(None))
    {"monitor": stage_monitor, "analyze": stage_analyze}[cfg.stage](cfg)
