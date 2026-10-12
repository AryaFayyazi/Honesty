#!/usr/bin/env python
"""Layer scan of future-harm predictability from actor activations.

python scripts/04_layer_scan.py activations=outputs/activations/pilot/<dir> label=eventual_harm probe=logistic \
    layers=all group_split=scenario_id [pooling=pre_action_last] [population=all|xminus|informed] \
    [multiple_comparison_correction=bh] [n_boot=1000]

Layer selection uses validation AUROC only (reported as val_auroc); test AUROC is reported for every layer with BH
correction, never used for selection.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.activations.storage import available, load_activations
from cape.eval.early_warning import auroc_by_distance
from cape.eval.prediction import event_table
from cape.eval.runner import fit_dense, oof_predictions
from cape.eval.statistics import within_fold_auroc, auroc, benjamini_hochberg, cluster_bootstrap
from cape.utils.config import REPO_ROOT, load_config
from cape.utils.repro import snapshot, write_json

DEFAULTS = OmegaConf.create({"activations": None, "label": "eventual_harm", "probe": "logistic", "layers": "all",
                             "group_split": "scenario_id", "pooling": "pre_action_last", "population": "all",
                             "multiple_comparison_correction": "bh", "n_boot": 1000, "out": "results/pilot",
                             "trajectories": None, "seed": 0, "tag": "", "Cs": [1e-3, 1e-2]})
LABELS = {"eventual_harm": "y_eventual", "eventual": "y_eventual", "h1": "y_1", "h2": "y_2", "h4": "y_4", "h8": "y_8"}
LEVEL = {"scenario_id": "scenario", "template": "template", "scenario_family": "family"}


def population(df, name):
    if name == "xminus":
        return df[df.cf_value == "unsafe"]
    if name == "informed":
        return df[df.informed == 1]
    return df


def main():
    cfg = OmegaConf.merge(DEFAULTS, load_config(None))
    act = REPO_ROOT / cfg.activations
    meta = available(act)
    traj = Path(cfg.trajectories or meta["trajectories"])
    out = REPO_ROOT / cfg.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "runs").mkdir(exist_ok=True)
    eps = pd.read_parquet(traj)
    ev = event_table(eps)
    index, X = load_activations(act, cfg.pooling, None if cfg.layers == "all" else list(cfg.layers))
    ev = ev.merge(index, on=["episode_id", "event_id"], how="inner")
    ev = population(ev, cfg.population).reset_index(drop=True)
    lab = LABELS[cfg.label]
    level = LEVEL[cfg.group_split]
    print(f"{len(ev)} events, {ev.episode_id.nunique()} episodes, pos rate {ev[lab].mean():.3f}; layers {list(X)}")

    rows, heat = [], []
    for l, A in X.items():
        Xl = A[ev.row.values]
        pred = oof_predictions(ev, fit_dense(Xl, ev[lab].values, cfg.probe, seed=cfg.seed, df=ev, Cs=list(cfg.Cs)), label=lab,
                               level=level, seed=cfg.seed)
        pred["score"] = pred.score.astype(float)
        f = lambda d: within_fold_auroc(d, lab)
        a, lo, hi = cluster_bootstrap(pred, "scenario_id", f, n=cfg.n_boot, seed=cfg.seed)
        # one-sided bootstrap p-value for AUROC > 0.5 (cluster resampling)
        rng = np.random.default_rng(cfg.seed)
        groups = {k: v.index.values for k, v in pred.groupby("scenario_id")}
        keys = list(groups)
        bs = [f(pred.loc[np.concatenate([groups[keys[i]] for i in rng.choice(len(keys), len(keys))])])
              for _ in range(cfg.n_boot)]
        p = (np.sum(np.asarray(bs) <= 0.5) + 1) / (len(bs) + 1)
        rows.append({"layer": l, "pooling": cfg.pooling, "population": cfg.population, "label": lab,
                     "split": level, "auroc": a, "lo": lo, "hi": hi, "p_gt_chance": p,
                     "n_events": len(pred), "n_pos": int(pred[lab].sum()),
                     "val_auroc": float(pred.groupby("fold").val_auroc.first().mean())})
        if lab == "y_eventual":
            bd = auroc_by_distance(pred, n_boot=200, seed=cfg.seed)
            for r in bd.itertuples():
                heat.append({"layer": l, "d_bin": r.d_bin, "auroc": r.auroc, "n_pos": r.n_pos})
        print(rows[-1])
    res = pd.DataFrame(rows)
    res["p_bh"], res["sig_bh"] = benjamini_hochberg(res.p_gt_chance.values)
    tag = f"_{cfg.pooling}_{cfg.population}_{level}{cfg.tag}"
    res.to_csv(out / f"layer_auc{tag}.csv", index=False)
    if heat:
        H = pd.DataFrame(heat)
        H.to_csv(out / f"layer_time{tag}.csv", index=False)
        piv = H.pivot(index="layer", columns="d_bin", values="auroc").sort_index()
        fig, ax = plt.subplots(figsize=(6, max(3, 0.18 * len(piv))))
        im = ax.imshow(piv.values, aspect="auto", cmap="viridis", vmin=0.5, vmax=1.0, origin="lower")
        ax.set_xticks(range(len(piv.columns)), [f"{c}" + ("+" if c in (4, 6, 8) else "") for c in piv.columns])
        ax.set_yticks(range(len(piv.index)), piv.index)
        ax.set_xlabel("decisions before first unsafe action (d)")
        ax.set_ylabel("layer")
        ax.set_title(f"Future-harm AUROC ({cfg.pooling}, {cfg.population}, {level} holdout)", fontsize=8)
        fig.colorbar(im, label="AUROC")
        fig.tight_layout()
        fig.savefig(out / f"layer_time_heatmap{tag}.pdf")
    write_json(out / f"layer_scan{tag}.json", {"selected_layer_by_validation": int(res.loc[res.val_auroc.idxmax(), "layer"]),
                                              "n_sig_bh": int(res.sig_bh.sum()), "n_layers": len(res)})
    snapshot(out / "runs", cfg)
    print(res.to_string())


if __name__ == "__main__":
    main()
