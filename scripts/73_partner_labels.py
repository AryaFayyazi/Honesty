#!/usr/bin/env python
"""World-invariant criticality labels: replay every tool call of every episode in the matched PARTNER environment and
record whether the same call would be unsafe / critical there.

python scripts/73_partner_labels.py actor=gptoss20b bench=v2fresh

Theorem 4 needs P_crit to be invariant across the matched worlds ("is this an action that is unsafe in SOME world?").
The env's per-world `critical` flag is not: e.g. in con_ci_green, editing the test file is a violation in x- but a
non-critical action in x+, so a per-world label forces the criticality predicate to learn the world itself.
Output: outputs/xm_feats/partner_labels_<actor>_<bench>.parquet (episode_id, event_id, partner_unsafe, partner_critical)
"""
import json

import pandas as pd
from omegaconf import OmegaConf

from cape.envs.base import MockEnv
from cape.utils.config import REPO_ROOT, load_config

D = OmegaConf.create({"actor": "gptoss20b", "bench": "v2fresh"})


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    S = {}
    for l in open(REPO_ROOT / f"outputs/capebench/{cfg.bench}/scenarios.jsonl"):
        s = json.loads(l); S[s["instance_id"]] = s
    pair = {}
    for s in S.values():
        if not s["nuisance"]:
            pair.setdefault(s["counterfactual_pair_id"], []).append(s["instance_id"])
    pre = cfg.bench if cfg.actor in ("qwen38", "qwenexact") else f"xm_{cfg.actor}_{cfg.bench}"
    rows = []
    for sfx in ("minus", "plus", "plus23"):
        p = REPO_ROOT / f"outputs/rollouts/{pre}_{sfx}.parquet"
        if not p.exists():
            continue
        for ep in pd.read_parquet(p).itertuples():
            spec = S[ep.instance_id]
            other = [i for i in pair[spec["counterfactual_pair_id"]] if i != ep.instance_id][0]
            penv = MockEnv(S[other])
            for e in ep.events:
                if not (e["is_tool_call"] and e["tool"]):
                    continue
                try:
                    a = json.loads(e["args_json"]) if e["args_json"] else None
                except Exception:
                    a = None
                if a is None:
                    continue
                _, info = penv.step(e["tool"], a)
                rows.append({"episode_id": ep.episode_id, "event_id": e["event_id"],
                             "partner_unsafe": int(bool(info.unsafe)), "partner_critical": int(bool(info.critical))})
    D_ = pd.DataFrame(rows)
    D_.to_parquet(REPO_ROOT / f"outputs/xm_feats/partner_labels_{cfg.actor}_{cfg.bench}.parquet")
    print(cfg.actor, cfg.bench, len(D_), "partner_unsafe", int(D_.partner_unsafe.sum()), "partner_critical", int(D_.partner_critical.sum()))


if __name__ == "__main__":
    main()
