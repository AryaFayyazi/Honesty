# Related-work verification (web search, 2026-09-28)

All works cited in the brief were verified to exist (see table in session notes). Corrections: TRACES is EMNLP 2026
(arXiv 2605.27690); DRAFT is arXiv 2604.03242; DreamGuard is arXiv 2608.05695 and uses a **frozen Qwen3-4B observer**
encoder (layer 31) + GRU RSSM, not actor internals.

## Closest novelty threats NOT cited in the brief (must be cited / differentiated)
1. arXiv 2607.06503 "Doomed from the Start: Early Abort of LLM Agent Episodes via a Recall-Controlled Probe Cascade"
   — linear probes on the *actor's own* activations predict *eventual episode failure* from round 1, beating
   behaviour-only monitors (TextCraft/WebShop). Same design as CAPE's Q1 but target = task failure, not safety; no patching.
2. arXiv 2608.02657 "Your Agentic LLMs Secretly Encode Indirect Prompt-Injection Exposure in Hidden States"
   — actor pre-generation hidden states predict compliance with IPI (AUROC >0.9, 8 models). Next-action horizon.
   => CAPE's prompt-injection family alone is NOT novel; the multi-step warning horizon + non-IPI families + causal
      patching are the differentiators.
3. arXiv 2605.06890 "Beyond the Black Box: Interpretability of Agentic AI Tool Use" — SAE features on GPT-OSS-20B /
   Gemma-3-27B pre-action activations, next-call risk probe + ablations.
4. arXiv 2607.29254 "Tool Specifications Matter" — hidden-state directions from tool schemas that causally suppress
   refusal in harmful tool execution.
5. TRACES / DreamGuard — prefix-risk forecasting from **observer** latents.
Also: 2606.22936 "When Agents Commit Too Soon" (representational commitment, not safety), 2607.16451 (answers committed
before reasoning), 2606.10487 (streaming hidden-state moderation probes).

## Implication for the pilot
The defensible novel combination is: (a) actor residual stream predicts unsafe tool actions *several decisions* ahead,
(b) head-to-head lead time vs action / transcript / CoT / observer-hidden-state monitors, (c) causal test with matched
counterfactual environments + activation patching with negative controls. The observer-LLM hidden-state baseline
(TRACES/DreamGuard-style) is therefore mandatory in Experiment 1.

Public benchmark access: AgentHarm is on HF (ai-safety-institute/AgentHarm, not gated; MIT + AI-safety-use clause;
only public subset of behaviours). SLEIGHT-Bench: github.com/safety-research/sleight-bench. SHADE/CUA-SHADE: scale.com/research/mrt.

## Added 2026-10-01 (user-flagged; existence verified via arxiv-troller listings; read the full papers before citing)
- **Says Block, Still Acts** (arXiv 2609.35870, Chen, Zhao, Yao, Wei; 2026-09-26, v2 09-30).
  - Finding: agents judge actions unsafe yet execute them. Safety information is still recoverable from action states,
    but judgment-side interventions barely move action preference compared with action-side ones; the judgment and
    action control subspaces only partly overlap.
  - Relation to us: complementary. They show internal judgment-action decoupling. We show a behavioral cause of it
    (believed external enforcement licenses acting against one's own judgment) and a fix that re-couples them by
    moving the judgment outside the model (the oracle: 0/1,430 acted after NOT ALLOWED).
  - Exploratory text-level support: scripts/43_judgment_action.py, results/theory/judgment_action_text.json.
- **Safety of Latent Communication in Multi-Agent Systems** (2026-09-30). Trainable latent links between agents
  increase harmful compliance, even under benign training; repairing the link restores safety. This occupies the
  earlier "pass hidden vectors between agents" idea; not part of the current CAPE line.
- **SafeCoEvo** (arXiv 2609.36580; 2026-09-29). Test-time co-evolution of a safety harness and a guard (-10.05% unsafe,
  +12.15% success). Online guard adaptation is occupied; not a CAPE claim.
- **Speculative Safety Honeypot** (2026-09). Small LLMs predict trees of future agent behavior and prune them as real
  actions arrive. Future-trajectory prediction alone is not novel.
