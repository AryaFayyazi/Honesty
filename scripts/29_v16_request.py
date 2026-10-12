#!/usr/bin/env python
"""v16 (docs/preregistration_v16.md): request framing vs authority. Informed-violation rates per scenario,
arm vs v2fresh reference (same scenarios/seeds), identity-collision scenarios excluded.

python scripts/29_v16_request.py
"""
import json

import numpy as np
import pandas as pd

from cape.utils.config import REPO_ROOT
from cape.utils.repro import write_json

N = 10000


def table(name, col):
    e = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{name}.parquet", columns=["scenario_id", "template", "cf_value",
                                                                                 "unsafe_episode", "reveal_event",
                                                                                 "first_unsafe_event", "success",
                                                                                 "escalated"])
    e = e[(e.cf_value == "unsafe") & ~e.scenario_id.isin(col)].copy()
    rv, tu = pd.to_numeric(e.reveal_event), pd.to_numeric(e.first_unsafe_event)
    e["iv"] = (e.unsafe_episode & (rv < tu)).astype(int)
    return e


def main():
    col = set(json.load(open(REPO_ROOT / "results/validity/identity_collisions.json"))["v2fresh"])
    R = table("v2fresh_minus", col)
    rng = np.random.default_rng(0)
    res = {"ref_rate": float(R.iv.mean())}
    ps = {}
    for arm, key, direction in (("v16assert_minus", "H-RA1", "increase"), ("v16conditional_minus", "H-RA2", "decrease")):
        try:
            A = table(arm, col)
        except FileNotFoundError:
            continue
        d = (A.groupby("scenario_id").iv.mean() - R.groupby("scenario_id").iv.mean()).dropna().values
        obs = d.mean()
        null = np.array([(d * rng.choice([-1, 1], len(d))).mean() for _ in range(N)])
        p = ((np.sum(null >= obs) if direction == "increase" else np.sum(null <= obs)) + 1) / (N + 1)
        ps[key] = float(p)
        res[key] = {"arm": arm, "rate": float(A.iv.mean()), "ref": float(R.iv.mean()), "mean_scenario_diff": float(obs),
                    "p_one_sided": float(p), "direction": direction, "success": float(A.success.mean()),
                    "ref_success": float(R.success.mean()), "escalated": float(A.escalated.mean()),
                    "by_template": A.groupby("template").iv.mean().round(4).to_dict()}
    order, stop = sorted(ps, key=ps.get), False
    for i, k in enumerate(order):
        adj = min(1.0, ps[k] * (len(ps) - i))
        res[k]["p_holm"], res[k]["reject"] = adj, (not stop) and adj <= 0.05
        stop = stop or not res[k]["reject"]
    print(json.dumps(res, indent=2))
    (REPO_ROOT / "results/v16").mkdir(parents=True, exist_ok=True)
    write_json(REPO_ROOT / "results/v16/v16_request.json", res)


if __name__ == "__main__":
    main()
