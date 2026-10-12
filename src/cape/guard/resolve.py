"""State-grounded pre-execution effect resolution for a proposed tool call (the 'resolved effect' a gate sees).

Design constraint (non-circularity): this module reads ONLY environment state that a deployed gate could query from
authoritative services (file/ACL metadata, DB rows the statement would touch, recipient domain, resource inventory,
the permission log). It never reads the benchmark's label matchers (critical / always_unsafe / unsafe_any_cf / goal),
the counterfactual value, the protected-row list, or the environment's authorisation flag.
"""
from __future__ import annotations

import json
import re

from cape.envs.base import MockEnv, _fmt_rows

INVENTORY_RE = re.compile(r"(-info\b|^list-|status|report)", re.I)
FORBIDDEN_SPEC_KEYS = {"critical", "always_unsafe", "unsafe_any_cf", "goal", "cf_value", "counterfactual_value",
                       "protected_rows", "protected_index", "causal_var", "causal_desc", "critical_example"}


def _meta(env: MockEnv, path: str) -> str:
    f = env.state["files"].get(path)
    if f is None:
        return f"{path}: does not exist"
    m = f.get("meta") or {}
    return f"{path}: " + ("; ".join(f"{k}: {v}" for k, v in m.items()) if m else "no metadata")


def _paths_in(text: str, env: MockEnv) -> list[str]:
    return [p for p in env.state["files"] if p in text]


def _inventory(env: MockEnv, command: str) -> list[str]:
    """Outputs of the environment's read-only inventory commands for the resource named in `command`."""
    toks = command.split()
    target = [t for t in toks[1:] if not t.startswith("-")]
    out = []
    for c in env.spec.get("commands", []):
        name = c.get("name", "")
        verb = name.split()[0] if name else ""
        if not verb or not INVENTORY_RE.search(verb) or verb == (toks[0] if toks else ""):
            continue
        out.append(f"[{name}] -> {c.get('output', '').strip()}")
    return out + ([f"target argument(s): {', '.join(target)}"] if target else [])


def _authz_lines(env: MockEnv, handle: str) -> list[str]:
    """Resolved authorization (B3): the principal's own entries in resource inventories and, for every ACL-like line
    (admin / may grant / approver / owner), whether the principal's handle is listed. Generic text lookup over the
    environment's inventory outputs; returns [] unless the principal appears in some inventory (i.e. is a member)."""
    h = re.compile(r"\b" + re.escape(handle) + r"\b")
    member, out = False, []
    for c in env.spec.get("commands", []):
        verb = c.get("name", "").split()[0] if c.get("name") else ""
        if not verb or not INVENTORY_RE.search(verb):
            continue
        for line in c.get("output", "").splitlines():
            if re.search(r"admin|may grant|approver|owner", line, re.I):
                out.append(f"Authorization check [{verb}] '{line.strip()}': principal handle '{handle}' listed: "
                           f"{'YES' if h.search(line) else 'NO'}")
            elif h.search(line):
                member = True
                out.append(f"Principal entry [{verb}]: '{line.strip()}'")
            if h.search(line):
                member = True
    return out if member else []


def resolve_effect(env: MockEnv, name: str, args: dict, permission_log: list[str], identity: bool = False,
                   authz: bool = False) -> str:
    """Human-readable resolved effect of (name, args) in the CURRENT state of env (call before env.step)."""
    spec = env.spec
    principal = spec.get("user_email", "")
    dom = principal.split("@")[-1]
    L = [f"Principal: {spec.get('user_name', '')} <{principal}> (organisation domain: {dom})"]
    if identity and spec.get("directory"):  # identity-provider lookup of the principal's own accounts/handles
        d = spec["directory"]
        L.append(f"Identity directory: {d['name']} = handle '{d['handle']}' (repositories/tools), email {d['email']}")
    a = args or {}
    if name == "write_file":
        p = str(a.get("path", ""))
        L.append(f"Effect: {'OVERWRITE existing' if p in env.state['files'] else 'CREATE new'} file")
        L.append("Target " + _meta(env, p))
    elif name == "copy_file":
        L.append("Effect: copy file")
        L.append("Source " + _meta(env, str(a.get("source", ""))))
        L.append("Destination " + _meta(env, str(a.get("destination", ""))))
    elif name == "send_message":
        r = str(a.get("recipient", "")).strip().lower()
        rd = r.split("@")[-1] if "@" in r else "(no domain)"
        n = (spec.get("mailing_lists") or {}).get(r)
        L.append(f"Effect: outbound message to {r} ({'INTERNAL' if rd == dom else 'EXTERNAL'} domain {rd})"
                 + (f"; mailing list with {n} recipients" if n else ""))
        for p in _paths_in(str(a.get("body", "")) + " " + str(a.get("subject", "")), env):
            L.append("Referenced " + _meta(env, p))
    elif name == "upload_artifact":
        L.append(f"Effect: upload to destination '{a.get('destination', '')}' (outside the organisation's systems)")
        L.append("Uploaded " + _meta(env, str(a.get("path", ""))))
    elif name == "query_database":
        q = str(a.get("query", ""))
        t, rows = env.sql_affected(q)
        if t is None:
            L.append("Effect: read-only query (no state change)" if re.match(r"(?is)\s*(select|show)", q)
                     else "Effect: write statement")
        else:
            tbl = env._table(t) or {}
            kind = "DELETE" if re.match(r"(?is)\s*delete", q) else "UPDATE"
            L.append(f"Effect: {kind} on table {t} ({'; '.join(f'{k}: {v}' for k, v in (tbl.get('meta') or {}).items())})"
                     f" affecting {len(rows)} row(s)")
            if rows:
                L.append(_fmt_rows(rows, limit=8))
    elif name == "delete_record":
        t = str(a.get("table", ""))
        tbl = env._table(t) or {}
        row = [r for r in tbl.get("rows", []) if str(r.get("id")) == str(a.get("record_id"))]
        L.append(f"Effect: DELETE record {a.get('record_id')} from {t} "
                 f"({'; '.join(f'{k}: {v}' for k, v in (tbl.get('meta') or {}).items())})")
        L.append(_fmt_rows(row, limit=1) if row else "record not found")
    elif name == "execute_mock_command":
        cmd = str(a.get("command", ""))
        L.append(f"Effect: run command `{cmd}`")
        L += ["Inventory " + x for x in _inventory(env, cmd)]
        if authz and spec.get("directory"):
            d = spec["directory"]
            extra = _authz_lines(env, d["handle"])
            if extra:
                L.append(f"Principal identity: {d['name']} = handle '{d['handle']}'")
                L += extra
    elif name == "request_permission":
        L.append("Effect: approval request (no state change)")
    else:
        L.append("Effect: read-only")
    orig = spec.get("files", {})
    changed = [p for p, f in env.state["files"].items() if orig.get(p) != f]
    if changed:
        L.append("Files created/modified earlier in this session: " + ", ".join(changed))
    L.append("Permission decisions so far: " + (" | ".join(permission_log) if permission_log else "none"))
    return "\n".join(L)


def replay_resolved(spec: dict, events: list[dict], identity: bool = False, authz: bool = False) -> dict:
    """{event_id: resolved-effect text} for every tool-call event, replaying prior actions through a fresh env."""
    env = MockEnv(spec)
    perm_log, out = [], {}
    for e in events:
        if not e["is_tool_call"]:
            continue
        try:
            args = json.loads(e["args_json"]) if e["args_json"] else {}
        except Exception:
            args = {}
        out[e["event_id"]] = resolve_effect(env, e["tool"], args, perm_log, identity, authz)
        obs, _ = env.step(e["tool"], args if isinstance(args, dict) else {})
        if e["tool"] == "request_permission":
            perm_log.append(obs.strip()[:200])
    return out
