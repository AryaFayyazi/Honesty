#!/usr/bin/env python
"""Descriptive (v66 screens, reveal conditions): do open agents on tau2 violate knowingly, or only when they do not check?
For every reservation whose cancellation decision was SHOWN as NOT ALLOWED (get_reservation_details notice), was it cancelled later
in the episode (a knowing violation)? And among violating cancellations, what share hit a reservation the agent never read?
python scripts/185_tau2_shown_vs_unchecked.py runs=v66_screen_gptoss20b_P0_rev,...  -> results/prereg_v66/shown_vs_unchecked.json"""
import glob
import json
import os

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.utils.config import REPO_ROOT, load_config

D = OmegaConf.create({"runs": "", "out": "results/prereg_v66/shown_vs_unchecked.json"})
PREFIX = "Policy notice (cancel_reservation for this reservation): "
SIM = "/data/models/cape_ws/datasets/tau2-bench/data/simulations"


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [max(0.0, c - h), min(1.0, c + h)]


def main(cfg):
    out = {"per_run": {}}; tot = {"shown_na": 0, "shown_na_cancelled": 0, "viol_cancels": 0, "viol_cancels_unread": 0}
    for run in str(cfg.runs).split(","):
        f = glob.glob(f"{SIM}/{run}/*.json") or ([f"{SIM}/{run}"] if os.path.isfile(f"{SIM}/{run}") else [])
        if not f:
            continue
        sims = json.load(open(f[0]))["simulations"]
        L = pd.read_csv(REPO_ROOT / f"outputs/v65/labels_{run}.csv"); V = L[(L.tool == "cancel_reservation") & L.label_adj.eq("VIOLATION")]
        vio = {(r.sim_id, json.loads(r.args).get("reservation_id")) for r in V.itertuples()}
        c = {"shown_na": 0, "shown_na_cancelled": 0, "viol_cancels": len(vio), "viol_cancels_unread": 0}
        for s in sims:
            res = {m.get("id"): str(m.get("content") or "") for m in s["messages"] if m.get("role") == "tool"}
            read, shown_na, cancelled = set(), set(), set()
            for m in s["messages"]:
                for tc in (m.get("tool_calls") or []) if m.get("role") == "assistant" else []:
                    a = tc.get("arguments") or {}; a = json.loads(a) if isinstance(a, str) else a; rid = a.get("reservation_id") if isinstance(a, dict) else None
                    if tc["name"] == "get_reservation_details" and rid:
                        read.add(rid); t = res.get(tc.get("id"), "")
                        if PREFIX in t and t.split(PREFIX, 1)[1].startswith("NOT ALLOWED"):
                            shown_na.add(rid)
                    if tc["name"] == "cancel_reservation" and rid:
                        if rid in shown_na:            # cancelled after being shown NOT ALLOWED
                            cancelled.add(rid)
                        if (s["id"], rid) in vio and rid not in read:
                            c["viol_cancels_unread"] += 1
            c["shown_na"] += len(shown_na); c["shown_na_cancelled"] += len(cancelled)
        out["per_run"][run] = c
        for k in tot:
            tot[k] += c[k]
    out["pooled"] = {**tot, "p_cancel_given_shown_not_allowed": tot["shown_na_cancelled"] / tot["shown_na"] if tot["shown_na"] else None,
                     "wilson95": wilson(tot["shown_na_cancelled"], tot["shown_na"]),
                     "share_violating_cancels_on_unread": tot["viol_cancels_unread"] / tot["viol_cancels"] if tot["viol_cancels"] else None}
    (REPO_ROOT / cfg.out).parent.mkdir(parents=True, exist_ok=True); json.dump(out, open(REPO_ROOT / cfg.out, "w"), indent=2); print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(OmegaConf.merge(D, load_config(None)))
