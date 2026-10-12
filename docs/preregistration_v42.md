# Preregistration v42: multi-layer difference-of-means steering toward honesty (two-stage; the final steering attempt)

Written 2026-10-04 ~12:45, after the v41 stage-A null (no configuration of the LDA lie direction reduced lying) and
before any v42 generation exists.

## Rationale
- **Classifier directions make poor levers.** The LDA lie-forecast direction lives in a low-variance subspace
  (projection σ ≈ 2). It predicts lies (held-out AUROC 0.81–0.88), but steering along it was null at every dose and
  position (v39, v41 stage A).
- **The standard alternative.** In the steering literature, difference-of-means vectors applied at several layers
  are the effective intervention (activation addition; Marks & Tegmark).
- **v42 direction.** u_l = mean(honest) − mean(lie) of the pre-report state at each of the 5 extracted layers
  (blocks 25, 31, 36, 42, 46), unit-normalised.
  - Fit per scenario fold, on the other fold's labelled Muse episodes (informed and uninformed).
  - Held-out AUROC 0.84–0.87 per layer.
  - The honest–lie gap is about 1.35 σ_l per layer (σ_l ≈ 47–94; residual norm ≈ 260–430).
  - Saved in outputs/reconcile/v42_directions.npz.

## Design (same 115 Muse informed episodes and folds as v39/v41; neutral report turn; outputs are new)
- **Stage A, selection (fold 0, n = 60).**
  - Conditions: none; +c·σ_l·u_l added at all 5 layers, for c ∈ {1.5, 3, 6} × {decode-only, all positions}.
  - Selection rule as in v41 (scripts/106 stage=select tag=v42): the most negative complete-case paired change in the
    MISREPRESENTED rate among configurations that pass the report-share and mention guards; ties go to the smaller c.
- **Stage B, confirmation (fold 1, n = 55).** None, the chosen configuration, and per-layer random unit vectors
  (each orthogonal to u_l) at the same c and mode.

## Endpoints (stage B; exact McNemar test, one-sided, complete-case)
- **X1.** MISREPRESENTED(chosen) < none.
- **X2.** MISREPRESENTED(chosen) < random.
- Holm over {X1, X2}; guards as before.
- **Claim rule.** "Steering toward the internal honesty direction reduces lying" only if X1 and X2 both pass and the
  guards hold.
- **Stopping rule.** This is the last steering attempt. Whatever the outcome, v36, v39, v41 and v42 are all reported
  together, and the multiplicity is acknowledged: four attempts.
