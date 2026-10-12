# Preregistration v53: is the intervention-choice law internal, or visible in the chain of thought?

Written 2026-10-05 ~23:20. At this time no Qwen v49 label exists (Qwen rollouts are still running), so B_Qwen is unknown.
B for Muse, Gemma and gpt-oss is known (v49 partial).

## Indices (development data, core24 informed violations; results/prereg_v53/ktext.json, scripts/138)
| Model | K internal (prereg v49) | K_text (any authorization concept in CoT) | K_text_strict (CoT flags a problem) |
|---|---|---|---|
| Muse | 0.94 | 1.00 | 0.764 |
| Qwen | 0.81 | 0.98 | 0.764 |
| Gemma | 0.69 | 0.906 | 0.471 |
| gpt-oss | 0.03 | 0.908 | 0.333 |

- The lexicons are fixed in `scripts/138_ktext.py`.
- Already observable (descriptive, post hoc): K_text does not separate gpt-oss from Gemma, although their B differ
  (−0.25 vs +0.01). K_text_strict orders the three known models like K.

## Competing predictions for Qwen (fixed now)
- **Internal law (K):** B_Muse > B_Qwen > B_Gemma.
- **Strict text law (K_text_strict):** B_Qwen ≈ B_Muse (tied index), and both > B_Gemma.
- **Both** predict B_Qwen > B_Gemma.

## Discriminating test
- Paired bootstrap (episode clusters) of B_Muse − B_Qwen on the fresh v49 episodes.
- If the 95% CI lies above 0 (Qwen clearly below Muse), the result **favours K over K_text_strict**.
- If it includes 0, the test is **inconclusive** between the two laws.
- B_Qwen > B_Gemma (one-sided bootstrap) is reported for both laws.

## Reporting
- All three indices and the result appear in the paper.
- If the strict text index explains B as well as K does, the paper states that the law is "explicit recognition of
  the violation", visible in CoT or in activations, not uniquely internal.
- Four models give only weak discrimination; more models would be needed for a decisive test. This is stated as a
  limitation.
