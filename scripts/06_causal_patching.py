#!/usr/bin/env python
"""Causal counterfactual activation patching (brief sections 33-37, 98-99).

Stage 1 (HF, hooks):  python scripts/06_causal_patching.py stage=patch model=Qwen/Qwen3.8-27B \
        pairs=outputs/capebench/test_pairs.parquet layers='[15,31,47,63]' continuations_per_patch=8
Stage 2 (vLLM):       python scripts/06_causal_patching.py stage=continue model=Qwen/Qwen3.8-27B
Stage 3 (CPU):        python scripts/06_causal_patching.py stage=analyze

Sites: x- episodes, decision t* = first decision after the causal variable was revealed. The patch is applied to the
decision-t* prefill (the residuals at the aligned common-suffix positions of layer l); the model then samples its
turn-t* reasoning + action under the patch (8 samples, common random seeds across conditions). Stage 2 continues each
sample to episode end WITHOUT further patching, so eventual outcomes measure a single-decision intervention.
"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from omegaconf import OmegaConf

from cape.agents.actor import ChatFormatter
from cape.agents.rollout import EpisodeState, run_lockstep, stable_seed
from cape.causal.activation_patch import CONDITIONS, condition_edit, make_patch, suffix_states
from cape.causal.pairing import make_site
from cape.utils.config import REPO_ROOT, load_config
from cape.utils.repro import snapshot, write_json

DEFAULTS = OmegaConf.create({
    "stage": "patch", "trajectories": "outputs/rollouts/pilot.parquet", "pairs": "outputs/capebench/pilot/pairs.parquet",
    "scenarios": "outputs/capebench/pilot/scenarios.jsonl", "layers": [15, 31, 47, 63],
    "continuations_per_patch": 8, "max_sites": 32, "conditions": CONDITIONS, "intervention": "state_swap",
    "require_unsafe": True, "max_suffix": 512, "max_new_tokens": 4096, "temperature": 0.6, "top_p": 0.95,
    "top_k": 20, "reasoning_effort": None, "out": "outputs/patching/pilot", "seed": 0, "max_turns": 20})


def select_sites(cfg, fmt, eps, toks, specs, pairs):
    keep_pairs = set(pairs.counterfactual_pair_id)
    cand = eps[(eps.cf_value == "unsafe") & eps.counterfactual_pair_id.isin(keep_pairs) & eps.reveal_event.notna()]
    cand = cand[cand.reveal_event + 1 < cand.n_events]
    if cfg.require_unsafe:
        u = cand[cand.unsafe_episode & (cand.first_unsafe_event >= cand.reveal_event + 1)]
        # fall back to informed-but-safe x- episodes when too few unsafe ones exist (reported separately)
        cand = pd.concat([u, cand[~cand.episode_id.isin(u.episode_id)]]) if len(u) < cfg.max_sites else u
    rng = np.random.default_rng(cfg.seed)
    cand = cand.iloc[rng.permutation(len(cand))]
    cand = cand.sort_values("unsafe_episode", ascending=False, kind="stable")
    sites, used_pairs, fam_count = [], set(), {}
    cap = max(2, int(np.ceil(cfg.max_sites / max(1, cand.scenario_family.nunique()))))
    for ep in cand.itertuples():
        if ep.counterfactual_pair_id in used_pairs or fam_count.get(ep.scenario_family, 0) >= cap:
            continue
        sm = specs[ep.instance_id]
        sp = specs[ep.instance_id.replace(".unsafe", ".safe")]
        sn = specs.get(ep.instance_id + ".nuis") or specs.get(ep.instance_id.replace(".unsafe", ".unsafe.nuis"))
        s = make_site(fmt, ep, [int(x) for x in toks.loc[ep.episode_id].input_ids], sm, sp, sn, cfg.max_suffix)
        if s is None or s.suffix_len < 4:
            continue
        s.unsafe_episode = bool(ep.unsafe_episode)
        sites.append(s)
        used_pairs.add(ep.counterfactual_pair_id)
        fam_count[ep.scenario_family] = fam_count.get(ep.scenario_family, 0) + 1
        if len(sites) >= cfg.max_sites:
            break
    return sites


def stage_patch(cfg, mcfg):
    from cape.models.load import discover_transformer_blocks, load_hf_model, load_tokenizer
    out = REPO_ROOT / cfg.out
    out.mkdir(parents=True, exist_ok=True)
    snapshot(out, cfg, model_revision=mcfg.get("revision"))
    traj = REPO_ROOT / cfg.trajectories
    eps = pd.read_parquet(traj)
    toks = pd.read_parquet(str(traj).replace(".parquet", "_tokens.parquet")).set_index("episode_id")
    specs = {json.loads(l)["instance_id"]: json.loads(l) for l in open(REPO_ROOT / cfg.scenarios)}
    pairs = pd.read_parquet(REPO_ROOT / cfg.pairs)
    tok = load_tokenizer(mcfg)
    fmt = ChatFormatter(tok, reasoning_effort=cfg.reasoning_effort or mcfg.chat.reasoning_effort)
    sites = select_sites(cfg, fmt, eps, toks, specs, pairs)
    print(f"{len(sites)} sites; unsafe-outcome sites: {sum(s.unsafe_episode for s in sites)}; "
          f"families: {pd.Series([s.family for s in sites]).value_counts().to_dict()}")
    model = load_hf_model(mcfg)
    blocks, _ = discover_transformer_blocks(model, expected=mcfg.num_layers)
    layers = [int(l) for l in cfg.layers]
    K = int(cfg.continuations_per_patch)
    I = fmt.ids
    stop = [I.tool_call_end, I.im_end, I.eot]
    done = set()
    res_path = out / "turn_samples.parquet"
    prev = pd.read_parquet(res_path) if res_path.exists() else pd.DataFrame()
    if len(prev):
        done = set(zip(prev.site_id, prev.condition, prev.layer))
    rows = prev.to_dict("records") if len(prev) else []
    site_meta = []
    t0 = time.time()
    for si, s in enumerate(sites):
        h_minus = suffix_states(model, blocks, s.minus, s.suffix_len, layers)
        h_plus = suffix_states(model, blocks, s.plus, s.suffix_len, layers)
        h_nuis = suffix_states(model, blocks, s.nuis, s.nuis_suffix_len, layers) if s.nuis else None
        other = sites[(si + 1) % len(sites)]
        h_mism = suffix_states(model, blocks, other.plus, other.suffix_len, layers) if other.scenario_id != s.scenario_id else None
        site_meta.append({"site_id": s.site_id, "episode_id": s.episode_id, "pair_id": s.pair_id,
                          "scenario_id": s.scenario_id, "family": s.family, "t_star": s.t_star, "T_harm": s.T_harm,
                          "unsafe_episode": s.unsafe_episode, "suffix_len": s.suffix_len, "diff_tokens": s.diff_tokens,
                          "has_nuis": s.nuis is not None, "prefix_len": len(s.minus),
                          **{f"delta_norm_L{l}": float((h_plus[l] - h_minus[l]).norm(dim=-1).mean()) for l in layers},
                          **{f"h_norm_L{l}": float(h_minus[l].norm(dim=-1).mean()) for l in layers}})
        for cond in cfg.conditions:
            for l in (layers if cond not in ("base_neg", "base_pos") else [-1]):
                if (s.site_id, cond, l) in done:
                    continue
                g = torch.Generator().manual_seed(stable_seed(s.site_id, cond, l, "rand"))
                ll = l if l >= 0 else layers[0]
                ce = condition_edit(cond, ll, len(s.plus if cond in ("rev", "base_pos", "rand_pos") else s.minus),
                                    h_minus[ll], h_plus[ll], h_nuis[ll] if h_nuis else None,
                                    h_mism[ll] if h_mism else None, g)
                if ce is None:
                    continue
                recip, edits = ce
                prefix = s.minus if recip == "minus" else s.plus
                x = torch.tensor([prefix] * K, device=model.device)
                torch.manual_seed(stable_seed(s.site_id, "crn"))  # common random numbers across conditions
                patch = make_patch(blocks, ll, edits, K)
                with torch.no_grad():
                    if patch is not None:
                        with patch:
                            o = model.generate(x, max_new_tokens=cfg.max_new_tokens, do_sample=True,
                                               temperature=cfg.temperature, top_p=cfg.top_p, top_k=cfg.top_k,
                                               eos_token_id=stop, pad_token_id=I.eot)
                        assert patch.n_applied > 0
                    else:
                        o = model.generate(x, max_new_tokens=cfg.max_new_tokens, do_sample=True,
                                           temperature=cfg.temperature, top_p=cfg.top_p, top_k=cfg.top_k,
                                           eos_token_id=stop, pad_token_id=I.eot)
                for k in range(K):
                    gen = o[k, len(prefix):].tolist()
                    cut = next((j for j, t in enumerate(gen) if t in stop), None)
                    rows.append({"site_id": s.site_id, "condition": cond, "layer": int(l), "sample": k, "recipient": recip,
                                 "gen_ids": gen[:cut + 1] if cut is not None else gen,
                                 "finish": "stop" if cut is not None else "length"})
            pd.DataFrame(rows).to_parquet(res_path)
        print(f"site {si + 1}/{len(sites)} {s.site_id} done, {time.time() - t0:.0f}s", flush=True)
    pd.DataFrame(site_meta).to_parquet(out / "sites.parquet")
    # store prefixes/specs needed by the continuation stage
    with open(out / "sites.jsonl", "w") as f:
        for s in sites:
            f.write(json.dumps({"site_id": s.site_id, "minus": s.minus, "plus": s.plus, "spec_minus": s.spec_minus,
                                "spec_plus": s.spec_plus, "actions": s.actions, "t_star": s.t_star}) + "\n")
    print("stage patch done ->", out)


def stage_continue(cfg, mcfg):
    from cape.agents.generators import VLLMGenerator
    from cape.models.load import load_tokenizer, model_path
    out = REPO_ROOT / cfg.out
    tok = load_tokenizer(mcfg)
    fmt = ChatFormatter(tok, reasoning_effort=cfg.reasoning_effort or mcfg.chat.reasoning_effort)
    sites = {d["site_id"]: d for d in map(json.loads, open(out / "sites.jsonl"))}
    samples = pd.read_parquet(out / "turn_samples.parquet")
    eps = []
    for r in samples.itertuples():
        s = sites[r.site_id]
        spec = s["spec_minus"] if r.recipient == "minus" else s["spec_plus"]
        partner = s["spec_plus"] if r.recipient == "minus" else s["spec_minus"]
        prefix = [int(x) for x in (s["minus"] if r.recipient == "minus" else s["plus"])]
        e = EpisodeState(spec=spec, seed=int(r.sample), fmt=fmt, partner_spec=partner, ids=list(prefix),
                         gen_mask=[0] * len(prefix), logprobs=[float("nan")] * len(prefix),
                         max_turns=max(1, cfg.max_turns - s["t_star"]),
                         tag=f".{r.site_id}.{r.condition}.L{r.layer}")
        e.fast_forward([tuple(a) if a[0] is not None else (None, None) for a in s["actions"]])
        e.consume([int(x) for x in r.gen_ids], None, r.finish)
        eps.append(e)
    print(f"continuing {len(eps)} episodes ({sum(not e.done for e in eps)} still active after patched turn)")
    gen = VLLMGenerator(model_path(mcfg), temperature=cfg.temperature, top_p=cfg.top_p, top_k=cfg.top_k,
                        max_tokens=cfg.max_new_tokens)
    run_lockstep(eps, gen)
    rows = []
    for r, e in zip(samples.itertuples(), eps):
        t = e.turns
        first = t[0]
        crit_idx = [i for i, x in enumerate(t) if x["critical"]]
        esc_idx = [i for i, x in enumerate(t) if x["escalation"]]
        rows.append({"site_id": r.site_id, "condition": r.condition, "layer": r.layer, "sample": r.sample,
                     "recipient": r.recipient,
                     "imm_critical": bool(first["critical"]), "imm_escalation": bool(first["escalation"]),
                     "imm_final": not first["is_tool_call"], "imm_tool": first["tool"],
                     "imm_unsafe": bool(first["unsafe_action"]),
                     "proceed": bool(crit_idx and (not esc_idx or crit_idx[0] < esc_idx[0])),
                     "critical_any": bool(crit_idx), "escalated": bool(esc_idx),
                     "unsafe": any(x["unsafe_action"] for x in t), "n_turns": len(t), "status": e.status,
                     "reasoning_t_star": first["reasoning_text"][:2000]})
    pd.DataFrame(rows).to_parquet(out / "outcomes.parquet")
    print("stage continue done ->", out / "outcomes.parquet")


def stage_analyze(cfg):
    from cape.causal.intervention_analysis import analyze
    name = Path(cfg.out).name
    analyze(REPO_ROOT / cfg.out, REPO_ROOT / "results" / "pilot" / ("" if name == "pilot" else name), n_boot=2000,
            seed=cfg.seed)


def main():
    cfg = OmegaConf.merge(DEFAULTS, load_config(None))
    if cfg.stage == "patch":
        stage_patch(cfg, cfg.model)
    elif cfg.stage == "continue":
        stage_continue(cfg, cfg.model)
    elif cfg.stage == "analyze":
        stage_analyze(cfg)
    else:
        raise ValueError(cfg.stage)


if __name__ == "__main__":
    main()
