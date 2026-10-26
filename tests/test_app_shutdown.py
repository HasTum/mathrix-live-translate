"""Tests for stopping the live app (Ctrl+C): the summary must always be printed and
utterances left in the queue must be counted, not silently dropped."""
import queue
import threading

from livetrans.app import finish, report


class InterruptedJoin:
    """Stands in for the worker thread when the user presses Ctrl+C a second time."""
    def join(self, timeout=None):
        raise KeyboardInterrupt


class StuckWorker:
    """Stands in for a worker that is still busy when the timeout ends."""
    def join(self, timeout=None):
        return None


def queued(n):
    q = queue.Queue()
    for i in range(n):
        q.put(f"utterance {i}")
    q.put(None)                               # stop signal, as in main()
    return q


def test_worker_finishes_the_queue():
    q = queued(3)

    def work():
        while q.get() is not None:
            pass

    th = threading.Thread(target=work)
    th.start()
    assert finish(th, q, timeout_s=5) == 0


def test_second_ctrl_c_counts_unprocessed():
    assert finish(InterruptedJoin(), queued(3), timeout_s=5) == 3


def test_timeout_counts_unprocessed():
    assert finish(StuckWorker(), queued(2), timeout_s=0) == 2


def test_summary_without_segments_shows_unprocessed(capsys):
    report([], [], 0, unprocessed=2)
    assert "2 not processed" in capsys.readouterr().out


def test_summary_with_segments_shows_unprocessed(capsys):
    rec = {"source": "system", "latency": 3.0, "audio": 7.0, "wait": 0.0,
           "asr": 0.4, "spk": 0.2, "mt": 2.4}
    report([rec], [], 1, unprocessed=1)
    out = capsys.readouterr().out
    assert "1 segments" in out and "1 not processed" in out and "over 5 s: 0" in out
