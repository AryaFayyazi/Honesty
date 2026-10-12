#!/usr/bin/env python
"""Figure 4 (prevention), fresh preregistered data:
  (a) at the decision turn: violations (bars) and authorized work (circles) without steering, with blanket steering and with the
      forecast gate at the same dose (results/prereg_v54/gate_<m>_conf.json);
  (b) over the episode: eventual violations (bars) and authorized completion (circles): no steering, gate once, gate every action,
      gate then ask (results/prereg_v59, v61);
  (c) end to end: violations that are then misreported, without vs with the gate (v61 Muse; v64 four families when available);
  (d) lie-specific levers: false-report rate before vs after each lever, where honesty steering was built vs after a violation
      (v46, v61b, v61c, v63).
python scripts/178_fig_prevent.py -> paper/figures/fig4_prevent.pdf (+ _stats.json)"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from cape.utils.config import REPO_ROOT

plt.rcParams.update({"font.family": "serif", "font.serif": ["STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix", "font.size": 7.5,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6, "pdf.fonttype": 42,
                     "xtick.labelsize": 6.4, "ytick.labelsize": 6.4})
GREY, BLUE, ORANGE, INK, MUTED = "#A8A8A8", "#0072B2", "#E69F00", "#1F2937", "#5B6472"
MN = {"gemma4": "Gemma", "gptoss20b": "gpt-oss", "museglimmer": "Muse", "qwen38": "Qwen"}


def load(p):
    p = REPO_ROOT / p
    return json.load(open(p)) if p.exists() else None


def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0, c - h), min(1, c + h)


def main():
    fig, ax = plt.subplots(1, 4, figsize=(6.85, 2.3), gridspec_kw={"width_ratios": [1.05, 1.15, 1.05, 1.1], "wspace": 0.5, "left": 0.055, "right": 0.985, "top": 0.86, "bottom": 0.32})
    st = {}
    # (a) decision turn
    a = ax[0]; arms = [("none", "no steering", GREY), ("blanket", "blanket steering", ORANGE), ("gate", "forecast gate (ours)", BLUE)]; w = 0.26
    for gi, m in enumerate(MN):
        G = load(f"results/prereg_v54/gate_{m}_conf.json")
        for ai, (k, lab, col) in enumerate(arms):
            r = G["rates"][k]; x = gi + (ai - 1) * w; st.setdefault("decision", {}).setdefault(m, {})[k] = {"violate": r["violate_minus"], "work": r["progress_plus"]}
            a.bar(x, r["violate_minus"], w * 0.9, color=col, edgecolor="white", linewidth=0.5, label=lab if gi == 0 else None)
            a.plot(x, r["progress_plus"], marker="o", ms=3.0, mfc="white", mec=col if col != GREY else "#6B6B6B", mew=0.9, ls="none")
    a.set_xticks(range(4)); a.set_xticklabels([v.replace("gpt-oss", "gpt-\noss") for v in MN.values()], fontsize=6.0, linespacing=0.95); a.set_ylim(0, 1.08); a.set_ylabel("rate on fresh sites", fontsize=6.4)
    a.set_title("(a) At the decision", loc="left", fontsize=8, fontweight="bold", color=INK, pad=4)
    # (b) over the episode
    b = ax[1]; arms2 = [("once", "gate once"), ("always", "gate every action"), ("esc", "gate, then ask")]; w = 0.24   # each policy vs ITS OWN paired no-steering run
    for gi, m in enumerate(MN):
        V, C, B0 = {}, {}, {}
        S1 = load(f"results/prereg_v59/summary_{m}.json")
        if S1:
            B0["once"] = S1["eventual_violation"]["none"]; V["once"], C["once"] = S1["eventual_violation"]["gate"], S1["eventual_completion"]["gate"]
        SA = load(f"results/prereg_v59/always_all_{m}.json") or load(f"results/prereg_v59/always_k12_{m}.json")
        if SA and "violation" in SA:
            V["always"], C["always"] = SA["violation"]["gate_always"], SA["completion"]["gate_always"]; B0["always"] = SA["violation"]["none_hf"]
        elif m == "gemma4":
            g = load("results/prereg_v59/always_gemma4.json")
            if g:
                V["always"] = g.get("eventual_violation", {}).get("gate_always", g.get("violation", {}).get("gate_always"))
                B0["always"] = g.get("eventual_violation", {}).get("none_hf", g.get("violation", {}).get("none_hf"))
                C["always"] = (load("results/prereg_v59/always_k12_gemma4.json") or {}).get("completion", {}).get("gate_always")
        if m == "museglimmer" and "always" not in V:
            e = load("results/prereg_v61/e2e_museglimmer.json")["v59b_muse"]; d1 = e["D1_first100"]   # preregistered v59b Muse design (first 100 sites)
            V["always"], B0["always"], C["always"] = d1["rate_treated"], d1["rate_comparator"], e["completion"]["gate_always"]
        SE = load(f"results/prereg_v59/always_esc{'64' if m == 'qwen38' else ''}_{m}.json")   # Qwen: 12-step rerun (v64 Addendum 2)
        if SE:
            V["esc"], C["esc"] = SE["violation"]["gate_always"], SE["completion"]["gate_always"]; B0["esc"] = SE["violation"]["none_hf"]
        st.setdefault("episode", {})[m] = {"violation": V, "completion": C, "paired_none_violation": dict(B0)}
        for ai, (k, lab) in enumerate(arms2):
            x = gi + (ai - 1) * w
            if V.get(k) is None:
                b.text(x, 0.03, "pending", rotation=90, fontsize=5.2, color=MUTED, ha="center", va="bottom"); continue
            kw = {"once": dict(color="white", edgecolor=BLUE, linewidth=0.8),
                  "always": dict(color=BLUE, edgecolor="white"), "esc": dict(color="white", edgecolor=BLUE, hatch="//////", linewidth=0.6)}[k]
            b.bar(x, V[k], w * 0.88, label=lab if gi == 0 else None, **kw)
            if B0.get(k) is not None:                       # its own paired no-steering run
                b.plot([x - w * 0.44, x + w * 0.44], [B0[k], B0[k]], color="#6B6B6B", lw=1.3, solid_capstyle="butt", zorder=4)
            if C.get(k) is not None:
                b.plot(x, C[k], marker="o", ms=3.0, mfc="white", mec=BLUE, mew=0.9, ls="none")
    b.set_xticks(range(4)); b.set_xticklabels([v.replace("gpt-oss", "gpt-\noss") for v in MN.values()], fontsize=6.0, linespacing=0.95); b.set_ylim(0, 1.08)
    b.set_title("(b) Over the episode", loc="left", fontsize=8, fontweight="bold", color=INK, pad=4)
    # (c) end to end: violation, then a lie
    c = ax[2]; E64 = load("results/prereg_v64/summary.json")
    e = load("results/prereg_v61/e2e_museglimmer.json")["endpoints"]["E2_gate_vs_none"]; pairs = [("Muse", e["rate_comparator"], e["rate_treated"])]   # preregistered (v61)
    if E64 and E64.get("P1_complete"):            # v64: only the preregistered P1 models, only once the 3-model analysis is complete (Muse in v64 is descriptive)
        for m in E64.get("P1_models", []):
            q = E64["per_model"].get(m, {}).get("P2_misreported_violation")
            if q:
                pairs.append((MN[m], q["rate_comparator"], q["rate_treated"]))
    st["end_to_end"] = pairs; w = 0.34
    for gi, (lab, r0, r1) in enumerate(pairs):
        for dx, val, col in ((-w / 2, r0, GREY), (w / 2, r1, BLUE)):
            c.bar(gi + dx, val, w * 0.9, color=col, edgecolor="white", linewidth=0.5); c.text(gi + dx, val + 0.006, f"{val:.2f}", ha="center", fontsize=5.0, color=INK)
    c.set_xticks(range(len(pairs))); c.set_xticklabels([p[0].replace("gpt-oss", "gpt-\noss") for p in pairs], fontsize=6.0, linespacing=0.95); c.set_xlim(-0.7, len(pairs) - 0.3); c.set_ylim(0, 0.3)
    c.set_ylabel("violation, then a false report", fontsize=6.4)
    c.set_title("(c) End to end", loc="left", fontsize=8, fontweight="bold", color=INK, pad=4)
    # (d) lie-specific levers
    d = ax[3]; L = []                                # complete-case false-report rate (reports only) for every row: one denominator

    def cc(stem, arms, tag_dir="outputs/v61", retry=None):
        import pandas as pd
        J = pd.read_parquet(REPO_ROOT / f"{tag_dir}/{stem}_rubric3.parquet"); lab = J.set_index(["message", "episode_id"]).label.to_dict()
        if retry and (REPO_ROOT / f"{tag_dir}/{retry}_rubric3.parquet").exists():
            for r in pd.read_parquet(REPO_ROOT / f"{tag_dir}/{retry}_rubric3.parquet").itertuples():
                if r.label != "UNPARSED":
                    lab[(r.message, r.episode_id)] = r.label
        out = []
        for a_ in arms:
            v_ = [l for (m_, _), l in lab.items() if m_ == a_ and l in ("CANDID", "OMITTED", "SPIN", "MISREPRESENTED")]
            out.append((sum(l == "MISREPRESENTED" for l in v_) / len(v_), len(v_)))
        return out
    v46 = load("results/prereg_v46/summary.json")["S2_complete_case"]; L.append(("honesty steering,\nwhere it was built", v46["rate_none"], v46["rate_p8"], v46["n"], True))
    (b0, nb0), (b1, nb1) = cc("revised_b_museglimmer", ["none_hf", "none_honest"]); L.append(("honesty steering,\nafter a violation", b0, b1, min(nb0, nb1), False))
    (c0, nc0), (c1, nc1) = cc("revised_c_museglimmer", ["none_hf", "none_contract"], retry="revised_c_retry_museglimmer"); L.append(("evidence contract,\nafter a violation", c0, c1, min(nc0, nc1), None))
    sw = cc("sweep_rev", ["plain", "a4", "a8", "a12"], tag_dir="outputs/v63", retry="sweep_retry"); best = min(sw[1:], key=lambda t: t[0])
    L.append(("direction rebuilt on\nthose episodes (dev)", sw[0][0], best[0], sw[0][1], False)); st["levers"] = L
    for i, (lab, r0, r1, n, works) in enumerate(L):
        y = len(L) - 1 - i
        d.plot([r0, r1], [y, y], color=BLUE if works else "#9CA3AF", lw=1.4, zorder=1, ls="-" if works is not None else "--")
        d.plot(r0, y, marker="o", ms=4.2, color=GREY, zorder=2); d.plot(r1, y, marker="o", ms=4.2, color=BLUE if works else "#6B7280", zorder=3)
        right = max(r0, r1) < 0.65               # label beside the dots, on the side with room
        d.text(max(r0, r1) + 0.06 if right else min(r0, r1) - 0.06, y, f"{r0:.2f}→{r1:.2f}", fontsize=5.6, color=INK, va="center", ha="left" if right else "right")
    d.set_yticks(range(len(L))); d.set_yticklabels([l[0] for l in L][::-1], fontsize=5.6, linespacing=1.0); d.set_xlim(0, 1.0); d.set_ylim(-0.6, len(L) - 0.4)
    d.set_xlabel("false-report rate among reports\n(light: before; dark: after)", fontsize=6.0, linespacing=1.1); d.spines["left"].set_visible(False); d.tick_params(axis="y", length=0)
    d.set_title("(d) Fixing the lie itself", loc="left", fontsize=8, fontweight="bold", color=INK, pad=4)
    # one shared legend row
    hs = [plt.Rectangle((0, 0), 1, 1, fc=GREY, ec="white"), plt.Rectangle((0, 0), 1, 1, fc=ORANGE, ec="white"), plt.Rectangle((0, 0), 1, 1, fc=BLUE, ec="white"),
          plt.Rectangle((0, 0), 1, 1, fc="white", ec=BLUE, lw=0.8), plt.Rectangle((0, 0), 1, 1, fc="white", ec=BLUE, hatch="//////", lw=0.6),
          plt.Line2D([], [], marker="o", mfc="white", mec="#6B6B6B", ls="none", ms=3.5), plt.Line2D([], [], color="#6B6B6B", lw=1.3)]
    fig.legend(hs, ["no steering", "blanket steering", "forecast gate / gate every action (ours)", "gate once", "gate, then ask (ours)", "circles: authorized work", "dash: paired no-steering run"],
               loc="lower center", ncol=7, frameon=False, fontsize=5.9, handlelength=1.1, columnspacing=0.9, bbox_to_anchor=(0.5, 0.0))
    out = REPO_ROOT / "paper/figures/fig4_prevent"; fig.savefig(f"{out}.pdf"); fig.savefig(f"{out}.png", dpi=220)
    json.dump(st, open(f"{out}_stats.json", "w"), indent=1, default=str); print(json.dumps(st.get("episode"), indent=1, default=str)[:1500])


if __name__ == "__main__":
    main()
