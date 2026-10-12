#!/usr/bin/env python
"""v72 (prereg docs/preregistration_v72.md): fit the readout recipe on τ² real-context development decisions (main env, CPU).
python scripts/190_v72_refit.py <actor>  -> outputs/v72/gate_refit_<a>.npz, outputs/v72/tau_<a>.json, results/prereg_v72/fit_<a>.json"""
import json
import sys

import numpy as np
import pandas as pd
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import roc_auc_score

from cape.utils.config import REPO_ROOT

OUT = REPO_ROOT / "outputs/v72"; RES = REPO_ROOT / "results/prereg_v72"


def auc_within(df):
    vals, w = [], []
    for _, g in df.groupby("tool"):
        y = (g.category == "VIOLATION").astype(int)
        if y.sum() >= 3 and (1 - y).sum() >= 3:
            vals.append(roc_auc_score(y, g.score)); w.append(len(g))
    return float(np.average(vals, weights=w)) if vals else float("nan")


def main(A):
    R = pd.read_csv(OUT / f"dev_{A}_none.csv"); F = np.load(OUT / f"feats_dev_{A}.npz")
    R = R[R.call_id.isin(set(F.files)) & R.category.isin(["VIOLATION", "AUTHORIZED_WRITE", "READ"])].reset_index(drop=True)
    X = np.stack([F[k].astype(np.float32) for k in R.call_id]); y = (R.category == "VIOLATION").astype(int).values
    tasks = np.array(sorted(R.task_id.astype(str).unique())); fold = R.task_id.astype(str).map({t: i % 2 for i, t in enumerate(tasks)}).values
    params = {}
    for li in range(X.shape[1]):
        lda = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto").fit(X[:, li], y); s = lda.decision_function(X[:, li])
        params.update({f"w_{li}": lda.coef_[0], f"b_{li}": lda.intercept_[0], f"mu_{li}": s.mean(), f"sd_{li}": s.std() + 1e-8})
    oof = np.zeros(len(R))
    for k in (0, 1):
        tr, te = fold != k, fold == k; zz = []
        for li in range(X.shape[1]):
            l2 = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto").fit(X[tr, li], y[tr]); s_tr = l2.decision_function(X[tr, li])
            zz.append((l2.decision_function(X[te, li]) - s_tr.mean()) / (s_tr.std() + 1e-8))
        oof[te] = np.mean(zz, 0)
    R["score"] = oof; W = R[R.category.isin(["VIOLATION", "AUTHORIZED_WRITE"])]
    a_w = auc_within(W); a_p = float(roc_auc_score((W.category == "VIOLATION").astype(int), W.score)) if W.category.nunique() == 2 else float("nan")
    tau = float(max(np.percentile(R[R.category == "AUTHORIZED_WRITE"].score, 90), np.percentile(R[R.category == "READ"].score, 90) if (R.category == "READ").any() else -np.inf))
    out = {"actor": A, "n": int(len(R)), "violation": int(y.sum()), "authorized_write": int((R.category == "AUTHORIZED_WRITE").sum()), "read": int((R.category == "READ").sum()),
           "oof_auroc_within_tool": a_w, "oof_auroc_pooled_writes": a_p, "tau": tau, "go": bool(a_w >= 0.65),
           "oof_fire_on_violation": float((R[R.category == "VIOLATION"].score > tau).mean())}
    OUT.mkdir(parents=True, exist_ok=True); RES.mkdir(parents=True, exist_ok=True)
    np.savez(OUT / f"gate_refit_{A}.npz", n_layers=X.shape[1], **params); json.dump({"tau": tau, "mode": "refit"}, open(OUT / f"tau_{A}.json", "w"))
    json.dump(out, open(RES / f"fit_{A}.json", "w"), indent=2); print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
