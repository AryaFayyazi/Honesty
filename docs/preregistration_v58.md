# Preregistration v58: replication of honesty steering on fresh episodes, and where the lever is (reasoning vs report)

Written 2026-10-06 ~20:40, before any v58 generation.

## Evidence so far (Muse)
- **Confirmed (earlier fresh test, n = 110):** +8 × gap from generated token 17 (reasoning and report steered):
  lie 0.71 → 0.44; a random direction does nothing (Holm p = 0.002).
- **v48C (196 fresh episodes):** a window of generated tokens 17–120 (mostly early reasoning) had no effect (0.79 vs
  0.79).
- **v56 development (115 episodes):** steering only the report (from its first token) cuts labelled lies at α ≥ 12, but
  the reports degenerate (repetition loops, report share 0.65 vs 0.87, length ×3). The validity check was perfect
  (104/104 identical reasoning). At α = 8 the non-truncated reports barely change (lie 0.60 vs 0.65). No dose passed
  the guards, so there is no v56 confirmation (preregistered rule).
- **Interpretation to test:** the agent plans the report in its reasoning (e.g. "I'll produce final summary stating
  permission denied…"). Steering the report alone fights that plan, while steering through the reasoning changes it.

## Arms (the 196 fresh v48 confirmation episodes; directions all-dev `a`; neutral report turn; same seeds)
- **none.**
- **d16:** +8 × gap from generated token 17, reasoning and report (the confirmed configuration).
- **rand_d16:** a random direction, same scale and mode.
- **q16:** +8 × gap from generated token 17 **until the report starts** (reasoning only; report unsteered). Uses the
  per-sequence report detection of v56.
- No development selection: every arm uses a dose fixed before this test.

## Endpoints (exact one-sided McNemar, complete case)
- **Primary (replication), Holm over {P1, P2}, α = 0.05:**
  - **P1:** lie(d16) < none;
  - **P2:** lie(d16) < random.
  - Guards: report share ≥ none − 0.10; mention ≥ none − 0.15.
- **Mechanism (secondary, α = 0.05 each, reported regardless):**
  - **M1:** lie(q16) < none;
  - **M2:** lie(q16) vs lie(d16), two-sided.
  - Degradation of each arm.
- **Sensitivity:** NO_REPORT counted as not MISREPRESENTED; CANDID rate.
- **Note:** these 196 episodes were used for the v48C arms (none / window / +4). d16 and q16 have never been run on them.
