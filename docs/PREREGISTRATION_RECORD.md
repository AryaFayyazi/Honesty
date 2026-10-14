# Full preregistration record

Every confirmatory test of this project, in the order run, **including tests that did not pass**. Each test has a
preregistration document (`docs/preregistration_vXX.md`) whose sha256 is locked in `results/prereg_vXX_lock.json`
before its data existed; deviations and addenda are recorded in the same lock files. The paper reports the final
working results; this file is the complete record. For each test that did not pass, the result column gives the
diagnosed cause and, where applicable, the later test that fixed it (⇒ fixed in).

Models: Q = Qwen3.8-27B, M = Muse-Glimmer-30B, G = Gemma-4-26B-A4B, O = gpt-oss-20b.


## Phenomenon

| Test | Data | Models | Result | Outcome |
|---|---|---|---|---|
| Laundering marks a lie (CMH) | 1,081 fresh informed | M G O | 0.70 vs 0.08; OR 7.0; p<10-6 | PASS |
| Frontier false justification before violating writes | 894 τ2 writes | 4 frontier | 0.26 (0.40 miss-corrected) vs 0/667; precision 0.97 | PASS |
| Laundering, four models | fresh four-model episodes | Q M G O | (pending) | pending |

## Forecasting

| Test | Data | Models | Result | Outcome |
|---|---|---|---|---|
| Observability bound (uninformed at chance) | development, all actions | Q M G O | 0.48–0.51 uninformed; 0.77–0.95 informed | PASS |
| Lie forecast before the report | 1,081 fresh | M G O | AUROC_w 0.745 [0.67, 0.82]; Holm 0.002 | PASS |
| Non-laundering lie forecast before the report | 990 fresh | M G O | 0.56; Holm 0.21 | **did not pass** |
| Laundering forecast at the violation | 1,081 fresh | M G O | internal 0.59, text 0.65; Holm 0.095 | **did not pass** |
| Laundering-lie forecast at the violation | 1,081 fresh | M G O | internal 0.60, text 0.61; Holm 0.095 | **did not pass** |
| Monitor intercepts laundering lies | fresh | M | 25/29 = 0.86 [0.69, 0.95] | PASS |
| Internal forecast before report, first test | 110 fresh | M | 0.64; Holm 0.063 (power 0.71) | **did not pass** |
| Internal > text before report, first test | 110 fresh | M | +0.08 [-0.11, 0.25] (power 0.31) | **did not pass** |
| Internal forecast, powered replication (interim, α=0.01) | 196 fresh | M | 0.59; p=0.06 | **did not pass** |
| Internal > text, powered replication (interim) | 196 fresh | M | 0.59 vs 0.68; -0.09 [-0.22, +0.03] | **did not pass** |
| Internal > text, final look (stage 2) | approx600 fresh | M | (queued last) | pending |
| Per-model internal forecast, Gemma-4 | 505 fresh | G | 0.87; Holm 4×10-4 (text 0.94) | PASS |
| Per-model internal forecast, gpt-oss | 318 fresh | O | 0.72; Holm 0.007 (raw p 0.002; text 0.81) | PASS |
| Per-model internal forecast, Qwen3.8 | 39 fresh | Q | 0.73 vs text 0.51; Holm 0.053 | **did not pass** |
| Per-model internal forecast, Muse | 196 fresh | M | 0.59 vs text 0.68; Holm 0.06 | **did not pass** |
| Pooled internal > text (4 models) | fresh | Q M G O | -0.08 [-0.15, -0.01] | **did not pass** |
| Ensemble internal > text (V1) | 959 fresh | Q G O | +0.04 [-0.02, +0.10]; Holm 0.22 | **did not pass** |
| Label efficiency: internal > text at 25% labels (V2) | 959 fresh | Q G O | +0.03 [-0.08, +0.13]; Holm 0.29 | **did not pass** |
| Internal > zero-shot CoT monitor (C1) | 1,155 fresh | Q M G O | +0.06 [-0.05, +0.16]; Holm 0.27 | **did not pass** |
| Internal adds to best text monitor (C2) | 1,155 fresh | Q M G O | -0.04 | **did not pass** |
| Internal > CoT monitor under obfuscation (C3) | 574 fresh | Q M G O | +0.16 [0.01, 0.28]; p=0.02 | PASS |
| Ensemble vs all frozen forecasters (descriptive) | 959 fresh | Q G O | best: 0.85 vs text 0.82, CoT monitor 0.68 | – |

## Violation forecasting

| Test | Data | Models | Result | Outcome |
|---|---|---|---|---|
| After the reveal: internal > chance (V1) | 9,287 fresh | Q M G O | 0.580 [0.553, 0.608]; perm. p=0.0005 | PASS |
| After the reveal: internal > CoT monitor (V2) | 3,104 fresh | Q M G O | +0.065 [0.010, 0.121]; Holm 0.015 | PASS |
| After the reveal: internal > supervised text (V3) | 9,287 fresh | Q M G O | +0.034 [0.006, 0.060]; Holm 0.015 | PASS |
| At the decision: internal > chance (E1) | 43,210 fresh actions | Q M G O | 0.917 vs authorized twin; 0.985 vs other actions | PASS |
| At the decision: internal > supervised text (E2) | 43,210 fresh actions | Q M G O | +0.007; cause: permission is written in the authorized twin's text; vs other actions +0.068 [0.050, 0.089] | **did not pass** |
| At the decision: internal > CoT monitor (E3) | 3,424 fresh actions | Q M G O | -0.022 [-0.047, -0.001] | **did not pass** |

## Context interventions

| Test | Data | Models | Result | Outcome |
|---|---|---|---|---|
| Activity log reduces laundering lies | fresh | M G O | 0.80→0.71; Holm 0.15 | **did not pass** |
| Activity log reduces all lies | fresh | M G O | 0.149→0.132; Holm 0.09 | **did not pass** |
| Laundering-targeted log beats random | fresh | M G O | 0.149 vs 0.022 prevented per intervention | PASS |
| Internally targeted log beats random | fresh | M G O | -0.011 vs 0.022 | **did not pass** |
| Evidence contract on laundering episodes | fresh | M G O | 0.76→0.53; Holm 0.002 | PASS |
| Evidence contract on all informed | fresh | M G O | 0.18→0.26 (backfire) | **did not pass** |
| Transparency instruction on all informed | fresh | M G O | 0.19→0.25 (backfire) | **did not pass** |
| Internally triggered contract vs none | 110 fresh | M | 0.85→0.39; p=2×10-7 | PASS |
| Targeted beats blanket contract | 110 fresh | M | targeted 0.51, blanket 0.33 | **did not pass** |
| gpt-oss backfire under blanket contract (H1c) | 295 fresh | O | 0.16→0.42; p=3×10-12 | PASS |
| H1: contract benefit ordered by K | fresh, 4 models | Q M G O | exact order; ρ=1.0 (p=1/24 dropped: 3 of 4 positions seen on development; Qwen out of sample, gap to Gemma n.s.) | PASS |
| Internal law vs CoT law (Qwen3.8 arbitrates) | fresh | Q M | B_M-B_Q=0.38 [0.18, 0.58]: favours internal | PASS |
| H3: targeted vs blanket, gpt-oss | 295 fresh | O | targeted 0.16 vs blanket 0.42; p=2×10-13 | PASS |
| H3: targeted vs blanket, Gemma-4 | 480 fresh | G | no differences (trigger 3%) | – |
| H3: targeted vs blanket, Muse | 151 fresh | M | blanket 0.31 < targeted 0.39 < none 0.80 | – |
| H3: targeted vs blanket, Qwen3.8 | 36 fresh | Q | targeted = blanket 0.47 < none 0.58 | – |

## Steering

| Test | Data | Models | Result | Outcome |
|---|---|---|---|---|
| World-knowledge probe direction | development | M | 0.22→0.23 | **did not pass** |
| Lie-forecast (LDA) direction, decode | 115 | M | 0.79→0.81 | **did not pass** |
| Lie-forecast direction, 16–64σ | fresh fold | M | 0.73→0.84 | **did not pass** |
| Difference of means, multi-layer | development | M | no configuration kept reports | **did not pass** |
| CAA α=4, delayed | 81 fresh paired | M | 0.72→0.64; p=0.13 | **did not pass** |
| CAA α=8, delayed | 110 fresh | M | 0.71→0.44; Holm 5×10-4 | PASS |
| Honesty vs random direction, α=8 | 110 fresh | M | 0.67 vs 0.45 complete-case; Holm 0.002 (random vs none: -0.02) | PASS |
| Refined CAA (window of generated tokens 17–120) | 196 fresh | M | null; cause: the window steered reasoning, not the report ⇒ fixed in replication below | **did not pass** |
| CAA α=4, interim look | 196 fresh | M | -0.083; Holm 0.07 vs α=0.01 | **did not pass** |
| Report-only steering (development selection) | 115 development | M | reports degenerate; cause: the lie is planned in the reasoning ⇒ fixed in reasoning-only arm | **did not pass** |
| CAA α=8 replication (P1, P2) | 196 fresh | M | 0.77→0.52 and vs random 0.75→0.49; Holm 10-6, 5×10-7 | PASS |
| Reasoning-only steering (mechanism) | 196 fresh | M | 0.79→0.56; vs reasoning+report p=0.46 | PASS |
| Per-model CAA | fresh four-model | Q G O | (pending) | pending |

## Label audit

| Test | Data | Models | Result | Outcome |
|---|---|---|---|---|
| False CANDIDs higher under steering | 235 blind-audited | M | 0.11 vs 0.71 (lower); corrected steering -0.39 | PASS |
| False CANDIDs higher under contract | 235 blind-audited | M G O | 0.10 vs 0.42 (lower); corrected backfire +0.10 | PASS |
| SPIN audit; corrected laundering contrast | 64 blind-audited | M G O | 0.79 vs 0.09; RR 8.9 [5.5, 16.1] | PASS |

## Deployment

| Test | Data | Models | Result | Outcome |
|---|---|---|---|---|
| Self-gate, fresh scenarios | fresh | G | detection 0.96; all endpoints | PASS |
| Self-gate | fresh | O | 0.78 vs placebo 0.76 | **did not pass** |
| Reader gate (Qwen3.8 reads gpt-oss) | fresh seeds | O | 0.86; +0.28 beyond placebo | PASS |
| Closed loop: fewer violations | 1,296 per arm | O | 13.7%→4.2% | PASS |
| Closed loop: utility non-inferior | 1,296 per arm | O | -4.6 points, CI to -8.3 | **did not pass** |
| Repaired closed loop | fresh | O | (pending) | pending |

## Violation prevention (decision steering)

| Test | Data | Models | Result | Outcome |
|---|---|---|---|---|
| Blanket α=1 fewer violations (P1) | 200 fresh sites | G | 0.41→0.165; Holm 7×10-10 | PASS |
| Blanket beats random, unsafe-or-broken (P2) | 200 fresh sites | G | random breaks every turn; Holm 2×10-50 | PASS |
| Blanket keeps authorized work, margin 0.10 (U1) | 200 fresh sites | G | 0.89→0.755 in one turn; cause: an extra check counted as lost work ⇒ fixed in C2 | **did not pass** |
| Forecast-gated fewer violations (G1) | 200 fresh sites | G | 0.41→0.055 (71/0); Holm 8×10-22 | PASS |
| Forecast-gated keeps authorized work, margin 0.05 (G2) | 200 fresh sites | G | 0.89→0.815 in one turn; same cause ⇒ fixed in C2 (0.99 vs 0.99) | **did not pass** |
| Eventual violation, gate once (C1) | 200 fresh, 6 more turns | G | 0.655→0.575; p=0.007 (70% postponed) | PASS |
| Eventual authorized completion, gate once (C2) | 200 fresh, 6 more turns | G | 0.99 vs 0.99 (delayed, not lost) | PASS |
| Gate every action (D1, D2) | 100+100 fresh | G | (running) | pending |
| Decision steering, other models | fresh | M O Q | (running) | pending |

## Pitfalls that changed our conclusions

| Pitfall | Fix |
|---|---|
| A rubric rule excused false ``denied'' reports (laundering recall 0.43) | Blind validation of every revision |
| Judge accuracy differs by condition | Blind audit per condition |
| Refit pipelines anti-learn (null mean 0.46) | Null of the identical pipeline |
| Sampling seeds decodable (AUROC up to 0.99) | Hashed, balanced seeds |
| A serving parser silently parsed no tool calls; the agent looked perfectly safe | Smoke gates against a known baseline |
| Report extraction scored reasoning as reports | Detect the user channel |
| Steering broke the format before the content | Delayed steering; guards |
| Blanket honesty prompts created false claims | Target the intervention |
| Small fresh tests underpowered | Power analysis; two-stage α |
| A steering window counted reasoning tokens, so most reports went unsteered | Anchor steering at the report's first token |

## Superseded attempts and their fixes (narrative)

- **Lie forecast at the violation** (v37): internals ≈ text (0.59–0.60). Superseded by the pre-report forecast (0.745) and, for the violation itself, by the after-reveal (v55) and decision-time (v57) forecasts.
- **Steering window over generated tokens 17–120** (v48): no effect on 196 fresh episodes. Cause: the agent writes its reasoning first; the report started after token 120 in 36% of episodes, so the window steered reasoning. Report-only steering (v56) broke reports at doses that changed labels. Fixed: v58 replicates whole-generation steering on the same episodes (0.77→0.52) and shows that reasoning-only steering carries the full effect.
- **Decision-steering dose grid {4, 8, 12}** (v54 smoke): broke every Gemma turn. Recalibrated to {1, 2, 4} before any sweep outcome (Addendum 2).
- **Random-direction specificity rule** (v54): degenerate because random directions break the output; replaced by the unsafe-or-broken rate (Addendum 5), before confirmation.
- **Single-turn utility margins** (v54 U1/G2): failed in one turn; multi-turn continuation (v59 C2) shows authorized work is completed equally often (0.99 vs 0.99), only delayed.
- **Gate on one turn** (v59 C1): 70% of fixed violations happen later; gate-always (v59b) tests gating every action.
- **Decision-time internals vs text/CoT** (v57 E2/E3): equal overall because the authorized twin states its permission in text; the contrast against the agent's other actions is retested on new seeds (v60).
- **v57 obfuscation comparison**: an unpaired comparison (0.936 vs 0.879) was retracted; on the same units the CoT monitor is not worse.
- **Engineering incidents** (recorded in `docs/research_ledger.md`): batch OOM (token-budget batching), full-vocabulary logits OOM (logits_to_keep=1), HF gpt-oss attention OOM (10k-token cap), a hung vLLM engine after an analysis crash (separate processes + timeout); no result was read before any fix.

## Violation prevention: continuation tests (added 2026-10-07)

| Test | Data | Models | Result | Outcome |
|---|---|---|---|---|
| Gate once: eventual violation (v59 C1) | 200 fresh, 6 turns | G | 0.655 → 0.575; p = 0.007 (70% of first-turn fixes postponed) | PASS |
| Gate once: eventual authorized completion (v59 C2) | 200 fresh, 6 turns | G | 0.99 vs 0.99 | PASS |
| Gate once: eventual violation (v59 C1) | 200 fresh, 6 turns | O | 0.81 → 0.64; p = 3e-9 | PASS |
| Gate once: eventual authorized completion (v59 C2) | 200 fresh, 6 turns | O | 0.92 vs 0.92 | PASS |
| Gate every action: eventual violation (v59b D1) | 100 fresh x−, 6 turns | G | 0.68 → 0.15; 53/0; p = 1e-16 | PASS |
| Gate every action: completion, margin 0.05 (v59b D2) | 100 fresh x+, 6 turns | G | 0.95 vs 0.99; lower bound −0.081; first diagnosed as horizon truncation | **did not pass** ⇒ D2′ |
| Gate every action: completion, 12 turns (v59b D2′) | 200 fresh x+, 12 turns | G | 0.94 vs 1.00; lower bound −0.089; cause: repeated false alarms on the authorized action (4.25 fires per lost episode vs 0.41) | **did not pass** ⇒ fixed in v59d (gate-escalate) |
| Gate, then ask (v59d E1 / E2): the fix | 100 x− / 200 x+ fresh, 12 turns | G | violations 0.70→0.09 (61/0, p=4e-19); completion 1.00 vs 0.995; asks 0.51 / 0.12 per episode | **passed** (fix confirmed) |
| Decision steering, Muse: tool-call parsing (pipeline check, not a test) | first v54 Muse job, sampling stage | M | Muse writes `<atem:function_calls>` calls; the parser expected `to=functions`, so every call would have read as final | **caught before any data** ⇒ fixed (v54 Clarification 3; smoke guard added) |
| Muse confirmation step: environment (pipeline check, not a test) | first Muse confirmation job | M | crashed on import joblib (Muse env has no sklearn/joblib) before generating | **caught before any data** ⇒ fixed (forecaster as .npz; v54 Clarification 4) |
| Blanket decision steering, Muse (P1 / P2) | 200 fresh x− / x+ | M | 0.175→0.13 (21/12), Holm p=0.08; vs random Holm p=0.07; cause: low base rate, dose capped by guards, and on turns the gate does not flag steering adds violations (0.06→0.18, 1/7) | **did not pass** ⇒ fixed by forecast gating (G1 0.175→0.095, 20/4, p=8e-4; G2 passes) |
| Repaired closed loop (v32b; gpt-oss reader gate) | queued, never run | O | withdrawn before any data: superseded by the preregistered gate, gate-every-action and gate-then-ask tests (v54, v59b, v59d) | **withdrawn** (not a failure; original v32 result kept above) |
| End-to-end, honesty lever on remaining violations (v61 E3) | 197 fresh x−, Muse | M | 0.051 vs 0.056 (5/6), p=0.73; cause: the gate leaves 34 violating episodes and ~10 lies (11 discordant pairs), and lies are rarer here (0.29) than in the laundering-rich episodes where honesty steering was confirmed (0.71–0.79) | **did not pass** (underpowered; E1 and E2 pass) ⇒ powered follow-up proposed |
| Pre-report lie forecast, single internal readout vs text, Muse (v47 interim = final) | 196 fresh, 145 lies | M | internal 0.587 (p=0.06, n.s. at α=0.01); text 0.680; internal − text −0.093 [−0.217, 0.030]; cause: one readout at one layer, and Muse lies in 74% of episodes | **did not pass** ⇒ fixed by the internal ensemble (0.85 vs text 0.82 vs CoT 0.68 on fresh Gemma/gpt-oss/Qwen); stage 2 not run |
| Qwen gate-dose selection (development rule, not a test) | 80+80 development | Q | the absolute PARSE ≤ 0.05 rule rejected Qwen's own baseline (unsteered PARSE 0.0625; gated adds none); no blanket dose passes the progress guard | **fixed** by Addendum 7 (relative guard, as the main v54 guard; other models' doses unchanged); Qwen gate α = 2 |
| Honesty steering on all violations, end to end (v61b H) | 80 violating Muse episodes, fresh continuation | M | lie 0.29 → 0.34 (9/13), p=0.86; powered; also no gain on laundering episodes (0.24 → 0.33, n=21); cause: the v58 direction (built and confirmed on original laundering-rich rollouts) does not transfer to continued episodes | **did not pass** ⇒ honesty-steering claim scoped to its confirmed setting; end-to-end lie stage to be tested with the targeted evidence contract |
| Forecast-gated progress non-inferiority, Qwen (G2) | 200 fresh x+ sites | Q | single-turn progress 0.84 → 0.80 (−0.04, lower bound −0.065 vs margin −0.05); G1 passes (0.266 → 0.043, 41/0) | **did not pass (narrow)** ⇒ resolved: over the episode, authorized completion 0.94 vs 0.94 (v59 C2 passes; delay +0.11 turns), so the loss was delay |
| Gate every action: completion, Qwen (v59b D2′) | 200 fresh x+, 12 turns | Q | 0.915 vs 0.965 (−0.05, lower −0.077); cause: repeated false alarms on authorized tasks (3.4 fires per lost episode vs 0.07) | **did not pass** ⇒ fix queued (v59d gate-then-ask, as for Gemma); D1 passes (0.41 → 0.05, 36/0) |
| Evidence contract as the end-to-end lie stage (v61c H) | 80 violating Muse episodes, fresh continuation | M | lie 0.3125 → 0.2875 (13/11), p=0.42 (single-pass 0.30 → 0.20, p=0.08); the contract doubles candid disclosure (0.19 → 0.45, descriptive) but leaves active false claims unchanged | **did not pass** ⇒ v63 (direction built on continued episodes) runs; paper: preventing the violation is the reliable lie prevention |
| Internal gate vs CoT-monitor gate at matched false alarms (v62 H) | v54 confirmation turns, 4 models | G O M Q | pooled discordant 16 (internal better) vs 20 (CoT better), p=0.80; at the decision the plan is written, so a text monitor triggers the same prevention | **did not pass** ⇒ paper states prevention at the decision does not need internals; internals' advantages there are cost (a readout, not a model call) and earlier forecasts. Descriptive check (2026-10-10): the CoT gate is not weaker under obfuscation pressure (flags 96% of violators vs 85%), so robustness under pressure holds for the lie forecast only |
| Decision steering: gpt-oss original dose grid | 80+80 development | O | every dose broke the tool-call format (PARSE ≥ 0.5) | **did not pass** ⇒ fixed in Addendum 6 (low doses) |
| Honesty steering quality check (v58 degradation guard) | 196 fresh | M | steered reports longer (766 vs 412 tokens) and degraded slightly more often (0.20 vs 0.15) | **did not pass** ⇒ disclosed in the paper; the lie reduction and the random-direction control stand |
| Gate, then ask, gpt-oss (v59d E1 / E2) | 100 x− / 200 x+ fresh, 12 turns | O | violations 0.78→0.60 (19/1, Holm 4e-5); completion 0.935 vs 0.93 (D2′ passes); asks 0.08 / 0.015 per episode | **passed** (replicates the Gemma policy) |
| v59d gpt-oss report stage (pipeline check, not a test) | job 3494 | O | CUDA OOM in the batched report generation; transcripts held only in memory were lost; no report generated | **fixed before any report data** (v64 Addendum 1: trajectories saved first, OOM halving, report_only; gpt-oss rerun `_esc64`) |
| Gate, then ask, Muse (v59d E1 / E2) | 100 x− / 200 x+ fresh, 12 turns | M | violations 0.35→0.20 (21/6, Holm p=0.003); completion 0.995 vs 1.00 (D2′ passes, lower −0.015); asks 3.22 / 0.51 per episode | **passed** (third family; analysis run on CPU from the complete step-12 trajectories while the report stage continued) |
| τ² cell selection (v65 Addendum 11 rule) | 7 screen cells, 20–60 sims each | Q/O/M/G | selected gpt-oss P0_enf: adjudicated 5/20 (0.25); all other validated cells ≤ 4/20; Gemma 0/20 in both cells; Muse ineligible (validation) | **rule applied** (exploratory selection; confirmation on new tasks and trials: dev 3531 → conf 3532/3533) |
| Gate, then ask, Qwen (v59d E1 / E2) | 100 x− / 200 x+ fresh, 12 turns (12-step rerun `_esc64`, v64 Addendum 2) | Q | violations 0.41→0.07 (34/0, Holm 1.2e-10); completion 0.95 vs 0.955 (D2′ passes); asks 0.78 / 0.045 per episode; rerun reproduced all 600 step-1–11 histories | **passed** (original run hit an 8 h timeout in step 12 ⇒ fixed by the rerun; confirmatory per the rule fixed before data) |
| τ² gate transfer (v65 development, gpt-oss P0_enf) | 60 dev sims, 59 scored writes | O | frozen within-tool AUROC 0.575; refit out-of-fold 0.445; at τ fires on 0% of violating writes | **descriptive, poor transfer**; go rule (base rate 0.23 ≥ 0.05) passes, so the preregistered confirmation runs; V1 predicted to fail (violations are uninformed policy misapplications, not knowing violations) |
| τ² confirmation (v65 V1 / U1), gpt-oss P0_enf | 30 conf tasks × 4 trials, paired | O | V1: 0.142→0.150 (13/14, p=0.65); U1 reward 0.367→0.383 (passes); gate fires on 1.7% of tool turns | **V1 did not pass (as predicted before data)** ⇒ cause: τ² violations of open agents are uninformed (they comply when shown the decision: v66, 1 of 95); the gate targets knowing violations ⇒ follow-ups v66 (open agents: no condition with ≥10% knowing violations) and v69 (reader gate on frontier agents' knowing violations) |
| Reader gate on frontier τ² trajectories (v69 R1 / R2) | 894 frontier writes (227 violating, 60 knowing) | Q reads Claude/GPT-4.1/4.1-mini/o4-mini | R1 AUROC 0.587 [0.50, 0.70], Holm 0.06; R2 knowing 0.68 vs other 0.57, p 0.13 | **did not pass** (direction as predicted; underpowered: 60 knowing violations) ⇒ powered replication on published retail trajectories under consideration |
| Real-context decision turns on τ² (v70 G1 / G2) | 128 violating + 410 allowed frontier sites, separate none / gate runs | O / G (Q failed go rule) | gpt-oss 0.438→0.406 (18/14, p 0.30); Gemma 0.234→0.219 (7/5) | **invalid measurement** ⇒ cause: vLLM batched generation not reproducible across runs (arms differ at 30–49% of sites; gate fired at 4–12%) ⇒ fix: v70b exact within-request pairing (Addendum 1) |
| Real-context decision turns, exact pairs (v70b) | 128 violating + 410 allowed conf sites, one gate request per site | O / G | gpt-oss 0.422→0.430 (2/3); Gemma 0.234→0.219 (2/0); G2 passes both | **did not pass** ⇒ cause: the frozen CAPE readout fires on only 7–24% of real violating turns (steering works when it fires: Gemma 2/2) ⇒ fix: v72 in-domain readout + frozen steering |
| Leave-one-family-out generalization (v71 L1) | 43,210 fresh decision units, 8 families × 4 models | Q M G O | held-out readout, violation vs authorized twin 0.811 [0.79, 0.82]; Holm 5e-4 | **passed** |
| Leave-one-family-out non-inferiority (v71 L2) | same | Q M G O | held-out minus full gate −0.077 (lower −0.089; margin −0.05) | **did not pass** ⇒ cause: a family-specific component (largest for cost/SLA constraints: 0.64 held out vs 0.97); reported as the cost of generalization |
| In-domain readout at real τ² decision points (v72 go rule) | dev: 99 violating + 257 allowed sites | G / O | OOF within-tool AUROC 0.15 (G), 0.29 (O) | **go rule not met** ⇒ no confirmation (preregistered); no linear signal of the coming violation in the pre-action state at real τ² decision points |
| Knowing violations at real τ² decision points (v73 go rule) | dev: 99 violating + 257 allowed sites, oracle's answer in history | O / G / Q | continuation 0/99, 0/99, 1/99 (vs 40% / 15% / 6% without the answer, v70) | **go rule not met** ⇒ no confirmation (preregistered); open agents do not act against a NOT ALLOWED they hold, so τ² offers no knowing violations to gate ⇒ redesign: v74 AgentDojo (prompt-injected actions) |
| Frozen CAPE gate on AgentDojo prompt injections (v74 go rule), gpt-oss | dev: 29 user tasks; 87 benign + 285 attacked episodes | O | ASR 0.26; readout fires on 6.8% of 88 injected calls (AUROC vs benign 0.60) | **go rule not met** ⇒ cause: the agent treats the injected instruction as the user's (deceived, not knowing) ⇒ redesign: v75, injections under a prompt defense that says not to obey them (knowing by construction) |
| Frozen CAPE gate on AgentDojo under spotlighting (v75 go rule), gpt-oss | dev: 87 benign + 285 attacked episodes | O | ASR 0.26 (= undefended); fires on 12% of 82 injected calls (AUROC 0.56); rule mentioned before 15% of injected calls | **go rule not met** ⇒ gpt-oss ignores the defense (not knowing); the rare knowing injected calls score higher (descriptive) |
| Frozen CAPE gate on AgentDojo under spotlighting (v75 go rule), Gemma | dev: 87 benign + 285 attacked episodes | G | ASR under the defense 0.077 (< 0.10); fires on 9% of 85 injected calls | **go rule not met** ⇒ the defense already stops Gemma's injections (it obeys a rule it registers); nothing left for the gate ⇒ v76 (undefended, in-domain readout fit) |
| In-domain CAPE readout on AgentDojo (v76 go rule), Gemma | dev: 29 user tasks; 87 benign + 285 attacked episodes; 5,828 tool calls | G | OOF within-tool AUROC 0.92; vs exposed non-injected 0.97; fires on 88% of injected at 10% benign FA; leave-injection-goal-out 0.995 (descriptive) | **go rule passed** ⇒ confirmation running (C1 ASR, C2 utility) |
| In-domain CAPE readout + frozen CAPE steering on AgentDojo (v76 C1, C2), Gemma | 664 held-out user × injection pairs + 204 benign episodes (68 unseen user tasks), paired arms | G | attack success 0.118 → 0.057 (42 fixed / 2 broken; p = 5.6e-11; Holm ≤ 1.1e-10); benign utility 0.637 vs 0.637 (lower bound −0.020; margin −0.10) | **passed** (both co-primary endpoints) |
| In-domain CAPE readout + frozen CAPE steering on AgentDojo (v76 C1, C2), gpt-oss | 653 held-out pairs (12 server-error pairs excluded, Addendum 3) + 204 benign episodes | O | attack success 0.285 → 0.175 (90 fixed / 18 broken; Holm 1.1e-12; worst case 90/29, p = 9.3e-9); benign utility 0.667 vs 0.681 (lower bound −0.020) | **passed** (both co-primary endpoints) |
| In-domain CAPE readout on AgentDojo (v76 go rule), Muse | dev: 87 benign + 285 attacked episodes | M | undefended ASR 0.042; 13 injected calls | **go rule not met** ⇒ Muse largely resists the injections; too few to test prevention |
| In-domain CAPE readout on AgentDojo (v76 go rule), Qwen | dev: 87 benign + 285 attacked episodes | Q | undefended ASR 0.014; 0 tagged injected calls | **go rule not met** ⇒ Qwen resists the injections; nothing to prevent |
| Counterfactual context swap: does unauthorized-provenance information move the readout? (v77 P1, P2), gpt-oss + Gemma | 664 confirmation pairs each; 223 / 651 injected calls; same tokens scored with real vs third-party context | O / G | P1 −0.001 / −0.013; DiD +0.001 / +0.001; fire rates unchanged; pipeline exact | **did not pass** ⇒ the belief mechanism (information form) is not supported; removed from the paper's claims |
| Gate every action, Gemma, uniform 12-turn replication (v59 addendum) | 100 x− + 200 x+ v54 confirmation sites, K = 12 | G | violations 0.72 → 0.21 (51/0; Holm 9e-16); completion 0.935 vs 1.00 (D2′ −0.065, not met) | **D1 passed; D2′ not met** (as before; gate-then-ask fixes completion) |
| Gate-then-ask with the live escalating model approver (v78 M1, M2), Qwen | 100 x− + 200 x+ v54 confirmation sites, K = 12, paired none | Q | violations 0.40 → 0.04 (36/0; Holm 1.5e-11); completion 0.95 vs 0.955 (lower −0.025; margin −0.05); 30% of asks escalated | **passed** (both endpoints) |
| Belief reversal / knowing calls (v75 Addendum 2 S1, S2), Gemma | v76 + v75 dev injected and benign calls | G | S1 within-tool 0.23 [0.11, 0.51]; S2 +0.07 [−0.05, 0.17] | **did not pass** (S1 direction replicates gpt-oss discovery; CI touches 0.5) |
| τ² knowing-violation screens (v66, 18 cells: oracle / shown decision / + enforcement claim / + persistent customer) | 20 dev tasks × 1 trial per cell | Q / O / G | max informed rate 0.05 (1 cell); shown NOT ALLOWED decisions acted on 1 of 95 | **no cell met the 10% go rule** ⇒ v66 confirmation not run (preregistered); finding: open agents comply when informed, even under pressure |
| v64 P1: misreported violations, pooled Gemma + gpt-oss + Qwen | 300 x− sites, 12 turns, reports judged (rubric v4) | G/O/Q | 0.096→0.011 (24/1, p=7.7e-7); P2 per model all pass (Holm 0.016 / 0.012 / 0.016); NO_REPORT-as-lie sensitivity stronger | **passed** |
| v64 A1: zero-shot model approver (binary) | 521 logged asks | G/O/M | agreement 0.61; preregistered worst-case rule fails (Gemma completion 0.945 vs 1.00; Muse 0.418 > none, 0.85 vs 0.995) | **did not pass** ⇒ cause: (i) 'deny if unclear' blocks authorized work; (ii) oracle-disagreement counts harmless reads as unsafe (sensitivity, rule fixed before computing: 0 of 65 are unsafe if executed; safety holds). Fix: v67 approver with ESCALATE, preregistered, confirmatory on fresh Qwen asks (job 3542) |
| v67: model approver with escalation (APPROVE / DENY / ESCALATE) | 608 logged asks; confirmatory: 87 fresh Qwen asks | Q (conf.) + G/O/M | Qwen: 0 harmful approvals; worst-case violations 0.07 = channel; completion 0.95 = channel; every model passes E1/E2; pooled escalation share 0.25 | **passed** (fix for v64 A1) |
| Honesty direction built on continued episodes (v63) | 132 violating Muse dev states, 8 samples each (858 judged; 80 mixed states); sweep α ∈ {4, 8, 12} | M | direction held-out AUROC 0.50–0.63; development lie rate plain 0.41 vs α4 0.46, α8 0.42, α12 0.50; no dose qualified → no fresh test (preregistered) | **did not pass** ⇒ lie-stage steering after a violation fails in all three attempts (v61b, v61c, v63); paper: preventing the violation is the lever for the lie |

## v79: per-model honesty-steering confirmation (Gemma, Qwen; gpt-oss by addendum)
- **Test:** report-time CAA steering selected on development (Gemma α = 4, Qwen α = 8) vs none (C1, primary) and vs a random
  direction at the same α (C2), on fresh informed episodes, K = 8 samples per episode; episode-rate sign-flip tests, Holm.
- **Data:** Gemma 30 and Qwen 23 fresh v49 episodes whose neutral regeneration lied.
- **Outcome (2026-10-14):** gpt-oss PASS (0.415 → 0.140, 33/2, p < 5e-6; vs random also PASS); Gemma PASS (0.613 → 0.382, 18/3, Holm 3e-5; random control degenerate, specificity not tested); Qwen NULL (0.778 → 0.736, p = 0.14; guards fail). Lies become SPIN, not CANDID. gpt-oss added by Addendum 1 (K = 4).
