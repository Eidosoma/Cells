"""Analytic, source-witness and corruption checks before a detached trajectory panel."""

import copy
import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


ref = module("junction_reference_test", "reference.py")
check = module("junction_checker_test", "check.py")
bridge = module("junction_bridge_test", "cells_bridge.py")


@pytest.fixture
def witness():
    folder = os.environ.get("CELLS_JUNCTION_TRAJECTORY_PREFLIGHT")
    if not folder:
        pytest.skip("An immutable four-step native development witness is required")
    root = Path(folder)
    protocol = json.loads((root / "protocol.json").read_text())
    p = root / "native/network_mixed/step-0/observed"
    row = json.loads((p / "result.json").read_text())
    prepared = json.loads((p / "preparation.json").read_text())
    with np.load(p / "trace.npz", allow_pickle=False) as archive:
        trace = dict(archive)
    assert check.u.sha(p / "trace.npz") == row["trace_sha256"]
    assert check.u.sha(p / "preparation.json") == row["preparation_sha256"]
    return ref.bind(prepared, row, trace, protocol), row, trace, protocol


def salt_pair():
    return {
        "initial_amount_fmol": np.array([[20.0, 20.0], [20.0, 20.0]]),
        "volume_pL": np.array([1.0, 2.0]),
        "initial_voltage_V": np.zeros(2),
        "capacitance_F": np.full(2, 1e-11),
        "valence": np.array([1, -1]),
        "edge_area_m2": np.array([1e-9]),
        "permeability_m_s": np.full((2, 1), 1e-8),
        "opening": np.ones(1),
        "senders": np.array([0]),
        "receivers": np.array([1]),
        "incidence": np.array([[-1.0], [1.0]]),
        "temperature_K": 298.15,
        "F": 96485.33212331001,
        "R": 8.31446261815324,
    }


@pytest.mark.parametrize("method", ["DOP853", "Radau"])
def test_independent_salt_relaxation_matches_analytic_unequal_volumes(method):
    c = salt_pair()
    protocol = {"duration_s": 2.0, "reference": {"rtol": 1e-11, "atol": 1e-13, "max_step_s": 0.05}}
    answer = ref.integrate(c, protocol, method)
    times = np.linspace(0, 2, 41)
    delta, transferred, energy = ref.unpack(c, answer.sol(times).T)
    difference = 10 * np.exp(-0.01 * 1.5 * times)
    ca = (40 + 2 * difference) / 3
    cb = (40 - difference) / 3
    expected = np.stack((ca - 20, 2 * cb - 20), axis=-1)
    np.testing.assert_allclose(delta[:, 0], expected, rtol=0, atol=3e-11)
    np.testing.assert_array_equal(delta[:, 0], delta[:, 1])
    np.testing.assert_array_equal(ref.voltage(c, delta), 0)
    checks = ref.accounting(c, delta, transferred, energy)
    assert checks["material_fmol"] < 1e-13
    assert checks["energy_pJ"] < 1e-11


def test_reference_boltzmann_equilibrium_and_current_direction():
    c = salt_pair()
    v = np.array([-0.02, 0.02])
    concentration = 20 * np.exp(-c["valence"][:, None] * c["F"] * v / (c["R"] * c["temperature_K"]))
    flux, power = ref.edge_rates(c, concentration, v)
    np.testing.assert_allclose(flux, 0, rtol=0, atol=1e-14)
    np.testing.assert_allclose(power, 0, rtol=0, atol=1e-14)
    forward, dissipation = ref.edge_rates(c, np.full((2, 2), 20.0), v)
    backward, _ = ref.edge_rates(c, np.full((2, 2), 20.0), -v)
    np.testing.assert_allclose(forward, -backward, rtol=1e-13, atol=1e-14)
    assert np.dot(c["valence"], forward[:, 0]) < 0
    assert np.min(dissipation) > 0


def test_native_saved_steps_account_conservatively(witness):
    c, row, trace, protocol = witness
    times, values, checks = check.native_values(c, row, trace, protocol)
    assert times[-1] == protocol["duration_s"]
    assert checks["material_fmol"] < protocol["tolerances"]["material_fmol"]
    assert checks["local_transfer_fmol"] < protocol["tolerances"]["local_transfer_fmol"]
    assert checks["energy_pJ"] > protocol["tolerances"]["native_energy_pJ"]
    with pytest.raises(ValueError, match="energy balance"):
        check.check_accounting(checks, protocol["tolerances"], "native_energy_pJ")
    assert np.any(values[-1] != 0)


@pytest.mark.parametrize(
    "corruption", ["labels", "ion_order", "lag", "direction", "outside", "charge", "state", "gate"]
)
def test_native_checker_rejects_corrupted_physical_evidence(witness, corruption):
    c, row, trace, protocol = witness
    trace = copy.deepcopy(trace)
    if corruption == "labels":
        trace["native_labels_s"] = (np.arange(row["steps"]) + 1) * row["dt_s"]
    elif corruption == "ion_order":
        trace["species_order"][-1] = trace["species_order"][-1][::-1]
    elif corruption == "lag":
        trace["before_cc_at_mem"][-1] = trace["before_cc_cells"][-1][:, c["owners"]]
    elif corruption == "direction":
        trace["transport_fluxes_gj"][0, 0, c["faces"][0, 0]] *= -1
    elif corruption == "outside":
        trace["after_cc_env"][-1, 0, 0] += 0.001
    elif corruption == "charge":
        trace["after_vm_ave"][-1, 0] += 0.001
    elif corruption == "state":
        trace["after_cc_cells"][-1, 0, 0] += 0.001
    elif corruption == "gate":
        trace["transport_gjopen"][0, c["faces"][0, 0]] = 0.5
    with pytest.raises((AssertionError, ValueError)):
        check.native_values(c, row, trace, protocol)


def saved_panel_row(case, index):
    folder = os.environ.get("CELLS_JUNCTION_TRAJECTORY_COMPLETED_NATIVE")
    if not folder:
        pytest.skip("A complete saved native trajectory panel is required")
    root = Path(folder)
    protocol = check.u.read(root / "protocol.json")
    path = root / "native" / case / f"step-{index}" / "observed"
    row = check.u.read(path / "result.json")
    assert check.u.sha(path / "trace.npz") == row["trace_sha256"]
    assert check.u.sha(path / "preparation.json") == row["preparation_sha256"]
    with np.load(path / "trace.npz", allow_pickle=False) as archive:
        trace = dict(archive)
    c = ref.bind(check.u.read(path / "preparation.json"), row, trace, protocol)
    return c, row, trace, protocol


@pytest.mark.parametrize("case", [c["id"] for c in check.u.read(HERE / "protocol.json")["cases"]])
@pytest.mark.parametrize("index", [0, 1, 2])
def test_saved_native_voltage_boundaries_replay_exact_source_operations(case, index):
    _, _, trace, protocol = saved_panel_row(case, index)
    check.check_native_voltage_boundaries(trace, len(protocol["species"]))


@pytest.mark.parametrize("index", [0, 1, 2])
def test_equal_voltage_native_capture_passes_full_step_checks(index, tmp_path):
    c, row, trace, protocol = saved_panel_row("network_equal", index)
    # The original exact-unmodified-voltage assertion really fails on this
    # source witness, while replaying native operations succeeds exactly.
    assert not np.array_equal(trace["before_vm"][0], trace["initial_vm"])
    times, _, accounting = check.native_values(c, row, trace, protocol)
    assert times[-1] == protocol["duration_s"]
    check.u.write(tmp_path / "accounting.json", accounting)


@pytest.mark.parametrize(
    "field", ["before_vm", "transport_vm", "before_vm_ave", "transport_vm_ave"]
)
def test_voltage_boundary_rejects_a_single_ulp_corruption(field):
    _, _, trace, protocol = saved_panel_row("network_equal", 0)
    trace[field][0, 0] = np.nextafter(trace[field][0, 0], np.inf)
    with pytest.raises(AssertionError):
        check.check_native_voltage_boundaries(trace, len(protocol["species"]))


@pytest.mark.parametrize("additions", [0, 2])
def test_voltage_boundary_rejects_missing_or_duplicate_native_offset(additions):
    _, _, trace, protocol = saved_panel_row("network_equal", 0)
    altered = trace["initial_vm"].copy()
    for _ in range(additions):
        altered += 1e-25
    trace["before_vm"][0] = altered
    with pytest.raises(AssertionError):
        check.check_native_voltage_boundaries(trace, len(protocol["species"]))


def test_cells_mapping_uses_complete_production_conservation_and_gate_independent_flux(witness):
    from cells.core.schedule import PhysicalIonicGraphControl, control_values
    from cells.core.specs import parse_spec
    from cells.models import kinetic_finite_extracellular as ionic

    c, _, _, protocol = witness
    spec = parse_spec(bridge.definition(c, protocol, protocol["cells_steps_s"][0]))
    y, layout = ionic.initial_values(spec)
    control = PhysicalIonicGraphControl(*(v[0] for v in control_values(spec, [0.0])))
    result = ionic.rhs(y, control, layout, layout.active, xp=np)
    compact = np.concatenate(
        (
            result.amount_increment.ravel(),
            result.junction_transferred.ravel(),
            result.junction_dissipated_energy_pJ,
        )
    )
    np.testing.assert_allclose(compact, ref.rhs(c, np.zeros(len(compact))), rtol=2e-12, atol=2e-12)
    for value in (0.0, 1.0):
        altered = y._replace(junction_gate=np.full_like(y.junction_gate, value))
        flux = ionic.junction_readouts(altered, control.junction, layout, xp=np).flux_fmol_per_s
        np.testing.assert_array_equal(flux, result.junction_transferred)
    assert ionic.check_values(y, spec)["max_energy_balance_error_pJ"] == 0


def test_unrefined_native_errors_cannot_pass():
    protocol = json.loads((HERE / "protocol.json").read_text())
    with pytest.raises(ValueError, match="refinement"):
        check.refinement([{"voltage_V": 1e-5}, {"voltage_V": 1e-5}], protocol, "native_")


def test_production_trajectory_disk_restart_and_independent_ode(witness, tmp_path):
    c, _, _, _ = witness
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = ref.integrate(c, protocol, "DOP853")
    times, values, report = bridge.run(
        c, protocol, protocol["cells_steps_s"][0], tmp_path / "cells", check.u.write
    )
    errors = ref.difference(c, values, result.sol(times).T)
    check.u.write(tmp_path / "accuracy.json", errors)
    check.check_errors(errors, protocol["tolerances"], "cells_")
    assert report["restart_exact"] and report["restart_loaded_from_disk"]
