"""Matched counterfactual prefixes for activation patching.

Given an x- episode and a decision index t*, the counterfactual prefix is built by replaying the *same* agent tokens
(reasoning + actions) for turns < t* and re-rendering each tool response from the counterfactual environment. With
t* = first decision after the causal variable was revealed, the two prefixes differ only inside one tool response.
The procedure is validated by rebuilding the original prefix from its own environment and requiring token equality.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from cape.agents.actor import ChatFormatter
from cape.agents.rollout import PARSE_ERROR_OBS
from cape.envs.base import MockEnv


def prior_actions(events: list[dict], t: int) -> list[tuple]:
    acts = []
    for e in events[:t]:
        if e["is_tool_call"] and e["parse_error"] is None:
            acts.append((e["tool"], json.loads(e["args_json"]) if e["args_json"] else {}))
        else:
            acts.append((None, None))
    return acts


def build_prefix(fmt: ChatFormatter, ids: list[int], events: list[dict], t: int, spec: dict) -> list[int]:
    """Token prefix up to (and including) the generation prompt of decision t, with observations from ``spec``."""
    env = MockEnv(spec)
    out = list(ids[:int(events[0]["prompt_len"])])
    for e, (name, args) in zip(events[:t], prior_actions(events, t)):
        gen = ids[int(e["prompt_len"]):int(e["gen_end_pos"]) + 1]
        out += gen
        obs = env.step(name, args)[0] if name is not None else PARSE_ERROR_OBS
        out += fmt.tool_response_ids(obs, close_assistant=gen[-1] != fmt.ids.im_end)
    return out


def common_suffix_len(a: list[int], b: list[int]) -> int:
    n = 0
    while n < min(len(a), len(b)) and a[-1 - n] == b[-1 - n]:
        n += 1
    return n


def common_prefix_len(a, b) -> int:
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return n


@dataclass
class Site:
    site_id: str
    episode_id: str
    pair_id: str
    scenario_id: str
    family: str
    t_star: int
    T_harm: int | None
    minus: list          # x- prefix tokens (recipient for forward patch)
    plus: list           # x+ prefix tokens
    nuis: list | None    # nuisance-variant x- prefix (None if identical to minus)
    suffix_len: int      # common suffix of minus/plus (patched positions, lexically identical)
    nuis_suffix_len: int
    diff_tokens: int     # tokens that differ between minus and plus prefixes
    spec_minus: dict
    spec_plus: dict
    actions: list


def make_site(fmt, ep, ids, spec_minus, spec_plus, spec_nuis, max_suffix: int = 512) -> Site | None:
    events = list(ep.events)
    r = ep.reveal_event
    if r is None or r != r:  # NaN
        return None
    t = int(r) + 1
    if t >= len(events):
        return None
    assert ids[:int(events[t]["prompt_len"])] == build_prefix(fmt, ids, events, t, spec_minus), \
        f"prefix reconstruction mismatch for {ep.episode_id}"
    minus = ids[:int(events[t]["prompt_len"])]
    plus = build_prefix(fmt, ids, events, t, spec_plus)
    nuis = build_prefix(fmt, ids, events, t, spec_nuis) if spec_nuis else None
    if nuis == minus:
        nuis = None
    ls = min(common_suffix_len(minus, plus), max_suffix)
    lp = common_prefix_len(minus, plus)
    return Site(site_id=f"{ep.episode_id}@t{t}", episode_id=ep.episode_id, pair_id=ep.counterfactual_pair_id,
                scenario_id=ep.scenario_id, family=ep.scenario_family, t_star=t,
                T_harm=None if ep.first_unsafe_event is None or ep.first_unsafe_event != ep.first_unsafe_event
                else int(ep.first_unsafe_event),
                minus=minus, plus=plus, nuis=nuis, suffix_len=ls,
                nuis_suffix_len=min(common_suffix_len(minus, nuis), max_suffix) if nuis else 0,
                diff_tokens=len(minus) - lp - common_suffix_len(minus, plus),
                spec_minus=spec_minus, spec_plus=spec_plus, actions=prior_actions(events, t))
