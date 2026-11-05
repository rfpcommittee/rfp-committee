"""Reading the per-language CSV files and cross-checking them (languages, ids, coverage)."""
import io

import pytest

import evaluator as ev
from conftest import build, load, parse, write_files


def errors_of(data, tmp_path):
    return load(data, tmp_path).errors


def validated(data, tmp_path):
    inp = load(data, tmp_path)
    assert not inp.errors, inp.errors
    return ev.validate(*inp.as_tuple())


# ---- the happy path
def test_valid_files(tmp_path):
    inp = load(build(3), tmp_path)
    assert not inp.errors and not inp.warnings
    assert len(inp.ref_files) == 13 and len(inp.vendor_files) == 13
    val = ev.validate(*inp.as_tuple())
    assert val.ok and not val.warnings
    assert val.info["expected_rows"] == 3 * 13 * 2 == val.info["received_rows"]
    assert val.info["missing_rows"] == 0


def test_joined_text_is_question_then_options(tmp_path):
    s, r, v = parse(build(1), tmp_path)
    assert s.loc[0, "english"] == "\n".join(f"english source {f} Q1" for f in ev.FIELDS)
    assert s.loc[0, "hindi"].startswith("हिंदी स्रोत भाग0 Q1\n")
    assert r["Tamil"].loc[0, "text"].count("\n") == 4


def test_every_file_is_hashed_under_its_group(tmp_path):
    inp = load(build(1), tmp_path)
    assert len(inp.hashes) == 2 + 13 + 13
    assert "source/source_english.csv" in inp.hashes and "reference/reference_tamil.csv" in inp.hashes
    assert "vendor/vendor_manipuri_meitei.csv" in inp.hashes
    assert all(len(h) == 64 for h in inp.hashes.values())


def test_uploaded_file_objects_work_like_paths(tmp_path):
    args = write_files(tmp_path, build(2))

    def upload(item):
        name, path = item
        return name, io.BytesIO(open(path, "rb").read())
    inp = ev.load_inputs(upload(args["source_english"]), upload(args["source_hindi"]),
                         [upload(x) for x in args["references"]], [upload(x) for x in args["vendor"]])
    assert not inp.errors
    assert ev.validate(*inp.as_tuple()).ok
    assert inp.hashes == ev.load_inputs(**args).hashes


def test_nothing_uploaded_yet(tmp_path):
    inp = ev.load_inputs()
    assert inp.source is None and inp.vendor is None and not inp.errors and inp.refs == {}


# ---- columns
@pytest.mark.parametrize("where,col", [("source_english", "option_c"), ("source_hindi", "id"), ("source_hindi", "question")])
def test_source_file_missing_a_column(tmp_path, where, col):
    data = build(2)
    data[where] = data[where].drop(columns=[col])
    errs = errors_of(data, tmp_path)
    assert any(f"{where}.csv" in e and col in e for e in errs)


def test_reference_file_missing_a_column_names_the_file(tmp_path):
    data = build(2)
    data["reference"]["Urdu"] = data["reference"]["Urdu"].drop(columns=["option_b"])
    errs = errors_of(data, tmp_path)
    assert len(errs) == 1 and "reference_urdu.csv" in errs[0] and "option_b" in errs[0]


@pytest.mark.parametrize("col", ["source_lang", "option_d", "id"])
def test_vendor_file_missing_a_column(tmp_path, col):
    data = build(2)
    data["vendor"]["Tamil"] = data["vendor"]["Tamil"].drop(columns=[col])
    errs = errors_of(data, tmp_path)
    assert any("vendor_tamil.csv" in e and col in e for e in errs)


def test_column_names_ignore_case_spaces_and_underscores(tmp_path):
    data = build(2)
    data["reference"]["Tamil"] = data["reference"]["Tamil"].rename(
        columns={"option_a": "Option A", "option_b": "OPTION-B", "id": "ID"})
    inp = load(data, tmp_path)
    assert not inp.errors and inp.refs["Tamil"]["text"].str.count("\n").eq(4).all()


def test_duplicate_column_header(tmp_path):
    data = build(2)
    args = write_files(tmp_path, data)
    path = args["source_english"][1]
    text = open(path, encoding="utf-8-sig").read().replace("option_a", "question", 1)
    open(path, "w", encoding="utf-8").write(text)
    assert any("duplicate column" in e for e in ev.load_inputs(**args).errors)


def test_headers_differing_only_by_case_are_ambiguous(tmp_path):
    data = build(2)
    r = data["reference"]["Tamil"].rename(columns={"option_a": "Option_A"})
    r.insert(1, "option_a", "x")
    data["reference"]["Tamil"] = r
    assert any("duplicate column" in e and "reference_tamil.csv" in e for e in errors_of(data, tmp_path))


# ---- ids: unique inside a file, the same question has the same id in every file
@pytest.mark.parametrize("where", ["source_english", "source_hindi"])
def test_duplicate_id_in_a_source_file(tmp_path, where):
    data = build(3)
    data[where].loc[1, "id"] = "Q1"
    errs = errors_of(data, tmp_path)
    assert any(f"{where}.csv" in e and "duplicate id" in e and "Q1" in e for e in errs)


def test_duplicate_id_in_a_reference_file(tmp_path):
    data = build(3)
    data["reference"]["Gujarati"].loc[2, "id"] = "Q1"
    errs = errors_of(data, tmp_path)
    assert len(errs) == 1 and "reference_gujarati.csv" in errs[0] and "duplicate id" in errs[0]


def test_duplicate_id_in_a_vendor_file_for_the_same_source(tmp_path):
    data = build(3)
    v = data["vendor"]["Tamil"]
    data["vendor"]["Tamil"] = v._append(v.iloc[0], ignore_index=True)
    errs = errors_of(data, tmp_path)
    assert any("vendor_tamil.csv" in e and "duplicate id" in e for e in errs)


def test_same_id_for_english_and_hindi_rows_of_one_vendor_file_is_normal(tmp_path):
    data = build(3)
    v = data["vendor"]["Tamil"]
    assert v["id"].duplicated().any()                         # Q1 appears for English and for Hindi
    assert not errors_of(data, tmp_path)


def test_blank_id(tmp_path):
    data = build(2)
    data["source_english"].loc[1, "id"] = ""
    assert any("empty id" in e and "source_english.csv" in e for e in errors_of(data, tmp_path))


def test_ids_that_differ_only_by_case_collide(tmp_path):
    data = build(3)
    data["reference"]["Odia"].loc[1, "id"] = "q1"            # Q1 and q1 in the same file
    errs = errors_of(data, tmp_path)
    assert any("reference_odia.csv" in e and "upper/lower case" in e for e in errs)


def test_whitespace_around_ids_is_ignored(tmp_path):
    data = build(2)
    data["reference"]["Odia"]["id"] = [" Q1 ", "Q2\t"]
    inp = load(data, tmp_path)
    assert not inp.errors and ev.validate(*inp.as_tuple()).ok


def test_english_and_hindi_source_must_have_the_same_ids(tmp_path):
    data = build(3)
    data["source_hindi"].loc[2, "id"] = "Q9"
    errs = errors_of(data, tmp_path)
    assert len(errs) == 1
    assert "same question ids" in errs[0] and "only in the English file: ['Q3']" in errs[0] \
        and "only in the Hindi file: ['Q9']" in errs[0]


def test_source_ids_that_differ_only_by_case_get_a_hint(tmp_path):
    data = build(2)
    data["source_hindi"]["id"] = ["q1", "Q2"]
    errs = errors_of(data, tmp_path)
    assert "'Q1' / 'q1'" in errs[0]


def test_reference_missing_question_id(tmp_path):
    data = build(3)
    data["reference"]["Tamil"] = data["reference"]["Tamil"].iloc[:2]
    val = validated(data, tmp_path)
    assert any("Reference Tamil" in e and "missing" in e and "Q3" in e for e in val.errors)
    assert not any("Telugu" in e for e in val.errors)


def test_reference_with_extra_id(tmp_path):
    data = build(3)
    data["reference"]["Telugu"].loc[0, "id"] = "Q77"
    val = validated(data, tmp_path)
    assert any("Reference Telugu" in e and "not in the source" in e and "Q77" in e for e in val.errors)
    assert any("Reference Telugu" in e and "missing" in e and "Q1" in e for e in val.errors)


def test_reference_id_in_a_different_case_is_explained(tmp_path):
    data = build(3)
    data["reference"]["Telugu"].loc[0, "id"] = "q1"
    val = validated(data, tmp_path)
    assert any("Telugu" in e and "'Q1' / 'q1'" in e for e in val.errors)


def test_vendor_ids_not_in_source_name_the_language_file(tmp_path):
    data = build(3)
    data["vendor"]["Bengali"].loc[0, "id"] = "Q99"
    val = validated(data, tmp_path)
    assert any("Q99" in e and "Bengali" in e for e in val.errors)


def test_the_same_id_in_all_files_is_what_makes_them_match(tmp_path):
    data = build(3)
    for df in [data["source_english"], data["source_hindi"], *data["reference"].values(), *data["vendor"].values()]:
        df["id"] = df["id"].str.replace("Q", "item-")        # rename every id the same way everywhere: still fine
    assert validated(data, tmp_path).ok


# ---- blank content
def test_blank_source_question_or_option(tmp_path):
    data = build(2)
    data["source_hindi"].loc[0, "option_d"] = ""
    assert any("source_hindi.csv" in e and "empty" in e for e in errors_of(data, tmp_path))


def test_fully_blank_reference_is_an_error(tmp_path):
    data = build(3)
    for f in ev.FIELDS:
        data["reference"]["Tamil"].loc[1, f] = ""
    val = validated(data, tmp_path)
    assert any("Reference Tamil" in e and "blank reference" in e for e in val.errors)


def test_one_blank_option_in_a_reference_is_a_warning_only(tmp_path):
    data = build(3)
    data["reference"]["Tamil"].loc[1, "option_c"] = ""
    inp = load(data, tmp_path)
    assert not inp.errors and any("Reference Tamil" in w and "blank" in w for w in inp.warnings)
    assert ev.validate(*inp.as_tuple()).ok


# ---- file names and languages
@pytest.mark.parametrize("name,lang", [
    ("reference_tamil.csv", "Tamil"), ("Reference-Tamil.CSV", "Tamil"), ("tamil.csv", "Tamil"),
    ("reference_manipuri_meitei.csv", "Manipuri (Meitei)"), ("reference_manipuri.csv", "Manipuri (Meitei)"),
    ("Reference Manipuri (Meitei).csv", "Manipuri (Meitei)"), ("vendor_odia_v2.csv", "Odia")])
def test_language_is_read_from_the_file_name(name, lang):
    assert ev.language_from_filename(name) == {lang}


def test_every_language_has_exactly_one_file_name_match():
    for lang in ev.LANGUAGES:
        assert ev.language_from_filename(f"reference_{ev._slug(lang)}.csv") == {lang}


def test_file_with_an_unrecognised_language_name(tmp_path):
    args = write_files(tmp_path, build(2))
    args["references"][0] = ("reference_klingon.csv", args["references"][0][1])
    inp = ev.load_inputs(**args)
    assert any("reference_klingon.csv" in e and "cannot tell which language" in e for e in inp.errors)
    assert "Assamese" not in inp.refs


def test_file_name_with_two_languages_is_ambiguous(tmp_path):
    args = write_files(tmp_path, build(2))
    args["references"][0] = ("reference_tamil_telugu.csv", args["references"][0][1])
    assert any("more than one language" in e for e in ev.load_inputs(**args).errors)


def test_two_files_for_one_language(tmp_path):
    args = write_files(tmp_path, build(2))
    args["vendor"].append(("vendor_tamil_copy.csv", args["vendor"][-1][1]))
    errs = ev.load_inputs(**args).errors
    assert any("two vendor files" in e for e in errs)


def test_vendor_file_added_as_a_reference_file_is_rejected(tmp_path):
    args = write_files(tmp_path, build(2))
    args["references"][10] = ("vendor_tamil.csv", args["vendor"][-1][1])
    inp = ev.load_inputs(**args)
    assert any("vendor_tamil.csv" in e and "looks like a vendor file" in e for e in inp.errors)


def test_reference_file_added_as_a_vendor_file_is_rejected(tmp_path):
    args = write_files(tmp_path, build(2))
    args["vendor"][0] = ("reference_assamese.csv", args["references"][0][1])
    assert any("looks like a reference file" in e for e in ev.load_inputs(**args).errors)


def test_a_missing_reference_language_is_a_validation_error(tmp_path):
    args = write_files(tmp_path, build(2))
    args["references"] = [x for x in args["references"] if "urdu" not in x[0]]
    inp = ev.load_inputs(**args)
    assert not inp.errors
    val = ev.validate(*inp.as_tuple())
    assert any("no file for Urdu" in e for e in val.errors)


def test_optional_target_lang_column_must_agree_with_the_file(tmp_path):
    data = build(2)
    data["vendor"]["Tamil"]["target_lang"] = "Tamil"
    assert not errors_of(data, tmp_path)
    data["vendor"]["Tamil"].loc[0, "target_lang"] = "Telugu"
    assert any("vendor_tamil.csv" in e and "target_lang" in e for e in errors_of(data, tmp_path))


def test_source_language_names_accept_aliases_and_case(tmp_path):
    data = build(1)
    v = data["vendor"]["Tamil"]
    v["source_lang"] = v["source_lang"].replace({"Hindi": "hi", "English": "EN"})
    inp = load(data, tmp_path)
    assert not inp.errors and ev.validate(*inp.as_tuple()).info["unsupported_rows"] == 0


def test_unsupported_vendor_source_language_is_reported_not_silent(tmp_path):
    data = build(2)
    v = data["vendor"]["Tamil"]
    data["vendor"]["Tamil"] = v._append(v.iloc[[0]].assign(source_lang="Klingon"), ignore_index=True)
    val = validated(data, tmp_path)
    assert val.ok and val.info["unsupported_rows"] == 1
    assert any("source_lang" in w and "Klingon" in w for w in val.warnings)


def test_vendor_file_with_no_usable_rows(tmp_path):
    data = build(1)
    data["vendor"]["Tamil"]["source_lang"] = "Klingon"
    assert any("vendor_tamil.csv" in e and "no usable rows" in e for e in errors_of(data, tmp_path))


def test_swapped_source_files_are_flagged(tmp_path):
    data = build(2)
    data["source_english"], data["source_hindi"] = data["source_hindi"], data["source_english"]
    inp = load(data, tmp_path)
    assert any("English" in w and "looks like Hindi" in w for w in inp.warnings)
    assert any("Hindi" in w and "other than Hindi" in w for w in inp.warnings)
    assert not inp.errors                                   # only a warning: the user decides


# ---- vendor coverage
def test_missing_vendor_output_is_counted_by_language_and_direction(tmp_path):
    def vf(lang, src, i, parts):
        if lang == "Odia" and src == "English":
            return None
        if lang == "Tamil" and src == "Hindi" and i == "Q2":
            return ["", "", "", "", ""]
        return parts
    val = validated(build(3, vf), tmp_path)
    odia = val.coverage.set_index("Language").loc["Odia"]
    assert odia["English received"] == 0 and odia["Hindi received"] == 3
    assert val.coverage.set_index("Language").loc["Tamil", "Hindi received"] == 2
    assert val.info["missing_rows"] == 3 + 1
    assert any("no output for English to Odia" in w for w in val.warnings)
    assert any("Tamil" in w and "1 of 3" in w for w in val.warnings)


def test_a_language_without_a_vendor_file_is_flagged_and_scores_zero(tmp_path):
    data = build(2, lambda lang, s, i, parts: None if lang == "Urdu" else parts)
    assert "Urdu" not in data["vendor"]
    inp = load(data, tmp_path)
    assert not inp.errors and "Urdu" not in inp.vendor_files
    val = ev.validate(*inp.as_tuple())
    assert any("Urdu: no vendor output at all" in w for w in val.warnings)
    assert val.info["missing_rows"] == 2 * 2


def test_vendor_files_for_only_some_languages(tmp_path):
    data = build(2)
    data["vendor"] = {k: v for k, v in data["vendor"].items() if k in ("Tamil", "Telugu")}
    inp = load(data, tmp_path)
    assert not inp.errors and sorted(inp.vendor_files) == ["Tamil", "Telugu"]
    val = ev.validate(*inp.as_tuple())
    assert val.ok and val.info["received_rows"] == 2 * 2 * 2


# ---- cross-check at evaluation time
def test_evaluate_refuses_inconsistent_files(tmp_path):
    data = build(3)
    data["reference"]["Tamil"] = data["reference"]["Tamil"].iloc[:2]
    parsed = parse(data, tmp_path)
    with pytest.raises(ev.InputError, match="do not match"):
        ev.evaluate(*parsed)


# ---- encoding and empty files
def test_invalid_encoding(tmp_path):
    args = write_files(tmp_path, build(1))
    open(args["source_english"][1], "wb").write("id,question\nQ1,caf\xe9\n".encode("latin-1"))
    assert any("UTF-8" in e and "source_english.csv" in e for e in ev.load_inputs(**args).errors)


def test_empty_file_and_header_only(tmp_path):
    args = write_files(tmp_path, build(1))
    open(args["source_english"][1], "wb").write(b"")
    assert any("empty" in e for e in ev.load_inputs(**args).errors)
    open(args["source_english"][1], "w", encoding="utf-8").write("id,question\n")
    assert ev.load_inputs(**args).errors


def test_a_bad_file_does_not_hide_the_other_problems(tmp_path):
    args = write_files(tmp_path, build(2))
    open(args["references"][0][1], "wb").write(b"")
    open(args["vendor"][0][1], "wb").write(b"")
    assert len(ev.load_inputs(**args).errors) == 2


def test_file_sha256_of_path_and_upload(tmp_path):
    f = tmp_path / "x.csv"
    f.write_bytes(b"abc")
    up = type("U", (), {"getvalue": lambda self: b"abc"})()
    assert ev.file_sha256(str(f)) == ev.file_sha256(up)
    assert ev.file_sha256(str(f)).startswith("ba7816bf")
