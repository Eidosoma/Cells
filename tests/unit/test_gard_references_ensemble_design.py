"""The registered beta = 0 ensemble design as a machine-readable input, and its run rules.

Planted controls: a run that stops before t = 2, and two runs sharing a stream. Both must
be refused as a harness failure, never read as a verdict. An extinct run is a valid sample.
"""

from __future__ import annotations

import copy
import json

import numpy as np
import pytest

from validation.gard.references import harness
from validation.gard.references.records import RecordFormatError, in_memory_bundle
from validation.gard.references.standin import ensemble_arrays


def test_the_design_file_transcribes_the_readme_values(tmp_path):
    out = harness.make_probe_inputs(tmp_path / "probes")
    d = json.loads((out / "beta0_ensemble_design.json").read_text())
    assert json.loads((out / "inputs.json").read_text())["beta0_ensemble"] == "beta0_ensemble_design.json"
    # the README's row 1: 4 types, k_f = 1, k_b = 0.5, rho = (0.1, 0.2, 0.3, 0.4), founder (5, 5, 5, 5),
    # t = 0.5, 1, 1.5, 2, 500 runs
    assert d["types"] == 4 and d["k_join"] == [1.0] * 4 and d["k_leave"] == [0.5] * 4
    assert d["transfer_constant"] == [2.0] * 4 and d["rho"] == [0.1, 0.2, 0.3, 0.4]
    assert d["founder"] == [5, 5, 5, 5] and d["observation_times"] == [0.5, 1.0, 1.5, 2.0]
    assert d["observation_time"] == 2.0 and d["runs"] == 500
    assert "no value changed" in d["note"] and "running_at_observation_time" in d["requirements"]


def test_the_committed_design_file_is_what_make_probes_writes(tmp_path):
    from pathlib import Path
    committed = Path(harness.__file__).with_name("beta0_ensemble_design.json").read_text()
    out = harness.make_probe_inputs(tmp_path / "p")
    assert json.loads(committed) == json.loads((out / "beta0_ensemble_design.json").read_text())


@pytest.fixture(scope="module")
def members():
    return [in_memory_bundle(w, r, a, path=f"<member {k}>") for k, (w, r, a) in enumerate(ensemble_arrays(3, seed=9))]


def test_a_valid_ensemble_is_read(members):
    times, counts, w = harness.ensemble_counts(members)
    assert counts.shape == (3, 4, 4) and np.all(counts.sum(axis=2) > 0)


def _variant(b, **run_changes):
    run = copy.deepcopy(b.run_raw)
    run.update(run_changes)
    return in_memory_bundle(b.world_raw, run, dict(b.arrays), path=b.path + " (variant)")


def test_a_run_that_stops_before_t2_is_a_harness_failure(members):
    b = members[1]
    keep = b.arrays["event_time"] <= 1.5
    arrays = dict(b.arrays, event_time=b.arrays["event_time"][keep], event_channel=b.arrays["event_channel"][keep])
    run = dict(copy.deepcopy(b.run_raw), end_status="event_limit", t_end=1.5)
    stopped = in_memory_bundle(b.world_raw, run, arrays, path="<stopped>")
    with pytest.raises(RecordFormatError, match="stopped before t = 2"):
        harness.ensemble_counts([members[0], stopped, members[2]])


def test_an_extinct_run_is_a_valid_sample_and_a_false_extinction_is_not(members):
    b = members[0]
    codes = np.repeat(-np.arange(1, 5), 5)  # every founder molecule leaves
    times = np.linspace(0.01, 0.2, codes.size)
    run = dict(copy.deepcopy(b.run_raw), end_status="extinct", t_end=0.2, stream={"seed": 9, "branch": 999})
    extinct = in_memory_bundle(b.world_raw, run, dict(b.arrays, event_time=times, event_channel=codes),
                               path="<extinct>")
    _, counts, _ = harness.ensemble_counts([extinct, members[1], members[2]])
    assert np.all(counts[0, :, :] == 0)
    half = in_memory_bundle(b.world_raw, run, dict(b.arrays, event_time=times[:10], event_channel=codes[:10]),
                            path="<half>")
    with pytest.raises(RecordFormatError, match="stopped before"):
        harness.ensemble_counts([half, members[1], members[2]])


def test_runs_sharing_a_stream_are_refused(members):
    twin = _variant(members[1], stream=members[0].run_raw["stream"])
    with pytest.raises(RecordFormatError, match="stream identity"):
        harness.ensemble_counts([members[0], twin, members[2]])
    copy_trace = in_memory_bundle(members[0].world_raw, dict(copy.deepcopy(members[0].run_raw), stream={"x": 1}),
                                  dict(members[0].arrays), path="<copy>")
    with pytest.raises(RecordFormatError, match="reused stream"):
        harness.ensemble_counts([members[0], copy_trace])
