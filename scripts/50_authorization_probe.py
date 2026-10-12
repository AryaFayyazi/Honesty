#!/usr/bin/env python
"""Feasibility: is the authorization JUDGMENT (is this action authorized?) a strong, cheap, GENERAL linear direction in
the agent's activations? Matched x+/x- critical-action events differ only in the authorization fact.

Label at the first critical event: y=1 if cf world is unauthorized (x-), 0 if authorized (x+).
Tests:
  within-scenario / grouped CV AUROC per layer (pick layer on a dev split of scenarios),
  TEMPLATE-TRANSFER: train on all-but-one template, test on the held-out template (general direction, not ACL-string),
  compare to the "will-violate" action probe (frozen_actor_probe, ~0.7).
CPU-only; needs outputs/activations/v2fresh_{plus,minus}.
"""
import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

from cape.activations.storage import load_activations
from cape.eval.statistics import auroc
from cape.utils.config import REPO_ROOT

LAYERS = [30, 38, 46, 54, 62]
ACTdir = {"plus": "outputs/activations/v2fresh_plus/L30-38-46-54-62_pre_action_last",
          "minus": "outputs/activations/v2fresh_minus/L46"}  # minus has L46 only (pre_action_last)


def first_critical_rows(stem, cf):
    eps = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{stem}.parquet")
    eps = eps[eps.cf_value == cf]
    col = set(json.load(open(REPO_ROOT / "results/validity/identity_collisions.json"))["v2fresh"])
    rows = []
    for ep in eps.itertuples():
        if ep.scenario_id in col:
            continue
        crit = [e for e in ep.events if e["critical"]]
        if not crit:
            continue
        # unauthorized instance only if NOT approved before the critical act (clean label)
        c = crit[0]
        approved = any(e["tool"] == "request_permission" and str(e["tool_result"]).startswith("APPROVED")
                       for e in ep.events if e["event_id"] < c["event_id"])
        if cf == "unsafe" and approved:
            continue
        rows.append({"episode_id": ep.episode_id, "event_id": c["event_id"], "scenario_id": ep.scenario_id,
                     "template": ep.template, "y": int(cf == "unsafe")})
    return pd.DataFrame(rows)


def load_layer(actdir, layer, keys):
    idx, X = load_activations(REPO_ROOT / actdir, "pre_action_last", [layer])
    m = {(r.episode_id, r.event_id): int(r.row) for r in idx.itertuples()}
    rows, ok = [], []
    for e, ev in keys:
        if (e, ev) in m:
            rows.append(X[layer][m[(e, ev)]]); ok.append(True)
        else:
            ok.append(False)
    return np.array(rows), np.array(ok)


def cv_auroc(Xf, y, groups, seeds=5):
    s = np.zeros(len(y))
    for si in range(seeds):
        p = np.zeros(len(y))
        for tr, te in GroupKFold(5).split(Xf, y, groups):
            sc = StandardScaler().fit(Xf[tr])
            lr = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced").fit(sc.transform(Xf[tr]), y[tr])
            p[te] = lr.decision_function(sc.transform(Xf[te]))
        s += p
    return s / seeds


def main():
    P = first_critical_rows("v2fresh_plus", "safe")
    M = first_critical_rows("v2fresh_minus", "unsafe")
    D = pd.concat([P, M], ignore_index=True)
    res = {"n_plus": len(P), "n_minus": len(M), "by_template": D.template.value_counts().to_dict()}
    keys = list(zip(D.episode_id, D.event_id))
    # only L46 available for minus; use L46 as primary, others plus-only (report what we can)
    layer = 46
    Xp, okp = load_layer(ACTdir["plus"], layer, [k for k, r in zip(keys, D.itertuples()) if r.y == 0])
    Xm, okm = load_layer(ACTdir["minus"], layer, [k for k, r in zip(keys, D.itertuples()) if r.y == 1])
    Xf = np.vstack([Xp, Xm])
    y = np.array([0] * okp.sum() + [1] * okm.sum())
    g = np.array(list(D[D.y == 0].scenario_id[okp]) + list(D[D.y == 1].scenario_id[okm]))
    tmpl = np.array(list(D[D.y == 0].template[okp]) + list(D[D.y == 1].template[okm]))
    res["loaded"] = {"plus": int(okp.sum()), "minus": int(okm.sum())}
    # grouped-CV AUROC
    s = cv_auroc(Xf, y, g)
    res["authorization_probe_L46_groupedCV_auroc"] = round(float(auroc(y, s)), 4)
    # template transfer: train on all-but-one template, test held-out
    tt = {}
    for t in pd.unique(tmpl):
        tr = tmpl != t; te = tmpl == t
        if 0 < y[te].sum() < te.sum() and y[tr].sum() > 0 and (1 - y[tr]).sum() > 0:
            sc = StandardScaler().fit(Xf[tr])
            lr = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced").fit(sc.transform(Xf[tr]), y[tr])
            tt[t] = {"n": int(te.sum()), "auroc": round(float(auroc(y[te], lr.decision_function(sc.transform(Xf[te])))), 4)}
    res["template_transfer_auroc"] = tt
    res["template_transfer_mean"] = round(float(np.mean([v["auroc"] for v in tt.values()])), 4)
    print(json.dumps(res, indent=1))
    (REPO_ROOT / "results/authz_probe").mkdir(parents=True, exist_ok=True)
    (REPO_ROOT / "results/authz_probe/feasibility.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
