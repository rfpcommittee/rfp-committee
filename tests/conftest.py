"""Shared helpers: small, fully controlled input files in the layout the app reads.

    source/     source_english.csv, source_hindi.csv
    reference/  reference_<language>.csv   (13 files)
    vendor/     vendor_<language>.csv      (one per language the vendor translated)
"""
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import evaluator as ev  # noqa: E402


def ref_parts(lang, i):
    """The reference MCQ of question i in a language: [question, option A..D]."""
    return [f"the quick brown fox number {i} jumps over the lazy dog in {lang}"] + \
           [f"option {x} alpha beta gamma delta {i} {lang}" for x in "abcd"]


def build(n=3, vendor_fn=None):
    """The raw content of all the files, as DataFrames, before they are written.

    Returns {"source_english": df, "source_hindi": df, "reference": {lang: df}, "vendor": {lang: df}}.
    vendor_fn(lang, src, i, parts) -> list of 5 strings, or None to leave the row out. Default: a perfect copy.
    A language whose vendor rows are all left out has no vendor file."""
    ids = [f"Q{i}" for i in range(1, n + 1)]
    data = {"reference": {}, "vendor": {}}
    data["source_english"] = pd.DataFrame({"id": ids, **{f: [f"english source {f} {i}" for i in ids] for f in ev.FIELDS}})
    data["source_hindi"] = pd.DataFrame({"id": ids, **{f: [f"हिंदी स्रोत भाग{k} {i}" for i in ids]    # Devanagari, like real Hindi
                                                       for k, f in enumerate(ev.FIELDS)}})
    for lang in ev.LANGUAGES:
        data["reference"][lang] = pd.DataFrame({"id": ids, **{f: [ref_parts(lang, i)[k] for i in ids]
                                                              for k, f in enumerate(ev.FIELDS)}})
        rows = []
        for s in ev.SOURCES:
            for i in ids:
                parts = ref_parts(lang, i)
                out = parts if vendor_fn is None else vendor_fn(lang, s, i, parts)
                if out is not None:
                    rows.append([i, s] + list(out))
        if rows:
            data["vendor"][lang] = pd.DataFrame(rows, columns=["id", "source_lang"] + ev.FIELDS)
    return data


def write_files(folder, data, encoding="utf-8-sig"):
    """Writes the files into folder/source, folder/reference, folder/vendor.
    Returns the arguments for ev.load_inputs: {"source_english", "source_hindi", "references", "vendor"}."""
    folder = str(folder)
    for sub in ("source", "reference", "vendor"):
        os.makedirs(os.path.join(folder, sub), exist_ok=True)

    def put(sub, name, df):
        path = os.path.join(folder, sub, name)
        df.to_csv(path, index=False, encoding=encoding)
        return name, path

    return {
        "source_english": put("source", "source_english.csv", data["source_english"]),
        "source_hindi": put("source", "source_hindi.csv", data["source_hindi"]),
        "references": [put("reference", f"reference_{ev._slug(lang)}.csv", df) for lang, df in data["reference"].items()],
        "vendor": [put("vendor", f"vendor_{ev._slug(lang)}.csv", df) for lang, df in data["vendor"].items()],
    }


def load(data, tmp_path, **kw):
    """Writes the files and reads them back with ev.load_inputs (which reports problems in .errors)."""
    return ev.load_inputs(**write_files(tmp_path, data, **kw))


def parse(data, tmp_path):
    """Like load(), but returns (source, refs, vendor) and raises if any file had a problem."""
    inp = load(data, tmp_path)
    if inp.errors:
        raise ev.InputError("\n".join(inp.errors))
    return inp.as_tuple()


@pytest.fixture
def run(tmp_path):
    """run(vendor_fn=None, n=3, with_comet=False, comet_model=None) -> evaluation Result."""
    def _run(vendor_fn=None, n=3, with_comet=False, comet_model=None, run_info=None):
        parsed = parse(build(n, vendor_fn), tmp_path)
        return ev.evaluate(*parsed, with_comet=with_comet, comet_model=comet_model, run_info=run_info)
    return _run


class FakeComet:
    """Stands in for the COMET model: predict() returns a fixed score per pair and records what it was given."""
    def __init__(self, score=0.9, scores=None, drop=0):
        self.score, self.scores, self.drop, self.calls = score, scores, drop, []

    def predict(self, data, batch_size, gpus, progress_bar):
        self.calls.append(list(data))
        vals = self.scores if self.scores is not None else [self.score] * len(data)
        return type("Out", (), {"scores": list(vals)[: len(vals) - self.drop]})()
