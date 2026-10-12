#!/usr/bin/env python
"""Addendum 1 (exploratory): label-error-corrected F1 (laundering -> lie) using the S0 audit (CANDID/MISREP/OMITTED) and the
SPIN addendum, by retro status. Corrected rate(group) = sum_label P(label | group) * P(gold = MISREP | label, group).
Bootstrap: episodes within group x audit items within (label, group). -> results/prereg_v50/addendum_summary.json"""
import importlib.util, json
import numpy as np, pandas as pd
from omegaconf import OmegaConf
from cape.utils.config import REPO_ROOT, load_config
s = importlib.util.spec_from_file_location("a98", REPO_ROOT / "scripts/98_v37_analysis.py"); a98 = importlib.util.module_from_spec(s); s.loader.exec_module(a98)
F = a98.episodes(OmegaConf.merge(a98.D, load_config(None))); C = F[(F.informed == 1) & F.C][["set", "episode_id", "retro", "label"]]
D = REPO_ROOT / "results/prereg_v50"
def load(key, ann, stratum=None):
    K = pd.read_csv(D / key); A = pd.DataFrame([json.loads(l) for l in open(D / ann)]); X = K.merge(A, on="item_id")
    if stratum:
        X = X[X.stratum == stratum]
    X["goldM"] = (X.q2 == "yes"); return X
a0 = load("audit_key.csv", "audit_annotations.jsonl", "S0").drop(columns=["retro"], errors="ignore").merge(C[["set", "episode_id", "retro"]], on=["set", "episode_id"], how="left")
a1 = load("addendum_key.csv", "addendum_annotations.jsonl")
AU = pd.concat([a0[["rubric_label", "retro", "goldM"]], a1[["rubric_label", "retro", "goldM"]]], ignore_index=True)
tab = AU.groupby(["rubric_label", "retro"]).goldM.agg(["sum", "size"]).reset_index()
rng = np.random.default_rng(51); B = 4000
def rate(Cg, AUg, boot):
    labs = Cg.label.values
    if boot:
        labs = labs[rng.integers(0, len(labs), len(labs))]
    p = {}
    for lab, g in AUg.groupby("rubric_label"):
        y = g.goldM.values.astype(float); p[lab] = (y[rng.integers(0, len(y), len(y))] if boot else y).mean()
    return float(np.mean([p.get(l, 1.0 if l == "MISREPRESENTED" else 0.0) for l in labs]))
res = {}
for r in (1, 0):
    Cg, AUg = C[C.retro == r], AU[AU.retro == r]
    res[r] = {"raw": float((Cg.label == "MISREPRESENTED").mean()), "corrected": rate(Cg, AUg, False), "boot": [rate(Cg, AUg, True) for _ in range(B)], "n": int(len(Cg))}
rr = np.array(res[1]["boot"]) / np.array(res[0]["boot"]); df = np.array(res[1]["boot"]) - np.array(res[0]["boot"])
out = {"audit_table_P_goldMisrep": tab.to_dict("records"),
       "retro": {"n": res[1]["n"], "raw": round(res[1]["raw"], 3), "corrected": round(res[1]["corrected"], 3), "ci95": [round(float(np.percentile(res[1]["boot"], q)), 3) for q in (2.5, 97.5)]},
       "noretro": {"n": res[0]["n"], "raw": round(res[0]["raw"], 3), "corrected": round(res[0]["corrected"], 3), "ci95": [round(float(np.percentile(res[0]["boot"], q)), 3) for q in (2.5, 97.5)]},
       "risk_ratio_corrected": round(res[1]["corrected"] / res[0]["corrected"], 2), "risk_ratio_ci95": [round(float(np.percentile(rr, q)), 2) for q in (2.5, 97.5)],
       "diff_corrected_ci95": [round(float(np.percentile(df, q)), 3) for q in (2.5, 97.5)],
       "raw_risk_ratio": round(res[1]["raw"] / res[0]["raw"], 2), "note": "exploratory (Addendum 1, designed after v50)"}
json.dump(out, open(D / "addendum_summary.json", "w"), indent=1); print(json.dumps(out, indent=1))
