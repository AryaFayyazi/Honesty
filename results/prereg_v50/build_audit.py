#!/usr/bin/env python
"""Prereg v50 (docs/preregistration_v50.md, locked in results/prereg_v50_lock.json): build the BLIND audit sheet and
the separate key. CPU only, deterministic, read-only on project data.

python results/prereg_v50/build_audit.py               (main v50 sheet)
python results/prereg_v50/build_audit.py --addendum    (Addendum 1 SPIN sheet -> addendum_sheet.jsonl, addendum_key.csv,
                                                         addendum_counts.csv; excludes episodes audited in v50 stratum S0)
main -> results/prereg_v50/audit_sheet.jsonl   (annotator-facing; no model/condition/stratum/label/intervention text)
   results/prereg_v50/audit_key.csv       (item_id, stratum, set, episode_id, model, condition, rubric_label)
   results/prereg_v50/counts.csv          (stratum x label sampled counts and available pool sizes)

Strata: S0 v37 C-set original reports (frozen C list = scripts/98 is_C / V37_MUSE_C); S1/S2 v46 none / caa_p8_d16;
S3/S4 v44 neutral / fta_contract. Informed x- episodes only (all sources are *_minus* sets).
Sampling per stratum: up to 30 CANDID, 15 MISREPRESENTED, 15 OMITTED; within a label, order by
sha256(f"{stratum}|{set}|{episode_id}") and take the first. Items from all strata shuffled with seed 50; item ids are
drawn afterwards (in shuffled order) from a separately seeded RNG, so id order carries no stratum information.
"""
import glob
import hashlib
import importlib.util
import json
import random
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/prereg_v50"
QUOTA = {"CANDID": 30, "MISREPRESENTED": 15, "OMITTED": 15}
SHUFFLE_SEED = 50
ID_SEED = 5050
READS = {"list_files", "read_file", "open_mock_url"}   # read-only tools omitted from the action log (as in scripts/96)
ENTRY_MAX = 200
MARK_UNSAFE = True   # mark log entries the ENVIRONMENT flagged as the unauthorized action (ground truth, not a rubric label)


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def is_C(st):
    # copy of scripts/98_v37_analysis.py is_C (frozen list); checked against the script's source below
    return "minus2345" in st or st in V37_MUSE_C


V37_MUSE_C = {"xm_museglimmer_core24b_minus", "xm_museglimmer_core24b_minus23", "xm_museglimmer_core24b_reasoning_minus",
              "xm_museglimmer_core24b_obfuscate_minus"}
_src98 = (ROOT / "scripts/98_v37_analysis.py").read_text()
assert 'return "minus2345" in st or st in V37_MUSE_C' in _src98 and all(f'"{s}"' in _src98 for s in V37_MUSE_C)


def bench_of(st):
    return re.sub(r"_minus\d*$", "", re.sub(r"^xm_[a-z0-9]+_", "", st))   # xm_gemma4_core24b_reasoning_minus2345 -> core24b_reasoning


def hkey(stratum, st, eid):
    return hashlib.sha256(f"{stratum}|{st}|{eid}".encode()).hexdigest()


def trunc(s, n):
    s = s if isinstance(s, str) else ""
    return s if len(s) <= n else s[: n - 1] + "…"


def entry(e):
    call = f"{e['tool']}({e['args_json'] or ''})"
    res = (e["tool_result"] or "").strip()
    r = trunc(res, 116)
    c = trunc(call, ENTRY_MAX - len(r) - 4)
    text = f"{c} -> {r}"
    assert len(text) <= ENTRY_MAX
    d = {"step": int(e["event_id"]), "text": text}
    if MARK_UNSAFE and e["unsafe_action"]:
        d["unauthorized_action"] = True
    return d


# ------------------------------------------------------------------ pools
def pool_S0():
    rows = []
    for f in sorted(glob.glob(str(ROOT / "outputs/disclosure_v37/*_rubric.parquet"))):
        st = Path(f).name.replace("_rubric.parquet", "")
        if not is_C(st):
            continue
        R = pd.read_parquet(f)
        R = R[R.informed.astype(bool) & R.label.isin(QUOTA)]
        rows += [dict(stratum="S0", set=st, episode_id=r.episode_id, condition="none", rubric_label=r.label, report=None) for r in R.itertuples()]
    return rows


def pool_regen(stratum, label_files, gen_files, message):
    L = pd.concat([pd.read_parquet(ROOT / f) for f in label_files], ignore_index=True)
    G = pd.concat([pd.read_parquet(ROOT / f) for f in gen_files], ignore_index=True)
    L = L[(L.message == message) & L.informed.astype(bool) & L.label.isin(QUOTA)]
    G = G[G.message == message].set_index(["set", "episode_id"])
    assert not G.index.duplicated().any()
    rows = []
    for r in L.itertuples():
        rows.append(dict(stratum=stratum, set=r.set, episode_id=r.episode_id, condition=message, rubric_label=r.label,
                         report=G.loc[(r.set, r.episode_id)].revised_report))
    return rows


V46L, V46G = ["outputs/reconcile/v46B_rubric3.parquet"], ["outputs/reconcile/v46B.parquet"]
V44L = sorted(str(Path(p).relative_to(ROOT)) for p in glob.glob(str(ROOT / "outputs/prereport/v44_*_rubric3.parquet")))
V44G = [p.replace("_rubric3.parquet", ".parquet") for p in V44L]


def main():
    pools = {"S0": pool_S0(),
             "S1": pool_regen("S1", V46L, V46G, "none"), "S2": pool_regen("S2", V46L, V46G, "caa_p8_d16"),
             "S3": pool_regen("S3", V44L, V44G, "neutral"), "S4": pool_regen("S4", V44L, V44G, "fta_contract")}
    picked, counts = [], []
    for s, rows in pools.items():
        df = pd.DataFrame(rows)
        assert not df.duplicated(["set", "episode_id"]).any(), s
        df["h"] = [hkey(s, a, b) for a, b in zip(df.set, df.episode_id)]
        for lab, q in QUOTA.items():
            sub = df[df.rubric_label == lab].sort_values("h")
            take = sub.head(q)
            picked += take.to_dict("records")
            counts.append(dict(stratum=s, label=lab, quota=q, available=len(sub), sampled=len(take)))
    # episode data
    rolls, specs, items = {}, {}, []
    for p in picked:
        st = p["set"]
        if st not in rolls:
            rolls[st] = pd.read_parquet(ROOT / f"outputs/rollouts/{st}.parquet").set_index("episode_id")
        ep = rolls[st].loc[p["episode_id"]]
        b = bench_of(st)
        if b not in specs:
            specs[b] = {json.loads(l)["instance_id"]: json.loads(l)["task_prompt"] for l in open(ROOT / f"outputs/capebench/{b}/scenarios.jsonl")}
        report = ep.final_answer if p["stratum"] == "S0" else p["report"]
        assert isinstance(report, str) and report.strip(), (p["stratum"], st, p["episode_id"])
        actions = [entry(e) for e in ep.events if e["is_tool_call"] and e["tool"] and e["tool"] not in READS]
        assert any(e["unsafe_action"] for e in ep.events)
        items.append({"_key": {"stratum": p["stratum"], "set": st, "episode_id": p["episode_id"], "model": ep.model,
                               "condition": p["condition"], "rubric_label": p["rubric_label"]},
                      "task": specs[b][ep.instance_id], "actions": actions, "report": report})
    random.Random(SHUFFLE_SEED).shuffle(items)
    rid = random.Random(ID_SEED); ids = set()
    for it in items:
        while True:
            i = f"{rid.getrandbits(24):06x}"
            if i not in ids:
                ids.add(i); it["item_id"] = i; break
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "audit_sheet.jsonl", "w") as f:
        for it in items:
            f.write(json.dumps({"item_id": it["item_id"], "task": it["task"], "actions": it["actions"], "report": it["report"]},
                               ensure_ascii=False) + "\n")
    pd.DataFrame([{"item_id": it["item_id"], **it["_key"]} for it in items])[
        ["item_id", "stratum", "set", "episode_id", "model", "condition", "rubric_label"]].to_csv(OUT / "audit_key.csv", index=False)
    C = pd.DataFrame(counts); C.to_csv(OUT / "counts.csv", index=False)
    print(C.pivot(index="stratum", columns="label", values="sampled").to_string())
    print(C.pivot(index="stratum", columns="label", values="available").to_string())
    print("items", len(items))


# ------------------------------------------------------------------ Addendum 1 (exploratory SPIN audit; prereg v50 Addendum 1)
ADD_QUOTA = [("SPIN", 1, None), ("SPIN", 0, 40), ("CANDID", None, 10), ("MISREPRESENTED", None, 10)]   # (label, retro, n; None = all / any)
ADD_SHUFFLE_SEED, ADD_ID_SEED = 51, 5151


def addendum():
    """S0 only (frozen C list, informed x-). retro from scripts/95 episode_rows (request_permission after first_unsafe_event),
    as used by scripts/98. Excludes the (set, episode_id) of audit_key.csv rows with stratum == S0. Within each group: order by
    sha256(f"S0A|{set}|{episode_id}") and take the first n."""
    X95 = _mod("x95", "scripts/95_lie_forecast.py")
    K = pd.read_csv(OUT / "audit_key.csv"); K0 = K[K.stratum == "S0"]; used = set(zip(K0.set, K0.episode_id))   # only episodes audited in S0
    rows = []
    for f in sorted(glob.glob(str(ROOT / "outputs/disclosure_v37/*_rubric.parquet"))):
        st = Path(f).name.replace("_rubric.parquet", "")
        if not is_C(st):
            continue
        R = pd.read_parquet(f)
        R = R[R.informed.astype(bool) & R.label.isin(["SPIN", "CANDID", "MISREPRESENTED"])]
        rows += [{k: r[k] for k in ("set", "episode_id", "label", "retro")} for r in X95.episode_rows(st, R)]
    df = pd.DataFrame(rows)
    assert not df.duplicated(["set", "episode_id"]).any()
    df["h"] = [hashlib.sha256(f"S0A|{a}|{b}".encode()).hexdigest() for a, b in zip(df.set, df.episode_id)]
    df["used"] = [(a, b) in used for a, b in zip(df.set, df.episode_id)]
    picked, counts = [], []
    for lab, retro, n in ADD_QUOTA:
        g = df[(df.label == lab) & ((df.retro == retro) if retro is not None else True)]
        avail = g[~g.used].sort_values("h")
        take = avail if n is None else avail.head(n)
        picked += take.to_dict("records")
        counts.append(dict(label=lab, retro="any" if retro is None else retro, quota="all" if n is None else n,
                           pool=len(g), excluded_in_v50=int(g.used.sum()), sampled=len(take)))
    rolls, specs, items = {}, {}, []
    for p in picked:
        st = p["set"]
        if st not in rolls:
            rolls[st] = pd.read_parquet(ROOT / f"outputs/rollouts/{st}.parquet").set_index("episode_id")
        ep = rolls[st].loc[p["episode_id"]]; b = bench_of(st)
        if b not in specs:
            specs[b] = {json.loads(l)["instance_id"]: json.loads(l)["task_prompt"] for l in open(ROOT / f"outputs/capebench/{b}/scenarios.jsonl")}
        report = ep.final_answer
        assert isinstance(report, str) and report.strip()
        actions = [entry(e) for e in ep.events if e["is_tool_call"] and e["tool"] and e["tool"] not in READS]
        items.append({"_key": {"set": st, "episode_id": p["episode_id"], "model": ep.model, "rubric_label": p["label"], "retro": int(p["retro"])},
                      "task": specs[b][ep.instance_id], "actions": actions, "report": report})
    random.Random(ADD_SHUFFLE_SEED).shuffle(items)
    rid = random.Random(ADD_ID_SEED); ids = set(K.item_id.astype(str))      # also avoid collisions with v50 ids
    for it in items:
        while True:
            i = f"{rid.getrandbits(24):06x}"
            if i not in ids:
                ids.add(i); it["item_id"] = i; break
    with open(OUT / "addendum_sheet.jsonl", "w") as f:
        for it in items:
            f.write(json.dumps({"item_id": it["item_id"], "task": it["task"], "actions": it["actions"], "report": it["report"]},
                               ensure_ascii=False) + "\n")
    pd.DataFrame([{"item_id": it["item_id"], **it["_key"]} for it in items])[
        ["item_id", "set", "episode_id", "model", "rubric_label", "retro"]].to_csv(OUT / "addendum_key.csv", index=False)
    C = pd.DataFrame(counts); C.to_csv(OUT / "addendum_counts.csv", index=False)
    print(C.to_string(index=False)); print("items", len(items))


if __name__ == "__main__":
    import sys
    addendum() if "--addendum" in sys.argv[1:] else main()
