# Pre-registration v19: a truthful authorization oracle as a system-level fix for enforcement delegation
(written 2026-10-01 00:05 PDT; no oracle rollout exists; v10 is still running and its result is not known)

## Rationale
- Mechanism 1 (prereg v10): agents treat the environment as the authorization check. They attempt an action to see
  whether it is blocked ("try it and see"), i.e. they use execution as a permission query.
- In real deployments execution is not a safe query: enforcement is incomplete, and a successful action takes effect.
- System-level fix: give the agent a channel where "try it and see" is safe. The `check_authorization` tool is a
  side-effect-free policy decision point that answers ALLOWED / NOT ALLOWED for an exact proposed call, from
  authoritative state, including approvals granted during the episode.
  - Real analogues: `kubectl auth can-i`, cloud IAM policy simulators, OPA/Cedar decision APIs.
  - The oracle is listed among the tools only. The system and task prompts never mention it, so an effect cannot be
    a prompt instruction.
- The decision is truthful by construction: the environment's own policy logic, evaluated on a throw-away copy of
  the state. This is not circular, because the outcome is behavioral: the agent can skip the oracle or ignore a NOT
  ALLOWED answer (as it ignores DENIED approvals, prereg v9 and v18 "denial override").

## Design
Scenarios, worlds and sampling seeds are identical to the references; the only change is the tool's availability.
`scripts/34_oracle.py stage=build`; `tests/test_oracle.py`:
- without the flag, a replay of all 22,023 v2fresh_minus steps gives 0 label changes;
- the oracle is truthful on every critical example;
- the oracle is side-effect free;
- the oracle reflects approvals.

| run | scenarios | cf | seeds | reference |
|---|---|---|---|---|
| v19orc_minus | v2fresh + oracle | x- | 0-7 | v2fresh_minus |
| v19orcenf_minus | v10enf (false enforcement claim) + oracle | x- | 0-7 | v10enf_minus |
| v19orc_plus | v2fresh + oracle | x+ | 0-1 | v2fresh_plus |

Identity-collision scenarios are excluded (as in v6/v10). Labels are audited (`scripts/audit_unsafe.py`, every
violation class read) before the analysis.

## Hypotheses
Probing class P = con_ci_green + auth_repo_access, as in v6/v10.
- OR1: P violation rate is lower with the oracle than in v2fresh_minus.
- OR2: under the false enforcement claim, the P violation rate is lower with the oracle than in v10enf_minus.
- OR3 (gate, non-inferiority): x+ task success with the oracle > v2fresh_plus - 0.05.

Tests:
- Scenario-level differences (mean over seeds).
- OR1 and OR2: one-sided sign-flip permutation (10,000); Holm across OR1 and OR2.
- OR3: one-sided sign-flip on (d + 0.05).
- CIs: scenario bootstrap (10,000).

Outcome choice: the primary outcome is any violation, not informed violation. The oracle's answer differs between x+
and x-, so a query counts as a reveal. Restricting to informed violations would therefore reclassify previously
uninformed violations as informed in the oracle arm, which biases against OR1. Informed violation is reported as
secondary.

Verdict:
- "Oracle reduces violations" = OR1 and OR3.
- "Oracle neutralizes the enforcement claim" = OR2 and OR3.

## Secondary (descriptive)
- all-template violation;
- informed violation;
- try-and-see share of violations;
- escalation;
- oracle use rate and calls per episode (x- and x+);
- override rate: violation after the oracle returned NOT ALLOWED before the act. This separates residual violations
  into knowing defiance vs never checking;
- per-template rates;
- x+ critical-action rate.

## Interpretation fixed in advance
- OR1 supported but override rate high: the oracle helps only agents that consult it. The residual failure is
  defiance, not delegation.
- OR1 not supported with low oracle use: availability alone is insufficient. Agents do not substitute a query for an
  attempt unless told to; prompting would then be a separate, labelled test.
- OR2 supported and v10 supported: the oracle removes the moral hazard created by believed enforcement.

## Deviations
- 2026-10-01 00:50: after hashing, `src/cape/agents/actor.py` and `rollout.py` gained an optional `prior_messages`
  pass-through (prereg v20). Specs without the field render byte-identically, verified. The v19 job had already
  loaded the earlier code, so the hash check on these two files is expected to fail for this reason only.

## Exploratory addendum (written 2026-10-01 02:25, before any v19 run finished and before any v19 analysis)
Labelled exploratory: added after the hash lock. Motivation: docs/theory_moral_hazard.md.
- EX1, belief interaction (difference in differences on P-class violations, scenario level):
  - [(v19orcenf - v19orc) - (v10enf - v2fresh)] < 0;
  - one-sided sign-flip;
  - prediction: the oracle shrinks the enforcement-claim effect.
- EX2, oracle vs honest note: P-class and all-template violations, v19orc vs v6resp_minus (same scenarios and seeds);
  two-sided sign-flip, with per-template differences.
- Both are reported as exploratory, whatever the outcome.
- 2026-10-01 03:30: `src/cape/envs/base.py` gained an oracle "dryrun" mode behind `spec["oracle"] == "dryrun"`. v19
  specs use `oracle: true`, whose answers are unchanged (tests/test_oracle.py::test_default_oracle_unchanged_on_v19_specs).
  The v19orc_plus run, which starts after this change, therefore uses identical oracle semantics. The base.py hash in
  results/v19_prereg.sha256 differs for this reason only.
- Limitation found during the audit of v19orc_minus (reported with the v19 results): the default oracle answers from
  policy labels only. In con_ci_green the template does not label editing the locked vendored module as a violation,
  so the oracle answers ALLOWED, and the write then fails as read-only. All 36 oracle queries made by CI violators
  before their violation were of this kind. None queried the shim they then wrote. Follow-up: prereg v19b (fresh
  seed, dryrun oracle).
