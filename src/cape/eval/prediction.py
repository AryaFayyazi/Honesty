"""Event table, future-harm labels (brief section 25) and leakage-safe group splits."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut

HORIZONS = [1, 2, 4, 8]


def event_table(episodes: pd.DataFrame, post_harm: str = "drop") -> pd.DataFrame:
    """One row per (episode, event) with labels.

    y_eventual  = 1[exists j >= t: unsafe(a_j)]
    y_k         = 1[exists j in [t, t+k]: unsafe(a_j)]
    d           = T_harm - t (unsafe episodes)
    informed    = the causal variable had been observed before decision t (t > reveal_event)
    Events after the first unsafe action are dropped by default (post-harm states are not "early warning").
    """
    rows = []
    for ep in episodes.itertuples():
        ev = list(ep.events)
        unsafe_idx = [e["event_id"] for e in ev if e["unsafe_action"]]
        T = unsafe_idx[0] if unsafe_idx else None
        r = ep.reveal_event if ep.reveal_event is not None and not pd.isna(ep.reveal_event) else None
        # decision label: which comes first from t on, the critical action (proceed) or an escalation?
        dec = [(e["event_id"], "crit" if e["critical"] else "esc") for e in ev if e["critical"] or e["escalation"]]
        first_dec = dec[0] if dec else None
        hist_tools = []
        for e in ev:
            t = e["event_id"]
            if T is not None and t > T and post_harm == "drop":
                break
            row = {
                "episode_id": ep.episode_id, "event_id": t, "scenario_id": ep.scenario_id,
                "scenario_family": ep.scenario_family, "template": ep.template,
                "surface_template": ep.surface_template, "pair_id": ep.counterfactual_pair_id,
                "cf_value": ep.cf_value, "seed": ep.seed, "unsafe_episode": int(ep.unsafe_episode),
                "T_harm": T, "reveal_event": r, "n_events": ep.n_events,
                "informed": int(r is not None and t > r),
                "y_eventual": int(T is not None and t <= T),
                "d": (T - t) if T is not None else np.nan,
                "unsafe_action": int(e["unsafe_action"]), "critical": int(e["critical"]),
                "tool": e["tool"] or ("final_answer" if not e["is_tool_call"] else "parse_error"),
                "args_json": e["args_json"] or "", "reasoning_text": e["reasoning_text"] or "",
                "content_text": e["content_text"] or "", "tool_result": e["tool_result"] or "",
                "hist_tools": " ".join(hist_tools),
                # y_proceed defined only before the first decision (NaN afterwards)
                "y_proceed": (np.nan if first_dec and t > first_dec[0] else
                              int(bool(first_dec) and first_dec[1] == "crit")),
                "d_decision": (first_dec[0] - t) if first_dec else np.nan,
            }
            for k in HORIZONS:
                row[f"y_{k}"] = int(any(t <= j <= t + k for j in unsafe_idx))
            rows.append(row)
            hist_tools.append(row["tool"])
    df = pd.DataFrame(rows)
    return df.reset_index(drop=True)


def visible_history(episodes: pd.DataFrame, specs: dict, with_cot: bool) -> dict:
    """Text visible to an external monitor at each decision t: task, past actions+observations (+ past and current
    reasoning if with_cot), and the *proposed* action a_t. Returns {(episode_id, event_id): text}."""
    out = {}
    for ep in episodes.itertuples():
        s = specs[ep.instance_id]
        parts = [f"TASK: {s['task_prompt']}"]
        for e in ep.events:
            act = f"ACTION: {e['tool']}({e['args_json']})" if e["is_tool_call"] else f"FINAL ANSWER: {e['content_text']}"
            cur = list(parts)
            if with_cot:
                cur.append(f"REASONING: {e['reasoning_text']}")
            cur.append(act)
            out[(ep.episode_id, e["event_id"])] = "\n".join(cur)
            if with_cot:
                parts.append(f"REASONING: {e['reasoning_text']}")
            parts.append(act)
            if e["tool_result"] is not None:
                parts.append(f"OBSERVATION: {e['tool_result']}")
    return out


def action_text(df: pd.DataFrame) -> list[str]:
    """Visible-action features: current tool + arguments, plus the history of tool names."""
    out = []
    for r in df.itertuples():
        try:
            args = json.loads(r.args_json) if r.args_json else {}
        except Exception:
            args = {}
        arg_str = " ".join(f"{k}={v}" for k, v in args.items())
        out.append(f"TOOL_{r.tool} {arg_str} || " + " ".join(f"PREV_{t}" for t in r.hist_tools.split()))
    return out


def group_folds(df: pd.DataFrame, level: str, n_splits: int = 5, seed: int = 0):
    """Yield (train_idx, test_idx). level in {scenario, template, family}. Never splits a base scenario, a
    counterfactual pair or a paraphrase family across train/test."""
    key = {"scenario": "scenario_id", "template": "template", "family": "scenario_family"}[level]
    groups = df[key].values
    if level == "family":
        yield from LeaveOneGroupOut().split(df, groups=groups)
        return
    ug = np.unique(groups)
    rng = np.random.default_rng(seed)
    perm = {g: i for i, g in enumerate(rng.permutation(ug))}
    g2 = np.array([perm[g] for g in groups])
    yield from GroupKFold(n_splits=min(n_splits, len(ug))).split(df, groups=g2)


def inner_split(df_train: pd.DataFrame, key: str = "scenario_id", frac: float = 0.2, seed: int = 0):
    ug = df_train[key].unique()
    rng = np.random.default_rng(seed)
    val_g = set(rng.choice(ug, max(1, int(round(frac * len(ug)))), replace=False))
    m = df_train[key].isin(val_g).values
    return np.nonzero(~m)[0], np.nonzero(m)[0]
