#!/usr/bin/env python
"""Consolidated cross-model table (seed-balanced design): observability test + epistemic compositional gate.

python scripts/67_xm_table.py        -> results/xm/summary_table.md + summary.json
"""
import json
from pathlib import Path

from cape.utils.config import REPO_ROOT

R = REPO_ROOT / "results/xm"
ACTORS = [("qwen38", "_seedsall"), ("gemma4", ""), ("gptoss20b", ""), ("museglimmer", ""),
          ("rdqwen-gemma4", ""), ("rdqwen-gptoss20b", ""), ("rdqwen-museglimmer", "")]


def j(p):
    p = R / p
    return json.load(open(p)) if p.exists() else None


def main():
    rows, out = [], {}
    hdr = ("| actor | harms | informed share | world AUROC uninformed / informed | ECG TPR@1% (all / hard) | "
           "mono TPR@1% (all / hard) | ECG informed TPR@1% hard | verify-request rate | LOTO TPR@1% ECG / mono | "
           "episode-conformal a=0.05: false-block, TPR |")
    rows += [hdr, "|" + "---|" * hdr.count("|")[:-1] if False else "|" + "---|" * (hdr.count("|") - 1)]
    for a, sfx in ACTORS:
        e = j(f"ecg_{a}_v2fresh_mean8_L2{sfx}.json"); o = j(f"observability_{a}_v2fresh_pre_L2{sfx}.json")
        if e is None:
            continue
        i = e["in_distribution"]; dc = e.get("deploy_episode_conformal", {}).get("0.05", {})
        ow = (f"{o['uninformed']['world_auroc_within_fold']:.3f} / {o['informed']['world_auroc_within_fold']:.3f}"
              if o and "uninformed" in o and "informed" in o else "-")
        rows.append(f"| {a} | {e['n_harm']} | {e['informed_harm_frac']:.2f} | {ow} | "
                    f"{i['ecg']['all']['TPR@1%compliant']:.3f} / {i['ecg']['all']['TPR@1%hard']:.3f} | "
                    f"{i['mono']['all']['TPR@1%compliant']:.3f} / {i['mono']['all']['TPR@1%hard']:.3f} | "
                    f"{i['ecg']['informed']['TPR@1%hard']} | {i['ecg']['verify_request_rate_unverified_safe_crit']} | "
                    f"{e['loto_mean_TPR@1%compliant']['ecg']:.3f} / {e['loto_mean_TPR@1%compliant']['mono']:.3f} | "
                    f"{dc.get('episode_false_block', '-')}, {dc.get('TPR', '-')} |")
        out[a] = {"ecg": e, "observability": o}
    md = "\n".join(rows)
    print(md)
    (R / "summary_table.md").write_text(md + "\n")
    (R / "summary.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
