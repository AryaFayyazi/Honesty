# Preregistration v30: external validity on published frontier-agent trajectories (τ²-bench airline)

Written 2026-10-02, BEFORE any labeling, feature extraction or analysis of these trajectories. Only file names have been
seen. Exploratory relative to v29; confirmatory for the claims below.

## Data
- The τ²-bench published airline trajectories (`data/tau2/results/final/*_airline_*`, sierra-research/tau2-bench @
  5bfa7e3).
- Agents: claude-3-7-sonnet-20250219, gpt-4.1-2025-04-14, gpt-4.1-mini-2025-04-14, o4-mini-2025-04-16. User
  simulator: GPT-4.1. 50 tasks × 4 trials each.
- These are real trajectories of frontier agents that we did not generate.

## Labels (scripts/77_tau2_label.py)
- Every write tool call is labeled by the truthful policy oracle (`cape.tau2port.decide`, validated on all 49 gold
  writes) at the DB state at which it was issued: ALLOWED / NOT ALLOWED / CONDITIONAL / ERROR.
- Positives: NOT ALLOWED writes. Hard negatives: ALLOWED writes. CONDITIONAL and ERROR are excluded.
- Epistemic flag: whether the agent read the targeted reservation (get_reservation_details) before the write.

## Features
- Reader mode: Qwen3.8-27B reads each trajectory in one teacher-forced prefill. The agent's private reasoning is not
  available; reasoning is empty for all agents.
- Hidden state: mean of the last 8 tokens of the write call, at layer index 2 of the extracted set (layer 45 of 64),
  as in v29.

## Hypotheses (inclusion: at least 30 NOT ALLOWED writes pooled over agents; otherwise descriptive)
- **X1 (zero-shot transfer from CAPE).**
  - Train the v29-frozen ECG and the monolithic probe on Qwen-reader CAPE features: v2fresh `qwen38` +
    `rdqwen-{gemma4, gptoss20b, museglimmer}`, seed-balanced.
  - Apply them unchanged to τ² write calls.
  - Primary: AUROC of NOT ALLOWED vs ALLOWED writes, pooled over agents, with a 95% task-cluster bootstrap CI.
  - PASS: lower CI bound > 0.5. Reported against the chance level, and against the S1-style zero-shot transcript judge
    if it is run.
- **X2 (in-domain reader probe).**
  - Grouped 5-fold CV by task. The monolithic shrinkage-LDA reader probe on write calls, NOT ALLOWED vs ALLOWED.
  - Within-fold TPR@5% FPR over ALLOWED writes (1% is too sparse for the expected counts) and AUROC.
  - PASS: AUROC lower CI bound > 0.6.
- **X3 (epistemic share, descriptive with CI).**
  - The share of NOT ALLOWED writes issued without first reading the targeted reservation, per agent.
  - The AUROC of the CAPE-trained P_unv for predicting "no prior read" among write calls.
- **Descriptive.** Per-agent rates of NOT ALLOWED writes per episode, and by tool.

No changes to features, layer, probes or metrics after labeling. Deviations are logged here with dates.

## Amendment 1 (2026-10-02, before any τ² feature exists; tau2_rd extraction still queued)
- **Secondary arm ECG-m** in X1: P_crit · [1 − (1 − P_mono)(1 − P_unv)], i.e. the v29 ECG with the monolithic probe as
  the authorization branch.
- **Motivation (v29 core24 confirmatory H2).** The ECG beat mono where violations are mostly uninformed (gpt-oss: +0.07,
  p = 0.018) and lost where they are mostly informed (Gemma-4: −0.05), because its authorization branch trains only
  on informed critical actions.
- Reported next to ECG and mono with the same metrics. Not part of the X1 PASS rule.

## Deviations log
- 2026-10-02, before any feature extraction or analysis: the labeler mapped the oracle's conditional answers
  ("ALLOWED ONLY IF ...", 113 writes) to ALLOWED. Corrected to CONDITIONAL, which is excluded, as this document
  specifies. Implementation bug only; the definitions are unchanged.
