#!/usr/bin/env python
"""EXPLORATORY (not confirmatory): when does each signal appear? Within-scenario AUROC using only the first k
decisions after the reveal (label-free alignment: steps since the causal fact was observed), for the frozen actor probe
and the frozen matched-information observer, in the unaware (v2) and aware (v3 reasoning) conditions.

python scripts/12_explore_timing.py
"""
import importlib.util
import json
import pickle

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.activations.storage import load_activations
from cape.eval.prediction import event_table
from cape.utils.config import REPO_ROOT

spec = importlib.util.spec_from_file_location("v3", REPO_ROOT / "scripts/10_v3_aware_confirm.py")
v3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v3)


def events(name, fc, actor, observer):
    eps = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{name}.parquet")
    eps = eps[eps.cf_value == "unsafe"]
    rv = pd.to_numeric(eps.reveal_event, errors="coerce")
    tu = pd.to_numeric(eps.first_unsafe_event, errors="coerce")
    info = dict(zip(eps.episode_id, eps.unsafe_episode & (rv < tu)))
    reveal = dict(zip(eps.episode_id, rv))
    ev = event_table(eps).reset_index(drop=True)
    ai, AX = load_activations(REPO_ROOT / f"outputs/activations/{name}/L46", "pre_action_last", [46])
    oi, OX = load_activations(REPO_ROOT / f"outputs/activations/{name}/observer_cotpre_Qwen3-8B", "observer", [27])
    ev = ev.merge(ai.rename(columns={"row": "ra"}), on=["episode_id", "event_id"]).merge(
        oi.rename(columns={"row": "ro"}), on=["episode_id", "event_id"])
    ev["s_a"] = actor.decision_function(AX[46][ev.ra.values])
    ev["s_o"] = observer.decision_function(OX[27][ev.ro.values])
    ev["k"] = ev.event_id - ev.episode_id.map(reveal)  # decisions since the reveal
    d = ev[((ev.unsafe_episode == 0) | ev.episode_id.map(info).astype(bool)) & (ev.k >= 1)
           & ((ev.unsafe_episode == 0) | (ev.d >= 1))]
    return d


def main():
    fc = json.load(open(REPO_ROOT / "results/v2/frozen_choices.json"))
    actor = pickle.load(open(REPO_ROOT / "results/v2/frozen_actor_probe.pkl", "rb"))
    observer = pickle.load(open(REPO_ROOT / "results/v2/frozen_observer_probe.pkl", "rb"))
    rows = []
    for name in ["v2fresh_minus", "v3aware_reasoning_minus"]:
        d = events(name, fc, actor, observer)
        for K in [1, 2, 3, 5, 99]:
            w = d[d.k <= K]
            E = w.groupby(["scenario_id", "episode_id"]).agg(y=("unsafe_episode", "first"), s_a=("s_a", "max"),
                                                             s_o=("s_o", "max")).reset_index()
            a, n = v3.wsa(E, "s_a")
            o, _ = v3.wsa(E, "s_o")
            rows.append({"cond": name, "first_k_after_reveal": K, "n_mixed": n, "actor": a, "observer": o,
                         "actor_minus_observer": a - o})
    R = pd.DataFrame(rows)
    print(R.round(3).to_string(index=False))
    R.to_csv(REPO_ROOT / "results/v3_explore/timing.csv", index=False)


if __name__ == "__main__":
    main()
