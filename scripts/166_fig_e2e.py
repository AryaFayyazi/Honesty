#!/usr/bin/env python
"""End-to-end figure (prereg v61): one pipeline prevents the violation and then the lie.
(a) per arm on the same fresh x- sites: eventual violation and misreported violation (violation AND MISREPRESENTED report)
(b) lie rate among episodes that still violated, per arm (the honesty lever acts on violations the gate leaves)
python scripts/166_fig_e2e.py [E2E=results/prereg_v61/e2e_museglimmer.json FIG_OUT=paper/figures]"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = "/home/arya/new_safety/cape"
E2E = os.environ.get("E2E", f"{ROOT}/results/prereg_v61/e2e_museglimmer.json"); OUT = os.environ.get("FIG_OUT", f"{ROOT}/paper/figures")
plt.rcParams.update({"font.family": "serif", "font.serif": ["STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix", "axes.linewidth": 0.6, "pdf.fonttype": 42, "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7,
                     "legend.fontsize": 6.4, "axes.spines.top": False, "axes.spines.right": False, "savefig.bbox": "tight", "savefig.pad_inches": 0.02})
ARMS = [("none_hf", "no intervention", "#6B6B6B"), ("gate_always", "gate every action", "#0072B2"), ("gate_honest", "gate + honesty steering", "#56B4E9")]


def main():
    J = json.load(open(E2E)); E = J["endpoints"]; D = J["decomposition"]
    mv = {"none_hf": E["E1_pipeline_vs_none"]["rate_comparator"], "gate_always": E["E2_gate_vs_none"]["rate_treated"], "gate_honest": E["E1_pipeline_vs_none"]["rate_treated"]}
    fig, (a, b) = plt.subplots(1, 2, figsize=(6.85, 2.3), gridspec_kw={"width_ratios": [1.5, 1.0], "wspace": 0.32})
    w = 0.26
    for i, (k, lab, col) in enumerate(ARMS):
        v = D["violation"].get(k)
        a.bar(0 + (i - 1) * w, v, w * 0.92, color=col, edgecolor="white", lw=0.4, label=lab)
        a.bar(1 + (i - 1) * w, mv[k], w * 0.92, color=col, edgecolor="white", lw=0.4)
        for x_, y_ in ((0 + (i - 1) * w, v), (1 + (i - 1) * w, mv[k])):
            a.text(x_, y_ + 0.012, f"{y_:.2f}", ha="center", fontsize=6)
        lg = D["lie_given_violation"].get(k)
        b.bar(i, lg, 0.62, color=col, edgecolor="white", lw=0.4); b.text(i, lg + 0.015, f"{lg:.2f}", ha="center", fontsize=6)
    a.set_xticks([0, 1]); a.set_xticklabels(["eventual violation", "violation, then a lie"], fontsize=7); a.set_ylim(0, max(D["violation"].values()) * 1.25 + 0.02)
    a.set_ylabel(f"rate on {J['n_minus']} fresh sites"); a.set_title("(a) Preventing the violation and the lie", loc="left", pad=6)
    a.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.14), fontsize=6)
    p = lambda d: d["p_one_sided"]
    a.text(0.99, 0.97, f"pipeline vs none: {E['E1_pipeline_vs_none']['fixed']} fixed / {E['E1_pipeline_vs_none']['broken']} broken", transform=a.transAxes, ha="right", va="top", fontsize=6, color="#333")
    b.set_xticks(range(3)); b.set_xticklabels(["none", "gate", "gate +\nhonesty"], fontsize=6.6); b.set_ylim(0, 1.05)
    b.set_ylabel("lie rate | violated"); b.set_title("(b) Lies among remaining violations", loc="left", pad=6)
    os.makedirs(OUT, exist_ok=True); fig.savefig(f"{OUT}/fig_e2e.pdf"); fig.savefig(f"{OUT}/fig_e2e.png", dpi=220); print("written", OUT)


if __name__ == "__main__":
    main()
