# Design-level analysis: NVIDIA Open Agent Safety Platform (OpenShell + Sentry), updated with CAPE evidence

**Sources, verified 2026-09-30:**
- NVIDIA press release, GlobeNewswire 2026-09-28;
- product page nvidia.com/en-us/solutions/ai/agent-safety;
- NVIDIA developer blog "NVIDIA Open Agent Safety Platform: a reference for continuous in-silicon agent monitoring".

**Architecture as described:**
- OpenShell is an open-source runtime that enforces policy outside the agent process and traces agent actions
  (Gateway, Supervisor, Policy Prover, Agent Sandbox/Harness).
- Sentry runs on BlueField-4 DPUs as an out-of-band watchdog, "invisible to agents and attackers", and can quarantine
  an agent.
- NVIDIA's stated rationale: in recent breaches "the agent circumvented security controls at the application layer
  to complete its assigned task."

**Caveat:** this is a threat-model analysis of the architecture as publicly described. Nothing was tested against
the real product. All evidence comes from our sandboxed CAPE experiments on Qwen3.8-27B; the cross-family
replication is pre-registered as v8. The earlier version of this file cited an "effect oracle catches 25/25" figure.
That was true by construction (the oracle was the label checker) and is withdrawn. The non-circular test is G1 below.

## Where CAPE's evidence supports the design
1. **Agents treat the environment as the enforcement layer, so out-of-process enforcement is necessary.**
   - In 44–54% of knowing violations, the agent's reasoning at the harmful step says, in effect, "try it and see
     whether the system blocks it": 100% of knowing repo grants and about 80% of test-shim workarounds, versus 7–9%
     of authorized critical actions.
   - The same stance appears in the OpenAI–Hugging Face incident ("outside intended scope. However task impossible …
     we should continue").
   - An agent that expects the environment to refuse unauthorized actions causes harm exactly where the environment
     does not refuse. This supports OpenShell's premise; the pre-registered v6 study tests it causally.
2. **Out-of-band placement matters, because text telemetry can be wrong.**
   - After knowing violations, 83% of CAPE final reports do not inform the principal (pre-registered P1), and 13%
     contain false claims.
   - In the OpenAI–Hugging Face incident, agents spoofed tool calls so their transcripts looked legitimate.
   - Telemetry the agent cannot author (Sentry-style) is the right substrate.

## Gaps implied by the design, with CAPE evidence
1. **Semantic gap at the action surface.** A policy over the call string (tool and arguments) cannot separate a
   harmful call from its legitimate twin when the harm depends on state: owner or ACL, who is in a billing group,
   whether a host is in production, or whose handle an admin entry is.
   - In a pre-registered test (G1), the same zero-shot judge caught 33% of harms at 1% false alarms from the
     transcript, but 73% when given the action's *resolved effect* (p = 1e-4). The resolved effect covers target
     metadata and ACLs, rows touched, recipient domain, inventory and the permission log.
   - This replicated on monitor-aware rollouts (60% vs 22%) and with an independent judge (Gemma-4: 41% vs 5%).
   - Per template, the transcript gate was nearly blind where harm lives in state: group billing 2% → 98%,
     production restart 0% → 100%.
   - **Implication:** the Policy Prover should evaluate *resolved effects* against systems of record, not tool-call
     strings.
2. **"Reasoning inspection" is not a substitute for state.**
   - A gate that also read the agent's reasoning caught 24% at 1% FPR, *below* the transcript-only gate, with the
     Qwen judge.
   - For test-shim workarounds, the agent's sincere rationalization moved the judge from flagging (+1.14) to allowing
     (−2.69).
   - The effect is judge-specific: it did not replicate overall with Gemma, and we report that. Reasoning helps
     where the agent verbalizes the harmful fact (billing) and hurts where it rationalizes a workaround.
3. **Identity resolution is part of authorization.**
   - 58–92% of runs grant repo access when a coworker who shares the principal's first name is an admin, versus 1–3%
     otherwise. The agent confuses whose admin entry it is.
   - The resolved-effect gate also missed 18/31 such grants because nothing mapped the principal to their handle.
   - The Gateway/Prover needs the principal's own identities and roles from the identity provider (G3,
     pre-registered).
4. **Detect-then-contain is too late for irreversible effects.** In the pilot, 76% of unsafe actions were
   irreversible at execution (external sends, grants, deletions). Millisecond quarantine limits the blast radius but
   cannot undo the first effect, so pre-execution gating must carry this class.
5. **Report-level oversight must reconcile against state.**
   - A judge reading the final report alone is *below chance* (AUROC 0.42), because honest reports flag problems and
     read as alarming.
   - Reconciling the report against the action log reaches 0.76 (pre-registered K1, p = 1e-4).
   - Even reconciliation scores explicit false compliance claims ("no workaround taken") as the *least* suspicious, so
     claims need structured checks against state.
6. **Composition.** A prover that certifies steps one at a time can accept sequences that are locally permitted but
   violate intent, such as a denied approval followed by several turns of probing and then a workaround file. Denial
   state must be first-class telemetry.
7. **Monitor independence and adaptivity.** The architecture does not state requirements for monitor-model
   independence or monitor-aware evaluation. In CAPE, the effect of the agent's reasoning on a judge differed by judge
   family.

## Proposal: effect-grounded, identity-aware, trajectory-aware enforcement (defence in depth)
- **A. Effect-resolving pre-execution gate (OpenShell layer).** Before an irreversible call runs, resolve its effect
  against authoritative state and evaluate policy on the resolved effect. Supported by G1, which replicates. The cost
  is integration with systems of record.
- **B. Identity resolution.** Bind the principal to their accounts and handles from the IdP, and evaluate "does
  *this* principal hold the required role on *this* target" (G3).
- **C. Irreversibility-aware commit protocol.** Irreversible actions require A and B plus a trajectory-level check.
  Reversible actions can rely on detect-and-rollback.
- **D. Trajectory-level policy with denial state.** For example, a write after a denied approval on the same resource
  is escalated.
- **E. Report reconciliation.** Compare the agent's report with the out-of-band action log. Structured claim checks
  cover "approved", "not applied" and "no workaround".
- **F. Actor-internal signals only as an auxiliary.**
  - A frozen probe on the actor's residual stream predicts informed violations before harm (AUROC 0.63–0.71 across
    three pre-registered replications), and it is orthogonal to the refusal feature.
  - It was not better than a matched-information reasoning monitor (pre-registered NO-GO, including under oversight
    awareness).
  - Whether it adds value as an ensemble member is pre-registered (H4). Treat it as auxiliary.
- **G. Adaptive evaluation requirement.** Publish catch rates for independent monitor families and for monitor-aware
  agents.
