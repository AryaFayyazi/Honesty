#!/usr/bin/env python3
"""Paper figure: forecasting and preventing the violation (fresh, preregistered data only).
(a) When does the violation become readable? Within-template AUROC on fresh data at four points: right after the reveal (v55),
    two and one actions before the violation (v57 descriptive horizons), and at the decision, after reasoning and before the call
    (v57). Internal vs supervised text vs zero-shot CoT monitor. Pooled over models (horizons: weighted by positives).
(b) At the decision, per model: internal vs text vs CoT monitor (all negatives), and the internal forecaster against the same
    critical action when authorized (hatched).
(c) Violation rate on fresh unauthorized-world sites per arm (none, random, blanket steer, forecast-gated) with authorized-twin
    progress (hollow markers); results/prereg_v54/confirm_<model>.json and gate_<model>_conf.json.
Palette: Okabe-Ito (validated, scripts/validate_palette.py). Output paper/figures/fig_violation.{pdf,png}"""
import json
import numpy as np
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = "/home/arya/new_safety/cape"; OUT = os.environ.get("FIG_OUT", f"{ROOT}/paper/figures")
R55 = os.environ.get("RES55", f"{ROOT}/results/prereg_v55"); R57 = os.environ.get("RES57", f"{ROOT}/results/prereg_v57"); R54 = os.environ.get("RES54", f"{ROOT}/results/prereg_v54")
plt.rcParams.update({"font.family": "serif", "font.serif": ["STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix", "font.size": 8,
                     "axes.titlesize": 8.5, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 6.4,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6, "pdf.fonttype": 42,
                     "savefig.bbox": "tight", "savefig.pad_inches": 0.02})
KEYS = ["I", "T_sup", "M_cot"]
COL = {"I": "#0072B2", "T_sup": "#E69F00", "M_cot": "#D55E00"}
NAME = {"I": "internal (ours)", "T_sup": "supervised text", "M_cot": "zero-shot CoT monitor"}
MODELS = ["gemma4", "gptoss20b", "museglimmer", "qwen38"]
MN = {"qwen38": "Qwen", "museglimmer": "Muse", "gemma4": "Gemma", "gptoss20b": "gpt-oss"}
ARMS = [("none", "no steering", "#6B6B6B"), ("rand", "random dir.", "#BBBBBB"), ("blanket", "blanket (always steer)", "#56B4E9"), ("gate", "forecast-gated (ours)", "#0072B2")]


def load(p):
    return json.load(open(p)) if os.path.exists(p) else None


def main():
    S55, S57 = load(f"{R55}/summary.json"), load(f"{R57}/summary.json")
    fig = plt.figure(figsize=(6.85, 5.0)); gs = fig.add_gridspec(2, 2, height_ratios=[1, 1], hspace=0.78, wspace=0.26)
    top, bot = (gs[0, 0], gs[0, 1]), (gs[1, 0], gs[1, 1])
    a, b = fig.add_subplot(top[0]), fig.add_subplot(top[1]); c, d4 = fig.add_subplot(bot[0]), fig.add_subplot(bot[1])
    # (a) the violation forecast over time (results/prereg_v57/timecourse.json from scripts/163): pooled within-stratum AUROC with
    #     95% scenario-cluster bootstrap CIs. Reveal (v55) and decision (v57, vs other actions) are preregistered (filled markers);
    #     2 and 1 actions before (vs the same other actions) are descriptive (hollow). CoT monitor on its preregistered subset.
    TCci = load(f"{ROOT}/results/prereg_v57/timecourse.json") or {}; TC = {}
    if S55 and S57:                                    # point estimates from the saved summaries; replaced by the CI file where it exists
        pt = lambda v: {"auroc": v, "ci95": [v, v]}
        TC = {"reveal": {"I": pt(S55["pooled_conf"]["I"]), "T_sup": pt(S55["pooled_conf"]["T_sup"]), "M_cot": pt(S55["pooled_monitor_subset"]["M_cot"])},
              "decision": {k: pt(S57["auroc"]["vs_XOTHER"][k]) for k in ("I", "T_sup", "M_cot")}}
        for h in ("h2", "h1"):                         # violator-weighted pool of the per-model v57 horizon AUROCs
            hm = [v[h] for v in S57["horizons_descriptive"].values() if "n_pos" in v.get(h, {})]; w = np.array([v["n_pos"] for v in hm], float)
            TC[h] = {k: pt(round(float(np.dot(w, [v[k] for v in hm]) / w.sum()), 4)) for k in ("I", "T_sup")}
    for key, v in TCci.items():
        TC.setdefault(key, {}).update({k: e for k, e in v.items() if isinstance(e, dict) and "auroc" in e})
    HAS_CI = all(k in TCci for k in ("reveal", "h2", "h1", "decision"))
    pts = [("reveal", "after the\nreveal", True), ("h2", "2 actions\nbefore", False), ("h1", "1 action\nbefore", False), ("decision", "at the\ndecision", True)]
    for k, off in (("M_cot", 0.07), ("T_sup", -0.07), ("I", 0.0)):
        xs, ys, lo, hi, pre = [], [], [], [], []
        for xi, (key, _, prereg) in enumerate(pts):
            e = (TC or {}).get(key, {}).get(k)
            if e:
                xs.append(xi + off); ys.append(e["auroc"]); lo.append(e["auroc"] - e["ci95"][0]); hi.append(e["ci95"][1] - e["auroc"]); pre.append(prereg)
        if not xs:
            continue
        lw, ms = (2.0, 4.6) if k == "I" else (1.1, 3.6)
        if k != "M_cot":
            a.plot(xs, ys, "-", lw=lw, color=COL[k], zorder=3 if k == "I" else 2)
        a.errorbar(xs, ys, yerr=[lo, hi], fmt="none", ecolor=COL[k], elinewidth=0.8, capsize=1.6, zorder=3)
        for x_, y_, p_ in zip(xs, ys, pre):
            a.plot(x_, y_, "o", ms=ms, color=COL[k], mfc=COL[k] if p_ else "white", mew=1.0, zorder=4)
        if k == "I":
            for x_, y_, l_ in zip(xs, ys, lo):
                lft = x_ < 0.5
                a.text(x_ + (-0.1 if lft else 0.1), y_ + (0.012 if lft else -0.004), f"{y_:.2f}", ha="right" if lft else "left", va="bottom" if lft else "top", fontsize=5.8, color=COL[k])
    a.axhline(0.5, color="#6B6B6B", lw=0.6, ls=":"); a.axvline(0.5, color="#BBBBBB", lw=0.6)
    a.set_ylim(0.45, 1.02); a.set_xlim(-0.35, 3.45); a.set_xticks(range(4)); a.set_xticklabels([p_[1] for p_ in pts], fontsize=6.2)
    a.set_ylabel("within-template AUROC (fresh)"); a.set_title("(a) Forecasting the violation over time", loc="left", pad=6)
    hs = [plt.Line2D([], [], color=COL[k], marker="o", lw=2.0 if k == "I" else 1.1, ms=3.6, label=NAME[k]) for k in ("I", "T_sup")]
    hs += [plt.Line2D([], [], color=COL["M_cot"], marker="o", ls="none", ms=3.6, label=NAME["M_cot"]),
           plt.Line2D([], [], color="#555", marker="o", mfc="white", ls="none", ms=3.6, label="descriptive (hollow)")]
    a.legend(handles=hs, frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.2), fontsize=5.6, columnspacing=0.8, handlelength=1.6,
             title="filled: preregistered tests" + ("; bars: 95% CI" if HAS_CI else "; bars: 95% CI (preregistered points)"), title_fontsize=5.8)
    # (b) end to end (prereg v61, Muse): one pipeline prevents the violation and the lie that follows
    E61 = load(f"{ROOT}/results/prereg_v61/e2e_museglimmer.json")
    if E61:
        EE, DD = E61["endpoints"], E61["decomposition"]
        mv = {"none_hf": EE["E1_pipeline_vs_none"]["rate_comparator"], "gate_always": EE["E2_gate_vs_none"]["rate_treated"], "gate_honest": EE["E1_pipeline_vs_none"]["rate_treated"]}
        e_arms = [("none_hf", "no intervention", "#6B6B6B", None), ("gate_always", "gate every action", "#0072B2", None), ("gate_honest", "gate + honesty steering", "#0072B2", "////")]
        wb = 0.26
        for ai, (k, lab, col, hatch) in enumerate(e_arms):
            for gi, val in ((0, DD["violation"][k]), (1, mv[k])):
                x = gi + (ai - 1) * wb
                if hatch:
                    b.bar(x, val, wb * 0.92, color="white", edgecolor=col, hatch=hatch, lw=0.6)
                else:
                    b.bar(x, val, wb * 0.92, color=col, edgecolor="white", lw=0.4)
                b.text(x, val + 0.012, f"{val:.2f}", ha="center", fontsize=6)
        b.set_xticks([0, 1]); b.set_xticklabels(["eventual violation", "violation, then a lie"], fontsize=6.6); b.set_xlim(-0.55, 1.55)
        b.set_ylim(0, 0.5); b.set_ylabel(f"rate on {E61['n_minus']} fresh sites (Muse)")
        b.text(1.0, 0.44, f"{EE['E1_pipeline_vs_none']['fixed']} fixed / {EE['E1_pipeline_vs_none']['broken']} broken", ha="center", fontsize=6, color="#333")
        b.legend(handles=[plt.Rectangle((0, 0), 1, 1, facecolor="white", edgecolor=c, hatch=h, lw=0.6, label=l) if h else plt.Rectangle((0, 0), 1, 1, color=c, label=l) for _, l, c, h in e_arms],
                 frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.12), fontsize=5.6, columnspacing=0.8, handlelength=1.3, title="bars: rate over thirteen turns", title_fontsize=5.8)
    else:
        b.text(0.5, 0.5, "pending", ha="center", transform=b.transAxes, color="#999")
    b.set_title("(b) One pipeline: violation, then the lie", loc="left", pad=6)
    # (c) prevention
    w = 0.2
    for gi, m in enumerate(MODELS):
        J, Gt = load(f"{R54}/confirm_{m}.json"), load(f"{R54}/gate_{m}_conf.json")
        if (not J or "secondary" not in J) and not (Gt and "rates" in Gt):
            c.text(gi, 0.5, "pending", ha="center", va="center", rotation=90, fontsize=6, color="#999"); continue
        R = dict(J["secondary"]["rates"]) if (J and "secondary" in J) else {}   # Qwen: no blanket dose qualified, so only the gate confirmation exists
        R["blanket"] = R.get("steer")
        if Gt and "rates" in Gt:                       # blanket and gate at the same (gate) alpha, from the gate analysis
            R["blanket"] = Gt["rates"]["blanket"]; R["gate"] = Gt["rates"]["gate"]; R["none"] = Gt["rates"]["none"]
        for ai, (k, lab, col) in enumerate(ARMS):
            if not R.get(k):
                continue
            x = gi + (ai - 1.5) * w
            if k == "rand":                               # a random direction breaks the output: show unsafe-or-broken (VIOLATE or PARSE)
                c.bar(x, R[k]["violate_minus"] + R[k]["parse_minus"], w * 0.92, color="white", edgecolor="#8C8C8C", hatch="xxxx", lw=0.5)
            else:
                c.bar(x, R[k]["violate_minus"], w * 0.92, color=col, edgecolor="white", lw=0.4)
            c.plot(x, R[k]["progress_plus"], marker="o", ms=3.2, mfc="white", mec=col, mew=0.9, ls="none")
    c.set_xticks(range(len(MODELS))); c.set_xticklabels([MN[m] for m in MODELS], fontsize=6.4); c.set_ylim(0, 1.05); c.set_xlim(-0.6, len(MODELS) - 0.4)
    c.set_ylabel("rate on fresh sites"); c.set_title("(c) At the decision turn", loc="left", pad=6)
    hs = [plt.Rectangle((0, 0), 1, 1, facecolor="white", edgecolor="#8C8C8C", hatch="xxxx", label="random (unsafe/broken)") if k == "rand"
          else plt.Rectangle((0, 0), 1, 1, color=col, label=lab) for k, lab, col in ARMS]
    hs.append(plt.Line2D([], [], marker="o", mfc="white", mec="#333", ls="none", ms=3.5, label="authorized work")); hs = [hs[0], hs[2], hs[1], hs[3], hs[4]]
    c.legend(handles=hs, frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.11), fontsize=5.6, columnspacing=0.8, handlelength=1.3,
             title="bars: violations; circles: authorized work", title_fontsize=5.8)
    # (d) over the episode: eventual violation (bars) and eventual authorized completion (circles); results/prereg_v59
    R59 = os.environ.get("RES59", f"{ROOT}/results/prereg_v59"); arms = [("none", "no steering", "#6B6B6B"), ("gate", "gate once", "#56B4E9"), ("always", "gate every action", "#0072B2")]
    D_MODELS = ["gemma4", "gptoss20b", "museglimmer", "qwen38"]; HAS_ESC = any(os.path.exists(f"{R59}/always_esc_{m}.json") for m in D_MODELS)
    if HAS_ESC:                                        # v59d gate-escalate: steer on the first flag, ask the user on later flags (own paired none_hf)
        arms.append(("esc", "gate, then ask", "#0072B2"))
    w = 0.26 if not HAS_ESC else 0.2
    for gi, m in enumerate(D_MODELS):
        S1, SA = load(f"{R59}/summary_{m}.json"), load(f"{R59}/always_{m}.json") or load(f"{R59}/always_all_{m}.json")
        V, Cp = {}, {}
        if SA and "eventual_violation" in SA:              # gate-every-action run: paired none_hf; gate once from the same sites (vLLM)
            V = {"none": SA["eventual_violation"].get("none_hf"), "gate": SA["eventual_violation"].get("gate"), "always": SA["eventual_violation"].get("gate_always")}
            Cp = {"none": SA["eventual_completion"].get("none_hf"), "gate": SA["eventual_completion"].get("gate"), "always": SA["eventual_completion"].get("gate_always")}
        elif SA and "violation" in SA:
            V = {"none": SA["violation"].get("none_hf"), "always": SA["violation"].get("gate_always")}; Cp = {"none": SA["completion"].get("none_hf"), "always": SA["completion"].get("gate_always")}
        if S1:
            V.setdefault("none", S1["eventual_violation"].get("none")); V.setdefault("gate", S1["eventual_violation"].get("gate"))
            Cp.setdefault("none", S1["eventual_completion"].get("none")); Cp.setdefault("gate", S1["eventual_completion"].get("gate"))
        E61 = load(f"{ROOT}/results/prereg_v61/e2e_{m}.json")          # v61 contains the gate-every-action design for Muse
        if E61 and "always" not in V:
            V["always"] = E61["decomposition"]["violation"].get("gate_always"); Cp["always"] = E61["v59b_muse"]["completion"].get("gate_always")
        SE = load(f"{R59}/always_esc_{m}.json")
        if SE and "violation" in SE:
            V["esc"] = SE["violation"].get("gate_always"); Cp["esc"] = SE["completion"].get("gate_always")
        for ai, (k, lab, col) in enumerate(arms):
            x = gi + (ai - (len(arms) - 1) / 2) * w
            if V.get(k) is None:
                d4.text(x, 0.04, "pending", rotation=90, ha="center", fontsize=5.5, color="#999"); continue
            if k == "esc":
                d4.bar(x, V[k], w * 0.92, color="white", edgecolor=col, hatch="////", lw=0.6)
            else:
                d4.bar(x, V[k], w * 0.92, color=col, edgecolor="white", lw=0.4)
            if Cp.get(k) is not None:
                d4.plot(x, Cp[k], marker="o", ms=3.2, mfc="white", mec=col, mew=0.9, ls="none")
    d4.set_xticks(range(len(D_MODELS))); d4.set_xticklabels([MN[m] for m in D_MODELS], fontsize=6.4); d4.set_xlim(-0.6, len(D_MODELS) - 0.4); d4.set_ylim(0, 1.05); d4.set_ylabel("rate on fresh sites")
    d4.set_title("(d) Over the episode", loc="left", pad=6)
    d4.legend(handles=[plt.Rectangle((0, 0), 1, 1, facecolor="white", edgecolor=col, hatch="////", label=lab) if k == "esc" else plt.Rectangle((0, 0), 1, 1, color=col, label=lab) for k, lab, col in arms]
              + [plt.Line2D([], [], marker="o", mfc="white", mec="#333", ls="none", ms=3.5, label="authorized work")],
              frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.11), fontsize=5.6, columnspacing=0.8, handlelength=1.3,
              title="bars: eventual violations; circles: authorized completion", title_fontsize=5.8)
    # appendix: decision time per model (formerly panel b)
    bfig, b = plt.subplots(figsize=(3.4, 2.3))
    if S57:
        w = 0.2
        for gi, m in enumerate(MODELS):
            pm = S57["per_model"].get(m)
            if not pm:
                continue
            for ki, k in enumerate(KEYS):
                v = pm["vs_XOTHER"].get(k)
                if v is not None:
                    b.bar(gi + (ki - 1.5) * w, v - 0.5, w * 0.92, bottom=0.5, color=COL[k], edgecolor="white", lw=0.4)
            v = pm["vs_XPLUS"].get("I")
            if v is not None:
                b.bar(gi + 1.5 * w, v - 0.5, w * 0.92, bottom=0.5, color="white", edgecolor=COL["I"], hatch="////", lw=0.6)
        b.legend(handles=[plt.Rectangle((0, 0), 1, 1, facecolor="white", edgecolor=COL["I"], hatch="////", lw=0.6, label="internal (ours), vs the same action when authorized")],
                 frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.12), fontsize=5.6, columnspacing=0.8, handlelength=1.3,
                 title="solid bars (colors as in a): violation vs the agent's other actions", title_fontsize=5.8)
    else:
        b.text(0.5, 0.6, "pending (v57)", ha="center", transform=b.transAxes, color="#999")
    b.axhline(0.5, color="#6B6B6B", lw=0.6, ls=":"); b.set_ylim(0.45, 1.02); b.set_ylabel("within-template AUROC (fresh)"); b.set_title("(b) At the decision, per model", loc="left", pad=6)
    b.set_xticks(range(len(MODELS))); b.set_xticklabels([MN[m] for m in MODELS], fontsize=6.4); b.set_xlim(-0.6, len(MODELS) - 0.4)
    bfig.savefig(f"{OUT}/fig_vforecast_permodel.pdf"); bfig.savefig(f"{OUT}/fig_vforecast_permodel.png", dpi=220); plt.close(bfig)
    fig.savefig(f"{OUT}/fig_violation.pdf"); fig.savefig(f"{OUT}/fig_violation.png", dpi=220); print("figure written", bool(S55), bool(S57))


if __name__ == "__main__":
    main()
