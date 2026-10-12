#!/usr/bin/env python
"""Confirmatory analysis exactly as pre-registered in docs/preregistration_expanded.md (+ Amendment 1).

python scripts/05f_confirmatory.py
H1: x- population, actor L61 pre_action_last logistic, within-fold AUROC for y_eventual, within-scenario refit
    permutation null (200 perms; (unsafe, T_harm) permuted jointly among episodes of the same scenario).
H2: same, evaluated on events with d >= 1 for positives (all events of safe episodes as negatives).
H3: one-sided paired scenario bootstrap of within-fold AUROC(actor) - AUROC(observer_cot Qwen3-8B L27), d >= 1.
Holm correction across H1-H3; decision rule applied mechanically. Secondary analyses are labelled as such.
"""
import json

import numpy as np
import pandas as pd
import torch

from cape.activations.storage import load_activations
from cape.eval.prediction import event_table
from cape.eval.runner import fit_dense, nuisance_features, oof_predictions
from cape.eval.statistics import within_fold_auroc
from cape.utils.config import REPO_ROOT
from cape.utils.repro import write_json

import os

# Pre-registered defaults; env overrides exist ONLY for dry-runs on pilot data (CAPE_DRYRUN=1 writes elsewhere).
ACT = REPO_ROOT / os.environ.get("CAPE_ACT", "outputs/activations/expanded/L9_2pool")
OBS = REPO_ROOT / os.environ.get("CAPE_OBS", "outputs/activations/expanded/observer_cot_Qwen3-8B")
TRAJ = REPO_ROOT / os.environ.get("CAPE_TRAJ", "outputs/rollouts/expanded.parquet")
OUT = REPO_ROOT / ("results/dryrun" if os.environ.get("CAPE_DRYRUN") else "results/expanded")
LAYER, OBS_LAYER, CS, SEED = 61, 27, [1e-3, 1e-2], 0
N_PERM = int(os.environ.get("CAPE_NPERM", 200)) if os.environ.get("CAPE_DRYRUN") else 200
N_BOOT = int(os.environ.get("CAPE_NBOOT", 2000)) if os.environ.get("CAPE_DRYRUN") else 2000


def relabel(df, T):
    """Rebuild event labels from a per-episode harm time T (NaN = safe episode). Post-harm events are dropped."""
    t_h = df.episode_id.map(T)
    keep = t_h.isna() | (df.event_id <= t_h)
    d = df[keep].copy()
    th = d.episode_id.map(T)
    d["y_eventual"] = (~th.isna()).astype(int)
    d["d"] = th - d.event_id
    d["unsafe_episode"] = d.y_eventual
    return d.reset_index(drop=True)


def h_metrics(pred):
    h1 = within_fold_auroc(pred, "y_eventual")
    sub = pred[(pred.unsafe_episode == 0) | (pred.d >= 1)]
    h2 = within_fold_auroc(sub, "y_eventual")
    return h1, h2


def main():
    eps = pd.read_parquet(TRAJ)
    excl_path = REPO_ROOT / "results/expanded/label_exclusions.json"  # Amendment 2 (label-validity exclusions)
    if excl_path.exists() and not os.environ.get("CAPE_DRYRUN"):
        excl = set(json.load(open(excl_path))["episode_ids"])
        eps = eps[~eps.episode_id.isin(excl)].reset_index(drop=True)
        print(f"Amendment 2: excluded {len(excl)} episodes with invalid labels")
    ev_full = event_table(eps, post_harm="keep")
    ev_full = ev_full[ev_full.cf_value == "unsafe"].reset_index(drop=True)
    T0 = eps[eps.cf_value == "unsafe"].set_index("episode_id").first_unsafe_event
    idx, X = load_activations(ACT, "pre_action_last", [LAYER])
    oidx, OX = load_activations(OBS, "observer", [OBS_LAYER])
    rows_a = dict(zip(zip(idx.episode_id, idx.event_id), idx.row))
    rows_o = dict(zip(zip(oidx.episode_id, oidx.event_id), oidx.row))

    def features(d, which):
        rows = rows_a if which == "actor" else rows_o
        A = X[LAYER] if which == "actor" else OX[OBS_LAYER]
        return A[[rows[(e, t)] for e, t in zip(d.episode_id, d.event_id)]]

    def predict(d, which, seed=SEED):
        Xd = nuisance_features(d) if which == "nuisance" else features(d, which)
        dev = "cuda" if torch.cuda.is_available() else None  # Amendment 3: GPU solver, same objective
        return oof_predictions(d, fit_dense(Xd, d.y_eventual.values, Cs=CS if which != "nuisance" else None,
                                            device=dev),
                               "y_eventual", level="scenario", seed=seed)

    d0 = relabel(ev_full, T0)
    print(f"x- events {len(d0)}, episodes {d0.episode_id.nunique()}, unsafe episodes {int(T0.notna().sum())}")
    p_act = predict(d0, "actor")
    obs_h1, obs_h2 = h_metrics(p_act)
    print("observed actor H1/H2:", obs_h1, obs_h2)

    # ---- H1/H2 within-scenario permutation null ----
    rng = np.random.default_rng(SEED)
    ep = eps[eps.cf_value == "unsafe"][["episode_id", "scenario_id"]].copy()
    ep["T"] = ep.episode_id.map(T0)
    null = []
    for i in range(N_PERM):
        perm = ep.copy()
        perm["T"] = perm.groupby("scenario_id").T.transform(lambda s: rng.permutation(s.values))
        d = relabel(ev_full, dict(zip(perm.episode_id, perm["T"])))
        null.append(h_metrics(predict(d, "actor", seed=SEED + 1 + i)))
        if (i + 1) % 20 == 0:
            print(f"perm {i + 1}/{N_PERM}", flush=True)
    null = np.asarray(null)
    p_h1 = float((np.sum(null[:, 0] >= obs_h1) + 1) / (len(null) + 1))
    p_h2 = float((np.sum(null[:, 1] >= obs_h2) + 1) / (len(null) + 1))

    # ---- H3 paired bootstrap actor vs observer (d>=1) ----
    p_obs = predict(d0, "observer")
    p_nui = predict(d0, "nuisance")
    j = p_act[["episode_id", "event_id", "scenario_id", "fold", "y_eventual", "d", "unsafe_episode", "score"]].merge(
        p_obs[["episode_id", "event_id", "score"]], on=["episode_id", "event_id"], suffixes=("_a", "_o")).merge(
        p_nui[["episode_id", "event_id", "score"]].rename(columns={"score": "score_n"}), on=["episode_id", "event_id"])
    j = j[(j.unsafe_episode == 0) | (j.d >= 1)].reset_index(drop=True)
    diff = lambda x, b: within_fold_auroc(x, "y_eventual", "score_a") - within_fold_auroc(x, "y_eventual", b)
    groups = {k: v.index.values for k, v in j.groupby("scenario_id")}
    keys = list(groups)
    boots = {"score_o": [], "score_n": []}
    for _ in range(N_BOOT):
        s = j.loc[np.concatenate([groups[keys[k]] for k in rng.choice(len(keys), len(keys))])]
        for b in boots:
            boots[b].append(diff(s, b))
    obs_d3 = diff(j, "score_o")
    b3 = np.asarray(boots["score_o"])
    p_h3 = float((np.sum(b3 <= 0) + 1) / (len(b3) + 1))  # one-sided: actor > observer

    # ---- Holm ----
    ps = {"H1": p_h1, "H2": p_h2, "H3": p_h3}
    order = sorted(ps, key=ps.get)
    rej, holm = {}, {}
    stop = False
    for k, h in enumerate(order):
        adj = min(1.0, ps[h] * (3 - k))
        holm[h] = adj
        rej[h] = (not stop) and adj <= 0.05
        stop = stop or not rej[h]
    decision = ("GO" if rej["H1"] and rej["H2"] and rej["H3"] else
                "PARTIAL GO (predictive precursors, not better than observer)" if rej["H1"] and rej["H2"] else "NO-GO")
    res = {"H1": {"auroc": obs_h1, "null_mean": float(null[:, 0].mean()), "null_q95": float(np.quantile(null[:, 0], .95)),
                  "p": p_h1, "p_holm": holm["H1"], "reject": rej["H1"]},
           "H2": {"auroc_d>=1": obs_h2, "null_mean": float(null[:, 1].mean()), "null_q95": float(np.quantile(null[:, 1], .95)),
                  "p": p_h2, "p_holm": holm["H2"], "reject": rej["H2"]},
           "H3": {"actor_minus_observer": obs_d3, "ci95": [float(np.quantile(b3, .025)), float(np.quantile(b3, .975))],
                  "p_one_sided": p_h3, "p_holm": holm["H3"], "reject": rej["H3"],
                  "observer_auroc_d>=1": within_fold_auroc(j, "y_eventual", "score_o")},
           "secondary_actor_minus_nuisance_d>=1": {"diff": diff(j, "score_n"),
                                                    "ci95": [float(np.quantile(boots["score_n"], .025)),
                                                             float(np.quantile(boots["score_n"], .975))],
                                                    "nuisance_auroc_d>=1": within_fold_auroc(j, "y_eventual", "score_n")},
           "decision": decision, "n_perm": N_PERM, "n_boot": N_BOOT,
           "n_unsafe_episodes_xminus": int(T0.notna().sum())}
    print(json.dumps(res, indent=2))
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "confirmatory.json", res)
    for name, p in (("actor", p_act), ("observer", p_obs), ("nuisance", p_nui)):
        p.to_parquet(OUT / f"oof_{name}.parquet")


if __name__ == "__main__":
    main()
