#!/usr/bin/env python
"""v76 Addendum 2: merge sharded AgentDojo episode files (<name>.shard<i>.jsonl) into <name>.jsonl (first record per key kept) and
sharded server logs (server_conf_<A>[_ref]_s<i>.jsonl) into server_conf_<A>[_ref].jsonl. python scripts/198_merge_shards.py <out_dir> <actor>"""
import glob
import json
import sys
from pathlib import Path


def merge(main, parts, key, keep="first"):
    """episodes: first record per key (a key is only written once it completes); server logs: last record per request id
    (a request re-sent after a restart supersedes the one from the killed run)."""
    d = {}
    for fn in [main] + parts:
        if fn.exists():
            for i, line in enumerate(open(fn)):
                r = json.loads(line); k = r.get(key, f"__{fn}_{i}")
                if keep == "last" or k not in d:
                    d[k] = line if line.endswith("\n") else line + "\n"
    main.write_text("".join(d.values())); return len(d)


def main(O, A):
    O = Path(O)
    for arm in ("none", "gate"):
        for kind in ("attack", "benign"):
            name = O / f"conf_{A}_{arm}_{kind}.jsonl"; parts = sorted(Path(p) for p in glob.glob(str(O / f"conf_{A}_{arm}_{kind}.shard*.jsonl")))
            if parts:
                print(name.name, merge(name, parts, "key"))
    for suf in ("", "_ref"):
        parts = sorted(Path(p) for p in glob.glob(str(O / f"server_conf_{A}{suf}_s*.jsonl")))
        if parts:
            print(f"server_conf_{A}{suf}", merge(O / f"server_conf_{A}{suf}.jsonl", parts, "rid", keep="last"))


if __name__ == "__main__":
    main(*sys.argv[1:])
