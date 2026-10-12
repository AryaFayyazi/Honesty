#!/usr/bin/env python
"""Cross-model white-box gate analysis on replay features (outputs/xm_feats), mirroring the Qwen analysis.

python scripts/61_xm_gate_analysis.py actor=gemma4

Primary feature fixed a priori: mean of the last 8 tokens at ~72% depth (layer index 2 of the 5 extracted).
(1) In-distribution harm-probe gate: repeated grouped CV over scenarios; TPR@1%FPR over all safe actions and over hard
    negatives (authorized critical actions in x+); scenario-bootstrap CIs.
(2) Out-of-distribution, leave-one-template-out: monolithic harm probe vs counterfactual compositional gate
    (critical predicate x unsafe-world predicate, neither trained on violation labels).
"""
import json

import numpy as np
import pandas as pd
from omegaconf import OmegaConf
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from cape.eval.statistics import auroc
from cape.utils.config import REPO_ROOT, load_config

D = OmegaConf.create({"bench": "v2fresh", "actor": "gemma4", "layer_idx": 2, "feat": "mean8", "repeats": 5, "nboot": 2000, "clean": False})


def load(actor, li, feat, bench="v2fresh", clean=False):
    col = set(json.load(open(REPO_ROOT / "results/validity/identity_collisions.json"))["v2fresh"])
    Ms, Xs = [], []
    for sfx in ("minus", "plus"):
        st = f"xm_{actor}_{bench}_{sfx}"
        m = pd.read_parquet(REPO_ROOT / f"outputs/xm_feats/{st}_meta.parquet")
        z = np.load(REPO_ROOT / f"outputs/xm_feats/{st}.npz")
        Ms.append(m); Xs.append(z[feat][:, li, :].astype(np.float32))
    M = pd.concat(Ms, ignore_index=True); X = np.vstack(Xs)
    keep = ~M.scenario_id.isin(col).values
    M = M[keep].reset_index(drop=True); X = X[keep]
    M["world"] = (M.cf == "unsafe").astype(int)
    if clean:  # gate semantics: harm = FIRST unsafe action; drop actions after it (already-contaminated context)
        M = M.sort_values(["episode_id", "event_id"])
        first = M[M.y == 1].groupby("episode_id").event_id.min()
        fu = M.episode_id.map(first)
        keepc = fu.isna() | (M.event_id <= fu)
        X = X[keepc.values[np.argsort(M.index.values)]] if False else X[M.index.values[keepc.values]]
        M = M[keepc].reset_index(drop=True)
    M["hard_neg"] = ((M.cf == "safe") & (M.critical == 1)).astype(int)
    return M, X


def fit(X, y):
    sc = StandardScaler().fit(X)
    m = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced").fit(sc.transform(X), y)
    return lambda Z: m.decision_function(sc.transform(Z))


def logsig(z):
    return -np.logaddexp(0, -z)


def tpr_at(s, y, neg, a=0.01):
    if neg.sum() < 10 or (y == 1).sum() == 0:
        return None
    return float((s[y == 1] >= np.quantile(s[neg], 1 - a)).mean())


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    M, X = load(cfg.actor, cfg.layer_idx, cfg.feat, cfg.bench, cfg.clean)
    y = M.y.values.astype(int); scen = M.scenario_id.values
    allneg = (y == 0); hard = (M.hard_neg.values == 1) & (y == 0)
    res = {"actor": cfg.actor, "n_actions": len(M), "n_harm": int(y.sum()), "n_hard_neg": int(hard.sum()),
           "harms_by_template": M[M.y == 1].template.value_counts().to_dict()}
    # (1) in-distribution
    uniq = np.array(sorted(set(scen))); oof = np.zeros(len(y))
    for rep in range(cfg.repeats):
        perm = np.random.default_rng(rep).permutation(uniq); fold = {s: i % 5 for i, s in enumerate(perm)}
        f = np.array([fold[s] for s in scen]); o = np.zeros(len(y))
        for k in range(5):
            tr, te = f != k, f == k
            o[te] = fit(X[tr], y[tr])(X[te])
        oof += o
    oof /= cfg.repeats
    idx_by = pd.Series(range(len(M))).groupby(list(scen)).apply(lambda v: v.values); keys = list(idx_by.index)
    rng = np.random.default_rng(0); b, bh = [], []
    for _ in range(cfg.nboot):
        p = np.concatenate([idx_by[keys[i]] for i in rng.integers(0, len(keys), len(keys))])
        t1 = tpr_at(oof[p], y[p], allneg[p]); t2 = tpr_at(oof[p], y[p], hard[p])
        if t1 is not None: b.append(t1)
        if t2 is not None: bh.append(t2)
    q = lambda v: [round(float(np.quantile(v, .025)), 3), round(float(np.quantile(v, .975)), 3)]
    res["in_distribution_harm_probe"] = {"auroc": round(float(auroc(y, oof)), 4),
                                         "TPR@1%FPR": round(tpr_at(oof, y, allneg), 3), "ci95": q(b),
                                         "TPR@1%FPR_hardneg": round(tpr_at(oof, y, hard), 3), "ci95_hardneg": q(bh)}
    # (2) leave-one-template-out
    loto = {}
    for t in sorted(M.template.unique()):
        te = (M.template == t).values; tr = ~te
        yt = y[te]
        if yt.sum() < 5:
            loto[t] = {"n_harm": int(yt.sum()), "note": "fewer than 5 harms"}; continue
        mono = fit(X[tr], y[tr])(X[te])
        crit = fit(X[tr], M.critical.values[tr])(X[te])
        world = fit(X[tr], M.world.values[tr])(X[te])
        comp = logsig(crit) + logsig(world)
        negt = allneg[te]; hardt = hard[te]
        loto[t] = {"n_harm": int(yt.sum()),
                   "monolithic": {"auroc": round(float(auroc(yt, mono)), 4), "TPR@1%": tpr_at(mono, yt, negt),
                                  "TPR@1%_hardneg": tpr_at(mono, yt, hardt)},
                   "compositional": {"auroc": round(float(auroc(yt, comp)), 4), "TPR@1%": tpr_at(comp, yt, negt),
                                     "TPR@1%_hardneg": tpr_at(comp, yt, hardt)},
                   "predicate_auroc": {"critical": round(float(auroc(M.critical.values[te], crit)), 4)
                                       if 0 < M.critical.values[te].sum() < te.sum() else None,
                                       "world": round(float(auroc(M.world.values[te], world)), 4)
                                       if 0 < M.world.values[te].sum() < te.sum() else None}}
    ev = [v for v in loto.values() if "monolithic" in v]
    res["loto"] = loto
    res["loto_mean"] = {k: round(float(np.mean([v[k]["auroc"] for v in ev])), 4) for k in ("monolithic", "compositional")}
    print(json.dumps(res, indent=1))
    (REPO_ROOT / "results/xm").mkdir(parents=True, exist_ok=True)
    (REPO_ROOT / f"results/xm/gate_{cfg.actor}_{cfg.bench}_{cfg.feat}{'_clean' if cfg.clean else ''}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
