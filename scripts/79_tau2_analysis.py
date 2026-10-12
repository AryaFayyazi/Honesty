#!/usr/bin/env python
"""Prereg v30 analyses on published tau2-bench airline trajectories of frontier agents (Qwen3.8 reader features).

python scripts/79_tau2_analysis.py
X1 zero-shot transfer: v29-frozen ECG + monolithic probe trained on CAPE v2fresh Qwen-reader features (qwen38 +
   rdqwen-{gemma4,gptoss20b,museglimmer}, seed-balanced) applied unchanged to tau2 write calls; AUROC NOT ALLOWED vs
   ALLOWED with task-cluster bootstrap CI.
X2 in-domain: grouped 5-fold CV by task, monolithic shrinkage-LDA reader probe on writes; within-fold TPR@5% FPR over
   ALLOWED writes; AUROC with task-cluster bootstrap CI.
X3 epistemic: share of NOT ALLOWED writes without a prior read of the reservation (per agent, bootstrap CI); AUROC of
   the CAPE-trained P_unv for "no prior read" among writes.
Output: results/v30/tau2_results.json
"""
import importlib.util
import json

import numpy as np
import pandas as pd

from cape.eval.statistics import auroc
from cape.utils.config import REPO_ROOT

spec = importlib.util.spec_from_file_location("ecg", REPO_ROOT / "scripts/65_epistemic_gate.py")
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)
CAPE_ACTORS = ["qwen38", "rdqwen-gemma4", "rdqwen-gptoss20b", "rdqwen-museglimmer"]
NBOOT = 2000


def boot_auc(y, s, groups, rng):
    u = np.unique(groups); idx = {g: np.where(groups == g)[0] for g in u}; out = []
    for _ in range(NBOOT):
        p = np.concatenate([idx[g] for g in rng.choice(u, len(u))])
        if 0 < y[p].sum() < len(p):
            out.append(auroc(y[p], s[p]))
    return [round(float(np.quantile(out, .025)), 4), round(float(np.quantile(out, .975)), 4)]


def main():
    rng = np.random.default_rng(0)
    T = pd.read_parquet(REPO_ROOT / "outputs/xm_feats/tau2_rdqwen_meta.parquet")
    XT = np.load(REPO_ROOT / "outputs/xm_feats/tau2_rdqwen.npz")["mean8"][:, 2].astype(np.float32)
    keep = T.label.isin(["NOT_ALLOWED", "ALLOWED"]).values
    T, XT = T[keep].reset_index(drop=True), XT[keep]
    y = (T.label == "NOT_ALLOWED").values.astype(int); tasks = T.task_id.astype(str).values
    res = {"n_writes": int(len(T)), "n_not_allowed": int(y.sum()), "by_agent": T.groupby("model").label.value_counts().unstack(fill_value=0).to_dict()}
    # X1: zero-shot from CAPE
    Ms, Xs = [], []
    for a in CAPE_ACTORS:
        G.SEEDS = [0, 1]
        M, X = G.load(a, "v2fresh", "mean8", 2); M["scenario_id"] = a + "|" + M.scenario_id; Ms.append(M); Xs.append(X)
    M = pd.concat(Ms, ignore_index=True); X = np.concatenate(Xs)
    g = G.gate(X, M, XT)
    # Amendment 1: ECG-m = P_crit * OR(P_mono, P_unv), from the same calibrated predicates
    c = G.lda(X, M.crit.values, M.scenario_id.values)(XT)
    x_ = np.minimum(G.ls(-g["mono"]) + G.ls(-g["p_unv"]), -1e-300)
    g["ecg_m"] = G.ls(c) + np.where(x_ > -np.log(2), np.log(-np.expm1(x_)), np.log1p(-np.exp(x_)))
    res["X1"] = {}
    for arm in ("ecg", "mono", "auth_only", "ecg_m"):
        s = g[arm]
        res["X1"][arm] = {"auroc": round(float(auroc(y, s)), 4), "ci95": boot_auc(y, s, tasks, rng),
                          "by_agent": {m: round(float(auroc(y[T.model.values == m], s[T.model.values == m])), 4)
                                       for m in sorted(T.model.unique()) if 0 < y[T.model.values == m].sum() < (T.model.values == m).sum()}}
    res["X1_PASS"] = res["X1"]["ecg"]["ci95"][0] > 0.5
    # X2: in-domain grouped CV by task (monolithic reader probe on writes)
    u = np.array(sorted(set(tasks))); f = {t: i % 5 for i, t in enumerate(np.random.default_rng(0).permutation(u))}
    fold = np.array([f[t] for t in tasks]); s2 = np.zeros(len(T)); hit = np.zeros(len(T), bool)
    for k in range(5):
        tr, te = fold != k, fold == k
        if len(set(y[tr])) < 2:
            continue
        s2[te] = G._lda_raw(XT[tr], y[tr])(XT[te])
        if (te & (y == 0)).sum() >= 10:
            hit[te] = s2[te] >= np.quantile(s2[te & (y == 0)], .95)
    res["X2"] = {"auroc": round(float(auroc(y, s2)), 4), "ci95": boot_auc(y, s2, tasks, rng),
                 "TPR@5%FPR_within_fold": round(float(hit[y == 1].mean()), 3)}
    res["X2_PASS"] = res["X2"]["ci95"][0] > 0.6
    # X3: epistemic share and CAPE-trained P_unv
    nr = ~T.read_reservation_before.astype(bool).values
    share = {}
    for m in sorted(T.model.unique()):
        sel = (T.model.values == m) & (y == 1)
        b = [nr[sel][rng.integers(0, sel.sum(), sel.sum())].mean() for _ in range(NBOOT)] if sel.sum() else [np.nan]
        share[m] = {"n": int(sel.sum()), "share_unread": round(float(nr[sel].mean()), 3) if sel.sum() else None,
                    "ci95": [round(float(np.nanquantile(b, .025)), 3), round(float(np.nanquantile(b, .975)), 3)]}
    res["X3"] = {"share_not_allowed_without_prior_read": share,
                 "P_unv_auroc_for_no_prior_read": round(float(auroc(nr.astype(int), g["p_unv"])), 4) if 0 < nr.sum() < len(nr) else None}
    print(json.dumps(res, indent=1))
    (REPO_ROOT / "results/v30").mkdir(parents=True, exist_ok=True)
    (REPO_ROOT / "results/v30/tau2_results.json").write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
