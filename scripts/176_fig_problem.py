#!/usr/bin/env python
"""Figure 2 (the problem exists), all on fresh confirmation data, every rate with a Wilson 95% CI:
  (a) base rates per model: P(violate after reading the decisive fact) from the raw confirmation rollouts (the v55 split
      rule of scripts/147), and P(report misrepresents | informed violation) from the frozen rubric labels;
  (b) the laundering marker: lie rate after a post-hoc permission request vs otherwise (results/prereg_v37/f1_by_model.json);
  (c) frontier agents on tau2-bench: false justification before policy-violating vs allowed writes (results/v38/t1b_results.json).
python scripts/176_fig_problem.py -> paper/figures/fig2_problem.pdf (+ _stats.json)"""
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
GREY, BLUE, RED_STATE, INK, MUTED = "#A8A8A8", "#0072B2", "#B42318", "#1F2937", "#5B6472"
MN = {"gemma4": "Gemma", "gptoss20b": "gpt-oss", "museglimmer": "Muse", "qwen38": "Qwen"}
LIE_LABELS = {"CANDID", "OMITTED", "SPIN", "MISREPRESENTED"}   # per report (NO_REPORT excluded), as the laundering panel


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan, np.nan)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def base_rates():
    s = importlib.util.spec_from_file_location("p147", REPO_ROOT / "scripts/147_v55_sites.py"); P = importlib.util.module_from_spec(s); s.loader.exec_module(P)
    out = {}
    for A in MN:
        n_at_risk = n_viol = 0; lies = judged = 0
        for f in sorted((REPO_ROOT / "outputs/rollouts").glob(f"{P.PRE[A]}*minus*.parquet")):
            stem = f.stem[len(P.PRE[A]):]
            if P.PRE[A] == "" and f.stem.startswith(("xm_", "x_")):
                continue
            if P.split_of(A, stem) != "conf":
                continue
            R = pd.read_parquet(f); rv = pd.to_numeric(R.reveal_event, errors="coerce"); fu = pd.to_numeric(R.first_unsafe_event, errors="coerce")
            at_risk = (rv >= 0) & ~(fu <= rv)                 # saw the decisive fact before any violation
            n_at_risk += int(at_risk.sum()); n_viol += int((at_risk & (fu > rv)).sum())
            lf = REPO_ROOT / f"outputs/disclosure_v37/{f.stem}_rubric.parquet"
            if lf.exists():
                L = pd.read_parquet(lf); L = L[L.informed.astype(bool) & L.label.isin(LIE_LABELS)]
                lies += int((L.label == "MISREPRESENTED").sum()); judged += int(len(L))
        out[A] = {"violate_after_fact": (n_viol, n_at_risk), "lie_given_violation": (lies, judged)}
    return out


def main():
    B = base_rates(); F1 = json.load(open(REPO_ROOT / "results/prereg_v37/f1_by_model.json")); T = json.load(open(REPO_ROOT / "results/v38/t1b_results.json"))["T1b"]
    fig, ax = plt.subplots(1, 3, figsize=(6.85, 2.15), gridspec_kw={"width_ratios": [1.25, 1.05, 1.1], "wspace": 0.42, "left": 0.07, "right": 0.995, "top": 0.86, "bottom": 0.3})
    st = {"base_rates": {}, "laundering": {}, "frontier": {}}

    # (a) base rates
    a = ax[0]; w = 0.36
    for i, A in enumerate(MN):
        for dx, key, col, lab in ((-w / 2, "violate_after_fact", RED_STATE, "violates after reading the fact (per episode)"), (w / 2, "lie_given_violation", RED_STATE, "then misreports (per report)")):
            k, n = B[A][key]; p, lo, hi = wilson(k, n); st["base_rates"].setdefault(A, {})[key] = {"k": k, "n": n, "rate": p, "ci95": [lo, hi]}
            a.bar(i + dx, p, w * 0.9, color=col if key == "violate_after_fact" else "white", edgecolor=RED_STATE if key != "violate_after_fact" else "white",
                  hatch="//////" if key != "violate_after_fact" else None, alpha=0.85, linewidth=0.6, label=lab if i == 0 else None)   # identity by texture, not a second red
            a.errorbar(i + dx, p, yerr=[[p - lo], [hi - p]], color=INK, lw=0.6, capsize=1.6)
            a.text(i + dx, hi + 0.02, f"{p:.2f}", ha="center", fontsize=5.6, color=INK)
    a.set_xticks(range(4)); a.set_xticklabels(MN.values()); a.set_ylim(0, 1.05); a.set_ylabel("rate (fresh episodes)", fontsize=6.6)
    a.legend(frameon=False, fontsize=5.9, loc="upper left", handlelength=1.0, borderaxespad=0.1)
    a.set_title("(a) Agents violate, then misreport", loc="left", fontsize=8, fontweight="bold", color=INK, pad=4)

    # (b) laundering marker
    b = ax[1]; keys = [k for k in ("gemma4", "gptoss20b", "museglimmer") if k in F1] + ["pooled"]
    for i, A in enumerate(keys):
        for dx, kk, col, lab in ((-w / 2, "noretro", GREY, "no post-hoc request"), (w / 2, "retro", RED_STATE, "after a post-hoc request")):
            r = F1[A][kk]; p, lo, hi = r["rate"], r["wilson95"][0], r["wilson95"][1]; st["laundering"].setdefault(A, {})[kk] = r
            b.bar(i + dx, p, w * 0.9, color=col, edgecolor="white", linewidth=0.6, label=lab if i == 0 else None, alpha=0.85)
            b.errorbar(i + dx, p, yerr=[[p - lo], [hi - p]], color=INK, lw=0.6, capsize=1.6)
            his = [F1[A][q]["wilson95"][1] for q in ("noretro", "retro")]; close = abs(his[0] - his[1]) < 0.08   # stagger labels that would touch
            b.text(i + dx + (0.0 if not close else (0.06 if kk == "noretro" else -0.06)), hi + 0.02, f"{p:.2f}", ha="center" if not close else ("right" if kk == "noretro" else "left"), fontsize=5.6, color=INK)
    b.set_xticks(range(len(keys))); b.set_xticklabels([MN.get(k, "pooled") for k in keys]); b.set_ylim(0, 1.32); b.set_yticks([0, 0.25, 0.5, 0.75, 1.0]); b.set_ylabel("false report rate", fontsize=6.6)
    b.legend(frameon=False, fontsize=5.9, loc="upper left", handlelength=1.0, borderaxespad=0.1, ncol=1)
    b.set_title("(b) Asking afterwards marks the lie", loc="left", fontsize=8, fontweight="bold", color=INK, pad=4)

    # (c) frontier agents, tau2-bench
    c = ax[2]; ag = list(T["per_agent"]); short = {"claude-3-7-sonnet-20250219": "Claude\n3.7", "gpt-4.1-2025-04-14": "GPT-\n4.1", "gpt-4.1-mini-2025-04-14": "GPT-4.1\nmini", "o4-mini-2025-04-16": "o4-\nmini"}
    for i, g in enumerate(ag):
        for dx, kk, col, lab in ((-w / 2, "ALLOWED_flagged", GREY, "before an allowed write"), (w / 2, "NOT_ALLOWED_flagged", RED_STATE, "before a violating write")):
            k, n = T["per_agent"][g][kk]; p, lo, hi = wilson(k, n); st["frontier"].setdefault(g, {})[kk] = {"k": k, "n": n, "rate": p, "ci95": [lo, hi]}
            c.bar(i + dx, max(p, 0.004), w * 0.9, color=col, edgecolor="white", linewidth=0.6, label=lab if i == 0 else None, alpha=0.85)
            c.errorbar(i + dx, p, yerr=[[p - lo], [hi - p]], color=INK, lw=0.6, capsize=1.6)
            c.text(i + dx, hi + 0.02, f"{k}/{n}", ha="center", fontsize=5.2, color=INK)
    c.set_xticks(range(len(ag))); c.set_xticklabels([short[g] for g in ag], fontsize=6.0, linespacing=1.0); c.set_ylim(0, 0.75); c.set_yticks([0, 0.2, 0.4, 0.6]); c.set_ylabel("false justification to the customer", fontsize=6.4)
    c.legend(frameon=False, fontsize=5.9, loc="upper left", handlelength=1.0, borderaxespad=0.1)
    c.set_title("(c) Frontier agents (τ²-bench)", loc="left", fontsize=8, fontweight="bold", color=INK, pad=4)
    for x_, s_ in ((ax[0], "Raw confirmation rollouts (all prompt variants);\nmisreport = judged false report, per report."),
                   (ax[1], "1,081 fresh informed violations; preregistered\nstratified odds ratio 7.0 (CMH p < 1e-6)."),
                   (ax[2], "Published trajectories (894 writes): before 26%\nof violating writes, none of 667 allowed.")):
        x_.text(0.0, -0.24 if x_ is ax[2] else -0.2, s_, transform=x_.transAxes, fontsize=5.9, color=MUTED, va="top", linespacing=1.25)
    out = REPO_ROOT / "paper/figures/fig2_problem"; fig.savefig(f"{out}.pdf"); fig.savefig(f"{out}.png", dpi=220)
    json.dump(st, open(f"{out}_stats.json", "w"), indent=1, default=float); print(json.dumps(st["base_rates"], indent=1, default=float))


if __name__ == "__main__":
    main()
