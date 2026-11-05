"""Slab boundaries. Scores are never rounded before marking (Run1 2.6)."""
import pytest

import rfp_final_table as rft

# BLEU Option B with the committee's revised instruction: 30 to below 40 = 8 and anything below 30 = 0.
# (Run1 3.4 alone would give 7, 6 and 5 below 30. The policy id recorded in every report names the revised rule.)
BLEU_CASES = [(0, 0), (20, 0), (29, 0), (29.99, 0), (30, 8), (39.99, 8), (40, 9), (49.99, 9), (50, 10),
              (59.99, 10), (60, 11), (69.99, 11), (70, 12), (100, 12)]


@pytest.mark.parametrize("score,marks", BLEU_CASES)
def test_bleu_option_b(score, marks):
    assert rft.bleu_marks(score) == marks


def test_bleu_old_name_is_the_same_function():
    assert rft.bleu_b is rft.bleu_marks


def test_bleu_examples_from_run1():
    assert rft.bleu_marks(65) == 11        # Run1 3.4 example
    assert rft.bleu_marks(41.5) == 9       # Run1 3.4 example


def test_policy_id_names_the_revised_rule():
    assert "Option B" in rft.POLICY_ID and "below 30 = 0" in rft.POLICY_ID


def test_option_a_is_gone():
    assert not hasattr(rft, "bleu_a")


@pytest.mark.parametrize("score,marks", [(0.6499, 0), (0.65, 4), (0.7499, 4), (0.75, 7), (0.8499, 7), (0.85, 10), (0.845, 7)])
def test_comet(score, marks):
    assert rft.comet_marks(score) == marks


@pytest.mark.parametrize("score,marks", [(64.99, 0), (65, 3), (74.99, 3), (74.5, 3), (75, 5)])
def test_chrf(score, marks):
    assert rft.chrf_marks(score) == marks


def test_cli_table_averages_over_languages():
    import pandas as pd
    parts = [pd.DataFrame({"Target": ["A", "B"], "Max BLEU": [80.0, 10.0]}),
             pd.DataFrame({"Target": ["A", "B"], "Max chrF++": [80.0, 80.0]})]
    t = rft.build_table(parts)
    last = t.iloc[-1]
    assert last["BLEU Marks"] == 6.0           # (12 + 0) / 2
    assert last["chrF++ Marks"] == 5.0
    assert last["Max Marks"] == 17             # out of 17, like the app, not a sum over languages
