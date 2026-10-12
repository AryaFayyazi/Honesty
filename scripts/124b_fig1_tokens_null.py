#!/usr/bin/env python3
"""SUPERSEDED (documented null, 2026-10-05): token-level readouts did not separate lying from honest episodes on fresh Muse data
(AUROC 0.33-0.64, no consistent sign; see docs/research_ledger.md). Kept for the record. Original docstring:
Figure 1 (paper): the lie inside the agent, and steering it. Reads outputs/reconcile/fig1_internals.{npz,_meta.parquet}
(scripts/123) and v46 rubric-v4 labels. Muse-Glimmer, 110 fresh steering-confirmation episodes. Output paper/figures/fig1_internals.pdf
Panels: (a) per-token score of the out-of-sample frozen lie forecaster along the time-warped episode, by unsteered outcome;
(b) per-token honesty readout (projection on the self-counterfactual direction, measured BEFORE the steering addition at that
layer, so only upstream propagation is visible) while the report is written: lying / candid / +8 steered;
(c) per-episode displacement under steering in the (detector, lever) plane, with cos(w, u)."""
import json
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from sklearn.metrics import roc_auc_score

R = os.environ.get("FIG1_R", "/home/arya/new_safety/cape/outputs/reconcile"); OUT = os.environ.get("FIG1_OUT", "/home/arya/new_safety/cape/paper/figures")
plt.rcParams.update({"font.family": "serif", "font.serif": ["STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix", "font.size": 8,
                     "axes.titlesize": 8.5, "axes.labelsize": 8, "xtick.labelsize": 6.8, "ytick.labelsize": 6.8, "legend.fontsize": 6.5,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6, "pdf.fonttype": 42,
                     "savefig.bbox": "tight", "savefig.pad_inches": 0.02})
LIE, HON, STEER, GREY = "#C0392B", "#2E86AB", "#1E8449", "#9AA0A6"
LU, LW = 2, 3          # u readout layer index (block 36, after two steered blocks); forecaster layer index (block 42)
NREP = 160             # report tokens shown


def boot_band(M, B=1000, seed=0):
    rng = np.random.default_rng(seed); M = np.asarray(M, float); n = M.shape[0]
    bs = np.stack([np.nanmean(M[rng.integers(0, n, n)], 0) for _ in range(B)])
    return np.nanmean(M, 0), np.nanpercentile(bs, 2.5, 0), np.nanpercentile(bs, 97.5, 0)


def roll(x, k=8):
    c = np.cumsum(np.insert(np.asarray(x, float), 0, 0)); out = np.full(len(x), np.nan); out[k - 1:] = (c[k:] - c[:-k]) / k
    out[:k - 1] = [np.mean(x[:i + 1]) for i in range(k - 1)]; return out


def warp(x, anchors, grid_per_seg):
    """piecewise-linear time warp: anchors (increasing token positions) -> fixed segment grid."""
    out = []
    for (a, b), n in zip(zip(anchors[:-1], anchors[1:]), grid_per_seg):
        t = np.linspace(a, b, n, endpoint=False); out.append(np.interp(t, np.arange(len(x)), x))
    return np.concatenate(out)


def main():
    Z = np.load(f"{R}/fig1_internals.npz"); M = pd.read_parquet(f"{R}/fig1_internals_meta.parquet")
    L = pd.read_parquet(f"{R}/v46B_rubric3.parquet")[["set", "episode_id", "message", "label"]]
    lab = {(r.set, r.episode_id, r.message): r.label for r in L.itertuples()}
    M["lab_none"] = [lab.get((r.set, r.episode_id, "none")) for r in M.itertuples()]
    M["lab_p8"] = [lab.get((r.set, r.episode_id, "caa_p8_d16")) for r in M.itertuples()]
    M["lie_none"] = M.lab_none == "MISREPRESENTED"; M["lie_p8"] = M.lab_p8 == "MISREPRESENTED"
    W = np.load(f"{R}/fig1_prep.npz"); Zd = np.load(f"{R}/caa_directions.npz")
    w = W["w"] / np.linalg.norm(W["w"]); u = Zd[f"ua_{LW}"] / np.linalg.norm(Zd[f"ua_{LW}"]); cos_wu = float(w @ u)

    fig = plt.figure(figsize=(6.75, 2.55)); gs = fig.add_gridspec(1, 3, width_ratios=[1.4, 1.05, 1.0], wspace=0.5)
    a, b, c = (fig.add_subplot(gs[0, i]) for i in range(3))

    # ---------- (a) forecaster score along the episode ----------
    segs = [40, 60, 70, 60]; curves = {True: [], False: []}; at_report = []
    for i, r in M.iterrows():
        s = Z[f"{i}_none_lda"].astype(float); pl = int(r.prompt_len)
        rev = r.a_reveal if r.a_reveal > 0 else 1; vio = max(r.a_violation, rev + 1)
        anchors = [0, rev, vio, pl, min(pl + NREP, len(s) - 1)]
        if not all(np.diff(anchors) > 0):
            continue
        sm = roll(s); curves[bool(r.lie_none)].append(warp(sm, anchors, segs)); at_report.append((bool(r.lie_none), s[pl - 1]))
    allc = np.vstack(curves[True] + curves[False]); mu, sd = np.nanmean(allc), np.nanstd(allc)
    x = np.arange(sum(segs))
    for key, col, name in ((False, HON, "report will be honest"), (True, LIE, "report will be a lie")):
        C = (np.vstack(curves[key]) - mu) / sd
        for row in C[:: max(1, len(C) // 12)]:
            a.plot(x, row, color=col, alpha=0.07, lw=0.5)
        m, lo, hi = boot_band(C); a.fill_between(x, lo, hi, color=col, alpha=0.22, lw=0); a.plot(x, m, color=col, lw=1.4, label=f"{name} (n={len(C)})")
    edges = np.cumsum([0] + segs)
    for e_, name in zip(edges[1:4], ("reveal", "violation", "report")):
        a.axvline(e_, color="#555", lw=0.6, ls=":"); a.text(e_ + 1, 0.98, name, transform=a.get_xaxis_transform(), ha="left", va="top", fontsize=5.8, color="#444")
    a.axvspan(edges[3], edges[4], color="#F4D03F", alpha=0.10, lw=0)
    y_ = np.array([t for t, _ in at_report]); s_ = np.array([v for _, v in at_report]); auc = roc_auc_score(y_, s_)
    a.text(0.02, 0.04, f"frozen forecaster, out-of-sample\nAUROC at report start = {auc:.2f}", transform=a.transAxes, fontsize=6.2, color="#333")
    a.set_xticks([]); a.set_xlabel("episode time (warped between events)"); a.set_ylabel("internal lie score (z)")
    a.set_title("(a) The lie forms before it is written", loc="left")
    a.legend(frameon=False, loc="lower right", fontsize=6.0, handlelength=1.4)

    # ---------- (b) honesty readout while writing the report ----------
    def rep_curve(i, pas):
        r = M.loc[i]; v = Z[f"{i}_{pas}_u{LU}"].astype(float)[int(r.prompt_len):]
        out = np.full(NREP, np.nan); out[:min(NREP, len(v))] = v[:NREP]; return roll(np.nan_to_num(out, nan=np.nanmean(v[:NREP]) if len(v) else 0))
    lies = [i for i in M.index if M.lie_none[i]]; cand = [i for i in M.index if M.lab_none[i] == "CANDID"]
    flip = [i for i in lies if not M.lie_p8[i]]
    A = np.array([rep_curve(i, "none") for i in lies]); H = np.array([rep_curve(i, "none") for i in cand]); S = np.array([rep_curve(i, "p8") for i in flip])
    lo_ref, hi_ref = np.nanmean(A[:, 20:]), np.nanmean(H[:, 20:]); nz = lambda X: (X - lo_ref) / (hi_ref - lo_ref)
    xr = np.arange(NREP)
    for X, col, name in ((A, LIE, f"lying report, no steering (n={len(A)})"), (H, HON, f"candid report, no steering (n={len(H)})"),
                         (S, STEER, f"same lying episodes, steered $\\alpha$=8\n(became non-lies, n={len(S)})")):
        m, lo, hi = boot_band(nz(X)); b.fill_between(xr, lo, hi, color=col, alpha=0.2, lw=0); b.plot(xr, m, color=col, lw=1.3, label=name)
    b.axvline(16, color=STEER, lw=0.7, ls="--"); b.text(17, 0.02, "steering on", transform=b.get_xaxis_transform(), color=STEER, fontsize=6.2)
    b.axhline(0, color=LIE, lw=0.4, ls=":"); b.axhline(1, color=HON, lw=0.4, ls=":")
    b.set_xlabel("report token"); b.set_ylabel("honesty readout\n(0 = lying mean, 1 = candid mean)")
    b.set_title("(b) Steering from the inside", loc="left"); b.legend(frameon=False, loc="upper left", fontsize=5.9, handlelength=1.3)

    # ---------- (c) detector vs lever plane ----------
    pts = []
    for i, r in M.iterrows():
        pl = int(r.prompt_len)
        d0 = np.nanmean(Z[f"{i}_none_lda"].astype(float)[pl + 16:pl + NREP]); d1 = np.nanmean(Z[f"{i}_p8_lda"].astype(float)[pl + 16:pl + NREP])
        l0 = np.nanmean(Z[f"{i}_none_u{LW}"].astype(float)[pl + 16:pl + NREP]); l1 = np.nanmean(Z[f"{i}_p8_u{LW}"].astype(float)[pl + 16:pl + NREP])
        pts.append((d0, l0, d1, l1, bool(r.lie_none), bool(r.lie_p8)))
    P = np.array(pts, float); dz = lambda v: (v - np.nanmean(P[:, 0])) / np.nanstd(P[:, 0]); lz = lambda v: (v - np.nanmean(P[:, 1])) / np.nanstd(P[:, 1])
    for d0, l0, d1, l1, y0, y1 in P:
        col = STEER if (y0 and not y1) else (LIE if (not y0 and y1) else GREY)
        c.annotate("", xy=(dz(d1), lz(l1)), xytext=(dz(d0), lz(l0)), arrowprops=dict(arrowstyle="-|>", color=col, lw=0.6, alpha=0.75, mutation_scale=5))
        c.plot(dz(d0), lz(l0), "o", ms=2.2, color=LIE if y0 else HON, alpha=0.8, mew=0)
    dd = np.nanmedian(dz(P[:, 2]) - dz(P[:, 0])); dl = np.nanmedian(lz(P[:, 3]) - lz(P[:, 1]))
    c.set_xlabel("detector axis: lie-forecast direction $w$ (z)"); c.set_ylabel("lever axis: honesty direction $u$ (z)")
    c.set_title("(c) Detector $\\perp$ lever", loc="left")
    c.text(0.98, 0.03, f"cos$(w,u)$ = {cos_wu:+.3f}\n(random pairs: |cos| < 0.024)\nmedian shift: $w$ {dd:+.1f}, $u$ {dl:+.1f}", transform=c.transAxes,
           ha="right", va="bottom", fontsize=6.0, bbox=dict(fc="white", ec="#ccc", lw=0.4, pad=1.5))
    c.legend(handles=[Line2D([], [], color=STEER, lw=1, label="lie $\\rightarrow$ non-lie"), Line2D([], [], color=GREY, lw=1, label="unchanged"),
                      Line2D([], [], color=LIE, lw=1, label="non-lie $\\rightarrow$ lie")], frameon=False, loc="upper left", fontsize=5.9, handlelength=1.2)
    fig.savefig(f"{OUT}/fig1_tokens_null.pdf"); fig.savefig(f"{OUT}/fig1_tokens_null.png", dpi=220)
    stats = {"n": len(M), "auroc_forecaster_report_start": round(float(auc), 4), "cos_w_u": round(cos_wu, 4), "n_lie_none": len(lies), "n_candid_none": len(cand),
             "n_flip": len(flip), "median_shift_detector_z": round(float(dd), 3), "median_shift_lever_z": round(float(dl), 3)}
    json.dump(stats, open(f"{OUT}/fig1_tokens_null_stats.json", "w"), indent=1); print(stats)


if __name__ == "__main__":
    main()
