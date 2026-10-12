#!/usr/bin/env python
"""v71 (prereg docs/preregistration_v71.md): leave-one-family-out generalization of the pre-action readout (CPU).
-> results/prereg_v71/summary.json, outputs/v71/scores.parquet"""
import hashlib
import importlib.util
import json
import re

import numpy as np
import pandas as pd

from cape.utils.config import REPO_ROOT

OUT = REPO_ROOT / "outputs/v71"; RES = REPO_ROOT / "results/prereg_v71"
MODELS = ["qwen38", "gemma4", "gptoss20b", "museglimmer"]; MAX_NEG = 6000   # = scripts/154 max_neg


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def fam(t):
    return re.match(r"^([a-z]+)_", str(t)).group(1)


def dev_data(G154, A):
    """the v54 gate training set (scripts/154 stage_fit), with the template kept for family selection."""
    Xs, rows = [], []
    for st, w in G154.dev_sets(A):
        Mt = pd.read_parquet(REPO_ROOT / f"outputs/xm_feats/{st}_meta.parquet"); Z = np.load(REPO_ROOT / f"outputs/xm_feats/{st}.npz")["pre"]
        if w == "minus":
            R = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{G154.roll_name(A, st)}.parquet", columns=["episode_id", "reveal_event", "first_unsafe_event"]).set_index("episode_id")
            Mt = Mt.join(R, on="episode_id"); rv = pd.to_numeric(Mt.reveal_event, errors="coerce"); fu = pd.to_numeric(Mt.first_unsafe_event, errors="coerce")
            pos = (fu > rv) & (Mt.event_id == fu); neg = (rv >= 0) & fu.isna() & (Mt.event_id > rv)
            Mt["cls"] = np.where(pos, "viol", np.where(neg, "x-other", ""))
        else:
            Mt["cls"] = np.where(Mt.critical.astype(bool), "x+crit", "")
        k = (Mt.cls != "").values; Xs.append(Z[k]); rows.append(Mt[k][["scenario_id", "template", "cls"]])
    M = pd.concat(rows, ignore_index=True); X = np.concatenate(Xs).astype(np.float32); M["family"] = M.template.map(fam)
    return M, X


def fit_lofo(M150, M, X, holdout):
    """same recipe as scripts/154 (negatives capped with seed 54; two scenario folds), without the held-out family."""
    keep = (M.family != holdout).values; M = M[keep].reset_index(drop=True); X = X[keep]
    rng = np.random.default_rng(54); drop = []
    for c in ("x-other", "x+crit"):
        idx = M.index[M.cls == c]
        if len(idx) > MAX_NEG:
            drop += list(rng.choice(idx, len(idx) - MAX_NEG, replace=False))
    keep2 = ~M.index.isin(drop); M = M[keep2].reset_index(drop=True); X = X[keep2]; y = (M.cls == "viol").astype(int).values
    fold = M.scenario_id.map(lambda s: int(hashlib.md5(s.encode()).hexdigest(), 16) % 2).values
    return [M150.fit_internal(X[fold != k], y[fold != k]) for k in (0, 1)]


def score(M150, models, X):
    return np.mean([M150.score_internal(m, X) for m in models], 0)


def strat_auc(d, col, neg):
    from sklearn.metrics import roc_auc_score
    d = d[(d.cls == "VIOL") | d.cls.isin(neg)]; num = den = 0.0
    for _, g in d.groupby(["model", "template"]):
        if g.cls.eq("VIOL").any() and (~g.cls.eq("VIOL")).any():
            num += roc_auc_score(g.cls.eq("VIOL").astype(int), g[col]) * len(g); den += len(g)
    return num / den if den else float("nan")


def main():
    G154 = _mod("g154", "scripts/154_v54_gate.py"); M150 = _mod("m150", "scripts/150_v55_analysis.py"); A155 = _mod("a155", "scripts/155_v57_analysis.py")
    parts = []
    for A in MODELS:
        Md, Xd = dev_data(G154, A); C, Xc = A155.units(A, "conf"); C = C[C.cls.isin(["VIOL", "XOTHER", "XPLUS"])].copy(); Xc = Xc[C.index.values]; C = C.reset_index(drop=True)
        C["family"] = C.template.map(fam); Gz = np.load(REPO_ROOT / f"outputs/v54/gate_{A}.npz"); G = {k: Gz[k] for k in Gz.files}
        C["full"] = G154.gate_score(G, Xc); C["lofo"] = np.nan
        for f in sorted(C.family.unique()):
            m = (C.family == f).values
            if not (Md.family == f).any() and not m.any():
                continue
            models = fit_lofo(M150, Md, Xd, f); C.loc[m, "lofo"] = score(M150, models, Xc[m]); print(A, f, int(m.sum()), flush=True)
        parts.append(C[["model", "scenario_id", "template", "family", "cls", "full", "lofo"]])
    D = pd.concat(parts, ignore_index=True); OUT.mkdir(parents=True, exist_ok=True); D.to_parquet(OUT / "scores.parquet")
    out = {"n": int(len(D)), "L1_lofo_viol_vs_xplus": strat_auc(D, "lofo", ["XPLUS"]), "full_viol_vs_xplus": strat_auc(D, "full", ["XPLUS"]),
           "lofo_all": strat_auc(D, "lofo", ["XOTHER", "XPLUS"]), "full_all": strat_auc(D, "full", ["XOTHER", "XPLUS"]),
           "lofo_viol_vs_xother": strat_auc(D, "lofo", ["XOTHER"]), "full_viol_vs_xother": strat_auc(D, "full", ["XOTHER"])}
    cl = (D.model + "|" + D.scenario_id).values; u = np.unique(cl); idx = {c: np.where(cl == c)[0] for c in u}; rng = np.random.default_rng(71); b1, b2 = [], []
    for _ in range(4000):
        d = D.iloc[np.concatenate([idx[c] for c in rng.choice(u, len(u))])]
        b1.append(strat_auc(d, "lofo", ["XPLUS"])); b2.append(strat_auc(d, "lofo", ["XOTHER", "XPLUS"]) - strat_auc(d, "full", ["XOTHER", "XPLUS"]))
    b1, b2 = np.array(b1), np.array(b2)
    p1 = float((np.sum(b1 <= 0.5) + 1) / (len(b1) + 1)); lo2 = float(np.percentile(b2, 5)); p2 = float((np.sum(b2 <= -0.05) + 1) / (len(b2) + 1))
    srt = sorted([("L1", p1), ("L2", p2)], key=lambda t: t[1]); holm = {srt[0][0]: min(1, 2 * srt[0][1])}; holm[srt[1][0]] = max(holm[srt[0][0]], srt[1][1])
    out.update({"L1_ci95": [float(np.percentile(b1, 2.5)), float(np.percentile(b1, 97.5))], "L1_p": p1, "L2_diff": out["lofo_all"] - out["full_all"], "L2_lower95": lo2, "L2_p": p2,
                "holm": holm, "L1_pass": holm["L1"] < 0.05, "L2_pass": holm["L2"] < 0.05,
                "per_family": {f: {"lofo_vs_xplus": strat_auc(g, "lofo", ["XPLUS"]), "full_vs_xplus": strat_auc(g, "full", ["XPLUS"]), "lofo_all": strat_auc(g, "lofo", ["XOTHER", "XPLUS"]),
                                   "full_all": strat_auc(g, "full", ["XOTHER", "XPLUS"]), "n_viol": int((g.cls == "VIOL").sum())} for f, g in D.groupby("family")},
                "per_model": {m: {"lofo_all": strat_auc(g, "lofo", ["XOTHER", "XPLUS"]), "full_all": strat_auc(g, "full", ["XOTHER", "XPLUS"])} for m, g in D.groupby("model")}})
    RES.mkdir(parents=True, exist_ok=True); json.dump(out, open(RES / "summary.json", "w"), indent=2, default=float); print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
