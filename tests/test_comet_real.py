"""End-to-end with the real Unbabel/wmt22-comet-da model. Skipped unless RUN_COMET_TEST=1 (it loads a 2 GB model and
takes a few minutes on a CPU). Needs unbabel-comet installed and the model downloaded or COMET_CHECKPOINT set.

    set RUN_COMET_TEST=1
    .venv\\Scripts\\python -m pytest tests/test_comet_real.py -q
"""
import math
import os

import pytest

import evaluator as ev
from conftest import build, parse

pytestmark = pytest.mark.skipif(os.environ.get("RUN_COMET_TEST") != "1", reason="set RUN_COMET_TEST=1 to run the real model")


def test_real_comet_end_to_end(tmp_path):
    model = ev.load_comet_model()
    noisy = lambda lang, s, i, parts: [p.replace("alpha", "omega") for p in parts]   # noqa: E731
    parsed = parse(build(1, noisy), tmp_path)
    a = ev.evaluate(*parsed, with_comet=True, comet_model=model)
    b = ev.evaluate(*parsed, with_comet=True, comet_model=model)
    assert a.summary["with_comet"] and a.summary["max_total"] == 27
    for col in ("COMET En→T", "COMET Hi→T", "Max COMET"):
        assert a.table[col].map(lambda x: math.isfinite(x) and -1 < x < 2).all(), col
    assert set(a.table["COMET Marks"]) <= {0, 4, 7, 10}
    assert a.table["COMET En→T"].tolist() == pytest.approx(b.table["COMET En→T"].tolist())   # repeatable
    assert "wmt22-comet-da" in a.meta["comet"] or os.environ.get("COMET_CHECKPOINT")
