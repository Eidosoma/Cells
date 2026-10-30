"""Source-exact Na/K join plus inherited-budget actual-parent local checks."""

import copy
import json
import os
import platform
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_normal_current as current
from cells.processes import betse_normal_gated_join as gated
from cells.processes import betse_normal_ion_join as join
from cells.processes import betse_normal_pump_join as pump
from cells.processes import betse_normal_voltage as voltage
from tests.unit.test_betse_fast_solver import archive_read
from tests.unit.test_betse_normal_gated_join import exact_gate
from tests.unit.test_betse_normal_ion_join import FLOORS as MATERIAL_FLOORS
from tests.unit.test_betse_normal_ion_join import exact
from validation.betse import betse_normal_pump_join_fixtures as fixtures
from validation.betse import betse_normal_pump_join_native as native


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "normal-pump-join"


def archive(tmp_path, name, payload):
    return native.write_archive(root(tmp_path) / name, join.data(payload))


def isolated(tmp_path, name, inputs):
    folder = root(tmp_path) / ("isolated-" + name)
    folder.mkdir(parents=True, exist_ok=False)
    path = folder / "inputs.json"
    path.write_text(json.dumps(inputs, indent=2, allow_nan=False) + "\n")
    command = [
        sys.executable,
        "-B",
        "-m",
        "validation.betse.betse_normal_pump_join_native",
        "--inputs",
        str(path),
        "--output",
        str(folder / "native"),
    ]
    with (folder / "native.stdout.log").open("x") as stream:
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180)
    captured = archive_read(folder / "native")
    assert captured["production_imports_denied"] and not captured["loaded_production_modules"]
    assert captured["RNG_unchanged"]
    if cpu := os.environ.get("CELLS_PUMP_JOIN_CPU"):
        assert captured["runtime"]["measured_cpu_affinity"] == [int(cpu)]
    return folder, captured


def independent(folder, mode="carried"):
    answers = []
    for level in (1, 2):
        path = folder / ("reference-" + str(level) + ".json")
        command = [
            sys.executable,
            "-B",
            "-m",
            "validation.betse.betse_normal_pump_join_reference",
            "--inputs",
            str(folder / "inputs.json"),
            "--output",
            str(path),
            "--mode",
            mode,
            "--refinement",
            str(level),
        ]
        with (folder / ("reference-" + str(level) + ".stdout.log")).open("x") as stream:
            subprocess.run(
                command, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180
            )
        answer = json.loads(path.read_text())
        assert answer["production_imports_denied"] and not answer["loaded_production_modules"]
        if cpu := os.environ.get("CELLS_PUMP_JOIN_CPU"):
            assert answer["runtime"]["measured_cpu_affinity"] == [int(cpu)]
        answers.append(answer)
    return answers


SOURCE_ROOT = Path(__file__).resolve().parents[2]
PUMP_TOLERANCES = json.loads(
    (SOURCE_ROOT / "validation/betse/pump_loop_preflight/protocol.json").read_text()
)["tolerances"]
GATE_TOLERANCES = json.loads(
    (SOURCE_ROOT / "validation/betse/junction_gate/protocol.json").read_text()
)["tolerances"]


def plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value


def seed(case="forward", inputs=None):
    inputs = fixtures.fixture(case) if inputs is None else inputs
    ib = join.bind(inputs["ion_definition"])
    vb = voltage.bind(current.bind(inputs["current_definition"]), inputs["voltage_definition"])
    gb = gated.bind(ib, vb, inputs["gate_definition"])
    binding = pump.bind(gb, inputs["pump_definition"])
    parent = pump.initialize(
        binding,
        join.state(ib, inputs["initial"]),
        initial_gate_block=inputs["initial_gate_block"],
        initial_rate_proxy_mol_m2_s=inputs["initial_rate_proxy_mol_m2_s"],
    )
    return inputs, binding, parent


def advance(inputs, binding, parent, index=0, elapsed=None):
    forcing = inputs["drives"][index]
    return pump.advance(
        binding,
        parent,
        join.drive(binding.gated_binding.material_binding, **forcing["material"]),
        pump.packet(binding, **forcing["pump"]),
        boundary_V=forcing["boundary_V"],
        extra_charge_C_m3=forcing["extra_charge_C_m3"],
        extra_current_A_m2=forcing["extra_current_A_m2"],
        elapsed_s=inputs["elapsed_start_s"] if elapsed is None else elapsed,
    )


def one(case="forward"):
    inputs, binding, parent = seed(case)
    return inputs, binding, advance(inputs, binding, parent)


def actual_parent_inputs(inputs, parent, index, elapsed):
    local = copy.deepcopy(inputs)
    local["initial"] = plain(parent.gated.material.values._asdict())
    local["initial_rate_proxy_mol_m2_s"] = parent.rate_proxy_mol_m2_s.tolist()
    local["actual_gate_memory"] = plain(parent.gated.memory._asdict())
    local["actual_parent_identity"] = parent.identity
    local["drives"] = [copy.deepcopy(inputs["drives"][index])]
    local["elapsed_start_s"] = elapsed
    local["only_incoming_state_supplied"] = True
    return local


def metric(value, wanted, budget=None):
    a, b = np.asarray(value), np.asarray(wanted)
    error = abs(a - b)
    if not error.size:
        return dict(absolute_max_error=0.0, index_at_absolute_max=[], normalized_max_error=0.0)
    where = np.unravel_index(np.argmax(error), error.shape)
    row = dict(
        absolute_max_error=float(error[where]),
        index_at_absolute_max=[int(index) for index in where],
        model_at_absolute_max=float(a[where]),
        reference_at_absolute_max=float(b[where]),
    )
    if budget is not None:
        budget = np.broadcast_to(budget, error.shape)
        row.update(
            budget_at_absolute_max=float(budget[where]),
            minimum_budget=float(np.min(budget)),
            maximum_budget=float(np.max(budget)),
            normalized_max_error=float(np.max(error / budget)),
        )
    return row


def field_unit(group, key):
    if group == "pump":
        return "mol/(m2*s)"
    if group == "gate":
        return "V" if "voltage" in key else "1/ms" if "per_ms" in key else "dimensionless"
    if "flux" in key:
        return "mol/(m2*s)"
    if "mol_m3" in key:
        return "mol/m3 (mM)"
    if "charge_density" in key:
        return "C/m3"
    if "surface_charge" in key:
        return "C/m2"
    if "conductivity" in key:
        return "S/m"
    if "derivative" in key:
        return "V/s"
    if "field" in key:
        return "V/m"
    if "rhs" in key:
        return "V/m2"
    if "voltage" in key or "potential" in key:
        return "V"
    if "current" in key:
        return "A" if key.endswith("_A") else "A/m2"
    return "dimensionless"


def local_comparisons(binding, trial, target, less):
    """Registered inherited budgets, conditioned on this actual pre-call state."""
    ib = binding.gated_binding.material_binding
    vb = binding.gated_binding.voltage_binding
    count, membranes = len(ib.ion_ids), len(ib.membrane_ids)
    eps = np.finfo(np.float64).eps
    rows, errors, budgets = {}, {}, {}
    groups = (
        (
            "material",
            trial.material.candidate.gated.material.values,
            target["material_state"],
            target["material_gross"],
            less["material_state"],
        ),
        (
            "current",
            trial.current.values,
            target["current"]["values"],
            target["current"]["gross"],
            less["current"]["values"],
        ),
        (
            "voltage",
            trial.voltage.values,
            target["voltage"]["values"],
            target["voltage"]["gross"],
            less["voltage"]["values"],
        ),
    )
    for group, values, expected, gross, less_values in groups:
        for key, value in values._asdict().items():
            factor = (
                128 * eps * (count + membranes + 4 + 32)
                if group == "material"
                else 32 * eps * (count + membranes + 16)
                if group == "current"
                else 1024 * eps * (count + membranes + np.prod(vb.kernel.shape) + 16 + 64)
            )
            budget = factor * np.asarray(gross[key]) + (
                MATERIAL_FLOORS[key] if group == "material" else 1e-30
            )
            name = group + "/" + key
            rows[name] = metric(value, expected[key], budget) | dict(
                unit=field_unit(group, key),
                budget_source=group + " registered single-call component budget",
            )
            rows["reference/" + name] = metric(less_values[key], expected[key], budget)
            errors[name], budgets[name] = abs(value - np.asarray(expected[key])), budget
    for key, expected in target["pump"]["values"].items():
        value = getattr(trial.material.pump, key)
        budget = PUMP_TOLERANCES["density_mol_per_m2_s"] + PUMP_TOLERANCES["relative"] * abs(
            np.asarray(expected)
        )
        name = "pump/" + key
        rows[name] = metric(value, expected, budget) | dict(
            unit=field_unit("pump", key), budget_source="pump_loop_preflight density/relative"
        )
        rows["reference/" + name] = metric(less["pump"]["values"][key], expected, budget)
        errors[name], budgets[name] = abs(value - np.asarray(expected)), budget
    if target["pump"]["arithmetic"] is not None:
        for key, expected in target["pump"]["arithmetic"].items():
            value = getattr(trial.material.pump.arithmetic, key)
            if key == "zero_denominator_indices":
                np.testing.assert_array_equal(value, expected)
                continue
            name = "pump_arithmetic/" + key
            if "flux" in key or "proxy" in key:
                budget = PUMP_TOLERANCES["density_mol_per_m2_s"] + PUMP_TOLERANCES[
                    "relative"
                ] * abs(np.asarray(expected))
                rows[name] = metric(value, expected, budget) | dict(
                    unit="mol/(m2*s)", budget_source="pump_loop_preflight density/relative"
                )
                rows["reference/" + name] = metric(
                    less["pump"]["arithmetic"][key], expected, budget
                )
                errors[name], budgets[name] = abs(value - np.asarray(expected)), budget
            else:
                rows[name] = metric(value, expected) | dict(
                    unit="dimensionless source activity/coefficient", diagnostic_only=True
                )
    for slot, (event, expected, lesser) in enumerate(
        zip(
            trial.material.gated.gate_updates,
            target["gate_updates"],
            less["gate_updates"],
            strict=True,
        )
    ):
        for key, wanted in expected["values"].items():
            value = getattr(event, key)
            name = "gate/" + str(slot) + "/" + key
            if "opening" in key:
                budget = GATE_TOLERANCES["source_gate_atol"] + GATE_TOLERANCES[
                    "source_gate_rtol"
                ] * abs(np.asarray(wanted))
                rows[name] = metric(value, wanted, budget) | dict(
                    unit="dimensionless source gate",
                    budget_source="junction_gate source_gate_atol/rtol",
                )
                rows["reference/" + name] = metric(lesser["values"][key], wanted, budget)
                errors[name], budgets[name] = abs(value - np.asarray(wanted)), budget
            elif "voltage" in key:
                budget = (
                    128 * eps * (count + membranes + 4 + 32) * np.asarray(expected["gross"][key])
                    + MATERIAL_FLOORS["junction_voltage_V"]
                )
                rows[name] = metric(value, wanted, budget) | dict(
                    unit="V", budget_source="material junction_voltage local budget"
                )
                errors[name], budgets[name] = abs(value - np.asarray(wanted)), budget
            else:
                rows[name] = metric(value, wanted) | dict(unit="1/ms", diagnostic_only=True)
    return rows, errors, budgets


def exact_phase(phase, source):
    observed = source["pump_observations"]
    if phase.arithmetic is None:
        assert not observed
    else:
        for key, value in phase.arithmetic._asdict().items():
            assert value.dtype == observed[key].dtype, key
            np.testing.assert_array_equal(value, observed[key], err_msg=key)
        for key in (
            "sodium_at_mem_mM",
            "potassium_at_mem_mM",
            "sodium_bath_mM",
            "potassium_bath_mM",
            "voltage_before_nonce_V",
        ):
            np.testing.assert_array_equal(getattr(phase, key), observed[key])
        assert phase.runtime_temperature_K == observed["runtime_temperature_K"]
    for key in (
        "scaled_sodium_flux_mol_m2_s",
        "scaled_potassium_flux_mol_m2_s",
        "applied_sodium_flux_mol_m2_s",
        "applied_potassium_flux_mol_m2_s",
    ):
        np.testing.assert_array_equal(
            getattr(phase, key), observed[key] if phase.arithmetic is not None else np.zeros(9)
        )
    frames = source["history"][0]["frames"]
    assert frames[1]["stage"] == "reset_flux" and frames[2]["stage"] == "pump_accumulated"
    np.testing.assert_array_equal(
        phase.storage_before_mol_m2_s, frames[1]["values"]["membrane_flux_mol_m2_s"]
    )
    np.testing.assert_array_equal(
        phase.storage_after_mol_m2_s, frames[2]["values"]["membrane_flux_mol_m2_s"]
    )
    np.testing.assert_array_equal(phase.rate_proxy_before_mol_m2_s, source["rate_proxy_before"])
    np.testing.assert_array_equal(phase.rate_proxy_after_mol_m2_s, source["rate_proxy_after"])


@pytest.fixture(scope="module", autouse=True)
def runtime_evidence(tmp_path_factory):
    affinity = sorted(os.sched_getaffinity(0))
    if cpu := os.environ.get("CELLS_PUMP_JOIN_CPU"):
        assert affinity == [int(cpu)]
    shared = {
        "cells.core.grid",
        "cells.core.specs",
        "cells.core.runner",
        "cells.core.batch",
        "cells.ensemble.ionic",
        "cells.core.surface_cotransport_water_spec",
        "cells.models.surface_energy",
        "cells.models.surface_energy_water",
    }
    assert not shared.intersection(sys.modules)
    folder = root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "runtime.json").write_text(
        json.dumps(
            dict(
                python=platform.python_version(),
                numpy=np.__version__,
                measured_cpu_affinity=affinity,
                source_revision=pump.SOURCE_REVISION,
                exact_native_primary=True,
                independent_acceptance="actual-parent one-call checks with inherited budgets",
                carried_decimal="diagnostic only, no propagated-trajectory-bound claim",
                maintained_metabolic_pools=True,
                met_argument_used=False,
                coordinated_shared_edit_modules_loaded=[],
                full_native_or_physical_parity=False,
                gpu=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("case", fixtures.CASES)
def test_native_full_sequence_and_actual_parent_conditional_local_checks(tmp_path, case):
    inputs, binding, parent = seed(case)
    original = join.digest(inputs)
    folder, captured = isolated(tmp_path, case, inputs)
    assert captured["status"] == "source_completed" and len(captured["history"]) == 3
    carried_standard, carried_tight = independent(folder, "carried")
    assert carried_tight["carried_profile_is_diagnostic_only"]
    nmove = len(binding.gated_binding.material_binding.kernel.moving)
    assert nmove == fixtures.CASE_MOVING_COUNTS[case]
    elapsed = inputs["elapsed_start_s"]
    comparisons = []
    material_frames = gate_calls = 0
    for index, source in enumerate(captured["history"]):
        before = join.digest(parent)
        local = folder / ("local-" + str(index))
        local.mkdir()
        conditioned = actual_parent_inputs(inputs, parent, index, elapsed)
        (local / "inputs.json").write_text(
            json.dumps(conditioned, indent=2, allow_nan=False) + "\n"
        )
        less, tight = independent(local, "conditional_local")
        assert tight["conditional_on_actual_parent_identity"] == parent.identity
        assert tight["mode"] == "conditional_local" and len(tight["history"]) == 1
        # Local reference inputs are written and answered before the model's
        # outgoing state is computed. No candidate/current/voltage answers enter.
        trial = advance(inputs, binding, parent, index, elapsed)
        actual_path = archive(
            tmp_path, "actual-" + case + "-" + str(index), dict(binding=binding, trial=trial)
        )
        assert trial.parent is parent and join.digest(parent) == before
        native_material = source["material"]
        exact_phase(trial.material.pump, native_material)
        for frame, native_frame in zip(
            trial.material.gated.material.frames,
            native_material["history"][0]["frames"],
            strict=True,
        ):
            assert (frame.stage, frame.ion_id) == (native_frame["stage"], native_frame["ion_id"])
            exact(frame.values, native_frame["values"])
        for event, native_event in zip(
            trial.material.gated.gate_updates, native_material["gate_updates"], strict=True
        ):
            exact_gate(event, native_event)
        exact(trial.current.values, source["current"])
        exact(trial.voltage.values, source["voltage"])
        exact(trial.candidate.gated.material.values, source["final_state"])
        np.testing.assert_array_equal(
            trial.candidate.rate_proxy_mol_m2_s, native_material["rate_proxy_after"]
        )
        rows, errors, budgets = local_comparisons(
            binding, trial, tight["history"][0], less["history"][0]
        )
        error_path = archive(
            tmp_path,
            "local-errors-" + case + "-" + str(index),
            dict(absolute_error_arrays=errors, budgets=budgets),
        )
        (local / "comparison.json").write_text(
            json.dumps(
                dict(
                    context="conditional local from actual incoming parent",
                    parent_identity=parent.identity,
                    exact_native=True,
                    fields=rows,
                    absolute_error_arrays=str(error_path),
                    physical_accuracy_claim=False,
                ),
                indent=2,
            )
            + "\n"
        )
        # Full carried answers are preserved separately and do not inherit or
        # masquerade as fixed local acceptance budgets.
        carried_rows = {}
        for group, values, expected in (
            (
                "material",
                trial.material.candidate.gated.material.values,
                carried_tight["history"][index]["material_state"],
            ),
            ("current", trial.current.values, carried_tight["history"][index]["current"]["values"]),
            ("voltage", trial.voltage.values, carried_tight["history"][index]["voltage"]["values"]),
        ):
            for key, value in values._asdict().items():
                carried_rows[group + "/" + key] = metric(value, expected[key]) | dict(
                    unit=field_unit(group, key), diagnostic_only=True
                )
        (local / "carried-diagnostic.json").write_text(
            json.dumps(
                dict(
                    fields=carried_rows,
                    no_trajectory_error_bound=True,
                    two_precision_answers_preserved=True,
                    standard_precision=carried_standard["decimal_precision"],
                ),
                indent=2,
            )
            + "\n"
        )
        normalized = max(
            row["normalized_max_error"] for row in rows.values() if "normalized_max_error" in row
        )
        resolution = max(
            row["normalized_max_error"]
            for name, row in rows.items()
            if name.startswith("reference/")
        )
        comparisons.append(
            dict(
                call_index=index + 1,
                maximum_local_error_fraction=normalized,
                reference_resolution_fraction=resolution,
                raw_actual=str(actual_path),
                conditional_comparison=str(local / "comparison.json"),
            )
        )
        material_frames += len(trial.material.gated.material.frames)
        gate_calls += len(trial.material.gated.gate_updates)
        parent = trial.candidate
        elapsed = trial.clock["elapsed_end_s"]
    maximum = max(row["maximum_local_error_fraction"] for row in comparisons)
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                completed=True,
                complete_calls=3,
                frames=material_frames,
                gate_calls=gate_calls,
                comparisons=comparisons,
                exact_host_native_correspondence=True,
                conditional_actual_parent_calls=3,
                fresh_conditional_reference_forms=6,
                fresh_carried_reference_forms=2,
                maximum_error_fraction=maximum,
                carried_decimal_is_diagnostic_only=True,
                physical_accuracy_or_full_native_claim=False,
            ),
            indent=2,
        )
        + "\n"
    )
    assert join.digest(inputs) == original
    assert maximum <= 1 and all(
        row["reference_resolution_fraction"] <= 0.1 for row in comparisons
    ), comparisons


def test_pump_reads_stale_membrane_and_pre_electroflux_nonce_without_committing():
    inputs = fixtures.fixture()
    inputs["initial"]["voltage_V"] = [0.0] * 9
    inputs["initial"]["membrane_mol_m3"][0] = [2.0] * 9
    _, binding, parent = seed(inputs=inputs)
    trial = advance(inputs, binding, parent)
    phase = trial.material.pump
    np.testing.assert_array_equal(phase.sodium_at_mem_mM, np.full(9, 2.0))
    np.testing.assert_array_equal(phase.voltage_before_nonce_V, np.zeros(9))
    frames = trial.material.gated.material.frames
    assert frames[2].stage == "pump_accumulated" and frames[3].stage == "membrane_flux"
    np.testing.assert_array_equal(
        frames[2].values.cell_mol_m3, parent.gated.material.values.cell_mol_m3
    )
    np.testing.assert_array_equal(
        frames[2].values.membrane_mol_m3, parent.gated.material.values.membrane_mol_m3
    )
    np.testing.assert_array_equal(frames[3].values.voltage_V, np.full(9, 1e-25))


def test_raw_stoichiometry_and_cached_rate_are_distinct_from_applied_flux():
    _, binding, trial = one("redistributed")
    phase = trial.material.pump
    a = phase.arithmetic
    np.testing.assert_array_equal(
        a.raw_potassium_flux_mol_m2_s, -(2 / 3) * a.raw_sodium_flux_mol_m2_s
    )
    np.testing.assert_array_equal(phase.rate_proxy_after_mol_m2_s, -a.raw_sodium_flux_mol_m2_s)
    np.testing.assert_array_equal(
        phase.scaled_sodium_flux_mol_m2_s, phase.packet.rho_pump * a.raw_sodium_flux_mol_m2_s
    )
    boundary = binding.gated_binding.material_binding.kernel.boundary
    assert np.all(phase.applied_sodium_flux_mol_m2_s[boundary] == 0)
    assert np.any(phase.rate_proxy_after_mol_m2_s[boundary] != 0)
    assert not phase.diagnostics["proxy_is_cycle_flux"]


@pytest.mark.parametrize("case", ("alpha_zero", "alpha_negative"))
def test_source_alpha_guards_clear_or_retain_diagnostic_after_flux_reset(case):
    _, _, trial = one(case)
    phase = trial.material.pump
    assert phase.arithmetic is None and not phase.diagnostics["helper_called"]
    assert np.all(phase.storage_before_mol_m2_s == 0) and np.all(phase.storage_after_mol_m2_s == 0)
    expected = np.zeros(9) if case == "alpha_zero" else trial.parent.rate_proxy_mol_m2_s
    np.testing.assert_array_equal(trial.candidate.rate_proxy_mol_m2_s, expected)


def test_pump_flux_is_added_to_cleared_storage_before_passive_membrane_flux():
    _, binding, trial = one()
    phase = trial.material.pump
    na = binding.kernel.sodium
    frames = trial.material.gated.material.frames
    np.testing.assert_array_equal(
        phase.storage_after_mol_m2_s[na], phase.applied_sodium_flux_mol_m2_s
    )
    assert np.any(frames[3].values.membrane_flux_mol_m2_s[na] != phase.storage_after_mol_m2_s[na])
    assert np.all(frames[1].values.membrane_flux_mol_m2_s == 0)


def test_open_boundary_changes_applied_pump_but_not_raw_rate_proxy():
    _, binding, closed = one()
    _, _, opened = one("open_boundary")
    np.testing.assert_array_equal(
        closed.material.pump.rate_proxy_after_mol_m2_s,
        opened.material.pump.rate_proxy_after_mol_m2_s,
    )
    mask = binding.gated_binding.material_binding.kernel.boundary
    assert np.all(closed.material.pump.applied_sodium_flux_mol_m2_s[mask] == 0)
    assert np.any(opened.material.pump.applied_sodium_flux_mol_m2_s[mask] != 0)


def test_metabolic_argument_is_ignored_but_maintained_pool_changes_rates():
    inputs, binding, ignored = one("met_ignored")
    changed = copy.deepcopy(inputs)
    changed["drives"][0]["pump"]["met_concs"] = None
    no_argument = advance(changed, binding, ignored.parent)
    exact(
        ignored.candidate.gated.material.values,
        no_argument.candidate.gated.material.values._asdict(),
    )
    assert (
        ignored.identity != no_argument.identity
        and not ignored.material.pump.diagnostics["metabolic_argument_used"]
    )
    changed["pump_definition"]["maintained"]["cATP"] = 0.03
    _, other, parent = seed(inputs=changed)
    lower = advance(changed, other, parent)
    assert np.any(
        lower.material.pump.arithmetic.raw_sodium_flux_mol_m2_s
        != ignored.material.pump.arithmetic.raw_sodium_flux_mol_m2_s
    )
    assert binding.definition["maintained"]["cATP"] == 1.5
    assert not ignored.clock["endogenous_metabolic_consumption"]


def test_exact_zero_denominator_substitution_does_not_floor_concentrations():
    _, _, trial = one("zero_na_membrane")
    phase = trial.material.pump
    a = phase.arithmetic
    np.testing.assert_array_equal(a.zero_denominator_indices, np.arange(9))
    np.testing.assert_array_equal(a.quotient_denominator_raw, np.zeros(9))
    np.testing.assert_array_equal(a.quotient_denominator_used, np.full(9, 1e-15))
    np.testing.assert_array_equal(phase.sodium_at_mem_mM, np.zeros(9))
    np.testing.assert_array_equal(a.raw_sodium_flux_mol_m2_s, np.zeros(9))


def test_stationary_pump_role_stores_flux_without_bulk_or_bath_commit():
    _, binding, trial = one("na_stationary")
    na = binding.kernel.sodium
    assert np.any(trial.material.pump.applied_sodium_flux_mol_m2_s != 0)
    np.testing.assert_array_equal(
        trial.candidate.gated.material.values.cell_mol_m3[na],
        trial.parent.gated.material.values.cell_mol_m3[na],
    )
    assert (
        trial.candidate.gated.material.values.bath_mol_m3[na]
        == trial.parent.gated.material.values.bath_mol_m3[na]
    )
    np.testing.assert_array_equal(
        trial.current.source.membrane_flux_mol_m2_s[na],
        trial.material.pump.applied_sodium_flux_mol_m2_s,
    )


def test_named_roles_follow_reordered_ion_axes():
    _, binding, trial = one("reordered_roles")
    assert binding.kernel.sodium == 3 and binding.kernel.potassium == 2
    np.testing.assert_array_equal(
        trial.material.pump.sodium_at_mem_mM, trial.parent.gated.material.values.membrane_mol_m3[3]
    )
    assert binding.gated_binding.material_binding.ion_ids == ("P", "Cl", "K", "Na")


def test_pump_uses_live_temperature_while_gap_sigma_keep_configured_temperature():
    inputs, binding, first = one("temperature_split")
    assert first.material.pump.runtime_temperature_K == 281.0
    assert binding.gated_binding.voltage_binding.kernel.configured_temperature_K == 315.0
    changed = copy.deepcopy(inputs)
    changed["drives"][0]["material"]["runtime_temperature_K"] = 330.0
    hotter = advance(changed, binding, first.parent)
    assert np.any(
        first.material.pump.arithmetic.equilibrium != hotter.material.pump.arithmetic.equilibrium
    )
    np.testing.assert_array_equal(
        first.material.pump.arithmetic.saturation, hotter.material.pump.arithmetic.saturation
    )
    for a, b in zip(
        first.material.gated.gate_updates, hotter.material.gated.gate_updates, strict=True
    ):
        np.testing.assert_array_equal(a.alpha_per_ms, b.alpha_per_ms)


def test_reverse_pump_retains_signed_raw_flux_and_negative_proxy():
    _, _, trial = one("reverse")
    a = trial.material.pump.arithmetic
    assert np.all(a.raw_sodium_flux_mol_m2_s > 0) and np.all(a.raw_potassium_flux_mol_m2_s < 0)
    assert np.all(trial.candidate.rate_proxy_mol_m2_s < 0)


def test_parent_preservation_repeatability_and_immutable_pump_controls():
    inputs, binding, trial = one("met_ignored")
    before = join.digest(trial.parent)
    again = advance(inputs, binding, trial.parent)
    assert trial.identity == again.identity and join.digest(trial.parent) == before
    values = (
        *trial.material.pump.arithmetic,
        trial.candidate.rate_proxy_mol_m2_s,
        trial.material.pump.packet.block,
        *trial.material.pump.packet.met_concs.values(),
    )
    for value in values:
        assert not value.flags.writeable
        with pytest.raises(ValueError):
            value.setflags(write=True)


@pytest.mark.parametrize(
    "defect", ("role", "km", "proxy_shape", "proxy_dtype", "proxy_mutable", "packet_mutable")
)
def test_invalid_source_roles_parameters_or_cache_refuse_without_pump_work(defect, monkeypatch):
    inputs, binding, parent = seed()
    if defect in ("role", "km"):
        raw = copy.deepcopy(inputs["pump_definition"])
        if defect == "role":
            raw["sodium_id"] = "Cl"
        else:
            raw["kinetics"]["KmNK_Na"] = 0.0
        with pytest.raises(ValueError):
            pump.bind(binding.gated_binding, raw)
        return
    live = pump.packet(binding, **inputs["drives"][0]["pump"])
    if defect == "proxy_shape":
        parent = replace(parent, rate_proxy_mol_m2_s=join.freeze(parent.rate_proxy_mol_m2_s[:1]))
    elif defect == "proxy_dtype":
        parent = replace(
            parent, rate_proxy_mol_m2_s=join.freeze(parent.rate_proxy_mol_m2_s.astype(np.float32))
        )
    elif defect == "proxy_mutable":
        parent = replace(parent, rate_proxy_mol_m2_s=parent.rate_proxy_mol_m2_s.copy())
    else:
        live = live._replace(block=live.block.copy())
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Invalid cache reached pump")

    monkeypatch.setattr(pump, "_active_material_step", forbidden)
    forcing = inputs["drives"][0]
    with pytest.raises(pump.PumpJoinRejected):
        pump.advance(
            binding,
            parent,
            join.drive(binding.gated_binding.material_binding, **forcing["material"]),
            live,
            boundary_V=forcing["boundary_V"],
            extra_charge_C_m3=forcing["extra_charge_C_m3"],
            extra_current_A_m2=forcing["extra_current_A_m2"],
            elapsed_s=inputs["elapsed_start_s"],
        )
    assert not calls


@pytest.mark.parametrize(
    "mode", ("singular_saturation", "masked_proxy_nonfinite", "equilibrium_overflow")
)
def test_actual_nonfinite_pump_and_partial_join_trials_remain_lossless(tmp_path, mode):
    inputs = fixtures.fixture()
    inputs["drives"] = inputs["drives"][:1]
    if mode == "singular_saturation":
        inputs["initial"]["membrane_mol_m3"][0] = [-12.0] * 9
    elif mode == "masked_proxy_nonfinite":
        inputs["pump_definition"]["kinetics"]["deltaGATP"] = 1e9
        inputs["ion_definition"]["geometry"]["boundary"] = [True] * 9
    else:
        inputs["pump_definition"]["kinetics"]["deltaGATP"] = -1e9
    _, actual = isolated(tmp_path, mode, inputs)
    _, binding, parent = seed(inputs=inputs)
    before = join.digest(parent)
    with pytest.raises(pump.PumpJoinRejected) as caught:
        advance(inputs, binding, parent)
    error = caught.value
    assert error.parent is parent and join.digest(parent) == before and error.material is not None
    assert not error.material.pump.diagnostics["finite"]
    source = actual["history"][0]["material"]
    exact_phase(error.material.pump, source)
    exact(error.material.gated.candidate.material.values, source["final_state"])
    if mode == "singular_saturation":
        assert actual["status"] == "source_refused"
    else:
        assert actual["status"] == "source_completed"
    saved = archive(tmp_path, "actual-" + mode, error.material)
    assert join.digest(archive_read(saved)) == join.digest(error.material)
