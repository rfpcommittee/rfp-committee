"""The Streamlit app, driven with streamlit's AppTest (no browser). COMET is switched off through USE_MODEL=false.

Not covered here: the file-upload widget (AppTest cannot upload files), so the real-CSV path is tested through the
engine in test_validation.py / test_engine.py and by hand in the browser."""
import json
import os
import shutil

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import evaluator as ev
from conftest import ROOT, build, write_files

APP = os.path.join(ROOT, "app.py")
SAMPLE = os.path.join(ROOT, "sample_data")


def sample_args(folder=SAMPLE):
    """The sample files, as the arguments of ev.load_inputs."""
    def listing(sub):
        d = os.path.join(folder, sub)
        return [(f, os.path.join(d, f)) for f in sorted(os.listdir(d))]
    return dict(source_english=("source_english.csv", os.path.join(folder, "source", "source_english.csv")),
                source_hindi=("source_hindi.csv", os.path.join(folder, "source", "source_hindi.csv")),
                references=listing("reference"), vendor=listing("vendor"))


def sample_result(**kw):
    inp = ev.load_inputs(**sample_args())
    assert not inp.errors
    return ev.evaluate(*inp.as_tuple(), **kw)


@pytest.fixture(autouse=True)
def comet_off(monkeypatch):
    monkeypatch.setenv("USE_MODEL", "false")


def new_app():
    return AppTest.from_file(APP, default_timeout=180).run()


def metric(at, label):
    return next((m for m in at.metric if m.label == label), None)


def evaluate_sample(at, vendor="Acme"):
    at.text_input(key="vendor_name").set_value(vendor)
    at.toggle[0].set_value(True)
    at.run()
    next(b for b in at.button if b.label == "Evaluate").click()
    return at.run()


def test_first_screen_needs_a_vendor_name():
    at = new_app()
    assert not at.exception
    assert next(b for b in at.button if b.label == "Evaluate").disabled
    assert any("Enter the vendor name first" in c.value for c in at.caption)


def test_vendor_name_comes_before_the_file_selection():
    at = new_app()
    order = [e.type for e in at.main if e.type in ("text_input", "toggle")]
    assert order[:2] == ["text_input", "toggle"]


def test_sample_workflow_validation_summary_and_results():
    at = new_app()
    at.text_input(key="vendor_name").set_value("Acme")
    at.toggle[0].set_value(True)
    at.run()
    assert not at.exception
    assert metric(at, "Questions").value == "6"
    assert metric(at, "Expected vendor rows").value == str(6 * 13 * 2)
    assert any("The files match" in s.value for s in at.success)
    assert next(b for b in at.button if b.label == "Evaluate").disabled is False

    next(b for b in at.button if b.label == "Evaluate").click()
    at.run()
    assert not at.exception
    total = metric(at, "Total (Option B)")
    assert total is not None and total.value.endswith("/ 17")
    assert any("dummy sample files" in w.value for w in at.warning)
    assert any("COMET was not computed" in i.value for i in at.info)          # COMET disabled is stated
    assert metric(at, "COMET marks").value == "Not computed"
    # the figure on screen is the engine's figure
    res = sample_result()
    assert total.value == f"{res.summary['total']:.2f} / 17"
    assert not any("Option A" in str(m.label) for m in at.metric)


def test_results_are_cleared_when_the_vendor_name_changes():
    at = evaluate_sample(new_app())
    assert metric(at, "Total (Option B)") is not None
    at.text_input(key="vendor_name").set_value("Other vendor")
    at.run()
    assert metric(at, "Total (Option B)") is None
    assert any("earlier result was cleared" in i.value for i in at.info)


def test_results_are_cleared_when_the_inputs_change():
    at = evaluate_sample(new_app())
    assert metric(at, "Total (Option B)") is not None
    at.toggle[0].set_value(False)               # no files any more
    at.run()
    assert metric(at, "Total (Option B)") is None
    assert next(b for b in at.button if b.label == "Evaluate").disabled


def test_results_stay_when_nothing_changed():
    at = evaluate_sample(new_app())
    at.run()
    assert metric(at, "Total (Option B)") is not None


def test_validation_errors_are_shown_and_block_evaluate(tmp_path, monkeypatch):
    data = build(2)
    data["vendor"]["Tamil"].loc[0, "id"] = "Q99"                       # vendor id that is not in the source
    data["reference"]["Tamil"] = data["reference"]["Tamil"].iloc[:1]   # reference file lacks Q2
    write_files(tmp_path / "sample_data", data)
    monkeypatch.setattr(ev, "BASE_DIR", str(tmp_path))
    at = AppTest.from_file(APP, default_timeout=180).run()
    at.text_input(key="vendor_name").set_value("Acme")
    at.toggle[0].set_value(True)
    at.run()
    assert not at.exception
    errors = " ".join(e.value for e in at.error)
    assert "Q99" in errors and "Q2" in errors
    assert next(b for b in at.button if b.label == "Evaluate").disabled
    assert any("fixes for the validation errors" in c.value for c in at.caption)


def test_an_unreadable_file_gives_a_friendly_error(tmp_path, monkeypatch):
    args = write_files(tmp_path / "sample_data", build(2))
    open(args["vendor"][0][1], "wb").write(b"\xff\xfe\x00bad")
    monkeypatch.setattr(ev, "BASE_DIR", str(tmp_path))
    at = AppTest.from_file(APP, default_timeout=180).run()
    at.text_input(key="vendor_name").set_value("Acme")
    at.toggle[0].set_value(True)
    at.run()
    assert not at.exception
    assert any("vendor_assamese.csv" in e.value for e in at.error)
    assert next(b for b in at.button if b.label == "Evaluate").disabled


def test_csv_exports_agree_with_the_results_table():
    res = sample_result(run_info={"vendor": "Acme", "hashes": {}})
    detail, summary = ev.export_tables(res, "Acme")
    assert list(detail["Vendor"].unique()) == ["Acme"] == list(summary["Vendor"])
    assert detail["Run ID"].eq(res.meta["run_id"]).all() and summary.loc[0, "Run ID"] == res.meta["run_id"]
    assert detail["Language"].tolist() == ev.LANGUAGES
    assert detail["BLEU Marks"].mean() == pytest.approx(res.summary["bleu"])
    assert summary.loc[0, "Total"] == round(res.summary["total"], 2)
    assert summary.loc[0, "Max"] == 17
    assert not any("(A)" in c or "(B)" in c for c in detail.columns)
    audit = json.loads(json.dumps(ev.audit_record(res)))
    assert audit["run_id"] == res.meta["run_id"]
    csv_roundtrip = pd.read_csv(pd.io.common.StringIO(detail.to_csv(index=False)))
    assert csv_roundtrip["BLEU Marks"].tolist() == detail["BLEU Marks"].tolist()


def test_sample_folder_layout_and_names():
    """The sample data is organised as the README says: source / reference / vendor, one file per language."""
    names = {sub: sorted(os.listdir(os.path.join(SAMPLE, sub))) for sub in ("source", "reference", "vendor")}
    assert names["source"] == ["source_english.csv", "source_hindi.csv"]
    assert names["reference"] == [f"reference_{ev._slug(lang)}.csv" for lang in sorted(ev.LANGUAGES, key=ev._slug)]
    assert len(names["vendor"]) == 12 and "vendor_manipuri_meitei.csv" not in names["vendor"]   # the deliberate gap
    assert sorted(os.listdir(SAMPLE)) == ["reference", "source", "vendor"]                      # no stray old-layout files


def test_sample_ids_are_unique_in_each_file_and_the_same_in_all_files():
    inp = ev.load_inputs(**sample_args())
    assert not inp.errors and not inp.warnings
    ids = list(inp.source["id"])
    assert len(ids) == len(set(ids))
    for lang, df in inp.refs.items():
        assert list(df["id"]) == ids, lang
    for lang, g in inp.vendor.groupby("target_lang"):
        assert set(g["id"]) <= set(ids), lang


def test_the_files_found_table_is_shown():
    at = new_app()
    at.text_input(key="vendor_name").set_value("Acme")
    at.toggle[0].set_value(True)
    at.run()
    assert not at.exception
    found = next(d for d in at.dataframe if "Reference file" in d.value.columns)
    assert len(found.value) == 13
    row = found.value.set_index("Language").loc["Manipuri (Meitei)"]
    assert row["Reference file"] == "reference_manipuri_meitei.csv" and row["Vendor file"] == "none"
