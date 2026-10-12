# Novelty / prior-art check (v29), 2026-10-01

Scope: the five claims of the CAPE paper (observability bound, epistemic compositional gate, seed-fingerprint confound, matched-pair identification + 1/sqrt(K) transfer, cheapness of white-box self-monitoring). I opened every work cited below (arXiv abstract or HTML, the vendor blog, or the GitHub PR) and checked its authors, date and main content. Where only part of a paper could be checked, the entry says so. Nothing is cited from memory alone.

Verdict key: **novel** = I found no prior work making the claim. **partially novel** = the core idea or math exists, but our setting, scope or combination does not. **known** = already established; cite it, don't claim it.

---

## Claim 1: Observability bound (TPR(alpha) = alpha before the first differing observation; ceiling 1 - pi_u(1-alpha))

**Verdict: partially novel.** The math is textbook: if two worlds give the monitor's input the same distribution, no test does better than TPR = FPR (Le Cam two-point / Neyman-Pearson; TPR - FPR <= TV). A 2026 paper states exactly this bound for agent monitors. We should not present the inequality as new. What I could not find anywhere:
- (a) the coupling of the agent's **own context and internal state** up to the first differing tool observation, which brings **white-box self-monitors / activation probes** (not only external judges) under the bound;
- (b) the informed / uninformed split of violations and the per-model **detectability ceiling 1 - pi_u(1-alpha)**;
- (c) an empirical check that probes sit at chance (AUROC ~0.5) on the uninformed stratum while informed actions decode at 0.75-0.95, across three open models.

### Closest prior work

1. **Hu, Y. & Wang, R. (2026). "When Local Monitors Miss Compositional Harm: Diagnosing Distributed Backdoors in Multi-Agent Systems." arXiv:2607.11751.** https://arxiv.org/abs/2607.11751
   - Defines ε-local indistinguishability (TV(P_ben, P_att) <= ε under an observation function v). Proposition 1: any randomized decision rule seeing v(x_i) has TPR − FPR <= TV <= ε. They call this an "observability boundary": "no detector on that view can catch them, however strong it is."
   - **Difference:** it is about multi-agent payload fragmentation and external monitors' views. There is no agent-internal coupling, no white-box or activation monitors, no counterfactual environment pairs, no "first differing observation", and no informed/uninformed ceiling.
   - **This is the closest formal scoop. Cite it, and present our bound as an instance of the same TV principle applied to the agent's own information state.**
2. **Guan, M. Y., Wang, M., Carroll, M., Dou, Z., Wei, A. Y., Williams, M., Arnav, B., Huizinga, J., Kivlichan, I., Glaese, M., Pachocki, J., Baker, B. (2025). "Monitoring Monitorability." arXiv:2512.18311 (OpenAI).** https://arxiv.org/abs/2512.18311
   - Builds "intervention evaluations": an environment intervention X ∈ {0,1} with matched arms, then asks whether a CoT monitor can infer the change. Introduces a minimal-criterion TPR and g-mean².
   - **Difference:** black-box CoT monitors only. No impossibility theorem. The intervention is *observed* by the model, so it targets our informed case. Their matched-arm design is the methodological precedent for our counterfactual pairs, so we must cite it.
3. **Srivastava, V. (2026). "Fundamental Limits of Black-Box Safety Evaluation: Information-Theoretic and Computational Barriers from Latent Context Conditioning." arXiv:2602.16984.** https://arxiv.org/abs/2602.16984
   - Impossibility results for *evaluators* estimating deployment risk from latent-trigger policies, with a sample-complexity result for white-box probing.
   - **Difference:** about pre-deployment evaluation of a latent-conditioned policy, not runtime monitoring of single actions. Their white-box case remains possible, whereas ours is impossible because the information is absent from the agent itself.
4. **Arike, R., Moreno, R. M., Subramani, R., Biswas, S., Ward, F. R. (2026). "How does information access affect LLM monitors' ability to detect sabotage?" arXiv:2601.21112; ICML 2026 poster.** https://arxiv.org/abs/2601.21112
   - Empirical "less-is-more" effect for monitors' information access. No theoretical bound. Reviewers will associate it with "information access limits monitors", so cite it.
5. **Kinniment, M., Nix, S., Broadley, T., Wijk, H., Parikh, N. (METR, Jan 2026). "Early work on monitorability evaluations."** https://metr.org/blog/2026-01-19-early-work-on-monitorability-evaluations/
   - Informally notes that some side tasks leave no observable trace ("unfair" to monitors) and that "silent computation" limits monitorability. Not formalized.
6. **Emmons, S., Jenner, E., Elson, D. K., Saurous, R. A., Rajamanoharan, S., Chen, H., Shafkat, I., Shah, R. (2025). "When Chain of Thought is Necessary, Language Models Struggle to Evade Monitors." arXiv:2507.05246.** https://arxiv.org/abs/2507.05246
   - Argues monitorability comes from CoT *necessity*. Their conceptual converse: when nothing in the context distinguishes the cases, nothing is monitorable. No theorem.
7. **Korbak, T., Balesni, M., Barnes, E., Bengio, Y., Benton, J., et al. (41 authors) (2025). "Chain of Thought Monitorability: A New and Fragile Opportunity for AI Safety." arXiv:2507.11473.** https://arxiv.org/abs/2507.11473 — position paper; standard citation for CoT-monitor limits.
8. **Baker, B., Huizinga, J., Gao, L., Dou, Z., Guan, M. Y., Madry, A., Zaremba, W., Pachocki, J., Farhi, D. (2025). "Monitoring Reasoning Models for Misbehavior and the Risks of Promoting Obfuscation." arXiv:2503.11926.** https://arxiv.org/abs/2503.11926
9. **Jiao, D. & Anderson, A. (2026). "Agent Safety From Within: Detecting Harmful Trajectories from LLM Internal States" (TACIT). arXiv:2609.33039.** https://arxiv.org/abs/2609.33039
   - On byte-identical message/action pairs that differ only in the *called tool's schema*, guard models are at chance while frozen-backbone probes reach 0.981 rank accuracy (placebo edit 0.544).
   - **Useful contrast:** in their pairs the difference *is* in the context, so probes can decode it. In ours it is not, so nothing can. Present this as the informed / uninformed boundary.
10. **Tang, Y., Li, T., Li, E., Maddison, C. J., Dong, H., Ruan, Y. (2025). "LM Agents May Fail to Act on Their Own Risk Knowledge." arXiv:2508.13465.** https://arxiv.org/abs/2508.13465
    - Knowledge-action gap: agents know a risk but act anyway. Behavioral analogue of our informed stratum.

### What we can safely claim
- "We apply the standard indistinguishability (TV / two-point) argument to the agent's own information state. Using a coupling of matched environments up to the first differing tool observation, we show that any context-measurable monitor, *including white-box probes of the agent's activations*, has TPR(α) = α on uninformed violations. A per-model detectability ceiling 1 − π_u(1−α) follows."
- Avoid "first impossibility result for AI monitors." Hu & Wang (2026) and Srivastava (2026) both have impossibility-style results. Say: "to our knowledge, the first to (i) extend this bound to white-box self-monitoring and (ii) quantify the uninformed share π_u and the resulting ceiling empirically."
- State the scope explicitly. The bound applies to *distinguishing a violation from its authorized twin*. It does not rule out flagging an action as *unverified* (acting without the distinguishing observation), which is claim 2's lever. Without this caveat, reviewers will call the result trivial ("the information isn't there").

---

## Claim 2: Epistemic compositional gate (Critical ∧ (Unauthorized|informed ∨ Unverified); per-predicate calibrated probes; posterior composition; verify-before-act; episode-level split-conformal false-block bound)

**Verdict: partially novel. Each component has close 2025-2026 precedents. The specific combination appears new:**
- an *epistemic* decomposition with an "Unverified" predicate learned from counterfactual pairs without violation labels;
- AND/OR composition of calibrated residual-stream probe posteriors;
- an episode-level conformal bound on the **false-block** rate.

### Closest prior work, by component

**Probe-based gating / monitoring of agent actions (activation probes on the agent's own model):**
- **Dong, J., Liu, Y., Zhang, M., Deng, N., Xu, P., Zhang, X., Zhang, T., Zhang, J., Qiu, H. (2026). "Your Agentic LLMs Secretly Encode Indirect Prompt-Injection Exposure in Hidden States." arXiv:2608.02657.** https://arxiv.org/abs/2608.02657
  - Linear probes on the agent's hidden states detect IPI exposure (0.90+ AUROC on unseen attacks). A **probe-gated** defense (AGRI) inserts anti-injection reasoning above threshold 0.5.
  - No matched pairs, no conformal calibration, no cost analysis (confirmed in their HTML). **This is the closest "probe gates the agent's own action" precedent.**
- **Ruan, K., Huang, Z., Zhou, Z., Wei, Q., Lin, J., Wang, X., Sun, H. (2026). "Doomed from the Start: Early Abort of LLM Agent Episodes via a Recall-Controlled Probe Cascade." arXiv:2607.06503.** https://arxiv.org/abs/2607.06503
  - Probes on frozen-policy activations, no auxiliary LLM pass. Distribution-free calibration of a per-round cascade with an **episode-level recall guarantee** (successful episodes survive all gates at the target rate).
  - **Very close in mechanics** to our episode-level split-conformal false-block bound: their "successful episode wrongly aborted" is our "benign episode wrongly blocked". But they predict *task failure*, not safety violations, and use no predicate decomposition. **Reviewers will raise this; cite it and differentiate.**
- **Tatsat, H. & Shater, A. (2026). "Beyond the Black Box: Interpretability of Agentic AI Tool Use." arXiv:2605.06890.** https://arxiv.org/abs/2605.06890
  - SAE-feature linear probes (Tool-Need, Tool-Risk) read before each action on **GPT-OSS-20B** and Gemma-3-27B. Overlaps with our model set.
- **Jiao & Anderson (2026), TACIT, arXiv:2609.33039** (above).
  - Linear readouts of trajectory safety. Two nearly orthogonal risk directions (harmful content vs unsafe tool use), which is evidence that agent risk *decomposes* in representation space. Latency 40 ms vs 215 ms for Qwen3Guard.
- **Yeats, E., Kennedy, B., Truong, L., Buckheit, J., Lee, J., Friedbaum, J., Emanuello, J., Kvinge, H. (2026). "The Calls are Coming from Inside the Model: Investigating Probe-based Detection of Tool-Calling Errors in LLMs." arXiv:2608.27750.** https://arxiv.org/abs/2608.27750
- **Zhou, K., Venhoff, C., Michala, J., Wang, X. E., Saunders, W. (2026). "Probing the Misaligned Thinking Process of Language Models." arXiv:2606.24251.** https://arxiv.org/abs/2606.24251
  - 18 "misalignment indicator" probes combined by **OR-fusion**. Benign over-triggering controls share scenario, system prompt and first user turn (a matched-control design). 0.935 OOD AUROC. A probe→LLM cascade needs only 6.1% of LLM calls on benign traffic.
  - **Closest "compositional probes" precedent.** Ours differs in composing *calibrated posteriors* with AND/OR logic over epistemic predicates; theirs is an OR over thresholded behavior indicators.
- **Wang, H., Zhao, W., Zhang, Y., Poskitt, C. M., Sun, J. (2026-09-30). "Representation Transitions Reveal Emerging Safety Risks in Multi-Turn LLM Agents" (DART). arXiv:2610.00400.** https://arxiv.org/abs/2610.00400 — representation-shift defense for agents. Posted yesterday; reviewers may know it.

**Logical composition of per-category guard probabilities:**
- **Kang, M. & Li, B. (2024). "R²-Guard: Robust Reasoning Enabled LLM Guardrail via Knowledge-Enhanced Logical Reasoning." arXiv:2407.05557** (OpenReview; listed as ICLR 2025, venue to double-check).
  - Category-specific unsafety probabilities are composed through first-order logic rules in a PGM (MLN / probabilistic circuit).
  - **Precedent for "compose predicate posteriors."** It works on text-classifier outputs, not activations, and has no epistemic predicates.
- **Chen, Z., et al. (ICML 2025). "ShieldAgent: Shielding Agents via Verifiable Safety Policy Reasoning."** https://icml.cc/virtual/2025/poster/45989
  - Action-based probabilistic rule circuits (MLN potentials) over predicates extracted from policies, used to guard agent trajectories. (Venue and approach checked; I did not check the full author list, so cite from the proceedings.)

**Conformal / distribution-free guarantees for agent guardrails:**
- **Ray, S. (2026). "What Can Be Enforced? A Theory of Certified Runtime Safety for Tool-Using Agents." arXiv:2607.22868.** https://arxiv.org/abs/2607.22868
  - Theorem 4: conformal risk control on per-step miss risk at δ/H gives E[unsafe episode] <= δ.
  - **Difference:** they bound *misses on violating episodes*; we bound *false blocks on benign episodes*. No activation probes. They also show that closed-loop blocking changes future proposals, a caveat our guarantee must address.
- **Rahman, M. A., et al. (2026). "Beyond Aggregate Risk: Role-Stratified Conformal Risk Control for LLM Tool Calls." arXiv:2607.24343.** https://arxiv.org/abs/2607.24343 — per-argument-role conformal risk budgets for tool calls (AgentDojo, InjecAgent).
- **Ren, A. Z., et al. (CoRL 2023). "Robots That Ask For Help: Uncertainty Alignment for Large Language Model Planners" (KnowNo). arXiv:2307.01928.** https://arxiv.org/abs/2307.01928
  - Conformal prediction decides when an LLM planner should **ask for help** instead of acting. **This is the canonical "verify-before-act with conformal guarantee" precedent; must cite.**
- Background: Angelopoulos et al., "Conformal Risk Control" (ICLR 2024); Fisch et al., "Conformal Prediction Sets with Limited False Positives" (ICML 2022, PMLR v162).

**"Unverified" / acting-without-checking as a failure mode (behavioral, not monitor-based):**
- **Zhang, Z., Cui, S., Lu, Y., Zhou, J., Yang, J., Wang, H., Huang, M. (2024). "Agent-SafetyBench." arXiv:2412.14470.** Its 10 failure modes (Table 4) include, verbatim:
  - "mistakenly calls tools when the necessary information is incomplete"
  - "incorrectly calls tools before obtaining complete information"
  - "puts excessive trust in tool results without validation"
  - **This is a direct precedent for the Unverified predicate as a concept.**
- **Ruan, Y., et al. (ICLR 2024). "Identifying the Risks of LM Agents with an LM-Emulated Sandbox" (ToolEmu). arXiv:2309.15817.** "Unwarranted assumptions" under underspecified instructions.
- **Yang, T., Mi, Z., Huang, Y., Zhang, G., Chen, J., Yang, Y., Yi, J. (2026). "AgentBoundary: Counterfactual Evaluation of Safety in Tool-Using LLM Agents." arXiv:2609.33658.** https://arxiv.org/abs/2609.33658
  - Four-way counterfactuals that independently vary *apparent risk* and *action permissibility* (authorized-but-risky-looking vs routine-but-unauthorized), with 2,787 task families. **Behavioral benchmark that is very close to our authorized/unauthorized twins.** No probes or monitors.
- **Hu, Y. (2026). "Silence Is Endorsement: Verification-Status Laundering in LLM Agent Pipelines." arXiv:2609.20211.** Monitors approve unverified authorization claims (5%→60% on Llama-3.1-8B) once verification context is stripped. Supports "verification status must be tracked."
- **Bonagiri, V. K., Kumaraguru, P., Nguyen, K., Plaut, B. (2025). "Check Yourself Before You Wreck Yourself: Selectively Quitting Improves LLM Agent Safety." arXiv:2510.16492** (NeurIPS 2025 workshops). Prompted abstention baseline.
- **Althoubi, A. (2026). "Look Before You Leap: Pre-Action Verification for LLM Agents." arXiv:2609.11957**; **Mansoor, I. K., Phadke, A., Rana, P. (2026). "Verified Tool Calls Improve LLM Agent Reliability Under Non-Atomic Failures." arXiv:2608.02645.** Both are deterministic verify-before-act wrappers (reliability, not safety probes).

### What we can safely claim
- "An epistemic decomposition of agent violations into Critical ∧ (Unauthorized|informed ∨ Unverified), motivated by the observability bound. Each predicate is a calibrated linear probe on the agent's own residual stream, trained from counterfactually matched pairs, so the uninformed stratum needs no violation labels."
- "A probe-composed verify-before-act gate with an episode-level split-conformal bound on the *benign-episode false-block rate*."
- Do not claim "first probe-based gate for agents" (Dong et al. 2026; Ruan et al. 2026), "first compositional guardrail" (R²-Guard; ShieldAgent), or "first conformal agent guardrail" (Ray 2026; Rahman et al. 2026; KnowNo 2023). The defensible novelty is the *epistemic* predicate set, training from pairs without labels, and the *false-block* (utility-side) guarantee.
- State the exchangeability assumption, and Ray's closed-loop caveat: blocking changes the agent's subsequent behavior, so the calibration set must come from the gated policy, or the bound should be restricted to the first block.

---

## Claim 3: Seed-fingerprint confound (seed*1000+t reused across scenarios; fingerprint decodable from text at AUROC up to 0.99)

**Verdict: partially novel. The mechanism is known; its documentation as a confound in counterfactual safety / probe benchmarks appears novel.** I found no paper or blog reporting seed-index reuse as a spurious, decodable feature in monitor or probe evaluations.

### Mechanism precedents (must cite)
- **vLLM PR #50884, "[Core] Mix per-prompt seeds into seeded SamplingParams in the offline API" (tolleybot, opened 2026-08-03, still open as of 2026-10-01).** https://github.com/vllm-project/vllm/pull/50884
  - Quote: "Every request draws an identical Exp(1) noise vector in random_sample, so sampled tokens are correlated across the whole batch."
  - Fix: seed ← seed + sha256(prompt). **This is exactly our mechanism, stated for vLLM's Gumbel/exponential sampler.** The PR is about bias in marginal token distributions, not evaluation confounds.
- **Mächtle, F., Sander, J., Berndt, S., Weimar, B., Loose, N., Eisenbarth, T. (2026). "Steganography Without Modification: Hidden Communication via LLM Seeds." arXiv:2606.09135** (ARES 2026). The PRNG seed is recoverable from generated text alone: perfect with a known prompt, 600-800 tokens without one. **Shows a seed is decodable from text.**
- **Kuditipudi, R., Thickstun, J., Hashimoto, T., Liang, P. (2023/TMLR 2024). "Robust Distortion-free Watermarks for Language Models." arXiv:2307.15593.** A fixed key sequence of sampling randomness leaves a statistically detectable signature: the same mechanism used on purpose.
- **Benz, N. C., Tsirtsis, S., Straitouri, E., et al. (2025, rev. 2026). "Evaluation of Large Language Models via Coupled Token Generation." arXiv:2502.01754.** Shared sampling randomness across models; shows coupled vs independent sampling can change model rankings, i.e. sampling randomness can confound evaluation conclusions.
- Related evaluation-noise work (not the same claim): Larsen, E. (2025). "The Instability of Safety: How Random Seeds and Temperature Expose Inconsistent LLM Refusal Behavior." arXiv:2512.12066.
- Probe-confound methodology: Hewitt & Liang (2019) control tasks / selectivity; Belinkov (2022) "Probing Classifiers: Promises, Shortcomings, and Advances," *Computational Linguistics* 48(1), arXiv:2102.12452; Boxo, G., Neelappa, A., Raval, S. (2025). "Linear probes rely on textual evidence." arXiv:2509.21344, where probes lean on textual leakage.

### What we can safely claim
- "To our knowledge, the first report that reusing per-request sampling-seed indices across scenarios plants a decodable fingerprint (AUROC up to 0.99) that confounds counterfactual monitor/probe benchmarks when seeds are unbalanced across conditions."
- Credit the mechanism to the shared-noise literature above. Recommend fixes: balance seeds across arms, or hash (seed, prompt) as in vLLM PR #50884, and run a seed-only placebo probe.

---

## Claim 4: Matched counterfactual pairs remove confounding for safety probes; OOD transfer ≈ a + b/sqrt(K)

**Verdict, identification: known in principle; partially novel only in its specific application.** A paired / matched design that holds everything fixed except the treatment identifies the effect: this is standard causal inference and standard in NLP causal probing. Several 2026 safety-probe papers already use matched pairs or matched controls.

**Verdict, a + b/sqrt(K): the functional form is theory-standard. An empirical fit for safety-probe OOD transfer across task templates appears novel.** Present it as an empirical regularity consistent with learning-to-learn bounds, not as a new law. With few K values it will be challenged, so report confidence intervals and compare against alternative forms such as log K.

### Prior work
- Counterfactual data / invariance:
  - **Kaushik, D., Hovy, E., Lipton, Z. C. (2020). "Learning the Difference that Makes a Difference with Counterfactually-Augmented Data." ICLR 2020, arXiv:1909.12434.**
  - **Veitch, V., D'Amour, A., Yadlowsky, S., Eisenstein, J. (2021). "Counterfactual Invariance to Spurious Correlations in Text Classification." NeurIPS 2021.** https://proceedings.neurips.cc/paper/2021/hash/8710ef761bbb29a6f9d12e4ef8e4379c-Abstract.html
  - **Kumar, A., Tan, C., Sharma, A. (2022). "Probing Classifiers are Unreliable for Concept Removal and Detection." NeurIPS 2022, arXiv:2207.04153.** Probes pick up spurious, non-concept features: the problem matched pairs fix.
- Matched pairs in 2026 safety probing:
  - TACIT (Jiao & Anderson 2026): byte-identical pairs plus a placebo-edit control.
  - Zhou et al. 2026 (2606.24251): same-scenario benign controls.
  - Guan et al. 2025 (Monitoring Monitorability): intervention arms.
  - AgentBoundary (2026): four-way counterfactual families.
  - Contrast-pair probes: MacDiarmid et al. (Anthropic, 2024) "Simple probes can catch sleeper agents," https://www.anthropic.com/research/probes-catch-sleeper-agents ; Goldowsky-Dill et al. (ICML 2025).
- OOD transfer vs number of tasks / domains:
  - **Maurer, A., Pontil, M., Romera-Paredes, B. (2016). "The Benefit of Multitask Representation Learning." JMLR 17(81).** https://jmlr.org/papers/v17/15-242.html — learning-to-learn bounds with a 1/sqrt(#tasks) term.
  - **Blanchard, G., Lee, G., Scott, C. (2011). "Generalizing from Several Related Classification Tasks to a New Unlabeled Sample." NeurIPS 2011**, and **Blanchard, G., Deshmukh, A. A., Dogan, U., Lee, G., Scott, C. (2021). "Domain Generalization by Marginal Transfer Learning." JMLR 22.** https://jmlr.org/papers/v22/17-679.html
  - Empirical safety-probe generalization:
    - Martin, S. & Roger, F. (2026). "How Useful Is Cross-Domain Generalization for Training LLM Monitors?" arXiv:2605.12265 (LLM monitors; no K-scaling law).
    - Yoo, D. & Skapars, A. (2026). "Probe Generalization as Subspace Selection for OOD Deception Detection." arXiv:2609.02893.
    - Kramár, J., Engels, J., Wang, Z., Chughtai, B., Shah, R., Nanda, N., Conmy, A. (2026). "Building Production-Ready Probes For Gemini." arXiv:2601.11516 (probes fail under long-context shift).

### What we can safely claim
- "Training on counterfactually matched pairs identifies the predicate direction up to the matched factor, removing the confounding that unmatched safety-probe datasets suffer (cf. Kumar et al. 2022; Veitch et al. 2021). We show this empirically on agent violations."
- "OOD probe transfer improves with the number of training task templates K, and is well fit by a + b/sqrt(K), the rate learning-to-learn theory predicts (Maurer et al. 2016; Blanchard et al. 2011/2021)." Do not call it a scaling law.

---

## Claim 5: Cheapness (white-box self-monitoring reuses activations already computed)

**Verdict: known. The argument is established and well quantified.** Use it as motivation with citations, not as a contribution. The only new element available is cost measured *in an agentic tool-use gating setting with composed predicates*. Even that is partly covered: TACIT reports agent-guard latency, and Zhou et al. report cascade LLM-call savings.

### Prior work with numbers
- **Cunningham, H., Peng, A., Wei, J., Ong, E., Roger, F., Petrini, L., Wagner, M., Mikulik, V., Sharma, M. (Anthropic, 2025). "Cost-Effective Constitutional Classifiers via Representation Re-use."** https://alignment.anthropic.com/2025/cheap-monitors/
  - Linear probes add about 0.1% overhead and match a dedicated classifier 2% of the policy model's size. Single-layer fine-tuning adds about 4.25%. Using Claude 3.5 Haiku to filter Sonnet costs about 25%. Jailbreak / prompt classifiers only.
- **Cunningham, H., Sharma, M., et al. (2026). "Constitutional Classifiers++: Efficient Production-Grade Defenses against Universal Jailbreaks." arXiv:2601.04603.** Probe ensembles plus a cascade give a 40× compute reduction vs the baseline exchange classifier at a 0.05% refusal rate.
- **Sharma, M., et al. (2025). "Constitutional Classifiers: Defending against Universal Jailbreaks across Thousands of Hours of Red Teaming." arXiv:2501.18837.** 23.7% inference overhead for the classifier stack: the expensive baseline.
- **McKenzie, A., Pawar, U., Blandfort, P., Bankes, W., Krueger, D., Lubana, E. S., Krasheninnikov, D. (NeurIPS 2025). "Detecting High-Stakes Interactions with Activation Probes." arXiv:2506.10805.** Probes perform comparably to medium LLM monitors with "computational savings of six orders-of-magnitude... enabled by reusing activations"; hierarchical probe→LLM monitoring.
- **Kramár et al. (2026), arXiv:2601.11516.** Probes deployed in production Gemini; probe+classifier pairing is optimal at low cost.
- **Hua, T. T., Baskerville, J., Lemoine, H., Hopman, M., Bhatt, A., Tracy, T. (NeurIPS 2025). "Combining Cost-Constrained Runtime Monitors for AI Safety." arXiv:2507.15886.** Optimal combination of monitors under a cost budget: the framework to use for our cost comparison.
- **Goldowsky-Dill, N., Chughtai, B., Heimersheim, S., Hobbhahn, M. (ICML 2025). "Detecting Strategic Deception with Linear Probes." PMLR v267, arXiv:2502.03407.** AUROC 0.96-0.999; catches 95-99% of deceptive responses at 1% FPR on control chat data.
- **Jiao & Anderson (2026), TACIT.** 40 ms vs 53 ms (AgentDoG) vs 215 ms (Qwen3Guard); about 5k trainable parameters.
- **Zhou et al. (2026), arXiv:2606.24251.** Cascade needs 6.1% of LLM-judge calls on benign traffic.
- **Inan, H., et al. (2023). "Llama Guard: LLM-based Input-Output Safeguard for Human-AI Conversations." arXiv:2312.06674.** Standard separate-model guard baseline.
- **Lindner, D., Griffin, C., Korbak, T., Zimmermann, R. S., Irving, G., Farquhar, S., Cooney, A. (2025). "Practical challenges of control monitoring in frontier AI deployments." arXiv:2512.22154.** Synchronous vs asynchronous monitoring and latency trade-offs; relevant to "gate before act."

### What we can safely claim
- "Following Cunningham et al. (2025) and McKenzie et al. (2025), the gate reuses activations computed during generation. We measure its overhead in an agentic gating loop (X ms/step, Y% FLOPs) against an LLM-judge and a Llama-Guard-class guard." Present it as a measurement, not a novel insight.

---

## Works that could scoop us or that reviewers will ask about (priority order)

1. **Hu & Wang 2026 (arXiv:2607.11751).** Same TV-based "observability boundary" theorem for monitors. Must cite next to our bound.
2. **Jiao & Anderson 2026, TACIT (arXiv:2609.33039).** Agent-trajectory probes on matched pairs where guards are at chance; the informed-stratum counterpart of our setup. Expect a request to compare.
3. **Ruan et al. 2026, Doomed from the Start (arXiv:2607.06503).** Probe cascade on agent activations with an episode-level distribution-free guarantee, very close to our conformal machinery.
4. **Dong et al. 2026 (arXiv:2608.02657).** Probe-gated defense on the agent's own hidden states.
5. **Guan et al. 2025, Monitoring Monitorability (arXiv:2512.18311).** Intervention/matched-arm monitorability evals.
6. **AgentBoundary, Yang et al. 2026 (arXiv:2609.33658).** Counterfactual authorized/unauthorized task families (behavioral).
7. **Zhou et al. 2026 (arXiv:2606.24251).** Multi-indicator (OR-fused) misalignment probes plus a cascade.
8. **Ray 2026 (arXiv:2607.22868).** Episode-level conformal certificates for runtime agent guardrails.
9. **R²-Guard (arXiv:2407.05557) and ShieldAgent (ICML 2025).** Logical composition of predicate probabilities.
10. **Cunningham et al. 2025 cheap monitors; McKenzie et al. 2025.** The cheapness argument.
11. **Agent-SafetyBench (arXiv:2412.14470) and ToolEmu (arXiv:2309.15817).** "Acting before obtaining complete information" / "unwarranted assumptions" as named failure modes.
12. **Boxo et al. 2025 (arXiv:2509.21344).** Reviewers will ask whether our probes rely on textual leakage; our matched-pair design is the answer.
13. **Bailey et al., "Obfuscated Activations Bypass LLM Latent-Space Defenses" (arXiv:2412.09565; ICLR 2026)** and **RL-Obfuscation (arXiv:2506.14261).** Robustness of probe monitors under optimization pressure; expect the question "can the agent evade the gate?"
14. **vLLM PR #50884; Mächtle et al. 2026 (arXiv:2606.09135).** Shared-seed noise and seed recoverability (claim 3).

## Suggested baselines
- **Black-box LLM judge / action-only monitor:** e.g., a strong judge on the action alone and on action+CoT. Follow Arike et al. 2026; include their extract-and-evaluate variant if feasible.
- **CoT monitor** (Baker et al. 2025 style) on reasoning models (gpt-oss-20b, Qwen3.8 thinking).
- **Off-the-shelf guards:** Llama Guard 3 (8B), Qwen3Guard-4B, AgentDoG-4B. These are the guards TACIT benchmarks.
- **Monolithic linear probe** on "violation" labels (no decomposition), plus TACIT-style trajectory readout, plus Goldowsky-Dill-style deception probe transfer. This isolates the gain from composition and matched-pair training.
- **OR-fusion of indicator probes** (Zhou et al. 2026) vs our calibrated AND/OR posterior composition.
- **Prompted verify/abstain baselines:** "quit when uncertain" (Bonagiri et al. 2025) and a KnowNo-style conformal ask-for-help (Ren et al. 2023) on the agent's own token probabilities.
- **Probe→LLM cascade** (McKenzie et al. 2025; Hua et al. 2025) to present cost-performance frontiers.
- **Seed-only placebo probe** (seed index as the only feature) and Hewitt-Liang control tasks, to show the seed confound is removed.

## Wording guardrails (summary)
- Do say "an instance of the classical indistinguishability bound applied to the agent's own information state", "extends to white-box self-monitors", and "to our knowledge first to quantify the uninformed share and the resulting ceiling."
- Don't say "first impossibility theorem for monitors", "first probe-based agent gate", "first conformal guardrail", or "novel insight that probes are cheap."
- For the seed confound, say "to our knowledge first documented as a benchmark confound; mechanism known (shared sampling noise)."
- For 1/sqrt(K), say "consistent with learning-to-learn rates," not "scaling law."

## Caveats on this search
- 2026 arXiv IDs (e.g., 2609.33039, 2610.00400) were verified on arXiv abs pages today. Several are under a week old and may change.
- For ShieldAgent I checked the venue (ICML 2025 poster page) but not the full author list. For R²-Guard, the ICLR 2025 venue comes from an OpenReview / institutional listing that I could not open (bot check). Confirm both before the camera-ready.
- Not covered: Google Scholar full-text (blocked), and non-arXiv industry reports not indexed by search (e.g., internal UK AISI white-box control notes).
