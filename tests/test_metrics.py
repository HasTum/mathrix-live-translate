"""Tests for CER/WER. We must trust these numbers before using them to choose models."""
import pytest

from livetrans.eval.metrics import cer, normalize, wer


def test_identical_text_scores_zero():
    s = "Այսօր եղանակը շատ լավ է Երևանում։"
    assert cer(s, s) == 0.0
    assert wer(s, s) == 0.0


def test_punctuation_and_case_are_ignored():
    assert cer("Բարև, ինչպե՞ս ես։", "բարև ինչպես ես") == 0.0


def test_question_mark_inside_word_does_not_split_it():
    assert normalize("ինչպե՞ս") == "ինչպես"


def test_both_spellings_of_yev_are_equal():
    assert cer("և", "եւ") == 0.0
    assert wer("հաջողություն և ցտեսություն", "հաջողություն եւ ցտեսություն") == 0.0


def test_one_substitution():
    assert cer("abcd", "abxd") == pytest.approx(0.25)


def test_word_deletion_and_insertion():
    assert wer("a b c", "a c") == pytest.approx(1 / 3)
    assert wer("a b", "a b c") == pytest.approx(0.5)


def test_empty_hypothesis_is_all_wrong():
    assert cer("abc", "") == 1.0
    assert wer("a b", "") == 1.0


def test_empty_reference_is_an_error():
    with pytest.raises(ValueError):
        cer("", "abc")
