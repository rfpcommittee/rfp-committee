"""
RFP Translation-Quality Evaluator - web UI.

CSV files go in (2 source files, 13 reference files, one vendor's output files, one file per language pair); BLEU, COMET
and chrF++ scores and marks come out, with BLEU marks under Option B.
The scoring engine is evaluator.py; the marking rules are in rfp_final_table.py.

Run:  streamlit run app.py     (or double-click run_app.bat)
"""
import hashlib
import io
import json
import os
import re
import zipfile

import pandas as pd
import streamlit as st

import evaluator as ev
import rfp_final_table as rft

SAMPLE_DIR = os.path.join(ev.BASE_DIR, "sample_data")
TOTAL_LANGS = len(ev.LANGUAGES)
TOTAL_PAIRS = TOTAL_LANGS * len(ev.SOURCES)

st.set_page_config(page_title="RFP Translation Evaluator", page_icon=":material/analytics:", layout="wide")

# Inline SVG icons (Lucide-style, stroke = currentColor so they follow the theme)
_SVG = {
    "chart": '<path d="M3 3v18h18"/><rect x="7" y="12" width="3" height="6" rx="1"/><rect x="12" y="8" width="3" height="10" rx="1"/><rect x="17" y="5" width="3" height="13" rx="1"/>',
    "sliders": '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
    "ruler": '<path d="M21.3 15.3 8.7 2.7a1 1 0 0 0-1.4 0L2.7 7.3a1 1 0 0 0 0 1.4l12.6 12.6a1 1 0 0 0 1.4 0l4.6-4.6a1 1 0 0 0 0-1.4z"/><path d="m7.5 10.5 2 2M10.5 7.5l2 2M13.5 4.5l2 2M4.5 13.5l2 2"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5M12 3v12"/>',
    "cpu": '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/>',
    "award": '<circle cx="12" cy="8" r="6"/><path d="M15.5 13.5 17 22l-5-3-5 3 1.5-8.5"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h8"/>',
    "languages": '<path d="m5 8 6 6M4 14l6-6 2-3M2 5h12M7 2h1M22 22l-5-10-5 10M14 18h6"/>',
    "book": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
    "users": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    "alert": '<path d="m10.3 3.9-8.5 14.7A2 2 0 0 0 3.5 21.6h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5M12 15V3"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="m8 12 3 3 5-6"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
}


def icon(name, size=20):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            f'style="vertical-align:-4px;margin-right:8px">{_SVG[name]}</svg>')


st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; max-width: 1250px;}
      .hero {padding: 1.5rem 1.8rem; border-radius: 16px; margin-bottom: 1.4rem; color: #fff;
             background: linear-gradient(120deg, #1b3157 0%, #2f5ea8 60%, #4b8bd6 100%);
             box-shadow: 0 6px 20px rgba(31,58,104,.25);}
      .hero h1 {margin: 0; font-size: 1.8rem; color: #fff; padding: 0;}
      .hero p {margin: .4rem 0 0; opacity: .88;}
      .step {display: flex; align-items: center; font-weight: 700; font-size: 1.15rem; margin: 1.6rem 0 .6rem;}
      .step .num {display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px;
                  border-radius: 50%; background: #2f5ea8; color: #fff; font-size: .85rem; margin-right: 10px;}
      .side-h {display: flex; align-items: center; font-weight: 700; font-size: 1.05rem; margin: .2rem 0 .6rem;}
      .fcard {display: flex; align-items: center; font-weight: 700; font-size: 1rem; margin-bottom: .1rem;}
      .fcard .pill {margin-left: auto; font-size: .72rem; font-weight: 600; padding: 2px 9px; border-radius: 99px;
                    background: rgba(47,94,168,.15); color: #4b8bd6;}
      .fsub {font-size: .82rem; opacity: .7; margin: 0 0 .4rem 30px;}
      .rule {margin: .5rem 0 .1rem; font-weight: 700;}
      .chip {display: inline-block; padding: 2px 9px; margin: 2px 3px 2px 0; border-radius: 8px; font-size: .8rem;
             background: rgba(128,128,128,.14);}
      .chip b {color: #4b8bd6;}
      .tag {display: inline-block; font-size: .75rem; font-weight: 700; padding: 2px 10px; border-radius: 99px;}
      .tag.on {background: rgba(46,160,67,.2); color: #2ea043;}
      .tag.off {background: rgba(128,128,128,.2); color: #8b949e;}
      .dot {display: inline-block; width: 11px; height: 11px; border-radius: 3px; margin: 0 4px 0 12px; vertical-align: -1px;}
      .pg {border: 1px solid rgba(128,128,128,.25); border-radius: 14px; padding: 1rem 1.2rem; margin: .4rem 0 1rem;
           background: rgba(128,128,128,.06);}
      .pg-top {display: flex; justify-content: space-between; align-items: baseline; font-weight: 700;}
      .pg-pct {font-size: 1.5rem; color: #4b8bd6;}
      .pg-bar {height: 12px; border-radius: 99px; background: rgba(128,128,128,.2); overflow: hidden; margin: .5rem 0 .8rem;}
      .pg-fill {height: 100%; border-radius: 99px; transition: width .4s ease;
                background: linear-gradient(90deg, #2f5ea8, #4b8bd6);}
      .pg-fill.live {background-image: repeating-linear-gradient(45deg, rgba(255,255,255,.28) 0 10px, rgba(255,255,255,0) 10px 20px),
                     linear-gradient(90deg, #2f5ea8, #4b8bd6); background-size: 28px 28px, 100% 100%;
                     animation: pgmove 1s linear infinite;}
      @keyframes pgmove {from {background-position: 0 0, 0 0;} to {background-position: 28px 0, 0 0;}}
      .pg-steps {display: flex; flex-wrap: wrap; gap: .5rem;}
      .pg-step {display: inline-flex; align-items: center; padding: 3px 12px; border-radius: 99px; font-size: .82rem;
                background: rgba(128,128,128,.14); opacity: .6;}
      .pg-step.done {background: rgba(46,160,67,.18); color: #2ea043; opacity: 1;}
      .pg-step.active {background: rgba(47,94,168,.2); color: #4b8bd6; opacity: 1; font-weight: 700;}
      .pg-msg {font-size: .85rem; opacity: .75; margin-top: .6rem;}
      div[data-testid="stMetric"] {background: rgba(128,128,128,.08); border-radius: 12px; padding: .8rem 1rem;
                                    border: 1px solid rgba(128,128,128,.15);}
      div[data-testid="stFileUploader"] section {border-radius: 12px; border: 1.5px dashed rgba(75,139,214,.6);}
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    f"""
    <div class="hero">
      <h1>{icon("chart", 30)}RFP Translation Quality Evaluator</h1>
      <p>Load the English and Hindi source questions, the reference translations (one file per language) and one vendor's output files (one file per language pair). You get BLEU, COMET
         and chrF++ scores with marks, and BLEU marks under Option B.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


def step(n, svg, text):
    st.markdown(f'<div class="step"><span class="num">{n}</span>{icon(svg, 22)}{text}</div>', unsafe_allow_html=True)


def chips(*items):
    return "".join(f'<span class="chip">{a} <b>→ {m}</b></span>' for a, m in items)


@st.cache_resource(show_spinner="Loading the COMET model (the first time it is downloaded, which can take a while)...")
def get_comet():
    return ev.load_comet_model()


MODEL_ON = ev.use_model()


class Progress:
    """A progress card: percentage, an animated bar and the stages (done / running / waiting)."""

    def __init__(self, with_comet):
        self.slot = st.empty()
        self.stages = [("folder", "Reading files", 0.0), ("chart", "BLEU and chrF++", 0.05)]
        if with_comet:
            self.stages.append(("cpu", "COMET model", 0.6))
        self.stages.append(("award", "Marks", 0.9))

    def progress(self, frac, text=""):
        frac = min(max(frac, 0.0), 1.0)
        current = max(i for i, (_, _, start) in enumerate(self.stages) if frac >= start)
        chips = ""
        for i, (svg, label, _) in enumerate(self.stages):
            state = "done" if (i < current or frac >= 1.0) else "active" if i == current else ""
            chips += f'<span class="pg-step {state}">{icon("check" if state == "done" else svg, 15)}{label}</span>'
        live = "" if frac >= 1.0 else " live"
        self.slot.markdown(
            f'<div class="pg"><div class="pg-top"><span>{icon("cpu")}Evaluating</span><span class="pg-pct">{frac * 100:.0f}%</span></div>'
            f'<div class="pg-bar"><div class="pg-fill{live}" style="width:{max(frac * 100, 2):.0f}%"></div></div>'
            f'<div class="pg-steps">{chips}</div><div class="pg-msg">{text}</div></div>',
            unsafe_allow_html=True)

    def empty(self):
        self.slot.empty()

# ---------- sidebar ----------
with st.sidebar:
    st.markdown(f'<div class="side-h">{icon("sliders")}Settings</div>', unsafe_allow_html=True)
    st.markdown('<div class="rule">COMET model</div>', unsafe_allow_html=True)
    if MODEL_ON:
        st.markdown('<span class="tag on">ON</span> &nbsp;set by USE_MODEL in .env', unsafe_allow_html=True)
        st.caption(f"Model: {ev.setting('COMET_CHECKPOINT') or ev.setting('COMET_MODEL', 'Unbabel/wmt22-comet-da')}")
        if not ev.comet_available():
            st.warning("The unbabel-comet library is not installed in this Python. Run setup_model_env.bat "
                       "(Python 3.10-3.12), or set USE_MODEL=false in .env.")
    else:
        st.markdown('<span class="tag off">OFF</span> &nbsp;set by USE_MODEL in .env', unsafe_allow_html=True)
        st.caption("COMET is skipped. BLEU and chrF++ are computed. Set USE_MODEL=true in .env and restart to include COMET.")

    st.divider()
    st.markdown(f'<div class="side-h">{icon("ruler")}Marking rules</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="rule">BLEU <small>(max {rft.BLEU_MAX})</small></div>
<b>Option B (Lenient)</b><br>{chips(("≥70", 12), ("60 to &lt;70", 11), ("50 to &lt;60", 10), ("40 to &lt;50", 9), ("30 to &lt;40", 8), ("below 30", 0))}
<small style="opacity:.7">Rule: 12 minus 1 for every 10 points (or part of 10) below 70, down to 8 at 30. Below 30 is 0. A language with no output gets 0.</small>
<div class="rule">COMET <small>(max {rft.COMET_MAX})</small></div>
{chips(("≥0.85", 10), ("≥0.75", 7), ("≥0.65", 4), ("below", 0))}
<div class="rule">chrF++ <small>(max {rft.CHRF_MAX})</small></div>
{chips(("≥75", 5), ("≥65", 3), ("below", 0))}
<p style="font-size:.78rem;opacity:.7;margin-top:.8rem">Slabs are half-open on the unrounded score.
For each language the higher of the English→T and Hindi→T scores is used.</p>
""",
        unsafe_allow_html=True,
    )

# ---------- step 1: input files ----------
step(1, "upload", "Input files")

bidder = st.text_input(
    "Vendor name (required)", placeholder="e.g. Sarvam", key="vendor_name",
    help="Shown in the results and used in the exported CSV files (inside the file and in the file name).",
)
if not bidder.strip():
    st.caption("Enter the vendor name first. Evaluate stays disabled until you do.")

SAMPLE_SUBDIRS = ("source", "reference", "vendor")
HAS_SAMPLE = all(os.path.isdir(os.path.join(SAMPLE_DIR, d)) for d in SAMPLE_SUBDIRS)

use_sample = st.toggle(
    "Use the dummy sample files (to try the app; not real data)",
    value=False,
    disabled=not HAS_SAMPLE,
    help="Created by make_sample_data.py in the sample_data folder (sub-folders source, reference and vendor).",
)


def sample_list(sub):
    folder = os.path.join(SAMPLE_DIR, sub)
    return [(f, os.path.join(folder, f)) for f in sorted(os.listdir(folder)) if f.lower().endswith(".csv")]


def sample_zip():
    """The dummy sample CSV files as one ZIP (folders source, reference, vendor), as a template for the layout."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for sub in SAMPLE_SUBDIRS:
            for name, path in sample_list(sub):
                z.write(path, arcname=f"sample_data/{sub}/{name}")
    return buf.getvalue()


if HAS_SAMPLE:
    st.download_button("Download the sample files (ZIP, folders source / reference / vendor)", sample_zip(),
                       file_name="sample_data.zip", mime="application/zip", icon=":material/download:",
                       help="The same dummy files, also saved in the sample_data folder of the project. "
                            "Use them as a template for the layout and the file names. They are not real data.")


def card_header(icon_name, title, pill, sub):
    st.markdown(f'<div class="fcard">{icon(icon_name)}{title}<span class="pill">{pill}</span></div>'
                f'<div class="fsub">{sub}</div>', unsafe_allow_html=True)


def named(files):
    return [(f.name, f) for f in files or []]


source_en = source_hi = None
refs_in, vendor_in = [], []
pill = "sample" if use_sample else "CSV"

with st.container(border=True):
    card_header("book", "Source questions", pill, "Two files: the questions in English and the same questions in Hindi")
    c_en, c_hi = st.columns(2)
    if use_sample:
        source_en = ("source_english.csv", os.path.join(SAMPLE_DIR, "source", "source_english.csv"))
        source_hi = ("source_hindi.csv", os.path.join(SAMPLE_DIR, "source", "source_hindi.csv"))
        c_en.markdown(f"English: **{source_en[0]}**")
        c_hi.markdown(f"Hindi: **{source_hi[0]}**")
    else:
        src_files = named(st.file_uploader("Source files (select both at once: source_english.csv and source_hindi.csv)",
                                           type="csv", key="sources", accept_multiple_files=True))
        by_lang = {"English": [], "Hindi": []}
        for item in src_files:
            langs = ev.source_from_filename(item[0])
            if len(langs) == 1:
                by_lang[next(iter(langs))].append(item)
            else:
                st.error(f"{item[0]}: the file name must contain either 'english' or 'hindi' (for example source_english.csv).")
        for lang, items in by_lang.items():
            if len(items) > 1:
                st.error(f"Two {lang} source files were selected ({', '.join(i[0] for i in items)}). Keep only one.")
        source_en = by_lang["English"][0] if len(by_lang["English"]) == 1 else None
        source_hi = by_lang["Hindi"][0] if len(by_lang["Hindi"]) == 1 else None
    st.caption("Columns: id, question, option_a, option_b, option_c, option_d")

with st.container(border=True):
    card_header("languages", "Reference translations", pill,
                f"{TOTAL_LANGS} files, one per language (reference_tamil.csv, reference_telugu.csv, ...)")
    if use_sample:
        refs_in = sample_list("reference")
        st.markdown(f"**{len(refs_in)} files** from sample_data/reference")
    else:
        refs_in = named(st.file_uploader("Reference files (select all 13 at once)", type="csv", key="refs",
                                         accept_multiple_files=True))
    st.caption("Columns: id, question, option_a, option_b, option_c, option_d. The language is read from the file name.")

with st.container(border=True):
    card_header("users", "Vendor output", pill,
                f"One vendor at a time. One file per language pair: {TOTAL_PAIRS} files (vendor_english_tamil.csv, vendor_hindi_tamil.csv, ...)")
    if use_sample:
        vendor_in = sample_list("vendor")
        st.markdown(f"**{len(vendor_in)} files** from sample_data/vendor")
    else:
        vendor_in = named(st.file_uploader("Vendor files (select all 26 at once, or all the files the vendor sent)", type="csv",
                                           key="vendor", accept_multiple_files=True))
    st.caption("Columns: id, question, option_a, option_b, option_c, option_d. The source and the target language are read "
               "from the file name. A pair the vendor did not translate has no file; a language with no output at all gets 0 marks.")

any_file = bool(source_en or source_hi or refs_in or vendor_in)
inputs = ev.load_inputs(source_en, source_hi, refs_in, vendor_in) if any_file else ev.Inputs()

validation = None
if inputs.source is not None and inputs.vendor is not None and not inputs.errors:
    validation = ev.validate(*inputs.as_tuple())

accepted = False
if any_file:
    n_ref, n_ven = len(inputs.ref_files), len(inputs.vendor_files)
    with st.expander(f":material/folder_open: Files found: {n_ref} of {TOTAL_LANGS} reference, {n_ven} of {TOTAL_PAIRS} vendor",
                     expanded=bool(inputs.errors)):
        found = pd.DataFrame({
            "Language": ev.LANGUAGES,
            "Reference file": [inputs.ref_files.get(lang, "missing") for lang in ev.LANGUAGES],
            "Vendor: English to language": [inputs.vendor_files.get(("English", lang), "none") for lang in ev.LANGUAGES],
            "Vendor: Hindi to language": [inputs.vendor_files.get(("Hindi", lang), "none") for lang in ev.LANGUAGES],
        })
        st.dataframe(found, hide_index=True, use_container_width=True, height=36 * (TOTAL_LANGS + 1) + 3)
        st.caption(f"Source: English {'loaded' if source_en else 'missing'}, Hindi {'loaded' if source_hi else 'missing'}.")
    for e in inputs.errors:
        st.error(e)

    if validation is not None:
        info = validation.info
        st.markdown(f'<div class="fcard" style="margin-top:.8rem">{icon("list")}Validation summary</div>', unsafe_allow_html=True)
        c = st.columns(4)
        c[0].metric("Questions", info["questions"])
        c[1].metric("Expected vendor rows", info["expected_rows"],
                    f"{info['questions']} × {info['languages']} languages × {info['directions']} directions", delta_color="off")
        c[2].metric("Received (non-blank)", info["received_rows"])
        c[3].metric("Missing", info["missing_rows"], "BLEU, chrF++: empty text. COMET: 0", delta_color="off")
        for e in validation.errors:
            st.error(e)

    if inputs.confirm and not inputs.errors:
        st.markdown(f'<div class="fcard" style="margin-top:.8rem;color:#d29922">{icon("alert")}Blank cells in the reference files</div>',
                    unsafe_allow_html=True)
        for msg in inputs.confirm:
            st.error(msg)
        st.caption("Nothing is set to 0 marks because of this. The reference of such a question is made from the cells that "
                   "are filled, so the vendor's full text is compared with a shorter reference, which can lower the vendor's "
                   "scores. The better fix is to complete the reference file.")
        tag = hashlib.sha256("|".join(inputs.confirm).encode("utf-8")).hexdigest()[:10]
        accepted = st.checkbox("Continue anyway with these blank cells (it will be written in the audit record)",
                               key=f"accept_{tag}")

    notes = list(inputs.warnings) + (list(validation.warnings) if validation is not None else [])
    if notes:
        with st.expander(f":material/warning: Warnings ({len(notes)})"):
            for w in notes:
                st.markdown(f"- {w}")
    if validation is not None:
        if validation.ok:
            st.success("The files match: the same question ids in every file, 13 reference languages. The evaluation can run.")
        with st.expander(":material/table_view: Vendor output received, by language and direction"):
            st.dataframe(validation.coverage, hide_index=True, use_container_width=True, height=36 * 14 + 3)

with st.expander(":material/help: File format help"):
    st.markdown(
        """
All files are **CSV, UTF-8** (in Excel: Save As, "CSV UTF-8"). Every question is a multiple-choice question: the
**question and each option (A to D) go in their own columns**. Download the sample ZIP above to see the layout.

| Folder | Files | Columns |
|---|---|---|
| `source` | `source_english.csv`, `source_hindi.csv` | `id, question, option_a, option_b, option_c, option_d` |
| `reference` | `reference_<language>.csv`, 13 files | `id, question, option_a, option_b, option_c, option_d` |
| `vendor` | `vendor_<source>_<language>.csv`, 26 files (one per language pair) | `id, question, option_a, option_b, option_c, option_d` |

- **Languages in the file names:** `assamese, bengali, gujarati, kannada, konkani, malayalam, manipuri_meitei, marathi,
  odia, punjabi, tamil, telugu, urdu`. A reference file is named like `reference_tamil.csv`.
- **Vendor files:** the source language (`english` or `hindi`) comes first, then the target language:
  `vendor_english_tamil.csv` is English to Tamil and `vendor_hindi_tamil.csv` is Hindi to Tamil. The source and the target
  language of a vendor file are read from its name.
- **The `id` rule:** the `id` is the question number. Inside one file every id appears **once** (no two questions share an
  id, and `Q1` and `q1` count as the same id). The **same question has the same id in every file**: in the English and the
  Hindi source, in the 13 reference files and in all the vendor files. The two source files must have exactly the same ids.
- The question and its four options are joined (one per line) and scored as **one text**. Column names are matched
  ignoring upper and lower case, spaces and underscores.

A language pair with no vendor file (or only blank rows) has no output: the other direction of that language is used, and a
language with no output in either direction gets **0 marks**. A missing single translation is scored as an empty sentence for
BLEU and chrF++, and as **0 for COMET**. A vendor file whose name does not show the pair, or two files for one pair, is an
**error** that names the file.
"""
    )

# ---------- step 2: evaluate ----------
step(2, "cpu", "Evaluate")
complete = inputs.source is not None and inputs.vendor is not None and not inputs.errors
ready = (complete and bool(bidder.strip()) and bool(validation and validation.ok)
         and (accepted or not inputs.confirm))
if not ready:
    left = ["Vendor name"] if not bidder.strip() else []
    if source_en is None:
        left.append("English source file")
    if source_hi is None:
        left.append("Hindi source file")
    if len(inputs.ref_files) < TOTAL_LANGS:
        left.append(f"reference files ({len(inputs.ref_files)} of {TOTAL_LANGS})")
    if not vendor_in:
        left.append("vendor files")
    if inputs.errors:
        left.append("fixes for the file errors above")
    if validation is not None and not validation.ok:
        left.append("fixes for the validation errors above")
    if inputs.confirm and not accepted:
        left.append("your decision on the blank reference cells")
    st.caption("Waiting for: " + ", ".join(left))
signature = (bidder.strip(), tuple(sorted(inputs.hashes.items())), MODEL_ON, accepted) if ready else None
run = st.button("Evaluate", type="primary", icon=":material/play_arrow:", disabled=not ready)

if run:
    bar = Progress(MODEL_ON)
    bar.progress(0.0, "Starting")
    try:
        model = get_comet() if MODEL_ON else None
        res = ev.evaluate(
            *inputs.as_tuple(), with_comet=MODEL_ON, comet_model=model,
            run_info=dict(vendor=bidder.strip(), hashes=dict(inputs.hashes),
                          accepted=list(inputs.confirm) if accepted else []),
            progress=bar.progress,
        )
    except (ev.InputError, ev.ModelUnavailable, ev.ScoringError) as e:
        bar.empty()
        st.error(str(e))
        st.stop()
    except Exception as e:  # anything unexpected is shown in full instead of failing silently
        bar.empty()
        st.exception(e)
        st.stop()
    bar.empty()
    st.session_state["result"] = dict(res=res, bidder=bidder.strip(), sample=use_sample, sig=signature)

# ---------- step 3: results ----------
saved = st.session_state.get("result")
if saved and saved.get("sig") != signature:
    # vendor name, a file or the COMET setting changed after this result was produced: it no longer describes the inputs
    del st.session_state["result"]
    saved = None
    st.info("The vendor name or an input file changed. The earlier result was cleared. Press Evaluate to score again.")
if saved:
    res, s = saved["res"], saved["res"].summary
    table = res.table
    who = saved["bidder"] or "Vendor"
    step(3, "award", "Results")
    st.subheader(who)
    if saved["sample"]:
        st.warning("These are dummy sample files. The numbers are not a real vendor's results.")
    if not s["with_comet"]:
        st.info("COMET was not computed (USE_MODEL is false), so the maximum is "
                f"{s['max_total']:g} marks, not {rft.BLEU_MAX + rft.COMET_MAX + rft.CHRF_MAX}.")

    k = st.columns(3)
    k[0].metric("Total (Option B)", f"{s['total']:.2f} / {s['max_total']:g}",
                f"BLEU {s['bleu']:.2f} / {rft.BLEU_MAX}   |   {s['pct']:.1f}%", delta_color="off")
    if s["with_comet"]:
        k[1].metric("COMET marks", f"{s['comet']:.2f} / {rft.COMET_MAX}")
    else:
        k[1].metric("COMET marks", "Not computed", "USE_MODEL=false", delta_color="off")
    k[2].metric("chrF++ marks", f"{s['chrf']:.2f} / {rft.CHRF_MAX}")

    st.markdown(
        '<small style="opacity:.75">Each metric\'s marks are the average over all 13 languages. '
        "BLEU marks use Option B. "
        "Human evaluation (15 marks) is not part of this tool.</small>",
        unsafe_allow_html=True,
    )

    mark_max = {"BLEU Marks": rft.BLEU_MAX, "COMET Marks": rft.COMET_MAX, "chrF++ Marks": rft.CHRF_MAX}

    def color_marks(col):
        mx = mark_max.get(col.name)
        if mx is None:
            return [""] * len(col)
        out = []
        for v in col:
            if pd.isna(v):
                out.append("")
            elif v >= mx:
                out.append("background-color: rgba(46,160,67,.28)")
            elif v <= 0:
                out.append("background-color: rgba(218,54,51,.28)")
            else:
                out.append("background-color: rgba(210,153,34,.25)")
        return out

    def color_status(col):
        return ["color: #da3633; font-weight: 700" if v in (ev.NO_OUTPUT, ev.NO_REFERENCE)
                else "color: #d29922" if v != "OK" and pd.notna(v) else "" for v in col]

    def show(df, last_row_bold=False):
        marks = [c for c in df.columns if c in mark_max]
        fmt = {c: "{:.2f}" for c in df.columns if ("BLEU" in c or "chrF++" in c) and "Marks" not in c}
        fmt.update({c: "{:.4f}" for c in df.columns if "COMET" in c and "Marks" not in c})
        fmt.update({c: (lambda v: f"{v:.2f}".rstrip("0").rstrip(".")) for c in marks})
        styler = df.style.apply(color_marks, subset=marks).apply(color_status, subset=["Status"]).format(fmt, na_rep="–")
        if last_row_bold:
            styler = styler.apply(lambda r: ["font-weight:700" if r.name == len(df) - 1 else ""] * len(r), axis=1)
        st.dataframe(styler, hide_index=True, use_container_width=True, height=36 * (len(df) + 1) + 3)

    if True:
        cols = ["Language", "Status", "BLEU En→T", "BLEU Hi→T", "Max BLEU", "BLEU Marks"]
        if s["with_comet"]:
            cols += ["COMET En→T", "COMET Hi→T", "Max COMET", "COMET Marks"]
        cols += ["chrF++ En→T", "chrF++ Hi→T", "Max chrF++", "chrF++ Marks"]
        view = table[cols].copy()
        avg = {c: view[c].mean() for c in mark_max if c in view.columns}
        avg_row = {c: float("nan") for c in view.columns}
        avg_row.update(avg)
        avg_row["Language"] = "Average of 13 languages (marks)"
        avg_row["Status"] = ""
        view = pd.concat([view, pd.DataFrame([avg_row])], ignore_index=True)
        view["Status"] = view["Status"].astype(object)
        show(view, last_row_bold=True)
        st.markdown(
            '<span class="dot" style="background:rgba(46,160,67,.6);margin-left:0"></span>full marks'
            '<span class="dot" style="background:rgba(210,153,34,.6)"></span>partial'
            '<span class="dot" style="background:rgba(218,54,51,.6)"></span>zero'
            '<br><small style="opacity:.7">Max is the higher of En→T and Hi→T. – means no output for that direction. '
            "A language with no vendor output shows 0 for its scores and 0 marks.</small>",
            unsafe_allow_html=True,
        )

    with st.expander(":material/bar_chart: BLEU marks by language (Option B)"):
        st.bar_chart(table.set_index("Language")[["BLEU Marks"]])

    m = res.meta
    detail_df, summary_df = ev.export_tables(res, who)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", who).strip("_") or "vendor"
    audit_json = json.dumps(ev.audit_record(res), indent=2, ensure_ascii=False).encode("utf-8")

    st.markdown(f'<div class="fcard" style="margin-top:1rem">{icon("download")}Downloads</div>', unsafe_allow_html=True)
    st.caption(f"Exported files carry the vendor name “{who}”, the run ID and the scoring policy, in the columns and "
               "(for the vendor name) in the file name. The audit file also has the input file hashes and the validation summary.")
    d1, d2, d3 = st.columns(3)
    d1.download_button("Download per-language results (CSV)", detail_df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"{stem}_per_language.csv", mime="text/csv", use_container_width=True,
                       icon=":material/download:")
    d2.download_button("Download summary, Option B (CSV)", summary_df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"{stem}_summary.csv", mime="text/csv", use_container_width=True,
                       icon=":material/download:")
    d3.download_button("Download audit record (JSON)", audit_json, file_name=f"{stem}_audit.json",
                       mime="application/json", use_container_width=True, icon=":material/download:")

    with st.expander(f":material/fact_check: Evaluation details ({len(res.warnings)} warning(s))"):
        st.markdown(
            f"- Run ID: `{m['run_id']}` at {m['timestamp_utc']} (UTC)\n"
            f"- Scoring policy: {m['scoring_policy']}\n"
            f"- Questions: **{m['questions']}**; vendor rows received {m['received_rows']} of {m['expected_rows']} expected\n"
            + "".join(f"- SHA-256, {k_}: `{v_}`\n" for k_, v_ in m["input_sha256"].items())
            + f"- Python {m['python']}, pandas {m['pandas']}\n"
            f"- sacreBLEU **{m['sacrebleu']}**\n"
            f"- BLEU signature: `{m['bleu_signature']}`\n"
            f"- chrF++ signature: `{m['chrf_signature']}`\n"
            f"- COMET: **{m['comet'] or 'not computed'}**"
            + (f" (batch size {m['comet_batch_size']}, GPUs {m['comet_gpus']})" if m["comet"] else "") + "\n"
            f"- Missing translations: {m['missing_translation_rule']}\n"
            + (("- **Accepted by the user:** " + "; ".join(m["accepted_issues"]) + "\n") if m["accepted_issues"] else "")
        )
        if res.warnings:
            st.markdown("**Warnings**")
            for w in res.warnings:
                st.markdown(f"- {w}")
        else:
            st.markdown("No warnings.")
