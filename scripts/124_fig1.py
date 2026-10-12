#!/usr/bin/env python3
"""Figure 1 (paper): detector vs lever inside the agent (Muse-Glimmer). Every number is read from result files.
(a) Every steering direction we tried: held-out detection AUROC of the direction (its own training target) vs the change in the
    false-report rate when the agent is steered along it (fresh confirmation where available).
(b) Cosine similarity among all directions: the lie forecaster (LDA, full fit and its two cross-fitted folds), the multi-layer
    difference of means, the self-counterfactual CAA honesty direction (5 blocks) and a random control.
(c) Where each fresh episode's report goes: no steering (centre) -> honesty direction alpha=8 (right) and -> random direction
    alpha=8 (left), same episodes, same seeds.
Palette: Okabe-Ito, validated with scripts/validate_palette.py (all-pairs CVD >= 6 with direct labels; normal-vision >= 15).
Output: paper/figures/fig1_internals.{pdf,png} + fig1_internals_stats.json"""
import json
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

ROOT = "/home/arya/new_safety/cape"; R = os.environ.get("FIG1_R", f"{ROOT}/outputs/reconcile"); RES = f"{ROOT}/results"; OUT = os.environ.get("FIG1_OUT", f"{ROOT}/paper/figures")
plt.rcParams.update({"font.family": "serif", "font.serif": ["STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix", "font.size": 8,
                     "axes.titlesize": 8.5, "axes.labelsize": 7.8, "xtick.labelsize": 6.8, "ytick.labelsize": 6.8, "legend.fontsize": 6.5,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6, "pdf.fonttype": 42,
                     "savefig.bbox": "tight", "savefig.pad_inches": 0.02})
LIE, HON, OTH, NOREP, LEVER, INK, MUTED = "#D55E00", "#0072B2", "#CC79A7", "#A6A6A6", "#009E73", "#222222", "#6B6B6B"
J = lambda p: json.load(open(f"{RES}/{p}"))
unit = lambda v: v / np.linalg.norm(v)


def panel_a(ax):
    v39 = np.load(f"{R}/v39_directions.npz"); v42 = np.load(f"{R}/v42_directions.npz"); caa = np.load(f"{R}/caa_directions.npz")
    lda_auc = [float(v39["heldout_auroc0"]), float(v39["heldout_auroc1"])]
    dim_auc = [float(v42[f"auroc{k}_{i}"]) for k in (0, 1) for i in range(5)]
    caa_auc = [float(caa[f"auroc{k}_{i}"]) for k in (0, 1) for i in range(5)]
    v41 = J("prereg_v41/confirm.json"); d_lda = v41["W1_chosen_vs_none"]["diff"] if "diff" in v41["W1_chosen_vs_none"] else \
        v41["W1_chosen_vs_none"]["rate_chosen"] - v41["W1_chosen_vs_none"]["rate_none"]
    v43 = J("prereg_v43/confirm.json")["W1_chosen_vs_none"]["diff"]; s2 = J("prereg_v46/summary.json")["S2_complete_case"]; d8 = s2["rate_p8"] - s2["rate_none"]
    d8c = J("prereg_v50/summary.json")["A3"]["steering"]["corrected_diff"]; drand = J("prereg_v46b/summary.json")["descriptive_random_vs_none"]["diff"]
    ax.axhline(0, color=MUTED, lw=0.6); ax.axvline(0.5, color=MUTED, lw=0.5, ls=":")
    ax.axhspan(0.2, 0.32, color=NOREP, alpha=0.15, lw=0); ax.text(0.512, 0.30, "no usable reports", fontsize=5.6, color=MUTED, va="center")

    def pt(xs, y, col, label, marker="o", ms=6, hollow=False, dx=0.008, dy=0.0, ha="left"):
        x = float(np.mean(xs))
        if len(xs) > 1:
            ax.hlines(y, min(xs), max(xs), color=col, lw=1.4, alpha=0.6)
        ax.plot(x, y, marker, ms=ms, color=col, mfc="white" if hollow else col, mew=1.3, zorder=3)
        ax.text(x + dx, y + dy, label, fontsize=6.3, color=INK, ha=ha, va="center")
    pt(lda_auc, d_lda, LIE, "lie forecaster (LDA),\nheld-out fold, $-32\\sigma$", dx=-0.035, dy=-0.005, ha="right")
    pt(dim_auc, 0.235, LIE, "difference of means", marker="X", ms=7, dx=-0.03, dy=0.0, ha="right")
    pt(caa_auc, v43, LEVER, "honesty CAA, $\\alpha$=4", dx=0.035)
    pt(caa_auc, d8, LEVER, "honesty CAA, $\\alpha$=8", ms=7, dx=0.035)
    pt(caa_auc, d8c, LEVER, "label-corrected ($\\alpha$=8)", hollow=True, ms=6, dx=0.035)
    pt([0.5], drand, MUTED, "random, $\\alpha$=8", marker="s", ms=5, dx=0.012, dy=-0.05)
    ax.set_xlim(0.47, 0.92); ax.set_ylim(-0.46, 0.32)
    ax.set_xlabel("detection: held-out AUROC of the direction"); ax.set_ylabel("lever: $\\Delta$ false-report rate when steered")
    ax.set_title("(a) The best detectors are not levers", loc="left")
    return {"lda_auc": lda_auc, "dim_auc_mean": float(np.mean(dim_auc)), "caa_auc_mean": float(np.mean(caa_auc)), "d_lda_fresh": d_lda, "d_caa4": v43,
            "d_caa8": d8, "d_caa8_corrected": d8c, "d_random8": drand}


def panel_b(ax, fig):
    P = np.load(f"{R}/fig1_prep.npz"); v39 = np.load(f"{R}/v39_directions.npz"); v42 = np.load(f"{R}/v42_directions.npz"); caa = np.load(f"{R}/caa_directions.npz")
    D = {"LDA": unit(P["w"]), "LDA fold 0": unit(v39["w0"]), "LDA fold 1": unit(v39["w1"])}
    for i, l in enumerate(v42["layers"]):
        D[f"DiM {l}"] = unit(v42[f"u0_{i}"])
    for i, l in enumerate(caa["layers"]):
        D[f"CAA {l}"] = unit(caa[f"ua_{i}"])
    D["random"] = unit(caa["ra_2"])
    k = list(D); M = np.array([[D[a] @ D[b] for b in k] for a in k])
    cmap = LinearSegmentedColormap.from_list("div", [HON, "#F2F2F2", LIE])
    im = ax.imshow(M, cmap=cmap, vmin=-1, vmax=1)
    ax.set_xticks(range(len(k))); ax.set_yticks(range(len(k))); ax.set_xticklabels(k, rotation=90, fontsize=5.6); ax.set_yticklabels(k, fontsize=5.6)
    for b in (2.5, 7.5, 12.5):
        ax.axhline(b, color="white", lw=1.2); ax.axvline(b, color="white", lw=1.2)
    for i in range(len(k)):
        for j in range(len(k)):
            if i != j and abs(M[i, j]) >= 0.3:
                ax.text(j, i, f"{M[i, j]:.1f}", ha="center", va="center", fontsize=4.6, color="white" if abs(M[i, j]) > 0.6 else INK)
    ax.spines[:].set_visible(False); ax.tick_params(length=0)
    cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.02, ticks=[-1, 0, 1]); cb.ax.tick_params(labelsize=6, length=0); cb.outline.set_visible(False)
    cb.set_label("cosine", fontsize=6.5)
    ax.set_title("(b) Cosine between directions", loc="left")
    iL, iC = [k.index(x) for x in k if x.startswith("LDA")], [k.index(x) for x in k if x.startswith("CAA")]
    return {"max_abs_cos_lda_caa": float(np.abs(M[np.ix_(iL, iC)]).max()), "cos_lda_fold0_fold1": float(M[1, 2]),
            "caa_adjacent_layer_cos": [float(M[iC[i], iC[i + 1]]) for i in range(len(iC) - 1)]}


def cat(l):
    return {"MISREPRESENTED": "lie", "CANDID": "candid", "SPIN": "other", "OMITTED": "other"}.get(l, "none")


def panel_c(ax):
    def lab(name):
        V = pd.read_parquet(f"{R}/{name}_rubric3.parquet"); S = pd.read_parquet(f"{R}/{name}.parquet")
        W = V.pivot_table(index=["set", "episode_id"], columns="message", values="label", aggfunc="first")
        return W.reindex(S.pivot_table(index=["set", "episode_id"], columns="message", values="fold", aggfunc="first").index).fillna("NO_REPORT")
    W = lab("v46B").join(lab("v46R")[["rand_p8_d16"]], how="inner").map(cat)
    order = ["lie", "other", "candid", "none"]; col = {"lie": LIE, "other": OTH, "candid": HON, "none": NOREP}
    name = {"lie": "lie", "other": "spin / omit", "candid": "candid", "none": "no report"}
    n = len(W); gap = 0.035; xs = {"rand_p8_d16": 0.0, "none": 1.0, "caa_p8_d16": 2.0}; w = 0.11

    def stack(c):
        y, out = 0.0, {}
        for o in order:
            h = (W[c] == o).mean() * (1 - gap * (len(order) - 1)); out[o] = (y, y + h); y += h + gap
        return out
    S = {c: stack(c) for c in xs}
    for c, x in xs.items():
        for o in order:
            a, b = S[c][o]
            if b - a > 0:
                ax.add_patch(plt.Rectangle((x - w / 2, a), w, b - a, color=col[o], lw=0))
                if b - a > 0.035:
                    ax.text(x, (a + b) / 2, f"{int(round((W[c] == o).sum()))}", ha="center", va="center", fontsize=5.6, color="white")
    t = np.linspace(0, 1, 40); sm = (1 - np.cos(np.pi * t)) / 2
    for src, dst in (("none", "caa_p8_d16"), ("none", "rand_p8_d16")):
        off_s = {o: S[src][o][0] for o in order}; off_d = {o: S[dst][o][0] for o in order}
        x0, x1 = xs[src] + (w / 2 if xs[dst] > xs[src] else -w / 2), xs[dst] - (w / 2 if xs[dst] > xs[src] else -w / 2)
        for o in order:
            for p in order:
                f = ((W[src] == o) & (W[dst] == p)).mean() * (1 - gap * (len(order) - 1))
                if f <= 0:
                    continue
                y0a, y1a = off_s[o], off_d[p]; off_s[o] += f; off_d[p] += f
                xx = x0 + (x1 - x0) * t; lo = y0a + (y1a - y0a) * sm
                hot = o == "lie" and p != "lie"
                ax.fill_between(xx, lo, lo + f, color=LEVER if (hot and dst == "caa_p8_d16") else col[o], alpha=0.55 if hot else 0.22, lw=0)
    for o in order:
        a, b = S["none"][o]; ax.text(1.0 + w / 2 + 0.03, (a + b) / 2, "", fontsize=6)
    for c, ttl in (("rand_p8_d16", "random\n$\\alpha$=8"), ("none", "no\nsteering"), ("caa_p8_d16", "honesty\n$\\alpha$=8")):
        ax.text(xs[c], 1.03, ttl, ha="center", va="top", fontsize=6.4, color=INK)
    for o in order:
        a, b = S["caa_p8_d16"][o]
        if b - a > 0:
            ax.text(2.0 + w / 2 + 0.05, (a + b) / 2, name[o], ha="left", va="center", fontsize=6.2, color=INK)
    ax.set_xlim(-0.12, 2.75); ax.set_ylim(1.2, -0.02); ax.axis("off")
    ax.set_title("(c) Steering along $u$ turns lies into candid reports", loc="left")
    tr = lambda d: {f"{o}->{p}": int(((W["none"] == o) & (W[d] == p)).sum()) for o in order for p in order}
    return {"n": int(n), "honesty_transitions": tr("caa_p8_d16"), "random_transitions": tr("rand_p8_d16")}


def panel_traj(ax):
    """(a) the confirmatory forecaster along the episode (3 models, fresh set C), aligned to the violation."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("x95", f"{ROOT}/scripts/95_lie_forecast.py"); X95 = importlib.util.module_from_spec(spec); spec.loader.exec_module(X95)
    P = np.load(f"{R}/fig1_traj_prep.npz"); rows = []
    for m in ("gemma4", "gptoss20b", "museglimmer"):
        f = f"{R}/fig1_traj_{m}.parquet"
        if not os.path.exists(f):
            return None
        T = pd.read_parquet(f); mu, sd = float(P[f"{m}_mu"]), float(P[f"{m}_sd"])
        for r in T.itertuples():
            ev = list(r.events); sc = (np.array(r.scores) - mu) / sd
            if r.violation_event not in ev:
                continue
            iv = ev.index(r.violation_event); d = {f"V{j - iv:+d}" if j != iv else "V": sc[j] for j in range(len(ev)) if -3 <= j - iv <= 3}
            d["report"] = (r.pre_report - mu) / sd
            grp = "laundering lie" if (r.y and r.retro) else ("other lie" if r.y else "no lie")
            rows.append({"model": m, "template": r.template, "y": r.y, "retro": r.retro, "grp": grp, **d})
    D = pd.DataFrame(rows); xs = ["V-3", "V-2", "V-1", "V", "V+1", "V+2", "V+3", "report"]; xi = np.arange(len(xs))
    col = {"no lie": HON, "laundering lie": LIE, "other lie": OTH}; rng = np.random.default_rng(0); ends = {}
    for g in ("no lie", "other lie", "laundering lie"):
        Dg = D[D.grp == g]; mean, lo, hi = [], [], []
        for x in xs:
            v = Dg[x].dropna().values
            if len(v) < 10:
                mean.append(np.nan); lo.append(np.nan); hi.append(np.nan); continue
            bs = [v[rng.integers(0, len(v), len(v))].mean() for _ in range(1000)]
            mean.append(v.mean()); lo.append(np.percentile(bs, 2.5)); hi.append(np.percentile(bs, 97.5))
        ax.fill_between(xi, lo, hi, color=col[g], alpha=0.18, lw=0); ax.plot(xi, mean, "-o", color=col[g], ms=3.2, lw=1.5)
        ends[g] = (mean[-1], len(Dg))
    lab_y = sorted(ends.items(), key=lambda kv: kv[1][0]); ylo, yhi = ax.get_ylim(); gapy = (yhi - ylo) * 0.13; last = -1e9
    for g, (y, n) in lab_y:
        yy = max(y, last + gapy); last = yy
        ax.annotate(f"{g} (n={n})", (xi[-1], y), xytext=(xi[-1] + 0.25, yy), fontsize=6.2, color=INK, va="center",
                    arrowprops=dict(arrowstyle="-", color=col[g], lw=0.6))
    aucs = {}
    for x in ("V", "report"):
        d = D.dropna(subset=[x]); aucs[x] = float(X95.strat_auc(d.y.values, d[x].values, (d.model + "|" + d.template).values))
    ax.axvline(3, color=MUTED, lw=0.6, ls=":"); ax.axvline(7, color=MUTED, lw=0.6, ls=":")
    ax.text(3, 1.0, f"violation\nAUROC {aucs['V']:.2f}", transform=ax.get_xaxis_transform(), ha="center", va="bottom", fontsize=6.2, color=INK)
    ax.text(7, 1.0, f"before report\nAUROC {aucs['report']:.2f}", transform=ax.get_xaxis_transform(), ha="center", va="bottom", fontsize=6.2, color=INK)
    ax.set_xticks(xi); ax.set_xticklabels(["$-3$", "$-2$", "$-1$", "V", "$+1$", "$+2$", "$+3$", "pre-\nreport"])
    ax.set_xlabel("agent action, relative to the unauthorized action V"); ax.set_ylabel("internal lie score (z)")
    ax.set_xlim(-0.3, 9.3); ax.set_title("(a) A laundering lie appears inside just before it is written", loc="left", pad=20)
    return {"n": int(len(D)), "group_n": D.grp.value_counts().to_dict(), "auroc_at_violation": aucs["V"], "auroc_pre_report": aucs["report"]}


def main():
    have = all(os.path.exists(f"{R}/fig1_traj_{m}.parquet") for m in ("gemma4", "gptoss20b", "museglimmer"))
    if have:
        fig = plt.figure(figsize=(6.85, 5.6)); gs = fig.add_gridspec(2, 1, height_ratios=[1, 1.08], hspace=0.5)
        top = gs[0].subgridspec(1, 2, width_ratios=[2.15, 1.1], wspace=0.38); bot = gs[1].subgridspec(1, 3, width_ratios=[1.0, 0.28, 1.75], wspace=0.0)
        a0 = fig.add_subplot(top[0]); a, b, c = fig.add_subplot(top[1]), fig.add_subplot(bot[0]), fig.add_subplot(bot[2])
        stats = {"traj": panel_traj(a0)}
        for ax_, lab in ((a, "(b)"), (b, "(c)"), (c, "(d)")):
            pass
        stats.update({"a": panel_a(a), "b": panel_b(b, fig), "c": panel_c(c)})
        for ax_, old_, new_ in ((a, "(a)", "(b)"), (b, "(b)", "(c)"), (c, "(c)", "(d)")):
            ax_.set_title(ax_.get_title(loc="left").replace(old_, new_, 1), loc="left")
    else:
        fig = plt.figure(figsize=(6.85, 2.75)); gs = fig.add_gridspec(1, 3, width_ratios=[1.12, 1.0, 1.1], wspace=0.42)
        a, b, c = (fig.add_subplot(gs[0, i]) for i in range(3))
        stats = {"a": panel_a(a), "b": panel_b(b, fig), "c": panel_c(c)}
    fig.savefig(f"{OUT}/fig1_internals.pdf"); fig.savefig(f"{OUT}/fig1_internals.png", dpi=220)
    json.dump(stats, open(f"{OUT}/fig1_internals_stats.json", "w"), indent=1, default=str); print(json.dumps(stats, indent=1, default=str))


if __name__ == "__main__":
    main()
