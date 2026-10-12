#!/usr/bin/env python
"""Figure-3a time course (CPU, main env): pooled AUROC with 95% scenario-cluster bootstrap CIs at every moment.
- reveal:   v55 fresh scores (outputs/v55/scores.parquet; preregistered; I, T_sup on all units, M_cot on its subset)
- h2, h1:   1 and 2 actions before the violation vs X-OTHER (v57 secondary, descriptive). Recomputed with the exact
            scripts/155 horizons() recipe (same seed), keeping per-unit scores so the four models can be pooled.
- decision: v57 fresh scores vs X-OTHER (outputs/v57/scores.parquet; preregistered)
python scripts/163_timecourse_ci.py   -> results/prereg_v57/timecourse.json"""
import importlib.util
import json

import numpy as np
import pandas as pd

from cape.utils.config import REPO_ROOT


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


V57 = _mod("v57", "scripts/155_v57_analysis.py"); M150 = V57.M150; B = 2000


def pboot(D, a, b=None, B=B, seed=55, n_jobs=32):
    """M150.boot with the same resamples (same rng draws), evaluated in parallel."""
    from joblib import Parallel, delayed
    D = D.dropna(subset=[a] + ([b] if b else [])).reset_index(drop=True); rng = np.random.default_rng(seed); cl = (D.model + "|" + D.scenario_id).values
    u = np.unique(cl); idx = {c: np.where(cl == c)[0] for c in u}; f = (lambda d: M150.auc(d, a) - M150.auc(d, b)) if b else (lambda d: M150.auc(d, a) - 0.5)
    draws = [np.concatenate([idx[c] for c in rng.choice(u, len(u))]) for _ in range(B)]
    v = np.array(Parallel(n_jobs=n_jobs, batch_size=16)(delayed(f)(D.iloc[ix]) for ix in draws)); v = v[~np.isnan(v)]
    return {"diff": round(f(D), 4), "ci95": [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)],
            "p_one_sided": float((np.sum(v <= 0) + 1) / (len(v) + 1)), "n": int(len(D)), "violators": int(D.y.sum())}


def horizon_scores(A, C, X):
    """scripts/155 horizons(), returning the scored fresh units instead of per-model summaries."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    Dv, Xd = V57.units(A, "dev", with_x=True); res = {}; rng = np.random.default_rng(57)
    for h in (1, 2):
        def pick(M, Xm, k_neg=2):
            pos = np.where(M.cls.values == f"H{h}")[0]; neg = np.where(M.cls.values == "XOTHER")[0]
            neg = rng.choice(neg, min(len(neg), k_neg * len(pos)), replace=False) if len(pos) else neg[:0]
            idx = np.concatenate([pos, neg]); d = M.iloc[idx].reset_index(drop=True); d["y"] = (d.cls == f"H{h}").astype(int)
            return d, (Xm[idx] if Xm is not None else None)
        dd, xd = pick(Dv, Xd); cc, xc = pick(C, X)
        if dd.y.sum() < 30 or cc.y.sum() < 15:
            continue
        cc["I"] = M150.score_internal(M150.fit_internal(xd, dd.y.values), xc)
        v = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True); lr = LogisticRegression(C=1.0, max_iter=3000).fit(v.fit_transform(V57.texts(dd)), dd.y.values)
        cc["T_sup"] = lr.decision_function(v.transform(V57.texts(cc))); cc["template"] = cc.template + "|" + cc.tool
        res[f"h{h}"] = cc[["model", "template", "scenario_id", "y", "I", "T_sup"]]
    return res


def point(D, keys, sub=None):
    out = {}
    for k in keys:
        d = D if (sub is None or k != "M_cot") else D[sub]
        if k not in d or d[k].notna().sum() == 0:
            continue
        b = pboot(d, k); out[k] = {"auroc": round(b["diff"] + 0.5, 4), "ci95": [round(b["ci95"][0] + 0.5, 4), round(b["ci95"][1] + 0.5, 4)],
                                            "n": b["n"], "violators": b["violators"]}
    if "I" in D and "T_sup" in D:
        out["I_minus_T"] = pboot(D, "I", "T_sup")
    return out


def main():
    out = {}
    S55 = pd.read_parquet(REPO_ROOT / "outputs/v55/scores.parquet")
    print("start", flush=True)
    S55c = S55[S55.split == "conf"] if "split" in S55 else S55
    out["reveal"] = point(S55c, ["I", "T_sup", "M_cot"], sub=S55c.M_cot.notna() if "M_cot" in S55c else None)
    S57 = pd.read_parquet(REPO_ROOT / "outputs/v57/scores.parquet"); vo = S57[S57.cls.isin(["VIOL", "XOTHER"])]
    out["decision"] = point(vo, ["I", "T_sup", "M_cot"], sub=vo.M_cot.notna())
    json.dump(out, open(REPO_ROOT / "results/prereg_v57/timecourse.json", "w"), indent=1, default=str); print("reveal+decision done", flush=True)
    H = {"h1": [], "h2": []}
    for A in V57.D.models:
        C, X = V57.units(A, "conf"); hs = horizon_scores(A, C, X)
        for k, d in hs.items():
            H[k].append(d); print(A, k, "I", round(M150.auc(d, "I"), 4), "T", round(M150.auc(d, "T_sup"), 4), flush=True)
        del C, X
    for k, parts in H.items():
        out[k] = point(pd.concat(parts, ignore_index=True), ["I", "T_sup"])
    json.dump(out, open(REPO_ROOT / "results/prereg_v57/timecourse.json", "w"), indent=1, default=str); print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
