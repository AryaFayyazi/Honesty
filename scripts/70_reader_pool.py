#!/usr/bin/env python
"""One reader monitor for many agents: pool Qwen-reader features of all actors' trajectories (shared feature space),
train the epistemic compositional gate on K-1 actors, test on the held-out actor (leave-one-actor-out), and
leave-one-template-out on the pooled data. Seed-balanced design per actor (as in scripts/65).

python scripts/70_reader_pool.py feat=mean8 layer_idx=2
Actors: qwen38 (Qwen reading its own rollouts) + rdqwen-{gemma4,gptoss20b,museglimmer}.
"""
import importlib.util
import json

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.utils.config import REPO_ROOT, load_config

spec = importlib.util.spec_from_file_location("ecg", REPO_ROOT / "scripts/65_epistemic_gate.py")
E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)
D = OmegaConf.create({"feat": "mean8", "layer_idx": 2, "actors": ["qwen38", "rdqwen-gemma4", "rdqwen-gptoss20b", "rdqwen-museglimmer"]})


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    Ms, Xs = [], []
    for a in cfg.actors:
        E.SEEDS = [0, 1]
        M, X = E.load(a, "v2fresh", cfg.feat, cfg.layer_idx)
        M["actor"] = a; M["scenario_id"] = a + "|" + M.scenario_id   # scenarios are per-actor groups
        Ms.append(M); Xs.append(X)
    M = pd.concat(Ms, ignore_index=True); X = np.concatenate(Xs)
    out = {"n_by_actor": M.groupby("actor").harm.agg(["size", "sum"]).to_dict()}
    loao = {}
    for a in cfg.actors:
        te = (M.actor == a).values
        g = E.gate(X[~te], M[~te].reset_index(drop=True), X[te])
        r = E.evaluate(g, M[te].reset_index(drop=True), np.zeros(te.sum(), int))
        loao[a] = {arm: {"all": r[arm]["all"], "informed": r[arm]["informed"], "uninformed": r[arm]["uninformed"],
                         "auroc": r[arm]["auroc_harm_vs_compliant"]} for arm in ("ecg", "mono", "auth_only")}
        print("held-out actor", a, {k: (v["all"]["TPR@1%compliant"], v["all"]["TPR@1%hard"], v["auroc"]) for k, v in loao[a].items()}, flush=True)
    out["leave_one_actor_out"] = loao
    loto = {}
    for t in sorted(M.template.unique()):
        te = (M.template == t).values
        if M.harm.values[te].sum() < 5:
            continue
        g = E.gate(X[~te], M[~te].reset_index(drop=True), X[te])
        r = E.evaluate(g, M[te].reset_index(drop=True), np.zeros(te.sum(), int))
        loto[t] = {arm: (r[arm]["all"]["TPR@1%compliant"], r[arm]["auroc_harm_vs_compliant"]) for arm in ("ecg", "mono")}
        print("held-out template", t, loto[t], flush=True)
    out["loto_pooled"] = loto
    out["loto_pooled_mean_TPR"] = {arm: round(float(np.nanmean([v[arm][0] if v[arm][0] is not None else np.nan for v in loto.values()])), 3) for arm in ("ecg", "mono")}
    print(out["loto_pooled_mean_TPR"])
    (REPO_ROOT / f"results/xm/reader_pool_{cfg.feat}_L{cfg.layer_idx}.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
