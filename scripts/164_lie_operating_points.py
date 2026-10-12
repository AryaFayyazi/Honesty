#!/usr/bin/env python
"""Descriptive operating points for the lie forecasters (no new test), on the unified fresh comparison of scripts/142.
Per model, the threshold is the 90th (and 95th) percentile of that forecaster's scores on fresh honest episodes; we report
the share of lies above it (TPR at 10% / 5% FPR), pooled over models, with scenario-cluster bootstrap CIs and the paired
difference E_lda minus each forecaster. -> results/lie_operating_points.json"""
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

def tpr(d, c, q):
    hits = []
    for _, g in d.dropna(subset=[c]).groupby("model"):
        neg = g.loc[g.y == 0, c]
        if len(neg) == 0 or g.y.sum() == 0:
            continue
        thr = np.quantile(neg, q); hits.append(g.loc[g.y == 1, c] > thr)
    return float(pd.concat(hits).mean()) if hits else np.nan

cl = (D.model + "|" + D.scenario_id).values; u = np.unique(cl); idx = {k: np.where(cl == k)[0] for k in u}; rng = np.random.default_rng(164); B = 2000
draws = [np.concatenate([idx[k] for k in rng.choice(u, len(u))]) for _ in range(B)]
out = {"n": int(len(D)), "lies": int(D.y.sum()), "note": "per-model threshold at the q-quantile of fresh honest scores; descriptive"}
for q, lab in ((0.90, "fpr10"), (0.95, "fpr05")):
    r = {}
    for c in cols:
        v = np.array([tpr(D.iloc[ix], c, q) for ix in draws]); v = v[~np.isnan(v)]
        r[c] = {"tpr": round(tpr(D, c, q), 3), "ci95": [round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3)]}
    for c in cols[1:]:
        v = np.array([tpr(D.iloc[ix], "E_lda", q) - tpr(D.iloc[ix], c, q) for ix in draws]); v = v[~np.isnan(v)]
        r[f"E_minus_{c}"] = {"diff": round(r["E_lda"]["tpr"] - r[c]["tpr"], 3), "ci95": [round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3)],
                             "p_one_sided": float((np.sum(v <= 0) + 1) / (len(v) + 1))}
    out[lab] = r
json.dump(out, open(REPO_ROOT / "results/lie_operating_points.json", "w"), indent=1); print(json.dumps(out, indent=1))
