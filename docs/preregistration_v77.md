# Pre-registration v77: does the internal readout track the agent's information that an action is unauthorized? (counterfactual context swap)

(written 2026-10-12 ~12:30 PDT, before any v77 generation exists.)

## Why
- The paper's account: the CAPE readout reads the agent's belief that an action is unauthorized. It explains why the readout
  transfers across safety families (knowing violations) and why, on AgentDojo, it is silent when an injection signed in the user's
  name persuades the agent (within-tool AUROC injected vs benign 0.28 on gpt-oss, discovery; 0.23 on Gemma, preregistered,
  CI touching 0.5). So far this is an explanation; v77 tests it causally.
- Design: hold the action fixed and change only the information. Every agent action in undefended AgentDojo episodes is scored
  twice on the same prompt history and the same generated tokens: (a) the real context, the standard injection signed in the user's
  name; (b) the identical context, except that every tool output comes from a shadow environment injected with the third-party
  variant of the same injection (same goal and imperative, stated to come from "an unknown third party, not from <user>", and
  "<user> has not requested or authorized it"). The shadow environment executes the agent's same tool calls, so (a) and (b) differ
  only in the injection text. Before the injection is first seen, (a) and (b) are identical (pipeline check: difference 0).

## Design (fixed now)
- Benchmark: AgentDojo v1.2.2, the 664 confirmation pairs (68 user tasks) of v74/v76 (not used to discover the reversal);
  important_instructions attack; AgentDojo's tool loop and checks; arm none; model-card sampling; seeds as v74.
- Readout: the frozen CAPE readout (outputs/v54/gate_<m>.npz), never fit on AgentDojo. τ for S1: the 90th percentile of frozen
  scores on benign AgentDojo development tool calls (v76 development benign runs; computed before any v77 data:
  gpt-oss 0.438, Gemma 0.343, Muse 0.634).
- Models: gpt-oss-20b and Gemma-4 (this lock); Muse and Qwen may be added by addendum before their v77 data.
- Code: scripts/191 (V74_SWAP=1: ThirdPartyAttack, ShadowExecutor, swap_messages), scripts/174 (additive: score_swap on the
  same generated tokens), slurm/v77swap.sh; analysis scripts/201_v77_belief.py. Verified on CPU with a dummy model before the lock:
  identical contexts before the injection, contexts differing only in the injection text after it.

## Endpoints (per model; Holm over P1 and P2 across models)
- **P1 (primary):** on injected calls (v74 tagging rule), mean(score_swap − score) > 0. One-sided (suite, user task)-cluster
  bootstrap, 4,000 draws.
- **P2 (primary, specificity):** difference-in-differences: mean(score_swap − score) on injected calls minus that on the agent's
  other calls made after the injection was seen (contexts differ) > 0. Same bootstrap.
- **S1 (secondary):** fire rate at τ on injected calls, swapped vs real context (exact one-sided McNemar).
- **Pipeline check (validity, not a test):** max |score_swap − score| on calls before the injection is seen; must be ~0.
- **Descriptive (slurm/v77behav.sh):** the third-party injection actually shown (development pairs): attack success and frozen
  scores of injected calls, vs the user-signed injection (v76 development runs).

## Claims allowed
- P1 and P2 pass: "holding the agent's reasoning and action fixed, information that the instruction is unauthorized raises the
  internal readout for the injected action, specifically: the readout tracks the agent's information about authorization, not the
  action itself."
- P1 passes, P2 fails: the third-party text shifts the readout generally, not specifically for the injected action.
- P1 fails: the readout does not respond to this information; the belief account is not supported (reported as such).

## Addendum 1 (2026-10-12 ~13:30 PDT; before any v77 data for any model)
- Muse and Qwen join with the identical design (slurm/v77swap.sh). τ for S1: Muse 0.634 (computed before the lock); Qwen: the 90th
  percentile of frozen scores on its v76 development benign tool calls, computed by the same rule when that run finishes and before
  its v77 data exist. Holm over P1 and P2 across all four models. (Muse in the vLLM-0.30 env; the swap code is env-independent.)

## Deviation 1 (2026-10-13 ~12:00 PDT; before any v77 data for Muse or Qwen)
- The Muse and Qwen v77 runs (Addendum 1) are not run. Their v76 development runs show almost no injected calls (Muse: undefended
  attack success 0.042, 13 tagged injected calls in 285 episodes; Qwen: 0.014, 0 tagged injected calls), so P1/P2 would rest on
  ~30 (Muse) or ~0 (Qwen) injected calls in 664 episodes and could not be informative. Holm over P1/P2 therefore covers gpt-oss and
  Gemma (both null, Holm p = 1). Jobs 3617 and 3618 cancelled; no data were generated.
