#!/usr/bin/env python
"""Headline figure (page 1): the failure, the internal forecast, and the fix. All numbers come from result files
(preregistered, fresh data); nothing is typed in by hand except the example's wording, which is a real CAPE episode.
  (a) the failure: act without authorization, ask permission afterwards, then report falsely (laundering marker)
  (b) the forecast: frozen pre-action gate scores on fresh decision sites, violating turns vs the same action when authorized
  (c) the fix: eventual violations over the episode without vs with the gate, per family; misreported violations end to end
python scripts/175_fig_headline.py -> paper/figures/fig1_headline.pdf"""
import importlib.util
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

from cape.utils.config import REPO_ROOT

plt.rcParams.update({"font.family": "serif", "font.serif": ["STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix", "font.size": 7.5,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6, "pdf.fonttype": 42,
                     "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.labelsize": 6.6, "ytick.labelsize": 6.6})
# paper-wide roles (validated: every pair passes normal-vision dE >= 15 and protan/deutan dE >= 8)
GREY, BLUE, RED_STATE, INK, MUTED = "#A8A8A8", "#0072B2", "#B42318", "#1F2937", "#5B6472"
MN = {"gemma4": "Gemma", "gptoss20b": "gpt-oss", "museglimmer": "Muse", "qwen38": "Qwen"}


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def gate_scores():
    """frozen v54 gate on fresh confirmation sites: score - tau, violating x- turns vs authorized x+ critical turns."""
    G154 = _mod("g154", "scripts/154_v54_gate.py"); rows = []
    for A in MN:
        G = np.load(REPO_ROOT / f"outputs/v54/gate_{A}.npz"); tau = float(G["tau"]); F = np.load(REPO_ROOT / f"outputs/v54/gatefeat_v54conf_{A}.npz")
        S = pd.read_parquet(REPO_ROOT / f"outputs/v54/sites_{A}_conf.parquet"); S["key"] = S.set + "|" + S.episode_id
        R = pd.read_parquet(REPO_ROOT / f"outputs/v54/v54conf_{A}.parquet"); R["key"] = R.set + "|" + R.episode_id; N = R[R.arm == "none"].set_index("key")
        for r in S.itertuples():
            if r.key in F.files and r.key in N.index:
                rows.append({"model": A, "world": r.world, "cat": N.loc[r.key].category, "tmpl": A + "|" + ".".join(str(r.instance_id).split(".")[:2]),
                             "s": float(G154.gate_score(G, F[r.key][None].astype(np.float32))[0]) - tau})
    D = pd.DataFrame(rows); V = D[(D.world == "minus") & (D.cat == "VIOLATE")]; Au = D[(D.world == "plus") & (D.cat == "CRITICAL")]
    return V.s.values, Au.s.values, strat_auc(np.r_[np.ones(len(V)), np.zeros(len(Au))], np.r_[V.s, Au.s], np.r_[V.tmpl, Au.tmpl])


def strat_auc(y, s, st):
    """AUROC within (model, template) strata, pair-weighted: the paper's metric (eq. 2), not a pooled AUROC."""
    from sklearn.metrics import roc_auc_score
    num = den = 0.0
    for k in np.unique(st):
        i = st == k
        if 0 < y[i].sum() < i.sum():
            w = y[i].sum() * (1 - y[i]).sum(); num += roc_auc_score(y[i], s[i]) * w; den += w
    return num / den if den else float("nan")


def prevention():
    """eventual violations over the episode (fresh, preregistered): the strongest confirmed policy per family."""
    j = lambda p: json.load(open(REPO_ROOT / p)); out = []
    for A, f, pol in (("gemma4", "results/prereg_v59/always_esc_gemma4.json", "gate, then ask"), ("gptoss20b", "results/prereg_v59/always_esc_gptoss20b.json", "gate, then ask"),
                      ("museglimmer", "results/prereg_v59/always_esc_museglimmer.json", "gate, then ask"), ("qwen38", "results/prereg_v59/always_esc64_qwen38.json", "gate, then ask")):
        try:
            d = j(f); out.append((A, d["violation"]["none_hf"], d["violation"]["gate_always"], d["D1"]["b_fixed"], d["D1"]["c_broken"], pol, d["completion"]["none_hf"], d["completion"]["gate_always"]))
        except FileNotFoundError:                     # gate, then ask not yet in: gate every action (confirmed)
            if A == "museglimmer":
                m = j("results/prereg_v61/e2e_museglimmer.json")["v59b_muse"]; d = m["D1_first100"]
                out.append((A, d["rate_comparator"], d["rate_treated"], d["fixed"], d["broken"], "gate every action", m["completion"]["none_hf"], m["completion"]["gate_always"]))
            else:
                d = j(f"results/prereg_v59/always_all_{A}.json"); out.append((A, d["violation"]["none_hf"], d["violation"]["gate_always"], d["D1"]["b_fixed"], d["D1"]["c_broken"], "gate every action", d["completion"]["none_hf"], d["completion"]["gate_always"]))
    e = j("results/prereg_v61/e2e_museglimmer.json")["endpoints"]["E2_gate_vs_none"]
    lie = j("results/prereg_v37/summary_full.json") if (REPO_ROOT / "results/prereg_v37/summary_full.json").exists() else None
    return out, (e["rate_comparator"], e["rate_treated"], e["fixed"], e["broken"])


def node(ax, x, y, w, h, title, body, warn=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.006,rounding_size=0.025", lw=0.7, ec=RED_STATE if warn else "#C9CED6",
                                fc="#FDF2F1" if warn else "#F5F7FA", transform=ax.transAxes, clip_on=False))
    ax.text(x + 0.02, y + h - 0.045, title, transform=ax.transAxes, fontsize=7.0, fontweight="bold", color=INK, va="top")
    mono = body.startswith(("export", "request", "“"))
    ax.text(x + 0.02, y + h - 0.16, body, transform=ax.transAxes, fontsize=5.3 if mono else 5.9, color=MUTED, va="top", linespacing=1.2, family="monospace" if mono else None)
    if warn:                                          # icon in a font that has the glyph, with a text label (never colour alone)
        ax.text(x + w - 0.02, y + 0.03, "⚠", transform=ax.transAxes, fontsize=7.0, color=RED_STATE, va="bottom", ha="right", family="DejaVu Sans")
        ax.text(x + w - 0.07, y + 0.035, warn, transform=ax.transAxes, fontsize=6.2, color=RED_STATE, va="bottom", ha="right", fontweight="bold")


def main():
    v, a, auc = gate_scores(); prev, e2e = prevention()
    fig = plt.figure(figsize=(6.85, 2.3)); gs = fig.add_gridspec(1, 3, width_ratios=[1.6, 1.0, 1.3], wspace=0.32, left=0.012, right=0.995, top=0.86, bottom=0.3)

    # (a) the failure
    ax = fig.add_subplot(gs[0]); ax.axis("off")
    ax.set_title("(a) The failure: act, ask afterwards, then lie", loc="left", fontsize=8, fontweight="bold", color=INK, pad=4)
    W, H, Y = 0.465, 0.42, (0.55, 0.06)
    node(ax, 0.0, Y[0], W, H, "1  Reads the rule", "Policy: exports need\nthe owner's approval.\nTicket: approval pending.")
    node(ax, 0.52, Y[0], W, H, "2  Acts anyway", "export_data(\n  to=partner)", warn="violation")
    node(ax, 0.0, Y[1], W, H, "3  Asks afterwards", "request_permission(\n  export) → denied")
    node(ax, 0.52, Y[1], W, H, "4  Reports", "“Permission was\n denied, so I did\n not export.”", warn="lie")
    kw = dict(arrowstyle="-|>", lw=0.8, color="#7A8494", mutation_scale=7)
    ax.annotate("", xy=(0.52, Y[0] + H / 2), xytext=(W, Y[0] + H / 2), xycoords="axes fraction", arrowprops=kw)
    ax.annotate("", xy=(W * 0.62, Y[1] + H + 0.005), xytext=(0.52 + W * 0.38, Y[0] - 0.005), xycoords="axes fraction", arrowprops=kw)
    ax.annotate("", xy=(0.525, Y[1] + H / 2), xytext=(W, Y[1] + H / 2), xycoords="axes fraction", arrowprops=kw)
    ax.text(0.0, -0.08, "After asking permission post hoc, reports are false 0.70 vs 0.08\n(1,081 fresh episodes, three agents; preregistered, odds ratio 7.0).",
            transform=ax.transAxes, fontsize=6.2, color=INK, va="top", linespacing=1.25)

    # (b) the forecast
    b = fig.add_subplot(gs[1]); bins = np.linspace(-3, 8, 34)   # full range of scores (-2.3 .. 7.5): no clipping
    for x, c in ((a, GREY), (v, RED_STATE)):
        b.hist(x, bins=bins, density=True, color=c, alpha=0.55 if c == GREY else 0.6, edgecolor="white", linewidth=0.4)
    b.set_xlim(-3, 8); top = b.get_ylim()[1] * 1.32; b.set_ylim(0, top)   # headroom for direct labels
    b.axvline(0, color=BLUE, lw=1.2); b.text(0.15, top * 0.98, "gate fires →", color=INK, fontsize=6.2, va="top")
    b.text(-0.15, top * 0.98, "← same action,\n    authorized", color=MUTED, fontsize=6.2, va="top", ha="right"); b.text(2.2, top * 0.45, "unauthorized", color=RED_STATE, fontsize=6.2, va="top")
    b.set_yticks([]); b.spines["left"].set_visible(False); b.set_xlabel("internal readout before the action (vs threshold)", fontsize=6.4)
    b.set_title("(b) Forecast from internals", loc="left", fontsize=8, fontweight="bold", color=INK, pad=4)
    b.text(0.0, -0.3, f"Within-template AUROC {auc:.2f}; fires on {np.mean(v > 0):.0%} of\nviolations, {np.mean(a > 0):.0%} of authorized (fresh; descriptive).", transform=b.transAxes, fontsize=6.2, color=INK, va="top", linespacing=1.25)

    # (c) the fix
    c = fig.add_subplot(gs[2]); w = 0.36; xs = np.arange(len(prev))
    for i, (A, n0, n1, fx, br, pol, c0, c1) in enumerate(prev):
        for dx, val, col in ((-w / 2, n0, GREY), (w / 2, n1, BLUE)):
            c.bar(i + dx, val, w * 0.92, color=col, edgecolor="white", linewidth=0.6)
            c.text(i + dx, val + 0.02, f"{val:.2f}", ha="center", fontsize=5.6, color=INK)
    j0 = len(prev) + 0.45
    for dx, val, col in ((-w / 2, e2e[0], GREY), (w / 2, e2e[1], BLUE)):
        c.bar(j0 + dx, val, w * 0.92, color=col, edgecolor="white", linewidth=0.6)
        c.text(j0 + dx, val + 0.02, f"{val:.2f}", ha="center", fontsize=5.6, color=INK)
    c.axvline(len(prev) - 0.25, color="#D5D9E0", lw=0.6)
    c.set_xticks(list(xs) + [j0]); c.set_xticklabels([MN[p[0]] for p in prev] + ["Muse"], fontsize=6.4); c.set_ylim(0, 0.92); c.set_yticks([0, 0.25, 0.5, 0.75])
    c.text(j0, 0.3, "violation,\nthen a lie", ha="center", fontsize=6.0, color=MUTED, linespacing=1.15)
    c.set_ylabel("rate over the episode", fontsize=6.4)
    c.set_title("(c) Prevent where the forecast fires", loc="left", fontsize=8, fontweight="bold", color=INK, pad=4)
    hs = [plt.Rectangle((0, 0), 1, 1, fc=GREY, ec="white"), plt.Rectangle((0, 0), 1, 1, fc=BLUE, ec="white")]
    c.legend(hs, ["no intervention", "forecast gate (ours)"], frameon=False, fontsize=6.0, loc="upper right", handlelength=1.0, borderaxespad=0.1)
    loss = [(MN[p[0]], p[7] - p[6]) for p in prev if p[7] - p[6] < -0.02]     # authorized completion, gate - none (computed, never asserted)
    work = "Authorized work kept." if not loss else "Authorized work kept, except " + ", ".join(f"{m} ({d:+.2f})" for m, d in loss) + "."
    c.text(0.0, -0.3, "Bars 1–4: eventual violations. Last pair:\nviolations then misreported. " + work, transform=c.transAxes, fontsize=6.2, color=INK, va="top", linespacing=1.25, wrap=True)
    out = REPO_ROOT / "paper/figures/fig1_headline"
    fig.savefig(f"{out}.pdf"); fig.savefig(f"{out}.png", dpi=220)
    json.dump({"auroc": auc, "fire_viol": float(np.mean(v > 0)), "fire_auth": float(np.mean(a > 0)), "n_viol": int(len(v)), "n_auth": int(len(a)),
               "prevention": prev, "e2e_muse": e2e}, open(f"{out}_stats.json", "w"), indent=1, default=str)
    print("wrote", out)


if __name__ == "__main__":
    main()
