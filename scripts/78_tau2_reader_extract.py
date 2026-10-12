#!/usr/bin/env python
"""Reader-mode features for the published tau2-bench airline trajectories (prereg v30): Qwen3.8-27B reads each frontier
agent's conversation (tau2's own agent system prompt + tool schemas, results/v30/tau2_airline_agent_context.json) in a
teacher-forced prefill; hidden states at each WRITE call, with the same positions as scripts/56: `mean8` = mean of the
last 8 tokens up to the end of the assistant turn holding the call (LCP of the turn-t render with the next render),
`pre` = token before the turn's <tool_call> marker; layers at depth fractions (0.5, 0.62, 0.72, 0.82, 0.9).

python scripts/78_tau2_reader_extract.py              (GPU, v030 env)
python scripts/78_tau2_reader_extract.py stage=check  (CPU: rendering + prefix property)
Output: outputs/xm_feats/tau2_rdqwen.npz + tau2_rdqwen_meta.parquet (rows aligned with results/v30/tau2_write_labels.csv)
"""
import glob
import importlib.util
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.models.load import model_path
from cape.utils.config import REPO_ROOT, load_config, resolve_model

spec = importlib.util.spec_from_file_location("x56", REPO_ROOT / "scripts/56_xm_replay_extract.py")
X56 = importlib.util.module_from_spec(spec); spec.loader.exec_module(X56)
FINAL = Path("/data/models/cape_ws/datasets/tau2-bench/data/tau2/results/final")
D = OmegaConf.create({"stage": "extract", "max_tokens": 30000, "limit": None})


def to_msgs(sim, upto, sysp):
    """tau2 messages[0..upto] -> chat messages (assistant tool calls with dict arguments; tool results by call id)."""
    out = [{"role": "system", "content": sysp}]
    for m in sim["messages"][: upto + 1]:
        r = m["role"]
        if r == "assistant":
            tcs = m.get("tool_calls") or []
            x = {"role": "assistant", "content": m.get("content") or ""}
            if tcs:
                x["tool_calls"] = [{"id": tc.get("id"), "type": "function",
                                    "function": {"name": tc["name"], "arguments": tc.get("arguments") or {}}} for tc in tcs]
            out.append(x)
        elif r == "user":
            out.append({"role": "user", "content": m.get("content") or ""})
        elif r == "tool":
            out.append({"role": "tool", "tool_call_id": m.get("id"), "content": m.get("content") or ""})
    return out


def render(tok, msgs, tools):
    return tok.apply_chat_template(msgs, tools=tools, tokenize=False, add_generation_prompt=False, enable_thinking=True)


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    ctx = json.load(open(REPO_ROOT / "results/v30/tau2_airline_agent_context.json"))
    tools, sysp = ctx["tools"], ctx["system_prompt"]
    W = pd.read_csv(REPO_ROOT / "results/v30/tau2_write_labels.csv")
    sims = {}
    for f in sorted(glob.glob(str(FINAL / "*_airline_*.json"))):
        for s in json.load(open(f))["simulations"]:
            sims[s["id"]] = s
    from transformers import AutoTokenizer
    mcfg = resolve_model("Qwen/Qwen3.8-27B"); tok = AutoTokenizer.from_pretrained(model_path(mcfg))
    groups = list(W.groupby("sim_id"))
    if cfg.limit:
        groups = groups[: int(cfg.limit)]
    if cfg.stage == "check":
        ok = n = 0
        for sid, g in groups[:30]:
            sim = sims[sid]
            for mi in sorted(set(g.msg_idx)):
                part = render(tok, to_msgs(sim, mi, sysp), tools); nxt = render(tok, to_msgs(sim, mi + 1, sysp), tools)
                c = X56.lcp(part, nxt) if hasattr(X56, "lcp") else None
                n += 1; ok += nxt.startswith(part.rstrip()[: max(1, len(part.rstrip()) - 40)])
        print(f"writes checked {n}; next-turn render extends the turn render: {ok}/{n}"); print(part[-500:]); return
    import torch
    from transformers import AutoModelForCausalLM
    torch.backends.cuda.enable_cudnn_sdp(False)
    model = AutoModelForCausalLM.from_pretrained(model_path(mcfg), dtype=torch.bfloat16, device_map="cuda").eval()
    from cape.models.load import discover_transformer_blocks
    blocks, _ = discover_transformer_blocks(model); L = X56.layers_for(len(blocks)); cap = {}

    def hook_for(l):
        def fn(mod, inp, outp):
            h = outp[0] if isinstance(outp, tuple) else outp
            cap[l] = h[0, cap["pos"]].float().cpu().numpy()
        return fn
    hooks = [blocks[l].register_forward_hook(hook_for(l)) for l in L]

    def lcp(a, b):
        n = min(len(a), len(b)); i = 0
        while i < n and a[i] == b[i]:
            i += 1
        return i
    F_pre, F_last, F_mean, meta = [], [], [], []; t0 = time.time()
    for gi, (sid, g) in enumerate(groups):
        sim = sims[sid]; mis = sorted(set(g.msg_idx)); last = max(mis)
        full = render(tok, to_msgs(sim, min(last + 1, len(sim["messages"]) - 1), sysp), tools)
        enc = tok(full, return_offsets_mapping=True, add_special_tokens=False); ids, offs = enc["input_ids"], enc["offset_mapping"]
        if len(ids) > cfg.max_tokens:
            continue
        ends, pres = {}, {}
        for mi in mis:
            part = render(tok, to_msgs(sim, mi, sysp), tools)
            c = lcp(part, full); ti = max(k for k, (s0, _) in enumerate(offs) if s0 < c)
            mk = full.rfind("<tool_call>", 0, c)
            ends[mi] = ti; pres[mi] = max(k for k, (s0, _) in enumerate(offs) if s0 < mk) if mk > 0 else ti
        pos = sorted({p for t in ends.values() for p in range(max(0, t - 7), t + 1)} | set(pres.values()))
        cap["pos"] = pos
        with torch.no_grad():
            model(input_ids=torch.tensor([ids[: max(pos) + 1]]).cuda())
        pidx = {p: j for j, p in enumerate(pos)}
        for r in g.itertuples():
            t, pr = ends[r.msg_idx], pres[r.msg_idx]; win = [pidx[p] for p in range(max(0, t - 7), t + 1)]
            F_pre.append(np.stack([cap[l][pidx[pr]] for l in L])); F_last.append(np.stack([cap[l][pidx[t]] for l in L]))
            F_mean.append(np.stack([cap[l][win].mean(0) for l in L]))
            meta.append({"sim_id": sid, "msg_idx": r.msg_idx, "tool_call_id": r.tool_call_id, "model": r.model, "task_id": str(r.task_id),
                         "tool": r.tool, "label": r.label, "read_reservation_before": r.read_reservation_before, "pos": int(t)})
        if gi % 50 == 0:
            print(f"{gi}/{len(groups)} sims, {len(meta)} writes, {time.time()-t0:.0f}s", flush=True)
    out = REPO_ROOT / "outputs/xm_feats"
    np.savez_compressed(out / "tau2_rdqwen.npz", pre=np.array(F_pre, np.float16), last=np.array(F_last, np.float16),
                        mean8=np.array(F_mean, np.float16), layers=np.array(L))
    pd.DataFrame(meta).to_parquet(out / "tau2_rdqwen_meta.parquet")
    print(f"wrote tau2_rdqwen: {len(meta)} writes in {time.time()-t0:.0f}s", flush=True)
    for h in hooks:
        h.remove()


if __name__ == "__main__":
    main()
