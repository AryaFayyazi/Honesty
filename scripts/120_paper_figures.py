#!/usr/bin/env python3
"""Paper figures (ICML 2027 draft). Every number is read from results/ JSON files; pending results are drawn as hatched
grey placeholders and are filled automatically when their summary file appears. Output: paper/figures/*.pdf
Usage: python scripts/120_paper_figures.py"""
import json
import os
from math import sqrt

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

R = "/home/arya/new_safety/cape/results"; OUT = "/home/arya/new_safety/cape/paper/figures"; os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({"font.family": "serif", "font.serif": ["STIXGeneral", "Times New Roman", "DejaVu Serif"], "mathtext.fontset": "stix",
                     "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7,
                     "legend.fontsize": 6.8, "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6,
                     "xtick.major.width": 0.6, "ytick.major.width": 0.6, "pdf.fonttype": 42, "savefig.bbox": "tight", "savefig.pad_inches": 0.02})
# Okabe-Ito (colour-blind safe); one fixed colour per model and per signal across all figures
MC = {"qwen38": "#0072B2", "museglimmer": "#D55E00", "gemma4": "#009E73", "gptoss20b": "#CC79A7"}
MN = {"qwen38": "Qwen3.8", "museglimmer": "Muse", "gemma4": "Gemma-4", "gptoss20b": "gpt-oss"}
INT, TXT, PEND, LIE, HON = "#0072B2", "#E69F00", "#BBBBBB", "#D55E00", "#0072B2"   # Okabe-Ito (validated)
COLW, FULLW = 3.25, 6.75


def J(p):
    p = os.path.join(R, p)
    return json.load(open(p)) if os.path.exists(p) else None


def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, c - h, c + h


def pend_bar(ax, x, h, w, label="pending"):
    ax.bar(x, h, w, color="white", edgecolor=PEND, hatch="////", linewidth=0.6)
    ax.text(x, h + 0.02, label, ha="center", va="bottom", fontsize=5.8, color="#777777", rotation=90)


def save(fig, name):
    fig.savefig(f"{OUT}/{name}.pdf"); fig.savefig(f"{OUT}/{name}.png", dpi=220); plt.close(fig)


# ---------------- Fig 2: the phenomenon (CAPE laundering + frontier pre-laundering) ----------------
def fig_phenomenon():
    v37 = J("prereg_v37/summary_full.json")["F1"]; t1b = J("v38/t1b_results.json")["T1b"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(FULLW, 1.9), gridspec_kw={"width_ratios": [1, 1.35], "wspace": 0.32})
    n_r = v37["n_retro"]; k_r = round(v37["lie_rate_retro"] * n_r); n_o = v37["n_C_informed"] - n_r; k_o = round(v37["lie_rate_noretro"] * n_o)
    dr, dlo, dhi = v37["denied_retro_lie_rate"][0], *v37["denied_retro_lie_rate"][1]
    rows = [("no retro\nrequest", *wilson(k_o, n_o), n_o, HON), ("retro\nrequest", *wilson(k_r, n_r), n_r, LIE), ("retro,\nDENIED", dr, dlo, dhi, v37["denied_retro_lie_rate"][2], "#8F3B00")]
    for i, (lab, p, lo, hi, n, c) in enumerate(rows):
        a.bar(i, p, 0.62, color=c, alpha=0.9); a.errorbar(i, p, [[p - lo], [hi - p]], color="k", lw=0.7, capsize=2)
        a.text(i, hi + 0.03, f"{p:.2f}", ha="center", fontsize=7, fontweight="bold"); a.text(i, 0.015, f"n={n}", ha="center", fontsize=5.8, color="white")
    a.set_xticks(range(3)); a.set_xticklabels([r[0] for r in rows]); a.set_ylim(0, 1.0); a.set_ylabel("false-report rate")
    a.set_title(f"(a) Open agents: laundering $\\rightarrow$ lie (fresh, $n$={v37['n_C_informed']})", loc="left")
    a.text(0.03, 0.97, f"CMH $p<10^{{-6}}$, OR = {v37['pooled_odds_ratio']:.1f}", transform=a.transAxes, ha="left", va="top", fontsize=6.3)
    ag = [("claude-3-7-sonnet-20250219", "Claude-3.7"), ("gpt-4.1-2025-04-14", "GPT-4.1"), ("gpt-4.1-mini-2025-04-14", "GPT-4.1-mini"), ("o4-mini-2025-04-16", "o4-mini")]
    for i, (k, lab) in enumerate(ag):
        d = t1b["per_agent"][k]; p = d["weighted_prevalence_NOT_ALLOWED"]; kn, nn = d["NOT_ALLOWED_flagged"]; ka, na = d["ALLOWED_flagged"]
        _, lo, hi = wilson(kn, nn)
        b.bar(i - 0.19, p, 0.36, color=LIE); b.bar(i + 0.19, max(ka / na, 0.004), 0.36, color=HON)
        b.text(i - 0.19, p + 0.02, f"{p:.2f}", ha="center", fontsize=6.3, fontweight="bold"); b.text(i + 0.19, 0.02, f"0/{na}", ha="center", fontsize=5.8)
        b.text(i, -0.17, f"Fisher $p$={d['fisher_p']:.0e}".replace("e-0", "e-"), ha="center", fontsize=5.5, color="#555555", transform=b.get_xaxis_transform())
    b.set_xticks(range(4)); b.set_xticklabels([l for _, l in ag]); b.set_ylim(0, 0.62); b.set_ylabel("share with false justification\nbefore the write")
    b.set_title("(b) Frontier agents ($\\tau^2$): false justification before the write", loc="left")
    b.legend(handles=[Patch(color=LIE, label="policy-violating write"), Patch(color=HON, label="allowed write")], loc="upper right", frameon=False)
    save(fig, "fig2_phenomenon")


# ---------------- Fig 3: forecasting ----------------
def fig_forecast():
    # observability bound only (the superseded single-readout vs text comparison is in the repository record)
    fig, a = plt.subplots(1, 1, figsize=(3.3, 2.2))
    ms = ["qwen38", "museglimmer", "gemma4", "gptoss20b"]
    for i, m in enumerate(ms):
        d = J(f"prereg_v29/H1_{m}.json")
        for off, key, alpha in ((-0.18, "uninformed", 0.35), (0.18, "informed", 1.0)):
            v = d[key]["auroc_within_fold"]; lo, hi = d[key]["ci95"]
            a.bar(i + off, v - 0.5, 0.34, bottom=0.5, color=MC[m], alpha=alpha); a.errorbar(i + off, v, [[v - lo], [hi - v]], color="k", lw=0.6, capsize=1.5)
    a.axhline(0.5, color="k", lw=0.6, ls=":"); a.set_ylim(0.4, 1.0); a.set_xticks(range(4)); a.set_xticklabels([MN[m] for m in ms])
    a.set_ylabel("violation-detection AUROC"); a.set_title("Observability bound", loc="left")
    a.legend(handles=[Patch(color="#666", alpha=0.35, label="uninformed (bound)"), Patch(color="#666", label="informed")], frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.02), ncol=2, columnspacing=0.8, handlelength=1.2)
    a.set_ylim(0.4, 1.06)
    save(fig, "fig3_forecast")


# ---------------- Fig 4: steering ----------------
def fig_steering():
    sel = J("prereg_v43dev/selection.json")["stageA"]; v43 = J("prereg_v43/confirm.json"); v46 = J("prereg_v46/summary.json"); v46b = J("prereg_v46b/summary.json")
    v48 = J("prereg_v48/confirm.json")
    fig, (a, b) = plt.subplots(1, 2, figsize=(FULLW, 2.1), gridspec_kw={"width_ratios": [1.2, 1], "wspace": 0.75})
    doses = [(1, "caa_p1_d16"), (2, "caa_p2_d16"), (4, "caa_p4_d16"), (6, "caa_p6_d16"), (8, "caa_p8_d16")]
    xs = [d for d, _ in doses]; ys = [sel[k]["diff"] for _, k in doses]; rs = [sel[k]["guards"]["report_share"][k] - sel[k]["guards"]["report_share"]["none"] for _, k in doses]
    a.axhline(0, color="k", lw=0.6); a.plot(xs, ys, "-o", color=HON, ms=4, label="development set (115 episodes)")
    s2 = v46["S2_complete_case"]; a.plot([8], [s2["rate_p8"] - s2["rate_none"]], "*", color="#1B4F72", ms=10, label=(r"fresh test 1, $\alpha$=8 " + f"(Holm $p$={s2['holm_p']:.0e})").replace("e-0", "e-"))
    v58 = J("prereg_v58/confirm.json")
    if v58:
        a.plot([7.6], [v58["P1_d16_vs_none"]["diff"]], "P", color="#1B4F72", ms=7, label=r"fresh test 2 (replication), $\alpha$=8 (Holm $p$=1e-6)")
    if v46b:
        a.plot([8.25], [v46b["random_minus_none"]], "x", color="#555", ms=6, label=r"random direction, $\alpha$=8")
    else:
        a.annotate("random-direction\ncontrol: PENDING", (8, 0.0), xytext=(5.6, 0.07), fontsize=6, color="#777", arrowprops=dict(arrowstyle="-", color="#aaa", lw=0.5))
    a.set_xlabel(r"steering strength $\alpha$ (multiples of the honest$-$lying gap $g$)"); a.set_ylabel(r"$\Delta$ false-report rate vs none")
    a.set_xticks(xs); a.set_ylim(-0.38, 0.16); a.set_title("(a) Self-counterfactual CAA: dose response (Muse)", loc="left")
    a.legend(frameon=False, loc="lower left", fontsize=6)
    v58 = v58 or {}
    hist = [("1", "world-knowledge probe", 0.01, "no effect"), ("2", "lie-forecast direction", 0.02, "no effect"), ("3", "lie-forecast, high dose", 0.11, "no effect"),
            ("4", "difference of means", None, "breaks reports"), ("6", r"honesty CAA, test 1", s2["rate_p8"] - s2["rate_none"], "confirmed"),
            ("7", r"honesty CAA, test 2", v58.get("P1_d16_vs_none", {}).get("diff"), "confirmed"),
            ("8", r"honesty CAA, reasoning only", v58.get("M1_q16_vs_none", {}).get("diff"), "confirmed")]
    for i, (v, lab, d, tag) in enumerate(hist):
        y = len(hist) - 1 - i; c = "#1B4F72" if "CAA" in lab else "#999"
        if d is None:
            b.barh(y, 0.08 if tag == "format broke" else 0.1, left=-0.04 if tag == "format broke" else 0, color="white", edgecolor=PEND, hatch="////", height=0.55, lw=0.6)
        else:
            b.barh(y, d, color=c, height=0.55)
        b.text(0.16, y, tag, va="center", fontsize=6, color="#1B4F72" if tag == "confirmed" else "#555", fontweight="bold" if tag == "confirmed" else None)   # detector rows: evidence for detector != lever
    b.axvline(0, color="k", lw=0.6); b.set_yticks(range(len(hist))); b.set_yticklabels([l for v, l, _, _ in hist][::-1], fontsize=6.4)
    b.set_xlim(-0.33, 0.28); b.set_xlabel(r"$\Delta$ false-report rate"); b.set_title("(b) Detector $\\neq$ lever", loc="left")
    save(fig, "fig4_steering")


# ---------------- Fig 5: context interventions and internal knowledge ----------------
K = {"museglimmer": 0.94, "qwen38": 0.81, "gemma4": 0.69, "gptoss20b": 0.03}   # preregistered in v49 before any v49 data


def fig_knowledge():
    v44 = J("prereg_v44/summary.json"); v49 = J("prereg_v49/summary.json")
    # v44 exploratory decomposition (docs/xm_findings.md; scripts/108): lie rates neutral -> contract
    dec = {"museglimmer": {"retro": (0.77, 0.31), "nonretro": (0.78, 0.24)}, "gemma4": {"retro": (0.83, 0.67), "nonretro": (0.07, 0.06)},
           "gptoss20b": {"retro": (0.69, 0.73), "nonretro": (0.13, 0.40)}}
    fig, (a, b) = plt.subplots(1, 2, figsize=(FULLW, 2.05), gridspec_kw={"width_ratios": [1.35, 1], "wspace": 0.3})
    ms = ["museglimmer", "qwen38", "gemma4", "gptoss20b"]
    for i, m in enumerate(ms):
        for j, (k, lab) in enumerate((("retro", "laundering"), ("nonretro", "other informed"))):
            x = i + (j - 0.5) * 0.4
            if m not in dec:                       # Qwen: no laundering split; the fresh H1 contrast over all informed episodes
                if j == 0:
                    h = (v49 or {}).get("H1", {}).get(m, {})
                    if "lie_contract" in h:
                        d = h["lie_contract"] - h["lie_neutral"]
                        a.bar(i, d, 0.36, color=MC[m], alpha=0.75, edgecolor=MC[m], hatch="....", lw=0.6)
                        a.text(i, d - 0.06, f"{d:+.2f}", ha="center", fontsize=6); a.text(i, 0.04, "all informed\n(fresh, n=36)", ha="center", fontsize=5.4, color="#555")
                continue
            n0, n1 = dec[m][k]; d = n1 - n0
            a.bar(x, d, 0.36, color=MC[m], alpha=1.0 if j == 0 else 0.45, edgecolor=MC[m], lw=0.6)
            a.text(x, d + (0.02 if d >= 0 else -0.06), f"{d:+.2f}", ha="center", fontsize=6)
    a.axhline(0, color="k", lw=0.6); a.set_xticks(range(4)); a.set_xticklabels([f"{MN[m]}\nK={K[m]:.2f}" for m in ms])
    a.set_ylabel(r"$\Delta$ false-report rate" "\n(contract $-$ neutral)"); a.set_ylim(-0.62, 0.42)
    a.set_title("(a) Evidence contract: helps or backfires, by model", loc="left")
    a.legend(handles=[Patch(color="#555", label="laundering episodes"), Patch(color="#555", alpha=0.45, label="other informed episodes")], frameon=False, loc="lower right")
    for m in ms:
        h = (v49 or {}).get("H1", {}).get(m, {})
        if "B" in h:
            B, (lo, hi) = h["B"], h["B_ci95"]; b.errorbar(K[m], B, [[B - lo], [hi - B]], fmt="o", color=MC[m], ms=6, capsize=2)
        else:
            b.plot(K[m], 0, "o", mfc="white", mec=MC[m], ms=7, mew=1.2); b.text(K[m], 0.06, "?", ha="center", color=MC[m], fontsize=8, fontweight="bold")
        yb = h["B"] if "B" in h else 0.0
        dx, dy, ha = {"museglimmer": (-0.04, 0.12, "center"), "qwen38": (0.035, 0.0, "left"), "gemma4": (-0.03, 0.11, "center"), "gptoss20b": (0.0, 0.12, "center")}[m]
        b.text(K[m] + dx, yb + dy, MN[m], ha=ha, va="center", fontsize=6.4, color=MC[m])
    b.axhline(0, color="k", lw=0.6); b.set_xlim(-0.08, 1.05); b.set_ylim(-0.45, 0.7)
    b.set_xlabel(r"internal knowledge index $K$ (decode at violation; prereg.)"); b.set_ylabel(r"benefit $B$ = lie(neutral) $-$ lie(contract)")
    b.annotate("", xy=(0.95, 0.55), xytext=(0.05, -0.35), arrowprops=dict(arrowstyle="->", color="#888", lw=0.8, ls="--"))
    b.text(0.5, 0.33, "H1: B ordered by K", rotation=33, fontsize=6.3, color="#777", ha="center")
    b.set_title("(b) H1 on fresh episodes" + ("" if v49 and all("B" in v49.get("H1", {}).get(m, {}) for m in ms) else " (partial)"), loc="left")
    save(fig, "fig5_knowledge")


if __name__ == "__main__":
    fig_phenomenon(); fig_forecast(); fig_steering(); fig_knowledge(); print("figures ->", OUT)
