#!/usr/bin/env python
"""Label audit helper (required before scoring, prereg v2/v3): one line per unsafe episode with the unsafe action,
the permission decisions received before it, and whether the causal fact was revealed first; grouped by template and
action pattern so every distinct violation class is read.

python scripts/audit_unsafe.py outputs/rollouts/v3aware_reasoning_minus.parquet [--full N]
"""
import argparse
import re

import pandas as pd


def pattern(e):
    a = re.sub(r"\d+", "#", (e["args_json"] or ""))
    return f"{e['tool']} {a[:90]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("traj")
    ap.add_argument("--full", type=int, default=0, help="print N full unsafe transcripts per template")
    a = ap.parse_args()
    eps = pd.read_parquet(a.traj)
    x = eps[eps.cf_value == "unsafe"]
    print(f"{len(x)} x- episodes; unsafe {int(x.unsafe_episode.sum())}; status {x.status.value_counts().to_dict()}")
    rows = []
    for ep in x[x.unsafe_episode].itertuples():
        evs = list(ep.events)
        u = next(e for e in evs if e["unsafe_action"])
        perms = [(e["tool_result"] or "").split()[0] if e["tool_result"] else "?" for e in evs
                 if e["tool"] == "request_permission" and e["event_id"] < u["event_id"]]
        rv = ep.reveal_event
        rows.append({"episode_id": ep.episode_id, "template": ep.template, "t_u": u["event_id"],
                     "informed": bool(rv == rv and rv < u["event_id"]), "viol": u["violations"],
                     "perms": "|".join(perms) or "-", "pattern": pattern(u)})
    R = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 110)
    print(R.groupby(["template", "informed", "viol", "perms"]).size().to_string())
    print("\nDistinct action patterns:")
    print(R.groupby(["template", "pattern"]).size().to_string())
    for t, g in R.groupby("template"):
        for eid in g.episode_id.head(a.full):
            ep = x[x.episode_id == eid].iloc[0]
            print(f"\n######## {eid}")
            for e in ep.events:
                flag = " [UNSAFE]" if e["unsafe_action"] else ""
                if e["is_tool_call"]:
                    print(f"  t={e['event_id']} THINK: {(e['reasoning_text'] or '')[-500:]!r}")
                    print(f"      ACT: {e['tool']} {(e['args_json'] or '')[:300]}{flag}")
                    print(f"      OBS: {(e['tool_result'] or '')[:250]!r}")
                else:
                    print(f"  t={e['event_id']} FINAL: {(e['content_text'] or '')[:400]!r}")


if __name__ == "__main__":
    main()
