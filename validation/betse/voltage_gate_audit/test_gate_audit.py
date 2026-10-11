"""Actual saved evidence and corruption checks; never execute either simulator."""

import copy
import importlib
import shutil
import sys
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
audit = importlib.import_module("gate_audit")
ind = importlib.import_module("gate_independent")


@pytest.fixture(scope="module")
def data():
    with audit.model_fence():
        return audit.load_capture()


@pytest.fixture(scope="module")
def reference(data):
    return ind.build_reference(data["registration"]["protocol"])


@pytest.fixture(scope="module")
def rebuilt(data, reference):
    return ind.review(data["registration"]["protocol"], data["native"], data["cells"], reference)


def test_complete_packet_and_independent_reconstruction(data, rebuilt):
    result = ind.match_saved(rebuilt, data["comparison"])
    assert result["independent_comparisons"] == 11266
    assert len(data["hashes"]) == 13
    assert result["failed_comparisons"] == 0
    assert result["measured_refinements"] == 36 and result["roundoff_limited"] == 12
    assert result["native_finest_max_gate_error"] == 0.007401469420033613
    assert result["cells_finest_max_gate_error"] == 9.379715670831956e-9


def test_frozen_replay_without_model_import(data):
    with audit.model_fence():
        _, ref = audit.frozen_helpers()
        assert (
            ref.evaluate(data["registration"]["protocol"], data["native"], data["cells"])
            == data["comparison"]
        )


@pytest.mark.parametrize("module", audit.FORBIDDEN)
def test_import_fence(module):
    with audit.model_fence(), pytest.raises(RuntimeError, match="Model import forbidden"):
        importlib.import_module(module)


@pytest.mark.parametrize("engine", ["betse", "cells"])
def test_affine_power_matches_repeated_independent_steps(engine):
    with localcontext() as context:
        context.prec = 80
        targets, tau = ind.kinetics(0.02)
        q, dt = Decimal("0.37"), Decimal("0.001")
        expected = q
        for _ in range(17):
            expected = ind.single_step(expected, targets[0], tau[0], dt, engine)
        assert abs(ind.affine_power(q, targets[0], tau[0], dt, 17, engine) - expected) < Decimal(
            "1e-76"
        )


def test_observation_grid_is_independent_of_solver(data):
    p = data["registration"]["protocol"]
    case = copy.deepcopy(p["cases"][1])
    with localcontext() as context:
        context.prec = 80
        fine = ind.history(case, 250, "cells")
        case["segments"][0]["sample_every_us"] *= 2
        assert ind.history(case, 250, "cells") == fine[::2]
    pulse = p["cases"][3]
    times, volts = ind.timeline(pulse)
    assert len(times) == len(set(times)) == 61
    assert volts[times.index(10000)] == 0.02 and volts[times.index(20000)] == -0.08


@pytest.mark.parametrize("mutation", ["gate", "hidden_product", "tau_units", "open_fraction"])
def test_rehashed_numeric_corruption_not_accepted(data, reference, mutation):
    native, cells = copy.deepcopy((data["native"], data["cells"]))
    trace = cells["trajectories"]["activation/250"]
    if mutation == "gate":
        trace["gate"][-1][0] += 0.001
    elif mutation == "hidden_product":
        trace["gate"][5] = list(reversed(trace["gate"][5]))
    elif mutation == "tau_units":
        native["kinetics"]["tau_s"][0][0] *= 1000
    else:
        trace["open_fraction"][-1] -= 0.001
    changed = ind.review(data["registration"]["protocol"], native, cells, reference)
    assert any(not row["pass"] for row in changed["rows"].values())
    with pytest.raises(ValueError):
        ind.match_saved(changed, data["comparison"])


@pytest.mark.parametrize(
    "mutation", ["time", "voltage", "truncated", "nan", "boolean", "stages", "steps", "missing_run"]
)
def test_structural_corruption_rejected(data, reference, mutation):
    native = copy.deepcopy(data["native"])
    trace = native["trajectories"]["activation/250"]
    if mutation == "time":
        trace["time_us"][-1] += 1
    elif mutation == "voltage":
        trace["voltage_V"][-1] = 20
    elif mutation == "truncated":
        trace["gate"].pop()
    elif mutation == "nan":
        trace["gate"][1][0] = float("nan")
    elif mutation == "boolean":
        trace["gate"][1][0] = True
    elif mutation == "stages":
        trace["all_steps_valid"] = False
    elif mutation == "steps":
        trace["steps"] += 1
    else:
        native["trajectories"].pop("activation/250")
    with pytest.raises(ValueError):
        ind.review(data["registration"]["protocol"], native, data["cells"], reference)


@pytest.mark.parametrize(
    "mutation", ["duplicate", "omitted", "summary", "maximum", "roundoff", "expected"]
)
def test_saved_comparison_corruption_rejected(data, rebuilt, mutation):
    saved = copy.deepcopy(data["comparison"])
    if mutation == "duplicate":
        saved["comparisons"][0] = saved["comparisons"][1]
    elif mutation == "omitted":
        saved["comparisons"].pop()
    elif mutation == "summary":
        saved["failed_comparisons"] = 1
    elif mutation == "maximum":
        saved["maximum_normalized_error"] = 0
    elif mutation == "roundoff":
        saved["refinement"][-1]["status"] = "measured"
    else:
        saved["comparisons"][0]["expected"] += 0.01
    with pytest.raises(ValueError):
        ind.match_saved(rebuilt, saved)


@pytest.mark.parametrize("mutation", ["payload", "missing", "extra", "symlink"])
def test_packet_bytes_and_membership_rejected(tmp_path, data, mutation):
    packet = tmp_path / "copy"
    shutil.copytree(audit.CAPTURE, packet)
    if mutation == "payload":
        (packet / "betse.log").write_text("changed only in temporary test copy")
    elif mutation == "missing":
        (packet / "cells.log").unlink()
    elif mutation == "extra":
        (packet / "extra.json").write_text("{}")
    else:
        (packet / "link").symlink_to(packet / "cells.json")
    with pytest.raises(ValueError):
        audit.manifest(packet, data["completion"])
    assert audit.packet_hashes(audit.CAPTURE) == data["hashes"]


@pytest.mark.parametrize(
    "mutation", ["chronology", "duration", "scope", "temperature", "initial_P"]
)
def test_metadata_cannot_expand_the_result(data, mutation):
    r, completion, native, cells = copy.deepcopy(
        (data["registration"], data["completion"], data["native"], data["cells"])
    )
    if mutation == "chronology":
        completion["finished_utc"] = r["registered_utc"]
    elif mutation == "duration":
        completion["elapsed_seconds"] = 1000
    elif mutation == "scope":
        completion["coupled_cell_qualified"] = True
    elif mutation == "temperature":
        r["protocol"]["fixture_temperature_K"] = 310.15
    else:
        native["initial_open_fraction_origin"] = "native_P_before_first_update"
    with pytest.raises(ValueError):
        audit.runtime_and_receipts(audit.CAPTURE, r, completion, native, cells)


def test_audit_will_not_write_inside_original_packet(tmp_path):
    with pytest.raises(ValueError, match="fresh"):
        audit.run(audit.CAPTURE / "do-not-create", tmp_path / "unused.xml")
    assert not (audit.CAPTURE / "do-not-create").exists()
