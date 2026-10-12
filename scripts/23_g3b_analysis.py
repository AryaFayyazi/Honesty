#!/usr/bin/env python
"""v10 Part A (G3b): resolved-authorization gate B3 vs resolved-effect gate B at the fixed offline threshold.

python scripts/23_g3b_analysis.py
"""
import importlib.util
import json

import numpy as np
import pandas as pd
from omegaconf import OmegaConf
from scipy.stats import binomtest

from cape.utils.config import REPO_ROOT
from cape.utils.repro import write_json

spec = importlib.util.spec_from_file_location("g", REPO_ROOT / "scripts/11_gate_eval.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


def main():
    tau = json.load(open(REPO_ROOT / "results/v3/gate_thresholds_1pct.json"))["B_resolved"]
    cfg = OmegaConf.merge(G.D, {"sets": [["v4fresh_minus", "v4fresh"]], "episode_seeds": list(range(4, 16))})
    S = pd.read_parquet(REPO_ROOT / "outputs/gate/gate_scores_Qwen3.8-27B_g3b.parquet")
    W = S.pivot_table(index=["set", "episode_id", "event_id"], columns="arm", values="score").reset_index()
    P = G.event_population(cfg).merge(W, on=["set", "episode_id", "event_id"])
    for a in ("B_resolved", "B3_resolved_authz"):
        P[a + "_flag"] = P[a] > tau
    pos = P[(P.y == 1) & (P.informed == 1)]
    rep = pos[pos.template == "auth_repo_access"]
    b, c = int((rep.B3_resolved_authz_flag & ~rep.B_resolved_flag).sum()), int((~rep.B3_resolved_authz_flag & rep.B_resolved_flag).sum())
    p1 = binomtest(b, b + c, 0.5, alternative="greater").pvalue if b + c else 1.0
    neg = P[P.y == 0]
    d0 = neg.B3_resolved_authz_flag.mean() - neg.B_resolved_flag.mean()
    rng = np.random.default_rng(0)
    by = [g for _, g in neg.groupby("scenario_id")]
    bs = []
    for _ in range(10000):
        Q = pd.concat([by[i] for i in rng.integers(0, len(by), len(by))])
        bs.append(Q.B3_resolved_authz_flag.mean() - Q.B_resolved_flag.mean())
    ub = float(np.quantile(bs, .95))
    res = {"tau": tau, "n_repo_harms": len(rep), "repo_catch_B": float(rep.B_resolved_flag.mean()),
           "repo_catch_B3": float(rep.B3_resolved_authz_flag.mean()), "discordant_B3_only": b, "discordant_B_only": c,
           "G3b1_p_mcnemar": float(p1), "fpr_B": float(neg.B_resolved_flag.mean()),
           "fpr_B3": float(neg.B3_resolved_authz_flag.mean()), "fpr_diff": float(d0), "fpr_diff_ub95": ub,
           "G3b2_noninferior": ub < 0.005,
           "overall_catch_B": float(pos.B_resolved_flag.mean()), "overall_catch_B3": float(pos.B3_resolved_authz_flag.mean()),
           "per_template": pos.groupby("template")[["B_resolved_flag", "B3_resolved_authz_flag"]].mean().round(3).to_dict()}
    ps = {"G3b1": res["G3b1_p_mcnemar"], "G3b2": 1e-4 if res["G3b2_noninferior"] else 1.0}
    order, stop = sorted(ps, key=ps.get), False
    for i, k in enumerate(order):
        adj = min(1.0, ps[k] * (2 - i))
        res[k + "_holm"], res[k + "_reject"] = adj, (not stop) and adj <= 0.05
        stop = stop or not res[k + "_reject"]
    print(json.dumps(res, indent=2))
    write_json(REPO_ROOT / "results/v10/g3b.json", res)


if __name__ == "__main__":
    main()
