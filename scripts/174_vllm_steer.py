#!/usr/bin/env python
"""v65 (prereg docs/preregistration_v65.md, Addendum 6): the gate-every-action policy served with vLLM (paged attention,
prefix caching, per-request seeds) instead of HF generate, with the SAME intervention as scripts/160 / 171:
  - residual stream = decoder-layer output hidden_states + residual (= the HF block output read by the CAPE hooks);
  - gate feature = that stream at the last token before the tool-call markup, at the 5 CAPE layers (prefill-only call);
  - steering = + alpha * g_l * u_l at the last query token of every sequence in each forward pass (the prompt's last
    position at prefill, then every decode step), i.e. exactly the HF gate steering of scripts/160.
The engine runs in-process (VLLM_ENABLE_V1_MULTIPROCESSING=0), eager, without torch.compile, so the forward hooks run
on every step.
  stage=validate : CAPE v54 confirmation sites (Qwen). (a) gate scores from vLLM features vs the HF features already
                   saved (outputs/v54/gatefeat_v54conf_<A>.npz): Pearson r and fire agreement at tau; (b) steered vs
                   unsteered decision-turn violations on fired x- sites. -> results/prereg_v65/vllm_validation.json
  stage=serve    : the OpenAI-compatible server of scripts/171 (same request/response handling and logging)."""
import os

os.environ.setdefault("VLLM_ENABLE_V1_MULTIPROCESSING", "0")
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

D = OmegaConf.create({"stage": "validate", "actor": "qwen38", "port": 8124, "log": "outputs/v65/server.jsonl", "tau_file": "", "gate_refit": "",
                      "shadow": True, "batch_wait": 2.0, "max_model_len": 32768, "gpu_mem": 0.88, "n_val": 120, "save_feats": ""})


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


class Steer:
    """vLLM engine + forward hooks implementing capture and HF-equivalent gate steering."""

    def __init__(self, A, cfg):
        import torch
        from transformers import AutoTokenizer
        from vllm import LLM
        from cape.models.load import model_path
        from cape.utils.config import resolve_model
        self.torch = torch; self.A = A
        self.X56 = _mod("x56", "scripts/56_xm_replay_extract.py"); self.G154 = _mod("g154", "scripts/154_v54_gate.py"); a = self.X56.ACT[A]
        p = model_path(resolve_model(a["model"])); self.tok = AutoTokenizer.from_pretrained(p)
        extra = {"qwen38": {"language_model_only": True, "gdn_prefill_backend": "triton"}, "gemma4": {"language_model_only": True},
                 "museglimmer": {"language_model_only": True}}.get(A, {})   # Muse runs in the vLLM-0.30 env   # per-model engine options
        self.llm = LLM(model=p, dtype="bfloat16", max_model_len=int(cfg.max_model_len), gpu_memory_utilization=float(cfg.gpu_mem), enable_prefix_caching=True,
                       enforce_eager=True, compilation_config={"mode": 0}, max_num_seqs=64, **extra)
        model = self.llm.apply_model(lambda m: m)[0]
        layers = [m for n, m in model.named_modules() if (type(m).__name__.endswith("DecoderLayer") or type(m).__name__ == "TransformerBlock")
                  and not any(x in type(m).__name__ for x in ("MTP", "DSpark"))]   # Qwen/Gemma DecoderLayer; gpt-oss TransformerBlock; no speculative heads
        print(f"vLLM decoder layers: {len(layers)} ({type(layers[0]).__name__})", flush=True)
        self.L = self.X56.layers_for(len(layers)); self.st = {"steer": False, "cap": None}
        ga = json.load(open(REPO_ROOT / f"results/prereg_v54/gate_alpha_{A}.json"))["gate_alpha"]; Zd = np.load(REPO_ROOT / f"outputs/v54/dir_{A}.npz")
        dev = next(model.parameters()).device; self.ga = ga
        self.vecs = [torch.tensor(float(ga) * float(Zd[f"ga_{li}"]) * Zd[f"ua_{li}"], dtype=torch.bfloat16, device=dev) for li in range(len(self.L))]
        for li, bl in enumerate(self.L):
            layers[bl].register_forward_hook(self._hook(li))
        gc = json.load(open(f"{p}/generation_config.json")); self.eos = set(gc["eos_token_id"] if isinstance(gc["eos_token_id"], list) else [gc["eos_token_id"]])
        self.n_layers = len(layers)

    def _last_rows(self, n_tokens):
        """flattened-batch row index of the last query token of each sequence in this forward pass."""
        from vllm.forward_context import get_forward_context
        md = get_forward_context().attn_metadata
        for m in (md.values() if isinstance(md, dict) else [md]):
            q = getattr(m, "query_start_loc", None)
            if q is not None:
                return (q[1:] - 1).long()
        return self.torch.tensor([n_tokens - 1], device=self.vecs[0].device)

    def _hook(self, li):
        def h(mod, inp, out):
            if not (self.st["steer"] or self.st["cap"] is not None):
                return out
            hs, res = out if isinstance(out, tuple) else (out, None)
            rows = self._last_rows(hs.shape[0])
            if self.st["cap"] is not None:
                full = hs[rows] + (res[rows] if res is not None else 0)
                self.st["cap"][li] = full[-1].float().cpu().numpy()     # scoring calls hold one sequence
            if self.st["steer"]:
                hs = hs.clone(); hs[rows] = hs[rows] + self.vecs[li]
                return (hs, res) if isinstance(out, tuple) else hs
            return out
        return h

    def generate(self, prompts_ids, samps, steer=False):
        from vllm import SamplingParams
        from vllm.inputs import TokensPrompt
        sp = [SamplingParams(temperature=s.get("temperature") or 1.0, top_p=s.get("top_p") or 1.0, top_k=s.get("top_k") or -1, max_tokens=int(s["max_tokens"]),
                             seed=int(s["seed"]), stop_token_ids=list(self.eos)) for s in samps]
        self.st["steer"] = steer
        try:
            outs = self.llm.generate([TokensPrompt(prompt_token_ids=i) for i in prompts_ids], sp, use_tqdm=False)
        finally:
            self.st["steer"] = False
        return [(list(o.outputs[0].token_ids), self.tok.decode(list(o.outputs[0].token_ids), skip_special_tokens=False)) for o in outs]

    def features(self, ids):
        """residual stream at the last token of ids, at the 5 CAPE layers: [5, d] (prefill-only call)."""
        from vllm import SamplingParams
        from vllm.inputs import TokensPrompt
        self.st["cap"] = {}
        try:
            self.llm.generate([TokensPrompt(prompt_token_ids=ids)], SamplingParams(max_tokens=1, temperature=0.0), use_tqdm=False)
            f = np.stack([self.st["cap"][li] for li in range(len(self.L))])
        finally:
            self.st["cap"] = None
        return f

    def pre_action_ids(self, prompt_ids, g):
        """scripts/160 fires(): prompt + generated tokens up to (not including) the tool-call markup; None if no markup."""
        A, tok, mark = self.A, self.tok, self.G154.TEXT_MARK[self.A]
        if mark not in tok.decode(g, skip_special_tokens=False):
            return None
        lo, hi = 1, len(g)
        while lo < hi:
            mid = (lo + hi) // 2
            if mark in tok.decode(g[:mid], skip_special_tokens=False):
                hi = mid
            else:
                lo = mid + 1
        j = lo - 1
        while j > 0 and mark not in tok.decode(g[j:lo], skip_special_tokens=False):
            j -= 1
        if A in ("gptoss20b", "museglimmer"):
            sid = tok.convert_tokens_to_ids("<|start|>")
            while j > 0 and g[j] != sid:
                j -= 1
        return None if j <= 0 else list(prompt_ids) + list(g[:j])


def stage_validate(cfg):
    import pandas as pd
    A = cfg.actor; S = Steer(A, cfg); M144 = _mod("m144", "scripts/144_v54_steer.py"); C159 = _mod("c159", "scripts/159_v59_continue.py")
    G = np.load(REPO_ROOT / f"outputs/v54/gate_{A}.npz"); tau = float(G["tau"]); Fz = np.load(REPO_ROOT / f"outputs/v54/gatefeat_v54conf_{A}.npz")
    R = pd.read_parquet(REPO_ROOT / f"outputs/v54/v54conf_{A}.parquet"); R["key"] = R.set + "|" + R.episode_id; none = R[R.arm == "none"].set_index("key")
    Sx = pd.read_parquet(REPO_ROOT / f"outputs/v54/sites_{A}_conf.parquet"); Sx["key"] = Sx.set + "|" + Sx.episode_id
    Sx = Sx[Sx.key.isin(none.index) & Sx.key.isin(Fz.files)].groupby("world").head(int(cfg.n_val) // 2).set_index("key")
    specs, roll, rows = {}, {}, []
    for b in Sx.bench.unique():
        for l in open(REPO_ROOT / f"outputs/capebench/{b}/scenarios.jsonl"):
            x = json.loads(l); specs[(b, x["instance_id"])] = x
    for s_ in Sx.set.unique():
        roll[s_] = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{s_}.parquet").set_index("episode_id")
    a = S.X56.ACT[A]
    for k, r in Sx.iterrows():
        ev = list(roll[r.set].loc[r.episode_id].events); spec = specs[(r.bench, r.instance_id)]
        base = S.X56.messages_upto(spec, ev, int(r.site_event), a["suffix"])
        base = base[:-1] if base and base[-1]["role"] == "assistant" else base
        prompt = M144.render_gen(S.X56, S.tok, base, a["kwargs"]); pid = S.tok(prompt, add_special_tokens=False)["input_ids"]
        g = S.tok(none.loc[k].gen_text.split("<|endoftext|>")[0], add_special_tokens=False)["input_ids"]
        ids = S.pre_action_ids(pid, g)
        hf = float(S.G154.gate_score(G, Fz[k][None].astype(np.float32))[0])
        vl = float(S.G154.gate_score(G, S.features(ids)[None].astype(np.float32))[0]) if ids else np.nan
        rows.append({"key": k, "world": r.world, "hf": hf, "vllm": vl, "prompt_ids": pid, "spec": spec, "ev": ev, "site": int(r.site_event)})
    V = pd.DataFrame(rows); ok = V.vllm.notna()
    out = {"n": int(len(V)), "scored": int(ok.sum()), "pearson_r": float(np.corrcoef(V.hf[ok], V.vllm[ok])[0, 1]),
           "fire_agreement_at_tau": float(((V.hf[ok] > tau) == (V.vllm[ok] > tau)).mean()), "tau": tau,
           "mean_abs_diff": float((V.hf[ok] - V.vllm[ok]).abs().mean())}
    # (b) steering effect: fired x- sites, unsteered vs steered regeneration from the same prompt and seed, labelled by replay
    F = V[(V.world == "minus") & (V.vllm > tau)]
    if len(F):
        samp = [{"temperature": 0.6, "top_p": 0.95, "top_k": 20, "max_tokens": 1536, "seed": int(hashlib.md5(k.encode()).hexdigest(), 16) % 2**31} for k in F.key]
        lab = {}
        for steer in (False, True):
            outs = S.generate(list(F.prompt_ids), samp, steer=steer); cats = []
            for (g, txt), r in zip(outs, F.itertuples()):
                tool, args = M144.parse_call(A, txt)
                if tool in (None, "__final__"):
                    cats.append("FINAL" if tool == "__final__" else "PARSE"); continue
                env = C159.env_after_prefix(r.spec, r.ev, r.site); cats.append(C159.step_label(env, r.spec, tool, args)[1])
            lab["steer" if steer else "none"] = cats
        out["steering_on_fired_minus"] = {"n": int(len(F)), **{k: {"violate": round(float(np.mean([c == "VIOLATE" for c in v])), 4),
                                                                   "parse": round(float(np.mean([c == "PARSE" for c in v])), 4)} for k, v in lab.items()}}
    (REPO_ROOT / "results/prereg_v65").mkdir(parents=True, exist_ok=True)
    fn = "vllm_validation.json" if A == "qwen38" else f"vllm_validation_{A}.json"      # v65 Addendum 9: per-model validation
    json.dump(out, open(REPO_ROOT / "results/prereg_v65" / fn, "w"), indent=2); print(json.dumps(out, indent=1), flush=True)
    os._exit(0)


def stage_serve(cfg):
    import uvicorn
    from fastapi import FastAPI, Request
    A = cfg.actor; S = Steer(A, cfg); M171 = _mod("m171", "scripts/171_tau2_steer_server.py"); M144 = _mod("m144", "scripts/144_v54_steer.py")
    C159 = _mod("c159", "scripts/159_v59_continue.py"); M165 = _mod("m165", "scripts/165_v61_e2e.py"); a = S.X56.ACT[A]
    G = np.load(REPO_ROOT / f"outputs/v54/gate_{A}.npz"); tau = float(G["tau"]); Rf = np.load(REPO_ROOT / cfg.gate_refit) if cfg.gate_refit else None
    if cfg.tau_file:
        tau = float(json.load(open(REPO_ROOT / cfg.tau_file))["tau"])
    logf = open(REPO_ROOT / cfg.log, "a"); feats = {}; print(f"vLLM steer server: actor {A} alpha {S.ga} tau {tau:.4f} layers {list(S.L)}", flush=True)

    def score(f):
        if Rf is not None:
            return float(np.mean([(f[li] @ Rf[f"w_{li}"] + Rf[f"b_{li}"] - Rf[f"mu_{li}"]) / Rf[f"sd_{li}"] for li in range(len(S.L))]))
        return float(S.G154.gate_score(G, f[None].astype(np.float32))[0])

    def to_message(txt, is_agent, tools=None):
        rs, _ = C159.split_turn(A, txt) if is_agent else ("", "")
        tool, args = M144.parse_call(A, txt) if is_agent else ("__final__", None)
        if tool not in (None, "__final__"):
            args = M171.coerce_args(args, tools, tool)          # v65 Addendum 8: typed tau2 parameters
            cid = "call_" + uuid.uuid4().hex[:20]
            return {"role": "assistant", "content": None, "reasoning_content": rs,
                    "tool_calls": [{"id": cid, "type": "function", "function": {"name": tool, "arguments": json.dumps(args or {})}}]}, tool, args, cid
        if A in ("gptoss20b", "museglimmer"):
            content = M165.report_of(A, txt, None) or M171.clean(re.split(r"<\|channel\|>final<\|message\|>", txt)[-1])
        elif A == "qwen38":
            content = M171.clean(txt.split("</think>")[-1])
        else:
            content = M171.clean(txt.split("<channel|>")[-1])
        return {"role": "assistant", "content": content, "reasoning_content": rs}, tool, args, None

    q = []; lock = threading.Lock(); loop_ref = {}

    def worker():
        while True:
            time.sleep(cfg.batch_wait)
            with lock:
                batch = q[:]; q.clear()
            if not batch:
                continue
            try:
                outs = S.generate([r["ids"] for r in batch], [r["samp"] for r in batch])
                for r, o in zip(batch, outs):
                    r["out"] = o
                fire = []
                for r in batch:
                    if not r["is_agent"] or not (r["mode"] == "gate" or cfg.shadow):
                        continue
                    ids = S.pre_action_ids(r["ids"], r["out"][0])
                    if ids is None or len(ids) >= cfg.max_model_len - 2:
                        continue
                    r["feat"] = S.features(ids); r["score"] = score(r["feat"])
                    if r["mode"] == "gate" and r["score"] > tau:
                        r["fired"] = True; fire.append(r)
                if fire:
                    for r, o in zip(fire, S.generate([r["ids"] for r in fire], [r["samp"] for r in fire], steer=True)):
                        r["orig"] = r["out"]; r["out"] = o
                for r in batch:
                    msg, tool, args, cid = to_message(r["out"][1], r["is_agent"], r.get("tools"))
                    if r["is_agent"]:
                        row = {"ts": time.time(), "mode": r["mode"], "seed": r["samp"]["seed"], "call_id": cid, "tool": tool, "args": args, "score": r.get("score"),
                               "fired": bool(r.get("fired")), "n_prompt_tokens": len(r["ids"])}
                        if r.get("orig") is not None:
                            ot, oa = M144.parse_call(A, r["orig"][1]); row.update({"orig_tool": ot, "orig_args": oa})
                        # v70 Addendum 1 (additive): request id and the first (unsteered) generation of EVERY request, so the gate's effect
                        # can be measured within the same request (first vs final), free of run-to-run nondeterminism
                        if r.get("rid") is not None:
                            ft, fa = (M144.parse_call(A, r["orig"][1]) if r.get("orig") is not None else (tool, args))
                            row.update({"rid": r["rid"], "first_tool": ft, "first_args": fa, "first_text": (r["orig"][1] if r.get("orig") is not None else r["out"][1])[-4000:]})
                        logf.write(json.dumps(row, default=str) + "\n"); logf.flush()
                        if cfg.save_feats and cid and r.get("feat") is not None:
                            feats[cid] = r["feat"].astype(np.float16)
                            if len(feats) % 200 == 0:
                                np.savez(REPO_ROOT / cfg.save_feats, **feats)
                    loop_ref["loop"].call_soon_threadsafe(r["fut"].set_result, msg)
            except Exception as ex:                      # plain error (no traceback references kept); never hang a client
                err = RuntimeError(f"{type(ex).__name__}: {str(ex)[:300]}"); del ex
                for r in batch:
                    if not r["fut"].done():
                        loop_ref["loop"].call_soon_threadsafe(r["fut"].set_exception, err)

    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/flush")
    async def flush():
        if cfg.save_feats and feats:
            np.savez(REPO_ROOT / cfg.save_feats, **feats)
        logf.flush(); return {"feats": len(feats)}

    @app.post("/v1/chat/completions")
    async def chat(req: Request):
        b = await req.json(); loop_ref["loop"] = asyncio.get_running_loop()
        name = str(b.get("model", A)); mode = "gate" if name.endswith("-gate") else "none"; is_agent = bool(b.get("tools"))
        kw = dict(a["kwargs"]); kw.update(b.get("chat_template_kwargs") or {}); msgs = M171.to_hf_messages(b["messages"]); prompt = None
        for m in (msgs, S.X56._merge_content_into_thinking(msgs)):
            try:
                prompt = S.tok.apply_chat_template(m, tools=b.get("tools") or None, tokenize=False, add_generation_prompt=True, **kw); break
            except Exception:
                continue
        if prompt is None:
            return {"error": "render failed"}
        ids = S.tok(prompt, add_special_tokens=False)["input_ids"]; mx = int(b.get("max_tokens") or 2048)
        ids = ids[-(int(cfg.max_model_len) - mx - 8):]
        samp = {"temperature": b.get("temperature"), "top_p": b.get("top_p"), "top_k": b.get("top_k"), "max_tokens": mx,
                "seed": int(b["seed"]) if b.get("seed") is not None else int(hashlib.md5(prompt.encode()).hexdigest(), 16) % 2**31}   # v70 Add. 1: optional override
        fut = loop_ref["loop"].create_future()
        with lock:
            q.append({"ids": ids, "samp": samp, "mode": mode, "is_agent": is_agent, "fut": fut, "tools": b.get("tools"), "rid": (b.get("metadata") or {}).get("rid")})
        msg = await fut
        return {"id": "chatcmpl-" + uuid.uuid4().hex[:12], "object": "chat.completion", "created": int(time.time()), "model": name,
                "choices": [{"index": 0, "message": msg, "finish_reason": "tool_calls" if msg.get("tool_calls") else "stop"}],
                "usage": {"prompt_tokens": len(ids), "completion_tokens": 0, "total_tokens": len(ids)}}

    threading.Thread(target=worker, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=int(cfg.port), log_level="warning")


if __name__ == "__main__":
    cfg = OmegaConf.merge(D, load_config(None))
    {"validate": stage_validate, "serve": stage_serve}[cfg.stage](cfg)
