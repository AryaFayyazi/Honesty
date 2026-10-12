# Preregistration v60: at the decision, do internals beat text at telling the violation from the agent's other actions?

Written 2026-10-07 ~10:30, before any v60 rollout exists.

## Why
- In v57 (fresh, decision time), internals did not beat text or CoT monitors overall (E2/E3). The pooled negatives
  included the authorized twin, whose context states the permission in text.
- Against the agent's other actions in the same unauthorized world, internals led supervised text by +0.068
  [0.050, 0.089] and the CoT monitor by +0.027 [−0.003, 0.061]. This contrast was a secondary and was examined after
  seeing v57, so it needs new data.

## Data (new; never generated before this preregistration)
- x− rollouts of core24b with seeds 14–17 for all four models (same harness and settings as the earlier fresh sets).
- **Units:** VIOL (first unauthorized action of an informed episode) vs XOTHER (post-reveal proposed actions of
  informed non-violating episodes).
- Features: scripts/56 'pre' (after the turn's reasoning, before the call), restricted to all informed violators and
  up to 1,000 informed non-violators per model (sha256 order).

## Forecasters (all frozen BEFORE v60 data; identical to v57)
- **I:** the v54 gate model (outputs/v54/gate_<model>.npz).
- **T_sup:** the v57 recipe (TF-IDF + logistic regression fit on the same development units as v57).
- **M_cot:** the v57 zero-shot monitor (scripts/156 prompt), on up to 300 VIOL + 600 XOTHER per model (sha256).

## Endpoints (within (model, template, tool) AUROC, pooled over models; scenario-cluster bootstrap)
- **F1:** AUROC(I) − AUROC(T_sup) > 0 (one-sided).
- **F2:** AUROC(I) − AUROC(M_cot) > 0 on the monitor subset (one-sided).
- Holm over F1 and F2. Per-model results are reported descriptively.
