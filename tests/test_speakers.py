"""Tests for SpeakerClusterer (R4: call speakers told apart, stable labels)."""
import numpy as np

from livetrans.speakers import SpeakerClusterer

A = np.array([1.0, 0.0, 0.0, 0.0])        # voice A
A2 = np.array([0.9, 0.1, 0.0, 0.0])       # voice A again (similarity ~0.99)
B = np.array([0.0, 1.0, 0.0, 0.0])        # voice B (similarity 0 to A)


def test_first_voice_is_speaker_1():
    assert SpeakerClusterer().assign(A, 3.0)[0] == 1


def test_same_voice_keeps_its_label():
    c = SpeakerClusterer(threshold=0.5)
    c.assign(A, 3.0)
    assert c.assign(A2, 3.0)[0] == 1


def test_new_voice_gets_new_label():
    c = SpeakerClusterer(threshold=0.5)
    c.assign(A, 3.0)
    assert c.assign(B, 3.0)[0] == 2
    assert c.n_speakers == 2


def test_label_is_stable_when_speaker_returns():
    c = SpeakerClusterer(threshold=0.5)
    labels = [c.assign(v, 3.0)[0] for v in (A, B, A2, B)]
    assert labels == [1, 2, 1, 2]


def test_short_utterance_does_not_create_a_speaker():
    c = SpeakerClusterer(threshold=0.5, min_new_s=1.5)
    c.assign(A, 3.0)
    assert c.assign(B, 0.8)[0] == 1           # too short to trust: closest existing speaker
    assert c.n_speakers == 1


def test_short_utterance_does_not_change_the_average():
    c = SpeakerClusterer(threshold=0.5, min_new_s=1.5)
    c.assign(A, 3.0)
    c.assign(B, 0.8)                          # assigned to 1, but must not pull its average
    assert c.assign(A, 3.0)[1] > 0.99
