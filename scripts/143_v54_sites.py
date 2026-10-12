#!/usr/bin/env python
"""v54 decision sites (CPU). For each model and split (dev / conf) and world (minus / plus):
  minus: informed violating episodes (reveal < first_unsafe); site event = first_unsafe_event
  plus : authorized-twin episodes that executed the critical action; site event = first_critical_event
Up to `cap` sites per (model, split, world), ordered by sha256(model|set|episode_id). Prefix = all turns before the site call.
-> outputs/v54/sites_<model>_<split>.parquet  (set, episode_id, instance_id, bench, world, site_event, fold)
python scripts/143_v54_sites.py gemma4"""
import hashlib, re, sys
from pathlib import Path
import pandas as pd
from cape.utils.config import REPO_ROOT
CONF_MINUS = re.compile(r"_minus(6789|10111213)$"); CONF_PLUS = {"core24b_plus", "core24b_reasoning_plus", "core24b_obfuscate_plus"}
DEV_PLUS = {"core24_plus", "v2fresh_plus", "v2fresh_plus23"}
# v54 Clarification 2: Muse and Qwen have other fresh set names (same sets as v55 confirmation)
CONF_MINUS_M = {"museglimmer": re.compile(r"_minus(89|1011|1213|1415)$"),
                "qwen38": re.compile(r"^(core24b_minus2345|core24b_obfuscate_minus0123|core24b_reasoning_minus0123)$")}
DEV_MINUS_M = {"museglimmer": re.compile(r"_minus(23|45|67)?$"), "qwen38": re.compile(r"^(core24_minus|core24b_minus|v2fresh_minus|v4fresh_minus)$")}
CONF_PLUS_M = {"museglimmer": {"v2fresh_plus23"}, "qwen38": {"core24b_plus"}}
DEV_PLUS_M = {"museglimmer": {"core24_plus", "v2fresh_plus"}, "qwen38": {"core24_plus", "v2fresh_plus"}}
PRE = {"gemma4": "xm_gemma4_", "gptoss20b": "xm_gptoss20b_", "museglimmer": "xm_museglimmer_", "qwen38": ""}
def bench_of(stem): return re.sub(r"_(minus|plus)\d*$", "", stem)
def main(model, cap=300):
    out = []
    for f in sorted((REPO_ROOT / "outputs/rollouts").glob(f"{PRE[model]}*.parquet")):
        st = f.stem
        if st.endswith("_tokens") or (PRE[model] == "" and st.startswith(("xm_", "v24", "qwen_", "smoke"))):
            continue
        stem = st[len(PRE[model]):]; m = re.search(r"_(minus|plus)\d*$", stem)
        if not m or not (REPO_ROOT / f"outputs/capebench/{bench_of(stem)}/scenarios.jsonl").exists():
            continue
        world = m.group(1)
        if model in CONF_MINUS_M:
            if world == "minus":
                split = "conf" if CONF_MINUS_M[model].search(stem) else ("dev" if DEV_MINUS_M[model].search(stem) else None)
            else:
                split = "conf" if stem in CONF_PLUS_M[model] else ("dev" if stem in DEV_PLUS_M[model] else None)
        elif world == "minus":
            split = "conf" if CONF_MINUS.search(stem) else "dev"
        else:
            split = "conf" if re.sub(r"\d+$", "", stem) in CONF_PLUS and stem in CONF_PLUS else ("dev" if stem in DEV_PLUS else None)
        if split is None:
            continue
        R = pd.read_parquet(f, columns=["episode_id", "instance_id", "scenario_id", "unsafe_episode", "first_unsafe_event", "reveal_event", "first_critical_event", "critical_done"])
        if world == "minus":
            R = R[R.unsafe_episode & R.reveal_event.notna() & (R.reveal_event < R.first_unsafe_event)]; ev = R.first_unsafe_event
        else:
            R = R[R.critical_done.astype(bool) & R.first_critical_event.notna()]; ev = R.first_critical_event
        out.append(pd.DataFrame({"set": st, "episode_id": R.episode_id.values, "instance_id": R.instance_id.values, "scenario_id": R.scenario_id.values,
                                 "bench": bench_of(stem), "world": world, "split": split, "site_event": ev.astype(int).values}))
    S = pd.concat(out, ignore_index=True)
    S["h"] = [hashlib.sha256(f"{model}|{a}|{b}".encode()).hexdigest() for a, b in zip(S.set, S.episode_id)]
    S = S.sort_values("h").groupby(["split", "world"]).head(cap).reset_index(drop=True)
    S["fold"] = S.scenario_id.map(lambda s: int(hashlib.md5(s.encode()).hexdigest(), 16) % 2)
    o = REPO_ROOT / "outputs/v54"; o.mkdir(parents=True, exist_ok=True)
    for sp, g in S.groupby("split"):
        g.drop(columns="h").to_parquet(o / f"sites_{model}_{sp}.parquet")
    print(model, S.groupby(["split", "world"]).size().to_dict(), sorted(S.set.unique()))
if __name__ == "__main__":
    main(sys.argv[1])
