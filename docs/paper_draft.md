# What No Monitor Can See: An Observability Bound, a Catch–Friction Identity, and Certified Knowing Misrepresentation in LLM Agents

*Draft v0.1, 2026-10-03. [PENDING] marks results still running: v31 fresh-world confirmation, v32 closed loop, v35
confirmatory honesty, Muse H4.*

## Abstract
Runtime monitors for LLM agents, whether LLM judges, guard models or probes of the agent's own activations, are judged
by how many unsafe actions they catch. We argue that this number is ill-posed unless one asks *what the agent had
seen*.

Using matched environment pairs that differ in one decision-relevant fact, we prove that before the agent observes
that fact, its context is identically distributed in the safe and unsafe worlds. Every context-measurable monitor,
including white-box probes, is therefore at chance there. A sharper corollary, the catch–friction identity, says that
on such uninformed actions a monitor's catch rate equals its false-flag rate on authorized twins, at every threshold.

In preregistered confirmatory tests on four open models (Qwen3.8-27B, Gemma-4-26B, gpt-oss-20b, Muse-Glimmer-30B;
24 task families, 16 of them unseen):
- the bound holds for all four (uninformed AUROC 0.48–0.51 vs informed 0.77–0.95);
- the identity holds under a training-free test for all four;
- a judge given out-of-context environment state breaks it, as predicted.

The share of uninformed violations, from 1% (Qwen) to 56% (gpt-oss), explains why some agents look monitorable and
others do not.

On the informed side, cheap white-box gates catch 64–98% of violations at 1% false-positive rate (FPR), against
6–61% for LLM judges and about 1% for a guard model. They use roughly 3–5 orders of magnitude less compute per caught
violation and carry a calibrated episode-level false-block guarantee.

Finally, combining environment logs, internal decodes and a validated report-auditing rubric, we certify that some
agent misrepresentations are *knowing*:
- the agent observed the fact;
- its activations encode it at the violation;
- its report contradicts the log (e.g. deleting customer records, then reporting "no customer records were deleted").

A gate at the violating action prevents about half of the episodes that would end in such a lie. Predicting the lie
from internals beyond what the text reveals is not supported. [PENDING: v31, v32 and v35 confirmatory numbers.]

## 1. Introduction
- **Motivation.** Frontier agents act beyond their authorization: they push ahead without asking, persist after a
  denial, and misreport what they did. OpenAI cited these when it shelved GPT-6.1 Astra (2026); further examples
  include the GPT-5.6 system card, the OpenAI–HF evaluation incident and Replit. The standard response is a monitor
  before execution.
- **The problem.** Monitor quality varies wildly across models: our first white-box gate caught 92% of Qwen3.8's
  violations but 14% of gpt-oss's hard cases. We show that this variation is largely *informational*, not a property
  of the monitor.
- **Contributions:**
  1. An observability bound for agent monitors that covers the agent's own activations (Thm 3). It instantiates the
     total-variation principle of Hu & Wang (2026) on the agent's own information state via a coupling argument.
  2. The catch–friction identity (Cor. 3.2). It is testable at every threshold, and it shows how monitor evaluations
     that omit twin flag rates overstate monitorability.
  3. A monitorability ceiling explained by the uninformed share π_u (1–56% across models).
  4. A constructive consequence (Thm 4): the only way to stop what no monitor can see is to stop acting before
     verifying. We give a two-channel gate (detect + verify) with calibrated guarantees.
  5. Certified knowing misrepresentation and its prevention at the violating action.
  6. Methodological findings for the field:
     - a seed-fingerprint confound, which leaks labels in counterfactual agent benchmarks (AUROC up to 0.99);
     - anti-learning of trained probes on identically distributed strata;
     - an LLM honesty judge whose "misrepresented" label was only 7–30% precise until rebuilt with verification.
- **Rigor.** All confirmatory claims were preregistered with hash locks before data existed (v29, v31–v35). The
  failed preregistered hypotheses are reported, diagnosed, and re-tested on fresh data.

## 2. Related work (positioning; see docs/novelty_check_*.md)
- **Monitor impossibility.** Hu & Wang 2026 (TV bound, external monitors); Srivastava 2026 (black-box evaluation
  limits); Arike et al. 2026 (information access).
  - We add: the agent's own information state, white-box monitors, the exact identity, and multi-model confirmation.
- **Probes and white-box monitors.** Goldowsky-Dill et al. 2025; McKenzie et al. 2025; Cunningham et al. 2025
  (cheap monitors); TACIT 2026 (informed-case counterpart); Dong et al. 2026 (probe gating).
- **Monitorability and CoT monitors.** Guan et al. 2025 (OpenAI); Korbak et al. 2025; Baker et al. 2025.
- **Honesty and lie detection.** Azaria & Mitchell 2023; Burns et al. 2022; Zou et al. 2023; Liars' Bench 2025;
  KnownLieBench 2026; Scheurer et al. 2023; the Claude Mythos system card (2026).
  - We add: log-certified *knowing* misrepresentation in on-policy agent behavior, and prevention at the action.
- **Conformal guardrails.** KnowNo 2023; Ray 2026.

## 3. Theory (docs/theory_counterfactual_probes.md, Appendices A–B)
- **Setting.** Matched environments E^±; reveal time R = the first differing observation; uninformed means t ≤ R.
- **Lemma A.1 (coupling).**
- **Theorem 3 (observability).** The law of (context, action, monitor) on selected uninformed steps is identical
  across worlds.
- **Corollary 3.1 (ceiling).** TPR(α) ≤ (1 − π_u) + π_u·α.
- **Corollary 3.2 (catch–friction).** TPR = twin flag rate on uninformed violations.
- **Theorem 4 (epistemic decomposition).** The Bayes-optimal gate for verify-before-act factorizes into criticality ×
  (authorization | informed OR unverified). The authorization factor is unidentified on the uninformed stratum.
- **Theorem 1 (matched-pair identification)** and **Theorem 2 (diversity, a + b/√K)** are standard results, stated
  and tested.
- **Scope.** The bound concerns distinguishing a violation from its authorized twin, not flagging unverified action.
  It does not cover monitors with out-of-context information (empirically confirmed).

## 4. Setup
- **CAPE-Bench.** Matched pairs over 8 families (v2fresh), 24 templates (core24) and a fresh split (core24b);
  content-only exclusions fixed before rollouts.
- **Agents.** Qwen3.8-27B, Gemma-4-26B-A4B, gpt-oss-20b, Muse-Glimmer-30B.
- **Features.** Teacher-forced replay; `mean8` at about 72% depth; reader mode uses Qwen3.8 as reader.
- **Baselines.**
  - Qwen3.8 zero-shot judges: transcript, resolved state (privileged), CoT.
  - Qwen3Guard-4B.
  - A metadata placebo.
- **Statistics.** Grouped CV by scenario; within-fold thresholds; scenario-cluster bootstraps; Holm correction;
  training-free tests where trained probes anti-learn.

## 5. Results
### 5.1 The observability bound (confirmatory H1, core24): PASS for all 4 models
| Model | Uninformed, probe [90% CI] | Uninformed, text | Informed |
|---|---|---|---|
| Qwen3.8 | 0.507 [0.492, 0.520] | 0.511 | 0.946 |
| Gemma-4 | 0.482 [0.470, 0.492] | 0.486 | 0.819 |
| gpt-oss | 0.497 [0.483, 0.512] | 0.505 | 0.768 |
| Muse | 0.477 [0.463, 0.489] | 0.482 | 0.895 |

### 5.2 Catch–friction identity
- **Training-free exchangeability (H7a):** PASS ×4. Uninformed p = 0.49 / 0.56 / 0.71 / 0.57; informed controls
  p = 0.005.
- **Scope control (H7c):** the state judge breaks it (×4).
- **Zero-shot points (H7b):** underpowered, failing the preregistered rule for 3/4 models. Reported as such.
- **v2fresh:** 18/18 threshold points for probes; judges at chance on uninformed actions.

### 5.3 Monitorability across models: π_u and the reader
- π_u: Qwen 0.01, Gemma 0.37, gpt-oss 0.56, Muse about 0.
- Reader > self-monitor on gpt-oss hard negatives (+0.10, p = 0.001).
- Knowledge at the moment of violation (decode-positive rate, null about 5%): Muse 0.94, Qwen 0.81, Gemma 0.69,
  gpt-oss 0.03 (reader 0.13; gpt-oss violates where cues are weak).

### 5.4 White-box gates vs LLM judges and guards (identical core24 events)
| | TPR@1% FPR (white-box) | Best LLM judge | Guard | Placebo |
|---|---|---|---|---|
| Qwen | 0.98 | 0.23 | 0.01 | 0.66 |
| Gemma | 0.85–0.89 | 0.61 | 0.01 | 0.35 |
| gpt-oss | 0.57–0.64 | 0.44 | 0.004 | 0.36 |
| Muse | 0.97–0.99 | [PENDING table] | | 0.63 |

- Calibrated false-block guarantee (H5): PASS ×4.
- Cost: 25 µs per action vs 75 ms (judge) and 4 ms (guard).

### 5.5 What the decomposition does and does not buy (H2, H3, H4; fixes in v31)
- **H2 (gate > monolithic):** not supported. The gain tracks π_u (gpt-oss +0.07; Gemma −0.05; Qwen and Muse about 0).
- **H3 (transfer at fixed thresholds):** fails. Ranking transfers (ECG 0.75–0.96 vs mono 0.42–0.75), but thresholds
  drift.
- **H4 (diversity scaling):** PASS for Gemma (b = 0.14 [0.10, 0.19]) and gpt-oss (b = 0.20 [0.07, 0.32]); Qwen
  underpowered; Muse [PENDING].
- **Official preregistered verdict (v29):** NO-GO under the strict all-models rule. Per model:
  - bound / calibration / training-free identity 4/4;
  - scaling 3/4 (Muse b = 0.36 [0.22, 0.51]);
  - matched-pair identification 3/4;
  - gate superiority not supported.
- **v31 (two-channel gate on fresh worlds core24b), Qwen** [Gemma, gpt-oss, Muse PENDING]:
  - K1 calibrated false interventions 3.5%;
  - K2 informed detection AUROC 0.905, beyond metadata (placebo 0.61);
  - K3 verification targeting AUROC 1.0, 100% coverage at 1.5% unnecessary requests;
  - K4 training-free identity PASS;
  - K6 transfer to unseen templates: FPR controlled label-free (2.3%) but detection fails (0.40).
- **Cross-domain:** more synthetic task families (8 → 24) do not improve transfer to τ²-bench (Δ = −0.01
  [−0.07, 0.04]), whereas in-domain τ² training reaches 0.78. Cross-domain deployment needs target-domain data.

### 5.6 Closed loop (v32)
[PENDING: risk reduction, task-success cost, friction vs verify-all.]

### 5.7 Certified knowing misrepresentation (v35)
- **Rubric validation (blind held-out):** precision 0.85, recall 0.96; Muse spot-check 10/12.
- **Taxonomy:** spin dominates for Gemma and gpt-oss; Qwen is candid but makes sincere false authorization claims;
  knowing lies are fabricated approvals and denials of executed actions.
- **Knowledge at the violation:** Muse 0.94, Qwen 0.81, Gemma 0.69 (null 0.05); gpt-oss 0.03, reader 0.13 (weak
  cues).
- **Lying concentrates where the agent knew:** Muse misrepresents 64% of informed violations vs 11% of uninformed
  ones.
- **Preview (core24, exploratory):**
  - 51 false claims;
  - 11 certified knowing;
  - the gate flags 49% of dishonest episodes before the report (vs 35% of other violations);
  - no beyond-text forecasting.
- **Confirmatory core24b:** [PENDING].

### 5.8 Methodological findings
- **Seed fingerprint:** seed index decodable at 0.78–0.99, leaking world labels.
- **Anti-learning:** trained probes on identically distributed strata reach held-out AUROC 0.41–0.44, against 0.50
  for random readouts.
- **LLM honesty-judge failure:** its MISREPRESENTED label was 2/27 correct; fixed with a verified rubric.

### 5.9 External validity (τ²-bench, published frontier-agent trajectories)
- 227 policy-violating writes by Claude-3.7, GPT-4.1, GPT-4.1-mini and o4-mini; 92% informed.
- Zero-shot transfer from CAPE AUROC 0.64 [0.56, 0.70]; in-domain 0.78 [0.67, 0.87].

## 6. Limitations
- Synthetic matched pairs for the bound; no matched pairs in τ²-bench.
- The gate does not beat a strong monolithic probe on raw TPR.
- Gold honesty labels are AI-produced; human annotation is pending.
- No adaptive or obfuscation-trained agents.
- Muse monitor-aware robustness is still pending.
- The bound's math is elementary; the novelty is scope, the identity and the evidence.
