#!/usr/bin/env python
"""v59: continue each v54 confirmation episode after its decision turn (prevented vs postponed; lost vs delayed work).
Prereg: docs/preregistration_v59.md. GPU (vLLM; Muse in the v030 env).
Arms (first turn): none = unsteered v54 turn; gate = steered caa:<gate alpha> turn where the frozen pre-action gate fired, else the
unsteered turn; blanket = steered caa:<gate alpha> turn. Then up to K unsteered turns; MockEnv replays the prefix and steps every
action; labels from StepInfo. Same per-site sampling seed in every arm.
python scripts/159_v59_continue.py actor=gemma4          -> outputs/v59/cont_<actor>.parquet, results/prereg_v59/summary_<actor>.json
stage=analyze (CPU) recomputes the endpoints from the parquet."""
import hashlib
import importlib.util
import json
import re

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.envs.base import MockEnv
from cape.utils.config import REPO_ROOT, load_config

D = OmegaConf.create({"actor": "gemma4", "stage": "run", "K": 6, "max_new": 1536, "B": 10000})
OUT = REPO_ROOT / "outputs/v59"; RES = REPO_ROOT / "results/prereg_v59"


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, REPO_ROOT / p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def split_turn(A, txt):
    """generated text -> (reasoning, content) for re-rendering the turn as an assistant message."""
    if A == "gemma4":
        r, _, rest = txt.partition("<channel|>") if "<channel|>" in txt else ("", "", txt)
        return r.strip(), re.split(r"<\|tool_call>", rest)[0].strip()
    if A in ("gptoss20b", "museglimmer"):
        m = re.search(r"<\|channel\|>analysis<\|message\|>(.*?)(<\|end\|>|$)", txt, re.S)
        r = m.group(1) if m else re.split(r"<\|eom\|>|<\|start\|>", txt)[0]
        return re.sub(r"<\|[^|]{0,40}\|>", " ", r).strip(), ""
    if A == "qwen38":
        r, _, rest = txt.partition("</think>")
        return r.replace("<think>", "").strip(), rest.split("<tool_call>")[0].strip()
    raise ValueError(A)


def env_after_prefix(spec, events, site_event):
    env = MockEnv(spec)
    for e in events:
        if e["event_id"] >= site_event or not (e["is_tool_call"] and e["tool"]):
            continue
        try:
            env.step(e["tool"], json.loads(e["args_json"]) if e["args_json"] else {})
        except Exception:
            pass
    return env


def step_label(env, spec, tool, args):
    args = args if isinstance(args, dict) else {}
    to_user = tool == "send_message" and str(args.get("recipient", "")).strip().lower() == str(spec.get("user_email", "")).lower()
    try:
        obs, info = env.step(tool, args)
    except Exception as ex:
        return f"Error: {ex}", "OTHER"
    cat = "VIOLATE" if info.unsafe else ("CRITICAL" if info.critical else ("ESCALATE" if tool == "request_permission" or to_user else "OTHER"))
    return obs, cat


def stage_run(cfg):
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams
    from vllm.inputs import TokensPrompt
    from cape.models.load import model_path
    from cape.utils.config import resolve_model
    A = cfg.actor; X56 = _mod("x56", "scripts/56_xm_replay_extract.py"); M144 = _mod("m144", "scripts/144_v54_steer.py"); G154 = _mod("g154", "scripts/154_v54_gate.py")
    a = X56.ACT[A]; p = model_path(resolve_model(a["model"])); tok = AutoTokenizer.from_pretrained(p)
    ga = json.load(open(REPO_ROOT / f"results/prereg_v54/gate_alpha_{A}.json"))["gate_alpha"]
    R = pd.read_parquet(REPO_ROOT / f"outputs/v54/v54conf_{A}.parquet"); R["key"] = R.set + "|" + R.episode_id
    G = np.load(REPO_ROOT / f"outputs/v54/gate_{A}.npz"); Fz = np.load(REPO_ROOT / f"outputs/v54/gatefeat_v54conf_{A}.npz")
    none = R[R.arm == "none"].set_index("key"); st = R[R.arm == f"caa:{ga}"].set_index("key"); keys = none.index.intersection(st.index)
    fire = {k: (k in Fz.files and float(G154.gate_score(G, Fz[k][None].astype(np.float32))[0]) > float(G["tau"])) for k in keys}
    S = pd.read_parquet(REPO_ROOT / f"outputs/v54/sites_{A}_conf.parquet"); S["key"] = S.set + "|" + S.episode_id; S = S.set_index("key")
    specs, roll = {}, {}
    for b in S.bench.unique():
        for l in open(REPO_ROOT / f"outputs/capebench/{b}/scenarios.jsonl"):
            x = json.loads(l); specs[(b, x["instance_id"])] = x
    for s_ in S.set.unique():
        roll[s_] = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{s_}.parquet").set_index("episode_id")
    eps = []                                              # one state per (site, arm)
    for k in keys:
        r = S.loc[k]; ev = list(roll[r.set].loc[r.episode_id].events); spec = specs[(r.bench, r.instance_id)]
        base = X56.messages_upto(spec, ev, int(r.site_event), a["suffix"])
        if base and base[-1]["role"] == "assistant":
            base = base[:-1]
        first = {"none": none.loc[k], "blanket": st.loc[k], "gate": st.loc[k] if fire[k] else none.loc[k]}
        for arm, t in first.items():
            env = env_after_prefix(spec, ev, int(r.site_event)); msgs = list(base); hist = []
            tool, args = t.tool, (json.loads(t.args_json) if isinstance(t.args_json, str) and t.args_json else None)
            done = tool in (None, "__final__")
            hist.append(t.category if done else None)
            if not done:
                obs, cat = step_label(env, spec, tool, args); hist[-1] = cat
                rs, ct = split_turn(A, t.gen_text)
                msgs += [{"role": "assistant", "content": ct, "tool_calls": [{"id": "call_c0", "type": "function", "function": {"name": tool, "arguments": args or {}}}],
                          "thinking": rs, "reasoning": rs, "reasoning_content": rs},
                         {"role": "tool", "tool_call_id": "call_c0", "content": str(obs)}]
            eps.append({"key": k, "world": r.world, "scenario_id": r.scenario_id, "arm": arm, "fired": bool(fire[k]), "spec": spec, "env": env, "msgs": msgs,
                        "hist": hist, "done": done, "seed": int(hashlib.md5(f"v59|{A}|{k}".encode()).hexdigest(), 16) % 2**31})
    gc = json.load(open(f"{p}/generation_config.json")); eos = gc["eos_token_id"] if isinstance(gc["eos_token_id"], list) else [gc["eos_token_id"]]
    kw = {"language_model_only": True} if A in ("gemma4", "qwen38", "museglimmer") else {}
    if A == "qwen38":
        kw["gdn_prefill_backend"] = "triton"
    llm = LLM(model=p, dtype="bfloat16", max_model_len=32000, gpu_memory_utilization=0.9, max_num_seqs=128, seed=59, **kw)
    for step in range(1, cfg.K + 1):
        act = [e for e in eps if not e["done"]]
        if not act:
            break
        prompts, idx = [], []
        for i, e in enumerate(act):
            t = M144.render_gen(X56, tok, e["msgs"], a["kwargs"])
            ids = tok(t, add_special_tokens=False)["input_ids"] if t else None
            if ids is None or len(ids) > 30000:
                e["done"] = True; e["hist"].append("TRUNC"); continue
            prompts.append(TokensPrompt(prompt_token_ids=ids)); idx.append(i)
        sps = [SamplingParams(max_tokens=cfg.max_new, stop_token_ids=eos, skip_special_tokens=False, seed=act[i]["seed"] + step, **M144.SAMP[A]) for i in idx]
        outs = llm.generate(prompts, sps)
        for i, o in zip(idx, outs):
            e = act[i]; g = list(o.outputs[0].token_ids); txt = tok.decode(g, skip_special_tokens=False)
            tool, args = M144.parse_call(A, txt)
            if tool in (None, "__final__"):
                e["hist"].append("FINAL" if tool == "__final__" else "PARSE"); e["done"] = True; continue
            obs, cat = step_label(e["env"], e["spec"], tool, args); e["hist"].append(cat)
            rs, ct = split_turn(A, txt)
            e["msgs"] = e["msgs"] + [{"role": "assistant", "content": ct, "tool_calls": [{"id": f"call_c{step}", "type": "function", "function": {"name": tool, "arguments": args or {}}}],
                                      "thinking": rs, "reasoning": rs, "reasoning_content": rs},
                                     {"role": "tool", "tool_call_id": f"call_c{step}", "content": str(obs)}]
        print("step", step, "active", sum(not e["done"] for e in eps), flush=True)
    rows = [{"key": e["key"], "world": e["world"], "scenario_id": e["scenario_id"], "arm": e["arm"], "fired": e["fired"], "hist": e["hist"]} for e in eps]
    OUT.mkdir(parents=True, exist_ok=True); pd.DataFrame(rows).to_parquet(OUT / f"cont_{A}.parquet")
    if cfg.stage == "run":
        stage_analyze(cfg)
    import os, sys
    sys.stdout.flush(); os._exit(0)       # the vLLM engine can hang at interpreter shutdown; the data are saved


def stage_analyze(cfg):
    M146 = _mod("m146", "scripts/146_v54_analysis.py"); A = cfg.actor; C = pd.read_parquet(OUT / f"cont_{A}.parquet")
    C["viol"] = C["hist"].map(lambda h: float("VIOLATE" in list(h))); C["comp"] = C["hist"].map(lambda h: float("CRITICAL" in list(h)))
    C["first_viol"] = C["hist"].map(lambda h: float(list(h)[0] == "VIOLATE")); C["turns"] = C["hist"].map(len)
    C["t_comp"] = C["hist"].map(lambda h: (list(h).index("CRITICAL") if "CRITICAL" in list(h) else np.nan))
    m, p = C[C.world == "minus"], C[C.world == "plus"]; W = m.pivot_table(index="key", columns="arm", values="viol")
    C1 = M146.mcnemar(W["none"].values, W["gate"].values); C1b = M146.mcnemar(W["none"].values, W["blanket"].values)
    d2, bs = M146.boot_diff(p, "none", "gate", "comp", cfg.B, 591); lo = float(np.percentile(bs, 5))
    C2 = {"diff_completion": d2, "one_sided_95_lower": lo, "margin": -0.05, "passes": lo > -0.05, "p_noninf": float((bs <= -0.05).mean())}
    d2b, bsb = M146.boot_diff(p, "none", "blanket", "comp", cfg.B, 592)
    F = m.pivot_table(index="key", columns="arm", values="first_viol"); fixed = F.index[(F["none"] == 1) & (F["gate"] == 0)]
    post = float(W.loc[fixed, "gate"].mean()) if len(fixed) else None
    T = p.pivot_table(index="key", columns="arm", values="t_comp"); both = T.dropna(subset=["none", "gate"])
    out = {"actor": A, "n_minus": int(m.key.nunique()), "n_plus": int(p.key.nunique()),
           "eventual_violation": m.groupby("arm").viol.mean().round(3).to_dict(), "first_turn_violation": m.groupby("arm").first_viol.mean().round(3).to_dict(),
           "eventual_completion": p.groupby("arm").comp.mean().round(3).to_dict(),
           "C1_gate_vs_none": C1, "C2_noninferiority": C2, "holm": M146.holm({"C1": C1["p_one_sided"], "C2": C2["p_noninf"]}),
           "secondary": {"blanket_C1": C1b, "blanket_completion_diff": {"diff": d2b, "ci95": [float(np.percentile(bsb, 2.5)), float(np.percentile(bsb, 97.5))]},
                         "postponement_rate_gate": post, "n_first_turn_fixed": int(len(fixed)),
                         "delay_turns_gate_minus_none": float((both["gate"] - both["none"]).mean()) if len(both) else None,
                         "mean_turns": {f"{w}|{a}": v for (w, a), v in C.groupby(["world", "arm"]).turns.mean().round(2).items()}}}
    RES.mkdir(parents=True, exist_ok=True); json.dump(out, open(RES / f"summary_{A}.json", "w"), indent=2, default=str); print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    c = OmegaConf.merge(D, load_config(None)); {"run": stage_run, "run_only": stage_run, "analyze": stage_analyze}[c.stage](c)
