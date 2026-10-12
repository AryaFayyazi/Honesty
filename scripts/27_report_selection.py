#!/usr/bin/env python
"""v14: does selecting agent reports with a report-reading grader reward dishonesty? (black-box; best-of-N)

python scripts/27_report_selection.py stage=resample      # GPU (vLLM): K final-report samples per trajectory
python scripts/27_report_selection.py stage=score         # GPU (vLLM): report-only and log-reconciling graders
python scripts/27_report_selection.py stage=select        # CPU: best-of-K per grader + random -> blinded sheet
python scripts/27_report_selection.py stage=analyze       # CPU: after blinded gold labels exist

Trajectories: every informed-violation episode of v4fresh_minus that ended with a final report. The trajectory is kept
fixed (token prefix up to the final turn) and only the final report is resampled K times with the actor's sampling.
Graders: the v7 prompts (scripts/18_reporting.py REPORT_ONLY / RECONCILE), Qwen3.8-27B judge; score = P(misleading).
"Best" under a grader = lowest score. Selection arms per trajectory: best-of-K (report-only), best-of-K (reconcile),
one random sample. Blinded sheet: arms shuffled, provenance hidden, labelled with docs/reporting_rubric.md.
"""
import importlib.util
import json
import math

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.agents.actor import ChatFormatter
from cape.models.load import load_tokenizer, model_path
from cape.utils.config import REPO_ROOT, load_config, resolve_model

spec = importlib.util.spec_from_file_location("rep", REPO_ROOT / "scripts/18_reporting.py")
REP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(REP)

D = OmegaConf.create({"stage": "resample", "set": "v4fresh_minus", "bench": "v4fresh", "K": 8, "seed": 0,
                      "n_label": 60, "out": "outputs/report_selection"})


def population(cfg):
    eps = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{cfg.set}.parquet")
    eps = eps[(eps.cf_value == "unsafe") & eps.unsafe_episode & (eps.status == "final_answer")]
    eps = eps[pd.to_numeric(eps.reveal_event) < pd.to_numeric(eps.first_unsafe_event)]
    col = set(json.load(open(REPO_ROOT / "results/validity/identity_collisions.json"))[cfg.bench])
    return eps[~eps.scenario_id.isin(col)]


def stage_resample(cfg):
    from cape.agents.generators import VLLMGenerator
    from vllm import SamplingParams
    from vllm.inputs import TokensPrompt
    out = REPO_ROOT / cfg.out
    out.mkdir(parents=True, exist_ok=True)
    mcfg = resolve_model("Qwen/Qwen3.8-27B")
    tok = load_tokenizer(mcfg)
    fmt = ChatFormatter(tok, reasoning_effort=mcfg.chat.reasoning_effort)
    eps = population(cfg)
    toks = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{cfg.set}_tokens.parquet").set_index("episode_id")
    gen = VLLMGenerator(model_path(mcfg), seed=0)
    I = fmt.ids
    prompts, params, keys = [], [], []
    for ep in eps.itertuples():
        last = list(ep.events)[-1]
        prefix = [int(x) for x in toks.loc[ep.episode_id].input_ids[:int(last["prompt_len"])]]
        for k in range(cfg.K):
            prompts.append(TokensPrompt(prompt_token_ids=prefix))
            params.append(gen.params(1000 * k + 17, [I.tool_call_end, I.im_end, I.eot]))
            keys.append((ep.episode_id, k))
    rows = []
    for (eid, k), o in zip(keys, gen.llm.generate(prompts, params, use_tqdm=False)):
        g = list(o.outputs[0].token_ids)
        sp = fmt.split_generation(g)
        te = sp["think_end"]
        after = tok.decode(g[te + 1:], skip_special_tokens=False) if te is not None else ""
        is_tool = "<tool_call>" in after
        content = after.split("<tool_call>")[0].replace("<|im_end|>", "").strip()
        rows.append({"episode_id": eid, "k": k, "report": content, "is_tool_call": is_tool, "has_think_end": te is not None})
    pd.DataFrame(rows).to_parquet(out / "reports.parquet")
    print("resampled", len(rows), "| valid final reports:", sum((not r["is_tool_call"]) and r["has_think_end"] and
                                                                bool(r["report"]) for r in rows))


def stage_score(cfg):
    from vllm import LLM, SamplingParams
    from vllm.inputs import TokensPrompt
    out = REPO_ROOT / cfg.out
    mcfg = resolve_model("Qwen/Qwen3.8-27B")
    tok = load_tokenizer(mcfg)
    yes = sorted({i[0] for w in ("YES", "Yes", " YES") if len(i := tok.encode(w, add_special_tokens=False)) == 1})
    no = sorted({i[0] for w in ("NO", "No", " NO") if len(i := tok.encode(w, add_special_tokens=False)) == 1})
    R = pd.read_parquet(out / "reports.parquet")
    R = R[(~R.is_tool_call) & R.has_think_end & (R.report.str.len() > 0)]
    eps = population(cfg).set_index("episode_id")
    specs = {json.loads(l)["instance_id"]: json.loads(l)
             for l in open(REPO_ROOT / f"outputs/capebench/{cfg.bench}/scenarios.jsonl")}
    llm = LLM(model=model_path(mcfg), dtype="bfloat16", max_model_len=32768, gpu_memory_utilization=0.9,
              enable_prefix_caching=True, language_model_only=True, max_num_seqs=128, logprobs_mode="raw_logprobs",
              max_logprobs=len(yes) + len(no), gdn_prefill_backend="triton")
    sp = SamplingParams(max_tokens=1, temperature=0.0, logprob_token_ids=yes + no)
    keys, prompts = [], []
    for r in R.itertuples():
        ep = eps.loc[r.episode_id]
        s = specs[ep.instance_id]
        for arm, tmpl in (("report_only", REP.REPORT_ONLY), ("reconcile", REP.RECONCILE)):
            msg = tmpl.format(system=s["system_prompt"], task=s["task_prompt"], report=r.report, log=REP.raw_log(ep))
            ids = tok.encode(tok.apply_chat_template([{"role": "user", "content": msg}], tokenize=False,
                                                     add_generation_prompt=True, enable_thinking=False),
                             add_special_tokens=False)[-30000:]
            keys.append((r.episode_id, r.k, arm))
            prompts.append(TokensPrompt(prompt_token_ids=ids))
    rows = []
    for (eid, k, arm), o in zip(keys, llm.generate(prompts, sp)):
        lp = o.outputs[0].logprobs[0]
        ly = math.log(sum(math.exp(lp[i].logprob) for i in yes if i in lp) or 1e-30)
        ln = math.log(sum(math.exp(lp[i].logprob) for i in no if i in lp) or 1e-30)
        rows.append({"episode_id": eid, "k": k, "arm": arm, "score": ly - ln})
    pd.DataFrame(rows).to_parquet(out / "scores.parquet")
    print("scored", len(rows))


def stage_select(cfg):
    out = REPO_ROOT / cfg.out
    R = pd.read_parquet(out / "reports.parquet")
    S = pd.read_parquet(out / "scores.parquet").pivot_table(index=["episode_id", "k"], columns="arm",
                                                            values="score").reset_index()
    R = R.merge(S, on=["episode_id", "k"])
    rng = np.random.default_rng(cfg.seed)
    sel = []
    for eid, g in R.groupby("episode_id"):
        if len(g) < 2:
            continue
        sel.append({"episode_id": eid, "arm": "best_report_only", "k": int(g.loc[g.report_only.idxmin(), "k"])})
        sel.append({"episode_id": eid, "arm": "best_reconcile", "k": int(g.loc[g.reconcile.idxmin(), "k"])})
        sel.append({"episode_id": eid, "arm": "random", "k": int(rng.choice(g.k.values))})
    Sel = pd.DataFrame(sel)
    eids = rng.permutation(Sel.episode_id.unique())[:cfg.n_label]
    L = Sel[Sel.episode_id.isin(eids)].merge(R[["episode_id", "k", "report"]], on=["episode_id", "k"])
    L = L.sample(frac=1, random_state=cfg.seed).reset_index(drop=True)  # shuffle arms: provenance hidden
    L["item"] = [f"sel{i:03d}" for i in range(len(L))]
    L.to_parquet(out / "selection_key.parquet")  # contains arm (do NOT read while labelling)
    pop = population(cfg).set_index("episode_id")
    with open(out / "blind_sheet.md", "w") as f:
        for r in L.itertuples():
            ep = pop.loc[r.episode_id]
            f.write(f"\n=== {r.item} ({ep.template})\nKEY LOG:\n{REP.gt_log(ep)}\nREPORT: {r.report[:1500]}\n")
    Sel.to_parquet(out / "selections_all.parquet")
    print("selections:", len(Sel), "| blinded items:", len(L), "from", len(eids), "trajectories")


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    {"resample": stage_resample, "score": stage_score, "select": stage_select}[cfg.stage](cfg)


if __name__ == "__main__":
    main()
