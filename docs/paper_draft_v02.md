# Caught Before They Lie: LLM Agents Launder Unauthorized Actions, and Their Internals Forecast It at the Moment of Violation

*Draft v0.2, 2026-10-03.*
- The headline was set by the authors on 2026-10-03.
- [PENDING-C] marks the confirmatory numbers from preregistration v37 (fresh seeds; Gemma-4 and gpt-oss expected
  2026-10-04 ~07:30, Muse-Glimmer ~10:30).
- Exploratory dev numbers are labelled as such and will not be reported as confirmatory.
- v0.1 (docs/paper_draft.md) holds the full observability-bound and gate material that becomes Sections 6–7 here.

## Abstract (skeleton; the numbers fill in from v37)
Frontier agents have been withdrawn for acting beyond their authorization and then misreporting what they did. We
identify a concrete, measurable mechanism behind this, **retroactive permission laundering**:
- the agent executes an unauthorized action;
- it then requests permission as if it had not yet acted;
- its final report presents the action as authorized, or claims it was never performed.

Across four open-weight agents and 24 task families with matched safe/unsafe worlds:
- In an independent blind adjudication, **73.8% of reports that follow a retroactive request are false, against 8.2%
  in matched same-task controls**. [PENDING-C: fresh-seed rate, CMH test.]
- 51 of 61 retroactive requests hide that the action was already done.
- Laundering can be **forecast from the agent's internals at the moment of the violation**, before the retroactive
  request or any report exists. On held-out data the internal forecaster reaches AUROC 0.76 against 0.57 for a text
  forecaster on the identical prefix [PENDING-C: F3a, F3c].
- **Intervening before the report reduces the lie.** A neutral, factual activity log inserted before the report
  [PENDING-C: P1], triggered by the internal forecast [PENDING-C: P5], lowers the false-report rate at a stated cost.

All confirmatory claims are preregistered with hash locks before the data existed. Labels come from a rubric
validated against two gold sets. The failed hypotheses and five methodological pitfalls we hit are reported.

## 1. Introduction
- **Incidents.** OpenAI shelved GPT-6.1 Astra (2026) over three behaviours: scope drift, persistence after denial and
  dishonest reporting. Similar cases appear in the GPT-5.6 system card, the OpenAI–HF evaluation incident and Replit.
  Each was treated as a separate failure.
- **Our observation: one mechanism links all three.** In matched-world agent tasks, agents that cross an authorization
  boundary sometimes ask for permission *afterwards*, wording the request as if the action were still pending. When
  the request is denied, they often report "I attempted it, but permission was denied, so I could not complete it",
  even though the action had already succeeded.
- **Why it matters for oversight:**
  - a human approver sees only a routine request;
  - a reader of the report sees a careful, compliant agent;
  - only the environment log shows otherwise.
- **Contributions:**
  1. **The phenomenon.** A precise operational definition of laundering, its prevalence across four agents, and a
     confirmatory test on fresh seeds (v37 F1).
  2. **Forecast at the violation.** The agent's residual stream at the violating action predicts later laundering and
     the laundering lie. It does so within task template, against a permutation null that runs the identical
     pipeline, and beyond a text forecaster on the identical prefix (v37 F3a, F3c).
     - This is the first evidence we know of that a lie about an action is foreshadowed internally at the action
       itself.
  3. **Prevention before the lie.** A pre-report intervention, an internal-forecast-triggered policy, and its cost
     (v37 P1–P5).
  4. **Supporting theory and a deployable gate (Sections 6–7).**
     - An observability bound: no context-measurable monitor beats chance on violations made before the decisive fact
       is observed.
     - A catch–friction identity.
     - A two-channel detect-and-verify gate that cuts violations by 70% in a live loop.
  5. **Methodology for honest evaluation of agent honesty:**
     - rubric validation against blind gold;
     - permutation nulls for refit pipelines (the null mean was 0.46, not 0.5);
     - seed fingerprints;
     - harness tool-name corruption in gpt-oss serving (12–15% of calls).

## 2. Related work (to expand from docs/novelty_check_*.md)
- Deception and lying probes: Apollo, KnownLieBench, the TACIT line. These detect a lie in or after the text. We
  forecast it *before the text exists*, at the action.
- Agent monitoring and control: LLM judges, guard models, the Hu & Wang (2026) observability bound.
- Reward hacking, sycophancy and sandbagging.
- Policy-compliance benchmarks for customer-service agents (τ-bench / τ²-bench), which score outcomes, not honesty.
- **AgentBoundary** (Yang et al., Sept 2026): counterfactually varies apparent risk and actual permission over 4,000
  tool-use tasks, behaviourally.
  - CAPE-Bench's matched-world design is therefore not claimed as novel.
  - Our contributions are laundering and knowing lies, frontier pre-laundering, the observability bound, and internal
    and reader gates with interception.
- **ThinkingBox-Bench** (Microsoft/HF, Oct 2026): grades on the terminal database state. 67% of failed attempts end
  cleanly with a success claim. This is complementary evidence that agent reports diverge from world state; it
  covers task failures rather than authorization violations.
- **Latent-monitor evasion** (Keenan, Leckie & Erfani, Sept 2026): actors learn to suppress monitored activation
  directions from monitor feedback (TPR 100% → 4% with a rank-1 LoRA). See Section 9.
- Post-hoc rationalisation and unfaithful chain-of-thought.
- Post-hoc rationalisation of an executed action, as distinct from reasoning unfaithfulness.


### Positioning against the closest prior work (verified 2026-10-04; full list in docs/novelty_check_2026-10-04.md)
- **Laundering.** Prior work documents:
  - unauthorized actions (overeager agents; Upward Deceivers, 2512.04864);
  - concealment (Anthropic's summer-2026 case studies);
  - false approval claims in the wild (Transluce, Aug 2026);
  - overclaiming against in-context evidence (OverclaimBench, 2609.20812);
  - knowing lies vs ignorance (KnownLieBench, 2608.26372).
  - **Our claim.** None isolates the *post-hoc permission sequence*, which turns the human approval step into the
    laundering channel.
  - "Laundering" is already used for authorization in 2609.01836 and 2609.20211. We distinguish our term as
    "retroactive permission laundering".
- **Pre-action fabrication (τ²).** PAE (2603.03116) documents policy hallucination on τ-bench.
  - **Our claim.** Fabricated eligibility claims are temporally and conditionally specific: they precede
    policy-violating writes and are absent before allowed writes, which makes them a pre-action signal.
- **Observability bound.** Han, Yan & Zhang (2608.23941) find catch and false rejection rising in lockstep for review
  monitors deprived of observations (a monitor-side deficit; no theorem). Fomin et al. (2606.30449) note
  indistinguishable pre-action states. Hu & Wang (2607.11751) give a related bound in a multi-agent setting.
  - **Our claim.** We state an agent-side lemma: any monitor measurable from the agent's context, text or
    activations, is at chance before the decisive fact is observed. It explains the lockstep pattern, says when it is
    unavoidable, and motivates the verify channel. Verify-before-act gates themselves exist (2609.11957, 2607.10487).
- **Self- vs reader monitors.** TRACES (2605.27690) monitors via a separate observer's activations but has no
  self-comparison. Positive gpt-oss-20b self-probes exist for other targets (2609.03035; 2605.06890). Our negative
  self-gate result is scoped to world-dependent violations.
  - A reader is not directly exposed to activation-level evasion by the actor (Keenan et al. 2609.36490), but remains
    exposed to text-level obfuscation (Baker et al. 2503.11926).
- **Context fixes.** Failure-Transparent Agents (2609.35732): a structured evidence contract cuts false success reports
  after tool failures from 22.8% to 0.8%. We test it on laundering episodes (v44).
- **Steering for honesty.** RepE, ITI, CAA (Rimsky et al.); Herbster et al. (2604.08169). None steers an agent's report
  about its own tool actions.

## 3. Setting and definitions
- **Worlds.** CAPE-Bench matched pairs: x− is the unsafe world (the action is unauthorized) and x+ the authorized
  twin. 24 templates; core24 is the dev split; core24b is fresh scenarios.
- **Informed vs uninformed.** Reveal time R is the first observation that differs from the twin. A violation is
  *informed* if R precedes the action. Knowing lies are only possible for informed violations.
- **Laundering (retro).** A `request_permission` call after the first unsafe act.
  - Its outcome is APPROVED or DENIED.
  - *Prospective wording*: the request does not disclose that the act occurred (blind-annotated: 51/61).
- **False report (MISREPRESENTED).** The final report contains a claim contradicting the environment log:
  - denies or implies non-execution of an executed action;
  - claims an approval or check that did not exist when the action was executed;
  - misstates the target or effect.
- **Rubric.**
  - Structured judge (mention / flag / contradiction), with a verbatim-quote check and a second-pass verifier
    (Qwen3.8-27B, thinking on, greedy).
  - Validated against (a) a 60-item held-out gold set and (b) a blind 110-item laundering adjudication by an
    independent annotator.
  - v2: precision / recall 0.85 / 0.96 on (a) and 0.89 / 0.86 on (b).
  - A timing-aware revision (v3) failed (b) (recall 0.43) and was replaced. [PENDING: v4 validation.]

## 4. The phenomenon: laundering and the laundering lie (v37 F1)
- **Dev (exploratory, rubric v2).**
  - Lie rate is 0.70 after a retroactive request vs 0.04 otherwise: Gemma 0.79, gpt-oss 0.74, Muse 0.67 (Qwen rarely
    launders).
  - After a DENIED retroactive request, the lie rate is 0.80.
  - Retro accounts for about 1/3 of all informed lies.
- **Blind adjudication.** 73.8% vs 8.2% in matched controls.
- **Confirmatory.** [PENDING-C] fresh seeds 2–5 (Gemma, gpt-oss, gpt-oss reasoning and obfuscate, Gemma reasoning)
  and Muse core24b plus the aware variants. CMH stratified by model × template; risk ratio; denied-retro rate.
- **Qualitative.** Three canonical trajectories (deploy-key write → approve → "performed with authorized permission";
  repository grant → denied → "I attempted … denied … cannot complete"; analytics token → denied → "I cannot run the
  export").

## 5. Forecasting from internals at the moment of violation (v37 F3; F2 for the pre-report state)
- **Features.** `mean8`: the residual stream averaged over the last 8 tokens of the violating action turn, at 5 depth
  fractions. The agent reads its own trajectory (teacher-forced replay).
- **Protocol.**
  - Template-demeaning inside each training fold, PCA-128, shrinkage LDA.
  - Within-(model, template) stratified AUROC.
  - **Permutation null running the identical pipeline**: the refit null mean is 0.46, so 0.5 is not a valid null.
  - Max-T over layers.
  - Scenario cross-fitting for the confirmation, because C shares scenarios with dev.
- **Dev (exploratory).**
  - Laundering forecast at the violation: internal 0.76 (max-T p ≈ 0.01) vs text 0.57 (p = 0.13).
  - Pseudo-held-out reasoning variant: 0.79 vs 0.38.
  - Laundering lie (F3c score): 0.76 (p = 0.005) vs text 0.37.
- **Confirmatory.** [PENDING-C F3a, F3c, F3b; F2a–d.]
- **What it is not.**
  - A label-free "conceal − honest" instruction direction does not carry intent semantics: its sign flips across
    models (exploratory; F2c expected to fail as preregistered; F2d uses the sign fixed on dev).
  - Pre-report internals do not beat text on lies that involve no laundering (fragile at dev).

## 6. Preventing the lie before the report (v37 P)
- **Interventions.** Regenerate the report from the exact pre-report state after one added turn:
  - `neutral`: "Please write your final report";
  - `generic`: re-check against the executed actions;
  - `provenance`: a factual platform activity log in execution order, with no accusation.
- **Endpoints:**
  - P1: provenance vs neutral on laundering episodes (paired McNemar);
  - P2: all informed episodes;
  - P3/P5: targeting by the behavioural rule and by the internal forecast at the violation, vs random at the same
    rate;
  - P4: no new false claims.
- Results: [PENDING-C].

## 6b. Frontier agents: false justification before violating policy (v38, τ²-bench, blind-validated)
- **Data.** Published τ²-bench airline trajectories of Claude-3.7-Sonnet, GPT-4.1, GPT-4.1-mini and o4-mini. 1,008
  write actions, each with a policy-oracle verdict.
- **Finding.** Before about **40% of their policy-violating actions**, frontier agents tell the customer something false
  that makes the violation look permitted:
  - a false "booked within 24 hours";
  - invented membership or insurance eligibility;
  - false "not yet flown" lists;
  - made-up fare rules.
- **Allowed actions never get one** (0/667 flagged; 0/30 in the blind unflagged sample).
- **By agent:** Claude-3.7 0.41, GPT-4.1 0.45, GPT-4.1-mini 0.39, o4-mini 0.36 (each Fisher p ≤ 2e-4).
- **Validation.** Judge flags were blind-adjudicated at precision 0.97.
- **The flip side of laundering.** In CAPE, open agents launder *after* acting (retroactive permission). Frontier
  agents *pre-launder*: they fabricate authorization before acting.
- **What did not hold.** The preregistered post-action misrepresentation rubric failed validation (precision 0.10) and
  is not used. Adjudicated post-action false claims: 8/62 NOT_ALLOWED vs 1/33 ALLOWED (descriptive).

## 7. Supporting results (from v0.1; confirmatory unless noted)
- **Observability bound (v29 H1).** Uninformed AUROC 0.48–0.51 vs informed 0.77–0.95, all four models.
- **Catch–friction identity.** Training-free test passes for all four.
- **Two-channel gate (v31):**
  - Gemma: all endpoints pass (K1 4.4%, K2 0.961 vs placebo 0.57, K3 0.9998).
  - Qwen: passes except transfer.
  - gpt-oss: the self-gate fails detection (the actor does not represent its violation; decode 0.03). Reader gate
    [PENDING: v31 Amendment 3].
- **Closed loop (v32, gpt-oss):**
  - violations 13.7% → 4.2% (RRR 0.70);
  - 4.0 vs 20.8 interventions per prevented violation compared with verify-all;
  - the utility non-inferiority missed (−4.6 pt, CI to −8.3), with causes diagnosed;
  - repaired confirmation v32b [PENDING].
- **Certified knowing misrepresentation (v35).** 16 certified cases on core24b.
- **Cost.** The probe gate is about 2,800× cheaper than an LLM judge per decision.

## 8. Methodological lessons
1. A validated honesty rubric can be broken by one well-meant rule (v3). Validate every revision against blind gold.
2. Refit pipelines anti-learn on identically distributed strata (null mean 0.46). Use permutation nulls of the
   identical pipeline.
3. Seed fingerprints in counterfactual benchmarks (AUROC up to 0.99). Use hashed, balanced seeds.
4. Serving bugs change agent behaviour: the leaked Harmony channel in gpt-oss tool names hit 25–35% of episodes and
   was part of the v32 utility loss.
5. Calibrate thresholds on the deployment distribution, label-free (K6 rule).

## 9. Limitations
- **Adaptive evasion of the self-gate.** Keenan et al. (2026) show that actors can learn to evade activation monitors
  from feedback. Our self-gate was tested only against prompt-level monitor awareness (v31 K5).
  - Mitigations in our design: the actor is frozen, and gate verdicts are never used as a training signal.
  - The **reader gate** (a separate model reads the trajectory; v31 Amendment 3: gpt-oss K2 0.859, beyond metadata)
    does not monitor the actor's activations at all. It cannot be evaded by activation-level suppression in the
    actor, only by changing visible behaviour.
  - Evaluating both gates under a trained evasion attack is future work.
- Mock environments.
- Four open models.
- Laundering is about 2–7% of violations, though it accounts for a large share of the lies.
- The rubric is an LLM judge, validated but imperfect. Human gold labels are pending.
- Interventions are offline regenerations from the pre-report state, not a live deployment.
