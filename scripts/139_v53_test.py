#!/usr/bin/env python
"""Prereg v53 test: paired cluster bootstrap of B_Muse - B_Qwen and B_Qwen - B_Gemma on fresh v49 regenerations
(complete-case, informed; same data as scripts/125 H1). -> results/prereg_v53/summary.json"""
import importlib.util, json
import numpy as np
from cape.utils.config import REPO_ROOT
s = importlib.util.spec_from_file_location("a", REPO_ROOT / "scripts/125_v49_analysis.py"); A = importlib.util.module_from_spec(s); s.loader.exec_module(A)
def tab(m):
    W = A.regen_table(m); W = W[W.neutral.isin(A.LIES) & W.fta_contract.isin(A.LIES)]
    return W.assign(d=(W.neutral == "MISREPRESENTED").astype(float) - (W.fta_contract == "MISREPRESENTED").astype(float))
T = {m: tab(m) for m in ("museglimmer", "qwen38", "gemma4")}; rng = np.random.default_rng(53); B = 4000
def boot(a, b):
    ca, cb = T[a].scenario_id.values, T[b].scenario_id.values; ua, ub = np.unique(ca), np.unique(cb)
    ia = {c: np.where(ca == c)[0] for c in ua}; ib = {c: np.where(cb == c)[0] for c in ub}; v = []
    for _ in range(B):
        pa = np.concatenate([ia[c] for c in rng.choice(ua, len(ua))]); pb = np.concatenate([ib[c] for c in rng.choice(ub, len(ub))])
        v.append(T[a].d.values[pa].mean() - T[b].d.values[pb].mean())
    v = np.array(v); return {"diff": round(float(T[a].d.mean() - T[b].d.mean()), 4), "ci95": [round(float(np.percentile(v, q)), 4) for q in (2.5, 97.5)], "p_one_sided_gt0": float((np.sum(v <= 0) + 1) / (B + 1))}
out = {"B": {m: round(float(t.d.mean()), 4) for m, t in T.items()}, "Muse_minus_Qwen": boot("museglimmer", "qwen38"), "Qwen_minus_Gemma": boot("qwen38", "gemma4")}
out["verdict"] = "favours internal K over strict text index" if out["Muse_minus_Qwen"]["ci95"][0] > 0 else "inconclusive between K and strict text index"
(REPO_ROOT / "results/prereg_v53/summary.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
