#!/usr/bin/env python
"""Pre-registration v19b (docs/preregistration_v19b.md): dry-run oracle vs label-only oracle vs no oracle, on fresh
seed-2033 worlds. Rollouts: slurm/v19b.sh. Analysis (after the label audit):

python scripts/42_oracle_v19b.py
"""
import importlib.util
import json

import numpy as np
from omegaconf import OmegaConf

from cape.utils.config import REPO_ROOT, load_config
from cape.utils.repro import write_json

spec = importlib.util.spec_from_file_location("o", REPO_ROOT / "scripts/34_oracle.py")
O = importlib.util.module_from_spec(spec)
spec.loader.exec_module(O)
D = OmegaConf.create({"n": 10000, "seed": 0, "margin": 0.05})


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    excl = set(json.load(open(REPO_ROOT / "results/v19b/excluded_scenarios.json")))
    rng = np.random.default_rng(cfg.seed)
    N, R, Y = (O.table(f"v19b{a}_minus", excl) for a in ("none", "orc", "dry"))
    Np, Yp = O.table("v19bnone_plus", excl), O.table("v19bdry_plus", excl)
    Np["succ"], Yp["succ"] = Np.success.astype(int), Yp.success.astype(int)
    res = {"OB1_dry_vs_orc": O.paired(Y, R, "viol", ["P"], cfg.n, rng),
           "OB2_dry_vs_none": O.paired(Y, N, "viol", ["P"], cfg.n, rng),
           "OB3_xplus_noninf": O.paired(Yp, Np, "succ", ["P", "other"], cfg.n, rng, "greater", cfg.margin)}
    order, stop = sorted(["OB1_dry_vs_orc", "OB2_dry_vs_none"], key=lambda k: res[k]["p_one_sided"]), False
    for i, k in enumerate(order):
        adj = min(1.0, res[k]["p_one_sided"] * (2 - i))
        res[k]["p_holm"], res[k]["reject"] = adj, (not stop) and adj <= 0.05
        stop = stop or not res[k]["reject"]
    res["OB3_xplus_noninf"]["pass"] = res["OB3_xplus_noninf"]["p_one_sided"] <= 0.05
    sec = {"orc_vs_none_P (replication of v19 OR1)": O.paired(R, N, "viol", ["P"], cfg.n, rng),
           "dry_vs_none_all": O.paired(Y, N, "viol", ["P", "other"], cfg.n, rng),
           "dry_vs_orc_all": O.paired(Y, R, "viol", ["P", "other"], cfg.n, rng)}
    for name, X in (("none", N), ("orc", R), ("dry", Y)):
        v = X[X.viol == 1]
        sec[f"rates_{name}"] = {"viol_P": float(X[X.cls == "P"].viol.mean()), "viol_all": float(X.viol.mean()),
                                "oracle_use": float(X.oracle_used.mean()), "escalation": float(X.escalated.mean()),
                                "viol_after_oracle_NOT_ALLOWED": float(X[X.oracle_denied_before == 1].viol.mean())
                                if X.oracle_denied_before.sum() else None,
                                "try_and_see_share": float(v.probe.mean()) if len(v) else None,
                                "by_template": X.groupby("template").viol.mean().round(4).to_dict()}
    sec["xplus_success"] = {"none": float(Np.succ.mean()), "dry": float(Yp.succ.mean()),
                            "dry_oracle_use": float(Yp.oracle_used.mean())}
    res["secondary"] = sec
    res["verdict"] = {"dryrun_fix_improves_on_label_oracle": bool(res["OB1_dry_vs_orc"]["reject"]),
                      "dryrun_oracle_reduces_violations": bool(res["OB2_dry_vs_none"]["reject"]
                                                               and res["OB3_xplus_noninf"]["pass"])}
    print(json.dumps(res, indent=2))
    write_json(REPO_ROOT / "results/v19b/v19b_oracle.json", res)


if __name__ == "__main__":
    main()
