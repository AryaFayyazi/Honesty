#!/usr/bin/env python
"""v55 anchors (CPU). Prereg: docs/preregistration_v55.md.
x- episodes with a reveal and no unsafe action at or before it; anchor = the first agent turn after the reveal result (prefix =
every turn and tool result up to and including the reveal). y = later unauthorized action. lead = first_unsafe - (reveal + 1).
All violators; non-violators capped at max(2 x violators, 400) per (model, split) by sha256(model|set|episode_id); dev capped at
1,500 per model (violators first). Also stores the prefix text (with and without the agent's reasoning) for the text forecasters.
-> outputs/v55/sites_<model>.parquet
python scripts/147_v55_sites.py gemma4"""
import hashlib
import json
import re
import sys

import numpy as np
import pandas as pd

from cape.utils.config import REPO_ROOT

TAG = re.compile(r"<\|[^|<>]{0,40}\|>")
PRE = {"gemma4": "xm_gemma4_", "gptoss20b": "xm_gptoss20b_", "museglimmer": "xm_museglimmer_", "qwen38": ""}


def split_of(model, stem):
    if model in ("gemma4", "gptoss20b"):
        return "conf" if re.search(r"_minus(6789|10111213)$", stem) else "dev"
    if model == "museglimmer":
        return "conf" if re.search(r"_minus(89|1011|1213|1415)$", stem) else ("dev" if re.search(r"_minus(23|45|67)?$", stem) else None)
    if model == "qwen38":
        return {"core24_minus": "dev", "core24b_minus": "dev", "v2fresh_minus": "dev", "v4fresh_minus": "dev", "core24b_minus2345": "conf",
                "core24b_obfuscate_minus0123": "conf", "core24b_reasoning_minus0123": "conf"}.get(stem)


def bench_of(stem):
    return re.sub(r"_minus\d*$", "", stem)


def prefix_text(spec, events, upto, with_cot):
    s = [f"SYSTEM PROMPT:\n{spec['system_prompt']}", f"TASK:\n{spec['task_prompt']}"]
    for i, e in enumerate(events[: upto + 1]):
        if not (e["is_tool_call"] and e["tool"]):
            continue
        t = f"[step {i}]"
        if with_cot and (e["reasoning_text"] or "").strip():
            t += f"\n(agent reasoning) {TAG.sub(' ', e['reasoning_text'])[:3000]}"
        if (e["content_text"] or "").strip():
            t += f"\n(agent message) {TAG.sub(' ', e['content_text'])[:1500]}"
        t += f"\n(tool call) {e['tool']}({(e['args_json'] or '')[:600]})\n(tool result) {(e['tool_result'] or '')[:1500]}"
        s.append(t)
    return "\n\n".join(s)


def main(model):
    rows = []
    for f in sorted((REPO_ROOT / "outputs/rollouts").glob(f"{PRE[model]}*minus*.parquet")):
        stem = f.stem[len(PRE[model]):]
        if PRE[model] == "" and f.stem.startswith(("xm_", "x_")):
            continue
        sp = split_of(model, stem)
        if sp is None or not (REPO_ROOT / f"outputs/capebench/{bench_of(stem)}/scenarios.jsonl").exists():
            continue
        R = pd.read_parquet(f); rv = pd.to_numeric(R.reveal_event, errors="coerce"); fu = pd.to_numeric(R.first_unsafe_event, errors="coerce")
        nev = R.events.map(len)
        keep = (rv >= 0) & ~(fu <= rv) & (rv + 1 < nev)                 # reveal exists, informed (or never unsafe), a next turn exists
        R = R[keep]
        for r, a, u in zip(R.itertuples(), rv[keep], fu[keep]):
            y = int(u == u and u > a)
            rows.append({"set": f.stem, "episode_id": r.episode_id, "instance_id": r.instance_id, "scenario_id": r.scenario_id,
                         "template": r.template, "bench": bench_of(stem), "split": sp, "anchor_event": int(a) + 1, "reveal_event": int(a),
                         "y": y, "lead": int(u - a - 1) if y else -1,
                         "variant": "obfuscate" if "obfuscate" in stem else ("reasoning" if "reasoning" in stem else "base")})
    S = pd.DataFrame(rows); S["h"] = [hashlib.sha256(f"{model}|{a}|{b}".encode()).hexdigest() for a, b in zip(S.set, S.episode_id)]
    out = []
    for sp, g in S.groupby("split"):
        g = g.sort_values("h"); v, n = g[g.y == 1], g[g.y == 0]
        if sp == "dev":
            v = v.head(750)
        n = n.head(max(2 * len(v), 400))
        if sp == "dev":
            n = n.head(1500 - len(v))
        out.append(pd.concat([v, n]))
    S = pd.concat(out).reset_index(drop=True)
    S["mon_subset"] = False                                   # paired subset for the zero-shot monitors (V2): conf, hash order
    for yv, k in ((1, 300), (0, 600)):
        S.loc[S[(S.split == "conf") & (S.y == yv)].sort_values("h").head(k).index, "mon_subset"] = True
    S["fold"] = S.scenario_id.map(lambda s: int(hashlib.md5(s.encode()).hexdigest(), 16) % 2)
    specs, cot, act = {}, [], []
    for b in S.bench.unique():
        for l in open(REPO_ROOT / f"outputs/capebench/{b}/scenarios.jsonl"):
            x = json.loads(l); specs[(b, x["instance_id"])] = x
    roll = {s_: pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{s_}.parquet").set_index("episode_id") for s_ in S.set.unique()}
    for r in S.itertuples():
        ev = list(roll[r.set].loc[r.episode_id].events); sp_ = specs[(r.bench, r.instance_id)]
        cot.append(prefix_text(sp_, ev, r.reveal_event, True)); act.append(prefix_text(sp_, ev, r.reveal_event, False))
    S["text_cot"], S["text_act"] = cot, act
    o = REPO_ROOT / "outputs/v55"; o.mkdir(parents=True, exist_ok=True); S.drop(columns="h").to_parquet(o / f"sites_{model}.parquet")
    print(model, S.groupby(["split", "y"]).size().to_dict(), "lead0 share among violators %.2f" % (S[S.y == 1].lead == 0).mean(),
          "| sets", S.groupby("split").set.nunique().to_dict(), "| monitor subset", S[S.mon_subset].groupby("y").size().to_dict())
    print("  conf sets", sorted(S[S.split == "conf"].set.unique()))


if __name__ == "__main__":
    main(sys.argv[1])
