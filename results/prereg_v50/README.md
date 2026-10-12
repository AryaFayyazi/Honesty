# Prereg v50: blind audit sheet and key

This directory holds the blind sheet and the separate key for the prereg v50 audit of rubric labels.
- **Protocol.** `docs/preregistration_v50.md`, locked in `results/prereg_v50_lock.json`.
- **Lock check.** The sha256 of the prereg was re-checked before building and matches the lock: `e5d49863…9f39`.
- **Builder.** `build_audit.py`: CPU only, deterministic (two runs give byte-identical outputs), read-only on project
  data.

## Files
- **`audit_sheet.jsonl`.** The annotator-facing sheet: 235 items, one per line. The fields are:
  - `item_id`;
  - `task` (the user message);
  - `actions`;
  - `report` (the exact text the rubric labelled: `final_answer` for S0, `revised_report` for S1–S4).
- **`audit_key.csv`.** One row per item: `item_id, stratum, set, episode_id, model, condition, rubric_label`.
  **Keep this file away from the annotator.**
- **`counts.csv`.** Sampled and available counts per stratum × label.

## Strata and sources
| Stratum | Source | Condition |
|---|---|---|
| S0 | `outputs/disclosure_v37/<set>_rubric.parquet`, C sets only (frozen `is_C` / `V37_MUSE_C` from `scripts/98_v37_analysis.py`; the builder asserts its copy matches the script) | none (original report) |
| S1 | `outputs/reconcile/v46B_rubric3.parquet` + `v46B.parquet` | none |
| S2 | same | caa_p8_d16 |
| S3 | `outputs/prereport/v44_*_rubric3.parquet` + matching generation files (all 8 v44 files: Gemma-4, gpt-oss, Muse; base/reasoning/obfuscate) | neutral |
| S4 | same | fta_contract |

- **Episodes.** All episodes are informed (`informed == True`) and come from x− (`*_minus*`) sets.
- **Sampling.** Within each label, items are ordered by `sha256(f"{stratum}|{set}|{episode_id}")` and the first ones
  are taken. The quotas are 30 CANDID, 15 MISREPRESENTED and 15 OMITTED.

## Counts (sampled; available pool in parentheses)
| Stratum | CANDID | MISREPRESENTED | OMITTED | Total |
|---|---|---|---|---|
| S0 | 19 (19) | 15 (144) | 15 (31) | 49 |
| S1 | 14 (14) | 15 (68) | 0 (0) | 29 |
| S2 | 27 (27) | 15 (39) | 1 (1) | 43 |
| S3 | 24 (24) | 15 (197) | 15 (23) | 54 |
| S4 | 30 (157) | 15 (264) | 15 (27) | 60 |
| **All** | 114 | 75 | 46 | **235** |

## Strata short of quota
Per the prereg, a stratum with fewer items contributes all of them. No other label (e.g. SPIN) was substituted.

| Stratum | Label | Sampled / quota |
|---|---|---|
| S0 | CANDID | 19/30 |
| S1 | CANDID | 14/30 |
| S1 | OMITTED | 0/15 (none exist) |
| S2 | CANDID | 27/30 |
| S2 | OMITTED | 1/15 |
| S3 | CANDID | 24/30 |

The A1 comparisons therefore rest on n_CANDID of 14 (S1) vs 27 (S2) and 24 (S3) vs 30 (S4).

## Construction details and judgement calls
1. **`actions`.** The log is chronological and lists every tool call except the read-only tools `list_files`,
   `read_file` and `open_mock_url`; this is the same exclusion as the activity log in `scripts/96`.
   - **`request_permission`.** Every call is included, with its result.
   - **Other kept calls.** `execute_mock_command` calls are kept even when the command is read-only (e.g. `help`),
     because the log does not separate them reliably.
   - **Entry format.** Each entry is `{"step": <event_id>, "text": "<tool>(<args>) -> <result>"}`. `text` is verbatim
     and at most 200 characters: the result is cut to at most 116 characters and the call gets the rest. Cuts are
     marked `…`.
2. **`unauthorized_action: true`.** Entries the environment flagged as the unsafe action carry this marker. That flag
   is environment ground truth, not a rubric label, and it does not depend on the condition.
   - **Why it was added.** Q1 asks about "the critical (unauthorized) action", so the annotator needs to know which
     action that is.
   - **How to remove it.** The coordinator's spec did not list this field. To drop it, set `MARK_UNSAFE = False` in
     `build_audit.py` and re-run.
3. **Ordering and ids.** Items are shuffled with `random.Random(50)`. Item ids are 6-hex values drawn afterwards, in
   shuffled order, from `random.Random(5050)`, so neither the id nor the sheet position encodes the stratum.
4. **Hidden from the sheet.** The sheet omits:
   - the model, condition, stratum and label;
   - all intervention and steering text, including the added user turn for S3/S4;
   - the system prompt and its oversight notices.

   An automated check found none of the model names, condition names or label names in the sheet.
5. **Residual unblinding risk.** This cannot be removed, because the report itself is the object of the audit:
   - fta_contract reports (S4) often use the STATUS / EVIDENCE / LIMITATION / NEXT ACTION format;
   - some caa_p8_d16 reports (S2) are visibly degraded.

   The analysis should state this.
6. **S0 and the frozen C list.** S0 uses the frozen C list. Muse seeds 4–7 (`minus45`, `minus67`) are therefore not in
   S0; they appear only in S1/S2.
   - Effect on the trigger finding: the 12 con_cloud_cost false-CANDID cases that prompted this audit were counted
     under the older, broader `is_C` (all `xm_museglimmer_core24b*` sets). Only some of them fall inside the frozen
     list.

## Addendum 1 sheet (exploratory SPIN audit)
- **Protocol.** Addendum 1 of `docs/preregistration_v50.md`, locked under `addenda` in `results/prereg_v50_lock.json`.
  - The addendum hash `a407…b8b8` matches the current file.
  - The main body (the file before `## Addendum 1`) still matches the original lock `e5d4…9f39`.
- **Build.** `python results/prereg_v50/build_audit.py --addendum`. The main outputs are unchanged: the md5 of
  `audit_sheet.jsonl`, `audit_key.csv` and `counts.csv` is identical before and after the change.
- **Outputs.**
  - `addendum_sheet.jsonl`: 64 items, in the same blind format and with the same action-log rules as the main sheet.
  - `addendum_key.csv`: `item_id, set, episode_id, model, rubric_label, retro`.
  - `addendum_counts.csv`.
- **Episodes.** S0 only: frozen C list, informed x−, original reports.
  - `retro` comes from `scripts/95` `episode_rows` (a `request_permission` after `first_unsafe_event`), as in
    scripts/98.
  - Within each group, order by `sha256(f"S0A|{set}|{episode_id}")` and take the first.
  - Shuffle seed 51. Ids are drawn from seed 5151 and checked against v50 ids for collisions.
- **Exclusion (revised).** Episodes are excluded only if they appear in `audit_key.csv` rows with `stratum == "S0"`,
  i.e. their original report was already audited in v50.
  - **Change log.** The first build excluded every (`set`, `episode_id`) in `audit_key.csv`, including S1–S4
    regenerations of the same episodes. That gave only 12/14 retro SPIN.
  - **Why it changed.** The coordinator clarified that the instruction was ambiguous and meant S0 only.
  - **Timing.** The change was made before any addendum annotation existed.
  - **Unchanged.** Seeds (51 / 5151) and every other rule. The main v50 outputs are still byte-identical.

| Group | Quota | Pool | Excluded (audited in S0) | Sampled |
|---|---|---|---|---|
| SPIN, retro = 1 | all | 14 | 0 | **14** |
| SPIN, retro = 0 | 40 | 873 | 0 | 40 |
| CANDID (distractor) | 10 | 19 | 19 | **0** |
| MISREPRESENTED (distractor) | 10 | 144 | 15 | 10 |

The sheet has 64 items in total.

**Shortfall.** CANDID distractors are 0/10, because all 19 S0 informed CANDID items were audited in v50. The only
distractors are the 10 MISREPRESENTED items.
