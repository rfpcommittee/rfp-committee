# RFP Translation Quality Evaluator

A web app that scores one vendor's translations for the RFP translation-quality criteria and turns the scores into marks:

| Metric | Library / model | Max marks |
|---|---|---|
| BLEU | sacreBLEU, `flores200` tokenizer | 12 |
| COMET | `Unbabel/wmt22-comet-da` (Hugging Face) | 10 |
| chrF++ | sacreBLEU, `word_order=2` | 5 |

For every one of the 13 target languages the app scores English → T and Hindi → T and uses the higher score. BLEU marks are shown under **both** Option A (Standard) and Option B (Lenient), side by side. Human evaluation (15 marks) is not part of this tool, so the maximum here is 27 marks (17 when COMET is switched off).

Only one vendor is evaluated at a time.

## What goes in

Three CSV files, UTF-8 (in Excel: Save As, "CSV UTF-8"). The `id` is the question number and must match across the files.

| File | Columns |
|---|---|
| Source questions | `id, english, hindi` |
| Reference translations | `id`, then one column per language |
| Vendor output | `id, source_lang, target_lang, translation` |

- The 13 languages are: Assamese, Bengali, Gujarati, Kannada, Konkani, Malayalam, Manipuri (Meitei), Marathi, Odia, Punjabi, Tamil, Telugu, Urdu. Column and value names are matched ignoring upper/lower case.
- Vendor output has one row per question, per language, per direction. `source_lang` is `English` or `Hindi`.
- A language or direction with no vendor output gets **0 marks** (the score columns show 0). A single missing translation is scored as an empty sentence.
- Examples are in `sample_data/`. They are **dummy**: the reference text is placeholder text that was not checked by native speakers, and the "vendor output" is the reference with some words removed. Do not use them as results. Recreate them with `python make_sample_data.py`.

## Install

You need Python 3.12 (3.10 or 3.11 also work). COMET does not install on Python 3.13 or newer.

### Windows, quickest

```
setup_model_env.bat
```

This creates a `.venv` and installs everything in `requirements.txt`. Then start the app with `run_app.bat`.

### Manual

```
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py --server.address localhost
```

On macOS or Linux use `python3.12 -m venv .venv`, `.venv/bin/python -m pip install -r requirements.txt` and `.venv/bin/python -m streamlit run app.py`.

The app opens at http://localhost:8501.

### Why the versions are pinned

`requirements.txt` pins a few packages on purpose. `unbabel-comet` needs `protobuf<5` and `numpy<2`; because of that `streamlit` is held at 1.46.1, `pyarrow` below 21, and `setuptools` below 81 (for `pkg_resources`). Changing these will probably break the install; run `pip check` after any change.

## Turning COMET on

COMET uses a model, which is downloaded from Hugging Face the first time (a few GB). Without it the app still computes BLEU and chrF++.

1. Copy `.env.example` to `.env`.
2. Set `USE_MODEL=true` in `.env`.
3. Optional, to download the model before the first run:
   ```
   .venv\Scripts\python -c "from comet import download_model; print(download_model('Unbabel/wmt22-comet-da'))"
   ```
4. Restart the app.

Settings in `.env`:

| Setting | Meaning |
|---|---|
| `USE_MODEL` | `true` computes COMET, `false` skips it |
| `COMET_MODEL` | Hugging Face model name (default `Unbabel/wmt22-comet-da`) |
| `COMET_CHECKPOINT` | Path to an already downloaded `.ckpt`; leave empty to use `COMET_MODEL` |
| `COMET_BATCH_SIZE` | Batch size; keep it the same for every vendor |
| `COMET_GPUS` | `0` for CPU, `1` for one GPU. On a CPU, COMET is slow for a large test set |

## Use

1. Type the vendor's name (optional) in the sidebar.
2. In step 1, upload the three files. Each file is checked straight away and shows what it found, for example "6 questions, 13 of 13 languages". Tick **Use the dummy sample files** to try the app first.
3. In step 2, press **Evaluate**.
4. In step 3, read the results:
   - total marks under Option A and Option B, plus the COMET and chrF++ marks;
   - a table of marks by language, and a second tab with every score for both directions;
   - a chart comparing BLEU marks under Option A and Option B;
   - two CSV downloads (per language, and the A/B summary) and an "Evaluation details" section with the library versions, sacreBLEU signatures and warnings.

Which BLEU option counts: Option A is the default. Option B applies only if every vendor scores 0 BLEU marks under Option A, so compare with the other vendors before using it.

## Marking rules

| Metric | Rule (each slab starts at the value shown, on the unrounded score) |
|---|---|
| BLEU, Option A | 70 or more: 12 · 60 to below 70: 10 · 50 to below 60: 6 · below 50: 0 |
| BLEU, Option B | 70 or more: 12 · below 70: 12 minus 1 for every 10 points (or part of 10) below 70, minimum 0 |
| COMET | 0.85 or more: 10 · 0.75 to below 0.85: 7 · 0.65 to below 0.75: 4 · below 0.65: 0 |
| chrF++ | 75 or more: 5 · 65 to below 75: 3 · below 65: 0 |

The marks of each metric are the average of the 13 languages (equal weight). A language with no vendor output gets 0 marks under every rule, including Option B.

The rules live in one place, `rfp_final_table.py`. The app and the command-line script both use it.

## Command-line script

`rfp_final_table.py` also works on its own. It merges three result files (`sarvam_bleu_results.csv`, `sarvam_comet_results.csv`, `sarvam_chrf_results.csv`, each with a `Target` column and a `Max(...)` column) into one table:

```
python rfp_final_table.py --bleu_option A --bidder "Vendor" --out final_table.csv
```

Unlike the app, it adds up the marks of the languages instead of averaging them, and it uses one BLEU rule per run (`--bleu_option A`, `B` or `best`) instead of showing A and B together. Use the app for the official marks.

## Files

| File | Purpose |
|---|---|
| `app.py` | The Streamlit web app |
| `evaluator.py` | Reads and checks the three files, computes the scores, applies the marks |
| `rfp_final_table.py` | The marking rules, and the command-line merge script |
| `make_sample_data.py` | Builds the dummy files in `sample_data/` |
| `.env` / `.env.example` | Settings (`.env` is not committed) |
| `requirements.txt` | Pinned dependencies |
| `setup_model_env.bat`, `run_app.bat` | Windows helpers to install and start |

## Limits

- One vendor per run.
- The reference translations and the test set must be supplied by the committee; none are included.
- Human evaluation (15 marks) and the 25 out of 42 qualifying cutoff are not calculated.
- The app does not save results by itself; use the CSV download buttons.
