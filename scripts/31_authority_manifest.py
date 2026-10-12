#!/usr/bin/env python
"""Decision-point manifest for the authority-sensitivity study (data preparation only; no model is trained or run).

python scripts/31_authority_manifest.py

Lists, from saved rollouts, two kinds of decision points:
  harm_x-   : the first harmful decision of an informed violation in an unauthorized (x-) world
  auth_x+   : an authorised critical decision (critical and not unsafe) in an authorized (x+) world
Each row carries the keys needed to rebuild the exact token prefix from outputs/rollouts/<set>_tokens.parquet
(prompt_len of the event). Split: templates in HELDOUT are never used for any fitting; identity-collision scenarios
are excluded. Output: results/authority/manifest.parquet and manifest_summary.json.
"""
import json

import pandas as pd

from cape.utils.config import REPO_ROOT

SETS = [("v2fresh_minus", "v2fresh"), ("v2fresh_plus", "v2fresh"), ("v3aware_reasoning_minus", "v3aware_reasoning"),
        ("v3aware_internal_minus", "v3aware_internal"), ("v6resp_minus", "v6resp")]
HELDOUT = {"auth_repo_access", "con_cloud_cost"}
FRESH = [("v4fresh_minus", "v4fresh")]  # never used for fitting; in-distribution held-out evaluation


def rows_for(stem, bench, split_override=None):
    col = set(json.load(open(REPO_ROOT / "results/validity/identity_collisions.json"))[bench if bench in
              json.load(open(REPO_ROOT / "results/validity/identity_collisions.json")) else "v2fresh"])
    eps = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{stem}.parquet")
    out = []
    for ep in eps.itertuples():
        if ep.scenario_id in col:
            continue
        ev = list(ep.events)
        if ep.cf_value == "unsafe" and ep.unsafe_episode:
            rv, tu = ep.reveal_event, int(ep.first_unsafe_event)
            if rv == rv and rv < tu:
                kind, t = "harm_x-", tu
            else:
                continue
        elif ep.cf_value == "safe":
            crit = [e for e in ev if e["critical"] and not e["unsafe_action"]]
            if not crit:
                continue
            kind, t = "auth_x+", crit[0]["event_id"]
        else:
            continue
        split = split_override or ("heldout_template" if ep.template in HELDOUT else "train")
        out.append({"set": stem, "bench": bench, "episode_id": ep.episode_id, "scenario_id": ep.scenario_id,
                    "template": ep.template, "event_id": t, "kind": kind, "split": split,
                    "prompt_len": int(ev[t]["prompt_len"]), "tool": ev[t]["tool"]})
    return out


def main():
    rows = []
    for stem, bench in SETS:
        rows += rows_for(stem, bench)
    for stem, bench in FRESH:
        rows += rows_for(stem, bench, split_override="fresh_eval")
    M = pd.DataFrame(rows)
    out = REPO_ROOT / "results/authority"
    out.mkdir(parents=True, exist_ok=True)
    M.to_parquet(out / "manifest.parquet")
    summ = M.groupby(["split", "kind", "template"]).size().unstack(fill_value=0)
    print(summ.to_string())
    (out / "manifest_summary.json").write_text(json.dumps(M.groupby(["split", "kind"]).size().to_dict().__repr__()))


if __name__ == "__main__":
    main()
