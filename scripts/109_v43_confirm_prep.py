#!/usr/bin/env python
"""v43 confirmation plumbing.
stage=lock     : copy the development selection (results/prereg_v43dev/selection.json) to results/prereg_v43/selection.json and
                 hash-lock it (must run BEFORE any fresh v40 label exists; checked).
stage=episodes : fresh informed labelled v40 episodes -> outputs/reconcile/v43_fresh_episodes.parquet (fold 0; directions use fold_key=a)
"""
import hashlib, json, sys, datetime
from pathlib import Path
import pandas as pd
from cape.utils.config import REPO_ROOT
FRESH = ["xm_museglimmer_core24b_minus45", "xm_museglimmer_core24b_minus67", "xm_museglimmer_core24b_reasoning_minus23", "xm_museglimmer_core24b_obfuscate_minus23"]


def lock():
    lab = [s for s in FRESH if (REPO_ROOT / f"outputs/disclosure_v37/{s}_rubric.parquet").exists()]
    sel = json.load(open(REPO_ROOT / "results/prereg_v43dev/selection.json"))
    o = REPO_ROOT / "results/prereg_v43"; o.mkdir(parents=True, exist_ok=True)
    (o / "selection.json").write_text(json.dumps(sel, indent=1))
    L = json.load(open(REPO_ROOT / "results/prereg_v43_lock.json"))
    L["locked_intervention"] = {"at": datetime.datetime.now().isoformat(), "chosen": sel.get("chosen"), "fresh_labels_existing_at_lock": lab,
                                "sha256_selection": hashlib.sha256((o / "selection.json").read_bytes()).hexdigest(),
                                "sha256_directions": hashlib.sha256((REPO_ROOT / "outputs/reconcile/caa_directions.npz").read_bytes()).hexdigest()}
    json.dump(L, open(REPO_ROOT / "results/prereg_v43_lock.json", "w"), indent=1); print("locked", sel.get("chosen"), "| fresh labels existing:", lab)


def episodes():
    rows = []
    for s in FRESH:
        t = pd.read_parquet(REPO_ROOT / f"outputs/disclosure_v37/{s}_rubric.parquet"); t = t[t.label.isin(["CANDID", "SPIN", "OMITTED", "MISREPRESENTED"]) & t.informed.astype(bool)]
        rows.append(t.assign(set=s)[["set", "episode_id", "scenario_id", "label"]])
    E = pd.concat(rows, ignore_index=True).assign(fold=0); E.to_parquet(REPO_ROOT / "outputs/reconcile/v43_fresh_episodes.parquet"); print("fresh episodes", len(E), "lies", int((E.label == "MISREPRESENTED").sum()))


if __name__ == "__main__":
    {"lock": lock, "episodes": episodes}[sys.argv[1].split("=")[1]]()
