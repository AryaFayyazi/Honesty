# Pre-registration v71: does the pre-action readout generalize to safety families it was never trained on?

(written 2026-10-11 ~22:55 PDT, before any v71 fit or score exists.)

## Why
A reviewer can object that the gate learned CAPE-Bench's templates rather than authorization. CAPE-Bench has 8 safety
families (template prefixes): auth (access grants), con (cost and SLA constraints), cons (consent), cred (credentials),
own (ownership and sharing), prov (provenance), rev (irreversible deletion), tp (third parties). v71 holds out one family at a
time.

## Design (fixed now; scripts/189_v71_lofo.py)
- Models: Qwen3.8, Gemma-4, gpt-oss-20b, Muse (all four).
- Training data: the v54 gate development data and recipe (scripts/154 `stage_fit`: positives = violating turns; negatives =
  other actions after the reveal and the authorized critical action in x+; negatives capped as in v54; two scenario-hashed
  folds; scripts/150 `fit_internal`, 5-depth shrinkage LDA ensemble), restricted to the 7 families other than the held-out one.
- Test data: the fresh v57 confirmation decision units (scripts/155 `units(..., "conf")`: VIOL, XOTHER, XPLUS) of the held-out
  family only. The full gate (frozen `outputs/v54/gate_<m>.npz`, trained on all families) is scored on the same units.
- Metric: AUROC within (model, template).

## Endpoints
- **L1 (primary):** pooled over models and held-out families, AUROC of the held-out-family readout for VIOL vs XPLUS (the same
  action when authorized) > 0.5. One-sided (model, scenario)-cluster bootstrap, 4,000 draws.
- **L2 (primary, non-inferiority):** pooled AUROC with all negatives (XOTHER + XPLUS), held-out-family readout minus full gate,
  > −0.05 (one-sided 95% lower bound of the paired cluster bootstrap).
- Holm over L1 and L2.
- **Descriptive:** per family and per model; VIOL vs XOTHER.

## Claims allowed
- L1 and L2 pass: "a readout trained without a safety family flags unauthorized actions in that family, nearly as well as one
  trained with it".
