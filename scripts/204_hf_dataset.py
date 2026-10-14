#!/usr/bin/env python
"""Hugging Face Hub export of CAPE-Bench (scenarios, agent episodes, report labels) as Parquet with one fixed schema per table.
Episodes keep their full event logs as JSON text (event fields changed over the project, so one struct schema cannot hold
them all). Token-id files, activation caches and experiment-specific outputs are not exported (they are in the GitHub release
or regenerable). CPU, main env.
python scripts/204_hf_dataset.py out=/data/models/cape_ws/hf_build/CAPE-Bench"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from cape.utils.config import REPO_ROOT

OUTPUTS = REPO_ROOT / "outputs"
EP_COLS = [("run", pa.string()), ("episode_id", pa.string()), ("model", pa.string()), ("benchmark", pa.string()),
           ("scenario_id", pa.string()), ("scenario_family", pa.string()), ("template", pa.string()), ("surface_template", pa.string()),
           ("instance_id", pa.string()), ("counterfactual_pair_id", pa.string()), ("cf_value", pa.string()), ("counterfactual_value", pa.string()),
           ("nuisance", pa.bool_()), ("monitor_aware", pa.bool_()), ("seed", pa.int64()), ("status", pa.string()), ("n_events", pa.int64()),
           ("n_tokens", pa.int64()), ("n_parse_errors", pa.int64()), ("success", pa.bool_()), ("unsafe_episode", pa.bool_()),
           ("first_unsafe_event", pa.int64()), ("critical_done", pa.bool_()), ("first_critical_event", pa.int64()), ("escalated", pa.bool_()),
           ("reveal_event", pa.int64()), ("informed_violation", pa.bool_()), ("final_answer", pa.string()), ("gate_arm", pa.string()),
           ("gate_tau", pa.float64()), ("n_blocked", pa.int64()), ("blocked_unsafe", pa.int64()), ("events_json", pa.string())]
LAB_COLS = [("run", pa.string()), ("episode_id", pa.string()), ("template", pa.string()), ("scenario_id", pa.string()), ("status", pa.string()),
            ("informed", pa.bool_()), ("label", pa.string()), ("mention", pa.bool_()), ("flag", pa.bool_()),
            ("contradiction_claimed", pa.bool_()), ("verifier_false_claim", pa.bool_()), ("quote", pa.string())]


def jsonable(x):
    if isinstance(x, np.ndarray):
        return [jsonable(v) for v in x]
    if isinstance(x, dict):
        return {k: jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return None if np.isnan(x) else float(x)
    if isinstance(x, float) and np.isnan(x):
        return None
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def to_int(v):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v) else int(v)


def episodes(out):
    d = out / "episodes"; d.mkdir(parents=True, exist_ok=True); schema = pa.schema(EP_COLS); n = 0
    for f in sorted(glob.glob(str(OUTPUTS / "rollouts/*.parquet"))):
        if f.endswith("_tokens.parquet") or "model" not in pq.read_schema(f).names:
            continue
        D = pd.read_parquet(f); run = Path(f).stem; rows = []
        for r in D.to_dict("records"):
            fu, rv = to_int(r.get("first_unsafe_event")), to_int(r.get("reveal_event"))
            row = {c: r.get(c) for c, _ in EP_COLS if c in r}
            row.update(run=run, first_unsafe_event=fu, reveal_event=rv, first_critical_event=to_int(r.get("first_critical_event")),
                       informed_violation=bool(fu is not None and rv is not None and rv < fu),
                       events_json=json.dumps(jsonable(r["events"]), ensure_ascii=False))
            for c, t in EP_COLS:
                v = row.get(c)
                if v is not None and not isinstance(v, str) and pd.isna(v):
                    row[c] = None
                elif t == pa.int64() and v is not None:
                    row[c] = int(v)
            rows.append(row)
        pq.write_table(pa.Table.from_pylist(rows, schema=schema), d / f"{run}.parquet", compression="zstd"); n += len(rows)
    return n


def scenarios(out):
    d = out / "scenarios"; d.mkdir(parents=True, exist_ok=True); sets = sorted(glob.glob(str(OUTPUTS / "capebench/*/scenarios.jsonl")))
    keys = set()
    for f in sets:
        for line in open(f):
            keys |= set(json.loads(line))
    keys = ["set"] + sorted(keys); schema = pa.schema([(k, pa.string()) for k in keys]); n = 0
    for f in sets:
        st = Path(f).parent.name; rows = []
        for line in open(f):
            s = json.loads(line); rows.append({k: (st if k == "set" else (None if k not in s else s[k] if isinstance(s[k], str) else json.dumps(s[k], ensure_ascii=False))) for k in keys})
        pq.write_table(pa.Table.from_pylist(rows, schema=schema), d / f"{st}.parquet", compression="zstd"); n += len(rows)
    return n


def labels(out):
    d = out / "report_labels"; d.mkdir(parents=True, exist_ok=True); schema = pa.schema(LAB_COLS); n = 0
    for f in sorted(glob.glob(str(OUTPUTS / "disclosure_v37/*_rubric.parquet"))):
        D = pd.read_parquet(f); run = Path(f).stem[: -len("_rubric")]; D["run"] = run
        rows = [{c: (None if (v := r.get(c)) is None or (not isinstance(v, str) and pd.isna(v)) else v) for c, _ in LAB_COLS} for r in D.to_dict("records")]
        pq.write_table(pa.Table.from_pylist(rows, schema=schema), d / f"{run}.parquet", compression="zstd"); n += len(rows)
    return n


if __name__ == "__main__":
    out = Path(next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("out=")), "/data/models/cape_ws/hf_build/CAPE-Bench"))
    print({"scenarios": scenarios(out), "report_labels": labels(out), "episodes": episodes(out)})
