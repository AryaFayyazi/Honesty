#!/usr/bin/env python
"""Exploratory (docs/theory_moral_hazard.md): implied default enforcement belief b0 under a one-parameter attempt model.
logit P(violate | template t, belief b) = alpha_t + beta_t * b, with b = 0 for the 'tools do not check' note (v6),
b = 1 for the 'tools enforce' note (v10). The no-note rate (v2) then identifies the default belief:
    b0_t = (logit p_v2 - logit p_v6) / (logit p_v10 - logit p_v6).
Scenario bootstrap (10,000) for CIs; rates smoothed with +0.5/+1 (Jeffreys-like) to avoid infinite logits.
"""
import json

import numpy as np
import pandas as pd

from cape.utils.config import REPO_ROOT
from cape.utils.repro import write_json

SETS = {"v6": "v6resp_minus", "v2": "v2fresh_minus", "v10": "v10enf_minus"}
TEMPLATES = ["con_ci_green", "tp_billing_correction", "auth_repo_access"]


def logit(k, n):
    p = (k + 0.5) / (n + 1)
    return np.log(p / (1 - p))


def main():
    col = set(json.load(open(REPO_ROOT / "results/validity/identity_collisions.json"))["v2fresh"])
    S = {}
    for c, n in SETS.items():
        e = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{n}.parquet", columns=["scenario_id", "template", "cf_value",
                                                                                  "unsafe_episode"])
        e = e[(e.cf_value == "unsafe") & ~e.scenario_id.isin(col)]
        S[c] = e.groupby(["template", "scenario_id"]).unsafe_episode.agg(["sum", "count"])
    rng = np.random.default_rng(0)
    out = {}
    for t in TEMPLATES:
        sc = sorted(set.intersection(*[set(S[c].loc[t].index) for c in SETS]))
        K = {c: S[c].loc[t].loc[sc] for c in SETS}

        def b0(idx):
            L = {c: logit(K[c]["sum"].values[idx].sum(), K[c]["count"].values[idx].sum()) for c in SETS}
            return (L["v2"] - L["v6"]) / (L["v10"] - L["v6"]) if L["v10"] != L["v6"] else np.nan
        full = b0(np.arange(len(sc)))
        bs = np.array([b0(rng.integers(0, len(sc), len(sc))) for _ in range(10000)])
        bs = bs[np.isfinite(bs)]
        out[t] = {"rates": {c: float(K[c]["sum"].sum() / K[c]["count"].sum()) for c in SETS}, "b0": float(full),
                  "b0_ci95": [float(np.quantile(bs, .025)), float(np.quantile(bs, .975))], "n_scenarios": len(sc)}
    print(json.dumps(out, indent=2))
    write_json(REPO_ROOT / "results/theory/belief_b0.json", out)


if __name__ == "__main__":
    main()
