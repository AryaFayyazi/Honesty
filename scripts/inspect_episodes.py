#!/usr/bin/env python
"""Render rollouts as readable transcripts for manual inspection.

python scripts/inspect_episodes.py outputs/rollouts/pilot.parquet [--n 20] [--filter unsafe|safe|xminus] [--max-reason 600]
"""
import argparse
import json

import pandas as pd


def render(ep, max_reason=600):
    lines = [f"=== {ep.episode_id} | family={ep.scenario_family} cf={ep.cf_value} status={ep.status} "
             f"unsafe={ep.unsafe_episode} T_u={ep.first_unsafe_event} crit={ep.critical_done} "
             f"escalated={ep.escalated} reveal={ep.reveal_event} success={ep.success}"]
    for e in ep.events:
        flag = " [UNSAFE]" if e["unsafe_action"] else (" [critical]" if e["critical"] else "")
        r = (e["reasoning_text"] or "").strip().replace("\n", " ")
        lines.append(f"  t={e['event_id']} ({e['n_gen_tokens']} tok) THINK: {r[:max_reason]}{'...' if len(r) > max_reason else ''}")
        if e["is_tool_call"]:
            lines.append(f"      ACT: {e['tool']} {e['args_json']}{flag}")
            obs = (e["tool_result"] or "").replace("\n", " | ")
            lines.append(f"      OBS{' (differs from partner)' if e['obs_differs_from_partner'] else ''}: {obs[:400]}")
        else:
            lines.append(f"      FINAL: {(e['content_text'] or '')[:500]}")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--filter", default=None)
    ap.add_argument("--family", default=None)
    ap.add_argument("--max-reason", type=int, default=600)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    df = pd.read_parquet(a.path)
    if a.filter == "unsafe":
        df = df[df.unsafe_episode]
    elif a.filter == "safe":
        df = df[~df.unsafe_episode]
    elif a.filter == "xminus":
        df = df[df.cf_value == "unsafe"]
    if a.family:
        df = df[df.scenario_family == a.family]
    for ep in df.sample(min(a.n, len(df)), random_state=a.seed).itertuples():
        print(render(ep, a.max_reason))
        print()
