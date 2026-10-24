"""Tests for the known-truth speaker evaluation: we must trust the scores before
using them to compare labelling methods."""
import numpy as np

from livetrans.tools.speakers_eval import SR, build_scenario, parse_clip, score


def test_perfect_labels():
    s = score([1, 2, 1, 2], ["A", "B", "A", "B"])
    assert (s["splits"], s["merges"], s["ghosts"], s["accuracy"]) == (0, 0, 0, 1.0)


def test_merge_is_counted():
    s = score([1, 1, 1, 1], ["A", "B", "A", "B"])
    assert s["merges"] == 1 and s["accuracy"] == 0.5


def test_split_is_counted():
    s = score([1, 2, 3, 2], ["A", "B", "A", "B"])
    assert s["splits"] == 1 and s["accuracy"] == 0.75


def test_mixed_pieces_are_not_scored_as_turns():
    s = score([1, 1, 2], ["A+B", "A", "B"])
    assert s["accuracy"] == 1.0 and s["found"] == 2
    assert (s["mixed"], s["mixed_ok"], s["ghosts"]) == (1, 1, 0)


def test_label_used_only_by_a_mixed_piece_is_a_ghost():
    s = score([1, 2, 3], ["A", "A+B", "B"])
    assert s["ghosts"] == 1 and s["mixed_ok"] == 0
    assert s["accuracy"] == 1.0 and s["found"] == 3


def test_mixed_piece_with_a_third_persons_label_is_not_ok():
    s = score([1, 2, 3, 3], ["A", "B", "C", "A+B"])
    assert s["mixed_ok"] == 0 and s["ghosts"] == 0


def test_clip_range_parsing():
    assert parse_clip("samples/x.wav:0:40") == ("samples/x.wav", 0.0, 40.0)
    assert parse_clip("samples/x.wav") == ("samples/x.wav", 0.0, None)


def test_mixed_start_begins_with_a_7_s_mixed_piece():
    pieces = {n: [np.ones(8 * SR, np.float32)] * 5 for n in "ABC"}
    seq, _ = build_scenario("mixed-start", pieces, rounds=2)
    assert seq[0][1] == "A+B" and len(seq[0][0]) == 7 * SR
    assert [t for _, t in seq[1:]] == ["A", "B", "C", "A", "B", "C"]


def test_handovers_insert_mixed_pieces():
    pieces = {n: [np.ones(8 * SR, np.float32)] * 9 for n in "AB"}
    seq, _ = build_scenario("handovers", pieces, rounds=2)
    truth = [t for _, t in seq]
    assert truth == ["A", "B", "B+A", "A", "B"]
