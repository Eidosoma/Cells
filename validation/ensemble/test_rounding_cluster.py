"""First-divergence evidence, complete tick coverage and state reconstruction."""

import numpy as np
import pytest

from cells.assembly_cell.io import flatten
from cells.assembly_cluster import engine
from validation.ensemble import rounding_cluster as trace
from validation.ensemble.test_parallel_cluster import physical_spec


def sample(tick):
    return {"tick": np.full(2, tick, dtype=np.uint32), "energy": np.array([1.0, 2.0])}


def test_first_one_ulp_difference_is_retained_even_if_later_values_match(tmp_path):
    reference = [sample(t) for t in range(4)]
    recorder = trace.TickTrace(reference[0], 3, reference=reference)
    assert recorder.append(1, sample(1)) is None
    value = sample(2)
    value["energy"][1] = np.nextafter(value["energy"][1], np.inf)
    first = recorder.append(2, value)
    value["energy"][:] = 99
    assert first["tick"] == 2
    assert first["different_fields"]["energy"]["max_ulp_difference"] == 1
    assert recorder.append(3, sample(3)) is None
    assert recorder.first is first
    assert recorder.first_by_field["energy"]["tick"] == 2
    recorder.save(tmp_path / "trace.npz")
    saved = trace.load_arrays(tmp_path / "trace.npz")
    assert saved["energy"].shape == (4, 2)
    assert saved["energy"][2, 1] == np.nextafter(2.0, np.inf)
    np.testing.assert_array_equal(saved["tick"][:, 0], np.arange(4))
    with pytest.raises(FileExistsError):
        recorder.save(tmp_path / "trace.npz")


def test_each_field_records_its_own_first_different_tick():
    reference = [sample(t) | {"counter": np.zeros(2, np.uint32)} for t in range(4)]
    recorder = trace.TickTrace(reference[0], 3, reference=reference)
    for tick in range(1, 4):
        value = {k: v.copy() for k, v in reference[tick].items()}
        if tick >= 2:
            value["energy"][0] = np.nextafter(1.0, np.inf)
        if tick == 3:
            value["counter"][0] = 1
        recorder.append(tick, value)
    assert recorder.first["tick"] == 2
    assert recorder.first_by_field["energy"]["tick"] == 2
    assert recorder.first_by_field["counter"]["tick"] == 3


@pytest.mark.parametrize("window,state_tick", [(0, 0), (2, 2), (1, 0), (1, 2)])
def test_missing_repeated_or_wrong_tick_refused(window, state_tick):
    recorder = trace.TickTrace(sample(0), 2)
    with pytest.raises(ValueError):
        recorder.append(window, sample(state_tick))
    assert len(recorder.samples) == 1


def test_repeated_tick_and_incomplete_reference_refused():
    recorder = trace.TickTrace(sample(0), 2)
    recorder.append(1, sample(1))
    with pytest.raises(ValueError, match="Missing or repeated"):
        recorder.append(1, sample(1))
    with pytest.raises(ValueError, match="incomplete"):
        trace.TickTrace(sample(0), 2, reference=[sample(0)])
    changed = sample(0)
    changed["energy"][0] += 1
    with pytest.raises(ValueError, match="Initial states differ"):
        trace.TickTrace(changed, 1, reference=[sample(0), sample(1)])


def test_schema_check_does_not_compare_new_values_to_initial_values():
    initial = sample(0) | {"pending_time": np.array([0.0, np.inf])}
    recorder = trace.TickTrace(initial, 1)
    next_state = sample(1) | {"pending_time": np.array([np.inf, np.inf])}
    recorder.append(1, next_state)
    assert np.all(np.isinf(recorder.samples[1]["pending_time"]))


@pytest.mark.parametrize("corruption", ["missing", "dtype", "shape"])
def test_complete_state_reconstruction_refuses_corruption(corruption):
    initial = engine.initial_state(physical_spec())
    values = flatten(initial)
    restored = trace.state_from_arrays(initial, values)
    assert not trace.differences(values, flatten(restored))["different_fields"]
    values = {k: np.array(v, copy=True) for k, v in values.items()}
    if corruption == "missing":
        del values["tick"]
    elif corruption == "dtype":
        values["tick"] = values["tick"].astype(np.uint64)
    else:
        values["tick"] = values["tick"][:, None]
    with pytest.raises(ValueError, match="trace state|Trace state"):
        trace.state_from_arrays(initial, values)
