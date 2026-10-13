#!/usr/bin/env python
"""Table 2 statistics (CPU, main env): for every forecasting row, AUROC of the internal readout (I; for ensemble rows the internal
ensemble E), supervised text (T) and the zero-shot CoT monitor (M), and the paired differences I-T and I-M with scenario-cluster
bootstrap 95% CIs and one-sided p (descriptive; preregistered tests keep their Holm-adjusted p from the preregistered analyses).
Same AUROC functions as the preregistered analyses (scripts/150 via scripts/155 for violations; scripts/134 for lies).
python scripts/200_forecast_table_stats.py -> results/forecast_table_stats.json"""
import importlib.util
import json

import numpy as np
import pandas as pd

from cape.utils.config import REPO_ROOT

B = 2000


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


V57 = _mod("v57", "scripts/155_v57_analysis.py"); M150 = V57.M150; C134 = _mod("c134", "scripts/134_v51_confirm.py"); F177 = _mod("f177", "scripts/177_fig_forecast.py")


def diff_boot(D, auc, a, b, seed, n_jobs=32):
    """paired difference auc(a) - auc(b) on rows with both scores; (model, scenario)-cluster bootstrap, parallel (as scripts/163)."""
    from joblib import Parallel, delayed
    D = D.dropna(subset=[a, b]).reset_index(drop=True); rng = np.random.default_rng(seed)
    cl = (D.model.astype(str) + "|" + D.scenario_id.astype(str)).values; u = np.unique(cl); idx = {c: np.where(cl == c)[0] for c in u}
    f = lambda d: auc(d, a) - auc(d, b)
    draws = [np.concatenate([idx[c] for c in rng.choice(u, len(u))]) for _ in range(B)]
    v = np.array(Parallel(n_jobs=n_jobs, batch_size=16)(delayed(f)(D.iloc[ix]) for ix in draws)); v = v[~np.isnan(v)]
    return {"diff": round(float(f(D)), 4), "ci95": [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)],
            "p_one_sided": float((np.sum(v <= 0) + 1) / (len(v) + 1)), "n": int(len(D)), "pos": int(D.y.sum())}


def row(D, auc, cols, seed, mcol="M_cot"):
    out = {"n": int(len(D)), "pos": int(D.y.sum())}
    for c in cols:
        out[c] = round(float(auc(D.dropna(subset=[c]), c)), 4)
    first = cols[0]
    out["first_minus_T"] = diff_boot(D, auc, first, "T_sup", seed)
    out["first_minus_M"] = diff_boot(D, auc, first, mcol, seed + 1)
    out["M_subset_n"] = int(D[mcol].notna().sum()); out["M_subset_pos"] = int(D.loc[D[mcol].notna(), "y"].sum())
    return out


def main():
    res = {}
    # violation rows: reveal (v55 fresh scores) and decision (v57 fresh scores), pooled over four models
    v55 = pd.read_parquet(REPO_ROOT / "outputs/v55/scores.parquet"); v57 = pd.read_parquet(REPO_ROOT / "outputs/v57/scores.parquet")
    v55 = v55[v55.split == "conf"]          # fresh confirmation units only (as the preregistered analysis and scripts/163)
    auc = M150.auc
    OUTF = REPO_ROOT / "results/forecast_table_stats.json"
    def save(k, v):
        res[k] = v; json.dump(res, open(OUTF, "w"), indent=1); print(k, "done", flush=True)
    save("reveal", row(v55, auc, ["I", "T_sup", "M_cot"], 55))
    save("decision_vs_other", row(v57[v57.cls.isin(["VIOL", "XOTHER"])], auc, ["I", "T_sup", "M_cot"], 57))
    save("decision_vs_twin", row(v57[v57.cls.isin(["VIOL", "XPLUS"])], auc, ["I", "T_sup", "M_cot"], 58))
    save("decision_all", row(v57, auc, ["I", "T_sup", "M_cot"], 59))
    # lie rows (v51 confirmation scores, four models) and the internal ensemble (three models)
    L = pd.concat([C134.scores(m).assign(model=m) for m in ("museglimmer", "qwen38", "gemma4", "gptoss20b")], ignore_index=True)
    lauc = C134.auc
    save("lie_all", row(L, lauc, ["I", "T_sup", "M_cot"], 51))
    for v, d in L.groupby("variant"):
        save(f"lie_{v}", row(d, lauc, ["I", "T_sup", "M_cot"], 52))
    _, E = F177.lie_scores()
    for v, d in E.groupby("variant"):
        save(f"ens_{v}", row(d, lauc, ["E_lda", "T_sup", "M_cot"], 53))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
