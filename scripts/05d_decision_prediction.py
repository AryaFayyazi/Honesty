#!/usr/bin/env python
"""Regime-independent analysis: forecasting the agent's proceed-vs-escalate decision.

python scripts/05d_decision_prediction.py data=outputs/activations/pilot/<actor dir> [populations='[xplus,all]']

Label y_proceed (events before the first decision): 1 if the next decision is the critical action taken without
asking, 0 if the agent escalates (request_permission) or never acts. Within x+ both choices are safe, so this is a
pure within-condition decision-forecasting test. Reported by distance to the decision (d_decision).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.activations.storage import available, load_activations
from cape.eval.prediction import action_text, event_table, visible_history
from cape.eval.runner import fit_dense, fit_text, oof_predictions
from cape.eval.statistics import within_fold_auroc, auroc, cluster_bootstrap
from cape.utils.config import REPO_ROOT, load_config
from cape.utils.repro import snapshot

DEFAULTS = OmegaConf.create({"data": None, "scenarios": "outputs/capebench/pilot/scenarios.jsonl",
                             "populations": ["xplus", "all"], "poolings": ["pre_action_last", "turn_start"],
                             "n_boot": 1000, "seed": 0, "out": "results/pilot", "splits": ["scenario", "family"]})


def main():
    cfg = OmegaConf.merge(DEFAULTS, load_config(None))
    act = REPO_ROOT / cfg.data
    meta = available(act)
    traj = Path(meta["trajectories"])
    out = REPO_ROOT / cfg.out
    out.mkdir(parents=True, exist_ok=True)
    eps = pd.read_parquet(traj)
    specs = {json.loads(l)["instance_id"]: json.loads(l) for l in open(REPO_ROOT / cfg.scenarios)}
    ev = event_table(eps)
    ev = ev[ev.y_proceed.notna()].copy()
    ev["y_proceed"] = ev.y_proceed.astype(int)
    vis = {False: visible_history(eps, specs, False), True: visible_history(eps, specs, True)}
    poolings = [p for p in cfg.poolings if p in meta["poolings"]]
    acts = {p: load_activations(act, p) for p in poolings}
    obs_dirs = sorted((REPO_ROOT / "outputs" / "activations" / traj.stem).glob("observer_*"))
    rows, dist = [], []
    for popname in cfg.populations:
        df = {"xplus": ev[ev.cf_value == "safe"], "xminus": ev[ev.cf_value == "unsafe"], "all": ev}[popname]
        df = df.reset_index(drop=True)
        y = df.y_proceed.values
        keys = list(zip(df.episode_id, df.event_id))
        M = {"action": fit_text(action_text(df), y, "hash"),
             "text_tfidf": fit_text([vis[False][k] for k in keys], y),
             "cot_tfidf": fit_text([vis[True][k] for k in keys], y)}
        for od in obs_dirs:
            oi, oX = load_activations(od, "observer")
            r = df.merge(oi, on=["episode_id", "event_id"], how="left").row.values.astype(int)
            for l, A in oX.items():
                M[f"{od.name}_L{l}"] = fit_dense(A[r], y)
        for p in poolings:
            idx, X = acts[p]
            r = df.merge(idx, on=["episode_id", "event_id"], how="left").row.values.astype(int)
            for l, A in X.items():
                M[f"actor_{p}_L{l}"] = fit_dense(A[r], y)
        print(f"== {popname}: {len(df)} events, {df.episode_id.nunique()} episodes, proceed rate "
              f"{df.groupby('episode_id').y_proceed.first().mean():.2f}")
        for split in cfg.splits:
            for name, fitter in M.items():
                p = oof_predictions(df, fitter, "y_proceed", level=split, seed=cfg.seed)
                if p.empty:
                    continue
                p = p.merge(df[["episode_id", "event_id", "d_decision"]], on=["episode_id", "event_id"])
                f = lambda x: within_fold_auroc(x, "y_proceed")
                a, lo, hi = cluster_bootstrap(p, "scenario_id", f, n=cfg.n_boot, seed=cfg.seed)
                row = {"population": popname, "split": split, "method": name, "auroc": a, "lo": lo, "hi": hi,
                       "val_auroc": float(p.groupby("fold").val_auroc.first().mean())}
                for dmin in (1, 2, 3):
                    sub = p[p.d_decision >= dmin]
                    row[f"auroc_d>={dmin}"] = within_fold_auroc(sub, "y_proceed")
                rows.append(row)
                if split == "scenario":
                    for d in range(0, 6):
                        sub = p[(p.d_decision == d) | ((d == 5) & (p.d_decision >= 5))]
                        if sub.y_proceed.nunique() == 2 and len(sub) >= 20:
                            dist.append({"population": popname, "method": name, "d": d, "n": len(sub),
                                         "auroc": within_fold_auroc(sub, "y_proceed")})
                print(f"  [{split}] {name:45s} AUROC {a:.3f} [{lo:.3f},{hi:.3f}] d>=1 {row['auroc_d>=1']:.3f} "
                      f"d>=2 {row['auroc_d>=2']:.3f}")
    pd.DataFrame(rows).to_csv(out / "decision_prediction.csv", index=False)
    pd.DataFrame(dist).to_csv(out / "decision_by_distance.csv", index=False)
    snapshot(out / "runs", cfg)


if __name__ == "__main__":
    main()
