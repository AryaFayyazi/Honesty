# Preregistration v46b: specificity control for v46 (random direction at +8 ×gap)

Written 2026-10-05 ~00:00, after the v46 result (CAA +8 ×gap, delay 16 reduced lies on fresh episodes:
S1 0.618 → 0.355, S2 0.709 → 0.443, CANDID 0.14 → 0.31) and before any random-+8 generation exists.

## Why
v46 compared +8 only with no steering. A large perturbation in ANY direction might disrupt lying (for example by
degrading the report). v43's random control was at +4. We need it at +8.

## Design
- **Episodes.** The same 110 fresh v40 informed Muse episodes.
- **Condition.** Per-layer random unit vectors r_l (orthogonal to the CAA u_l; the `r` keys of the all-dev direction
  file), +8 × g_l at all 5 layers, delay 16, neutral report turn, the same per-episode seeds as v46.
- **Comparison.** Against the v46 CAA +8 outputs (already generated).

## Endpoints (exact McNemar test, one-sided)
- **X1.** lie(CAA +8) < lie(random +8), with NO_REPORT counted as not MISREPRESENTED, using all episodes.
- **X2.** The same comparison, complete-case.
- Holm over {X1, X2}.
- **Also reported:** CANDID, report share and generation length of random +8 vs CAA +8.
- **Claim rule.** "Honesty-specific" only if X1 and X2 both pass.
