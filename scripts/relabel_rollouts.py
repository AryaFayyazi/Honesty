#!/usr/bin/env python
"""Re-apply the (rule-based) safety checker to saved rollouts by replaying their exact actions.

python scripts/relabel_rollouts.py outputs/rollouts/<name>.parquet outputs/capebench/<bench>/scenarios.jsonl
Used after any checker fix; writes the parquet in place and prints the label changes.
"""
import json
import sys

import pyarrow as pa
import pyarrow.parquet as pq

from cape.envs.base import MockEnv


def main(path, scen):
    specs = {json.loads(l)["instance_id"]: json.loads(l) for l in open(scen)}
    rows = pq.read_table(path).to_pylist()
    changed = 0
    for r in rows:
        env = MockEnv(specs[r["instance_id"]])
        before = r["unsafe_episode"]
        for e in r["events"]:
            if e["is_tool_call"] and e["parse_error"] is None:
                _, i = env.step(e["tool"], json.loads(e["args_json"]) if e["args_json"] else {})
                e.update(unsafe_action=i.unsafe, critical=i.critical, goal=i.goal, escalation=i.escalation,
                         violations=",".join(i.violations))
        u = [e["event_id"] for e in r["events"] if e["unsafe_action"]]
        c = [e["event_id"] for e in r["events"] if e["critical"]]
        r.update(unsafe_episode=bool(u), first_unsafe_event=u[0] if u else None, critical_done=bool(c),
                 first_critical_event=c[0] if c else None, escalated=any(e["escalation"] for e in r["events"]),
                 success=bool(any(e["goal"] for e in r["events"]) and not u))
        changed += before != r["unsafe_episode"]
    pq.write_table(pa.Table.from_pylist(rows), path)
    print(f"relabelled {len(rows)} episodes; unsafe_episode changed for {changed}; "
          f"unsafe now {sum(r['unsafe_episode'] for r in rows)}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
