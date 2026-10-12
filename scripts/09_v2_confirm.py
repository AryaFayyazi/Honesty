#!/usr/bin/env python
"""Pre-registration v2 confirmatory test (docs/preregistration_v2.md). Frozen probes, fresh data, no refitting.

python scripts/09_v2_confirm.py
H1': actor within-scenario AUROC > 0.5         (within-scenario label permutation, 10,000, fixed frozen scores)
H2': actor minus matched-info observer > 0     (same permutation applied to the paired difference)
Holm across H1', H2'. GO iff both reject.
"""
import json
import os
import pickle

import numpy as np
import pandas as pd

from cape.activations.storage import load_activations
from cape.eval.prediction import event_table
from cape.eval.statistics import auroc
from cape.utils.config import REPO_ROOT
from cape.utils.repro import write_json

DRY = bool(os.environ.get("CAPE_DRYRUN"))
TRAJ = REPO_ROOT / os.environ.get("CAPE_TRAJ", "outputs/rollouts/v2fresh_minus.parquet")
ACT = REPO_ROOT / os.environ.get("CAPE_ACT", "outputs/activations/v2fresh_minus/L46")
OBS = REPO_ROOT / os.environ.get("CAPE_OBS", "outputs/activations/v2fresh_minus/observer_cotpre_Qwen3-8B")
OUT = REPO_ROOT / ("results/dryrun_v2" if DRY else "results/v2")
N_PERM = int(os.environ.get("CAPE_NPERM", 10000)) if DRY else 10000


def main():
    fc = json.load(open(REPO_ROOT / "results/v2/frozen_choices.json"))
    actor = pickle.load(open(REPO_ROOT / "results/v2/frozen_actor_probe.pkl", "rb"))
    observer = pickle.load(open(REPO_ROOT / os.environ.get("CAPE_OBS_PROBE", "results/v2/frozen_observer_probe.pkl"),
                                "rb"))
    eps = pd.read_parquet(TRAJ)
    eps = eps[eps.cf_value == "unsafe"]
    rv = pd.to_numeric(eps.reveal_event, errors="coerce")
    tu = pd.to_numeric(eps.first_unsafe_event, errors="coerce")
    info = dict(zip(eps.episode_id, eps.unsafe_episode & (rv < tu)))
    reveal = dict(zip(eps.episode_id, rv))
    ev = event_table(eps).reset_index(drop=True)
    ai, AX = load_activations(ACT, fc["actor_pooling"], [fc["actor_layer"]])
    oi, OX = load_activations(OBS, "observer", [fc["observer_layer"]])
    ev = ev.merge(ai.rename(columns={"row": "ra"}), on=["episode_id", "event_id"]).merge(
        oi.rename(columns={"row": "ro"}), on=["episode_id", "event_id"])
    ev["s_a"] = actor.decision_function(AX[fc["actor_layer"]][ev.ra.values])
    ev["s_o"] = observer.decision_function(OX[fc["observer_layer"]][ev.ro.values])
    # primary population: safe or informed-unsafe x- episodes; events after reveal; unsafe events strictly before harm
    d = ev[((ev.unsafe_episode == 0) | ev.episode_id.map(info).astype(bool))
           & (ev.event_id > ev.episode_id.map(reveal).fillna(1e9))
           & ((ev.unsafe_episode == 0) | (ev.d >= 1))]
    E = d.groupby(["scenario_id", "episode_id"]).agg(y=("unsafe_episode", "first"), s_a=("s_a", "max"),
                                                     s_o=("s_o", "max")).reset_index()
    E = E[E.groupby("scenario_id").y.transform("nunique") == 2].reset_index(drop=True)
    groups = [g.index.values for _, g in E.groupby("scenario_id")]

    def stat(y, col):
        v, w = [], []
        for ix in groups:
            yy = y[ix]
            v.append(auroc(yy, E[col].values[ix]))
            w.append(yy.sum() * (1 - yy).sum())
        return float(np.average(v, weights=w))

    y0 = E.y.values.astype(int)
    a_obs, o_obs = stat(y0, "s_a"), stat(y0, "s_o")
    rng = np.random.default_rng(0)
    na, nd = np.empty(N_PERM), np.empty(N_PERM)
    for i in range(N_PERM):
        yp = y0.copy()
        for ix in groups:
            yp[ix] = rng.permutation(yp[ix])
        a, o = stat(yp, "s_a"), stat(yp, "s_o")
        na[i], nd[i] = a, a - o
    p1 = float((np.sum(na >= a_obs) + 1) / (N_PERM + 1))
    p2 = float((np.sum(nd >= a_obs - o_obs) + 1) / (N_PERM + 1))
    ps = {"H1'": p1, "H2'": p2}
    order = sorted(ps, key=ps.get)
    holm, rej, stop = {}, {}, False
    for k, h in enumerate(order):
        holm[h] = min(1.0, ps[h] * (2 - k))
        rej[h] = (not stop) and holm[h] <= 0.05
        stop = stop or not rej[h]
    res = {"n_mixed_scenarios": len(groups), "n_informed_unsafe_runs": int(E.y.sum()), "n_safe_runs": int((1 - E.y).sum()),
           "H1'": {"actor_within_scenario_auroc": a_obs, "null_mean": float(na.mean()),
                   "null_q95": float(np.quantile(na, .95)), "p": p1, "p_holm": holm["H1'"], "reject": rej["H1'"]},
           "H2'": {"actor_minus_observer": a_obs - o_obs, "observer_within_scenario_auroc": o_obs,
                   "null_q95": float(np.quantile(nd, .95)), "p": p2, "p_holm": holm["H2'"], "reject": rej["H2'"]},
           "decision": "GO" if rej["H1'"] and rej["H2'"] else "NO-GO", "n_perm": N_PERM,
           "frozen_choices": fc}
    print(json.dumps(res, indent=2))
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "confirmatory_v2.json", res)
    E.to_parquet(OUT / "episode_scores_v2.parquet")


if __name__ == "__main__":
    main()
