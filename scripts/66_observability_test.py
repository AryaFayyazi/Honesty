#!/usr/bin/env python
"""Direct test of the observability bound (Theorem 3): before the first world-distinguishing observation, the law of
the context is identical in x+ and x-, so the world is undecodable from ANY function of it, including the actor's
residual stream. Prediction: world-decoding AUROC = 0.5 on uninformed actions, high on informed actions.

python scripts/66_observability_test.py actor=gemma4 feat=pre layer_idx=2

Shrinkage-LDA world probe, grouped 5-fold CV over scenarios (within-fold AUROC averaged), trained and tested within
each stratum; scenario-cluster bootstrap CI; label-permutation null (world labels permuted across scenarios).
"""
import json

import numpy as np
import pandas as pd
from omegaconf import OmegaConf
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.preprocessing import StandardScaler

from cape.eval.statistics import auroc
from cape.utils.config import REPO_ROOT, load_config

D = OmegaConf.create({"actor": "gemma4", "bench": "v2fresh", "feat": "pre", "layer_idx": 2, "nboot": 1000, "nperm": 20})


SEEDS = [0, 1]


def load(actor, bench, feat, li):
    col = (set(json.load(open(REPO_ROOT / "results/validity/identity_collisions.json"))["v2fresh"]) if bench == "v2fresh" else
           set(json.load(open(REPO_ROOT / f"results/validity/{bench}_exclusions.json"))["excluded"]))   # fixed before rollouts
    Ms, Xs = [], []
    sets = [x for x in ("minus", "plus", "plus23", "minus23") if (REPO_ROOT / f"outputs/xm_feats/xm_{actor}_{bench}_{x}.npz").exists()]
    for sfx in sets:
        st = f"xm_{actor}_{bench}_{sfx}"
        Ms.append(pd.read_parquet(REPO_ROOT / f"outputs/xm_feats/{st}_meta.parquet"))
        z = np.load(REPO_ROOT / f"outputs/xm_feats/{st}.npz")[feat]
        Xs.append((z[:, li] if z.ndim == 3 else z).astype(np.float32))
    M = pd.concat(Ms, ignore_index=True); X = np.concatenate(Xs)
    # seed-balanced design: server rollouts used x- seeds 0-3 vs x+ seeds 0-1 with a shared per-seed random stream
    # (decodable fingerprint); keep seeds {0,1} in both worlds unless seeds=all
    sd = M.episode_id.str.extract(r"\.s(\d+)$")[0].astype(int)
    both = sorted(set(sd[M.cf.values == "unsafe"]) & set(sd[M.cf.values == "safe"]))
    keep = ~M.scenario_id.isin(col).values & (sd.isin(both).values if SEEDS is not None else True)
    print(f"sets={sets} seeds used={both if SEEDS is not None else 'all'}", flush=True)
    M, X = M[keep].reset_index(drop=True), X[keep]
    ra = actor.split("-", 1)[1] if actor.startswith("rdqwen-") else actor   # reader mode: rollouts of the read actor
    pre = bench if ra in ("qwenexact", "qwen38") else f"xm_{ra}_{bench}"   # Qwen rollouts: <bench>_{minus,plus}
    R = pd.concat([pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{pre}_{s}.parquet", columns=["episode_id", "reveal_event"])
                   for s in ("minus", "plus", "plus23", "minus23") if (REPO_ROOT / f"outputs/rollouts/{pre}_{s}.parquet").exists()]).drop_duplicates("episode_id").set_index("episode_id").reveal_event
    M["informed"] = (pd.to_numeric(M.episode_id.map(R), errors="coerce") < M.event_id).fillna(False).astype(int).values
    M["world"] = (M.cf == "unsafe").astype(int)
    return M, X


def cv_scores(X, y, scen, seed=0):
    uniq = np.array(sorted(set(scen))); f = {s: i % 5 for i, s in enumerate(np.random.default_rng(seed).permutation(uniq))}
    fold = np.array([f[s] for s in scen]); s = np.zeros(len(y))
    for k in range(5):
        tr, te = fold != k, fold == k
        if len(set(y[tr])) < 2:
            continue
        sc = StandardScaler().fit(X[tr])
        s[te] = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto").fit(sc.transform(X[tr]), y[tr]).decision_function(sc.transform(X[te]))
    return s, fold


def within_fold_auroc(s, y, fold):
    v = [auroc(y[fold == k], s[fold == k]) for k in range(5) if 0 < y[fold == k].sum() < (fold == k).sum()]
    return float(np.mean(v))


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    global SEEDS
    SEEDS = None if cfg.get("seeds", "01") == "all" else [0, 1]
    M, X = load(cfg.actor, cfg.bench, cfg.feat, cfg.layer_idx)
    out = {"actor": cfg.actor, "feat": cfg.feat, "layer_idx": cfg.layer_idx}
    for name, sel in (("uninformed", M.informed.values == 0), ("informed", M.informed.values == 1)):
        m, x = M[sel].reset_index(drop=True), X[sel]
        y, scen = m.world.values, m.scenario_id.values
        s, fold = cv_scores(x, y, scen)
        a = within_fold_auroc(s, y, fold)
        idx = pd.Series(range(len(m))).groupby(list(scen)).apply(lambda v: v.values); keys = list(idx.index)
        rng = np.random.default_rng(0); b = []
        for _ in range(cfg.nboot):
            p = np.concatenate([idx[keys[i]] for i in rng.integers(0, len(keys), len(keys))])
            if 0 < y[p].sum() < len(p):
                b.append(auroc(y[p], s[p]))
        # permutation null: permute world labels at the episode level within scenario (preserves the grouping)
        null = []
        ep = m.episode_id.values; ueps = pd.Series(ep).drop_duplicates()
        epw = m.groupby("episode_id").world.first()
        for r in range(cfg.nperm):
            g = np.random.default_rng(100 + r)
            perm = epw.groupby(m.groupby("episode_id").scenario_id.first()).transform(lambda v: g.permutation(v.values))
            yp = m.episode_id.map(perm).values
            sp, fp = cv_scores(x, yp, scen, seed=r)
            null.append(within_fold_auroc(sp, yp, fp))
        out[name] = {"n_actions": int(len(m)), "n_episodes": int(m.episode_id.nunique()),
                     "frac_unsafe_world": round(float(y.mean()), 3), "world_auroc_within_fold": round(a, 4),
                     "pooled_auroc_ci95": [round(float(np.quantile(b, .025)), 4), round(float(np.quantile(b, .975)), 4)],
                     "perm_null_mean": round(float(np.mean(null)), 4), "perm_null_q95": round(float(np.quantile(null, .95)), 4),
                     "p_perm": round(float((1 + sum(n >= a for n in null)) / (1 + len(null))), 4)}
        print(name, out[name], flush=True)
    (REPO_ROOT / f"results/xm/observability_{cfg.actor}_{cfg.bench}_{cfg.feat}_L{cfg.layer_idx}{'_seedsall' if SEEDS is None else ''}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
