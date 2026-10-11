"""Missing observations are unknown; observer failure cannot strand a sampler."""

import pytest

from validation.ensemble.qualification_metrics import GpuQualificationMetrics, busy_summary


def test_busy_mean_uses_observed_time_and_reports_missing_coverage():
    row = busy_summary([{"time": 0.0, "gpus": {"gpu": {"utilization_pct": 80}}}], "gpu", 0, 6)
    assert row["mean_pct_over_covered_time"] == 80
    assert row["coverage_fraction"] == 0.5
    assert not row["coverage_pass"] and not row["missing_values_are_zero"]
    assert busy_summary([], "gpu", 0, 6)["mean_pct_over_covered_time"] is None


def test_both_samplers_are_stopped_even_if_the_first_cleanup_fails(tmp_path):
    stopped = []

    class Monitor:
        def __init__(self, name):
            self.name = name

        def finish(self):
            stopped.append(self.name)
            if self.name == "busy":
                raise RuntimeError("Injected busy monitor failure")

    observer = GpuQualificationMetrics(tmp_path, {})
    observer.busy, observer.counters = Monitor("busy"), Monitor("counters")
    with pytest.raises(RuntimeError, match="Injected"):
        observer.close()
    assert stopped == ["busy", "counters"]
    assert (tmp_path / "cleanup-failure.json").is_file()
    observer.close()
    assert stopped == ["busy", "counters"]
