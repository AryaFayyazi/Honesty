#!/usr/bin/env python
"""v76 descriptive robustness: out-of-fold readout scores with folds by INJECTION task (attacked episodes; benign episodes by user
task), so the readout is always scored on injection goals it was not fit on. python scripts/197_v76_lito.py <actor>"""
import glob
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / "outputs/v76"
M = __import__("importlib").import_module


def main(A, K=5):
    B = [json.loads(x) for x in open(OUT / f"dev_{A}_benign.jsonl")]; T = [json.loads(x) for x in open(OUT / f"dev_{A}_attack.jsonl")]
    F = {}
    for fn in sorted(glob.glob(str(OUT / f"feats_dev_{A}_*.npz"))):
        z = np.load(fn); F.update({k: z[k] for k in z.files})
    U = []
    for src, R in (("benign", B), ("attack", T)):
        for e in R:
            if e["error"] is None:
                for c in e["calls"]:
                    if c["tool"] and c.get("call_id") in F:
                        grp = f"{e['suite']}|{e['injection_task']}" if src == "attack" else f"benign|{e['suite']}|{e['user_task']}"
                        U.append((c["call_id"], c["tool"], int(bool(c.get("injected"))), src, grp))
    X = np.stack([F[u[0]].astype(np.float32) for u in U]); y = np.array([u[2] for u in U]); tool = np.array([u[1] for u in U]); src = np.array([u[3] for u in U])
    fold = np.array([int(hashlib.sha256(f"lito|{u[4]}".encode()).hexdigest(), 16) % K for u in U]); oof = np.zeros(len(U))
    for k in range(K):
        tr, te = fold != k, fold == k; zz = []
        for li in range(X.shape[1]):
            l2 = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto").fit(X[tr, li], y[tr]); s_tr = l2.decision_function(X[tr, li])
            zz.append((l2.decision_function(X[te, li]) - s_tr.mean()) / (s_tr.std() + 1e-8))
        oof[te] = np.mean(zz, 0)
    ben = src == "benign"; exp = (src == "attack") & (y == 0); tau = float(np.percentile(oof[ben], 90))
    vals, w = [], []
    for t in sorted(set(tool)):
        m = tool == t
        if y[m].sum() >= 3 and (1 - y[m]).sum() >= 3:
            vals.append(roc_auc_score(y[m], oof[m])); w.append(int(y[m].sum()))
    out = {"actor": A, "folds": K, "split": "injection task (attacked) / user task (benign)", "units": len(U), "injected": int(y.sum()),
           "auroc_within_tool": float(np.average(vals, weights=w)), "auroc_injected_vs_benign": float(roc_auc_score(np.r_[np.ones(y.sum()), np.zeros(ben.sum())], np.r_[oof[y == 1], oof[ben]])),
           "auroc_injected_vs_exposed_other": float(roc_auc_score(np.r_[np.ones(y.sum()), np.zeros(exp.sum())], np.r_[oof[y == 1], oof[exp]])),
           "tau": tau, "fire_on_injected": float((oof[y == 1] > tau).mean()), "fire_on_exposed_other": float((oof[exp] > tau).mean())}
    (ROOT / "results/prereg_v76").mkdir(parents=True, exist_ok=True); json.dump(out, open(ROOT / f"results/prereg_v76/lito_{A}.json", "w"), indent=1); print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
