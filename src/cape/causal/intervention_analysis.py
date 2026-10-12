"""Analysis of activation-patching outcomes (site = unit of inference; samples are clustered within site)."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from cape.eval.statistics import benjamini_hochberg, permutation_test_paired

OUTCOMES = ["proceed", "unsafe", "escalated", "critical_any", "imm_critical", "imm_escalation", "imm_final"]


def _boot_ci(x, n=2000, seed=0):
    x = np.asarray(x, float)
    if len(x) < 2:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    m = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(n)]
    return float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))


def analyze(patch_dir: Path, res_dir: Path, n_boot: int = 2000, seed: int = 0) -> pd.DataFrame:
    patch_dir, res_dir = Path(patch_dir), Path(res_dir)
    res_dir.mkdir(parents=True, exist_ok=True)
    o = pd.read_parquet(patch_dir / "outcomes.parquet")
    sites = pd.read_parquet(patch_dir / "sites.parquet")
    site_mean = o.groupby(["site_id", "condition", "layer"])[OUTCOMES].mean().reset_index()
    base = {c: site_mean[site_mean.condition == c].set_index("site_id")[OUTCOMES] for c in ("base_neg", "base_pos")}

    rows = []
    recip = o.groupby("condition").recipient.first().to_dict()
    for (cond, layer), g in site_mean.groupby(["condition", "layer"]):
        g = g.set_index("site_id")
        ref = "base_pos" if recip.get(cond) == "plus" else "base_neg"
        row = {"condition": cond, "layer": layer, "reference": ref, "n_sites": len(g)}
        for oc in OUTCOMES:
            row[f"P_{oc}"] = float(g[oc].mean())
            row[f"P_{oc}_ci"] = list(_boot_ci(g[oc].values, n_boot, seed))
            if cond not in ("base_neg", "base_pos"):
                b = base[ref].reindex(g.index)[oc]
                d = g[oc].values - b.values
                ok = ~np.isnan(d)
                row[f"delta_{oc}"] = float(d[ok].mean()) if ok.any() else np.nan
                row[f"delta_{oc}_ci"] = list(_boot_ci(d[ok], n_boot, seed))
                row[f"p_{oc}"] = permutation_test_paired(g[oc].values[ok], b.values[ok], seed=seed) if ok.sum() > 1 else np.nan
        rows.append(row)
    R = pd.DataFrame(rows)
    # effect of each targeted patch relative to the norm-matched random control at the same layer
    for oc in ("proceed", "unsafe", "critical_any", "imm_critical"):
        if oc not in site_mean:
            continue
        R[f"vs_rand_{oc}"] = np.nan
        R[f"p_vs_rand_{oc}"] = np.nan
        for i, r in R.iterrows():
            ctrls = [c for c in (("rand_pos", "rev_dn_all_rand") if recip.get(r.condition) == "plus" else
                                 ("rand", "dn_all_rand")) if c in recip]
            if r.condition not in ("base_neg", "base_pos") and "rand" not in r.condition and ctrls:
                ctrl = ctrls[0]
                a = site_mean[(site_mean.condition == r.condition) & (site_mean.layer == r.layer)].set_index("site_id")[oc]
                b = site_mean[(site_mean.condition == ctrl) & (site_mean.layer == r.layer)].set_index("site_id")[oc]
                j = pd.concat([a, b], axis=1, keys=["a", "b"]).dropna()
                if len(j) > 1:
                    R.at[i, f"vs_rand_{oc}"] = float((j.a - j.b).mean())
                    R.at[i, f"p_vs_rand_{oc}"] = permutation_test_paired(j.a.values, j.b.values, seed=seed)
    for oc in ("proceed", "unsafe"):
        m = R[f"p_{oc}"].notna()
        if m.any():
            R.loc[m, f"p_bh_{oc}"] = benjamini_hochberg(R.loc[m, f"p_{oc}"].values)[0]
    R.to_csv(res_dir / "patching_effect.csv", index=False)

    # rescue effect R_{t,l} = P(Y=1 | x-) - P(Y=1 | do(h <- patched)) per condition x layer, plus by distance
    conds = [c for c in R.condition.unique() if c not in ("base_neg", "base_pos")]
    layers = sorted(l for l in R.layer.unique() if l >= 0)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    for ax, oc in zip(axes, ("proceed", "unsafe")):
        M = np.full((len(conds), len(layers)), np.nan)
        for i, c in enumerate(conds):
            for j, l in enumerate(layers):
                v = R[(R.condition == c) & (R.layer == l)][f"delta_{oc}"]
                if len(v):
                    M[i, j] = v.iloc[0]
        lim = np.nanmax(np.abs(M)) if np.isfinite(M).any() else 1
        im = ax.imshow(M, cmap="RdBu_r", vmin=-lim, vmax=lim, aspect="auto")
        ax.set_xticks(range(len(layers)), layers)
        ax.set_yticks(range(len(conds)), conds)
        for i in range(len(conds)):
            for j in range(len(layers)):
                if np.isfinite(M[i, j]):
                    ax.text(j, i, f"{M[i, j]:+.2f}", ha="center", va="center", fontsize=7)
        ax.set_xlabel("layer")
        ax.set_title(f"Delta P({oc}) vs unpatched reference\n(rev vs x+ baseline; others vs x- baseline)", fontsize=8)
        fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(res_dir / "patching_heatmap.pdf")

    # distance-to-harm view for sites whose original rollout was unsafe
    s = sites[["site_id", "t_star", "T_harm", "unsafe_episode", "family"]].copy()
    s["dist"] = s.T_harm - s.t_star
    sm = site_mean.merge(s, on="site_id")
    sm.to_csv(res_dir / "patching_site_level.csv", index=False)
    return R
