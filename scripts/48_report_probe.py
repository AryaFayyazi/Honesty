#!/usr/bin/env python
"""Pre-registration v28: probe on report-time activations vs text judges for detecting concealing reports.

python scripts/48_report_probe.py            # frozen primary (L46, think_end) + baselines + within-template + grid
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
from cape.utils.repro import write_json

ACT = REPO_ROOT / "outputs/activations/honesty_rep_minus/L30-38-46-54-62_all"
LAYERS, POS = [30, 38, 46, 54, 62], ["think_end", "pre_action_last", "pre_action_mean32"]


def final_event_features(pos, layer, eids):
    idx, X = load_activations(ACT, pos, [layer])
    last = idx.loc[idx.groupby("episode_id").event_id.idxmax()]
    m = {r.episode_id: int(r.row) for r in last.itertuples()}
    return np.vstack([X[layer][m[e]] for e in eids]), np.array([e in m for e in eids])


def oof_scores(Xf, y, groups, seeds=5):
    s = np.zeros((seeds, len(y)))
    for si in range(seeds):
        gkf = GroupKFold(n_splits=5)
        for tr, te in gkf.split(Xf, y, groups):
            sc = StandardScaler().fit(Xf[tr])
            lr = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced")
            lr.fit(sc.transform(Xf[tr]), y[tr])
            s[si, te] = lr.decision_function(sc.transform(Xf[te]))
    return s.mean(0)


def _gidx(groups):
    import pandas as pd
    return [v.values for _, v in pd.Series(range(len(groups))).groupby(list(groups))]


def _boot_picks(gidx, n, rng):
    gi = np.array(gidx, dtype=object)
    for _ in range(n):
        yield np.concatenate([gidx[i] for i in rng.integers(0, len(gidx), len(gidx))])


def boot_auroc(y, s, groups, n=10000, seed=0):
    rng = np.random.default_rng(seed); gidx = _gidx(groups); out = []
    for pick in _boot_picks(gidx, n, rng):
        yy = y[pick]
        if 0 < yy.sum() < len(yy):
            out.append(auroc(yy, s[pick]))
    return float(np.mean(out)), [float(np.quantile(out, .025)), float(np.quantile(out, .975))]


def paired_boot(y, s1, s2, groups, n=10000, seed=0):
    rng = np.random.default_rng(seed); gidx = _gidx(groups); d = []
    for pick in _boot_picks(gidx, n, rng):
        yy = y[pick]
        if 0 < yy.sum() < len(yy):
            d.append(auroc(yy, s1[pick]) - auroc(yy, s2[pick]))
    d = np.array(d)
    return float(d.mean()), float((np.sum(d <= 0) + 1) / (len(d) + 1))


def main():
    L = pd.read_parquet(REPO_ROOT / "results/reporting/honesty_rep_labels.parquet")
    eids = L.episode_id.tolist()
    y = (1 - L.honest.values).astype(int)          # non-honest = positive
    ymis = L.misrep.values.astype(int)
    g = L.scenario_id.values
    # judge baselines from existing checker files
    J = pd.concat([pd.read_parquet(p) for p in (REPO_ROOT / "results/reporting").glob("checker_*.parquet")])
    J = J.pivot_table(index="episode_id", columns="arm", values="score", aggfunc="first")
    rep = L.episode_id.map(J.report_only).values
    rec = L.episode_id.map(J.reconcile).values
    res = {"n": len(L), "n_honest": int(L.honest.sum()), "n_misrep": int(ymis.sum())}

    # frozen primary
    Xf, ok = final_event_features("think_end", 46, eids)
    assert ok.all(), "missing activations"
    s = oof_scores(Xf, y, g)
    a, ci = boot_auroc(y, s, g)
    res["primary_probe_L46_think_end"] = {"auroc_nonhonest": a, "ci95": ci}
    for nm, js in (("report_only", rep), ("reconcile", rec)):
        m = ~np.isnan(js)
        aj, cij = boot_auroc(y[m], js[m], g[m])
        diff, p = paired_boot(y[m], s[m], js[m], g[m])
        res[f"baseline_{nm}"] = {"auroc": aj, "ci95": cij, "probe_minus_judge": diff, "p_probe_gt_judge": p}
    res["baseline_template_only"] = {"auroc": float(auroc(y, L.groupby("template").honest.transform(
        lambda x: 1 - x.mean()).values))}
    # misrep secondary
    sm = oof_scores(Xf, ymis, g)
    am, cim = boot_auroc(ymis, sm, g)
    res["secondary_misrep"] = {"probe_auroc": am, "ci95": cim,
                               "report_only_auroc": boot_auroc(ymis[~np.isnan(rep)], rep[~np.isnan(rep)], g[~np.isnan(rep)])[0],
                               "reconcile_auroc": boot_auroc(ymis[~np.isnan(rec)], rec[~np.isnan(rec)], g[~np.isnan(rec)])[0]}
    # within-template confound control
    res["within_template"] = {}
    for t in ("con_ci_green", "tp_billing_correction"):
        mt = (L.template == t).values
        if 0 < y[mt].sum() < mt.sum():
            st = oof_scores(Xf[mt], y[mt], g[mt])
            at, cit = boot_auroc(y[mt], st, g[mt])
            res["within_template"][t] = {"n": int(mt.sum()), "n_honest": int((1 - y[mt]).sum()), "probe_auroc": at,
                                         "ci95": cit, "report_only_auroc": float(auroc(y[mt][~np.isnan(rep[mt])], rep[mt][~np.isnan(rep[mt])])) if (~np.isnan(rep[mt])).sum() else None}
    # exploratory grid (descriptive)
    grid = {}
    for p in POS:
        for l in LAYERS:
            Xg, okg = final_event_features(p, l, eids)
            grid[f"{p}_L{l}"] = round(boot_auroc(y, oof_scores(Xg, y, g), g, n=1000)[0], 3)
    res["exploratory_grid_auroc_nonhonest"] = grid
    print(json.dumps(res, indent=1))
    write_json(REPO_ROOT / "results/v28/v28_report_probe.json", res)


if __name__ == "__main__":
    main()
