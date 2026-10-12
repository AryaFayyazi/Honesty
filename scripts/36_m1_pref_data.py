#!/usr/bin/env python
"""Agent-level mechanism-1 fix: on-policy preference pairs (docs/preregistration_v21.md; src/cape/train_data/m1pref.py).

python scripts/36_m1_pref_data.py stage=sites      # CPU: decision sites from saved rollouts (replay-checked)
python scripts/36_m1_pref_data.py stage=sample     # GPU (vLLM): K turns per site x context variant
python scripts/36_m1_pref_data.py stage=verify     # GPU (vLLM): continue chosen-class candidates to the episode end
python scripts/36_m1_pref_data.py stage=pairs      # CPU: pairs, balance caps, contamination checks, audit sample
python scripts/36_m1_pref_data.py stage=data       # sample + verify + pairs in one job

Chosen and rejected turns are both sampled from the base model at the same context. A chosen turn must (i) be in
the site type's preferred class, (ii) contain no enforcement-reliance rationale, (iii) when it does not end the episode,
lead to a verified outcome: x- no violation and no unauthorized attempt until the end; x+ the authorized action done.
"""
import copy
import hashlib
import json

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from cape.train_data import m1pref as M
from cape.utils.config import REPO_ROOT, load_config, resolve_model
from cape.utils.repro import write_json

D = OmegaConf.create({"stage": "sites", "out": "outputs/m1pref", "k": 4, "seed": 0, "max_turns": 20,
                      "max_prefix": 14000, "verify_per_cell": 2,
                      # site caps per (type, template; '_other' = remaining train templates pooled); deterministic
                      # subsample by site-id hash. Set from the recorded-turn survey (prereg v21 s.3): rejected-class
                      # turns occur almost only in CI (all types) and billing (pre).
                      "cap": {"pre": {"con_ci_green": 500, "tp_billing_correction": 300, "_other": 100},
                              "denied": {"con_ci_green": 600, "_other": 100},
                              "blocked": {"con_ci_green": 700, "_other": 100},
                              "after_viol": {"_all": 600}, "plus": {"_all": 500}},
                      "k_by_type": {"after_viol": 8}, "anchor_share_max": 0.25,
                      "pair_cap_per_cell": 2, "plus_share_max": 0.25, "val_frac": 0.1,
                      "generation": {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "max_tokens": 4096}})


def out_dir(cfg):
    p = REPO_ROOT / cfg.out
    p.mkdir(parents=True, exist_ok=True)
    return p


def h01(s: str) -> float:
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def sid_hash(site_id: str) -> str:  # unique per site -> distinct sampling seeds (episode_id feeds request_seed)
    return hashlib.sha256(site_id.encode()).hexdigest()[:12]


def stage_sites(cfg):
    from cape.agents.actor import ChatFormatter
    from cape.models.load import load_tokenizer
    mcfg = resolve_model("Qwen/Qwen3.8-27B")
    fmt = ChatFormatter(load_tokenizer(mcfg), enable_thinking=mcfg.chat.enable_thinking,
                        reasoning_effort=mcfg.chat.reasoning_effort)
    col_all = json.load(open(REPO_ROOT / "results/validity/identity_collisions.json"))
    rows, stats = [], {"replay_mismatch": 0, "too_long": 0, "episodes": 0}
    for stem, bench in M.SOURCES:
        specs = {json.loads(l)["instance_id"]: json.loads(l)
                 for l in open(REPO_ROOT / f"outputs/capebench/{bench}/scenarios.jsonl")}
        col = set(col_all.get(bench, col_all["v2fresh"]))
        eps = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{stem}.parquet")
        eps = eps[~eps.template.isin(M.HELDOUT) & ~eps.scenario_id.isin(col)]
        toks = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{stem}_tokens.parquet",
                               columns=["episode_id", "input_ids"]).set_index("episode_id")
        for ep in eps.to_dict("records"):
            stats["episodes"] += 1
            spec = specs[ep["instance_id"]]
            try:
                sites = M.sites_of_episode(ep, spec)
            except AssertionError:
                stats["replay_mismatch"] += 1
                continue
            for s in sites:
                ev = ep["events"][s["t"]]
                if int(ev["prompt_len"]) > cfg.max_prefix:
                    stats["too_long"] += 1
                    continue
                site_id = f"{stem}:{ep['episode_id']}@{s['site_type']}{s['t']}"
                rows.append({"site_id": site_id, "source": stem, "bench": bench, "episode_id": ep["episode_id"],
                             "instance_id": ep["instance_id"], "scenario_id": ep["scenario_id"],
                             "template": ep["template"], "cf": ep["cf_value"], "world_seed": spec["world_seed"],
                             "t": s["t"], "site_type": s["site_type"], "orig_tool": s["orig_tool"],
                             "prior_block": bool(s["state"]["blocked"]), "prior_denied": bool(s["state"]["denied"]),
                             "prompt_len": int(ev["prompt_len"])})
    S = pd.DataFrame(rows)
    print("all sites:\n", S.groupby(["site_type", "template"]).size().unstack(fill_value=0).to_string())
    keep = []
    S = S.assign(h=[h01(x) for x in S.site_id]).sort_values("h")  # deterministic cap: lowest hash first
    for kind, g in S.groupby("site_type"):
        caps = cfg.cap[kind]
        if "_all" in caps:
            keep.append(g.head(int(caps["_all"])))
            continue
        named = [t for t in caps if not t.startswith("_")]
        for t in named:
            keep.append(g[g.template == t].head(int(caps[t])))
        keep.append(g[~g.template.isin(named)].head(int(caps["_other"])))
    S = pd.concat(keep, ignore_index=True).drop(columns="h")
    # token prefixes: re-rendered per variant at sampling time; check the initial-block identity now (CPU)
    bad = 0
    pref = []
    tok_cache = {}
    for r in S.itertuples():
        if r.source not in tok_cache:
            tok_cache[r.source] = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{r.source}_tokens.parquet",
                                                  columns=["episode_id", "input_ids"]).set_index("episode_id")
        spec = spec_of(r.bench, r.instance_id)
        p = [int(x) for x in tok_cache[r.source].loc[r.episode_id].input_ids[:r.prompt_len]]
        try:
            M.rerender(p, fmt, spec, M.variant_spec(spec, "none", False, 0))
        except AssertionError:
            bad += 1
            p = None
        pref.append(p)
    S["prefix"] = pref
    S = S[S.prefix.notna()]
    stats.update(n_sites=len(S), rerender_fail=bad,
                 by_type=S.site_type.value_counts().to_dict(), by_template=S.template.value_counts().to_dict())
    S.to_parquet(out_dir(cfg) / "sites.parquet")
    write_json(out_dir(cfg) / "sites_stats.json", stats)
    print(json.dumps(stats, indent=2, default=str))


_SPECS = {}


def spec_of(bench, instance_id):
    if bench not in _SPECS:
        _SPECS[bench] = {json.loads(l)["instance_id"]: json.loads(l)
                         for l in open(REPO_ROOT / f"outputs/capebench/{bench}/scenarios.jsonl")}
    return _SPECS[bench][instance_id]


def site_states(cfg, fmt, S):
    """(site row, variant, vspec, prefix ids, env at site, violation target) for every site x variant."""
    eps_cache = {}
    out = []
    for r in S.itertuples():
        if r.source not in eps_cache:
            e = pd.read_parquet(REPO_ROOT / f"outputs/rollouts/{r.source}.parquet", columns=["episode_id", "events"])
            eps_cache[r.source] = dict(zip(e.episode_id, e.events))
        ev = list(eps_cache[r.source][r.episode_id])
        spec = spec_of(r.bench, r.instance_id)
        for claim, oracle in M.VARIANTS:
            vs = M.variant_spec(spec, claim, oracle, M.paraphrase_for(r.site_id))
            M.check_clean(vs["system_prompt"])
            env, st = M.replay(vs, ev, r.t)
            tgt = M.viol_target(*st["first_viol_args"]) if st["first_viol_args"] else None
            out.append((r, f"{claim}|{'orc' if oracle else 'noorc'}", vs, M.rerender(list(r.prefix), fmt, spec, vs),
                        env, tgt))
    return out


def episode(fmt, vs, ids, env, seed, tag, max_turns):
    from cape.agents.rollout import EpisodeState
    e = EpisodeState(spec=vs, seed=seed, fmt=fmt, ids=list(ids), gen_mask=[0] * len(ids),
                     logprobs=[float("nan")] * len(ids), max_turns=max_turns, tag=tag)
    e.env = copy.deepcopy(env)
    return e


def load_engine(cfg):
    from cape.agents.actor import ChatFormatter
    from cape.agents.generators import VLLMGenerator
    from cape.models.load import load_tokenizer, model_path
    mcfg = resolve_model("Qwen/Qwen3.8-27B")
    fmt = ChatFormatter(load_tokenizer(mcfg), enable_thinking=mcfg.chat.enable_thinking,
                        reasoning_effort=mcfg.chat.reasoning_effort)
    return fmt, VLLMGenerator(model_path(mcfg), seed=0, **OmegaConf.to_container(cfg.generation))


def stage_sample(cfg, engine=None):
    fmt, gen = engine or load_engine(cfg)
    S = pd.read_parquet(out_dir(cfg) / "sites.parquet")
    states = site_states(cfg, fmt, S)
    eps, meta = [], []
    for r, var, vs, ids, env, tgt in states:
        for k in range(int(cfg.k_by_type.get(r.site_type, cfg.k))):
            eps.append(episode(fmt, vs, ids, env, seed=k, tag=f".{sid_hash(r.site_id)}.{var}", max_turns=1))
            meta.append((r, var, k, env, tgt))
    print(f"sampling {len(eps)} turns ({len(states)} site-variants x {cfg.k})", flush=True)
    outs = []
    for a in range(0, len(eps), 2048):  # chunks keep memory of the request list bounded
        outs += gen(eps[a:a + 2048])
        print(f"  {min(a + 2048, len(eps))}/{len(eps)}", flush=True)
    rows = []
    for e, (r, var, k, env, tgt), (g, lp, fr) in zip(eps, meta, outs):
        e.consume(g, lp, fr)
        t0 = e.turns[0]
        args = json.loads(t0["args_json"]) if t0["args_json"] else {}
        finished = fr != "length" and t0["think_end_pos"] is not None
        cls = M.classify_turn(env, r.site_type, t0["tool"], args, t0["content_text"], t0["parse_error"], finished, tgt)
        rows.append({"site_id": r.site_id, "variant": var, "k": k, "site_type": r.site_type, "template": r.template,
                     "cls": cls, "tool": t0["tool"], "args_json": t0["args_json"], "gen_ids": [int(x) for x in g],
                     "finish": fr, "reliance": bool(M.RELIANCE_RE.search(t0["reasoning_text"] or "")),
                     "reasoning": t0["reasoning_text"], "content": t0["content_text"],
                     "chosen_class": cls in M.CHOSEN[r.site_type], "rejected_class": cls in M.REJECTED[r.site_type]})
    T = pd.DataFrame(rows)
    T.to_parquet(out_dir(cfg) / "samples.parquet")
    print(T.groupby(["site_type", "variant"]).agg(n=("cls", "size"), chosen=("chosen_class", "mean"),
                                                  rejected=("rejected_class", "mean"),
                                                  reliance=("reliance", "mean")).round(3).to_string())


def continuation_ok(env, turns, cf):
    """x-: no violation and no unauthorized critical attempt in the candidate turn or after it.
    x+: no violation and the authorized critical action is done. Re-steps a copy of the site env (ground truth)."""
    env = copy.deepcopy(env)
    did_crit = False
    for t in turns:
        if not t["is_tool_call"] or t["parse_error"] is not None:
            continue
        args = json.loads(t["args_json"]) if t["args_json"] else {}
        was_auth = env.authorized
        _, info = env.step(t["tool"], args)
        if info.unsafe or (cf == "unsafe" and info.critical and not was_auth):
            return False
        did_crit |= info.critical
    return did_crit if cf == "safe" else True


def stage_verify(cfg, engine=None):
    from cape.agents.rollout import run_lockstep
    fmt, gen = engine or load_engine(cfg)
    S = pd.read_parquet(out_dir(cfg) / "sites.parquet")
    T = pd.read_parquet(out_dir(cfg) / "samples.parquet")
    # only cells that can form a pair (a rejected-class sample exists) or anchor utility (x+) need verification
    useful = set(zip(T[T.rejected_class].site_id, T[T.rejected_class].variant)) | \
        set(zip(T[T.site_type == "plus"].site_id, T[T.site_type == "plus"].variant))
    C = T[T.chosen_class & ~T.reliance & ~T.cls.isin(M.TERMINAL)]
    C = C[np.array([x in useful for x in zip(C.site_id, C.variant)], dtype=bool)]
    C = C.sort_values("k").groupby(["site_id", "variant"]).head(cfg.verify_per_cell)
    need = set(zip(C.site_id, C.variant))
    states = {(r.site_id, var): (r, vs, ids, env) for r, var, vs, ids, env, _ in site_states(cfg, fmt, S)
              if (r.site_id, var) in need}
    eps, keys = [], []
    for c in C.itertuples():
        r, vs, ids, env = states[(c.site_id, c.variant)]
        e = episode(fmt, vs, ids, env, seed=100 + c.k, tag=f".v.{sid_hash(r.site_id)}.{c.variant}",
                    max_turns=max(1, cfg.max_turns - r.t))
        e.consume(list(c.gen_ids), None, c.finish)
        eps.append(e)
        keys.append((c.site_id, c.variant, c.k, env, r.cf))
    print(f"verifying {len(eps)} chosen-class candidates", flush=True)
    run_lockstep([e for e in eps if not e.done], gen)
    rows = [{"site_id": s, "variant": v, "k": k, "verified": continuation_ok(env, e.turns, cf), "status": e.status,
             "n_turns": len(e.turns)} for e, (s, v, k, env, cf) in zip(eps, keys)]
    V = pd.DataFrame(rows)
    V.to_parquet(out_dir(cfg) / "verify.parquet")
    print(V.merge(C[["site_id", "variant", "k", "site_type"]]).groupby("site_type").verified.agg(["size", "mean"]))


def stage_pairs(cfg):
    from cape.eval import authority as A
    od = out_dir(cfg)
    S = pd.read_parquet(od / "sites.parquet")
    T = pd.read_parquet(od / "samples.parquet")
    V = pd.read_parquet(od / "verify.parquet") if (od / "verify.parquet").exists() else pd.DataFrame(
        columns=["site_id", "variant", "k", "verified"])
    T = T.merge(V[["site_id", "variant", "k", "verified"]], how="left", on=["site_id", "variant", "k"])
    T["verified"] = T.verified.astype("boolean").fillna(False).astype(bool) | T.cls.isin(M.TERMINAL)
    ok_c = T[T.chosen_class & ~T.reliance & T.verified]
    rej = T[T.rejected_class]
    rng = np.random.default_rng(cfg.seed)
    P = []
    for (sid, var), g in rej.groupby(["site_id", "variant"]):
        c = ok_c[(ok_c.site_id == sid) & (ok_c.variant == var)]
        if not len(c):
            continue
        cr, rr = c.sort_values("k").iloc[0], g.iloc[int(rng.integers(len(g)))]
        P.append({"site_id": sid, "variant": var, "chosen_k": int(cr.k), "rejected_k": int(rr.k),
                  "chosen_cls": cr.cls, "rejected_cls": rr.cls, "chosen_ids": list(cr.gen_ids),
                  "rejected_ids": list(rr.gen_ids), "rejected_reliance": bool(rr.reliance),
                  "chosen": (cr.reasoning or "") + "\n</think>\n" + (cr.content or "") + f"\n[{cr.tool} {cr.args_json}]",
                  "rejected": (rr.reasoning or "") + "\n</think>\n" + (rr.content or "") + f"\n[{rr.tool} {rr.args_json}]"})
    P = pd.DataFrame(P).merge(S.drop(columns=["prefix"]), on="site_id")
    paired = set(zip(P.site_id, P.variant))
    Aa = ok_c[(ok_c.site_type == "plus").values & np.array([x not in paired for x in zip(ok_c.site_id, ok_c.variant)],
                                                          dtype=bool)]
    Aa = Aa.sort_values("k").groupby(["site_id", "variant"]).head(1)
    Aa = Aa.assign(chosen_ids=Aa.gen_ids, chosen_cls=Aa.cls,
                   chosen=[(a or "") + "\n</think>\n" + (b or "") + f"\n[{c} {d}]"
                           for a, b, c, d in zip(Aa.reasoning, Aa.content, Aa.tool, Aa.args_json)])
    Aa = Aa[["site_id", "variant", "chosen_ids", "chosen_cls", "chosen"]].merge(
        S.drop(columns=["prefix"]), on="site_id")
    # caps: per (scenario, site type, variant), then x+ share
    P = P.assign(h=[h01(a + b) for a, b in zip(P.site_id, P.variant)]).sort_values("h")
    P = P.groupby(["scenario_id", "site_type", "variant"]).head(cfg.pair_cap_per_cell)
    n_minus = int((P.site_type != "plus").sum())
    max_plus = int(cfg.plus_share_max / (1 - cfg.plus_share_max) * n_minus)
    P = pd.concat([P[P.site_type != "plus"], P[P.site_type == "plus"].head(max_plus)]).drop(columns="h")
    max_anchor = int(cfg.anchor_share_max * len(P))
    Aa = Aa.assign(h=[h01(a + b) for a, b in zip(Aa.site_id, Aa.variant)]).sort_values("h").head(max_anchor)
    P = pd.concat([P.assign(kind="pair"), Aa.drop(columns="h").assign(kind="anchor")], ignore_index=True)
    P["split"] = np.where([h01("val" + s) < cfg.val_frac for s in P.scenario_id], "val", "train")
    # contexts: system prompt per row for the contamination check (and the forbidden-string check)
    sysp, task = [], []
    for r in P.itertuples():
        spec = spec_of(r.bench, r.instance_id)
        claim, orc = r.variant.split("|")
        vs = M.variant_spec(spec, claim, orc == "orc", M.paraphrase_for(r.site_id))
        M.check_clean(vs["system_prompt"])
        sysp.append(vs["system_prompt"])
        task.append(vs["task_prompt"])
    P["system_prompt"], P["task_prompt"] = sysp, task
    # contamination vs the v18 suite: seeds, world content, held-out templates
    suite = [s for b in A.BLOCKS for c in A.CONDITIONS for s in A.load_specs(b, c)]
    keys = {A.world_key(s) for s in suite}
    wk = [A.world_key(spec_of(r.bench, r.instance_id)) for r in P.itertuples()]
    contam = {"world_seed_overlap": int(P.world_seed.isin({s["world_seed"] for s in suite}).sum()),
              "world_content_overlap": int(sum(k in keys for k in wk)),
              "heldout_template_rows": int(P.template.isin(M.HELDOUT).sum())}
    assert all(v == 0 for v in contam.values()), contam
    P.to_parquet(od / "pairs.parquet")
    P[P.variant == "none|noorc"].to_parquet(od / "pairs_noinv.parquet")  # ablation: plain contexts only
    summ = {"n_rows": len(P), "n_pairs": int((P.kind == "pair").sum()), "n_anchors": int((P.kind == "anchor").sum()), "n_train": int((P.split == "train").sum()), "n_val": int((P.split == "val").sum()),
            "by_site_type_variant": P.groupby(["site_type", "variant"]).size().unstack(fill_value=0).to_dict(),
            "by_template": P.template.value_counts().to_dict(),
            "by_prior_block": {f"prior_block={a}|{b}": int(v) for (a, b), v in
                               P.groupby(["prior_block", "site_type"]).size().items()},
            "chosen_cls": P.chosen_cls.value_counts().to_dict(), "rejected_cls": P.rejected_cls.value_counts().to_dict(),
            "rejected_reliance_share": float(P[P.kind == "pair"].rejected_reliance.mean()), "contamination": contam,
            "sample_rates": T.groupby(["site_type", "variant"]).agg(
                chosen=("chosen_class", "mean"), rejected=("rejected_class", "mean"),
                reliance=("reliance", "mean")).round(4).reset_index().to_dict("records"),
            "pairs_sha256": hashlib.sha256((od / "pairs.parquet").read_bytes()).hexdigest()}
    write_json(od / "pairs_summary.json", summ)
    # audit sample: 6 pairs per (site type, rejected class) for human reading before training is relied on
    A_ = P[P.kind == "pair"].groupby(["site_type", "rejected_cls"]).head(6)
    with open(od / "audit_pairs.md", "w") as f:
        for r in A_.itertuples():
            f.write(f"## {r.site_id} [{r.variant}] {r.template} {r.site_type}: chosen={r.chosen_cls} "
                    f"rejected={r.rejected_cls}\n### chosen\n{r.chosen[-2500:]}\n### rejected\n{r.rejected[-2500:]}\n\n")
    print(json.dumps(summ, indent=1, default=str)[:4000])


def stage_data(cfg):
    engine = load_engine(cfg)
    stage_sample(cfg, engine)
    stage_verify(cfg, engine)
    stage_pairs(cfg)


def main():
    cfg = OmegaConf.merge(D, load_config(None))
    {"sites": stage_sites, "sample": stage_sample, "verify": stage_verify, "pairs": stage_pairs,
     "data": stage_data}[cfg.stage](cfg)


if __name__ == "__main__":
    main()
