# Theory: counterfactual invariance and task diversity for white-box safety probes (draft, 2026-10-01)

## Setting
- Tasks k = 1..K are drawn i.i.d. from a task distribution 𝒯 (in CAPE: scenario templates).
- At a decision point, the agent's residual-stream representation is h ∈ ℝ^d.
- The safety variable is z ∈ {0,1}, e.g. "the critical action is unsafe in this world" or "this action is critical".
- Linear structural model (random-task linear SCM):

      h = μ_k + A·z + B_k·s + ε,    ε ~ N(0, Σ_ε),  s ∈ ℝ^m task-specific nuisance content,

  where A ∈ ℝ^d is the **task-invariant** effect of z on the representation, and (μ_k, B_k) are task-specific with
  (μ_k, B_k) i.i.d. over tasks.
- **Confounding.** Within task k, E[s | z] = ρ_k·z. An *observational* training set (e.g. "harmful action vs any safe
  action") generally has ρ_k ≠ 0: z correlates with template content. A *counterfactually matched* design (CAPE's x+/x−
  pairs differ only in z) has ρ_k = 0 by construction.
- **Probe.** The linear score is w^T h. On a new task k* ~ 𝒯, its AUROC is Φ(δ_{k*}(w)/√2), with
  δ_{k*}(w) = w^T A / sqrt(w^T Σ_{k*} w) and Σ_{k*} = B_{k*} Cov(s) B_{k*}^T + Σ_ε. The Bayes-optimal direction for
  k* is Σ_{k*}^{-1} A.

## Theorem 1 (identification: matched design removes confounding bias)
Let Σ̄ = E_k[B_k Cov(s) B_k^T] + Cov_k(μ_k) + Σ_ε be the pooled within-class covariance. The population pooled-LDA
direction (and, to first order, the logistic-regression direction under the Gaussian model) is:
- matched design (ρ_k = 0):  w_cf = Σ̄^{-1} A;
- observational design:      w_obs = Σ̄^{-1} (A + β),  with β = E_k[B_k ρ_k].

If β ∉ span(A), then for a new task k* whose nuisance is independent of the training tasks' confounding,
E[δ_{k*}(w_obs)] < E[δ_{k*}(w_cf)]: the observational probe carries an **irreducible** out-of-distribution loss that
does not vanish with more data or more tasks.

*Proof sketch.* The class-conditional means differ by A + E_k[B_k ρ_k] under confounding and by A under matching, and
LDA is the whitened difference of means. For k* independent of the training confounding, the β-component projects onto
k*'s nuisance B_{k*} s, which adds variance to w^T h without adding separation along A. Hence δ decreases by
Cauchy–Schwarz unless β ∥ A. ∎

## Theorem 2 (diversity: OOD error decays as Θ(1/√K))
With K training tasks and n samples per task, let Σ̂_K be the empirical pooled covariance. Under bounded effective rank
r of the nuisance covariance, standard covariance concentration gives ‖Σ̂_K − Σ̄‖ = O_p(√(r/K) + √(d/(nK))). For a
matched probe ŵ = Σ̂_K^{-1} Â and a new task k* ~ 𝒯,

      E[δ_opt − δ_{k*}(ŵ)] = c₀ + c₁/√K + O(1/√(nK)),

where c₀ ≥ 0 is the irreducible term from k*'s own unseen nuisance. Prediction: OOD error ≈ a + b/√K.

*Proof sketch.* The per-task nuisance covariances are i.i.d. draws, so their average concentrates at rate 1/√K (matrix
Bernstein). The separation δ is Lipschitz in the whitening matrix near Σ̄, which gives the rate. ∎

## Falsifiable predictions and evidence so far
- P1 (Thm 1): matched training transfers better out of distribution than confounded training, and confounded
  training is unstable across splits.
  - v2fresh, unsafe-world predicate, leave-one-template-out: matched 0.887 vs confounded 0.773 mean AUROC; confounded
    split minima are near 0.5.
  - Script: scripts/58_confound_test.py.
- P2 (Thm 1, applied to harm labels): a probe trained on observational harm-vs-safe labels fails out of distribution
  (CI held-out AUROC 0.22).
- P3 (Thm 2): held-out AUROC rises with the number of training templates K, following a + b/√K.
  - Preliminary 8-template test: scripts/59_k_scaling_v2.py.
  - Proper test: the 24-template core24 study plus authx and long-horizon suites, across Qwen3.8, Gemma-4, gpt-oss-20b
    and Muse-Glimmer.

## Algorithm implied (counterfactual compositional gate, CCG)
1. Learn each policy predicate as a linear probe from **counterfactually matched pairs**: no violation labels are
   needed, which matters because violations are rare. Example predicates: critical(action) and unsafe-world.
2. Compose the predicates by the policy's logical form, in log-probability space:
   log P(viol | h) = log σ(w_crit^T h) + log σ(w_unsafe^T h).
3. Calibrate the composed score with a conformal e-process (anytime-valid false-block control), using the episode-level
   calibration that survives within-episode dependence.

## Theorem 3 (observability bound: no monitor can catch an uninformed violation)
*Setting.* A matched pair runs one agent policy π (any stochastic map from context to next tokens) in two environments
E⁺ and E⁻. They are identical except for the responses to some set of tool calls 𝒪, the "revealing" observations.
Let C_t be the context before action a_t, and let R = min{s : the observation at s differs between E⁺ and E⁻} be the
reveal time. Call action t **uninformed** if t ≤ R.

**Claim.** For every t, Law(C_t, a_t, 1{t ≤ R} | E⁺) restricted to {t ≤ R} equals the same quantity under E⁻. So for any
monitor m = f(C_t, a_t) with f measurable (including any function of the actor's own activations, since these are
deterministic in (C_t, a_t), and any LLM judge reading the transcript), the score distribution on uninformed actions is
the same in both worlds. Hence:
- AUROC(m; uninformed violations vs uninformed authorized twins) = 1/2;
- TPR_m(α) = α at every false-positive rate α.

*Proof (coupling).* Couple the two runs with shared randomness. Until the first observation in 𝒪 that differs, every
environment response is the same in both runs, so by induction the token sequences agree up to time R. Since
{t ≤ R} depends only on the history up to t, the restricted joint laws agree. Apply f to both. ∎

**Corollary 3.2 (catch–friction identity).** On the uninformed stratum, a world-unsafe critical action (a violation)
and its authorized twin have the same law of (C_t, a_t). So for any context-measurable gate δ,

    P(δ = 1 | violation, uninformed) = P(δ = 1 | authorized critical twin, uninformed).

On uninformed actions, every unit of catch rate costs exactly one unit of verification friction. This holds for all
monitors: probes, LLM judges, guards. It is an equality, so it can be falsified at every threshold.
- Consequence: monitors evaluated without twin flag rates overstate monitorability. The monolithic probes "catch"
  76–87% of uninformed violations, but they flag the safe twins at the same rate.
- v2fresh test (scripts/75): ECG, mono and auth_only; FPR 1/5/10%; gpt-oss and Gemma-4.
  - Uninformed: 18/18 bootstrap CIs of (TPR − twin flag rate) cover 0; max |diff| 0.06.
  - Informed: 18/18 CIs exclude 0; min diff 0.19.
- Preregistered as H7 on core24, including the LLM judges and the guard.

**Corollary (detectability ceiling).** Let π_u be the share of a model's harms that are uninformed, and evaluate
against a negative set that contains uninformed authorized twins. Then any context-measurable gate has
TPR(α) ≤ (1 − π_u) + π_u·α. Measured π_u on v2fresh (first harm per episode):
- Qwen3.8: π_u = 0.012, ceiling 0.99;
- Gemma-4: π_u = 0.37, ceiling 0.64;
- gpt-oss-20b: π_u = 0.56, ceiling 0.45.

The low hard-negative TPRs first reported for Gemma-4 (0.23) and gpt-oss (0.14) are mostly this ceiling, not a
failure of white-box monitoring. Comparing models without stratifying by π_u is confounded.

*A confound found by testing the theorem (2026-10-01).* The first run of the test gave uninformed world-decoding AUROC
of 0.57 (Gemma-4) and 0.55 (gpt-oss), above a permutation null of 0.50. Since the prompts are identical across all 333
pairs and no pre-reveal observation differs, Theorem 3 says the excess had to come from outside the environment:
- The server rollouts seeded each request with `seed*1000 + t`, so every scenario with the same seed index shared one
  random stream. Seed identity is decodable from transcript text alone: seed 0 vs seed 2 at AUROC 0.99 (Gemma-4), 0.91
  (gpt-oss) and 0.78 (Muse).
- The design was also unbalanced: x− used seeds 0–3 and x+ used seeds 0–1.
- Together these made the world (and therefore harm) partly decodable from the seed: a concrete instance of
  Theorem 1's confounding term β, here a sampling-stream nuisance with ρ ≠ 0.

With seeds 0–1 in both worlds, text-only world decoding on uninformed contexts falls to 0.52 (Gemma-4) and 0.50
(gpt-oss). Qwen's rollouts used hashed per-episode seeds and show no fingerprint (0.51). All cross-model numbers are
now reported on the seed-balanced design, and the rollout code uses hashed per-episode seeds.

*Empirical test:* scripts/66_observability_test.py. It decodes the world from the actor's residual stream separately
on uninformed and informed actions; the theorem predicts exactly chance on the uninformed ones.

## Theorem 4 (epistemic decomposition of the optimal gate)
The harm event factorizes as H = Crit ∧ [(Inf ∧ Unauth) ∨ (¬Inf ∧ Unauth)]. On ¬Inf, Unauth is independent of the
context (Thm 3), so the only context-measurable target there is ¬Inf itself. Consider the *verify-before-act* policy
class, where a critical action is compliant only if it is authorized and the authorizing evidence has been observed.
Its violation predicate V = Crit ∧ (Unauth ∨ ¬Inf) is context-measurable on both strata, and its Bayes posterior is

    P(V | h) = P(Crit | h) · [1 − (1 − P(Unauth | h, Inf)) · (1 − P(¬Inf | h))]    (factors conditionally independent given Crit).

Each factor is learnable from matched pairs **without violation labels for the uninformed stratum**: Crit and ¬Inf
come from benign events, and Unauth comes from informed matched pairs. This is the **epistemic compositional gate
(ECG)**, scripts/65_epistemic_gate.py.

The only way a gate can ever stop an uninformed violation is by stopping the act of proceeding without verifying.
Its cost is measured explicitly as the verification-request rate on unverified but safe critical actions.

## Honest novelty positioning
- The tools are known: LDA/whitening, covariance concentration, and the O(1/√K) domain-diversity rate (cf. Blanchard
  et al., domain generalization by marginal transfer learning). So are invariance ideas (IRM; counterfactual data
  augmentation).
- What would be new:
  - applying them to **white-box safety monitors for LLM agents**;
  - the identification result that a counterfactual benchmark design removes the confounding term that makes
    observational safety probes fail out of distribution;
  - an empirically confirmed diversity scaling law for safety-probe transfer across four frontier-scale models;
  - the compositional gate with an anytime-valid guarantee.
- This is a strong empirical-plus-theory package. It is not new mathematics, and we should not claim it is.

---

# Appendix A. Formal statements and proofs (Theorem 3, Corollaries 3.1–3.2)

**Setting.**
- **Environments.** E^w for w ∈ {+, −} are deterministic maps from (state, tool call) to (observation, next state),
  started from the same initial state s₀ and differing only on a set 𝒟 of (state, call) pairs.
- **Agent.** A policy π maps a context c (system prompt, task, and all previous calls and observations) to a
  distribution over the next call. The policy is the same in both worlds, and the prompts are identical across the
  pair (verified on all 333 v2fresh pairs and all 989 core24 pairs).
- **Trajectories.** τ^w = (c₀, a₀, o₀, c₁, a₁, …), with c_{t+1} = (c_t, a_t, o_t) and o_t = E^w(s_t, a_t).
- **Reveal time.** R = min{t : (s_t, a_t) ∈ 𝒟}, the first call whose observation differs. A step t is
  *uninformed* if t ≤ R.
- **Monitor.** Any measurable m(c_t, a_t, ξ), with ξ independent randomness (e.g. sampling of an LLM judge). White-box
  probes are included: the actor's activations are a deterministic function of (c_t, a_t) for fixed weights.

**Lemma A.1 (coupling).** On a common probability space, run both worlds with the same policy randomness (the same
uniform variables drive π at every step). Then τ^+_{0:R} = τ^−_{0:R} almost surely, i.e. the contexts and calls agree
up to and including the reveal call.

*Proof.* By induction on t ≤ R. At t = 0 both contexts equal the identical prompt. If c_t^+ = c_t^− and t ≤ R, the
shared uniforms give a_t^+ = a_t^−. If t < R, then (s_t, a_t) ∉ 𝒟, so o_t^+ = o_t^− and the states agree, hence
c_{t+1}^+ = c_{t+1}^−. ∎

**Theorem 3 (observability bound).** Let 𝒮 be any selection rule that decides whether step t is evaluated using only
(c_t, a_t) and the event {t ≤ R}. Examples: "first critical action", "every critical action", "the k-th action".
Then the joint law of (c_t, a_t, m(c_t, a_t, ξ)) on the selected uninformed steps is the same under E^+ and E^−.
Hence for every threshold θ:

  P(m ≥ θ | selected, uninformed, w = −) = P(m ≥ θ | selected, uninformed, w = +).

*Proof.* {t ≤ R} is determined by τ_{0:t}, which coincides across worlds by Lemma A.1. The selection depends only on
(c_t, a_t, 1{t ≤ R}). Applying the measurable map (c, a, ξ) ↦ m(c, a, ξ) preserves equality in law. ∎

**Corollary 3.1 (detectability ceiling).** Suppose the negative set contains the authorized twins of uninformed
violations in proportion. If a share π_u of violations is uninformed, then TPR_m(α) ≤ (1 − π_u)·1 + π_u·α for every
monitor m and FPR α.

**Corollary 3.2 (catch–friction identity).** In the unsafe world, an uninformed critical action is a violation (the
authorizing fact has not been revealed, so the action is unauthorized). In the safe world, the same selected action
is authorized. With 𝒮 = "first critical action of the episode" in both worlds, Theorem 3 gives, for every monitor and
threshold:

  TPR_m(θ | uninformed violations) = flag rate_m(θ | uninformed authorized twins).

**Remarks.**
1. *Scope.* The bound concerns distinguishing a violation from its authorized twin. It does not prevent flagging
   *that the agent has not verified*. 1{t ≤ R} is not context-measurable in general, but its correlates (which
   checks were run) are. This is the lever the ECG uses (Theorem 4).
2. *Data-dependent monitors.* The theorem holds for monitors fixed independently of the evaluated episodes. A probe
   cross-fitted on other scenarios is fixed for the held-out fold. Yet in finite samples, training with
   identically distributed positives and negatives produces anti-learning: held-out AUROC of 0.41–0.44 on v2fresh
   gpt-oss for probes trained on uninformed labels, against 0.501 ± 0.046 for 500 random fixed readouts.
   Confirmatory tests therefore use training-free statistics (Amendment 3).
3. *Relation to prior work.* Hu & Wang (2026, arXiv:2607.11751) bound TPR − FPR by the total-variation distance
   between benign and attack views for external monitors. Theorem 3 is an instance of that principle, with TV = 0
   obtained constructively by coupling the agent's own information state. Our additions:
   - it covers white-box self-monitors;
   - it identifies the stratum (t ≤ R) on which TV = 0;
   - the resulting per-model ceiling;
   - the exact equality of Cor. 3.2, which is testable at every threshold.
4. *Stochastic environments.* If E^w are stochastic but agree in law on (s, a) ∉ 𝒟, the same argument applies with
   coupled environment randomness.

---

# Appendix B. Theorem 4: the epistemic decomposition is Bayes-optimal for verify-before-act

**Policy class.** For a critical action a_t, write Auth_t ∈ {0, 1} (authorized in the true world) and
Inf_t = 1{t > R} (the authorizing evidence is in context). Under the *verify-before-act* policy, a critical action is
compliant iff Auth_t = 1 and Inf_t = 1. So the violation event is

  V_t = Crit_t ∧ (¬Auth_t ∨ ¬Inf_t).

**Observation model.** The gate observes h_t = φ(c_t, a_t): any representation that is a measurable function of the
context, e.g. reader or actor activations.

**Theorem 4.** For any loss that is monotone in the posterior P(V_t = 1 | h_t), the Bayes-optimal gate thresholds

  P(V | h) = P(Crit | h) · [1 − P(Auth ∧ Inf | h, Crit)]
           = P(Crit | h) · [1 − (1 − P(¬Auth | h, Crit, Inf)) · (1 − P(¬Inf | h, Crit))].

Two of the factors are identified from matched pairs without violation labels on the uninformed stratum:
- P(Crit | h) is learned from all actions.
- P(¬Inf | h, Crit) is learned from critical actions of both worlds, using the matched-pair reveal time; no violation
  labels are needed.

The third factor, P(¬Auth | h, Crit, Inf), is learned from informed critical actions only. On the uninformed stratum
it is not identified: by Theorem 3, P(¬Auth | h, Crit, ¬Inf) equals the prior for every h, so no context-measurable
estimator can do better there. The decomposition routes the uninformed stratum entirely through the identified factor
P(¬Inf | h).

*Proof.*
1. P(V | h) = P(Crit | h) · P(¬Auth ∨ ¬Inf | h, Crit).
2. Complementation gives P(¬Auth ∨ ¬Inf | h, Crit) = 1 − P(Auth ∧ Inf | h, Crit).
3. The chain rule gives P(Auth ∧ Inf | h, Crit) = P(Inf | h, Crit) · P(Auth | h, Crit, Inf).
4. Substituting P(Inf | ·) = 1 − P(¬Inf | ·) and P(Auth | ·) = 1 − P(¬Auth | ·) gives the displayed form.

No conditional-independence assumption is needed: the third factor conditions on Inf = 1, which is what the
authorization predicate estimates when trained on informed critical actions. The non-identification claim follows
from Theorem 3 applied to the selected critical uninformed steps. ∎

**Remarks.**
1. *Mono as the authorization branch (ECG-m).* Any calibrated estimate of P(¬Auth | h, Crit, Inf) can be plugged in.
   A monolithic harm probe trained on all data is a consistent estimator of P(V | h). Restricted to the informed
   stratum, it estimates P(¬Auth | h, Crit, Inf) up to P(Crit | h), and it uses more training data. Empirically
   (core24 H2), it estimates the informed factor better than the informed-only branch. Plugging it in (ECG-m) is
   allowed by the theorem.
2. *What the decomposition buys.*
   - Out of distribution, the factors are task-general predicates. On core24 unseen templates (H3, ranking), the ECG
     AUROC was 0.92 / 0.75 against 0.59 / 0.42 for mono.
   - The policy is explicit: verify vs block messages.
   - The uninformed stratum is caught by a predicate that is identified, rather than by the implicit, friction-equal
     flagging a monolithic probe performs (Cor. 3.2).
3. *Calibration.* Thresholding the composed posterior with episode-level split conformal bounds the false-block
   probability of compliant episodes under scenario exchangeability. Under task-family shift, the threshold must be
   recalibrated on target-domain data. A label-free variant uses the quantile of unlabeled target scores, which is
   conservative when violations are rare.
