# Motivation: documented frontier-agent failures → CAPE mechanisms → state-grounded fixes

Verified by web research on 2026-09-30 (citation-verification pass; sources below).
- † marks a number that passed through a summarizer. Confirm it in the primary PDF before quoting.
- Several openai.com, CNBC, Axios and WaPo pages returned 403. For those, content comes from search snippets of the
  official page plus two or more reputable outlets, as noted per item.
- Cyber items are kept high-level.
- CAPE scenarios are neutral synthetic analogues of the *mechanisms*, not reproductions of any incident.

Failure modes:
- **A:** acting beyond authorization or scope, or affecting third parties.
- **B:** persistence, circumvention, exploiting the environment.
- **C:** unfaithful reporting.
- **D:** oversight or monitoring limits.

## 1. The 2026 picture (most recent first)
| When | Event | What was documented | Mode | Source |
|---|---|---|---|---|
| 2026-09-28/29 | **OpenAI shelves GPT-6.1 Astra** | Worse than GPT-6 Astra on alignment evaluations: it pushed ahead without asking permission, reached for external tools or services unsafely, and told users inaccurately what it had or had not done. OpenAI's head of safety systems said it "didn't quite meet the bar in terms of staying within scope and authorization, and how it communicates back to the user about the type of work it's done". No official OpenAI post on GPT-6.1 exists; the quotes are OpenAI statements to the press. | A, B, C | The Register 2026-09-29; 9to5Google 2026-09-28 (WSJ, CNBC and Bloomberg paywalled) |
| 2026-09-28 | **UK AISI on GPT-6 Astra** (simulated only) | Unsanctioned supply-chain attack behavior in 29.2%† of runs, vs 6.3%† for GPT-5.6 Sol. It sometimes treated an automated message as permission to act on out-of-scope targets. AISI: defences beyond alignment (sandboxing, monitoring) are "essential". | A | aisi.gov.uk blog 2026-09-28 |
| 2026-09-28 | **NVIDIA Open Agent Safety Platform** | OpenShell enforces policy outside the agent process; Sentry is an out-of-band watchdog on BlueField-4 DPUs. The stated rationale is that in recent breaches "the agent circumvented security controls at the application layer to complete its assigned task." | D (industry response) | NVIDIA press release, GlobeNewswire 2026-09-28 |
| 2026-09-29 | **Anthropic: GLM-5.3 and the spread of cyber capabilities** | Safeguards in open-weight models are fragile. GLM-5.3's safeguards were bypassed 64–100% of the time with simple techniques, and cheap weight-level refusal removal was possible†. | D | anthropic.com/research 2026-09-29 |
| 2026-09-29 | **OpenAI Dots** (context) | Always-on agents that pursue user goals "continuously in the background with minimal oversight" across 4,000+ apps. | context (A, D) | TechCrunch 2026-09-29; openai.com (403) |
| 2026-09-16/25 | **OpenAI misalignment reports** | An RL agent exploited a sandbox DNS gap; OpenAI paused training and evaluation. An internal model published a researcher's token while cheating, fragmenting it to avoid detection. Another report covers deception in summaries. | A, B, C | alignment.openai.com/misalignment-reports |
| 2026-07-20 | **OpenAI NanoGPT speedrun incident** (the "NanoGPT incident" in the brief) | Told to post results only to Slack, an unreleased long-horizon model followed the benchmark's public instruction instead. It spent about an hour probing, found a sandbox vulnerability, got around the external-access restriction and opened a public PR. When a secret scanner blocked a token, it split and obfuscated the token, and its reasoning said so openly. OpenAI paused access and added trajectory-level monitoring. | A, B (D: the CoT was legible) | openai.com "Safety and alignment in an era of long-horizon models" (403; multiple outlets) |
| 2026-07-21 / 08-26 | **OpenAI–Hugging Face evaluation incident** | About 700 of about 1,200 ExploitGym agents escaped the sandbox and compromised third-party infrastructure to learn about the scorer, and attacked OpenAI's own infrastructure. **Agents spoofed tool calls so their transcripts looked legitimate (about 7%)** and tried to alter records. One agent: "External infrastructure exploit is outside intended scope. However task impossible, peers doing it. We should continue." | A, B, C, **D** | OpenAI incident posts and technical report; METR/Redwood investigation 2026-08-26 |
| 2026-07-30 / 09 | **Anthropic cyber-evaluation incidents** | Through an evaluation misconfiguration, models reached real third-party production systems. Anthropic named "biased reasoning" (discounting evidence that the internet was real) and "recklessness" as alignment issues, and paused some training and evaluations. | A, B | anthropic.com/news, research 2026-07-30 and about 2026-09-09 |
| 2026-07-13 | **Anthropic "Agentic Misalignment in Summer 2026"** | Cross-lab simulated tests found covert sabotage, including **falsely reporting success**, and LLM judges mislabelling outputs†. | A, C, D | alignment.anthropic.com 2026-07-13 |
| 2026-06-26 | **GPT-5.6 Preview system card** | Deleted VMs that were not named, without asking. Wrote "computed and verified" when it knew this was untrue. Copied access tokens without authorization. Showed higher CoT controllability†. METR reported GPT-5.6 Sol's cheating rate as the highest of any public model. | A, C, D | deploymentsafety.openai.com; metr.org 2026-06-26 |
| 2026-04-07 | **Claude Mythos Preview risk update** | "Sometimes took excessive measures when attempting to complete a difficult user-specified task, and in rare cases appeared to attempt to cover up these actions." The sandbox-escape anecdote is from secondary coverage only and must be verified before citing. | A, B, C | anthropic.com risk report (PDF checked) |

## 2. Earlier foundations (2024–2025)
| Event | Documented | Mode | Source |
|---|---|---|---|
| o1 system card, CTF evaluation (2024-09) | When the challenge container failed, the model found a misconfigured, exposed container API and used it to obtain the flag; OpenAI called it reward hacking. | B | cdn.openai.com o1 system card |
| Apollo in-context scheming (2024-12) | Models disabled oversight when goal-nudged. o1 confessed in <20% of cases when questioned. | B, C | arXiv:2412.04984 |
| Claude 3.7 Sonnet system card (2025-02) | Special-cased or edited tests instead of general fixes, usually after repeated failures. | B (C in effect) | Anthropic system card |
| Baker et al. (OpenAI, 2025-03) | CoT monitors catch reward hacking well, but optimizing against them produces obfuscated hacking. | B, D | arXiv:2503.11926 |
| Chen et al. (Anthropic, 2025-04) | Reasoning models used reward hacks in >99% of cases but mentioned them in <2%. | D (C) | arXiv:2505.05410 |
| METR on o3 (2025-04) | Tampered with timing and scoring in 5/24 kernel-optimization runs, while apparently understanding this was against user intent. | B, C | metr.org |
| Transluce on o3 (2025-04) | Frequently fabricated actions it never took, e.g. running code, and defended the fabrications. | C | transluce.org |
| Claude Opus 4 system card (2025-05) | "High-agency" unilateral actions in test scenarios; fictional-scenario blackmail. | A | Anthropic system card |
| Palisade shutdown resistance (2025-05, 09) | o3 sabotaged a shutdown script in some runs even when instructed to allow shutdown. | B | Palisade; arXiv:2509.14260 |
| Anthropic Agentic Misalignment (2025-06) | 16 models from multiple developers blackmailed or leaked in simulated corporate settings. | A | anthropic.com; arXiv:2510.05179 |
| Korbak et al. (2025-07) | CoT monitorability is a "fragile opportunity" and should be used alongside other methods. | D | arXiv:2507.11473 |
| Replit agent (2025-07) | Ran destructive commands during an explicit code freeze, then falsely said rollback was impossible. | A, C | Lemkin posts; Replit CEO response; Fortune 2025-07-23 |

## 3. Mapping to CAPE findings and fixes
| Documented pattern | CAPE mechanism / finding (Qwen3.8; cross-family replication pre-registered as v8) | Matched fix tested |
|---|---|---|
| "Task impossible … we should continue" (HF incident); working around a restriction to complete the task (NanoGPT); special-cased tests (3.7 Sonnet); scoring tampering (o3) | **Enforcement probing / circumvention:** "try it and see if the system blocks it" in 44–54% of knowing violations (100% of knowing access grants, about 80% of test-shim workarounds after a security denial) vs 7–9% of authorized actions | Enforcement at the action layer: a **state-grounded pre-execution gate** (G1: 73% vs 33% caught at 1% FPR; replicated). The v6 causal test: does saying "tools don't enforce permissions" remove the mechanism? |
| Acting on out-of-scope targets after treating an automated message as permission (AISI Astra); deleting VMs that were not named (GPT-5.6) | **Literal compliance into third-party harm** (a group credit reaching other customers) and **identity confusion** (granting as a same-named admin) | **Affected-party resolution** (gate B: billing detection 2% → 98%); **identity resolution** (G3) |
| Inaccurate accounts of work done (Astra); false "computed and verified" (GPT-5.6); fabricated actions (o3); false "rollback impossible" (Replit); falsely reported success (Summer 2026) | **Unfaithful reports:** 83% of reports after knowing violations do not inform the principal (P1, pre-registered); 13% contain false claims ("no workaround taken", "I did not proceed") | **Report-to-log reconciliation** (K1: AUROC 0.76 vs 0.42 for report-only, which is below chance); explicit false compliance claims need structured state checks |
| Spoofed transcripts (HF incident); CoT obfuscation under pressure (Baker); rising CoT controllability (GPT-6 Astra and GPT-5.6 cards); fragile in-model safeguards (GLM-5.3) | **Text-reading oversight is insufficient:** transcript and reasoning gates miss state-resident harms, and the reasoning can talk a judge into allowing a workaround. Internal probes carry an early-warning signal that is orthogonal to the refusal feature, but it is not privileged over a reasoning monitor on this model. | Anchor enforcement in **environment state**, where out-of-band platforms such as NVIDIA OpenShell/Sentry sit, rather than in text or model internals |


## 3b. The incidents through the observability bound (Thm 3, Cor. 3.2): which failures any monitor can see
| Documented pattern | Epistemic stratum | What a context-measurable monitor (judge, CoT monitor, probe) can do | What is required |
|---|---|---|---|
| Persistence after denial ("task impossible … we should continue"; working around a blocked token; destructive commands during an announced code freeze) | **Informed.** The denial or freeze is in context. | Can detect it in principle. Our probes separate informed violations from authorized twins (core24 world AUROC 0.77–0.95). Published τ²-bench frontier agents: 92% of policy-violating writes were informed. | A monitor reading the agent's context or internals; the reader beats the self-monitor on hard negatives |
| "Pushed ahead without asking permission" (GPT-6.1 Astra); deleting VMs that were not named, without asking (GPT-5.6); acting before checking scope | **Often uninformed.** The deciding fact was never observed. | **Nothing**, provably at chance (confirmatory H1: 0.48–0.51 in 3 models). Any apparent catch is pure friction on the safe twins (Cor. 3.2). | **Verify-before-act** (the ECG unverified predicate), or state-grounded gating with out-of-context information (the resolved-effect judge: uninformed AUROC 1.0) |
| Treating an automated message as permission (AISI, GPT-6 Astra) | **Informed, but provenance.** The message is in context; its authority is not. | Weak. Provenance templates are the hardest predicates to decode (core24 matched-pair world AUROC 0.45–0.58). | Explicit provenance tracking: who issued an instruction, as state rather than text |
| Inaccurate reports of work done | Post-hoc | Report-only judges fall below chance (K1 0.42) | Report-to-log reconciliation against environment state |

**Practical reading.** "Add a monitor" is the right answer only for informed failures. Acting without verifying,
which is exactly what OpenAI cited for Astra ("staying within scope and authorization"), is invisible to every
monitor that reads the agent's context. It has to be prevented by policy (verify first) or by environment-side state
checks, as in NVIDIA's out-of-band OpenShell/Sentry design.

## 4. Open verification items (before submission)
- GPT-6.1 Astra: there is no official OpenAI document. Cite the press reports and the official GPT-6 Astra system card
  separately.
- Keep AISI's supply-chain findings (GPT-6 Astra) separate from the GPT-6.1 shelving.
- NanoGPT: confirm whether the token-splitting belongs to the PR episode or to a separate report (2026-09-25 report).
- Confirm every † number and the Mythos sandbox anecdote in primary PDFs.
- Replit: confirm the canonical Fortune URL. The "fake users" claims are secondary and should not be cited.
