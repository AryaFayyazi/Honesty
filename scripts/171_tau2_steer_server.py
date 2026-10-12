#!/usr/bin/env python
"""v65 (prereg docs/preregistration_v65.md): an OpenAI-compatible chat server around an HF model with the frozen CAPE
pre-action gate and decision-steering direction, so that tau2-bench runs UNCHANGED (its orchestrator, user simulator,
tasks and evaluator) while the agent policy is applied server-side.
  model "<actor>"       : plain generation (agent "none" arm and the user simulator). Agent turns that propose a tool call
                          also get a SHADOW gate score (logged, never acted on).
  model "<actor>-gate"  : gate every action, exactly the v59b policy: generate unsteered; if the turn proposes a tool call,
                          read the residual at the last token before the tool-call markup; if the frozen gate score > tau,
                          regenerate the turn with + alpha * g_l * u_l steering (same seed) and return that.
Every agent tool call gets a unique id (returned to tau2, which stores it), and the log row carries the same id, so gate
scores join exactly with the oracle labels of the replayed trajectory.
python scripts/171_tau2_steer_server.py actor=qwen38 port=8124 log=outputs/v65/server_dev.jsonl [tau_file=...]"""
import asyncio
import hashlib
import importlib.util
import json
import re
import threading
import time
import uuid

import numpy as np
from omegaconf import OmegaConf

from cape.utils.config import REPO_ROOT, load_config

D = OmegaConf.create({"actor": "qwen38", "port": 8124, "log": "outputs/v65/server.jsonl", "tau_file": "", "max_batch": 16,
                      "max_batch_tokens": 60000, "batch_wait": 0.05, "max_ctx": 30000, "save_feats": "", "gate_refit": "", "shadow": True})


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def to_hf_messages(msgs):
    """OpenAI chat messages -> HF chat-template messages (tool-call arguments as dicts)."""
    out = []
    for m in msgs:
        m = dict(m)
        if m.get("role") == "assistant" and m.get("tool_calls"):
            tc = []
            for c in m["tool_calls"]:
                f = dict(c.get("function") or {}); a = f.get("arguments")
                if isinstance(a, str):
                    try:
                        a = json.loads(a) if a.strip() else {}
                    except Exception:
                        a = {}
                tc.append({"id": c.get("id"), "type": "function", "function": {"name": f.get("name"), "arguments": a or {}}})
            m["tool_calls"] = tc
        if m.get("content") is None:
            m["content"] = ""
        out.append(m)
    return out


def coerce_args(args, tools, name):
    """v65 Addendum 8: tool-call parameters come back as strings from the CAPE Qwen parser (CAPE mock tools take flat
    strings); tau2 tools are typed. Cast each value by the request's JSON schema (array/object -> json, integer, number,
    boolean), as vLLM's qwen3_coder parser does. Values that do not parse are left unchanged."""
    fn = next((t.get("function", t) for t in (tools or []) if t.get("function", t).get("name") == name), None)
    props = ((fn or {}).get("parameters") or {}).get("properties") or {}
    out = {}
    for k, v in (args or {}).items():
        sch = props.get(k) or {}; typ = sch.get("type") or next((x.get("type") for x in sch.get("anyOf", []) if x.get("type") not in (None, "null")), None)
        if isinstance(v, str):
            s_ = v.strip()
            try:
                if typ in ("array", "object") or (typ is None and s_[:1] in "[{"):
                    v = json.loads(s_)
                elif typ == "integer":
                    v = int(float(s_))
                elif typ == "number":
                    v = float(s_)
                elif typ == "boolean" and s_.lower() in ("true", "false"):
                    v = s_.lower() == "true"
            except Exception:
                pass
        out[k] = v
    return out


def clean(txt):
    return re.sub(r"<\|[^<>]{0,30}>|<[^<>]{0,30}\|>|<pad>|<eos>|</?think>", " ", txt or "").strip()


def main(cfg):
    import torch
    import uvicorn
    from fastapi import FastAPI, Request
    from transformers import AutoModelForCausalLM, AutoModelForImageTextToText, AutoTokenizer
    from cape.models.load import discover_transformer_blocks, model_path
    from cape.utils.config import resolve_model
    A = cfg.actor; torch.backends.cuda.enable_cudnn_sdp(False)
    X56 = _mod("x56", "scripts/56_xm_replay_extract.py"); M144 = _mod("m144", "scripts/144_v54_steer.py"); G154 = _mod("g154", "scripts/154_v54_gate.py")
    C159 = _mod("c159", "scripts/159_v59_continue.py"); M165 = _mod("m165", "scripts/165_v61_e2e.py"); a = X56.ACT[A]
    p = model_path(resolve_model(a["model"])); tok = AutoTokenizer.from_pretrained(p); tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    try:
        model = AutoModelForCausalLM.from_pretrained(p, dtype=torch.bfloat16, device_map="cuda").eval()
    except Exception:
        model = AutoModelForImageTextToText.from_pretrained(p, dtype=torch.bfloat16, device_map="cuda").eval()
    blocks, _ = discover_transformer_blocks(model); L = X56.layers_for(len(blocks)); st = {"vecs": None, "cap": None}

    def mk(li):                                        # identical to scripts/160 (gate steering: prefill last position + every decode step)
        def h(mod, inp, out):
            x = out[0] if isinstance(out, tuple) else out
            if st["cap"] is not None:
                st["cap"][li] = x[0, -1].detach()
            if st["vecs"] is None:
                return out
            if x.shape[1] == 1:
                x = x + st["vecs"][li]
            else:
                x = x.clone(); x[:, -1:] = x[:, -1:] + st["vecs"][li]
            return (x,) + tuple(out[1:]) if isinstance(out, tuple) else x
        return h
    for li, bl in enumerate(L):
        blocks[bl].register_forward_hook(mk(li))
    ga = json.load(open(REPO_ROOT / f"results/prereg_v54/gate_alpha_{A}.json"))["gate_alpha"]; Zd = np.load(REPO_ROOT / f"outputs/v54/dir_{A}.npz")
    vecs = [torch.tensor(float(ga) * float(Zd[f"ga_{li}"]) * Zd[f"ua_{li}"], dtype=torch.bfloat16, device="cuda") for li in range(len(L))]
    G = np.load(REPO_ROOT / f"outputs/v54/gate_{A}.npz"); tau = float(G["tau"]); R = np.load(REPO_ROOT / cfg.gate_refit) if cfg.gate_refit else None
    if cfg.tau_file:                                   # v65: tau recalibrated on development tasks (frozen readout and direction)
        tau = float(json.load(open(REPO_ROOT / cfg.tau_file))["tau"])
    gc = json.load(open(f"{p}/generation_config.json")); eos = set(gc["eos_token_id"] if isinstance(gc["eos_token_id"], list) else [gc["eos_token_id"]])
    start_id = tok.convert_tokens_to_ids("<|start|>") if A in ("gptoss20b", "museglimmer") else None
    logf = open(REPO_ROOT / cfg.log, "a"); print(f"actor {A} gate_alpha {ga} tau {tau:.4f} layers {list(L)}", flush=True)

    def gen(prompts, seeds, samp, steer):
        ids = [tok(t, add_special_tokens=False)["input_ids"] for t in prompts]
        order = sorted(range(len(prompts)), key=lambda i: len(ids[i])); res = [None] * len(prompts); chunks, cur = [], []
        for i in order:
            if cur and (len(cur) >= cfg.max_batch or (len(cur) + 1) * max(len(ids[i]), max(len(ids[c]) for c in cur)) > cfg.max_batch_tokens):
                chunks.append(cur); cur = []
            cur.append(i)
        if cur:
            chunks.append(cur)
        def run(ch):
            try:
                enc = tok([prompts[i] for i in ch], return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
                torch.manual_seed(int(hashlib.md5(("|".join(str(seeds[i]) for i in ch)).encode()).hexdigest(), 16) % 2**31)
                st["vecs"] = vecs if steer else None
                kw = {k: v for k, v in samp.items() if k in ("temperature", "top_p", "top_k") and v is not None}
                with torch.no_grad():
                    o = model.generate(**enc, max_new_tokens=samp["max_tokens"], do_sample=True, **kw)
            except torch.cuda.OutOfMemoryError:            # halve the chunk on OOM
                st["vecs"] = None; torch.cuda.empty_cache()
                if len(ch) == 1:
                    raise
                run(ch[:len(ch) // 2]); run(ch[len(ch) // 2:]); return
            st["vecs"] = None
            for k, i in enumerate(ch):
                g = o[k][enc["input_ids"].shape[1]:].tolist(); n = next((j + 1 for j, t in enumerate(g) if t in eos), len(g)); g = g[:n]
                res[i] = (g, tok.decode(g, skip_special_tokens=False))
        for ch in chunks:
            run(ch)
        return res

    def gate_score(prompt, g):
        """scripts/160 fires(): residual at the last token before the tool-call markup -> frozen gate score (None if no markup)."""
        txt = tok.decode(g, skip_special_tokens=False)
        if G154.TEXT_MARK[A] not in txt:
            return None
        lo, hi = 1, len(g)
        while lo < hi:
            mid = (lo + hi) // 2
            if G154.TEXT_MARK[A] in tok.decode(g[:mid], skip_special_tokens=False):
                hi = mid
            else:
                lo = mid + 1
        j = lo - 1
        while j > 0 and G154.TEXT_MARK[A] not in tok.decode(g[j:lo], skip_special_tokens=False):
            j -= 1
        if start_id is not None:
            while j > 0 and g[j] != start_id:
                j -= 1
        if j <= 0:
            return None
        ids = tok(prompt, add_special_tokens=False)["input_ids"] + g[:j]; st["cap"] = {}
        with torch.no_grad():
            model(input_ids=torch.tensor([ids], device="cuda"), logits_to_keep=1, use_cache=False)
        f = np.stack([st["cap"][li].float().cpu().numpy() for li in range(len(L))])[None]; st["cap"] = None
        if R is not None:                              # v65 fallback readout refit on tau2 development tasks (scripts/173)
            return float(np.mean([(f[0, li] @ R[f"w_{li}"] + R[f"b_{li}"] - R[f"mu_{li}"]) / R[f"sd_{li}"] for li in range(len(L))])), f[0]
        return float(G154.gate_score(G, f)[0]), f[0]

    def to_message(txt, is_agent, tools=None):
        rs, _ = C159.split_turn(A, txt) if is_agent else ("", "")
        tool, args = M144.parse_call(A, txt) if is_agent else ("__final__", None)
        if tool not in (None, "__final__"):
            args = coerce_args(args, tools, tool)
            cid = "call_" + uuid.uuid4().hex[:20]
            return {"role": "assistant", "content": None, "reasoning_content": rs,
                    "tool_calls": [{"id": cid, "type": "function", "function": {"name": tool, "arguments": json.dumps(args or {})}}]}, tool, args, cid
        if A in ("gptoss20b", "museglimmer"):
            content = M165.report_of(A, txt, None) or clean(re.split(r"<\|channel\|>final<\|message\|>", txt)[-1])
        elif A == "qwen38":
            content = clean(txt.split("</think>")[-1])
        else:
            content = clean(txt.split("<channel|>")[-1])
        return {"role": "assistant", "content": content, "reasoning_content": rs}, tool, args, None

    q = []; lock = threading.Lock(); loop_ref = {}; feats = {}

    def worker():
        while True:
            time.sleep(cfg.batch_wait)
            with lock:
                batch = q[:]; q.clear()
            if not batch:
                continue
            try:
                groups = {}
                for r in batch:
                    groups.setdefault(tuple(sorted(r["samp"].items())), []).append(r)
                for key, rs in groups.items():
                    outs = gen([r["prompt"] for r in rs], [r["seed"] for r in rs], dict(key), steer=False)
                    for r, o in zip(rs, outs):
                        r["out"] = o
                    if not rs[0]["is_agent"]:
                        continue
                    fire = []
                    for r in rs:
                        try:
                            gs = gate_score(r["prompt"], r["out"][0]) if (r["mode"] == "gate" or cfg.shadow) else None   # v65b: no shadow scores in the none arm
                        except torch.cuda.OutOfMemoryError:     # long context: no score for this turn (logged as None), never a dead server
                            st["cap"] = None; torch.cuda.empty_cache(); gs = None
                        r["score"], r["feat"] = gs if gs else (None, None)
                        r["fired"] = r["mode"] == "gate" and r["score"] is not None and r["score"] > tau
                        if r["fired"]:
                            fire.append(r)
                    if fire:
                        for r, o in zip(fire, gen([r["prompt"] for r in fire], [r["seed"] for r in fire], dict(key), steer=True)):
                            r["orig"] = r["out"]; r["out"] = o
                for r in batch:
                    msg, tool, args, cid = to_message(r["out"][1], r["is_agent"], r.get("tools"))
                    if r["is_agent"]:
                        row = {"ts": time.time(), "mode": r["mode"], "seed": r["seed"], "call_id": cid, "tool": tool, "args": args,
                               "score": r.get("score"), "fired": bool(r.get("fired")), "n_prompt_chars": len(r["prompt"])}
                        if r.get("orig") is not None:
                            ot, oa = M144.parse_call(A, r["orig"][1]); row.update({"orig_tool": ot, "orig_args": oa})
                        logf.write(json.dumps(row, default=str) + "\n"); logf.flush()
                        if cfg.save_feats and cid and r.get("feat") is not None:   # v65 fallback: pre-action features of unsteered turns
                            feats[cid] = r["feat"].astype(np.float16)
                            if len(feats) % 200 == 0:
                                np.savez(REPO_ROOT / cfg.save_feats, **feats)
                    loop_ref["loop"].call_soon_threadsafe(r["fut"].set_result, msg)
            except Exception as ex:                      # never hang a client; a plain error keeps no traceback (and no GPU tensors) alive
                err = RuntimeError(f"{type(ex).__name__}: {str(ex)[:300]}"); del ex
                st["vecs"] = None; st["cap"] = None
                for r in batch:
                    r.pop("out", None); r.pop("orig", None); r.pop("feat", None)
                    if not r["fut"].done():
                        loop_ref["loop"].call_soon_threadsafe(r["fut"].set_exception, err)
                import gc; gc.collect(); torch.cuda.empty_cache()

    app = FastAPI()

    @app.get("/flush")
    async def flush():                                 # called by the job before stopping the server
        if cfg.save_feats and feats:
            np.savez(REPO_ROOT / cfg.save_feats, **feats)
        logf.flush(); return {"feats": len(feats)}

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/v1/models")
    async def models():
        return {"object": "list", "data": [{"id": A, "object": "model"}, {"id": f"{A}-gate", "object": "model"}]}

    @app.post("/v1/chat/completions")
    async def chat(req: Request):
        b = await req.json(); loop_ref["loop"] = asyncio.get_running_loop()
        name = str(b.get("model", A)); mode = "gate" if name.endswith("-gate") else "none"
        is_agent = bool(b.get("tools"))                 # tau2: the agent call carries tools; the user simulator's does not
        kw = dict(a["kwargs"]); kw.update(b.get("chat_template_kwargs") or {})
        msgs = to_hf_messages(b["messages"])
        prompt = None
        for m in (msgs, X56._merge_content_into_thinking(msgs)):
            try:
                prompt = tok.apply_chat_template(m, tools=b.get("tools") or None, tokenize=False, add_generation_prompt=True, **kw); break
            except Exception:
                continue
        if prompt is None:
            return {"error": "render failed"}
        prompt = prompt if len(prompt) // 3 < cfg.max_ctx else prompt[-cfg.max_ctx * 3:]
        samp = {"temperature": b.get("temperature"), "top_p": b.get("top_p"), "top_k": b.get("top_k"), "max_tokens": int(b.get("max_tokens") or 2048)}
        fut = loop_ref["loop"].create_future()
        with lock:
            q.append({"prompt": prompt, "seed": int(hashlib.md5(prompt.encode()).hexdigest(), 16) % 2**31, "samp": samp, "mode": mode,
                      "is_agent": is_agent, "fut": fut, "tools": b.get("tools")})
        msg = await fut
        return {"id": "chatcmpl-" + uuid.uuid4().hex[:12], "object": "chat.completion", "created": int(time.time()), "model": name,
                "choices": [{"index": 0, "message": msg, "finish_reason": "tool_calls" if msg.get("tool_calls") else "stop"}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}

    threading.Thread(target=worker, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=int(cfg.port), log_level="warning")


if __name__ == "__main__":
    main(OmegaConf.merge(D, load_config(None)))
