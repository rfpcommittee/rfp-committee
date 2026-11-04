# RFP Translation Quality Evaluator

A web app that scores one vendor's translations for the RFP translation-quality criteria (BLEU, COMET, chrF++) and turns the scores into marks. You load three CSV files, press a button, and read the results on the same page.

## Install and run (start here)

### What you need

| Item | Detail |
|---|---|
| Computer | Windows 10 or 11 (the helper scripts are for Windows; macOS and Linux steps are given below). 8 GB RAM or more. |
| Python **3.12** | From https://www.python.org/downloads/ . Tested with 3.12. **Python 3.13 and newer do not work** (the COMET library does not install there). |
| Internet | Needed for the first install (Python packages, including PyTorch) and, if you use COMET, to download the model once. After that it can run offline. |
| Disk space | Several GB free (the Python environment plus the COMET model). |
| Git | Optional. You can download the repository as a ZIP instead. |

Check Python in a terminal (Command Prompt or PowerShell): `py -3.12 --version` should print `Python 3.12.x`.

### Steps

**1. Get the code**

```
git clone https://github.com/rfpcommittee/rfp-committee.git
cd rfp-committee
```

(Or use *Code → Download ZIP* on GitHub, unzip it, and open a terminal in that folder.)

**2. Install the libraries (once)**

```
setup_model_env.bat
```

This creates a `.venv` folder (a private Python 3.12 environment) and installs everything listed in `requirements.txt`: streamlit, pandas, sacreBLEU, sentencepiece and unbabel-comet (which brings PyTorch). It takes several minutes. If your network drops and an error appears, run the same command again; downloads already finished are reused.

**3. Choose whether to compute COMET**

COMET (10 of the 27 marks) needs a language model of a few GB, downloaded from Hugging Face the first time. BLEU and chrF++ need no model.

- **Without COMET:** do nothing. The app works and the maximum is 17 marks.
- **With COMET:**
  1. Copy the settings file: `copy .env.example .env`
  2. Open `.env` in Notepad and change `USE_MODEL=false` to `USE_MODEL=true`. Save.
  3. Download the model now (recommended, so the app does not look stuck on the first run):
     ```
     .venv\Scripts\python -c "from comet import download_model; print(download_model('Unbabel/wmt22-comet-da'))"
     ```
     If the download breaks, run the same command again.

**4. Start the app**

```
run_app.bat
```

Your browser opens at **http://localhost:8501**. If it does not, open that address yourself. Keep the terminal window open while you use the app. Press `Ctrl+C` in that window to stop it.

**5. Check that it works**

In the app, switch on **Use the dummy sample files**, then press **Evaluate**. You should see total marks under Option A and Option B. With COMET on, the total is out of 27 and the first run takes about 3 minutes on a laptop CPU (about 1.5 minutes to load the model, then the scoring); with COMET off it is out of 17 and takes a few seconds.

**6. Use your own files**

Switch the sample toggle off, upload your three CSV files (formats are described in [Input files](#input-files)), and press **Evaluate**.

### Without the .bat files (manual, also for macOS and Linux)

```
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py --server.address localhost
```

On macOS or Linux use `python3.12 -m venv .venv`, then `.venv/bin/python -m pip install -r requirements.txt` and `.venv/bin/python -m streamlit run app.py`.

### If something goes wrong

| Problem | What to do |
|---|---|
| `Python 3.12 was not found` when running `setup_model_env.bat` | Install Python 3.12 and run it again. |
| Install fails with timeout or "could not resolve pypi.org" | The network dropped. Run `setup_model_env.bat` again. |
| App sidebar says the unbabel-comet library is not installed | The app was started with the wrong Python. Start it with `run_app.bat` (it uses `.venv`). |
| Evaluate takes very long with COMET on | COMET is slow on a CPU; a large test set can take hours. Set `USE_MODEL=false` in `.env` to get BLEU and chrF++ right away, or run on a machine with a GPU (`COMET_GPUS=1`). |
| The page does not open | Check that no other program uses port 8501, and that the terminal window is still open. |
| After changing a package version the app breaks | Run `.venv\Scripts\python -m pip check`. The versions in `requirements.txt` are pinned on purpose (see below). |

### Why the versions are pinned

`unbabel-comet` needs `protobuf<5` and `numpy<2`. Because of that, `streamlit` is held at 1.46.1, `pyarrow` below 21, and `setuptools` below 81 (`torchmetrics` still imports `pkg_resources`). Changing these will probably break the install.

### Settings in `.env`

| Setting | Meaning |
|---|---|
| `USE_MODEL` | `true` computes COMET, `false` skips it |
| `COMET_MODEL` | Hugging Face model name (default `Unbabel/wmt22-comet-da`) |
| `COMET_CHECKPOINT` | Path to an already downloaded `.ckpt`, to run offline; leave empty to use `COMET_MODEL` |
| `COMET_BATCH_SIZE` | Batch size; keep it the same for every vendor |
| `COMET_GPUS` | `0` for CPU, `1` for one GPU |

Restart the app after changing `.env`. If there is no `.env`, the app runs with COMET off.

## How to use the app

1. Type the vendor's name (optional) in the sidebar.
2. **Step 1, Input files:** upload the three files. Each file is checked straight away and shows what it found, for example "6 questions, 13 of 13 languages", or an error that says what to fix.
3. **Step 2, Evaluate:** press the button. A progress bar shows the stage.
4. **Step 3, Results:**
   - total marks under Option A and Option B, plus the COMET and chrF++ marks;
   - a table of marks by language, and a second tab with every score for both directions;
   - a chart comparing BLEU marks under Option A and Option B;
   - two CSV downloads (per language, and the A/B summary) and an "Evaluation details" section with the library versions, sacreBLEU signatures and warnings.

Which BLEU option counts: Option A is the default. Option B applies only if every vendor scores 0 BLEU marks under Option A, so compare with the other vendors before using it.

## What it scores

| Metric | Library / model | Max marks |
|---|---|---|
| BLEU | sacreBLEU, `flores200` tokenizer | 12 |
| COMET | `Unbabel/wmt22-comet-da` (Hugging Face) | 10 |
| chrF++ | sacreBLEU, `word_order=2` | 5 |

For each of the 13 target languages the app scores English → T and Hindi → T, and the **Max** column is the higher of the two scores for that metric. BLEU marks are shown under **both** Option A (Standard) and Option B (Lenient), side by side. Human evaluation (15 marks) is not part of this tool, so the maximum here is 27 marks (17 when COMET is off). Only one vendor is evaluated at a time.

## Input files

Three CSV files, UTF-8 (in Excel: Save As, "CSV UTF-8"). The `id` is the question number and must match across the files.

| File | Columns |
|---|---|
| Source questions | `id, english, hindi` |
| Reference translations | `id`, then one column per language |
| Vendor output | `id, source_lang, target_lang, translation` |

- The 13 languages are: Assamese, Bengali, Gujarati, Kannada, Konkani, Malayalam, Manipuri (Meitei), Marathi, Odia, Punjabi, Tamil, Telugu, Urdu. Column and value names are matched ignoring upper/lower case.
- Vendor output has one row per question, per language, per direction. `source_lang` is `English` or `Hindi`.
- **Multiple-choice questions:** put the question and its four options in the same cell, one per line:
  ```
  What is the capital of India?
  (A) Mumbai
  (B) New Delhi
  (C) Kolkata
  (D) Chennai
  ```
  Each question is scored as one text (the whole cell), so the reference and the vendor output must use the same layout. In Excel use Alt+Enter for a new line inside a cell. CSV files keep the line breaks.
- A language or direction with no vendor output gets **0 marks** (the score columns show 0). A single missing translation is scored as an empty sentence.
- Examples are in `sample_data/`. They are **dummy**: the reference text is placeholder text that was not checked by native speakers, and the "vendor output" is the reference with some words removed or replaced. Do not use them as results. Recreate them with `python make_sample_data.py`.

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
