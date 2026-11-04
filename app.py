"""
RFP Translation-Quality Evaluator - web UI.

Three CSV files go in (source questions, reference translations, one vendor's output); BLEU, COMET and chrF++ scores
and marks come out, with BLEU marks shown under both Option A and Option B.
The scoring engine is evaluator.py; the marking rules are in rfp_final_table.py.

Run:  streamlit run app.py     (or double-click run_app.bat)
"""
import os
import re

import pandas as pd
import streamlit as st

import evaluator as ev
import rfp_final_table as rft

SAMPLE_DIR = os.path.join(ev.BASE_DIR, "sample_data")
TOTAL_LANGS = len(ev.LANGUAGES)

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
      <p>Load the source questions, the 13-language reference translations and one vendor's output. You get BLEU, COMET
         and chrF++ scores with marks, and BLEU marks under both Option A and Option B.</p>
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

# ---------- sidebar ----------
with st.sidebar:
    st.markdown(f'<div class="side-h">{icon("sliders")}Settings</div>', unsafe_allow_html=True)
    bidder = st.text_input("Vendor name", placeholder="e.g. Sarvam")

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
<b>Standard (Option A)</b><br>{chips(("≥70", 12), ("60 to &lt;70", 10), ("50 to &lt;60", 6), ("&lt;50", 0))}<br>
<b>Lenient (Option B)</b><br>{chips(("≥70", 12), ("below 70", "12 − ⌈(70−BLEU)/10⌉, min 0"))}
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

FILES = [
    dict(key="source", title="Source questions", sub="English and Hindi", icon="book",
         cols="id, english, hindi", reader=ev.read_source, sample="1_source_questions.csv"),
    dict(key="refs", title="Reference translations", sub="Human translations in the 13 languages", icon="languages",
         cols="id, then one column per language", reader=ev.read_refs, sample="2_reference_translations.csv"),
    dict(key="vendor", title="Vendor output", sub="One vendor at a time", icon="users",
         cols="id, source_lang, target_lang, translation", reader=ev.read_vendor, sample="3_vendor_output.csv"),
]


def preview(key, df):
    if key == "source":
        return f"{len(df)} questions"
    if key == "refs":
        found = [c for c in df.columns if c != "id"]
        miss = [lang for lang in ev.LANGUAGES if lang not in found]
        return f"{len(df)} questions, {len(found)} of {TOTAL_LANGS} languages" + (f". Missing: {', '.join(miss)}" if miss else "")
    pairs = df.groupby(["source_lang", "target_lang"]).ngroups
    return f"{len(df)} rows, {pairs} of {TOTAL_LANGS * 2} language pairs"


use_sample = st.toggle(
    "Use the dummy sample files (to try the app; not real data)",
    value=False,
    disabled=not os.path.isdir(SAMPLE_DIR),
    help="Created by make_sample_data.py in the sample_data folder.",
)

parsed = {}
for col, f in zip(st.columns(3), FILES):
    with col, st.container(border=True):
        st.markdown(
            f'<div class="fcard">{icon(f["icon"])}{f["title"]}<span class="pill">{"sample" if use_sample else "CSV"}</span></div>'
            f'<div class="fsub">{f["sub"]}</div>',
            unsafe_allow_html=True,
        )
        src = None
        if use_sample:
            src = os.path.join(SAMPLE_DIR, f["sample"])
            st.markdown(f"Selected: **{f['sample']}**")
        else:
            up = st.file_uploader(f["title"], type="csv", key=f["key"], label_visibility="collapsed")
            if up is not None:
                src = up
                st.markdown(f"Selected: **{up.name}**")
        st.caption(f"Columns: {f['cols']}")
        parsed[f["key"]] = None
        if src is not None:
            try:
                parsed[f["key"]] = f["reader"](src)
                st.success(preview(f["key"], parsed[f["key"]]))
            except ev.InputError as e:
                st.error(str(e))

with st.expander("File format help"):
    st.markdown(
        """
All three files are **CSV, UTF-8**. An id is the question number and must be the same in all three files.

- **Source questions:** `id, english, hindi`, one row per question.
- **Reference translations:** `id` plus one column per target language, named exactly like the languages
  (Assamese, Bengali, Gujarati, Kannada, Konkani, Malayalam, Manipuri (Meitei), Marathi, Odia, Punjabi, Tamil, Telugu, Urdu).
- **Vendor output:** `id, source_lang, target_lang, translation`, one row per question per language per direction.
  `source_lang` is English or Hindi; `target_lang` is one of the 13 languages.

**Multiple-choice questions:** put the question and its four options in the **same cell**, one per line
(`question`, `(A) ...`, `(B) ...`, `(C) ...`, `(D) ...`). Each question is scored as one text, and the vendor output
must use the same layout. In Excel press Alt+Enter for a new line inside a cell; CSV keeps it.

A language (or direction) with no vendor output gets **0 marks**. A missing single translation is scored as an empty sentence.
"""
    )

# ---------- step 2: evaluate ----------
step(2, "cpu", "Evaluate")
ready = all(v is not None for v in parsed.values())
if not ready:
    left = [f["title"] for f in FILES if parsed[f["key"]] is None]
    st.caption("Waiting for: " + ", ".join(left))
run = st.button("Evaluate", type="primary", icon=":material/play_arrow:", disabled=not ready)

if run:
    bar = st.progress(0.0, text="Starting")
    try:
        model = get_comet() if MODEL_ON else None
        res = ev.evaluate(
            parsed["source"], parsed["refs"], parsed["vendor"], with_comet=MODEL_ON, comet_model=model,
            progress=lambda frac, msg: bar.progress(min(max(frac, 0.0), 1.0), text=msg),
        )
    except (ev.InputError, ev.ModelUnavailable) as e:
        bar.empty()
        st.error(str(e))
        st.stop()
    except Exception as e:  # anything unexpected is shown in full instead of failing silently
        bar.empty()
        st.exception(e)
        st.stop()
    bar.empty()
    st.session_state["result"] = dict(res=res, bidder=bidder.strip(), sample=use_sample)

# ---------- step 3: results ----------
saved = st.session_state.get("result")
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

    k = st.columns(4)
    k[0].metric("Total, Option A (Standard)", f"{s['total_a']:.2f} / {s['max_total']:g}",
                f"BLEU {s['bleu_a']:.2f} / {rft.BLEU_MAX}   |   {s['pct_a']:.1f}%", delta_color="off")
    k[1].metric("Total, Option B (Lenient)", f"{s['total_b']:.2f} / {s['max_total']:g}",
                f"BLEU {s['bleu_b']:.2f} / {rft.BLEU_MAX}   |   {s['pct_b']:.1f}%", delta_color="off")
    if s["with_comet"]:
        k[2].metric("COMET marks", f"{s['comet']:.2f} / {rft.COMET_MAX}", "same under A and B", delta_color="off")
    else:
        k[2].metric("COMET marks", "Not computed", "USE_MODEL=false", delta_color="off")
    k[3].metric("chrF++ marks", f"{s['chrf']:.2f} / {rft.CHRF_MAX}", "same under A and B", delta_color="off")

    st.markdown(
        '<small style="opacity:.75">Each metric\'s marks are the average over all 13 languages. '
        "Option A is the default. Option B applies only if <b>every</b> vendor scores 0 BLEU marks under Option A, "
        "so compare with the other vendors before using Option B. "
        "Human evaluation (15 marks) is not part of this tool.</small>",
        unsafe_allow_html=True,
    )

    mark_max = {"BLEU Marks (A)": rft.BLEU_MAX, "BLEU Marks (B)": rft.BLEU_MAX,
                "COMET Marks": rft.COMET_MAX, "chrF++ Marks": rft.CHRF_MAX}

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

    tab1, tab2 = st.tabs(["Marks by language", "All scores (both directions)"])
    with tab1:
        cols = ["Language", "Status", "Max BLEU", "BLEU Marks (A)", "BLEU Marks (B)"]
        if s["with_comet"]:
            cols += ["Max COMET", "COMET Marks"]
        cols += ["Max chrF++", "chrF++ Marks"]
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
            '<br><small style="opacity:.7">A language with no vendor output shows 0 for its scores and 0 marks.</small>',
            unsafe_allow_html=True,
        )
    with tab2:
        show(table)
        st.caption("– means the vendor gave no output for that direction. The Max column uses the higher available score.")

    st.markdown(f'<div class="fcard" style="margin-top:1rem">{icon("languages")}BLEU marks, Option A and Option B</div>',
                unsafe_allow_html=True)
    st.bar_chart(table.set_index("Language")[["BLEU Marks (A)", "BLEU Marks (B)"]], stack=False)

    summary_df = pd.DataFrame([
        {"Vendor": who, "BLEU option": "A (Standard)", "BLEU marks": s["bleu_a"], "COMET marks": s["comet"],
         "chrF++ marks": s["chrf"], "Total": s["total_a"], "Max": s["max_total"], "Percent": s["pct_a"]},
        {"Vendor": who, "BLEU option": "B (Lenient)", "BLEU marks": s["bleu_b"], "COMET marks": s["comet"],
         "chrF++ marks": s["chrf"], "Total": s["total_b"], "Max": s["max_total"], "Percent": s["pct_b"]},
    ]).round(2)
    detail_df = table.copy()
    detail_df.insert(0, "Vendor", who)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", who).strip("_") or "vendor"

    d1, d2 = st.columns(2)
    d1.download_button("Download per-language results (CSV)", detail_df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"{stem}_per_language.csv", mime="text/csv", use_container_width=True,
                       icon=":material/download:")
    d2.download_button("Download summary, Option A and B (CSV)", summary_df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"{stem}_summary.csv", mime="text/csv", use_container_width=True,
                       icon=":material/download:")

    with st.expander(f"Evaluation details ({len(res.warnings)} warning(s))"):
        m = res.meta
        st.markdown(
            f"- Questions: **{m['questions']}**\n"
            f"- sacreBLEU **{m['sacrebleu']}**\n"
            f"- BLEU signature: `{m['bleu_signature']}`\n"
            f"- chrF++ signature: `{m['chrf_signature']}`\n"
            f"- COMET: **{m['comet'] or 'not computed'}**"
        )
        if res.warnings:
            st.markdown("**Warnings**")
            for w in res.warnings:
                st.markdown(f"- {w}")
        else:
            st.markdown("No warnings.")
