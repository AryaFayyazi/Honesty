"""Parse Qwen3.5/3.8 XML-style tool calls:

<tool_call>
<function=NAME>
<parameter=KEY>
VALUE
</parameter>
</function>
</tool_call>
"""
from __future__ import annotations

import json
import re

_CALL = re.compile(r"<tool_call>(.*?)(?:</tool_call>|$)", re.S)
_FN = re.compile(r"<function=([^>\s]+)>(.*?)(?:</function>|$)", re.S)
_PARAM = re.compile(r"<parameter=([^>\s]+)>\n?(.*?)\n?</parameter>", re.S)


def parse_tool_call(text: str) -> tuple[str | None, dict | None, str | None]:
    """Return (name, args, error). ``name is None`` and ``error is None`` means no tool call (final answer)."""
    m = _CALL.search(text)
    if not m:
        return None, None, None
    body = m.group(1)
    f = _FN.search(body)
    if f:
        name = f.group(1).strip()
        args = {k.strip(): v for k, v in _PARAM.findall(f.group(2))}
        return name, args, None
    # JSON fallback: {"name": ..., "arguments": {...}}
    try:
        obj = json.loads(body.strip())
        args = obj.get("arguments", {})
        if isinstance(args, str):
            args = json.loads(args)
        return obj["name"], {k: v if isinstance(v, str) else json.dumps(v) for k, v in args.items()}, None
    except Exception:
        return None, None, "unparseable tool call"
