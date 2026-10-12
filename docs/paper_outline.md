# Paper outline (draft, 2026-10-02): living document; [PENDING] = awaiting a confirmatory result

## Working title
**What No Monitor Can See: An Observability Bound and a Catch–Friction Identity for Monitoring LLM Agents**
(alt: "Monitorability Is an Information Problem")

## One-paragraph abstract (draft)
Runtime monitors for LLM agents, whether LLM judges, guard models or white-box probes of the agent's own activations,
are evaluated by how many unsafe actions they catch. We show this number is ill-posed without asking *what the agent
had seen*.
- **The bound.** Using matched environment pairs that differ only in one decision-relevant fact, we prove that before
  the agent observes that fact, its entire context is identically distributed in the safe and unsafe worlds. Any
  context-measurable monitor, including probes of the agent's own residual stream, is then at chance.
- **The identity.** A sharper consequence: on such "uninformed" actions, a monitor's catch rate equals its false-flag
  rate on the authorized twins, at every threshold. Apparent detection there is pure verification friction.
- **Evidence.**
  - [Confirmatory, preregistered] The bound holds on fresh data for Qwen3.8, Gemma-4 and gpt-oss: AUROC 0.48–0.51
    uninformed vs 0.77–0.95 informed.
  - The identity holds for probes, LLM judges and a guard model. A judge given out-of-context environment state breaks
    it, as predicted.
  - The uninformed share of violations, 1% to 56% across models, explains why some agents look "monitorable" and
    others do not.
- **Constructive consequence.** The only way to stop what no monitor can see is to stop acting before verifying. An
  epistemic compositional gate (three calibrated linear probes; about 25 µs per action) implements this with an
  episode-level conformal false-block guarantee.
- **External data.** On published τ²-bench trajectories of four frontier agents, 92% of policy-violating writes were
  informed, the monitorable regime: [PENDING X1/X2].
- **Artifact.** We also document a seed-fingerprint confound (AUROC up to 0.99) that silently leaks labels in
  counterfactual agent benchmarks.

## Contributions (claims, each with its evidence)
1. **Observability bound for self-monitors (Thm 3, coupling).**
   - Confirmatory H1 (core24, 3 models): PASS.
   - Exploratory: 4 model families on v2fresh.
   - Positioned as an instance of Hu & Wang's TV principle; new in covering the agent's own information state and
     white-box monitors.
2. **Catch–friction identity (Cor. 3.2).**
   - v2fresh: 18/18 threshold points for probes; LLM judges A and C, and the guard, at chance on uninformed.
   - Scope control: the state-grounded judge breaks it (AUROC 1.0).
   - Training-free exchangeability test p = 0.91 (positive control p = 0.005).
   - Confirmatory H7: [PENDING].
3. **Monitorability ceiling explains cross-model differences.**
   - π_u: Qwen 0.01, Gemma-4 0.37, gpt-oss 0.56 (v2fresh).
   - [PENDING core24 π_u per model.]
4. **Epistemic compositional gate (Thm 4).**
   - Calibrated: H5 PASS (Gemma; others [PENDING]).
   - Versus monolithic probe: H2 FAILS for Gemma-4 (informed branch weaker); [PENDING Qwen, gpt-oss].
   - Honest framing: the decomposition gives an explicit verify-before-act policy and a guarantee; a strong
     monolithic probe is itself an implicit verification gate (by the identity).
5. **Probes vs LLM judges / guard, with cost.**
   - Qwen v2fresh: probe 0.918 vs best judge 0.806 (hard negatives 0.882 vs 0.558), p ≤ 0.005.
   - Guard: 0.01 at 1% FPR.
   - Cost: gate 25 µs, guard 4 ms, judge 75 ms per action.
   - core24 S1/S2: [PENDING].
6. **Reader beats self-monitor** (gpt-oss: +0.10 on hard negatives, p = 0.001). Full design [PENDING].
7. **Seed-fingerprint confound.** Seed index decodable at AUROC 0.78–0.99; leaks world labels under unbalanced seeds;
   fix and check.
8. **External validity (τ²-bench, frontier agents)** [PENDING X1–X3].
9. **Matched beats confounded (Thm 1)** [PENDING H6]; **diversity scaling (Thm 2)** [PENDING H4], presented as
   consistent with learning-to-learn theory, not a new law.

## Figures / tables
- F1: Schematic of a matched pair, the reveal time, the informed/uninformed strata, and the three gate predicates.
- F2: The bound. World-decoding AUROC, uninformed vs informed, per model, probes and text classifier
  (confirmatory core24).
- F3: The identity. TPR vs twin flag rate across thresholds and monitors (probe, judges, guard, state judge), per
  stratum.
- F4: π_u per model vs apparent monitorability (TPR on hard negatives).
- T1: Confirmatory scorecard (H1–H7, Holm, GO/NO-GO).
- T2: Gate vs baselines on identical events (TPR@1%, hard, informed/uninformed, cost).
- T3: τ²-bench frontier agents: violation counts, informed share, X1/X2.
- F5: Seed fingerprint (decodability by seed index; leakage under unbalanced design).

## Honest limitations (to state up front)
- Synthetic environments for the bound's matched pairs; τ²-bench has no matched pairs, so the bound is not tested
  there.
- The gate does not beat a strong monolithic probe on raw TPR (H2 Gemma).
- Small informed-violation counts for gpt-oss.
- The bound's math is elementary; the contribution is scope, the identity and the evidence.
- No adaptive or obfuscating agents (cf. Bailey et al. 2024).
