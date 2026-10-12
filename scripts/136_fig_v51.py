#!/usr/bin/env python3
"""Paper Figure 6: forecasting the lie on fresh episodes, every frozen forecaster.
Reads results/unified_compare.json (scripts/142; Qwen, Gemma, gpt-oss, where the v52 ensemble exists) and results/prereg_v51/summary.json
(Muse, which has no ensemble because its fresh sets were examined before v52).
(a) Per model and pooled: internal ensemble (ours, v52), single-recipe internal (v51), supervised text, zero-shot CoT and action monitors.
(b) CoT-obfuscation episodes (three models): the same forecasters.
Palette: Okabe-Ito, validated with scripts/validate_palette.py. Output paper/figures/fig6_cotmon.{pdf,png}"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = "/home/arya/new_safety/cape"; OUT = os.environ.get("FIG_OUT", f"{ROOT}/paper/figures")
plt.rcParams.update({"font.family": "serif", "font.serif": ["STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix", "font.size": 8,
                     "axes.titlesize": 8.5, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 6.6,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6, "pdf.fonttype": 42,
                     "savefig.bbox": "tight", "savefig.pad_inches": 0.02})
KEYS = ["E_lda", "I", "T_sup", "M_cot", "M_act"]
COL = {"E_lda": "#0072B2", "I": "#56B4E9", "T_sup": "#E69F00", "M_cot": "#D55E00", "M_act": "#CC79A7"}
NAME = {"E_lda": "internal ensemble (ours)", "I": "internal, single readout", "T_sup": "supervised text classifier",
        "M_cot": "zero-shot CoT monitor", "M_act": "zero-shot action monitor"}
MN = {"qwen38": "Qwen3.8", "museglimmer": "Muse$^{*}$", "gemma4": "Gemma-4", "gptoss20b": "gpt-oss"}


def bars(ax, groups, data, w=0.16):
    for gi, g in enumerate(groups):
        for ki, k in enumerate(KEYS):
            v = data[g].get(k)
            if v is None:
                continue
            x = gi + (ki - 2) * w
            ax.bar(x, v - 0.5, w * 0.92, bottom=0.5, color=COL[k], edgecolor="white", lw=0.4)
            if k == "E_lda" or g == "pooled":
                ax.text(x, v + 0.01, f"{v:.2f}", ha="center", fontsize=5.4, rotation=90, color="#222")
    ax.axhline(0.5, color="#6B6B6B", lw=0.6, ls=":")


def main():
    U = json.load(open(f"{ROOT}/results/unified_compare.json")); V = json.load(open(f"{ROOT}/results/prereg_v51/summary.json"))
    data = {m: U["per_model"][m] for m in ("qwen38", "gemma4", "gptoss20b")}
    data["museglimmer"] = {k: V["C4_per_model"]["museglimmer"][k] for k in ("I", "T_sup", "M_cot", "M_act")}
    data["pooled"] = U["pooled"]
    groups = ["qwen38", "gemma4", "gptoss20b", "museglimmer", "pooled"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(6.85, 2.45), gridspec_kw={"width_ratios": [2.5, 1], "wspace": 0.25})
    bars(a, groups, data)
    a.set_xticks(range(len(groups))); a.set_xticklabels([MN.get(g, "pooled\n(3 models)") for g in groups])
    a.axvline(3.5, color="#BBBBBB", lw=0.6); a.set_ylim(0.4, 1.0); a.set_ylabel("within-template AUROC (fresh)")
    em = U["E_minus"]
    a.set_title("(a) Forecasting the lie before the report (fresh episodes)", loc="left", pad=27)
    a.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=COL[k], label=NAME[k]) for k in KEYS], frameon=False, ncol=3,
             loc="upper center", bbox_to_anchor=(0.5, 1.17), fontsize=6.2)
    ob = U["obfuscate"]["pooled"]
    for i, k in enumerate(KEYS):
        b.bar(i, ob[k] - 0.5, 0.7, bottom=0.5, color=COL[k], edgecolor="white", lw=0.4); b.text(i, ob[k] + 0.01, f"{ob[k]:.2f}", ha="center", fontsize=6)
    b.axhline(0.5, color="#6B6B6B", lw=0.6, ls=":"); b.set_ylim(0.4, 1.0); b.set_xticks([])
    d = U["obfuscate"]["E_minus_Mcot"]
    b.set_title("(b) CoT pressured to hide (same forecasters)", loc="left", pad=27)
    fig.savefig(f"{OUT}/fig6_cotmon.pdf"); fig.savefig(f"{OUT}/fig6_cotmon.png", dpi=220); print("figure written")


if __name__ == "__main__":
    main()
