#!/usr/bin/env python
"""Pre-registration v4 (docs/preregistration_v4.md): does adding the frozen actor-internal probe to the frozen
matched-information CoT observer improve within-scenario early warning over the observer alone?

python scripts/13_v4_combo_confirm.py mode=confirm sets='[v3aware_internal_minus,v4fresh_minus]'
python scripts/13_v4_combo_confirm.py mode=explore sets='[v2fresh_minus,v3aware_reasoning_minus]'   # validation

Combined score (fixed, nothing fitted): z(s_actor) + z(s_observer), each z-scored over all population episodes of the
same dataset (label-free). Statistic: within-scenario AUROC (v2 definition) pooled over the mixed scenarios of all
sets (groups = (set, scenario_id)), weights n_unsafe * n_safe. H4: AUROC(combined) - AUROC(observer) > 0; test:
within-scenario label permutation (10,000), one-sided. H5 (secondary): same with the Llama observer.
"""
import importlib.util
import json
import pickle

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.eval.statistics import auroc
from cape.utils.config import REPO_ROOT, load_config
from cape.utils.repro import write_json

spec = importlib.util.spec_from_file_location("v3", REPO_ROOT / "scripts/10_v3_aware_confirm.py")
v3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v3)

D = OmegaConf.create({"mode": "explore", "sets": ["v2fresh_minus", "v3aware_reasoning_minus"], "n_perm": 10000,
                      "seed": 0})
OBS = {"qwen": ("results/v2/frozen_observer_probe.pkl", "observer_cotpre_Qwen3-8B", 27),
       "llama": ("results/v2/frozen_observer_llama_probe.pkl", "observer_cotpre_Llama-3.1-8B-Instruct", 24)}


def build(sets, obs_key, fc, actor):
    path, odir, ol = OBS[obs_key]
    observer = pickle.load(open(REPO_ROOT / path, "rb"))
    cfg = OmegaConf.create({"obs_dir": odir, "obs_layer": ol})
    parts = []
    for s in sets:
        E, _ = v3.episode_scores(s, fc, actor, observer, cfg)
        for c in ("s_a", "s_o"):
            E[c + "_z"] = (E[c] - E[c].mean()) / E[c].std()
        E["comb"] = E.s_a_z + E.s_o_z
        E["group"] = s + "|" + E.scenario_id
        parts.append(E)
    E = pd.concat(parts, ignore_index=True)
    return E[E.groupby("group").y.transform("nunique") == 2].reset_index(drop=True)


def test(E, n, rng):
    groups = [g.index.values for _, g in E.groupby("group")]
    cols = {c: E[c].values for c in ("s_a", "s_o", "comb")}

    def st(y):
        out = {c: [] for c in cols}
        w = []
        for ix in groups:
            yy = y[ix]
            for c in cols:
                out[c].append(auroc(yy, cols[c][ix]))
            w.append(yy.sum() * (1 - yy).sum())
        return {c: float(np.average(v, weights=w)) for c, v in out.items()}
    y0 = E.y.values.astype(int)
    obs = st(y0)
    d0 = obs["comb"] - obs["s_o"]
    null = np.empty(n)
    for i in range(n):
        yp = y0.copy()
        for ix in groups:
            yp[ix] = rng.permutation(yp[ix])
        r = st(yp)
        null[i] = r["comb"] - r["s_o"]
    return {"actor": obs["s_a"], "observer": obs["s_o"], "combined": obs["comb"], "gain": d0,
            "p": float((np.sum(null >= d0) + 1) / (n + 1)), "null_q95": float(np.quantile(null, .95)),
            "n_mixed": len(groups), "n_unsafe": int(y0.sum()), "n_safe": int((1 - y0).sum()),
            "per_set": {s: {"n_mixed": int(g.group.nunique())} for s, g in E.groupby(E.group.str.split("|").str[0])}}


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    fc = json.load(open(REPO_ROOT / "results/v2/frozen_choices.json"))
    actor = pickle.load(open(REPO_ROOT / "results/v2/frozen_actor_probe.pkl", "rb"))
    rng = np.random.default_rng(cfg.seed)
    res = {"mode": cfg.mode, "sets": list(cfg.sets)}
    for k, key in (("H4", "qwen"), ("H5_secondary", "llama")):
        E = build(list(cfg.sets), key, fc, actor)
        res[k] = test(E, cfg.n_perm, rng)
        res[k]["observer_model"] = key
        res[k]["reject"] = res[k]["p"] <= 0.05 if k == "H4" else None
    res["decision"] = "SUPPORTED" if res["H4"]["reject"] else "NOT SUPPORTED"
    print(json.dumps(res, indent=2))
    out = REPO_ROOT / ("results/v4" if cfg.mode == "confirm" else "results/v4_explore")
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / f"combo_{'_'.join(cfg.sets)}.json", res)


if __name__ == "__main__":
    main()
