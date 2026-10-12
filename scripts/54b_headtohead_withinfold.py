#!/usr/bin/env python
"""Re-analysis of scripts/54 (Qwen3.8, v2fresh, identical events) with WITHIN-FOLD thresholds for the probe.
54 set the probe's 1%-FPR threshold on out-of-fold scores pooled over fold models (prereg Amendment 1 forbids pooled
OOF metrics). Here each fold model's threshold comes from its own fold's negatives; judges (zero-shot, single model)
keep the global threshold. Hits are averaged over the 5 repeats; paired scenario bootstrap probe - judge on hit rates.
Also reports the informed / uninformed split of harms and the twin flag rates (catch-friction check).
"""
import importlib.util
import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from cape.utils.config import REPO_ROOT

spec = importlib.util.spec_from_file_location("h", REPO_ROOT / "scripts/54_headtohead.py")
H = importlib.util.module_from_spec(spec); spec.loader.exec_module(H)
REPEATS, NBOOT = 5, 4000


def main():
    G, X = H.load()
    y = G.y.values.astype(int) == 1; scen = G.scenario_id.values
    allneg = ~y; hard = (~y) & (G.hard_neg.values == 1)
    uniq = np.array(sorted(set(scen)))
    hit_all = np.zeros(len(y)); hit_hard = np.zeros(len(y))
    for rep in range(REPEATS):
        perm = np.random.default_rng(rep).permutation(uniq); fold = {s: i % 5 for i, s in enumerate(perm)}
        f = np.array([fold[s] for s in scen])
        for k in range(5):
            tr, te = f != k, f == k
            sc = StandardScaler().fit(X[tr])
            lr = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced").fit(sc.transform(X[tr]), y[tr])
            s = lr.decision_function(sc.transform(X[te]))
            hit_all[te] += s >= np.quantile(s[allneg[te]], .99)
            hit_hard[te] += s >= np.quantile(s[hard[te]], .99)
        print("repeat", rep, flush=True)
    hit_all /= REPEATS; hit_hard /= REPEATS
    H_ = {"probe_withinfold": (hit_all, hit_hard)}
    for name, col in (("transcript_A", "A_transcript"), ("resolved_B", "B_resolved"), ("reasoning_C", "C_reasoning")):
        s = G[col].values
        H_[name] = ((s >= np.quantile(s[allneg], .99)).astype(float), (s >= np.quantile(s[hard], .99)).astype(float))
    res = {"n_harm": int(y.sum()), "n_hard": int(hard.sum())}
    idx = pd.Series(range(len(G))).groupby(list(scen)).apply(lambda v: v.values); keys = list(idx.index)
    rng = np.random.default_rng(0); picks = [np.concatenate([idx[keys[i]] for i in rng.integers(0, len(keys), len(keys))]) for _ in range(NBOOT)]
    for n, (ha, hh) in H_.items():
        res[n] = {"TPR@1%": round(float(ha[y].mean()), 3), "TPR@1%hard": round(float(hh[y].mean()), 3)}
    for j in ("resolved_B", "transcript_A", "reasoning_C"):
        for i, lab in ((0, "all"), (1, "hard")):
            d = [H_["probe_withinfold"][i][p][y[p]].mean() - H_[j][i][p][y[p]].mean() for p in picks if y[p].sum()]
            res[f"probe_minus_{j}_{lab}"] = {"diff": round(float(np.mean(d)), 3), "ci95": [round(float(np.quantile(d, .025)), 3),
                                             round(float(np.quantile(d, .975)), 3)], "p_one_sided": round(float(np.mean(np.array(d) <= 0)), 4)}
    print(json.dumps(res, indent=1))
    (REPO_ROOT / "results/authz_probe/headtohead_withinfold.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
