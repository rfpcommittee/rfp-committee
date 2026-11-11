# Review of the marking code (`rfp_final_table.py` and the app)

**Reviewed against:** [Annexure-1 / Run1](ai_evaluation/AI_RFP_Run1.docx), the clarification on translation-quality evaluation (BLEU, COMET, chrF++ and human evaluation), in its current version (Option B only, BLEU below 30 = 0 marks, rule 2.8 for missing translations), and the [Instructions to Bidders](ai_evaluation/Instructions%20to%20Bidders%20for%20the%20Proof%20of%20Concept%20%28POC%29.docx) (section 5, output files).
**Related documents in the same folder:** [Run2](ai_evaluation/AI_RFP_Run2_20marks.docx), [Run3](ai_evaluation/Ai_RFP_Run3_TBD.docx), [Run4](ai_evaluation/AI_RFP_Run4.docx), [Run5](ai_evaluation/AI_RFP_Run5.docx) and [Run6](ai_evaluation/AI_RFP_Run6.docx). They cover other criteria and are not implemented here.

> Notation: 📑 means "section of Annexure-1 (`AI_RFP_Run1.docx`)". For example, 📑 2.7 is section 2.7 of that document.

This file replaces an earlier review that was written when the project was only the merge script. Since then the project became the Streamlit app, which scores the vendor's files itself. The earlier findings are listed in section 3 with their status.

---

## 1. What the code is now

| Part | Role |
|---|---|
| `evaluator.py` + `app.py` | **The official calculation.** Reads the CSV files (2 source, 13 reference, the vendor's files), checks them, computes BLEU, COMET and chrF++, applies the marks and exports the results and an audit record. |
| `rfp_final_table.py` | **The marking rules** (`bleu_marks`, `comet_marks`, `chrf_marks`, `POLICY_ID`) used by the app, and a **command-line merge script** that builds a table from three existing result files. The script does no scoring and no input checking. |

Only the automatic-metrics part of Annexure-1 is implemented (📑 3, 📑 4, 📑 5; maximum 27 marks, 17 without COMET). Human evaluation (📑 6, 15 marks) and the qualification rule (📑 7, 25 of 42) are not covered.

## 2. What matches Annexure-1 (verified in the code and by tests)

| Item | Annexure-1 | Code |
|---|---|---|
| BLEU definition | 📑 3.1: sacreBLEU 2.6.0, corpus level, `flores200` | `BLEU(tokenize="flores200").corpus_score` over the whole language |
| BLEU marks (Option B) | 📑 3.3: ≥70 → 12; 60–<70 → 11; 50–<60 → 10; 40–<50 → 9; 30–<40 → 8; <30 → 0 | `bleu_marks`; checked at 29.99, 30, 39.99, 40, 69.99, 70 |
| COMET model and marks | 📑 4.1, 4.4: `Unbabel/wmt22-comet-da` 2.2.7; ≥0.85 → 10, ≥0.75 → 7, ≥0.65 → 4, else 0 | `comet_marks`; the language score is the mean of the sentence scores |
| COMET inputs | 📑 4.2: source question with options, the translation, the reference translation | `{"src", "mt", "ref"}` per question |
| chrF++ | 📑 5.1, 5.2: `word_order=2`; ≥75 → 5, ≥65 → 3, else 0 | `CHRF(word_order=2)`, `chrf_marks` |
| Unrounded, half-open slabs | 📑 2.6 | `>=` on raw scores; rounding only for display |
| Two directions, higher one | 📑 2.3, 2.4 | English→T and Hindi→T per language; `Max` per metric; if one direction has no output, the other is used |
| Mean over 13 languages, equal weight | 📑 2.7 | sum of the language marks ÷ 14: the 13 languages and Hindi (English to Hindi); Annexure-1 itself says 13, see the policy point below |
| No output for a language | 📑 2.7: 0 marks | 0 marks under every rule; the language stays in the average |
| Missing translation | 📑 2.8 | BLEU, chrF++: empty sentence; COMET: segment score 0, not sent to the model, counted in the mean |
| Output format | Instructions §5: 27 CSV files, one per language pair (26 plus `vendor_english_hindi.csv`), `vendor_<source>_<language>.csv` (for example `vendor_english_tamil.csv`), header `id, question, option_a..d` | `read_vendor_file` and `load_inputs`; the source and the target language come from the file name |
| English to Hindi (extra test) | Instructions §3: "Additionally English to Hindi will also be tested" | `vendor_english_hindi.csv`; the reference is the Hindi source file (no 14th reference file); scored with the same BLEU, COMET, chrF++ and slabs, shown as the last row of the one results table (En→T columns only, Hi→T empty) and **included in the average, now over 14 rows** (SSC's instruction) |
| Disqualification | Instructions §3: no output or unsupported language = 0 marks and the bidder is disqualified | a language (or English to Hindi) with no output in any direction sets `disqualified`; the results page shows a banner, an `Outcome` column and a last row, and the summary CSV has `Disqualified` columns; marks are still calculated |

The same `id` must be used for a question in every file; the rules are in the README ("Input files") and Instructions §5.

## 3. Findings of the earlier review and their status

| # | Earlier finding | Status |
|---|---|---|
| 3.1 | OVERALL row summed the marks instead of averaging them (📑 2.7) | **Fixed.** The app and the script both average over the languages; the script's `Max Marks` is the maximum of the metrics present. |
| 3.2 | Option B fallback and the `best` mode | **Closed.** Option A, the fallback (old 📑 3.3) and `best` were removed from the code, and Annexure-1 now states Option B only. |
| 3.3 | Languages missing from a result file; spelling differences | **Fixed in the app**: all 13 languages are required for the references, language names come from file names, and missing vendor languages are reported. **Still open in the script** (see 4.1). |
| 3.4 | Human evaluation and the 25 / 42 qualification are missing | **Open by design.** Out of scope for this tool. |
| 3.5 | Partial results look complete; bidder name not in the file; `sarvam_*` defaults; no range checks | **Fixed in the app** (vendor name required and written into every export; validation; the audit record). **Still open in the script** (see 4.1). |

## 4. Remaining gaps and points to confirm

### 4.1 The command-line script is not an official calculation

- It merges three existing result files with an outer merge on `Target`. A language absent from a file gets `NaN` and 0 marks, but the OVERALL line averages the score columns ignoring `NaN` while the marks columns count it as 0, so the two are computed on different sets of languages.
- A different spelling of a language (for example "Manipuri" and "Manipuri (Meitei)") creates two partly empty rows without a warning.
- A missing metric file only prints a `[note]` and the result still looks complete.
- `--bidder` appears in the printed title only; the defaults are `sarvam_*`; scores are not range-checked.
- **Advice:** use the app for the official marks (the README says so). If the script is kept, add a check for the 13 languages and a clear warning for partial results.

### 4.2 Policy and document points

- **Disqualification and English to Hindi:** Instructions §3 says a language with no output means 0 marks and disqualification; Annexure-1 (📑 2.7) only says 0 marks. Add the disqualification to Annexure-1 or keep it only in the Instructions. The app also treats a missing English-to-Hindi output as disqualifying (a literal reading of §3); confirm this. Annexure-1 (📑 2.3, 2.7) speaks of 13 languages only and does not mention English to Hindi, and the average is now over 14 rows (13 languages and Hindi); the Commission should confirm that this is intended and amend the 13 to 14.
- **BLEU below 30 = 0** is the Commission's decision. The text in this repository's Annexure-1 (📑 3.3) now says so; make sure the version issued to bidders carries the same wording and keep the Commission's written order with the project records.
- **COMET 0 for a missing translation** (📑 2.8) was decided for this tool; it is now written in Annexure-1. COMET gives an empty translation about 0.32 if it is sent to the model, so the rule changes marks only when many translations are missing.
- **Batch size 16** and the library versions (sacreBLEU 2.6.0, unbabel-comet 2.2.7) are written in Annexure-1. If `COMET_BATCH_SIZE` or a library version changes, change the document too. The audit record stores the actual values of every run.
- **Test data format:** the real Sample Test Data Set and the original test data must use the same layout as `sample_data/` (file names and columns), because the bidders are told to check their files with this tool.

### 4.3 Limits of the checks

- The app cannot know that the text under an id really is the translation of that question; it can only check that the ids match in every file.
- The language of the content of a file is not checked (only the English / Hindi source files get a script warning).
- The real COMET model and the browser upload path were tested by hand once; the automated tests use a mocked COMET model, and the upload widget is not covered by them.

## 5. Relation to the rest of `ai_evaluation`

| Document | Annexure | Criterion | Marks | Covered by this code |
|---|---|---|---|---|
| [Run1](ai_evaluation/AI_RFP_Run1.docx) | 1 | BLEU, COMET, chrF++, human evaluation | 12 + 10 + 5 + 15 = 42 | Partly (27 of 42) |
| [Run2](ai_evaluation/AI_RFP_Run2_20marks.docx) | 2 | Notation, tables, image text, RTL / multi-script | 20 | No |
| [Run3](ai_evaluation/Ai_RFP_Run3_TBD.docx) | 3 | Batch throughput, concurrent processing | 8 | No |
| [Run4](ai_evaluation/AI_RFP_Run4.docx) | 4 | API, CAT tool, glossary / translation memory (live demo) | 15 | No |
| [Run5](ai_evaluation/AI_RFP_Run5.docx) | 5 | Confidence score, error categorization, dashboard | 10 | No |
| [Run6](ai_evaluation/AI_RFP_Run6.docx) | 6 | Data handling, encryption (security) | 5 | No |

Annexures 2 to 6 are committee handbooks with their own score sheets. They would need separate tooling if a combined scoreboard is wanted. Annexure-3 (4.2, "Output integrity") mentions a BLEU comparison between a concurrent and a sequential run; it is not computed by this tool.

## 6. Suggested next steps

1. Confirm that the issued Annexure-1 and Instructions carry the same text as the repository versions (section 4.2).
2. Keep real test data in the `sample_data/` layout.
3. Decide whether the command-line script stays; if it does, add the language and partial-result checks (4.1).
4. If wanted later: human evaluation input and the 25 / 42 qualification line.
