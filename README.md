# RFP Translation Quality Evaluator

A web app that scores one vendor's translations for the RFP translation-quality criteria (BLEU, COMET, chrF++) and turns the scores into marks. You load the CSV files (one file per language), press a button, and read the results on the same page.

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

In the app, type any vendor name, switch on **Use the dummy sample files**, then press **Evaluate**. The sample files are in the **`sample_data`** folder of the project (next to `app.py`), in the sub-folders `source`, `reference` and `vendor` (see [Input files](#input-files)); you can also download them from the app with **Download the sample files (ZIP)**, to use as a template for your own files. You should see the total marks (BLEU under Option B). With COMET on, the total is out of 27 and the first run takes about 3 minutes on a laptop CPU (about 1.5 minutes to load the model, then the scoring); with COMET off it is out of 17 and takes a few seconds.

**6. Use your own files**

Switch the sample toggle off, upload your files (2 source files, 13 reference files, the vendor's files; formats and file names are described in [Input files](#input-files)), and press **Evaluate**.

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

1. **Step 1, Input files:** type the **vendor name** (required; it appears in the results and in the exported CSV files and file names), then upload the **English source file**, the **Hindi source file**, the **13 reference files** (select them all at once in the file dialog) and the **vendor's files**. A table "Files found" shows, for each language, which reference file and which vendor file was recognised. Every file is checked straight away and the errors name the file. Once the files are read, a **validation summary** compares them: question count, expected vendor rows (questions × 13 languages × 2 directions), rows received and missing, and a table of what the vendor delivered per language and direction. Errors (for example a question id that is missing in a reference file, a blank reference, a vendor id that is not in the source, two files for one language) block the **Evaluate** button; warnings (missing vendor output, unsupported language rows) do not.
2. **Step 2, Evaluate:** press the button. A progress bar shows the stage. If you change the vendor name or any file afterwards, the earlier result is cleared so it can never be shown against different inputs.
3. **Step 3, Results:**
   - total marks (BLEU Option B, COMET, chrF++);
   - one table with, for each metric, the `En→T` score, the `Hi→T` score, the `Max` (the higher of the two) and the marks;
   - a chart of the BLEU marks by language;
   - three downloads: per-language CSV, summary CSV, and an audit record (JSON). The CSVs carry the vendor name, a run ID, the time and the scoring policy; the audit record also has the SHA-256 of each input file, the validation summary, the library versions and the sacreBLEU signatures;
   - an "Evaluation details" section with the same information and the warnings.

## What it scores

| Metric | Library / model | Max marks |
|---|---|---|
| BLEU | sacreBLEU, `flores200` tokenizer | 12 |
| COMET | `Unbabel/wmt22-comet-da` (Hugging Face) | 10 |
| chrF++ | sacreBLEU, `word_order=2` | 5 |

For each of the 13 target languages the app scores English → T and Hindi → T, and the **Max** column is the higher of the two scores for that metric. BLEU marks use **Option B (Lenient)**. Human evaluation (15 marks) is not part of this tool, so the maximum here is 27 marks (17 when COMET is off). Only one vendor is evaluated at a time.

## Input files

All files are CSV, UTF-8 (in Excel: Save As, "CSV UTF-8"). There is **one file per language**, in three groups. Every question is a multiple-choice question: the **question and each of the four options sit in their own columns**.

| Group | File names | Columns |
|---|---|---|
| Source questions (2 files) | `source_english.csv`, `source_hindi.csv` | `id`, `question`, `option_a`, `option_b`, `option_c`, `option_d` |
| Reference translations (13 files) | `reference_<language>.csv` | `id`, `question`, `option_a`, `option_b`, `option_c`, `option_d` |
| Vendor output (one file per language) | `vendor_<language>.csv` | `id`, `source_lang`, `question`, `option_a`, `option_b`, `option_c`, `option_d` |

In the app you upload the two source files in their two boxes, and the 13 reference files and the vendor files each in one box (select many files at once).

### File names: the language comes from the name

`<language>` is one of: `assamese`, `bengali`, `gujarati`, `kannada`, `konkani`, `malayalam`, `manipuri_meitei`, `marathi`, `odia`, `punjabi`, `tamil`, `telugu`, `urdu`. The app reads the language of a reference or vendor file **from its file name** (upper or lower case, `-` or `_` or a space all work; `manipuri` alone also works). So `reference_tamil.csv` is the Tamil reference and `vendor_tamil.csv` is the vendor's Tamil output. A name with no language, with two languages, two files for the same language, or a vendor file uploaded among the reference files, is reported as an error.

### The id rules (so that ids never clash)

The `id` is the question number (`Q001`, `Q002`, ... or `1`, `2`, ...; any text without surrounding spaces). Follow these rules in **every** file:

1. **Inside one file, every id appears once.** No two questions share an id. `Q1` and `q1` count as the same id, so they clash too. (The only repeat allowed is in a vendor file, where the same id appears once for `English` and once for `Hindi` in `source_lang`.)
2. **The same question has the same id in every file.** Question `Q001` is `Q001` in `source_english.csv`, in `source_hindi.csv`, in all 13 reference files and in all vendor files. Spell it the same way everywhere (upper/lower case counts).
3. **The two source files have exactly the same ids.** If an id is only in one of them, the app stops and names it.
4. **Each reference file has every source id, and no other id.** Missing or extra ids are errors and the file's language is named.
5. **A vendor file may only use source ids.** An id that is not in the source is an error (it usually means the wrong vendor file). A source id that the vendor left out is not an error: it is counted as missing and scored as an empty translation.

An id is never used for two different questions, and a question never has two ids. Do not renumber questions in only some of the files.

### Other points

- `source_lang` in a vendor file is `English` or `Hindi`. One vendor file holds both the English-to-language and the Hindi-to-language translations of that language. (An optional `target_lang` column is accepted; if present it must name the same language as the file.)
- Column names are matched ignoring upper and lower case, spaces and underscores (`Option A` works for `option_a`).
- The question and its four options are joined (one per line, without the A to D labels) and scored as **one text**, so the reference and the vendor output must be arranged the same way.
- A language with no vendor file, or only blank rows, gets **0 marks** (the score columns show 0). A single missing translation is scored as an empty sentence.
- Each of the 13 reference files is required; a missing reference file is an error.

### Where the sample files are

The dummy example is in the **`sample_data`** folder of the project, next to `app.py`:

```
sample_data/
  source/      source_english.csv, source_hindi.csv
  reference/   reference_assamese.csv ... reference_urdu.csv        (13 files)
  vendor/      vendor_assamese.csv ... vendor_urdu.csv              (12 files: Manipuri (Meitei) was left out on purpose)
```

The same files can be downloaded from the app (**Download the sample files**, a ZIP with the same three folders). They are **dummy**: the reference text is placeholder text that was not checked by native speakers, and the "vendor output" is the reference with some words removed or replaced. Do not use them as results. Recreate them with `python make_sample_data.py` (close the files in Excel first).

## Marking rules

| Metric | Rule (each slab starts at the value shown, on the unrounded score) |
|---|---|
| BLEU (Option B) | 70 or more: 12 · 60 to below 70: 11 · 50 to below 60: 10 · 40 to below 50: 9 · 30 to below 40: 8 · below 30: 0 |
| COMET | 0.85 or more: 10 · 0.75 to below 0.85: 7 · 0.65 to below 0.75: 4 · below 0.65: 0 |
| chrF++ | 75 or more: 5 · 65 to below 75: 3 · below 65: 0 |

The marks of each metric are the average of the 13 languages (equal weight). A language with no vendor output gets 0 marks under every rule.

The rules live in one place, `rfp_final_table.py`. The app and the command-line script both use it.

## Command-line script

`rfp_final_table.py` also works on its own. It merges three result files (`sarvam_bleu_results.csv`, `sarvam_comet_results.csv`, `sarvam_chrf_results.csv`, each with a `Target` column and a `Max(...)` column) into one table:

```
python rfp_final_table.py --bidder "Vendor" --out final_table.csv
```

Like the app, it uses BLEU Option B and averages each metric's marks over the languages (the last row), so its total is out of 27. It only merges existing result files and does no scoring or input checking: use the app for the official marks.

## Tests

The automated tests (validation, marking slabs, scoring engine with a mocked COMET model, the screens and the Windows scripts) are kept on the maintainer's computer and are not part of this repository.

## Files

| File | Purpose |
|---|---|
| `app.py` | The Streamlit web app |
| `evaluator.py` | Reads and checks the input files, computes the scores, applies the marks |
| `rfp_final_table.py` | The marking rules, and the command-line merge script |
| `make_sample_data.py` | Builds the dummy files in `sample_data/` (folders `source`, `reference`, `vendor`) |
| `sample_data/` | The dummy example files |
| `.env` / `.env.example` | Settings (`.env` is not committed) |
| `requirements.txt` | Pinned dependencies |
| `setup_model_env.bat`, `run_app.bat` | Windows helpers to install and start |

## Limits

- One vendor per run.
- The reference translations and the test set must be supplied by the committee; none are included.
- Human evaluation (15 marks) and the 25 out of 42 qualifying cutoff are not calculated.
- The app does not save results by itself; use the download buttons.
- The BLEU rule below 30 (0 marks) is the Commission's decision. The published clarification (Run1 3.4) still shows the older text (7, 6 and 5 marks there), so keep the Commission's written order with the project records.
- Option A and the Run1 3.3 fallback are not part of the app.
