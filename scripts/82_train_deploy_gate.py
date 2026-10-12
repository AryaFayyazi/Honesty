#!/usr/bin/env python
"""Train and export a deployable reader-mode gate (for the closed-loop study, prereg v32).

python scripts/82_train_deploy_gate.py
Training data: Qwen3.8-reader `mean8` layer-2 features of v2fresh trajectories of qwen38 (own) + gemma4 + gptoss20b +
museglimmer (seed-balanced; scripts/56 reader mode), 75% of scenarios. Predicates (cross-fitted-Platt shrinkage LDA,
identical to scripts/65): crit, auth (informed critical: harm vs safe), unv (critical: uninformed vs informed),
mono (harm vs all). Episode-level split-conformal thresholds for ECG and ECG-m at alpha in {0.05, 0.10} from the
held-out 25% of scenarios (compliant actions only). Exports plain arrays so the gate is a few dot products at runtime.
Output: outputs/deploy_gate/gate_v32.npz + gate_v32.json
"""
import importlib.util
import json

import numpy as np
import pandas as pd

from cape.utils.config import REPO_ROOT

spec = importlib.util.spec_from_file_location("ecg", REPO_ROOT / "scripts/65_epistemic_gate.py")
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)
ACTORS = ["qwen38", "rdqwen-gemma4", "rdqwen-gptoss20b", "rdqwen-museglimmer"]


def fit_export(X, y, g):
    """Same estimator as G.lda, but returns explicit parameters: z = platt_a * (w . (x - mu)/sd + b) + platt_c."""
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    u = np.array(sorted(set(g))); f = {s: i % 3 for i, s in enumerate(np.random.default_rng(7).permutation(u))}
    fold = np.array([f[s] for s in g]); oof = np.full(len(y), np.nan)
    for k in range(3):
        tr, te = fold != k, fold == k
        if len(set(y[tr])) == 2 and te.sum():
            oof[te] = G._lda_raw(X[tr], y[tr])(X[te])
    ok = ~np.isnan(oof)
    pl = LogisticRegression(C=1e4, max_iter=1000).fit(oof[ok, None], y[ok])
    sc = StandardScaler().fit(X); m = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto").fit(sc.transform(X), y)
    return {"mu": sc.mean_.astype(np.float32), "sd": sc.scale_.astype(np.float32), "w": m.coef_[0].astype(np.float32),
            "b": float(m.intercept_[0]), "pa": float(pl.coef_[0, 0]), "pc": float(pl.intercept_[0])}


def apply(p, X):
    return p["pa"] * (((X - p["mu"]) / p["sd"]) @ p["w"] + p["b"]) + p["pc"]


def log_or(a, b):
    x = np.minimum(G.ls(-a) + G.ls(-b), -1e-300)
    return np.where(x > -np.log(2), np.log(-np.expm1(x)), np.log1p(-np.exp(x)))


def main():
    Ms, Xs = [], []
    for a in ACTORS:
        G.SEEDS = [0, 1]
        M, X = G.load(a, "v2fresh", "mean8", 2); M["scenario_id"] = a + "|" + M.scenario_id; Ms.append(M); Xs.append(X)
    M = pd.concat(Ms, ignore_index=True); X = np.concatenate(Xs)
    base = M.scenario_id.str.split("|").str[1].values           # hold out by underlying scenario across actors
    u = np.array(sorted(set(base))); cal = set(np.random.default_rng(10).permutation(u)[: len(u) // 4])
    ic = np.isin(base, list(cal)); tr = ~ic; g = M.scenario_id.values
    P = {}
    P["crit"] = fit_export(X[tr], M.crit.values[tr], g[tr])
    ci = tr & (M.crit.values == 1) & (M.informed.values == 1)
    P["auth"] = fit_export(X[ci], M.harm.values[ci], g[ci])
    cm = tr & (M.crit.values == 1)
    P["unv"] = fit_export(X[cm], 1 - M.informed.values[cm], g[cm])
    P["mono"] = fit_export(X[tr], M.harm.values[tr], g[tr])
    z = {k: apply(p, X[ic]) for k, p in P.items()}
    S = {"ecg": G.ls(z["crit"]) + log_or(z["auth"], z["unv"]), "ecg_m": G.ls(z["crit"]) + log_or(z["mono"], z["unv"]),
         # split-conformal union branches (each calibrated at alpha/2; union bound keeps the episode false-block <= alpha)
         "br_auth_mono": G.ls(z["crit"]) + G.ls(z["mono"]), "br_auth": G.ls(z["crit"]) + G.ls(z["auth"]),
         "br_unv": G.ls(z["crit"]) + G.ls(z["unv"])}
    Mc = M[ic].reset_index(drop=True); y = Mc.harm.values == 1; inf = Mc.informed.values == 1; crit = Mc.crit.values == 1
    comp = (~y) & ((~crit) | inf); ep = Mc.episode_id.values + "|" + Mc.scenario_id.str.split("|").str[0].values
    thr = {}
    for arm, s in S.items():
        ce = np.sort(pd.Series(s[comp]).groupby(ep[comp]).max().values)
        thr[arm] = {str(a_): float(ce[min(len(ce) - 1, int(np.ceil((len(ce) + 1) * (1 - a_))) - 1)]) for a_ in (0.025, 0.05, 0.10)}
        thr[arm]["calib_TPR@0.05"] = float((s[y] >= thr[arm]["0.05"]).mean())
    for un, ab in (("union_mono", "br_auth_mono"), ("union_auth", "br_auth")):   # branches at alpha/2 = 0.025
        fire = (S[ab] >= thr[ab]["0.025"]) | (S["br_unv"] >= thr["br_unv"]["0.025"])
        epf = pd.Series(fire[comp]).groupby(ep[comp]).max()
        thr[un] = {"rule": f"{ab}>=thr[{ab}][0.025] OR br_unv>=thr[br_unv][0.025]", "calib_episode_false_block": float(epf.mean()),
                   "calib_TPR": float(fire[y].mean())}
    out = REPO_ROOT / "outputs/deploy_gate"; out.mkdir(parents=True, exist_ok=True)
    np.savez(out / "gate_v32.npz", **{f"{k}_{f}": v for k, p in P.items() for f, v in p.items()})
    meta = {"layer_index_in_extracted": 2, "qwen_layer": 45, "feature": "mean of last 8 tokens of the proposed action turn",
            "train_actors": ACTORS, "n_train": int(tr.sum()), "n_cal": int(ic.sum()), "thresholds": thr}
    json.dump(meta, open(out / "gate_v32.json", "w"), indent=1); print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
