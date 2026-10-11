"""Standalone recorded-source auditing tests; no upstream imports or runs."""

import copy

import numpy as np
import pytest

from scripts import compare_source_pair_native as audit
from tests import reference_source_pair_numerics as ref


def fixture():
    panel = ref.eq.load_panel()
    model = ref.Model(panel, panel["cases"][5])
    y = model.initial()
    packet = ref.eq.derived_packet(model.anchor, model.context)
    slope = model.derivative(y, 0)[:12].reshape(6, 2)
    final = packet.copy()
    final[ref.eq.PRIMARY_INDEX] += slope * 3 * 0.005
    controls = copy.deepcopy(model.held[0]["controls"])
    record = {"level": {"time_step": 0.005}}
    phase = {
        "index": 0,
        "steps": 1,
        "local_accepted_time": 0.015,
        "actual_start": 0.0,
        "controls": controls,
    }
    arrays = {
        "incoming_packet": packet.copy(),
        "initial_packet": packet.copy(),
        "start_times": np.array([0.0]),
        "raw_start_packets": packet[None].copy(),
        "refreshed_caches": packet[None, ref.eq.DERIVED_INDEX].copy(),
        "primary_slopes": slope[None],
        "step_multiples": np.array([3]),
        "final_packet": final,
        "sample_times": np.array([0.015]),
        "sample_packets": final[None].copy(),
    }
    return model, record, phase, arrays


def test_native_integer_clock_raw_cache_and_euler_audit():
    model, record, phase, arrays = fixture()
    times, values, result = audit.audit_phase(model, record, phase, arrays)
    assert result["steps"] == result["rhs_witnesses"] == 1
    assert result["raw_primary_updates_exact"]
    assert result["raw_cache_carryover_exact"]
    np.testing.assert_array_equal(times, [0.0, 0.015])
    np.testing.assert_array_equal(
        values[-1, :12], arrays["final_packet"][ref.eq.PRIMARY_INDEX].ravel()
    )


@pytest.mark.parametrize(
    "corruption",
    ["clock", "rate", "cache", "context", "sample_time", "control", "initial", "shape"],
)
def test_source_audit_detects_corruption(corruption):
    model, record, phase, arrays = fixture()
    if corruption == "clock":
        arrays["step_multiples"][0] = 4
    elif corruption == "rate":
        arrays["primary_slopes"][0, 0, 0] += 1
    elif corruption == "cache":
        arrays["refreshed_caches"][0, 0, 0] += 1
    elif corruption == "context":
        arrays["final_packet"][3, 0] += 1
    elif corruption == "sample_time":
        arrays["sample_times"][0] = 0.02
    elif corruption == "control":
        phase["controls"]["mirna_contact"] = 0.25
    elif corruption == "initial":
        arrays["raw_start_packets"][0, 0, 0] += 1
    else:
        arrays["primary_slopes"] = arrays["primary_slopes"][:, :, :1]
    with pytest.raises((ValueError, AssertionError)):
        audit.audit_phase(model, record, phase, arrays)
