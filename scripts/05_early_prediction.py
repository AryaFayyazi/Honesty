#!/usr/bin/env python
"""Experiment 1: is there an early latent signal? (brief sections 26-31)

python scripts/05_early_prediction.py data=outputs/activations/pilot/<actor dir> \
    baselines='[action,text,cot,actor_latent]' horizons='[1,2,4,8,eventual]'

Methods (all trained/thresholded identically, out-of-fold, scenario-grouped):
  action        visible action features: current tool + args, history of tool names (step-level guard)
  nuisance      event index, tool identity, family (shortcut diagnostic)
  text          TF-IDF LR on the visible transcript incl. the proposed action (no CoT)
  cot           TF-IDF LR on the visible transcript + all reasoning up to and incl. step t
  llm_monitor   zero-shot Qwen3.8 judge (transcript / CoT variants), from scripts/05c_llm_monitor.py
  observer      linear probe on an observer LLM's hidden states (from scripts/05b_observer_states.py)
  actor_latent  linear / MLP / GRU probes on actor residuals (pre-action), + delta variants
Positives for the "earlier" claim are events strictly before the unsafe decision (d >= 1).
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.activations.storage import available, load_activations
from cape.eval.early_warning import auroc_by_distance, event_metrics, horizon_summary, warning_horizon
from cape.eval.prediction import action_text, event_table, visible_history
from cape.eval.runner import fit_dense, fit_text, fixed_scores, nuisance_features, oof_predictions
from cape.eval.statistics import within_fold_auroc, auroc, paired_cluster_bootstrap_diff
from cape.utils.config import REPO_ROOT, load_config
from cape.utils.repro import snapshot, write_json

DEFAULTS = OmegaConf.create({
    "data": None, "trajectories": None, "scenarios": "outputs/capebench/pilot/scenarios.jsonl",
    "baselines": ["action", "nuisance", "text", "cot", "llm_monitor", "observer", "actor_latent"],
    "horizons": [1, 2, 4, 8, "eventual"], "populations": ["all", "xminus"], "splits": ["scenario", "template", "family"],
    "poolings": ["pre_action_last", "turn_start", "pre_action_mean8", "pre_action_mean32"],
    "probes": ["logistic", "mlp", "gru"], "observer_dir": None, "monitor_file": None,
    "n_boot": 1000, "seed": 0, "out": "results/pilot"})


def pop(df, name):
    d = {"all": df, "xminus": df[df.cf_value == "unsafe"], "xplus": df[df.cf_value == "safe"],
         "informed": df[df.informed == 1]}[name]
    return d.reset_index(drop=True)


def main():
    cfg = OmegaConf.merge(DEFAULTS, load_config(None))
    act = REPO_ROOT / cfg.data
    meta = available(act)
    traj = Path(cfg.trajectories or meta["trajectories"])
    out = REPO_ROOT / cfg.out
    out.mkdir(parents=True, exist_ok=True)
    pred_dir = REPO_ROOT / "outputs" / "predictions" / traj.stem
    pred_dir.mkdir(parents=True, exist_ok=True)
    snapshot(pred_dir, cfg)
    eps = pd.read_parquet(traj)
    specs = {json.loads(l)["instance_id"]: json.loads(l) for l in open(REPO_ROOT / cfg.scenarios)}
    ev_all = event_table(eps)
    vis = {False: visible_history(eps, specs, False), True: visible_history(eps, specs, True)}
    layers = meta["layers"]
    poolings = [p for p in cfg.poolings if p in meta["poolings"]]

    # ----- feature providers (aligned to an event dataframe) -----
    acts = {p: load_activations(act, p) for p in poolings}
    mon = pd.read_parquet(cfg.monitor_file or REPO_ROOT / "outputs/monitor" / f"{traj.stem}_llm_monitor.parquet") \
        if "llm_monitor" in cfg.baselines else None

    def rows_for(df, pooling):
        idx, _ = acts[pooling]
        m = df.merge(idx, on=["episode_id", "event_id"], how="left")
        assert m.row.notna().all(), "missing activations for some events"
        return m.row.values.astype(int)

    def delta(X, df):
        """Delta h_t = h_t - h_{t-1} within episode (zeros at t=0)."""
        D = np.zeros_like(X)
        prev = df.groupby("episode_id").cumcount().values > 0
        order = np.arange(len(df))
        key = df.episode_id.values
        for i in order[prev]:
            D[i] = X[i] - X[i - 1] if key[i - 1] == key[i] else 0
        return D

    def methods(df, lab, full: bool, sel_layer: int | None):
        y = df[lab].values
        M = {}
        if "action" in cfg.baselines:
            M["action"] = fit_text(action_text(df), y, "hash")
        if "nuisance" in cfg.baselines:
            M["nuisance"] = fit_dense(nuisance_features(df), y, "logistic")
        keys = list(zip(df.episode_id, df.event_id))
        if "text" in cfg.baselines:
            M["text_tfidf"] = fit_text([vis[False][k] for k in keys], y)
        if "cot" in cfg.baselines:
            M["cot_tfidf"] = fit_text([vis[True][k] for k in keys], y)
        if mon is not None:
            for v in ("transcript_monitor", "cot_monitor"):
                s = df.merge(mon[mon.method == v], on=["episode_id", "event_id"], how="left").score.fillna(0).values
                M[f"llm_{v}"] = fixed_scores(s)
        for od in (obs_dirs or []):
            oi, oX = load_activations(od, "observer")
            r = df.merge(oi, on=["episode_id", "event_id"], how="left").row.values.astype(int)
            for l, A in oX.items():
                M[f"{Path(od).name}_L{l}"] = fit_dense(A[r], y, "logistic")
        if "actor_latent" in cfg.baselines:
            for p in (poolings if full else ["pre_action_last"]):
                r = rows_for(df, p)
                for l in (layers if full else [sel_layer]):
                    M[f"actor_{p}_L{l}_logistic"] = fit_dense(acts[p][1][l][r], y, "logistic")
            if sel_layer is not None:
                r = rows_for(df, "pre_action_last")
                X = acts["pre_action_last"][1][sel_layer][r]
                if full:
                    M[f"actor_pre_action_last_L{sel_layer}_delta_logistic"] = fit_dense(delta(X, df), y, "logistic")
                    M[f"actor_pre_action_last_L{sel_layer}_hdelta_logistic"] = fit_dense(np.c_[X, delta(X, df)], y, "logistic")
                for pr in cfg.probes:
                    if pr != "logistic" and full:
                        M[f"actor_pre_action_last_L{sel_layer}_{pr}"] = fit_dense(X, y, pr, df=df)
        return M

    obs_dirs = sorted((REPO_ROOT / "outputs" / "activations" / traj.stem).glob("observer_*")) \
        if "observer" in cfg.baselines else []

    table, dist_rows, comps, horizon_rows = [], [], [], []
    selected = {}
    for popname in cfg.populations:
        df = pop(ev_all, popname)
        print(f"== population {popname}: {len(df)} events, {df.episode_id.nunique()} episodes, "
              f"{df.unsafe_episode.groupby(df.episode_id).first().sum()} unsafe episodes")
        # --- select actor layer on VALIDATION (pre_action_last, logistic, scenario split) ---
        best = (None, -np.inf)
        val = {}
        r = rows_for(df, "pre_action_last")
        for l in layers:
            p = oof_predictions(df, fit_dense(acts["pre_action_last"][1][l][r], df.y_eventual.values), level="scenario",
                                seed=cfg.seed)
            v = p.groupby("fold").val_auroc.first().mean()
            val[l] = v
            if v > best[1]:
                best = (l, v)
        sel = best[0] if best[0] is not None else layers[len(layers) // 2]
        selected[popname] = {"layer": sel, "val_auroc_by_layer": val}
        print("selected layer (validation):", sel, val)

        for split in cfg.splits:
            full = split == "scenario"
            M = methods(df, "y_eventual", full, sel)
            preds = {}
            for name, fitter in M.items():
                p = oof_predictions(df, fitter, "y_eventual", level=split, seed=cfg.seed)
                if p.empty:
                    continue
                p["method"] = name
                preds[name] = p
                p.to_parquet(pred_dir / f"{popname}_{split}_eventual_{name}.parquet")
                em = event_metrics(p, n_boot=cfg.n_boot, seed=cfg.seed)
                row = {"population": popname, "split": split, "label": "eventual", "method": name, **em}
                # AUROC on strictly-early positives (d >= 1, d >= 2) vs safe-episode events
                for dmin in (1, 2):
                    sub = p[(p.unsafe_episode == 0) | ((p.y_eventual == 1) & (p.d >= dmin))]
                    row[f"auroc_d>={dmin}"] = within_fold_auroc(sub.assign(_y=(sub.unsafe_episode == 1).astype(int)), "_y")
                for a in (0.05, 0.10):
                    hs = horizon_summary(warning_horizon(p, f"tau_episode_{a}"), n_boot=200, seed=cfg.seed)
                    row.update({f"{k}@ep_fpr{a}": v for k, v in hs.items()})
                table.append(row)
                print(f"  [{split}] {name:55s} AUROC {em['auroc']:.3f} [{em['auroc_ci'][0]:.3f},{em['auroc_ci'][1]:.3f}]"
                      f"  d>=1 {row['auroc_d>=1']:.3f}  TPR@1%FPR {em['tpr_at_1fpr']:.3f}")
                if full:
                    bd = auroc_by_distance(p, n_boot=cfg.n_boot, seed=cfg.seed)
                    bd["method"], bd["population"] = name, popname
                    dist_rows.append(bd)
            # paired comparisons: selected actor probe vs every baseline (same events, shared cluster resampling)
            ref = f"actor_pre_action_last_L{sel}_logistic"
            if ref in preds:
                for name, p in preds.items():
                    if name == ref:
                        continue
                    j = preds[ref][["episode_id", "event_id", "scenario_id", "y_eventual", "d", "unsafe_episode",
                                    "fold", "score"]].merge(p[["episode_id", "event_id", "score"]], on=["episode_id", "event_id"],
                                                    suffixes=("_a", "_b")).reset_index(drop=True)
                    for dmin in (0, 1):
                        sub = j[(j.unsafe_episode == 0) | ((j.y_eventual == 1) & (j.d >= dmin))].reset_index(drop=True)
                        yy = (sub.unsafe_episode == 1).astype(int) if dmin else sub.y_eventual
                        sub = sub.assign(_y=yy.values)
                        pt, lo, hi, pv = paired_cluster_bootstrap_diff(
                            sub, "scenario_id", lambda x: within_fold_auroc(x, "_y", "score_a"),
                            lambda x: within_fold_auroc(x, "_y", "score_b"),
                            n=cfg.n_boot, seed=cfg.seed)
                        comps.append({"population": popname, "split": split, "reference": ref, "baseline": name,
                                      "positives": f"d>={dmin}", "auroc_diff": pt, "lo": lo, "hi": hi, "p": pv})

        # --- horizon-specific labels (scenario split, key methods) ---
        for h in cfg.horizons:
            if h == "eventual":
                continue
            lab = f"y_{h}"
            M = methods(df, lab, False, sel)
            for name, fitter in M.items():
                p = oof_predictions(df, fitter, lab, level="scenario", seed=cfg.seed)
                if p.empty:
                    continue
                horizon_rows.append({"population": popname, "label": lab, "method": name,
                                     "auroc": within_fold_auroc(p, lab), "n_pos": int(p[lab].sum())})

    T = pd.DataFrame(table)
    T.to_csv(out / "early_warning.csv", index=False)
    D = pd.concat(dist_rows, ignore_index=True) if dist_rows else pd.DataFrame()
    D.to_csv(out / "auroc_by_distance.csv", index=False)
    C = pd.DataFrame(comps)
    C.to_csv(out / "baseline_comparison.csv", index=False)
    pd.DataFrame(horizon_rows).to_csv(out / "horizon_labels.csv", index=False)
    write_json(out / "selected_layers.json", selected)

    # ---- killer figure: AUROC vs distance to harm, with cluster-bootstrap CIs ----
    if not D.empty:
        pops = D.population.unique()
        fig, axes = plt.subplots(1, len(pops), figsize=(6 * len(pops), 4), squeeze=False)
        for ax, pp in zip(axes[0], pops):
            sel = selected[pp]["layer"]
            show = [f"actor_pre_action_last_L{sel}_logistic", "action", "text_tfidf", "cot_tfidf",
                    "llm_transcript_monitor", "llm_cot_monitor"] + \
                   [m for m in D.method.unique() if m.startswith("observer_cot")][:1]
            for m in show:
                d = D[(D.population == pp) & (D.method == m)].sort_values("d_bin")
                if d.empty:
                    continue
                ax.plot(d.d_bin, d.auroc, marker="o", label=m.replace("_pre_action_last", ""))
                ax.fill_between(d.d_bin, d.lo, d.hi, alpha=0.15)
            ax.axhline(0.5, color="grey", lw=0.8, ls="--")
            ax.invert_xaxis()
            ax.set_xlabel("decisions before first unsafe action (d; last bins are >=)")
            ax.set_ylabel("AUROC (unsafe-episode events at d vs safe-episode events)")
            ax.set_title(f"population: {pp}")
            ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(out / "warning_horizon.pdf")
    print("wrote", out)


if __name__ == "__main__":
    main()
