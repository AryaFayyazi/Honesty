# CAPE pilot summary — Qwen3.8-27B (prediction complete; causal patching in progress)

Status: Phases 0–3 complete; Phase 4 (early prediction) and Phase 5 (causal patching) are running. Sections marked
**PENDING** will be filled only from the produced CSVs and figures. No number in this file is estimated or invented.

## 0. Infrastructure checks (all passed)
| check | result |
|---|---|
| architecture introspection | 64 language blocks, d=5120, full attention at layers 3, 7, …, 63 (matches the config) |
| streaming hooks vs `output_hidden_states` | equal (atol 1e-3); our hooks are removed after use |
| patch hook | replace/add applied at the exact sites; zero-add is a no-op; downstream logits change |
| replay equivalence (vLLM rollout vs HF teacher-forced) | 6 episodes, ~30k sampled tokens: mean abs Δ logprob 0.010–0.011, p99 ≈ 0.10, corr 0.9988 |
| chat template / tokenization | initial prompt equals the template rendering; all non-generated segments round-trip exactly |
| left-padded batch vs single sequence | total variation 0.0075 |
| counterfactual pairs (CPU tests) | each pair differs in exactly one resource; labels are rule-based; no network, filesystem or subprocess access |
| counterfactual prefix reconstruction | exact for 399/400 pilot x− episodes; matched prefixes differ in a median of 10 tokens |

## 1. Benchmark and labels
CAPE-Bench core suite: 8 safety families × 3 templates. The pilot is 50 base scenarios × 2 paraphrases × {x+, x−} × 4
seeds = 800 episodes, run in the pre-registered original configuration (explicit policy, working approval channel,
no pressure).

Reading transcripts turned up labeling bugs, all fixed before any analysis:
- backup copies and permission requests were being labeled unsafe;
- SQL `IN (...)` clauses were not parsed.

Labels are now state-based for database edits. They never fire on escalation, read-only inspection or reports to the
principal. All rollouts were re-labeled by replaying their exact actions.

## 2. Behavioral findings (these gate everything else)
| | unsafe episode | critical action | escalated | task success |
|---|---|---|---|---|
| x+ (authorized) | 0.000 | 0.988 | 0.425 | 0.902 |
| x− (not authorized) | 0.062 | 0.422 | 0.885 | 0.528 |

* 25/400 x− episodes are unsafe, but only 9 are informed, meaning the causal variable was observed before the unsafe
  action. The other 16 are uninformed: the agent sent to a distribution list without checking its size and learned it
  from the send result. Uninformed violations have identical x+ and x− prefixes, so no representation can forecast
  which condition they are in.
* The 9 informed violations happen late in the episode, typically about 8 decisions after the reveal, and mostly in
  the goal-conflict (constraint) family. After an approval was denied, the agent searched for several turns and then
  worked around the constraint.
* Calibration on separate worlds (640 episodes) gave the same picture under handbook policy, an unavailable approver
  and deadline pressure (about 1 informed violation).
* A long-horizon state-tracking suite produced 0/256 unsafe episodes. In it, the safety fact is revealed early, the
  protected item comes 3–4 positions later, and some items need an N-hop membership lookup. Auditing every sensitive
  action on a protected item confirmed each one followed an explicit APPROVED decision.
* Conclusion so far: Qwen3.8-27B reliably tracks and respects safety-relevant facts in these environments. The brief's
  primary target, forecasting informed unsafe actions, has too few positives here (9 episodes) for Experiment 1 to be
  conclusive.

## 3. Regime-independent analyses
In x+, agents proceed 57% of the time and escalate 42%, and 26/50 scenarios are mixed across seeds, so the
proceed-vs-escalate decision is a well-powered target. Two analyses:
- decision forecasting from actor latents vs action, transcript, CoT and observer baselines (`decision_prediction.csv`);
- causal patching of the matched counterfactual state at the first decision after the reveal, measuring proceed,
  escalate and unsafe outcomes (`patching_effect.csv`, `patching_heatmap.pdf`).

### 3a. Decision forecasting (proceed vs escalate), `decision_prediction.csv`
Within x+ (both choices are safe; 2,064 events, 400 episodes), under scenario holdout:
- actor pre-action latents: 0.82–0.84 AUROC;
- observer Qwen3-8B: 0.82–0.84;
- TF-IDF transcript: 0.80;
- action features alone: 0.81.

Two or more decisions ahead (d≥2): best actor representation (turn_start L63) 0.79, observer 0.78, text 0.75, with
overlapping CIs.

Under family holdout every method collapses to ≈0.5–0.63, and to ≤0.52 for d≥1. The predictable part is mostly "what
kind of scenario is this", not a transferable internal decision state. There is no evidence of an actor-internal
advantage over an observer reading the same transcript.

### 3b. Early prediction of eventual harm, `early_warning.csv`, `baseline_comparison.csv`, layer scan
There are 25 unsafe episodes (135 positive pre-harm events), 16 of them from a single template.

**Scenario holdout.** Actor probes reach 0.65–0.83 AUROC, e.g. validation-selected L62 pre_action_last:
- population all: 0.71 [0.32, 0.91];
- x− only: 0.79 [0.41, 0.96].

Baselines are similar:
- TF-IDF transcript: 0.85 [0.60, 0.96];
- observer (CoT, L18): 0.82 [0.72, 0.90];
- zero-shot LLM CoT monitor: 0.58.

No paired actor-minus-baseline difference is significant (all 95% CIs include 0). For example, at d≥1 in population
all: vs text −0.12 [−0.36, 0.02]; vs observer −0.08 [−0.43, 0.07].

**Template holdout.** The selected actor probe drops to 0.24 (all) / 0.22 (x−) and TF-IDF to 0.19, i.e. below chance.
Supervised probes learned template-specific cues that invert on unseen templates.

**Family holdout.** All supervised methods are ≤0.62, and the actor probe scores 0.29–0.33. Only the untrained LLM
monitor stays at ≈0.57.

**64-layer scan (pre_action_last, population all, scenario holdout).** No layer is significant after
Benjamini–Hochberg (p_BH ≈ 0.20 everywhere); point AUROCs are 0.63–0.78 and the CIs are very wide. Layer 0 (nearly raw
embeddings) already reaches 0.64, consistent with surface/scenario information.

## 4. Answers to the brief's nine questions
1. **Do actor activations predict future harm?** Only within scenario families seen in training (AUROC ≈0.7–0.8 with
   very wide CIs). Not transferably: they fall below chance under template and family holdout.
2. **How early?** Within-family AUROC for positives ≥1 decision before harm is similar to the overall AUROC (≈0.73–0.84),
   but this does not survive holdout, so no reliable warning horizon can be claimed.
3. **Which layers?** Validation selects late layers (L61/L62); no layer is significant after BH across 64 layers.
4. **Better than action?** No significant difference.
5. **Better than CoT?** No: TF-IDF on transcript/CoT and an observer LLM's hidden states perform as well or better; no
   paired difference is significant.
6. **Does it survive scenario holdout?** Scenario holdout gives the numbers above. The stronger template and family
   holdouts fail (below chance).
7. Does patching causally alter behavior?
8. Is the effect larger than norm-matched random intervention?
9. **Is there enough evidence to proceed to JEPA?** No, for the predictive part: GO/NO-GO #1 fails on criteria 2–4
   (holdout, paraphrase/template robustness, several categories). The limiting factor is that Qwen3.8-27B produces
   very few informed unsafe trajectories in these environments (9/400), not a demonstrated absence of the phenomenon.
   (Question 7/8 answers follow from the patching run.)
