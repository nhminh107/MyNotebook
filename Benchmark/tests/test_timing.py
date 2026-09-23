from rag_benchmark.timing import LatencyRecorder, percentile


def test_percentile_interpolates() -> None:
    assert percentile([1.0, 2.0, 3.0], 0.5) == 2.0
    assert percentile([], 0.95) == 0.0


def test_latency_recorder_returns_value_and_summary() -> None:
    recorder = LatencyRecorder()
    assert recorder.measure(lambda: 42) == 42
    summary = recorder.summary()
    assert summary["count"] == 1
    assert summary["mean_ms"] >= 0.0

