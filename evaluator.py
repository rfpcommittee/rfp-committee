"""
Evaluation engine for the RFP translation-quality marks (BLEU, COMET, chrF++).

One vendor is evaluated at a time. The input is a set of CSV files, one per language:
  source/      source_english.csv, source_hindi.csv          id, question, option_a, option_b, option_c, option_d
  reference/   reference_<language>.csv  (13 files)          id, question, option_a, option_b, option_c, option_d
  vendor/      vendor_<source>_<language>.csv (27 files)   id, question, option_a, option_b, option_c, option_d
               (vendor_english_tamil.csv = English to Tamil, vendor_hindi_tamil.csv = Hindi to Tamil, and one extra
               file vendor_english_hindi.csv = English to Hindi, whose reference is the Hindi source file)
The language of a reference file, and the source and target language of a vendor file, come from the file name. The
`id` of a question must be unique inside a file and identical for the same question in every file.
Every question is a multiple-choice question; its question and four options are joined (one per line) and scored
as one text.

Scores follow the RFP clarification (Run1): sacreBLEU corpus BLEU with the flores200 tokenizer, chrF++ (word_order=2),
COMET (Unbabel/wmt22-comet-da) and the higher of the English->T and Hindi->T scores for each language.
All slab / marking rules stay in rfp_final_table.py; this file only computes scores and applies those rules.
BLEU marks use Option B only (see rfp_final_table.POLICY_ID).
"""
import datetime as dt
import hashlib
import importlib.metadata as md
import math
import os
import platform
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import pandas as pd

import rfp_final_table as rft

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LANGUAGES = ["Assamese", "Bengali", "Gujarati", "Kannada", "Konkani", "Malayalam", "Manipuri (Meitei)",
             "Marathi", "Odia", "Punjabi", "Tamil", "Telugu", "Urdu"]
SOURCES = ("English", "Hindi")
HINDI = "Hindi"                      # extra target: English to Hindi, reference = the Hindi source file; reported, not averaged
PAIRS = [(s, lang) for lang in LANGUAGES for s in SOURCES] + [("English", HINDI)]
SHORT = {"English": "En", "Hindi": "Hi"}
FIELDS = ["question", "option_a", "option_b", "option_c", "option_d"]
_COL = re.compile(r"^(.+)_(" + "|".join(FIELDS) + r")$")

NO_OUTPUT = "No output"
NO_REFERENCE = "No reference"


class InputError(ValueError):
    """A problem in an input file that the user can fix."""


class ModelUnavailable(RuntimeError):
    """USE_MODEL is on but the COMET model / library cannot be used."""


class ScoringError(RuntimeError):
    """A metric returned something unusable (wrong number of scores, NaN, infinity)."""


def _key(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _slug(lang):
    """Column prefix of a language: lower case, words joined by underscores (manipuri_meitei)."""
    return re.sub(r"[^a-z0-9]+", "_", lang.lower()).strip("_")


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


# ---------------------------------------------------------------- reading the files
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
    names = list(df.columns)
    # pandas renames a repeated header "x" to "x.1"; spellings that differ only in case, spaces or "_" are also ambiguous
    groups = {}
    for c in names:
        stripped = re.sub(r"\.\d+$", "", c)
        base = stripped if stripped != c and stripped in names else c
        groups.setdefault(_key(base), []).append(c)
    dup = [v[0] for v in groups.values() if len(v) > 1]
    if dup:
        raise InputError(f"{label}: duplicate column name(s) {dup}. Each column must appear once.")
    for c in df.columns:
        df[c] = df[c].str.strip()
    if df.empty:
        raise InputError(f"{label}: the file has no data rows.")
    return df


def file_sha256(file):
    """SHA-256 of an input (a path, or an uploaded file object with getvalue())."""
    if isinstance(file, (str, os.PathLike)):
        with open(file, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    return hashlib.sha256(file.getvalue()).hexdigest()


def _need(df, cols, label):
    """Checks that the columns exist (matched ignoring case, spaces and '_') and gives them their standard names."""
    by_key = {_key(c): c for c in df.columns}
    missing = [c for c in cols if _key(c) not in by_key]
    if missing:
        raise InputError(f"{label}: missing column(s) {missing}. Columns found: {list(df.columns)}")
    return df.rename(columns={by_key[_key(c)]: c for c in cols})


def _id_problem(ids):
    """Describes what is wrong with a list of question ids (empty, repeated, or repeated apart from upper/lower
    case), or returns None. Two questions must never share an id."""
    ids = list(ids)
    if any(i == "" for i in ids):
        return "some rows have an empty id."
    dup = [i for i, c in pd.Series(ids).value_counts().items() if c > 1]
    if dup:
        return f"duplicate id(s) {sorted(dup)[:5]}. Every question needs its own id."
    low = pd.Series([i.lower() for i in ids])
    clash = sorted(i for i, l in zip(ids, low) if (low == l).sum() > 1)
    if clash:
        return (f"the ids {clash[:6]} differ only in upper/lower case. Use one spelling for each id "
                f"(ids are case-sensitive and must be written the same in every file).")
    return None


def _check_ids(df, label):
    problem = _id_problem(df["id"])
    if problem:
        raise InputError(f"{label}: {problem}")


def _clean(df, cols):
    """Joins one MCQ (question + options A-D, given as separate cells) into one text, one part per line."""
    return df[cols].apply(lambda r: "\n".join(v for v in r if v), axis=1)


def _devanagari_share(texts):
    letters = [ch for t in texts for ch in t if ch.isalpha()]
    return sum("ऀ" <= ch <= "ॿ" for ch in letters) / len(letters) if letters else 0.0


def language_from_filename(name):
    """Languages named in a file name: reference_tamil.csv -> {'Tamil'}; reference_manipuri_meitei.csv ->
    {'Manipuri (Meitei)'}. An empty set means none was recognised, more than one means the name is ambiguous."""
    rest = _key(os.path.splitext(os.path.basename(str(name)))[0])
    found = set()
    for k, lang in sorted(_LANG_MAP.items(), key=lambda kv: -len(kv[0])):      # longest first: 'manipurimeitei' before 'manipuri'
        if k in rest:
            found.add(lang)
            rest = rest.replace(k, "")
    return found


def source_from_filename(name):
    """Source languages named in a file name: vendor_english_tamil.csv -> {'English'}. Whole words only ('eng' is also
    inside 'bengali'). An empty set means none was recognised, more than one means the name is ambiguous."""
    rest = _key(os.path.splitext(os.path.basename(str(name)))[0])
    return {src for src in SOURCES if src.lower() in rest}


def read_source_file(file, label):
    """One source file (English or Hindi). Returns a frame with id and text (question and options joined)."""
    df = _need(_read_csv(file, label), ["id"] + FIELDS, label)
    _check_ids(df, label)
    blank = df.loc[(df[FIELDS] == "").any(axis=1), "id"].tolist()
    if blank:
        raise InputError(f"{label}: the question or an option is empty for id(s) {blank[:5]}.")
    return pd.DataFrame({"id": df["id"], "text": _clean(df, FIELDS)})


def read_ref_file(file, label):
    """One reference file (one language). Returns a frame with id and text.
    attrs['partial'] lists the questions with a blank cell, e.g. 'Q4 (option_c)'. The user must confirm these (see
    Inputs.confirm); a question that is blank in every cell is an error in validate()."""
    df = _need(_read_csv(file, label), ["id"] + FIELDS, label)
    _check_ids(df, label)
    out = pd.DataFrame({"id": df["id"], "text": _clean(df, FIELDS)})
    part = df[(df[FIELDS] == "").any(axis=1) & (out["text"] != "")]
    out.attrs["partial"] = [f"{r['id']} ({', '.join(f for f in FIELDS if r[f] == '')})" for _, r in part.iterrows()]
    return out


def read_vendor_file(file, source, lang, label):
    """One vendor file = the output for one language pair (source -> lang), both known from the file name.
    Returns the rows (id, source_lang, target_lang, translation = joined MCQ text). A row with an empty id is an
    error (never skipped silently). The optional columns source_lang / target_lang must agree with the file name."""
    df = _read_csv(file, label)
    by_key = {_key(c): c for c in df.columns}
    optional = {"source_lang": by_key.get("sourcelang"), "target_lang": by_key.get("targetlang")}
    df = _need(df, ["id"] + FIELDS, label)
    for column, expected, names in (("source_lang", source, _SRC_MAP), ("target_lang", lang, _LANG_MAP)):
        original = optional[column]
        if original is None:
            continue
        said = df[original].map(lambda v: None if v == "" else names.get(_key(v), v))
        wrong = df.loc[said.notna() & (said != expected), original].unique().tolist()
        if wrong:
            raise InputError(f"{label}: this file is {source} to {lang} but the {column} column says {wrong[:3]}. "
                             f"Put each language pair in its own file.")
    empty = df.index[df["id"] == ""]
    if len(empty):
        raise InputError(f"{label}: empty id in row(s) {[int(i) + 2 for i in empty[:5]]}.")
    _check_ids(df, label)
    return pd.DataFrame({"id": df["id"], "source_lang": source, "target_lang": lang, "translation": _clean(df, FIELDS)})


def combine_source(english, hindi):
    """Puts the English and Hindi source files side by side. They must hold the same question ids."""
    e, h = set(english["id"]), set(hindi["id"])
    if e != h:
        only_e, only_h = sorted(e - h), sorted(h - e)
        parts = []
        if only_e:
            parts.append(f"only in the English file: {only_e[:5]}")
        if only_h:
            parts.append(f"only in the Hindi file: {only_h[:5]}")
        raise InputError("Source files: the English and the Hindi file must have the same question ids (the same "
                         "question has the same id in both). " + "; ".join(parts) + _id_hint(only_e, only_h))
    hindi_text = dict(zip(hindi["id"], hindi["text"]))
    return pd.DataFrame({"id": english["id"], "english": english["text"], "hindi": english["id"].map(hindi_text)})


def _id_hint(missing, extra):
    """Points out ids that differ only in upper/lower case, the usual way two files fail to match."""
    low = {i.lower(): i for i in extra}
    pairs = [f"'{i}' / '{low[i.lower()]}'" for i in missing if i.lower() in low]
    return f" Ids that differ only in upper/lower case: {', '.join(pairs[:3])}." if pairs else ""


# ---------------------------------------------------------------- loading all the files
@dataclass
class Inputs:
    """Everything read from the uploaded files. errors block the evaluation; warnings do not."""
    source: pd.DataFrame = None                      # id, english, hindi
    refs: dict = field(default_factory=dict)         # language -> frame (id, text)
    vendor: pd.DataFrame = None                      # id, source_lang, target_lang, translation
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    confirm: list = field(default_factory=list)      # problems that block Evaluate until the user accepts them
    hashes: dict = field(default_factory=dict)       # "group/file name" -> SHA-256
    ref_files: dict = field(default_factory=dict)    # language -> file name
    vendor_files: dict = field(default_factory=dict)  # (source language, target language) -> file name

    def as_tuple(self):
        return self.source, self.refs, self.vendor


def _wrong_place(name, word, group):
    return (f"{name}: this looks like a {word} file but it was added under the {group} files. "
            f"Check that the files are in the right place.")


def _read_references(items, inp):
    """The reference files: one per language, the language comes from the file name."""
    frames = []
    for name, file in items:
        inp.hashes[f"reference/{name}"] = file_sha256(file)
        if "vendor" in _key(name):
            inp.errors.append(_wrong_place(name, "vendor", "reference"))
            continue
        langs = language_from_filename(name)
        if len(langs) != 1:
            why = ("it names more than one language: " + ", ".join(sorted(langs))) if langs else "no language found in it"
            inp.errors.append(f"{name}: cannot tell which language this file is for ({why}). "
                              f"Name it like reference_tamil.csv (names: {', '.join(_slug(x) for x in LANGUAGES)}).")
            continue
        lang = next(iter(langs))
        if lang in inp.ref_files:
            inp.errors.append(f"{lang} has two reference files ({inp.ref_files[lang]} and {name}). Keep one.")
            continue
        inp.ref_files[lang] = name
        try:
            frames.append((lang, read_ref_file(file, f"Reference file {name} ({lang})")))
        except InputError as e:
            inp.errors.append(str(e))
    return frames


def _read_vendor(items, inp):
    """The vendor files: one per language pair, both languages come from the file name."""
    frames = []
    for name, file in items:
        inp.hashes[f"vendor/{name}"] = file_sha256(file)
        if "reference" in _key(name):
            inp.errors.append(_wrong_place(name, "reference", "vendor"))
            continue
        langs, sources = language_from_filename(name), source_from_filename(name)
        if not langs and sources == set(SOURCES):                 # vendor_english_hindi.csv: the extra English to Hindi pair
            langs, sources = {HINDI}, {"English"}
        if len(langs) != 1 or len(sources) != 1:
            found = sorted(langs) + sorted(sources)
            why = (f"it names {', '.join(found)}; one source language and one target language are needed"
                   if found else "no language found in it")
            inp.errors.append(f"{name}: cannot tell which language pair this file is for ({why}). Name it like "
                              f"vendor_english_tamil.csv or vendor_hindi_tamil.csv (source first, then the target "
                              f"language: {', '.join(_slug(x) for x in LANGUAGES)}; English to Hindi is "
                              f"vendor_english_hindi.csv).")
            continue
        pair = (next(iter(sources)), next(iter(langs)))
        if pair in inp.vendor_files:
            inp.errors.append(f"{pair[0]} to {pair[1]} has two vendor files ({inp.vendor_files[pair]} and {name}). Keep one.")
            continue
        inp.vendor_files[pair] = name
        try:
            frames.append(read_vendor_file(file, pair[0], pair[1], f"Vendor file {name} ({pair[0]} to {pair[1]})"))
        except InputError as e:
            inp.errors.append(str(e))
    return frames


def load_inputs(source_english=None, source_hindi=None, references=(), vendor=()):
    """Reads and checks every file on its own. The arguments are (file name, file) pairs, where the file is a path
    or an uploaded file object; references (one file per language) and vendor (one file per language pair) are lists
    of such pairs.
    Cross-file checks (ids against the source, languages, coverage) are done by validate()."""
    inp = Inputs()
    tables = {}
    for lang, item in (("English", source_english), ("Hindi", source_hindi)):
        if item is None:
            continue
        name, file = item
        inp.hashes[f"source/{name}"] = file_sha256(file)
        try:
            tables[lang] = read_source_file(file, f"Source file {name} ({lang})")
        except InputError as e:
            inp.errors.append(str(e))
            continue
        share = _devanagari_share(tables[lang]["text"])
        if lang == "English" and share > 0.5 or lang == "Hindi" and share < 0.2:
            inp.warnings.append(f"Source file {name}: it was given as the {lang} file but the text looks like "
                                f"{'Hindi' if lang == 'English' else 'a language other than Hindi'}. "
                                f"Check that the English and Hindi files are not swapped.")
    if len(tables) == 2:
        try:
            inp.source = combine_source(tables["English"], tables["Hindi"])
        except InputError as e:
            inp.errors.append(str(e))

    for lang, df in _read_references(references, inp):
        inp.refs[lang] = df
        if df.attrs.get("partial"):
            inp.confirm.append(f"Reference {lang}: {len(df.attrs['partial'])} question(s) have a blank question or "
                               f"option, e.g. {', '.join(df.attrs['partial'][:3])}.")

    frames = _read_vendor(vendor, inp)
    if frames:
        inp.vendor = pd.concat(frames, ignore_index=True)
    return inp


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


_comet_lock = threading.Lock()
_comet_future = None


def start_comet_loading():
    """Starts loading the COMET model in a background thread and returns a Future for it. The model is loaded once and
    kept for later runs; a failed load is tried again on the next call. Lets BLEU and chrF++ run while the model loads."""
    global _comet_future
    with _comet_lock:
        f = _comet_future
        if f is None or (f.done() and f.exception() is not None):
            _comet_future = f = ThreadPoolExecutor(max_workers=1, thread_name_prefix="comet-load").submit(load_comet_model)
        return f


# ---------------------------------------------------------------- validation across the files
@dataclass
class Validation:
    errors: list = field(default_factory=list)      # block the evaluation
    warnings: list = field(default_factory=list)    # shown, evaluation can go on
    info: dict = field(default_factory=dict)        # counts
    coverage: pd.DataFrame = None                   # vendor translations received per language and direction

    @property
    def ok(self):
        return not self.errors


def validate(source, refs, vendor):
    """Cross-checks the parsed files (see load_inputs; the per-file checks are made there).

    Blocking errors: reference languages or question ids missing, extra ids, blank references, vendor ids that are not
    in the source. Warnings only: missing vendor output (it is scored, see evaluate)."""
    errors, warnings = [], []
    ids = list(source["id"])
    id_set, n = set(ids), len(ids)

    missing_langs = [lang for lang in LANGUAGES if lang not in refs]
    if missing_langs:
        errors.append(f"Reference translations: no file for {', '.join(missing_langs)}. All {len(LANGUAGES)} "
                      f"languages are required, one file each (for example reference_tamil.csv).")
    for lang in LANGUAGES:
        if lang not in refs:
            continue
        r = refs[lang]
        ref_ids = set(r["id"])
        miss = [i for i in ids if i not in ref_ids]
        extra = sorted(ref_ids - id_set)
        if miss:
            errors.append(f"Reference {lang}: {len(miss)} question id(s) of the source files are missing "
                          f"(e.g. {', '.join(miss[:5])})." + _id_hint(miss, extra))
        if extra:
            errors.append(f"Reference {lang}: {len(extra)} id(s) are not in the source questions "
                          f"(e.g. {', '.join(extra[:5])}).")
        blank = int((r.loc[r["id"].isin(id_set), "text"] == "").sum())
        if blank:
            errors.append(f"Reference {lang}: {blank} blank reference(s). Every question needs a reference "
                          f"in every language.")

    stray = vendor[~vendor["id"].isin(id_set)]
    if not stray.empty:
        where = ", ".join(sorted({f"{a} to {b}" for a, b in zip(stray["source_lang"], stray["target_lang"])}))
        vextra = sorted(set(stray["id"]))
        errors.append(f"Vendor output: {len(vextra)} id(s) are not in the source questions "
                      f"(e.g. {', '.join(vextra[:5])}; in the {where} file(s)). Check that this is the right vendor."
                      + _id_hint(sorted(id_set - set(vendor["id"])), vextra))

    v = vendor[vendor["id"].isin(id_set)]
    rows, received = [], 0
    for lang in LANGUAGES + [HINDI]:
        srcs = SOURCES if lang != HINDI else ("English",)          # English to Hindi has one direction only
        row = {"Language": lang if lang != HINDI else "Hindi (English to Hindi only)"}
        for src in SOURCES:
            if src not in srcs:
                row[f"{src} received"] = None
                continue
            g = v[(v["target_lang"] == lang) & (v["source_lang"] == src)]
            got = int((g["translation"] != "").sum())
            received += got
            row[f"{src} received"] = got
        row["Expected per direction"] = n
        rows.append(row)
        got_all = [row[f"{src} received"] for src in srcs]
        if not any(got_all):
            warnings.append(f"{lang}: no vendor output at all (no vendor file, or only blank rows). It will get 0 marks "
                            f"and the bidder is disqualified.")
            continue
        for src, got in zip(srcs, got_all):
            if got == 0:
                warnings.append(f"{lang}: no output for {src} to {lang}. The other direction is used.")
            elif got < n:
                warnings.append(f"{lang} ({src} to {lang}): {n - got} of {n} translation(s) missing or blank. "
                                f"They are scored as empty.")
    expected = n * len(PAIRS)
    info = {"questions": n, "languages": len(LANGUAGES), "directions": len(SOURCES), "pairs": len(PAIRS),
            "expected_rows": expected, "received_rows": received, "missing_rows": expected - received}
    cov = pd.DataFrame(rows)
    for c in [f"{s} received" for s in SOURCES]:
        cov[c] = cov[c].astype("Int64")
    return Validation(errors, warnings, info, cov)


# ---------------------------------------------------------------- scoring
@dataclass
class Result:
    table: pd.DataFrame
    summary: dict
    warnings: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    validation: Validation = None


def _best(*vals):
    ok = [v for v in vals if v is not None and not math.isnan(v)]
    return max(ok) if ok else float("nan")


def _finite(x, what):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ScoringError(f"{what} returned an invalid value ({x!r}).")
    return float(x)


def _signature(metric):
    try:
        return str(metric.get_signature())
    except ValueError:                       # sacreBLEU only knows its signature after it has scored something
        return "not available (no sentence pair was scored)"


def _version(pkg):
    try:
        return md.version(pkg)
    except md.PackageNotFoundError:
        return None


def evaluate(source, refs, vendor, with_comet=False, comet_model=None, progress=None, run_info=None):
    """Scores one vendor. run_info (optional) = {"vendor": name, "hashes": {file: sha256}} goes into the audit metadata."""
    from sacrebleu.metrics import BLEU, CHRF
    import sacrebleu

    tick = progress or (lambda frac, msg: None)
    val = validate(source, refs, vendor)
    if val.errors:
        raise InputError("The input files do not match:\n- " + "\n- ".join(val.errors))
    warnings = list(val.warnings)

    ids = list(source["id"])
    src_text = {"English": dict(zip(source["id"], source["english"])),
                "Hindi": dict(zip(source["id"], source["hindi"]))}
    ref_text = {lang: dict(zip(refs[lang]["id"], refs[lang]["text"])) for lang in LANGUAGES}
    ref_text[HINDI] = src_text["Hindi"]                  # the reference of English to Hindi is the Hindi source file
    vendor_text = {}
    for (s, t), g in vendor.groupby(["source_lang", "target_lang"]):
        vendor_text[(s, t)] = dict(zip(g["id"], g["translation"]))

    bleu_m = BLEU(tokenize="flores200")
    chrf_m = CHRF(word_order=2)

    scores = {}   # (language, source) -> {"bleu", "chrf", "comet"}
    groups = {}   # (language, source) -> (src list, mt list, ref list)
    pairs = [(lang, s) for s, lang in PAIRS]
    for n, (lang, s) in enumerate(pairs):
        loading = hasattr(comet_model, "result") and not comet_model.done()
        if hasattr(comet_model, "result") and comet_model.done() and comet_model.exception() is not None:
            raise comet_model.exception()                  # the model could not be loaded: stop now, not after BLEU
        tick(0.05 + 0.5 * n / len(pairs),
             f"BLEU and chrF++: {s} to {lang}" + ("  (the COMET model is loading in the background)" if loading else ""))
        vt = vendor_text.get((s, lang))
        if vt is None or not any(vt.values()):
            continue                                    # no output in this direction
        mts = [vt.get(i, "") for i in ids]               # a missing translation is an empty sentence, for every metric
        rfs = [ref_text[lang][i] for i in ids]
        scores[(lang, s)] = {"bleu": _finite(bleu_m.corpus_score(mts, [rfs]).score, "BLEU"),
                             "chrf": _finite(chrf_m.corpus_score(mts, [rfs]).score, "chrF++")}
        groups[(lang, s)] = ([src_text[s][i] for i in ids], mts, rfs)

    comet_info = None
    if with_comet:
        if comet_model is None:
            raise ModelUnavailable("COMET was requested but no model was loaded.")
        if hasattr(comet_model, "result"):                  # a Future from start_comet_loading()
            if not comet_model.done():
                tick(0.58, "BLEU and chrF++ done. Waiting for the COMET model to finish loading...")
            comet_model = comet_model.result()
        data, spans = [], {}
        for key, (srcs, mts, rfs) in groups.items():
            a = len(data)
            keep = [j for j, m in enumerate(mts) if m != ""]        # a missing translation is not sent to the model
            data += [{"src": srcs[j], "mt": mts[j], "ref": rfs[j]} for j in keep]
            spans[key] = (a, len(data), len(mts))
        if data:
            tick(0.6, f"COMET model scoring {len(data)} sentence pairs (this is the slow step)")
            out = comet_model.predict(data, batch_size=int(setting("COMET_BATCH_SIZE", "16")),
                                      gpus=int(setting("COMET_GPUS", "0")), progress_bar=False)
            seg = list(out.scores if hasattr(out, "scores") else out[0])
            if len(seg) != len(data):
                raise ScoringError(f"COMET returned {len(seg)} scores for {len(data)} sentence pairs.")
            seg = [_finite(x, "COMET") for x in seg]
            for key, (a, b, total) in spans.items():
                scores[key]["comet"] = sum(seg[a:b]) / total         # missing translations count as 0 in the mean
        else:
            warnings.append("COMET: there was no vendor output to score.")
        comet_info = (f"{setting('COMET_CHECKPOINT') or setting('COMET_MODEL', 'Unbabel/wmt22-comet-da')} "
                      f"(unbabel-comet {_version('unbabel-comet') or 'unknown'})")

    tick(0.9, "Applying marks")
    nan = float("nan")
    rows = []
    for lang in LANGUAGES + [HINDI]:
        srcs = SOURCES if lang != HINDI else ("English",)
        row = {"Language": lang}
        got = [s for s in srcs if (lang, s) in scores]
        row["Status"] = NO_OUTPUT if not got else "OK" if len(got) == len(srcs) else f"Only {got[0]} source"

        metrics = [("BLEU", "bleu"), ("chrF++", "chrf")] + ([("COMET", "comet")] if with_comet else [])
        maxima = {}
        for name, k in metrics:
            vals = []
            for s in srcs:
                v = scores.get((lang, s), {}).get(k, nan)
                row[f"{name} {SHORT[s]}→T"] = v
                vals.append(v)
            m = _best(*vals)
            maxima[name] = 0.0 if math.isnan(m) else m       # no score at all counts as 0
            row[f"Max {name}"] = maxima[name]

        scored = bool(got)                                   # no output for a language: 0 marks under every rule
        row["BLEU Marks"] = rft.bleu_marks(maxima["BLEU"]) if scored else 0
        if with_comet:
            row["COMET Marks"] = rft.comet_marks(maxima["COMET"]) if scored else 0
        row["chrF++ Marks"] = rft.chrf_marks(maxima["chrF++"]) if scored else 0
        rows.append(row)

    full = pd.DataFrame(rows)
    order = ["Language", "Status"]
    for name in ["BLEU"] + (["COMET"] if with_comet else []) + ["chrF++"]:
        order += [f"{name} En→T", f"{name} Hi→T", f"Max {name}"]
    order += ["BLEU Marks"] + (["COMET Marks"] if with_comet else []) + ["chrF++ Marks"]
    full = full[order]
    full["Outcome"] = ["DISQUALIFIED" if st == NO_OUTPUT else "" for st in full["Status"]]
    table = full                                       # the 13 languages and, as the last row, Hindi (English to Hindi only)
    disqualified = [r["Language"] for _, r in full.iterrows() if r["Status"] == NO_OUTPUT]

    n = len(table)                                     # the marks are averaged over these 14 rows

    def mean(col):
        return float(table[col].sum()) / n

    bleu, chrf = mean("BLEU Marks"), mean("chrF++ Marks")
    comet = mean("COMET Marks") if with_comet else None
    max_total = rft.BLEU_MAX + rft.CHRF_MAX + (rft.COMET_MAX if with_comet else 0)
    total = bleu + chrf + (comet or 0)
    summary = {"bleu": bleu, "comet": comet, "chrf": chrf, "total": total, "max_total": max_total,
               "pct": 100 * total / max_total, "with_comet": with_comet, "languages": n,
               "disqualified": bool(disqualified), "disqualified_languages": disqualified}
    run_info = run_info or {}
    meta = {
        "run_id": str(uuid.uuid4()),
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "vendor": run_info.get("vendor"),
        "input_sha256": run_info.get("hashes") or {},
        "scoring_policy": rft.POLICY_ID,
        "questions": len(ids),
        "expected_rows": val.info["expected_rows"], "received_rows": val.info["received_rows"],
        "sacrebleu": sacrebleu.__version__,
        "bleu_signature": _signature(bleu_m),
        "chrf_signature": _signature(chrf_m),
        "comet": comet_info,
        "comet_batch_size": int(setting("COMET_BATCH_SIZE", "16")) if with_comet else None,
        "comet_gpus": int(setting("COMET_GPUS", "0")) if with_comet else None,
        "bleu_config": "sacreBLEU BLEU(tokenize=flores200), corpus level",
        "chrf_config": "sacreBLEU CHRF(word_order=2), corpus level",
        "missing_translation_rule": "BLEU and chrF++: scored as an empty sentence; COMET: segment score 0 (not sent to the model)",
        "accepted_issues": list(run_info.get("accepted") or []),
        "python": platform.python_version(), "pandas": pd.__version__,
        "unbabel_comet": _version("unbabel-comet"),
    }
    tick(1.0, "Done")
    return Result(table=table, summary=summary, warnings=warnings, meta=meta, validation=val)


def audit_record(res):
    """Everything needed to reproduce and check a run, as a JSON-ready dict."""
    v = res.validation
    return {**res.meta,
            "summary": {k: (round(x, 4) if isinstance(x, float) else x) for k, x in res.summary.items()},
            "validation": {"errors": v.errors, "warnings": res.warnings, **v.info},
            "coverage": v.coverage.to_dict(orient="records")}


def export_tables(res, who):
    """The two CSV exports: (per-language frame, one-row summary frame). Both carry the vendor and run identifiers."""
    m, s = res.meta, res.summary
    ident = {"Vendor": who, "Run ID": m["run_id"], "Evaluated (UTC)": m["timestamp_utc"],
             "Scoring policy": m["scoring_policy"]}
    summary = pd.DataFrame([{**ident, "BLEU option": "B", "BLEU marks": s["bleu"], "COMET marks": s["comet"],
                             "chrF++ marks": s["chrf"], "Total": s["total"], "Max": s["max_total"],
                             "Percent": s["pct"],
                             "Disqualified": "Yes" if s["disqualified"] else "No",
                             "Disqualified for no output in": ", ".join(s["disqualified_languages"])}]).round(2)
    detail = res.table.copy()
    for i, (k, v) in enumerate(ident.items()):
        detail.insert(i, k, v)
    return detail, summary
