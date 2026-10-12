#!/usr/bin/env python
"""Pre-registration v2: choose + freeze probes on the EXPLORATION data (v1 expanded set). Never touches fresh data.

python scripts/08_v2_freeze.py stage=actor      # choose actor layer by CV of the primary metric, fit frozen probe
python scripts/08_v2_freeze.py stage=observer   # fit frozen matched-information observer probe (layer 27)
python scripts/08_v2_freeze.py stage=observer_llama  # secondary independent-family observer (Llama-3.1-8B, layer 24)
"""
import json
import pickle

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.activations.storage import load_activations
from cape.eval.prediction import event_table, group_folds
from cape.eval.statistics import auroc
from cape.probes.linear import fit_logistic
from cape.utils.config import REPO_ROOT, load_config
from cape.utils.repro import write_json

D = OmegaConf.create({"stage": "actor", "layers": [14, 15, 30, 31, 46, 47, 61, 62, 63], "Cs": [1e-3, 1e-2],
                      "obs_layer": 27})
TRAJ = REPO_ROOT / "outputs/rollouts/expanded.parquet"
ACT = REPO_ROOT / "outputs/activations/expanded/L9_2pool"
OBS_PRE = REPO_ROOT / "outputs/activations/expanded/observer_cotpre_Qwen3-8B"
OBS_LLAMA = REPO_ROOT / "outputs/activations/expanded/observer_cotpre_Llama-3.1-8B-Instruct"
OUT = REPO_ROOT / "results/v2"


def exploration_events():
    eps = pd.read_parquet(TRAJ)
    excl = set(json.load(open(REPO_ROOT / "results/expanded/label_exclusions.json"))["episode_ids"])
    eps = eps[(~eps.episode_id.isin(excl)) & (eps.cf_value == "unsafe")]
    ev = event_table(eps).reset_index(drop=True)
    rv = pd.to_numeric(eps.reveal_event, errors="coerce")
    tu = pd.to_numeric(eps.first_unsafe_event, errors="coerce")
    info = dict(zip(eps.episode_id, eps.unsafe_episode & (rv < tu)))
    reveal = dict(zip(eps.episode_id, rv))
    return ev, info, reveal


def primary_metric(pred, info, reveal):
    """Within-scenario episode-level AUROC (pre-registration v2 definition)."""
    d = pred[((pred.unsafe_episode == 0) | pred.episode_id.map(info).astype(bool))
             & (pred.event_id > pred.episode_id.map(reveal).fillna(1e9))
             & ((pred.unsafe_episode == 0) | (pred.d >= 1))]
    ep = d.groupby(["scenario_id", "episode_id"]).agg(y=("unsafe_episode", "first"), s=("score", "max")).reset_index()
    v, w = [], []
    for _, g in ep.groupby("scenario_id"):
        if g.y.nunique() == 2:
            v.append(auroc(g.y, g.s))
            w.append(g.y.sum() * (1 - g.y).sum())
    return float(np.average(v, weights=w)) if v else np.nan


def cv_metric(ev, X, info, reveal, Cs):
    parts = []
    for k, (tr, te) in enumerate(group_folds(ev, "scenario", n_splits=5, seed=0)):
        m, C, _ = fit_logistic(X[tr], ev.y_eventual.values[tr], X[te], ev.y_eventual.values[te], Cs=tuple(Cs))
        p = ev.iloc[te][["episode_id", "event_id", "scenario_id", "unsafe_episode", "d"]].copy()
        p["score"] = m.decision_function(X[te])
        parts.append(p)
    return primary_metric(pd.concat(parts), info, reveal)


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    OUT.mkdir(parents=True, exist_ok=True)
    ev, info, reveal = exploration_events()
    if cfg.stage == "actor":
        idx, X = load_activations(ACT, "pre_action_last", list(cfg.layers))
        rows = ev.merge(idx, on=["episode_id", "event_id"]).row.values
        scores = {}
        for l in cfg.layers:
            scores[l] = cv_metric(ev, X[l][rows], info, reveal, cfg.Cs)
            print(f"layer {l}: CV primary metric {scores[l]:.4f}", flush=True)
        best = max(scores, key=scores.get)
        # NOTE: selection via CV inside exploration data; the Cs grid for the final fit is chosen on a held-out split
        tr, va = next(group_folds(ev, "scenario", n_splits=5, seed=1))
        Xb = X[best][rows]
        m, C, _ = fit_logistic(Xb[tr], ev.y_eventual.values[tr], Xb[va], ev.y_eventual.values[va], Cs=tuple(cfg.Cs))
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        final = make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=3000, class_weight="balanced"))
        final.fit(Xb, ev.y_eventual.values)
        pickle.dump(final, open(OUT / "frozen_actor_probe.pkl", "wb"))
        write_json(OUT / "frozen_choices.json", {"actor_layer": int(best), "actor_pooling": "pre_action_last",
                                                 "actor_C": C, "cv_primary_metric_by_layer": scores,
                                                 "observer_layer": int(cfg.obs_layer),
                                                 "decided_before_fresh_data": True})
        print("frozen actor probe: layer", best, "C", C)
    elif cfg.stage == "observer_llama":  # same recipe as the primary observer; separate files (v2 locks untouched)
        L = 24
        idx, X = load_activations(OBS_LLAMA, "observer", [L])
        rows = ev.merge(idx, on=["episode_id", "event_id"]).row.values
        Xo = X[L][rows]
        tr, va = next(group_folds(ev, "scenario", n_splits=5, seed=1))
        m, C, _ = fit_logistic(Xo[tr], ev.y_eventual.values[tr], Xo[va], ev.y_eventual.values[va], Cs=tuple(cfg.Cs))
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        final = make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=3000, class_weight="balanced"))
        final.fit(Xo, ev.y_eventual.values)
        pickle.dump(final, open(OUT / "frozen_observer_llama_probe.pkl", "wb"))
        write_json(OUT / "frozen_choices_llama.json", {"observer": "meta-llama/Llama-3.1-8B-Instruct", "layer": L,
                                                       "C": C, "cutoff": "end of reasoning at step t"})
        print("frozen llama observer probe: C", C)
    else:
        idx, X = load_activations(OBS_PRE, "observer", [int(cfg.obs_layer)])
        rows = ev.merge(idx, on=["episode_id", "event_id"]).row.values
        Xo = X[int(cfg.obs_layer)][rows]
        tr, va = next(group_folds(ev, "scenario", n_splits=5, seed=1))
        m, C, _ = fit_logistic(Xo[tr], ev.y_eventual.values[tr], Xo[va], ev.y_eventual.values[va], Cs=tuple(cfg.Cs))
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        final = make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=3000, class_weight="balanced"))
        final.fit(Xo, ev.y_eventual.values)
        pickle.dump(final, open(OUT / "frozen_observer_probe.pkl", "wb"))
        fc = json.load(open(OUT / "frozen_choices.json"))
        fc.update({"observer_C": C, "observer_cutoff": "end of reasoning at step t (excludes proposed action)"})
        write_json(OUT / "frozen_choices.json", fc)
        print("frozen observer probe: C", C)


if __name__ == "__main__":
    main()
