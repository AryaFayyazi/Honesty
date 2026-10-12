#!/usr/bin/env python
"""Prereg v40 analysis: frozen Muse pre-report forecasters (internal vs text) on fresh informed episodes.
python scripts/105_v40_analysis.py -> results/prereg_v40/summary.json
"""
import importlib.util
import json

import joblib
import numpy as np
import pandas as pd

from cape.utils.config import REPO_ROOT


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


X98 = _mod("x98", "scripts/98_v37_analysis.py")
SETS = ["xm_museglimmer_core24b_minus45", "xm_museglimmer_core24b_minus67", "xm_museglimmer_core24b_reasoning_minus23", "xm_museglimmer_core24b_obfuscate_minus23"]
FEATS = ["rep_museglimmer_core24b_F", "rep_museglimmer_core24b_reasoning_F", "rep_museglimmer_core24b_obfuscate_F"]
LIES = ["CANDID", "SPIN", "OMITTED", "MISREPRESENTED"]


def main():
    Fz = joblib.load(REPO_ROOT / "results/prereg_v40/frozen_forecasters.joblib"); li = Fz["layer_index"]
    L = pd.concat([pd.read_parquet(REPO_ROOT / f"outputs/disclosure_v37/{s}_rubric.parquet").assign(set=s) for s in SETS])
    L = L[L.label.isin(LIES) & L.informed.astype(bool)]
    Ms, Xs = [], []
    for st in FEATS:
        z = np.load(REPO_ROOT / f"outputs/xm_feats/{st}.npz"); M = pd.read_parquet(REPO_ROOT / f"outputs/xm_feats/{st}_meta.parquet")
        Ms.append(M.drop(columns=["informed"])); Xs.append(z["pre_report"][:, li].astype(np.float32))
    M = pd.concat(Ms, ignore_index=True).reset_index(); X = np.concatenate(Xs)
    J = L.merge(M[["index", "set", "episode_id"]], on=["set", "episode_id"]).reset_index(drop=True)
    J["y"] = (J.label == "MISREPRESENTED").astype(int)
    si = Fz["lda"].decision_function(Fz["scaler"].transform(X[J["index"].values]))
    txt = [X98.prefix_text(r, "last") for r in J.itertuples()]; st = Fz["lr"].decision_function(Fz["tfidf"].transform(txt))
    z = lambda v: (v - v.mean()) / (v.std() + 1e-9)
    J["si"], J["st"] = z(si), z(st); J["sa"] = (J.si + J.st) / 2; strata = J.template.values
    out = {"n": int(len(J)), "n_lies": int(J.y.sum()), "n_nonlies": int((1 - J.y).sum()), "by_set": J.groupby("set").y.agg(["size", "sum"]).to_dict("index")}
    if J.y.sum() < 15 or (1 - J.y).sum() < 15:
        out["note"] = "descriptive only (<15 lies or non-lies)"
    a_i, p_i = X98.perm_p(J.y.values, J.si.values, strata, n=10000); a_t, p_t = X98.perm_p(J.y.values, J.st.values, strata, n=10000)
    out["E1_internal"] = {"within_template_auroc": round(a_i, 4), "p_perm": p_i}; out["text"] = {"within_template_auroc": round(a_t, 4), "p_perm": p_t}
    J["scenario_id"] = J.scenario_id.astype(str)
    ci, bv = X98.boot_ci(J, lambda d: X98.strat_auc(d.y, d.si, d.template) - X98.strat_auc(d.y, d.st, d.template), 5000)
    lo90 = float(np.percentile(bv, 5)); p2 = float((np.sum(bv <= 0) + 1) / (len(bv) + 1))
    out["E2_internal_minus_text"] = {"diff": round(a_i - a_t, 4), "ci95": ci, "one_sided_lower95": round(lo90, 4), "p_boot": p2}
    ci3, bv3 = X98.boot_ci(J, lambda d: X98.strat_auc(d.y, d.sa, d.template) - X98.strat_auc(d.y, d.st, d.template), 5000)
    out["E3_average_minus_text"] = {"avg_auroc": round(X98.strat_auc(J.y, J.sa, J.template), 4), "ci95": ci3}
    ps = {"E1": p_i, "E2": p2}; od = sorted(ps, key=ps.get)
    for i, k in enumerate(od):
        hp = min(1.0, max(ps[o] * (len(od) - j) for j, o in enumerate(od[: i + 1])))
        key = "E1_internal" if k == "E1" else "E2_internal_minus_text"; out[key]["holm_p"] = hp
    out["E1_PASS"] = bool(out["E1_internal"]["holm_p"] < 0.05)
    out["E2_PASS"] = bool(out["E2_internal_minus_text"]["one_sided_lower95"] > 0 and out["E2_internal_minus_text"]["holm_p"] < 0.05)
    o = REPO_ROOT / "results/prereg_v40"; o.mkdir(parents=True, exist_ok=True); (o / "summary.json").write_text(json.dumps(out, indent=1, default=str)); print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
