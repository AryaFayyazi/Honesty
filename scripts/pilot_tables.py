#!/usr/bin/env python
"""Collect pilot result CSVs into markdown tables (results/pilot/pilot_tables.md).

The interpretation in pilot_summary.md is written by hand from these tables; this script never writes conclusions.
"""
from pathlib import Path

import pandas as pd

from cape.utils.config import REPO_ROOT

R = REPO_ROOT / "results" / "pilot"


def fmt_ci(a, lo, hi):
    return f"{a:.3f} [{lo:.3f}, {hi:.3f}]" if pd.notna(a) else "n/a"


def main():
    out = []
    ew = R / "early_warning.csv"
    if ew.exists():
        d = pd.read_csv(ew)
        for (pop, split), g in d.groupby(["population", "split"]):
            out.append(f"\n### Early warning — population={pop}, holdout={split}\n")
            cols = ["method", "n_pos", "auroc", "auroc_d>=1", "auroc_d>=2", "tpr_at_1fpr", "realised_fpr",
                    "detection_rate@ep_fpr0.1", "H_median@ep_fpr0.1", "episode_false_alarm_rate@ep_fpr0.1"]
            g = g.copy()
            g["auroc"] = [fmt_ci(a, *eval(c)) if isinstance(c, str) else fmt_ci(a, *c)
                          for a, c in zip(g.auroc, g.auroc_ci)]
            out.append(g[[c for c in cols if c in g]].to_markdown(index=False, floatfmt=".3f"))
    for name in ["decision_prediction.csv", "baseline_comparison.csv", "patching_effect.csv"]:
        f = R / name
        if f.exists():
            out.append(f"\n### {name}\n")
            out.append(pd.read_csv(f).to_markdown(index=False, floatfmt=".3f"))
    for f in sorted(R.glob("layer_auc_*.csv")):
        out.append(f"\n### {f.name}\n")
        out.append(pd.read_csv(f).to_markdown(index=False, floatfmt=".3f"))
    (R / "pilot_tables.md").write_text("\n".join(out))
    print("wrote", R / "pilot_tables.md")


if __name__ == "__main__":
    main()
