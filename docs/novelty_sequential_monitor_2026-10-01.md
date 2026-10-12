# Novelty search: anytime-valid / conformal sequential monitor for LLM-agent action-gating

**Date:** 2026-10-01 · **Analyst:** research subagent (afayyazi@usc.edu / CAPE project)

## Proposed contribution under test
A cheap, out-of-band **runtime safety monitor** for LLM agents giving a **provable, distribution-free, horizon-independent** bound on the **false-intervention rate**. Mechanism per agent step: cheap **linear probe on the residual stream** → **conformal p-value** calibrated on authorized/compliant behavior → combine per-step evidence into a **test martingale / e-process** (anytime-valid; Ville's inequality) → alarm/intervene at crossing 1/α, with a lifetime false-alarm bound. Plus a **CUSUM/SPRT change-point** variant for minimal-delay detection of drift into an unsafe regime (scope/authorization drift, persistence-after-denial, long-horizon scheming). Claim: provable guarantees + ~1000× cheaper than LLM/CoT monitors, using internals, for **agent action-gating**.

## Access tags
- **[ABS]** arXiv abstract page opened & read
- **[HTML]** arXiv full-text HTML opened & read
- **[PDF]** PDF opened (readability noted)
- **[LEAD]** appeared in search results only — **NOT opened**, listed as lead, not a verified report

Every paper below the "Verified" line was actually opened. Leads are quarantined at the bottom.

---

## BOTTOM LINE

**Verdict: PARTIAL (narrow / combinatorial novelty).** The *exact full intersection* — {cheap internal residual-stream probe} × {conformal→e-process, anytime-valid} × {type-I / false-intervention control} × {LLM-agent action-gating} × {horizon-independent} × {+ change-point drift variant} × {~1000× cost win} — is **not pre-empted by any single paper**. But as of late 2026 **every component and most pairwise combinations are already published**, so this reads as an incremental synthesis, not a new primitive. A referee will have a strong "closest related work" shelf.

**Single closest paper: E-valuator (arXiv:2512.03109, Sadhuka, Prinster, Fannjiang, Scalia, Berger, Regev, Wang; Dec 2025, rev. May 2026).** It already does: e-process → **provable false-alarm-rate control** → **online monitoring of agents over arbitrarily long action sequences** (horizon-independent, "valid at every step") → **terminate problematic trajectories** (= gating). It is the skeleton of the proposal. Its one structural difference: it wraps **black-box verifier scores (LLM judges / process-reward models)** — i.e. it is *not* internals-based and is the *opposite* of cheap (it rides on the expensive monitor rather than replacing it).

**Most defensible novel core:** the cell no one occupies = **{internal residual-stream probe as the base e-process ingredient}** × **{anytime-valid, type-I false-intervention control}** × **{agent action-gating}**. Concretely: E-valuator has the type-I-controlled e-process but on expensive verifier scores; "Doomed from the Start" (2607.06503) has the cheap internal probe + sequential agent abort but with a *post-hoc recall (type-II)* certificate, not an anytime-valid *type-I* one; Conformal Selective Acting (2605.20270) has the Ville e-process + horizon-independent gating but on output scores, per-round, not multi-step agents. **Your union of the three + the safety-drift change-point taxonomy is the open ground.** The cost story (~1000×) and the drift/change-point *application* (scope/authorization drift, persistence-after-denial, scheming) are the most saleable differentiators.

**Theoretical risk (distribution shift): real, not fatal — but it forces an honest reframing.** See §7. The guarantee is only "distribution-free *conditional on the compliant null being exchangeable with calibration*." There is a ready-made referee rebuttal in the literature (2608.30502) showing this exact machinery fires on **135/135** clean *real* streams. Mitigations exist (weighted CTMs, predictive-rank martingales, margin-aware recalibration) but are imperfect, and one key fix (density-ratio weighting) **collapses in high-dim embeddings** — exactly the residual-stream regime.

---

## 1. Conformal prediction for LLMs / agents

| Paper | id / date / venue | Access | Rating | Note |
|---|---|---|---|---|
| **Conformal Selective Acting: Anytime-Valid Risk Control for RLVR-Trained LLMs** — Khosravi & Huo (Georgia Tech) | 2605.20270 · May 2026 · arXiv cs.LG | [HTML] | **PARTIAL (strong)** | Per-round wrapper maintaining a **Ville-type e-process per threshold** on a Bonferroni grid; **anytime-valid**, per-deployment, at every round; "selective acting" = **gating** released outputs; **Thm 5.5 horizon-independent release-rate gap**. But signal = **self-consistency agreement fraction (output scores)**, *not internals*; per-round single outputs, not multi-step agents. This pre-empts "anytime-valid + horizon-independent + gating for LLMs." |
| **What Can Be Enforced? A Theory of Certified Runtime Safety for Tool-Using Agents** — Shawn Ray (CMU) | 2607.22868 · Jul 2026 · arXiv | [HTML] | **PARTIAL (strong, theory)** | Separates (T1) automata/decidability of what a gate can enforce; (T2) **Neyman–Pearson false-block/miss frontier + conformal finite-sample certificate** bounding expected unsafe episodes ≤ δ under exchangeability; (T3) **closed-loop**: once blocking changes future proposals, static scores don't identify the frontier. Directly derives a **conformal certificate for agent action-gating with false-block (= false-intervention) control**. Key contrast: it is **marginal/per-step with a horizon-split budget (miss ≤ δ/H)** — *horizon-dependent* — **not** an anytime-valid e-process. Also independently raises your two biggest risks (exchangeability failure; closed-loop feedback). |
| **Language Models with Conformal Factuality Guarantees** — Mohri & Hashimoto | 2402.10978 · Feb 2024 · arXiv | [ABS] | RELATED (foundation) | Conformal factuality via back-off; **single-shot per-output**, black-box LM, no agents / internals / sequential gating. |
| **Conformal Language Modeling** — Quach, Fisch, Schuster, Yala, Sohn, Jaakkola, Barzilay | 2306.10193 · ICLR 2024 | [ABS] | RELATED (foundation) | Calibrated **generation sets** via sampling + stopping/rejection; per-query, not agent-step monitoring, no internals. |
| **Learn then Test: Calibrating Predictive Algorithms to Achieve Risk Control** — Angelopoulos, Bates, Candès, Jordan, Lei | 2110.01052 · 2021/22 · arXiv | [ABS] | RELATED (foundation) | Distribution-free **batch/single-shot** risk control via multiple testing. Lineage for "control risk below α," but not sequential/anytime, no agents. |

**Finding:** conformal risk control for LLMs is mature but overwhelmingly **single-shot/per-query**. The anytime-valid + gating + horizon-independent combination now exists for LLMs (Conformal Selective Acting) and tool-agent gating has a conformal *certificate* (2607.22868) — but neither uses internals, and 2607.22868's bound is horizon-*dependent*.

## 2. Anytime-valid / e-values / test martingales for LLM or agent monitoring

| Paper | id / date / venue | Access | Rating | Note |
|---|---|---|---|---|
| **E-valuator: Reliable Agent Verifiers with Sequential Hypothesis Testing** — Sadhuka, Prinster, Fannjiang, Scalia, Berger, Regev, Wang | 2512.03109 · Dec 2025 (rev May 2026) · arXiv cs.LG | [ABS] | **PARTIAL (closest overall)** | Converts **any black-box verifier score** into a decision rule with **provable false-alarm control**, framed as **sequential hypothesis testing built on e-processes**, **valid at every step over arbitrarily long trajectories**, used to **quickly terminate problematic trajectories**. = the proposal's skeleton for agents. **Gap:** uses expensive verifier scores (LLM judge / PRM), *not* internal probes; it *wraps* the expensive monitor rather than giving the ~1000× cheap-internals win. |
| **WATCH: Adaptive Monitoring for AI Deployments via Weighted-Conformal Martingales** — Prinster, Han, Liu, Saria | 2505.04608 · 2025 · arXiv | [PDF, partial] | RELATED (shift tool) | **Weighted conformal test martingales** for deployment monitoring; weighting handles **covariate shift** while preserving FPR validity; **output-level**, general ML (not LLM/agents). The canonical "anytime-valid under shift" tool to cite in §7. |
| **E-SHIFT: Anytime-valid sequential hypothesis testing for distribution shift in streaming learning systems** — Khan & Syed | 2510.03839 · rev May 2026 · arXiv | [HTML] | RELATED (machinery) | **e-process + Ville** on a frozen model's **internal signal** (KL-to-uniform + Mahalanobis in embedding space). Shows e-process+Ville+model-internal nonconformity *already exists* — but for **CLIP covariate shift**, not agent safety gating; "cannot address label shift or concept drift." |
| **Who Drifted: the System or the Judge? Anytime-Valid Attribution in LLM Evaluation Pipelines** — Yitao Li | 2606.15474 · Jun 2026 · arXiv cs.AI | [ABS] | RELATED | **Betting e-processes** for LLM eval monitoring, but disentangles **judge drift vs product drift** on a labeled anchor set; output/score level, no action-gating, no internals. |
| **Anytime Detection of Strategic Deviations in Multi-Agent Systems** — Gauthier, Bach, Jordan | 2601.05427 · Jan 2026 · arXiv cs.GT | [ABS] | RELATED | **Safe anytime-valid test supermartingale** "betting against" an equilibrium benchmark to detect drift in multi-agent play. Signal = **game-theoretic payoffs**, not internals; not LLM safety gating. (Notable: Jordan again.) |
| **When the Martingale Never Stops Firing: Anytime-Valid Gating on Real Forecast Streams** — Han & Qu | 2608.30502 · Aug 2026 · arXiv cs.LG | [ABS] | **RELATED — critical risk flag** | **Conformal test martingales + Ville for anytime-valid gating** of online model updates — the exact machinery — and finds the guarantee **fails catastrophically on real (non-exchangeable) streams: at α=0.05, 135/135 clean-stream runs fired vs 1/60 on synthetic exchangeable data.** Forecast streams, not agents, but this is the most dangerous precedent for your claim. |

**Finding:** anytime-valid monitoring of LLM/agent *scores/outputs* is now an active 2025–26 subfield. **E-valuator is the direct agent-gating e-process.** No opened paper applies an anytime-valid e-process to an **internal-state stream** for **agent safety gating**.

## 3. Sequential change-point detection (CUSUM/SPRT/Shiryaev-Roberts) for agents

| Paper | id / date / venue | Access | Rating | Note |
|---|---|---|---|---|
| **Change detection with conformal martingales: new optimal constructions, and suboptimality of existing methods** — Bhattacharyya & Ramdas | 2609.27179 · Sep 2026 · arXiv | [HTML] | RELATED (the foundation to build on) | Distribution-free changepoint detection via **conformal test martingales / e-detectors** (PFA + ARL control). Proves standard methods are **suboptimal (Ω(T), Ω(√ARL) delay)**; gives **minimax-optimal conformal e-processes/e-detectors (Θ(log T), Θ(log ARL))** via weighted restarted conformal mixture martingales. Generic (works on text embeddings) → **this is the correct technical backbone for your CUSUM/SPRT variant; cite and build on it, don't reinvent.** By Ramdas (your named authority). |
| **Real-Time Detection and Repair of LLM Agent Failures** — Sunny Dubey | 2608.02464 · Aug 2026 · arXiv cs.AI | [ABS] | PARTIAL (contrast) | One-class echo-state-network ensemble + **CUSUM alarms** on LLM agents, microseconds/step. But **observable telemetry only (no internal activations)**, **fixed thresholds / AUROC 0.872**, empirical FA rate 17% — **no anytime-valid or provable guarantee.** Shows CUSUM-on-agents is taken, without internals or guarantees. |
| **Anytime-Valid Distribution Shift Detection via Predictive Rank Martingales** — Kuang & Xia | 2609.00536 · Sep 2026 · arXiv stat.ME | [ABS] | RELATED (shift tool) | Fixes the "reference-set contamination" failure of sequential conformal p-values by deriving the **exact conditional null of the next rank**, giving **distribution-free finite-sample anytime type-I control** under the induced dependence. Generic, not LLM/agent. A §7 "save" tool. |

**Finding:** the change-point idea is well-served by generic optimal tools (2609.27179) and CUSUM-on-agents exists (2608.02464) — but **not** CUSUM/SPRT on **internal activations** with an **anytime-valid safety** guarantee framed for **scope-drift / persistence-after-denial / scheming**. The *application* is open; the *machinery* is not.

## 4. Probe-based runtime monitors for agents — any calibrated/guaranteed FA rate?

| Paper | id / date / venue | Access | Rating | Note |
|---|---|---|---|---|
| **Doomed from the Start: Early Abort of LLM Agent Episodes via a Recall-Controlled Probe Cascade** — Ruan, Huang, Zhou, Wei, Lin, Wang, Sun | 2607.06503 · Jul 2026 · arXiv | [ABS] | **PARTIAL (closest on the probe+agent axis)** | **Linear probes on internal activations** predict agent failure **from round 1, earlier than behavior-based monitors**; **distribution-free calibrated detector at each round**; **recall-controlled abort cascade = sequential agent gating**; "exact **post-selection recall** guarantee" after freezing on independent data. **Gaps vs proposal:** (a) **post-hoc split-conformal recall certificate, not an anytime-valid e-process**; (b) controls **recall (type-II / catch failures)**, *not* the **false-intervention (type-I)** rate; (c) target is **task failure / cost-saving**, not safety/unsafe-action. This is your nearest neighbor on internals+agent+sequential-gating. |
| **AgentLens: Interpretable Safety Steering via Mechanistic Subspaces for Multi-Turn Coding Agent** — Luo, Zhang, Quan, Jin, Cai, Xiao, Niu, Xiang | 2606.22673 · Jun 2026 · arXiv cs.AI/SE | [ABS] | RELATED | **Linear probes on step-level hidden states** → detect harmful execution states at runtime → **steer/gate** in a 10-dim subspace. Mechanistically close (probe→detect→gate) but **AUROC only, no calibrated/anytime guarantee.** (Distinct from the 2024 visual-analytics "AgentLens" 2402.08995.) |
| **DeceptGuard: A Constitutional Oversight Framework for Detecting Deception in LLM Agents** — Mukhopadhyay | 2603.13791 · Mar 2026 · arXiv cs.CL | [ABS] | RELATED | Compares black-box / CoT-aware / **activation-probe** monitors on agent deception; **pAUROC 0.934** only — **no conformal/e-process/anytime guarantee**, not sequential. |
| **Monitoring and Discovering Reward Hacking with Internal Representations during LLM Evaluations** — Bergen, Bhalla, Lee … McGrath, Lubana, Merullo (18 authors) | 2609.19101 · Sep 2026 · arXiv | [ABS] | RELATED (cost support) | **Difference-of-means vectors** on internal reps detect reward hacking, "**similarly effective but virtually free**." Strong support for "cheap internals monitor," but **no calibrated FA guarantee.** |
| **Detecting Strategic Deception Using Linear Probes** — Goldowsky-Dill, Chughtai, Heimersheim, Hobbhahn (Apollo) | 2502.03407 · Feb 2025 · arXiv cs.LG | [ABS] | RELATED (foundation) | Canonical deception probes: **AUROC 0.96–0.999**, threshold **calibrated to 1% FPR on a control set** — i.e. **fixed-threshold with an empirical FPR, not conformal/anytime.** Authors: "current performance is insufficient as a robust defence." |
| **Pressure-Testing Deception Probes in LLMs** — Sachin Kumar | 2605.27958 · May 2026 · GEM @ ACL 2026 | [ABS] | RELATED — risk flag | **Probe fragility gap:** AUROC ≥0.998 clean but **collapses under stylistic shift**; recoverable with style-diversity augmentation (0.979–0.983). Shows the **probe signal itself is non-stationary under shift** — compounds §7. |

**Finding (answers the task's Q4 directly):** across every opened probe-monitor, the guarantee is **AUROC / fixed-threshold / empirical-FPR / post-hoc recall** — **none** gives an **anytime-valid or type-I-calibrated false-intervention bound**. "Doomed" is the single exception with a *distribution-free* certificate, but it is **post-hoc recall (type-II), not anytime-valid type-I.** **This is the cleanest, most defensible gap for the paper.**

## 5. Shielding / runtime enforcement applied to LLM agents

| Paper | id / date / venue | Access | Rating | Note |
|---|---|---|---|---|
| **ProbGuard: Proactive Runtime Monitoring for LLM Agent Safety via Probabilistic Prediction** — Wang, Poskitt, Wei, Sun | 2508.00500 · Aug 2025 (rev Aug 2026) · **ASE 2026** | [ABS] | RELATED | **DTMC over symbolic abstract states** predicts safety probability; **intervenes (re-prompt/halt) when below a fixed user threshold.** Agent **action-gating** with intervention — but **no internals, fixed threshold, no provable FA/anytime bound.** |
| **What Can Be Enforced? …** (2607.22868) | — | [HTML] | see §1 | The statistical-enforcement theory for agents; conformal certificate + closed-loop impossibility. |

*(Classic shielding/edit-automata/LTL-RV lineage — Alshiekh et al. safe-RL shields, Ligatti/Bauer/Walker edit automata — not opened here; I did not independently verify them this session, so they are not reported as findings. For LLM-agent-specific LTL/enforcement I opened only ProbGuard + 2607.22868; others are LEADs below.)*

**Finding:** runtime enforcement/shielding for LLM agents exists (ProbGuard, and formally in 2607.22868), but via **symbolic/automata/DTMC + fixed thresholds or marginal conformal** — **not** anytime-valid statistical e-processes on internal states.

## 6. Cost arguments: cheap statistical monitors vs LLM-judge / CoT monitors

- **2609.19101** (opened): internal-rep monitor "**virtually free**" and competitive with heavier detection.
- **DeceptGuard 2603.13791** (opened): frames **activation-probe** as the cheap regime vs **CoT-aware / LLM-judge** regimes.
- **Practitioner + search-level (LEAD, not a verified paper):** a "cheap reward-hacking detection" result cited widely (small encoder + linear probe, **AUC 0.9467 vs sanitized LLM-judge 0.9510, ~4 orders of magnitude cheaper/trajectory**; ablation: removing reasoning text drops AUC→0.62) and dev.to engineering threads ("your LLM judge costs more than the agent"; "if a monitor exceeds ~20–25% of production cost you built the wrong monitor"). **I could not pin the exact arXiv source for the 0.9467 figure — treat as unverified lead, not a citation.**

**Finding:** the **~1000× cost claim is well-supported in spirit** (internals/probes are orders cheaper than per-step LLM/CoT judges) and is a legitimate selling point, **but no opened paper couples the cost win to an anytime-valid guarantee** — that coupling is yours to make. Verify your own ~1000× number empirically; cite 2609.19101 / DeceptGuard, not the unpinned 0.9467 figure.

---

## 7. THE KEY THEORETICAL RISK — does distribution shift sink or save the guarantee?

**Short answer: it does not sink the idea, but it bars any *unconditional* real-world guarantee and demands careful scoping + robust constructions + empirical FA validation on held-out real agent streams.**

**Three distinct threats (all evidenced in opened papers):**
1. **Exchangeability of the compliant null fails on real streams.** 2608.30502 ran the *exact* conformal-martingale-gating machinery and got **135/135 false fires on clean real streams** (vs 1/60 synthetic-exchangeable). This is the referee's ready-made rebuttal to "provable horizon-independent FA control."
2. **Closed-loop feedback.** 2607.22868 (T3): once the monitor *blocks/gates*, it changes the agent's future proposals, so the observed stream is no longer the calibrated null — static scores "need not identify the closed-loop frontier." Interventions break i.i.d./exchangeability by construction.
3. **The probe signal is itself non-stationary.** 2605.27958: residual-stream deception probes hit AUROC ≈0.998 clean but **collapse under stylistic/task shift** — the base nonconformity score drifts even when behavior is compliant.

**Mitigations that *partially* save it (opened):**
- **Weighted conformal test martingales** (WATCH 2505.04608) — preserve FPR validity under *covariate* shift via importance weights. **But** 2606.11949 (opened) shows **density-ratio weighting collapses in high-dim embeddings** (works only for DeBERTa-scale) — i.e. exactly the residual-stream regime is the hard case.
- **Predictive-rank martingales** (2609.00536) — avoid reference-set contamination, keep finite-sample anytime type-I control under the induced dependence (fixed calibration set).
- **Minimax-optimal conformal e-detectors** (2609.27179) — correct delay/ARL behavior for the change-point variant.
- **Margin-aware recalibration** (2607.22868, Cor. 3) — restore the certificate under bounded representation attack at an α penalty.
- **Null diversity / style augmentation** (2605.27958) — broaden the "authorized/compliant" calibration distribution so exchangeability holds more widely.

**Honest framing for the paper:** claim **"distribution-free FA control *conditional on exchangeability of the authorized-behavior null with deployment*,"** not an unconditional safety guarantee. Strengthen with: (a) weighted/robust CTM construction; (b) a broad, diverse compliant-null calibration; (c) explicit treatment of the closed-loop/intervention effect (e.g., gate on *counterfactual-free* signals, or re-derive under an occupancy model per 2607.22868); and (d) **empirical demonstration of FA control on held-out *real* agent streams** — the precise thing 2608.30502 shows is hard, and therefore your strongest possible evidence.

---

## 8. Recommended positioning

- **Lead with the open cell:** *first anytime-valid, **type-I / false-intervention**-controlled monitor on an **internal-state probe stream** for **LLM-agent action-gating***, horizon-independent, at ~1000× the cost of LLM/CoT monitors.
- **Cite as nearest work and distinguish explicitly:** E-valuator (2512.03109, verifier-scores not internals; wraps the expensive monitor), Doomed-from-the-Start (2607.06503, recall/type-II post-hoc not anytime type-I; cost not safety), Conformal Selective Acting (2605.20270, output scores, per-round RLVR), 2607.22868 (marginal/horizon-split conformal, not e-process).
- **Build the change-point variant on** Bhattacharyya & Ramdas (2609.27179), not from scratch.
- **Pre-empt the referee:** address 2608.30502 head-on; report held-out real-stream FA.
- **Do not overclaim** the cost number or cite the unpinned 0.9467 figure; measure your own.

## Appendix — LEADs (surfaced in search, **NOT opened**, not verified)
SafePath 2505.09427 · Conformal LLM Routing 2026.acl-srw.70 (PDF opened but unreadable/binary — not reportable) · ShieldAgent 2503.22738 · Plug in the Safety Chip 2309.09919 · Survey: Safe LLM Agents (Specification/Verification/Enforcement) 2608.14590 · Why Formal Monitors Fail (LTL coverage bound) 2608.01388 · Watchdogs and Oracles (RV meets LLMs) 2511.14435 · Stateful Online Monitoring Catches Distributed Agent Attacks 2605.31593 · StepShield (intervention-timing benchmark, EIR) 2601.22136 [ABS opened — benchmark, no method guarantee] · Tool-Call Dependency Linearly Decodable 2605.25310 · Simple probes catch sleeper agents (Anthropic blog) · Detecting Multi-Agent Collusion 2604.01151 · Calibrating LLM Judges: Linear Probes 2512.22245 · Hallucination Linearly Decodable 2606.02628 · Uncertainty Quantification for LLM Agents (taxonomy) 2609.07395 · MonitoringBench 2605.09684 · Conformal prediction beyond exchangeability (Barber et al.) · Conformal Validity for Any Distribution 2405.06627 · dev.to cost threads.

## Design decisions taken from this search (2026-10-01)
- Closest prior = E-valuator (2512.03109): e-process gating over long agent trajectories, horizon-independent — but wraps EXPENSIVE black-box verifier scores. OUR WEDGE = cheap INTERNAL residual-stream signal (authorization probe) + the safety-drift application. This is the empty cell.
- Build the CUSUM/change-point variant on Bhattacharyya & Ramdas 2609.27179 (minimax conformal e-detectors); do not reinvent.
- Guarantee framing: NOT unconditional. "Distribution-free CONDITIONAL on exchangeability of the authorized-behavior null," + REQUIRED empirical false-alarm control on held-out real agent streams. 2608.30502 shows naive machinery gives 135/135 false fires on real streams; our episode-level conformal fix already cut realized FA 7.5%->1.8% -> that controllability is a core empirical result, not a footnote.
- Do NOT cite the ~1000x / AUC-0.9467 practitioner figure; measure our own FLOPs/cost.
- Every existing probe monitor (Apollo 2502.03407, AgentLens 2606.22673, DeceptGuard 2603.13791) is AUROC/fixed-threshold only — none anytime-valid/type-I-calibrated. That is the cleanest gap.
