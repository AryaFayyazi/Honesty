#!/usr/bin/env python
"""Cross-model white-box gate features: teacher-forced replay of server rollouts through each model's OWN chat
template (the same template vLLM used to render the prompts the model saw), reading the model's residual stream at the
END of each proposed (non-read) action, with the full prior context. This is what a deployed self-monitoring gate
computes: forward the model over (history + proposed action) and read a linear probe.

python scripts/56_xm_replay_extract.py actor=gemma4 sets='[xm_gemma4_v2fresh_minus,xm_gemma4_v2fresh_plus]'
python scripts/56_xm_replay_extract.py actor=gemma4 stage=check     # CPU: template rendering + prefix property only
python scripts/56_xm_replay_extract.py actor=qwen38 out_prefix=rdqwen__ sets='[xm_gptoss20b_v2fresh_minus]'   # reader mode

Features per action event: hidden state at the last token, and the mean of the last 8 tokens, at layers spanning
depth (primary = ~72% depth, fixed a priori from Qwen L46/64). Output: outputs/xm_feats/<set>.npz + <set>_meta.parquet
"""
import json
import re
import time

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.envs.base import TOOLS
from cape.models.load import model_path
from cape.utils.config import REPO_ROOT, load_config, resolve_model

ACT = {"gemma4": {"model": "google/gemma-4-26B-A4B-it", "kwargs": {"enable_thinking": True}, "suffix": ""},
       "gptoss20b": {"model": "openai/gpt-oss-20b", "kwargs": {"reasoning_effort": "medium"}, "suffix": ""},
       "museglimmer": {"model": "meta-models/Muse-Glimmer-30B", "kwargs": {},
                       "suffix": "\n\nReasoning strength: medium"},
       "qwen38": {"model": "Qwen/Qwen3.8-27B", "kwargs": {"enable_thinking": True}, "suffix": ""}}
READS = {"list_files", "read_file", "open_mock_url"}
MARKER = {"gemma4": "<|tool_call>", "gptoss20b": "<|start|>assistant to=functions", "museglimmer": "<|start|>assistant to=",
          "qwen38": "<tool_call>"}
TAG = re.compile(r"<\|[^|<>]{0,40}\|>")
D = OmegaConf.create({"actor": "gemma4", "sets": [], "stage": "extract", "max_tokens": 30000, "limit": None,
                      "bench": "v2fresh", "out_prefix": "", "episodes": None, "out_suffix": ""})
# v57 (2026-10-06): episodes = parquet (set, episode_id) restricting extraction to those episodes; out_suffix names the output   # out_prefix: reader mode (actor model reads other actors' sets)


def messages_upto(spec, events, t, suffix, args_as_dict=True):
    msgs = [{"role": "system", "content": spec["system_prompt"] + suffix}, {"role": "user", "content": spec["task_prompt"]}]
    for e in events[: t + 1]:
        if not e["is_tool_call"] or e["tool"] is None:
            continue
        try:
            a = json.loads(e["args_json"]) if e["args_json"] else {}
        except Exception:
            a = {}
        args = a if args_as_dict else json.dumps(a)
        # strip stray chat-format tags from malformed generations (gpt-oss: 3.4% of turns contain raw <|channel|> etc.,
        # which its template rejects when replayed); documented in the paper's methods
        r = TAG.sub("", e["reasoning_text"] or "")
        msgs.append({"role": "assistant", "content": TAG.sub("", e["content_text"] or ""),
                     "tool_calls": [{"id": f"call_{e['event_id']}", "type": "function",
                                     "function": {"name": e["tool"], "arguments": args}}],
                     "thinking": r, "reasoning": r, "reasoning_content": r})
        if e["event_id"] < t:
            msgs.append({"role": "tool", "tool_call_id": f"call_{e['event_id']}", "content": e["tool_result"] or ""})
    return msgs


def _merge_content_into_thinking(msgs):
    out = []
    for x in msgs:
        if x.get("role") == "assistant" and x.get("tool_calls") and x.get("content") and x.get("thinking"):
            t = x["thinking"] + "\n" + x["content"]
            x = dict(x, content="", thinking=t, reasoning=t, reasoning_content=t)
        out.append(x)
    return out


def render(tok, msgs, kw):
    try:
        return _render(tok, msgs, kw)
    except Exception:   # e.g. gpt-oss: "cannot pass both content and thinking with tool calls"
        return _render(tok, _merge_content_into_thinking(msgs), kw)


def _render(tok, msgs, kw):
    for as_dict in (True, False):
        try:
            m = msgs if as_dict else [dict(x, tool_calls=[dict(c, function=dict(c["function"], arguments=json.dumps(
                c["function"]["arguments"]) if not isinstance(c["function"]["arguments"], str) else c["function"]["arguments"]))
                for c in x["tool_calls"]]) if "tool_calls" in x else x for x in msgs]
            return tok.apply_chat_template(m, tools=TOOLS, tokenize=False, add_generation_prompt=False, **kw)
        except Exception as ex:
            err = ex
    raise err


def action_events(ep):
    return [e for e in ep.events if e["is_tool_call"] and e["tool"] and e["tool"] not in READS and e["parse_error"] is None]


def layers_for(n):
    return sorted({int(round(n * f)) - 1 for f in (0.5, 0.62, 0.72, 0.82, 0.9)})


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    a = ACT[cfg.actor]
    mcfg = resolve_model(a["model"])
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(model_path(mcfg))
    specs = {}
    for b in (cfg.bench,):   # prompts must come from the bench the rollouts used (e.g. v2stress)
        for l in open(REPO_ROOT / f"outputs/capebench/{b}/scenarios.jsonl"):
            s = json.loads(l); specs[s["instance_id"]] = s
    if cfg.stage == "check":
        for st in cfg.sets:
            E = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{st}.parquet").head(40)
            ok_prefix, n = 0, 0
            for ep in E.itertuples():
                ev = list(ep.events); acts = action_events(ep)
                if not acts:
                    continue
                full = render(tok, messages_upto(specs[ep.instance_id], ev, acts[-1]["event_id"], a["suffix"]), a["kwargs"])
                for e in acts:
                    part = render(tok, messages_upto(specs[ep.instance_id], ev, e["event_id"], a["suffix"]), a["kwargs"])
                    n += 1; ok_prefix += full.startswith(part.rstrip()[: max(1, len(part.rstrip()) - 40)])
            print(f"{st}: actions checked={n}, rendered-turn is (near-)prefix of full render: {ok_prefix}/{n}")
            print("sample tail of a rendered turn:\n", part[-600:])
        return
    import torch
    from transformers import AutoModelForCausalLM, AutoModelForImageTextToText
    # the v030 env can load a mismatched cuDNN sub-library (CUDNN_STATUS_SUBLIBRARY_VERSION_MISMATCH in SDPA, seen on
    # Muse-Glimmer); use PyTorch's flash / memory-efficient attention kernels instead of the cuDNN one
    torch.backends.cuda.enable_cudnn_sdp(False)
    t0 = time.time()
    try:
        model = AutoModelForCausalLM.from_pretrained(model_path(mcfg), dtype=torch.bfloat16, device_map="cuda")
    except Exception:
        model = AutoModelForImageTextToText.from_pretrained(model_path(mcfg), dtype=torch.bfloat16, device_map="cuda")
    model.eval()
    from cape.models.load import discover_transformer_blocks
    blocks, _ = discover_transformer_blocks(model)
    L = layers_for(len(blocks))
    print(f"loaded {cfg.actor} in {time.time()-t0:.0f}s; {len(blocks)} blocks; layers {L}", flush=True)
    cap = {}

    def hook_for(l):
        def fn(mod, inp, outp):
            h = outp[0] if isinstance(outp, tuple) else outp
            cap[l] = h[0, cap["pos"]].float().cpu().numpy()   # only the requested positions
        return fn
    hooks = [blocks[l].register_forward_hook(hook_for(l)) for l in L]
    out = REPO_ROOT / "outputs/xm_feats"; out.mkdir(parents=True, exist_ok=True)

    def lcp(x, y):
        n = min(len(x), len(y)); i = 0
        while i < n and x[i] == y[i]:
            i += 1
        return i
    for st in cfg.sets:
        E = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{st}.parquet")
        if cfg.limit:
            E = E.head(int(cfg.limit))
        if cfg.episodes:
            keep = pd.read_parquet(REPO_ROOT / cfg.episodes); keep = set(keep[keep.set == st].episode_id)
            E = E[E.episode_id.isin(keep)]
        feats_last, feats_mean, feats_pre, meta = [], [], [], []
        for i, ep in enumerate(E.itertuples()):
            ev = list(ep.events); acts = action_events(ep)
            if not acts:
                continue
            spec = specs[ep.instance_id]
            full = render(tok, messages_upto(spec, ev, acts[-1]["event_id"], a["suffix"]), a["kwargs"])
            enc = tok(full, return_offsets_mapping=True, add_special_tokens=False)
            ids, offs = enc["input_ids"], enc["offset_mapping"]
            if len(ids) > cfg.max_tokens:
                continue  # skip over-long episodes (reported in meta count)
            ends, pres = [], []
            for e in acts:
                part = render(tok, messages_upto(spec, ev, e["event_id"], a["suffix"]), a["kwargs"])
                c = lcp(part, full)                      # char index where turn-t render diverges from full
                ti = max(k for k, (s0, _) in enumerate(offs) if s0 < c)   # last token starting before c
                ends.append(ti)
                mk = full.rfind(MARKER[cfg.actor], 0, c)  # start of THIS turn's tool-call markup
                pres.append(max(k for k, (s0, _) in enumerate(offs) if s0 < mk) if mk > 0 else ti)
            pos = sorted({p for t in ends for p in range(max(0, t - 7), t + 1)} | set(pres))
            cap["pos"] = pos
            with torch.no_grad():
                model(input_ids=torch.tensor([ids]).cuda(), logits_to_keep=1, use_cache=False)   # v57: hidden states only (full-vocab logits over 30k tokens OOM)
            pidx = {p: j for j, p in enumerate(pos)}
            for e, t, pr in zip(acts, ends, pres):
                win = [pidx[p] for p in range(max(0, t - 7), t + 1)]
                feats_pre.append(np.stack([cap[l][pidx[pr]] for l in L]))
                feats_last.append(np.stack([cap[l][pidx[t]] for l in L]))
                feats_mean.append(np.stack([cap[l][win].mean(0) for l in L]))
                meta.append({"set": st, "episode_id": ep.episode_id, "event_id": e["event_id"], "scenario_id": ep.scenario_id,
                             "template": ep.template, "cf": ep.cf_value, "tool": e["tool"],
                             "y": int(bool(e["unsafe_action"])), "critical": int(bool(e["critical"])),
                             "pos": int(t), "pre_pos": int(pr), "n_tokens": len(ids)})
            if i % 100 == 0:
                print(f"{st}: {i}/{len(E)} episodes, {len(meta)} actions, {time.time()-t0:.0f}s", flush=True)
        on = f"{cfg.out_prefix}{st}{cfg.out_suffix}"
        np.savez_compressed(out / f"{on}.npz", pre=np.array(feats_pre, dtype=np.float16),
                            last=np.array(feats_last, dtype=np.float16),
                            mean8=np.array(feats_mean, dtype=np.float16), layers=np.array(L))
        pd.DataFrame(meta).to_parquet(out / f"{on}_meta.parquet")
        print(f"wrote {on}: {len(meta)} actions", flush=True)
    for h in hooks:
        h.remove()


if __name__ == "__main__":
    main()
