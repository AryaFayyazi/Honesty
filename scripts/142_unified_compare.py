#!/usr/bin/env python
"""Descriptive unified comparison (no new test): every forecaster frozen BEFORE the fresh data existed, scored on the same fresh v51
sets of the models where the v52 ensemble exists (Qwen, Gemma, gpt-oss; Muse has no ensemble because its fresh sets were examined).
Forecasters: E_lda (v52 internal ensemble, ours), I (v51 single-recipe internal), T_sup (supervised text), M_cot / M_act (zero-shot LLM
monitors). Pooled within-(model, template) AUROC with per-model z-scores; scenario-cluster bootstrap CIs of E_lda minus each.
-> results/unified_compare.json"""
import importlib.util, json
import numpy as np, pandas as pd
from cape.utils.config import REPO_ROOT
def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
C = _mod("c134", "scripts/134_v51_confirm.py"); V = _mod("v141", "scripts/141_v52_confirm.py")
parts = []
for m in ("qwen38", "gemma4", "gptoss20b"):
    a = C.scores(m); b = V.fresh(m)[["set", "episode_id", "I"]].rename(columns={"I": "E_lda"})
    parts.append(a.merge(b, on=["set", "episode_id"], how="inner"))
D = pd.concat(parts, ignore_index=True); cols = ["E_lda", "I", "T_sup", "M_cot", "M_act"]
for c in cols:
    D[c] = D.groupby("model")[c].transform(lambda v: (v - v.mean()) / (v.std() + 1e-9))
out = {"n": int(len(D)), "lies": int(D.y.sum()), "pooled": {c: round(C.auc(D, c), 4) for c in cols},
       "per_model": {m: {c: round(C.auc(g, c), 4) for c in cols} for m, g in D.groupby("model")},
       "E_minus": {c: C.boot_diff(D, "E_lda", c) for c in cols if c != "E_lda"}}
ob = D[D.variant == "obfuscate"]
out["obfuscate"] = {"n": int(len(ob)), "lies": int(ob.y.sum()), "pooled": {c: round(C.auc(ob, c), 4) for c in cols}, "E_minus_Mcot": C.boot_diff(ob, "E_lda", "M_cot")}
json.dump(out, open(REPO_ROOT / "results/unified_compare.json", "w"), indent=1); print(json.dumps(out, indent=1))
