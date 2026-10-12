#!/usr/bin/env python
"""Within-scenario refit permutation null for the headline actor probe (scripts/05e_permutation_null.py).

python scripts/05e_permutation_null.py activations=outputs/activations/pilot/Lall_2pool layer=61 pooling=pre_action_last n_perm=100

Episode outcomes are permuted among episodes of the SAME scenario; this keeps scenario-level information (which
scenario types tend to go unsafe) in the null, so rejecting it requires episode-specific (run-level) signal.
"""
import json

import pandas as pd
from omegaconf import OmegaConf

from cape.activations.storage import available, load_activations
from cape.eval.prediction import event_table
from cape.eval.runner import fit_dense, permutation_null, repeated_cv
from cape.utils.config import REPO_ROOT, load_config
from cape.utils.repro import write_json

D = OmegaConf.create({"activations": None, "layer": 61, "pooling": "pre_action_last", "n_perm": 100,
                      "populations": ["all", "xminus"], "label": "y_eventual", "Cs": [1e-3, 1e-2]})


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    act = REPO_ROOT / cfg.activations
    ev = event_table(pd.read_parquet(available(act)["trajectories"]))
    idx, X = load_activations(act, cfg.pooling, [int(cfg.layer)])
    ev = ev.merge(idx, on=["episode_id", "event_id"])
    out = {}
    for pop in cfg.populations:
        df = (ev[ev.cf_value == "unsafe"] if pop == "xminus" else ev).reset_index(drop=True)
        A = X[int(cfg.layer)][df.row.values]
        mk = lambda y, A=A: fit_dense(A, y, Cs=list(cfg.Cs))
        r = permutation_null(df, mk, cfg.label, n_perm=int(cfg.n_perm))
        r["repeated_cv"] = repeated_cv(df, mk, cfg.label)
        r["n_events"], r["n_pos_episodes"] = len(df), int(df.groupby("episode_id").unsafe_episode.first().sum())
        out[pop] = r
        print(pop, json.dumps(r))
    write_json(REPO_ROOT / "results/pilot" / f"permutation_null_L{cfg.layer}_{cfg.pooling}.json", out)


if __name__ == "__main__":
    main()
