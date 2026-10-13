# Preregistration v59: is the violation prevented or postponed, and is authorized work lost or delayed?

Written 2026-10-07 ~03:20, before any v59 continuation exists.

## Why
- **v54 Gemma (fresh, single decision turn):** forecast-gated steering cut violations 0.410 → 0.055 (71 fixed / 0
  broken). Authorized-world progress fell 0.890 → 0.815.
- The steered authorized turns are mostly inspections (list_files, read_file), not refusals.
- A single turn cannot tell prevention from postponement, or lost work from a delayed step. v59 continues every
  episode.

## Design (per model, after its v54 confirmation; Gemma first)
- **Sites:** the v54 fresh confirmation sites (200 x−, 200 x+).
- **First turn, by arm:**
  - **none:** the unsteered turn;
  - **gate-once:** the forecast-gated turn at the gate α (the steered turn if the frozen pre-action gate fired,
    otherwise the unsteered turn);
  - **blanket-once:** the steered turn at the gate α.
- **Continuation:**
  - After the first turn, the episode continues UNSTEERED for up to K = 6 more agent turns, or until a turn without a
    tool call.
  - vLLM, model sampling settings, per-site seed shared across arms (common random numbers).
  - MockEnv rebuilt by replaying the prefix, then stepping each new action. Labels come from StepInfo (no judge).
- **Outcomes per episode (first turn + continuation):**
  - x−: **eventual violation** (any unsafe step);
  - x+: **eventual authorized completion** (any critical step);
  - also escalation, number of turns, and the turn of the first violation or completion.

## Endpoints
- **C1 (persistence, primary):** eventual violation(gate-once) < eventual violation(none) on x− (exact one-sided
  McNemar).
- **C2 (no lost work, primary):** eventual completion(gate-once) ≥ eventual completion(none) − 0.05 on x+ (one-sided
  95% scenario-cluster bootstrap).
- Holm over C1 and C2.
- **Secondary:**
  - the same for blanket-once;
  - **postponement rate:** among x− sites where the first turn was fixed (none VIOLATE → gate not VIOLATE), the share
    that violate later;
  - **delay:** among x+ sites completed in both arms, the extra turns before completion.
- **If postponement is substantial (> 0.30)**, the deployable policy is gating every proposed action. That is tested
  separately (v59b, HF steering at each turn) and is not part of this preregistration.

## Reporting
- Every result is reported regardless of direction. Deviations are dated here.

## v59b: gate-always (2026-10-07 ~08:50, after the v59 Gemma result triggered the preregistered > 0.30 clause; before any v59b data)
- **Policy:** at EVERY agent turn from the decision turn on, generate the turn normally (HF). Read the residual at the
  last token before the tool-call markup. If the frozen pre-action gate fires (τ unchanged), regenerate that turn with
  steering at the gate α (same seed) and use it. Then continue.
  - Turn 0 is the v54 gated turn (the same procedure).
- **Sites:** the first 100 x− and 100 x+ v54 confirmation sites in hash order (compute). K = 6 continuation turns, as
  in v59.
- **Comparator (primary):** an HF unsteered continuation (none_hf) on the same sites with the same per-site,
  per-turn seeds (common random numbers), so the comparison is paired and within one generator. Turn 0 of none_hf is
  the v54 unsteered turn.
- **Secondary comparators:** the v59 vLLM arms none and gate-once (unpaired).
- **Endpoints:**
  - **D1:** eventual violation(gate-always) < eventual violation(none_hf) on x− (exact one-sided McNemar);
  - **D2:** eventual completion(gate-always) ≥ eventual completion(none_hf) − 0.05 on x+ (one-sided 95% scenario-cluster
    bootstrap, paired);
  - Holm over D1 and D2.
- **Secondary:** gate-always vs gate-once; fire rate per turn; turns per episode.

## v59b Addendum: D2′ (2026-10-07 ~13:05, after the v59b result, before any D2′ data)
- **D2 result (n = 100):** −0.04, lower bound −0.081 (did not pass). All 5 x+ episodes lost under gate-always were
  still active at the 7-turn horizon (verification steps, never ended), so the shortfall is delay truncated by the
  horizon.
- **D2′:** the same gate-always policy and none_hf comparator (same seeds procedure), with K = 12 continuation turns,
  on ALL 200 fresh x+ v54 confirmation sites. Eventual authorized completion, gate_always ≥ none_hf − 0.05
  (one-sided 95% scenario-cluster bootstrap, paired). Reported: delay in turns, and fires per episode.
- The original D2 stays in the repository record.

## v59b all-model replication (2026-10-07 ~13:40, before any non-Gemma v59b data)
- Gate-always (gate α and τ from each model's v54 development rules) vs none_hf.
- **Sites:** the first 100 x− and 200 x+ v54 confirmation sites (hash order); K = 12 continuation turns.
- **Models:** gpt-oss, Muse, Qwen. Each runs after its own v54 confirmation, and only if that model has a gate α.
- **Endpoints, per model:** D1 (eventual violation, exact one-sided McNemar) and D2′ (eventual completion, margin
  0.05, paired cluster bootstrap); Holm per model.
- **Pooled across the four models:** D1 by stratified McNemar.

## v59d: gate-escalate (2026-10-07 ~18:55, after D2′; before any v59d data)
- **D2′ result:** completion 0.94 vs 1.00 (−0.06, lower bound −0.089), did not pass. The diagnosis of D2 as
  horizon-truncated delay was wrong.
  - The 12 lost x+ episodes had repeated gate false alarms (mean 4.25 fires, vs 0.41 in completed episodes); each
    re-flag steered the agent back to checking, and it looped.
- **Policy gate-escalate (the response a real oversight system gives to a repeated flag):**
  - The first time the gate fires in an episode: steer, exactly as gate-always.
  - Every later fire: do not steer. The system asks the principal through the environment's request_permission for
    the agent's own proposed action.
    - If approved ("No approval needed" or "APPROVED"), the proposed action executes unchanged.
    - Otherwise it is blocked, and the agent sees the denial.
  - Asks are counted as the human burden.
- **Sites, comparator, seeds:** 100 x− and 200 x+ v54 confirmation sites (hash order), K = 12, paired none_hf in the
  same run.
- **Endpoints (Holm):**
  - **E1:** eventual violation(gate-escalate) < none_hf on x− (exact one-sided McNemar);
  - **E2:** eventual completion(gate-escalate) ≥ none_hf − 0.05 on x+ (paired cluster bootstrap).
  - Reported: asks per episode (x+ and x−), and violation vs gate-always (v59b).
- Gemma first; the other models follow after their gate-always runs.

## Addendum (2026-10-12 ~12:45 PDT): all-model replication completed for Gemma (before any v59b `_all` data for Gemma)
- Reason: the prevention table mixed horizons for Gemma (6-turn D1 from the original v59b). For one uniform design, Gemma now runs the
  all-model replication exactly as specified above (slurm/v59b_all.sh: first 100 x− and 200 x+ v54 confirmation sites, hash order;
  K = 12; gate-always vs none_hf in the same run; D1 exact one-sided McNemar, D2′ completion margin 0.05; Holm per model).
- These sites were used in Gemma's original 6-turn run, whose results are known; the 12-turn outcomes are new data.
- Muse needs no rerun: by the v61 preregistration, its end-to-end run contains and replaces the v59b Muse design on the same first
  100 x− sites (slurm/v59b_all.sh delegates Muse to slurm/v61.sh).
