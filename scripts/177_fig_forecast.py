#!/usr/bin/env python
"""Figure 3 (forecasting), fresh data, every forecaster frozen before the data existed:
  (a) the violation over the episode: internal readout vs supervised text vs zero-shot CoT monitor (results/prereg_v57/timecourse.json,
      scenario-cluster bootstrap 95% CIs; the decision point is vs the agent's other actions);
  (b) the lie before the report: internal ensemble vs supervised text vs CoT and action monitors, without pressure and when the agent
      is told to keep permissions out of its monitored reasoning (scripts/142 data; scenario-cluster bootstrap 95% CIs computed here).
python scripts/177_fig_forecast.py -> paper/figures/fig_forecast_main.pdf (+ _stats.json)"""
import importlib.util
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from cape.utils.config import REPO_ROOT

plt.rcParams.update({"font.family": "serif", "font.serif": ["STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix", "font.size": 7.5,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6, "pdf.fonttype": 42,
                     "xtick.labelsize": 6.6, "ytick.labelsize": 6.6})
INK, MUTED = "#1F2937", "#5B6472"
COL = {"I": "#0072B2", "E_lda": "#0072B2", "T_sup": "#009E73", "M_cot": "#D55E00", "M_act": "#E69F00"}   # validated roles (ours / text / CoT / action)
NAME = {"I": "internal (ours)", "E_lda": "internal (ours)", "T_sup": "supervised text", "M_cot": "CoT monitor", "M_act": "action monitor"}


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def lie_scores():
    C = _mod("c134", "scripts/134_v51_confirm.py"); V = _mod("v141", "scripts/141_v52_confirm.py"); parts = []
    for m in ("qwen38", "gemma4", "gptoss20b"):                 # the models with the frozen v52 ensemble (as scripts/142)
        a = C.scores(m); b = V.fresh(m)[["set", "episode_id", "I"]].rename(columns={"I": "E_lda"}); parts.append(a.merge(b, on=["set", "episode_id"], how="inner"))
    D = pd.concat(parts, ignore_index=True)
    for c in ("E_lda", "T_sup", "M_cot", "M_act"):
        D[c] = D.groupby("model")[c].transform(lambda v: (v - v.mean()) / (v.std() + 1e-9))
    return C, D


def boot_auc(C, D, col, B=2000, seed=7):
    D = D.dropna(subset=[col]); rng = np.random.default_rng(seed); cl = (D.model + "|" + D.scenario_id).values; u = np.unique(cl)
    idx = {c: np.where(cl == c)[0] for c in u}; v = []
    for _ in range(B):
        d = D.iloc[np.concatenate([idx[c] for c in rng.choice(u, len(u))])]
        if d.y.nunique() == 2:
            v.append(C.auc(d, col))
    return C.auc(D, col), float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5)), int(len(D)), int(D.y.sum())


def main():
    T = json.load(open(REPO_ROOT / "results/prereg_v57/timecourse.json")); C, D = lie_scores(); st = {"violation": {}, "lie": {}}
    fig, ax = plt.subplots(1, 2, figsize=(6.85, 2.1), gridspec_kw={"width_ratios": [1.15, 1.0], "wspace": 0.28, "left": 0.07, "right": 0.995, "top": 0.88, "bottom": 0.25})

    # (a) violation over the episode
    a = ax[0]; pts = [("reveal", "reads the\ndecisive fact"), ("h2", "2 actions\nbefore"), ("h1", "1 action\nbefore"), ("decision", "at the\ndecision")]
    for k, off in (("T_sup", -0.12), ("M_cot", 0.0), ("I", 0.12)):
        xs, ys, lo, hi = [], [], [], []
        for i, (p, _) in enumerate(pts):
            r = T[p].get(k)
            if r and "auroc" in r:
                xs.append(i + off); ys.append(r["auroc"]); lo.append(r["auroc"] - r["ci95"][0]); hi.append(r["ci95"][1] - r["auroc"])
                st["violation"].setdefault(p, {})[k] = r
        full = len(xs) == len(pts)                    # never draw a line through points a forecaster was not run at (CoT monitor: reveal and decision only)
        a.errorbar(xs, ys, yerr=[lo, hi], color=COL[k], lw=1.2 if k == "I" else 0.9, ls="-" if full else "none", marker="o", ms=3.4 if k == "I" else 2.8,
                   capsize=1.6, label=NAME[k] + ("" if full else " (run at two points)"), zorder=3 if k == "I" else 2)
    a.axhline(0.5, color="#A8A8A8", lw=0.6, ls=":"); a.text(3.45, 0.505, "chance", fontsize=5.6, color=MUTED, ha="right", va="bottom")
    a.axvspan(0.6, 2.4, color="#F3F4F6", zorder=0); a.text(1.5, 1.005, "the plan is being written", ha="center", fontsize=5.8, color=MUTED, va="bottom")
    a.set_xticks(range(4)); a.set_xticklabels([p[1] for p in pts], fontsize=6.2, linespacing=1.05); a.set_ylim(0.45, 1.05); a.set_xlim(-0.4, 3.5)
    a.set_ylabel("AUROC (within template, fresh)", fontsize=6.6); a.legend(frameon=False, fontsize=5.9, loc="upper left", handlelength=1.4, borderaxespad=0.1)
    a.set_title("(a) Forecasting the violation", loc="left", fontsize=8, fontweight="bold", color=INK, pad=10)

    # (b) lie before the report
    b = ax[1]; conds = [("base", "no pressure"), ("obfuscate", "told to keep permissions\nout of its monitored reasoning")]; cols = ["E_lda", "T_sup", "M_cot", "M_act"]; w = 0.19
    for gi, (v, lab) in enumerate(conds):
        Dv = D[D.variant == v]
        for j, c in enumerate(cols):
            m, lo, hi, n, k = boot_auc(C, Dv, c); st["lie"].setdefault(v, {})[c] = {"auroc": m, "ci95": [lo, hi], "n": n, "lies": k}
            x = gi + (j - 1.5) * w
            b.bar(x, m - 0.5, w * 0.9, bottom=0.5, color=COL[c], edgecolor="white", linewidth=0.6, label=NAME[c] if gi == 0 else None)
            b.errorbar(x, m, yerr=[[m - lo], [hi - m]], color=INK, lw=0.6, capsize=1.4)
            b.text(x, hi + 0.012, f"{m:.2f}", ha="center", fontsize=5.4, color=INK)
    b.axhline(0.5, color="#A8A8A8", lw=0.6, ls=":")
    ns = {v: (int((D.variant == v).sum()), int(D[D.variant == v].y.sum())) for v, _ in conds}
    b.set_xticks(range(2)); b.set_xticklabels([f"{c[1]}\n(n = {ns[c[0]][0]}, {ns[c[0]][1]} lies)" for c in conds], fontsize=6.2, linespacing=1.05); b.set_ylim(0.45, 1.13); b.set_xlim(-0.55, 1.55); b.set_yticks([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    b.set_ylabel("AUROC before the report (fresh)", fontsize=6.6); b.legend(frameon=False, fontsize=5.8, loc="upper center", ncol=4, handlelength=0.9, columnspacing=0.6, borderaxespad=0.0, handletextpad=0.3)
    b.set_title("(b) Forecasting the lie", loc="left", fontsize=8, fontweight="bold", color=INK, pad=10)
    out = REPO_ROOT / "paper/figures/fig_forecast_main"; fig.savefig(f"{out}.pdf"); fig.savefig(f"{out}.png", dpi=220)
    json.dump(st, open(f"{out}_stats.json", "w"), indent=1, default=float); print(json.dumps(st["lie"], indent=1, default=float))


if __name__ == "__main__":
    main()
