"""
Evaluation engine for the RFP translation-quality marks (BLEU, COMET, chrF++).

One vendor is evaluated at a time from three CSV files:
  1. source questions         id, english, hindi
  2. reference translations   id + one column per target language (13 languages)
  3. vendor output            id, source_lang, target_lang, translation

Scores follow the RFP clarification (Run1): sacreBLEU corpus BLEU with the flores200 tokenizer, chrF++ (word_order=2),
COMET (Unbabel/wmt22-comet-da) and the higher of the English->T and Hindi->T scores for each language.
All slab / marking rules stay in rfp_final_table.py; this file only computes scores and applies those rules.
"""
import importlib.metadata as md
import math
import os
from dataclasses import dataclass, field

import pandas as pd

import rfp_final_table as rft

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LANGUAGES = ["Assamese", "Bengali", "Gujarati", "Kannada", "Konkani", "Malayalam", "Manipuri (Meitei)",
             "Marathi", "Odia", "Punjabi", "Tamil", "Telugu", "Urdu"]
SOURCES = ("English", "Hindi")
SHORT = {"English": "En", "Hindi": "Hi"}

NO_OUTPUT = "No output"
NO_REFERENCE = "No reference"


class InputError(ValueError):
    """A problem in an input file that the user can fix."""


class ModelUnavailable(RuntimeError):
    """USE_MODEL is on but the COMET model / library cannot be used."""


def _key(s):
    return "".join(str(s).lower().split())


_LANG_MAP = {_key(lang): lang for lang in LANGUAGES}
_LANG_MAP.update({"manipuri": "Manipuri (Meitei)", "meitei": "Manipuri (Meitei)"})
_SRC_MAP = {"english": "English", "en": "English", "eng": "English",
            "hindi": "Hindi", "hi": "Hindi", "hin": "Hindi"}


# ---------------------------------------------------------------- settings (.env)
def _dotenv():
    out = {}
    path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                out[k.strip()] = v.split(" #")[0].strip().strip('"').strip("'")
    return out


def setting(name, default=""):
    """Real environment variable first, then .env, then the default."""
    v = os.environ.get(name)
    if not v:
        v = _dotenv().get(name, "")
    return v if v else default


def use_model():
    return setting("USE_MODEL", "false").strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------- reading the three files
def _read_csv(file, label):
    try:
        if hasattr(file, "seek"):
            file.seek(0)
        df = pd.read_csv(file, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise InputError(f"{label}: the file is not UTF-8. Save it as 'CSV UTF-8'.") from None
    except pd.errors.EmptyDataError:
        raise InputError(f"{label}: the file is empty.") from None
    except pd.errors.ParserError as e:
        raise InputError(f"{label}: cannot read the CSV ({e}).") from None
    df.columns = [str(c).strip() for c in df.columns]
    for c in df.columns:
        df[c] = df[c].str.strip()
    if df.empty:
        raise InputError(f"{label}: the file has no data rows.")
    return df


def _need(df, cols, label):
    low = {c.lower(): c for c in df.columns}
    missing = [c for c in cols if c not in low]
    if missing:
        raise InputError(f"{label}: missing column(s) {missing}. Columns found: {list(df.columns)}")
    return df.rename(columns={low[c]: c for c in cols})


def _check_ids(df, label):
    if (df["id"] == "").any():
        raise InputError(f"{label}: some rows have an empty id.")
    dup = df.loc[df["id"].duplicated(), "id"].tolist()
    if dup:
        raise InputError(f"{label}: duplicate id(s) {dup[:5]}.")


def read_source(file):
    label = "Source questions"
    df = _need(_read_csv(file, label), ["id", "english", "hindi"], label)[["id", "english", "hindi"]]
    _check_ids(df, label)
    blank = df.loc[(df["english"] == "") | (df["hindi"] == ""), "id"].tolist()
    if blank:
        raise InputError(f"{label}: English or Hindi text is empty for id(s) {blank[:5]}.")
    return df


def read_refs(file):
    """Returns a frame with 'id' + one column per recognised language. attrs['ignored'] lists other columns."""
    label = "Reference translations"
    df = _need(_read_csv(file, label), ["id"], label)
    _check_ids(df, label)
    langs, ignored = {}, []
    for c in df.columns:
        if c == "id":
            continue
        lang = _LANG_MAP.get(_key(c))
        if lang is None:
            ignored.append(c)
        elif lang in langs:
            raise InputError(f"{label}: language '{lang}' appears twice ({langs[lang]!r} and {c!r}).")
        else:
            langs[lang] = c
    if not langs:
        raise InputError(f"{label}: no language columns recognised. Expected columns named like: {', '.join(LANGUAGES)}.")
    out = df[["id"] + list(langs.values())].rename(columns={v: k for k, v in langs.items()})
    out.attrs["ignored"] = ignored
    return out


def read_vendor(file):
    """Returns the usable rows. attrs['ignored_rows'] / attrs['ignored_examples'] describe rows that were skipped."""
    label = "Vendor output"
    df = _need(_read_csv(file, label), ["id", "source_lang", "target_lang", "translation"], label)
    df = df[["id", "source_lang", "target_lang", "translation"]].copy()
    src = df["source_lang"].map(lambda s: _SRC_MAP.get(_key(s)))
    tgt = df["target_lang"].map(lambda s: _LANG_MAP.get(_key(s)))
    bad = src.isna() | tgt.isna() | (df["id"] == "")
    examples = sorted({f"{a} -> {b}" for a, b in zip(df.loc[bad, "source_lang"], df.loc[bad, "target_lang"])})[:5]
    df["source_lang"], df["target_lang"] = src, tgt
    df = df[~bad]
    if df.empty:
        raise InputError(f"{label}: no usable rows. source_lang must be English or Hindi and target_lang one of "
                         f"the 13 languages.")
    dup = df[df.duplicated(["id", "source_lang", "target_lang"], keep=False)]
    if not dup.empty:
        r = dup.iloc[0]
        raise InputError(f"{label}: more than one translation for id {r['id']} "
                         f"({r['source_lang']} -> {r['target_lang']}).")
    df.attrs["ignored_rows"] = int(bad.sum())
    df.attrs["ignored_examples"] = examples
    return df


# ---------------------------------------------------------------- COMET
def comet_available():
    try:
        md.version("unbabel-comet")
        return True
    except md.PackageNotFoundError:
        return False


def load_comet_model():
    """Loads (and, the first time, downloads from Hugging Face) the COMET model named in .env."""
    try:
        from comet import download_model, load_from_checkpoint
    except ImportError:
        raise ModelUnavailable(
            "USE_MODEL is true but the 'unbabel-comet' library is not installed in this Python. "
            "It needs Python 3.10-3.12: run setup_model_env.bat, or set USE_MODEL=false in .env."
        ) from None
    ckpt = setting("COMET_CHECKPOINT")
    try:
        path = ckpt if ckpt else download_model(setting("COMET_MODEL", "Unbabel/wmt22-comet-da"))
        return load_from_checkpoint(path)
    except Exception as e:  # download / load problems are shown to the user as they are
        raise ModelUnavailable(f"Could not load the COMET model: {e}") from e


# ---------------------------------------------------------------- scoring
@dataclass
class Result:
    table: pd.DataFrame
    summary: dict
    warnings: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)


def _best(*vals):
    ok = [v for v in vals if v is not None and not math.isnan(v)]
    return max(ok) if ok else float("nan")


def evaluate(source, refs, vendor, with_comet=False, comet_model=None, progress=None):
    from sacrebleu.metrics import BLEU, CHRF
    import sacrebleu

    tick = progress or (lambda frac, msg: None)
    warnings = []

    ids = list(source["id"])
    id_set = set(ids)
    src_text = {"English": dict(zip(source["id"], source["english"])),
                "Hindi": dict(zip(source["id"], source["hindi"]))}
    ref_text = {lang: dict(zip(refs["id"], refs[lang])) for lang in refs.columns if lang != "id"}

    for c in refs.attrs.get("ignored", []):
        warnings.append(f"Reference file: column '{c}' is not a known language and was ignored.")
    extra = set(refs["id"]) - id_set
    if extra:
        warnings.append(f"Reference file: {len(extra)} id(s) are not in the source questions and were ignored.")
    if vendor.attrs.get("ignored_rows"):
        ex = vendor.attrs.get("ignored_examples") or []
        warnings.append(f"Vendor file: {vendor.attrs['ignored_rows']} row(s) skipped (unknown language or empty id)"
                        + (f", e.g. {', '.join(ex)}." if ex else "."))
    extra = set(vendor["id"]) - id_set
    if extra:
        warnings.append(f"Vendor file: {len(extra)} id(s) are not in the source questions and were ignored.")

    vendor_text = {}
    for (s, t), g in vendor.groupby(["source_lang", "target_lang"]):
        vendor_text[(s, t)] = dict(zip(g["id"], g["translation"]))

    bleu_m = BLEU(tokenize="flores200")
    chrf_m = CHRF(word_order=2)

    scores = {}   # (language, source) -> {"bleu", "chrf", "comet"}
    groups = {}   # (language, source) -> (src list, mt list, ref list)
    pairs = [(lang, s) for lang in LANGUAGES for s in SOURCES]
    for n, (lang, s) in enumerate(pairs):
        tick(0.05 + 0.5 * n / len(pairs), f"BLEU and chrF++: {s} to {lang}")
        rt, vt = ref_text.get(lang), vendor_text.get((s, lang))
        if rt is None or vt is None or not any(vt.values()):
            continue
        use = [i for i in ids if rt.get(i, "")]
        if not use:
            continue
        if len(use) < len(ids) and s == SOURCES[0]:
            warnings.append(f"{lang}: {len(ids) - len(use)} question(s) have no reference and are left out.")
        missing = sum(1 for i in use if not vt.get(i, ""))
        if missing:
            warnings.append(f"{lang} ({s} to {lang}): {missing} of {len(use)} translation(s) missing; scored as empty.")
        mts = [vt.get(i, "") for i in use]
        rfs = [rt[i] for i in use]
        scores[(lang, s)] = {"bleu": bleu_m.corpus_score(mts, [rfs]).score,
                             "chrf": chrf_m.corpus_score(mts, [rfs]).score}
        groups[(lang, s)] = ([src_text[s][i] for i in use], mts, rfs)

    comet_info = None
    if with_comet:
        if comet_model is None:
            raise ModelUnavailable("COMET was requested but no model was loaded.")
        data, spans = [], {}
        for key, (srcs, mts, rfs) in groups.items():
            a = len(data)
            data += [{"src": a_, "mt": b_, "ref": c_} for a_, b_, c_ in zip(srcs, mts, rfs)]
            spans[key] = (a, len(data))
        tick(0.6, f"COMET model scoring {len(data)} sentence pairs (this is the slow step)")
        out = comet_model.predict(data, batch_size=int(setting("COMET_BATCH_SIZE", "16")),
                                  gpus=int(setting("COMET_GPUS", "0")), progress_bar=False)
        seg = list(out.scores if hasattr(out, "scores") else out[0])
        for key, (a, b) in spans.items():
            scores[key]["comet"] = sum(seg[a:b]) / (b - a)
        try:
            ver = md.version("unbabel-comet")
        except md.PackageNotFoundError:
            ver = "unknown"
        comet_info = f"{setting('COMET_CHECKPOINT') or setting('COMET_MODEL', 'Unbabel/wmt22-comet-da')} (unbabel-comet {ver})"

    tick(0.9, "Applying marks")
    nan = float("nan")
    rows = []
    for lang in LANGUAGES:
        row = {"Language": lang}
        got = [s for s in SOURCES if (lang, s) in scores]
        if got:
            status = "OK" if len(got) == len(SOURCES) else f"Only {got[0]} source"
        elif lang not in ref_text or not any(ref_text[lang].values()):
            status = NO_REFERENCE
        else:
            status = NO_OUTPUT
        row["Status"] = status

        metrics = [("BLEU", "bleu"), ("chrF++", "chrf")] + ([("COMET", "comet")] if with_comet else [])
        maxima = {}
        for name, k in metrics:
            vals = []
            for s in SOURCES:
                v = scores.get((lang, s), {}).get(k, nan)
                row[f"{name} {SHORT[s]}→T"] = v
                vals.append(v)
            m = _best(*vals)
            maxima[name] = 0.0 if math.isnan(m) else m       # no score at all counts as 0
            row[f"Max {name}"] = maxima[name]

        scored = status not in (NO_OUTPUT, NO_REFERENCE)
        row["BLEU Marks (A)"] = rft.bleu_a(maxima["BLEU"]) if scored else 0
        row["BLEU Marks (B)"] = rft.bleu_b(maxima["BLEU"]) if scored else 0
        if with_comet:
            row["COMET Marks"] = rft.comet_marks(maxima["COMET"]) if scored else 0
        row["chrF++ Marks"] = rft.chrf_marks(maxima["chrF++"]) if scored else 0
        rows.append(row)

    table = pd.DataFrame(rows)
    order = ["Language", "Status"]
    for name in ["BLEU"] + (["COMET"] if with_comet else []) + ["chrF++"]:
        order += [f"{name} En→T", f"{name} Hi→T", f"Max {name}"]
    order += ["BLEU Marks (A)", "BLEU Marks (B)"] + (["COMET Marks"] if with_comet else []) + ["chrF++ Marks"]
    table = table[order]

    n = len(LANGUAGES)

    def mean(col):
        return float(table[col].sum()) / n

    bleu_a, bleu_b, chrf = mean("BLEU Marks (A)"), mean("BLEU Marks (B)"), mean("chrF++ Marks")
    comet = mean("COMET Marks") if with_comet else None
    max_total = rft.BLEU_MAX + rft.CHRF_MAX + (rft.COMET_MAX if with_comet else 0)
    rest = chrf + (comet or 0)
    summary = {
        "bleu_a": bleu_a, "bleu_b": bleu_b, "comet": comet, "chrf": chrf,
        "total_a": bleu_a + rest, "total_b": bleu_b + rest, "max_total": max_total,
        "pct_a": 100 * (bleu_a + rest) / max_total, "pct_b": 100 * (bleu_b + rest) / max_total,
        "with_comet": with_comet, "languages": n,
    }
    meta = {
        "questions": len(ids),
        "sacrebleu": sacrebleu.__version__,
        "bleu_signature": str(bleu_m.get_signature()),
        "chrf_signature": str(chrf_m.get_signature()),
        "comet": comet_info,
    }
    tick(1.0, "Done")
    return Result(table=table, summary=summary, warnings=warnings, meta=meta)
