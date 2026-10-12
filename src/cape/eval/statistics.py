"""Statistics: scenario-clustered bootstrap, paired comparisons, multiple-comparison control."""
from __future__ import annotations

import numpy as np
from scipy import stats
from sklearn.metrics import average_precision_score, roc_auc_score


def auroc(y, s):
    y = np.asarray(y)
    return float(roc_auc_score(y, s)) if 0 < y.sum() < len(y) else np.nan


def auprc(y, s):
    y = np.asarray(y)
    return float(average_precision_score(y, s)) if 0 < y.sum() < len(y) else np.nan


def threshold_at_fpr(y_val, s_val, fpr: float = 0.01) -> float:
    """Smallest threshold whose FPR on validation negatives is <= fpr (score > tau => alarm)."""
    neg = np.sort(np.asarray(s_val)[np.asarray(y_val) == 0])
    if len(neg) == 0:
        return np.inf
    k = int(np.floor(fpr * len(neg)))
    return float(neg[len(neg) - 1 - k]) if k < len(neg) else float(neg[0])


def tpr_fpr_at(y, s, tau):
    y, s = np.asarray(y), np.asarray(s)
    pos, neg = y == 1, y == 0
    return (float((s[pos] > tau).mean()) if pos.any() else np.nan,
            float((s[neg] > tau).mean()) if neg.any() else np.nan)


def cluster_bootstrap(df, cluster: str, fn, n: int = 2000, seed: int = 0, alpha: float = 0.05):
    """Percentile CI of fn(df_resampled), resampling whole clusters (e.g. scenario_id) with replacement."""
    rng = np.random.default_rng(seed)
    groups = {k: v.index.values for k, v in df.groupby(cluster)}
    keys = np.array(list(groups))
    point = fn(df)
    vals = []
    for _ in range(n):
        pick = rng.choice(len(keys), len(keys), replace=True)
        idx = np.concatenate([groups[keys[i]] for i in pick])
        v = fn(df.loc[idx])
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            vals.append(v)
    if not vals:
        return point, np.nan, np.nan
    lo, hi = np.quantile(vals, [alpha / 2, 1 - alpha / 2])
    return point, float(lo), float(hi)


def paired_cluster_bootstrap_diff(df, cluster, fn_a, fn_b, n: int = 2000, seed: int = 0):
    """CI and two-sided bootstrap p-value for fn_a(df) - fn_b(df) under shared cluster resampling."""
    rng = np.random.default_rng(seed)
    groups = {k: v.index.values for k, v in df.groupby(cluster)}
    keys = np.array(list(groups))
    point = fn_a(df) - fn_b(df)
    vals = []
    for _ in range(n):
        idx = np.concatenate([groups[keys[i]] for i in rng.choice(len(keys), len(keys), replace=True)])
        d = df.loc[idx]
        v = fn_a(d) - fn_b(d)
        if not np.isnan(v):
            vals.append(v)
    vals = np.asarray(vals)
    lo, hi = np.quantile(vals, [0.025, 0.975])
    p = float(min(1.0, 2 * min((vals <= 0).mean(), (vals >= 0).mean())))
    return float(point), float(lo), float(hi), p


def benjamini_hochberg(p, q: float = 0.05):
    p = np.asarray(p, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order] * n / (np.arange(n) + 1)
    adj = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(adj, 1.0)
    return out, out <= q


def mcnemar_exact(b: int, c: int) -> float:
    """b = base-positive/intervention-negative, c = the reverse discordant count."""
    n = b + c
    return float(stats.binomtest(min(b, c), n, 0.5).pvalue) if n else 1.0


def permutation_test_paired(x, y, n: int = 10000, seed: int = 0) -> float:
    d = np.asarray(x, float) - np.asarray(y, float)
    rng = np.random.default_rng(seed)
    obs = abs(d.mean())
    signs = rng.choice([-1, 1], size=(n, len(d)))
    return float(((np.abs((signs * d).mean(1)) >= obs).sum() + 1) / (n + 1))


def within_fold_auroc(df, label: str = "y_eventual", score: str = "score", fold: str = "fold") -> float:
    """AUROC computed inside each held-out fold (both classes present), averaged with weights = #positives.

    Pooling out-of-fold scores across folds compares scores produced by DIFFERENT models whose offsets are
    arbitrary; with unequal fold prevalence (e.g. leave-one-family-out) this biases pooled AUROC in either direction.
    """
    vals, w = [], []
    for _, g in df.groupby(fold):
        if g[label].nunique() == 2:
            vals.append(auroc(g[label], g[score]))
            w.append(g[label].sum())
    return float(np.average(vals, weights=w)) if vals else np.nan
