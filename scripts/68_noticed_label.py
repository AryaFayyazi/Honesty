#!/usr/bin/env python
"""Split informed actions into NOTICED vs UNNOTICED, automatically and template-free.

python scripts/68_noticed_label.py actor=gptoss20b

For each episode, replay the agent's tool calls in the matched partner environment, take the revealing observation
(first observation that differs from the partner), and extract the distinguishing content words: tokens in this
world's observation but not in the partner's. An informed action is NOTICED if the agent's own reasoning/content between
the reveal and that action (inclusive) mentions one of those words. Output: outputs/xm_feats/noticed_<actor>.parquet
(episode_id, event_id, informed, noticed, n_key, keys).
"""
import json
import re

import pandas as pd
from omegaconf import OmegaConf

from cape.envs.base import MockEnv
from cape.utils.config import REPO_ROOT, load_config

D = OmegaConf.create({"actor": "gptoss20b", "bench": "v2fresh"})
W = re.compile(r"[a-z][a-z_\-]{3,}")
STOP = {"metadata", "content", "owner", "with", "this", "that", "from", "file", "files", "none", "true", "false"}


def words(t):
    return set(W.findall((t or "").lower())) - STOP


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    S = {}
    for l in open(REPO_ROOT / f"outputs/capebench/{cfg.bench}/scenarios.jsonl"):
        s = json.loads(l); S[s["instance_id"]] = s
    pair = {}
    for s in S.values():
        pair.setdefault(s["counterfactual_pair_id"], []).append(s["instance_id"])
    pre = cfg.bench if cfg.actor in ("qwen38", "qwenexact") else f"xm_{cfg.actor}_{cfg.bench}"   # Qwen rollouts: <bench>_{minus,plus}
    rows = []
    for sfx in ("minus", "plus", "plus23"):
        p = REPO_ROOT / f"outputs/rollouts/{pre}_{sfx}.parquet"
        if not p.exists():
            continue
        for ep in pd.read_parquet(p).itertuples():
            spec = S[ep.instance_id]
            other = [i for i in pair[spec["counterfactual_pair_id"]] if i != ep.instance_id][0]
            penv = MockEnv(S[other]); keys = set(); R = None
            for e in ep.events:
                if not (e["is_tool_call"] and e["tool"]):
                    continue
                try:
                    a = json.loads(e["args_json"]) if e["args_json"] else None
                except Exception:
                    a = None
                pobs = penv.step(e["tool"], a)[0] if a is not None else None
                if R is None and e["obs_differs_from_partner"]:
                    R = e["event_id"]; keys = words(e["tool_result"]) - words(pobs)
            said = ""
            for e in ep.events:
                if not (e["is_tool_call"] and e["tool"]):
                    continue
                if R is not None and e["event_id"] > R:
                    said += " " + (e["reasoning_text"] or "") + " " + (e["content_text"] or "")
                rows.append({"episode_id": ep.episode_id, "event_id": e["event_id"],
                             "informed": int(R is not None and e["event_id"] > R),
                             "noticed": int(R is not None and e["event_id"] > R and bool(keys & words(said))),
                             "n_key": len(keys), "keys": " ".join(sorted(keys))[:300]})
    D_ = pd.DataFrame(rows)
    D_.to_parquet(REPO_ROOT / f"outputs/xm_feats/noticed_{cfg.actor}{'' if cfg.bench == 'v2fresh' else '_' + cfg.bench}.parquet")
    inf = D_[D_.informed == 1]
    print(cfg.actor, "informed actions", len(inf), "noticed share", round(inf.noticed.mean(), 3),
          "median #keys", inf.n_key.median())
    print(inf.drop_duplicates("episode_id")["keys"].head(12).to_string())


if __name__ == "__main__":
    main()
