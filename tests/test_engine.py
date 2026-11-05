"""Scoring engine: directions, missing output, maximum, averaging, COMET handling (mocked), audit metadata."""
import json
import math

import pytest
from sacrebleu.metrics import BLEU, CHRF

import evaluator as ev
from conftest import FakeComet, build, parse

N = 3
NLANG = len(ev.LANGUAGES)


def row(res, lang):
    return res.table.set_index("Language").loc[lang]


def test_perfect_vendor_gets_full_automatic_marks(run):
    res = run()
    assert res.summary["bleu"] == 12 and res.summary["chrf"] == 5 and res.summary["total"] == 17
    assert res.summary["max_total"] == 17 and res.summary["with_comet"] is False
    assert "COMET Marks" not in res.table.columns
    assert (res.table["Status"] == "OK").all()
    assert not res.warnings


def test_option_a_is_not_in_the_results(run):
    res = run()
    assert "BLEU Marks (A)" not in res.table.columns and "BLEU Marks (B)" not in res.table.columns
    assert {"bleu", "total", "pct"} <= set(res.summary) and "total_a" not in res.summary


def test_only_one_direction_available(run):
    res = run(lambda lang, s, i, parts: None if (lang == "Tamil" and s == "Hindi") else parts)
    t = row(res, "Tamil")
    assert t["Status"] == "Only English source"
    assert math.isnan(t["BLEU Hi→T"]) and t["Max BLEU"] == t["BLEU En→T"] == pytest.approx(100)
    assert t["BLEU Marks"] == 12
    assert any("Tamil: no output for Hindi" in w for w in res.warnings)


def test_no_output_for_a_language_is_zero_and_still_in_the_average(run):
    res = run(lambda lang, s, i, parts: None if lang == "Urdu" else parts)
    u = row(res, "Urdu")
    assert u["Status"] == ev.NO_OUTPUT
    assert u["Max BLEU"] == 0 and u["Max chrF++"] == 0                       # 0, not NaN
    assert u["BLEU Marks"] == 0 and u["chrF++ Marks"] == 0
    assert res.summary["bleu"] == pytest.approx(12 * 12 / NLANG)             # 13 languages, equal weight
    assert res.summary["chrf"] == pytest.approx(5 * 12 / NLANG)


def test_blank_translations_count_as_no_output(run):
    res = run(lambda lang, s, i, parts: [""] * 5 if lang == "Odia" else parts)
    o = row(res, "Odia")
    assert o["Status"] == ev.NO_OUTPUT and o["BLEU Marks"] == 0 and o["chrF++ Marks"] == 0


def test_a_missing_translation_is_scored_as_empty_for_every_metric(run):
    blank_q2 = lambda lang, s, i, parts: [""] * 5 if (lang == "Tamil" and i == "Q2") else parts   # noqa: E731
    model = FakeComet(0.9)
    res = run(blank_q2, with_comet=True, comet_model=model)
    t = row(res, "Tamil")
    assert t["Max BLEU"] < 100 and t["Max chrF++"] < 100
    assert len(model.calls[0]) == N * NLANG * 2          # the blank pair is still sent to COMET, not dropped


def test_max_takes_the_higher_direction_per_metric(run):
    bad = ["zzz"] * 5
    res = run(lambda lang, s, i, parts: bad if (lang == "Telugu" and s == "English") else parts)
    t = row(res, "Telugu")
    assert t["BLEU En→T"] < 5 and t["BLEU Hi→T"] == pytest.approx(100)
    assert t["Max BLEU"] == t["BLEU Hi→T"] and t["Max chrF++"] == t["chrF++ Hi→T"]
    res = run(lambda lang, s, i, parts: bad if (lang == "Telugu" and s == "Hindi") else parts)
    assert row(res, "Telugu")["Max BLEU"] == row(res, "Telugu")["BLEU En→T"]


def test_equal_weight_average_over_13_languages(run):
    bad = ["zzz"] * 5
    res = run(lambda lang, s, i, parts: bad if lang in ("Tamil", "Telugu", "Urdu") else parts)
    assert res.summary["bleu"] == pytest.approx(12 * 10 / NLANG)
    assert res.summary["chrf"] == pytest.approx(5 * 10 / NLANG)


def test_scores_match_an_independent_sacrebleu_calculation(tmp_path):
    def vf(lang, s, i, parts):
        return [p.replace("alpha", "omega") if lang == "Tamil" else p for p in parts]
    s, r, v = parse(build(N, vf), tmp_path)
    res = ev.evaluate(s, r, v)
    tam = v[(v.source_lang == "English") & (v.target_lang == "Tamil")].set_index("id")["translation"]
    mts = [tam[i] for i in s["id"]]
    rfs = list(r["Tamil"].set_index("id").loc[list(s["id"]), "text"])
    assert row(res, "Tamil")["BLEU En→T"] == pytest.approx(BLEU(tokenize="flores200").corpus_score(mts, [rfs]).score)
    assert row(res, "Tamil")["chrF++ En→T"] == pytest.approx(CHRF(word_order=2).corpus_score(mts, [rfs]).score)


def test_results_are_reproducible(run):
    noisy = lambda lang, s, i, parts: [p.replace("beta", "x") if lang == "Kannada" else p for p in parts]   # noqa: E731
    a, b = run(noisy), run(noisy)
    assert a.table.equals(b.table) and a.summary == b.summary
    assert a.meta["run_id"] != b.meta["run_id"]


# ---- COMET, with a mocked model
def test_comet_marks_and_totals(run):
    model = FakeComet(0.9)
    res = run(with_comet=True, comet_model=model)
    assert len(model.calls) == 1 and len(model.calls[0]) == N * NLANG * 2
    assert res.summary["comet"] == 10 and res.summary["total"] == 27 and res.summary["max_total"] == 27
    assert row(res, "Tamil")["Max COMET"] == pytest.approx(0.9)
    assert {"src", "mt", "ref"} == set(model.calls[0][0])


def test_comet_scores_go_to_the_right_language_and_direction(run):
    first = N * 2                                           # Assamese (English, Hindi) comes first
    res = run(with_comet=True, comet_model=FakeComet(scores=[0.5] * first + [0.9] * (N * 2 * (NLANG - 1))))
    a = row(res, "Assamese")
    assert a["COMET En→T"] == pytest.approx(0.5) and a["COMET Marks"] == 0
    assert res.summary["comet"] == pytest.approx(10 * 12 / NLANG)


def test_comet_wrong_number_of_scores_is_rejected(run):
    with pytest.raises(ev.ScoringError, match="scores for"):
        run(with_comet=True, comet_model=FakeComet(0.9, drop=1))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), None])
def test_comet_invalid_values_are_rejected(run, bad):
    scores = [0.9] * (N * NLANG * 2)
    scores[5] = bad
    with pytest.raises(ev.ScoringError, match="invalid value"):
        run(with_comet=True, comet_model=FakeComet(scores=scores))


def test_comet_with_nothing_to_score_does_not_call_the_model(run):
    model = FakeComet(0.9)
    res = run(lambda lang, s, i, parts: [""] * 5, with_comet=True, comet_model=model)
    assert model.calls == []
    assert res.summary["total"] == 0 and any("COMET: there was no vendor output" in w for w in res.warnings)


def test_comet_requested_without_a_model(run):
    with pytest.raises(ev.ModelUnavailable):
        run(with_comet=True, comet_model=None)


def test_comet_array_style_output_is_accepted(run):
    class Tuple:
        def predict(self, data, **kw):
            return ([0.9] * len(data), 0.9)
    assert run(with_comet=True, comet_model=Tuple()).summary["comet"] == 10


# ---- audit metadata
def test_audit_metadata(run):
    res = run(run_info={"vendor": "Acme", "hashes": {"source": "a" * 64}})
    m = res.meta
    assert m["vendor"] == "Acme" and m["input_sha256"] == {"source": "a" * 64}
    assert m["run_id"] and m["timestamp_utc"].endswith("+00:00")
    assert m["expected_rows"] == m["received_rows"] == N * 26
    assert "Option B" in m["scoring_policy"] and m["sacrebleu"] and "tok" in m["bleu_signature"]
    rec = json.loads(json.dumps(ev.audit_record(res)))
    assert rec["validation"]["errors"] == [] and len(rec["coverage"]) == NLANG
    assert rec["summary"]["total"] == 17


def test_nan_never_reaches_the_marks(run):
    res = run(lambda lang, s, i, parts: None if lang in ("Urdu", "Odia") else parts)
    marks = ["BLEU Marks", "chrF++ Marks"]
    assert not res.table[marks].isna().any().any()
    assert not res.table[["Max BLEU", "Max chrF++"]].isna().any().any()
