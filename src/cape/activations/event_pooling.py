"""Event-boundary representations (brief section 19).

A  pre_action_last   last token before the action (<tool_call> / first answer token)   [primary]
B  pre_action_mean8  mean of the final 8 generated tokens up to and including A
C  pre_action_mean32 mean of the final 32 generated tokens up to and including A
D  action_start      the <tool_call> token itself
-  turn_start        last prompt token of the turn (before any reasoning is generated)
-  think_end         the </think> token
-  post_action       last token of the action (option C of the action representation)
-  action_mean       mean over the action tokens (option A of the action representation)
E/F (delta, [h, delta]) are computed offline from A in cape.probes.
"""
from __future__ import annotations

import torch

POINT_POOLINGS = ["pre_action_last", "turn_start", "think_end", "action_start", "post_action"]
WINDOW_POOLINGS = ["pre_action_mean8", "pre_action_mean32", "action_mean"]
ALL_POOLINGS = POINT_POOLINGS + WINDOW_POOLINGS


def _int(x):
    return None if x is None or x != x else int(x)  # parquet may return float64 (NaN for None)


def event_positions(ev: dict) -> dict:
    d = _int(ev["decision_pos"])
    g0 = _int(ev["prompt_len"])
    ge = _int(ev["gen_end_pos"])
    a = _int(ev["action_start_pos"]) if _int(ev["action_start_pos"]) is not None else ge
    te = _int(ev["think_end_pos"]) if _int(ev["think_end_pos"]) is not None else d
    return {
        "pre_action_last": d, "turn_start": _int(ev["turn_start_pos"]), "think_end": te, "action_start": a,
        "post_action": ge,
        "pre_action_mean8": (max(d - 7, g0), d), "pre_action_mean32": (max(d - 31, g0), d),
        "action_mean": (a, ge),
    }


def capture_requests(events: list[dict], poolings: list[str]) -> dict:
    pos = [event_positions(e) for e in events]
    req = {}
    for p in poolings:
        if p in POINT_POOLINGS:
            req[p] = ("point", torch.tensor([x[p] for x in pos], dtype=torch.long))
        elif p in WINDOW_POOLINGS:
            req[p] = ("window", [x[p] for x in pos])
        else:
            raise ValueError(p)
    return req
