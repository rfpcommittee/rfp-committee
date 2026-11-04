# Review of `rfp_final_table.py`

**Reviewed against:** [ai_evaluation/AI_RFP_Run1.docx](ai_evaluation/AI_RFP_Run1.docx), the clarification on translation-quality evaluation (BLEU, COMET, chrF++ and human evaluation).
**Related documents in the same folder:** [Run2](ai_evaluation/AI_RFP_Run2_20marks.docx), [Run3](ai_evaluation/Ai_RFP_Run3_TBD.docx), [Run4](ai_evaluation/AI_RFP_Run4.docx), [Run5](ai_evaluation/AI_RFP_Run5.docx) and [Run6](ai_evaluation/AI_RFP_Run6.docx). They cover other criteria and are not implemented by this script.

> Notation: 📑 means "section of the referenced document". For example, 📑 2.7 is section 2.7 of `AI_RFP_Run1.docx`.

---

## 1. What the script is

`rfp_final_table.py` merges three per-language result files (BLEU, COMET, chrF++), converts each language's "Max" score into marks, totals them, and writes `rfp_final_table.csv`.

| Input CSV | Column used | Metric | Max marks |
|---|---|---|---|
| `sarvam_bleu_results.csv` | `Max(B1,B2)` | BLEU | 12 |
| `sarvam_comet_results.csv` | `Max(C1,C2)` | COMET | 10 |
| `sarvam_chrf_results.csv` | `Max(F1,F2)` | chrF++ | 5 |

It implements only the automatic-metrics part of Run1 (📑 3, 📑 4, 📑 5). Human evaluation (📑 6, 15 marks) and the qualification rule (📑 7) are not covered.

## 2. What matches Run1 (verified)

| Item | Run1 reference | Script |
|---|---|---|
| BLEU Option A slabs | 📑 3.2: 70 / 60 / 50 → 12 / 10 / 6 / 0 | `bleu_a` matches |
| BLEU Option B rule | 📑 3.4: 12 minus 1 per 10 points or part thereof, minimum 0 | `bleu_b` matches (BLEU 65 → 11, BLEU 41.5 → 9) |
| COMET slabs | 📑 4.4: 0.85 / 0.75 / 0.65 → 10 / 7 / 4 / 0 | `comet_marks` matches |
| chrF++ slabs | 📑 5.2: 75 / 65 → 5 / 3 / 0 | `chrf_marks` matches |
| Unrounded, half-open slabs | 📑 2.6 | Uses `>=` on raw scores, matches |
| Max of the two directions | 📑 2.4 | Reads the `Max(...)` columns, matches |
| Unsupported language gets 0 | 📑 2.7 | `NaN` score → 0 marks, matches |

## 3. Gaps and issues

### 3.1 Aggregation differs from Run1 (most important)

- **Run1 📑 2.7:** the marks of the 13 languages are averaged (simple mean, equal weight, 2 decimals). This gives BLEU out of 12, COMET out of 10 and chrF++ out of 5.
- **Script:** each language is scored out of 27 (12 + 10 + 5). The OVERALL row **sums** the marks across languages, for example 200 / 351, instead of averaging them.
- **Impact:** the percentage printed at the end is equivalent, but the OVERALL marks are not the official per-metric marks. A reader cannot compare them directly to the 12 / 10 / 5 maximums.
- **Fix:** in the OVERALL row, use the mean (rounded to 2 decimals) for each marks column, and set Max Marks to 27.

### 3.2 Option B fallback is not implemented as specified

- **Run1 📑 3.3:** Option A is the default for everyone. Option B is applied to all bidders and all languages only if every bidder's total BLEU marks under Option A is zero. If any bidder gets any BLEU marks under Option A, Option B is not used.
- **Script:** it handles one bidder at a time. The user picks `--bleu_option A|B|best` by hand, so the cross-bidder condition is never checked.
- **`best` mode:** it takes the higher of A and B per language. Run1 does not allow this. It could favour one bidder and conflicts with the statement that the choice "depends only on this condition and not on which bidder it favours".
- **Fix:** either remove `best`, or add a multi-bidder mode that checks the 📑 3.3 condition across all bidders before choosing A or B.

### 3.3 Inconsistent handling of languages missing from a CSV

- The script uses an outer merge on `Target`. A language that is absent from one CSV gets `NaN` for that metric and 0 marks, which is consistent with 📑 2.7.
- However, the OVERALL average of the score columns ignores `NaN`, while the marks columns count it as 0. The averages and the marks are therefore computed on different sets of languages.
- If one file spells a `Target` differently (for example "Manipuri" vs "Manipuri (Meitei)"), the merge creates two partly empty rows without any warning.
- **Fix:** validate that all files contain the same 13 languages and fail or warn if not.

### 3.4 Human evaluation and qualification are missing

- The script's maximum is 27, while Run1 📑 7.1 sets the total at 42 (BLEU 12 + COMET 10 + chrF++ 5 + human evaluation 15).
- The qualifying cutoff in 📑 7.2 is 25 out of 42. The script's final percentage cannot be compared with this cutoff, and it has no pass or fail output.
- **Fix:** add an optional human-evaluation input (📑 6.6 slabs: 4.5 / 4.0 / 3.5 → 15 / 10 / 5 / 0, then the mean over 13 languages), and print a qualification line using the unrounded total against 25.

### 3.5 Smaller issues

- **Partial results look complete:** if a metric file is missing, the script prints only a `[note]` and still reports a percentage, which can look like a full result. A clearer warning, or an error unless `--allow_partial` is passed, would be safer.
- **OVERALL row filter:** rows are dropped with `startswith("OVERALL")`. This is fine today, but it depends on the exact label used by the other three scripts.
- **Bidder name:** `--bidder` appears only in the printed title and is not written to the CSV, so output files from different bidders cannot be told apart.
- **Defaults:** file names default to `sarvam_*`, which ties the script to one bidder unless the paths are overridden.
- **No input validation:** non-numeric or out-of-range scores (for example BLEU above 100, COMET above 1) are not checked.

## 4. Relation to the rest of `ai_evaluation`

| Document | Criterion | Marks | Covered by this script |
|---|---|---|---|
| [Run1](ai_evaluation/AI_RFP_Run1.docx) | BLEU, COMET, chrF++, human evaluation | 12 + 10 + 5 + 15 = 42 | Partly (27 of 42) |
| [Run2](ai_evaluation/AI_RFP_Run2_20marks.docx) | Notation, tables, image text, RTL / multi-script | 20 | No |
| [Run3](ai_evaluation/Ai_RFP_Run3_TBD.docx) | Batch throughput, concurrent processing | 8 | No |
| [Run4](ai_evaluation/AI_RFP_Run4.docx) | API, CAT tool, glossary / translation memory (live demo) | 15 | No |
| [Run5](ai_evaluation/AI_RFP_Run5.docx) | Confidence score, error categorization, dashboard | 10 | No |
| [Run6](ai_evaluation/AI_RFP_Run6.docx) | Data handling, encryption (security) | 5 | No |

Run2 to Run6 are committee handbooks with their own scoring sheets. They would need separate tooling if a combined scoreboard is wanted.

## 5. Suggested priority

1. Fix the aggregation to a per-language mean (3.1).
2. Remove `best` mode and implement the Option B fallback condition across bidders (3.2).
3. Add language-set validation and a partial-results warning (3.3, 3.5).
4. Add human evaluation and the 25 / 42 qualification check (3.4).
