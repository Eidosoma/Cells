"""Prepared native feedback checks; chemistry execution is explicitly excluded."""

import copy
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_network_modulation as component
from cells.processes import betse_normal_current as current
from cells.processes import betse_normal_gated_join as gated
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_network_join as joined
from cells.processes import betse_normal_pump_join as pump
from cells.processes import betse_normal_voltage as voltage
from tests.unit import test_betse_normal_calcium_join as calcium_checks
from tests.unit import test_betse_normal_channel_join as old
from tests.unit.test_betse_fast_solver import archive_read
from tests.unit.test_betse_normal_ion_join import exact
from validation.betse import betse_normal_calcium_join_fixtures as calcium_fixtures
from validation.betse import betse_normal_network_join_fixtures as fixtures
from validation.betse import betse_normal_network_join_native as native
from validation.betse.betse_normal_channel_join_runtime import inventory as runtime_inventory

TOLERANCES = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "validation/regulation/betse_network_modulation_protocol.json"
    ).read_text()
)["tolerances"]


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "normal-network-join"


def archive(tmp_path, name, payload):
    return native.write_archive(root(tmp_path) / name, ions.data(payload))


def archive_refusal(tmp_path, name, inputs, error):
    payload = dict(
        inputs=inputs,
        type=type(error).__name__,
        message=str(error),
        traceback=traceback.format_exc(),
    )
    for key in (
        "stage",
        "parent",
        "initialization",
        "material",
        "channel_phases",
        "network",
        "readout",
        "voltage_trial",
    ):
        payload[key] = getattr(error, key, None)
    return archive(tmp_path, "unexpected-refusal-" + name, payload)


def seed(inputs):
    ib = ions.bind(inputs["ion_definition"])
    vb = voltage.bind(current.bind(inputs["current_definition"]), inputs["voltage_definition"])
    gb = gated.bind(ib, vb, inputs["gate_definition"])
    pb = pump.bind(gb, inputs["pump_definition"])
    binding = joined.bind(pb, inputs["channel_definition"])
    parent = joined.initialize_values(
        binding,
        inputs["initial"],
        initial_gate_block=inputs["initial_gate_block"],
        initial_NaK_rate=inputs["initial_rate_proxy_mol_m2_s"],
        initial_CaATP_rate=inputs["initial_calcium_rate_proxy_mol_m2_s"],
    )
    return binding, parent


def advance(inputs, binding, parent, index, elapsed, observer=None):
    drive = inputs["drives"][index]
    scheduled = drive["scheduled_controls"]
    effective = parent.network_controls if scheduled is None else scheduled
    material = dict(drive["material"], junction_block=effective["gj_block"])
    live_pump = dict(drive["pump"], block=effective["NaKATP_block"])
    return joined.advance(
        binding,
        parent,
        ions.drive(binding.pump_binding.gated_binding.material_binding, **material),
        pump.packet(binding.pump_binding, **live_pump),
        joined.packet(binding, **drive["channels"]),
        joined.calcium_packet(binding, **drive["calcium"]),
        before_network=observer,
        scheduled_controls=scheduled,
        boundary_V=drive["boundary_V"],
        extra_charge_C_m3=drive["extra_charge_C_m3"],
        extra_current_A_m2=drive["extra_current_A_m2"],
        elapsed_s=elapsed,
    )


def isolated(tmp_path, name, inputs):
    folder = root(tmp_path) / ("isolated-" + name)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(json.dumps(inputs, indent=2, allow_nan=False) + "\n")
    command = [
        sys.executable,
        "-B",
        "-m",
        "validation.betse.betse_normal_network_join_native",
        "--inputs",
        str(folder / "inputs.json"),
        "--output",
        str(folder / "native"),
    ]
    with (folder / "native.stdout.log").open("x") as stream:
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180)
    result = archive_read(folder / "native")
    assert result["production_imports_denied"] and not result["loaded_production_modules"]
    assert result["RNG_unchanged"]
    return folder, result


def references(folder, before):
    (folder / "inputs.json").write_text(
        json.dumps(old.plain(ions.data(before)), indent=2, allow_nan=False) + "\n"
    )
    result = []
    for level in (1, 2):
        path = folder / ("reference-" + str(level) + ".json")
        command = [
            sys.executable,
            "-B",
            "-m",
            "validation.betse.betse_normal_network_join_reference",
            "--inputs",
            str(folder / "inputs.json"),
            "--output",
            str(path),
            "--refinement",
            str(level),
        ]
        with (folder / ("reference-" + str(level) + ".stdout.log")).open("x") as stream:
            subprocess.run(
                command, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180
            )
        answer = json.loads(path.read_text())
        assert answer["production_imports_denied"] and not answer["loaded_production_modules"]
        result.append(answer)
    return result


def standalone(before):
    values, definition = before["values_before"], before["definition"]
    m = len(values["voltage_V"])
    topology, parameters = component.bind(
        ions.data(definition["modulators"]),
        [],
        before["ion_ids"],
        before["valence"],
        definition["membrane_to_environment"],
        m,
        before["ion_ids"],
        tj_targets=[False] * m,
        faraday_C_mol=before["F"],
        gas_constant_J_mol_K=before["R"],
        temperature_K=before["runtime_temperature_K"],
    )
    samples = np.concatenate((values["membrane_mol_m3"], values["bath_mol_m3"]), axis=-1)
    controls = component.Controls(
        before["controls_before"]["gj_block"],
        before["controls_before"]["NaKATP_block"],
        np.zeros((len(before["ion_ids"]), m)),
        np.zeros((len(definition["modulators"]), m)),
    )
    assert component.domain_valid(
        samples, values["voltage_V"], controls, topology, parameters, xp=np
    )
    factors = component.evaluate(samples, values["voltage_V"], topology, parameters, xp=np)
    after = component.apply(factors.value, controls, topology, xp=np)
    return dict(controls_after=dict(gj_block=after.gj, NaKATP_block=after.nak), factors=factors)


def compare_channel_routes(trial, captured):
    phases = captured["channel_capture"]["events"]
    for actual, expected in zip(trial.material.channel_phases, phases, strict=True):
        for key in ("channel_id", "class_name", "skipped", "call_index", "dt_s", "native_dt"):
            assert getattr(actual, key) == expected[key], key
        for key in ("cache_before", "cache_after"):
            old.exact_cache(getattr(actual, key), expected[key])
        for key in ("values_before", "values_after"):
            exact(getattr(actual, key), expected[key])
        for route, wanted in zip(actual.routes, expected["routes"], strict=True):
            assert (
                route.ion_id == wanted["ion_id"]
                and route.relative_permeability == wanted["relative_permeability"]
            )
            for key in ("values_before", "values_after"):
                exact(getattr(route, key), wanted[key])
            old.exact_cache(route.cache_after, wanted["cache_after"])
            for key in (
                "sampled_bulk_mM",
                "sampled_membrane_mM",
                "sampled_bath_mM",
                "diffusion_m2_s",
                "flux_mol_m2_s",
                "network_current_before_A_m2",
                "network_current_after_A_m2",
            ):
                assert getattr(route, key).dtype == wanted[key].dtype, key
                np.testing.assert_array_equal(getattr(route, key), wanted[key], err_msg=key)


def compare_feedback(actual, source):
    for key in ("values_before", "values_after"):
        exact(ions.Values(**actual[key]), source[key])
    for key in ("controls_before", "controls_after"):
        old.exact_cache(actual[key], source[key])
    if actual["cache_before"] is None:
        assert source["cache_before"] is None
    else:
        old.exact_cache(actual["cache_before"], source["cache_before"])
    old.exact_cache(actual["cache_after"], source["cache_after"])
    for row, wanted in zip(actual["control_writes"], source["control_writes"], strict=True):
        assert row["rule_id"] == wanted["rule_id"] and row["target"] == wanted["target"]
        for key in ("value", "gj_block", "NaKATP_block"):
            assert row[key].dtype == wanted[key].dtype
            np.testing.assert_array_equal(row[key], wanted[key])
    assert actual["source_completed"] and source["source_completed"]
    assert not actual["executed_chemistry"] and not source["executed_chemistry"]


def local_comparisons(trial, lower, target, reused):
    rows, errors, budgets = {}, {}, {}
    for key, actual in trial.material.network_feedback["controls_after"].items():
        wanted = np.asarray(target["controls_after"][key])
        budget = TOLERANCES["factor_atol"] + TOLERANCES["relative"] * abs(wanted)
        rows[key] = old.metric(actual, wanted, budget) | dict(unit="dimensionless")
        rows["reference/" + key] = old.metric(lower["controls_after"][key], wanted, budget)
        rows["standalone/" + key] = old.metric(reused["controls_after"][key], wanted, budget)
        errors[key], budgets[key] = abs(actual - wanted), budget
    for index, (actual, wanted, less) in enumerate(
        zip(
            trial.material.network_feedback["control_writes"],
            target["control_writes"],
            lower["control_writes"],
            strict=True,
        )
    ):
        for key in ("value", "gj_block", "NaKATP_block"):
            name = "write/" + str(index) + "/" + key
            value = np.asarray(wanted[key])
            budget = TOLERANCES["factor_atol"] + TOLERANCES["relative"] * abs(value)
            rows[name] = old.metric(actual[key], value, budget) | dict(unit="dimensionless")
            rows["reference/" + name] = old.metric(less[key], value, budget)
            errors[name], budgets[name] = abs(actual[key] - value), budget
    return rows, errors, budgets


@pytest.mark.parametrize("case", fixtures.CASES)
def test_native_endogenous_feedback_and_pre_network_reference(tmp_path, case):
    inputs = fixtures.fixture(case)
    preparation = root(tmp_path) / ("preparation-" + case)
    preparation.mkdir(parents=True, exist_ok=False)
    (preparation / "inputs-before-constructor.json").write_text(
        json.dumps(inputs, indent=2, allow_nan=False) + "\n"
    )
    try:
        binding, parent = seed(inputs)
    except Exception as error:
        archive_refusal(tmp_path, case + "-constructor", inputs, error)
        raise
    archive(tmp_path, case + "-constructor-return", dict(binding=binding, parent=parent))
    folder, captured = isolated(tmp_path, case, inputs)
    assert captured["status"] == "source_completed" and len(captured["history"]) == 3
    elapsed = inputs["elapsed_start_s"]
    reports = []
    for index, source in enumerate(captured["history"]):
        local = folder / ("pre-network-" + str(index))
        local.mkdir()
        answers, reused = [], []

        def observer(before, local=local, index=index, answers=answers, reused=reused):
            archive(tmp_path, case + "-pre-network-" + str(index), before)
            answers.extend(references(local, before))
            reused.append(standalone(before))

        old_parent = ions.digest(parent)
        try:
            trial = advance(inputs, binding, parent, index, elapsed, observer)
        except Exception as error:
            archive_refusal(
                tmp_path, case + "-call-" + str(index), dict(inputs=inputs, parent=parent), error
            )
            raise
        archive(tmp_path, "actual-" + case + "-" + str(index), dict(binding=binding, trial=trial))
        assert ions.digest(parent) == old_parent and len(answers) == 2
        material = source["material"]
        old.exact_phase(trial.material.pump.pump, material)
        for a, b in zip(
            trial.material.pump.gated.material.frames, material["history"][0]["frames"], strict=True
        ):
            assert (a.stage, a.ion_id) == (b["stage"], b["ion_id"])
            exact(a.values, b["values"])
        calcium_checks.compare_calcium(trial.material.calcium_handler, material)
        compare_channel_routes(trial, material)
        compare_feedback(
            trial.material.network_feedback, material["channel_capture"]["network_feedback"]
        )
        for a, b in zip(
            trial.material.pump.gated.gate_updates, material["gate_updates"], strict=True
        ):
            old.exact_gate(a, b)
        for a, b in zip(trial.candidate.channel_caches, material["channel_caches"], strict=True):
            old.exact_cache(a, b)
        old.exact_cache(
            trial.candidate.network_controls,
            material["channel_capture"]["network_feedback"]["controls_after"],
        )
        old.exact_cache(
            trial.candidate.network_cache,
            material["channel_capture"]["network_feedback"]["cache_after"],
        )
        exact(trial.current.values, source["current"])
        exact(trial.voltage.values, source["voltage"])
        exact(trial.candidate.pump.gated.material.values, source["final_state"])
        np.testing.assert_array_equal(
            trial.material.network_feedback["cache_after"]["delta_conc"],
            np.zeros(len(binding.pump_binding.gated_binding.material_binding.ion_ids)),
        )
        rows, errors, budgets = local_comparisons(trial, answers[0], answers[1], reused[0])
        archive(
            tmp_path,
            "local-errors-" + case + "-" + str(index),
            dict(errors=errors, budgets=budgets),
        )
        (local / "comparison.json").write_text(
            json.dumps(
                dict(fields=rows, conditional_pre_network_only=True, executed_chemistry=False),
                indent=2,
            )
            + "\n"
        )
        assert max(row["normalized_max_error"] for row in rows.values()) <= 1
        assert (
            max(
                row["normalized_max_error"]
                for name, row in rows.items()
                if name.startswith("reference/")
            )
            <= 0.1
        )
        reports.append(rows)
        parent, elapsed = trial.candidate, trial.clock["elapsed_end_s"]
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                completed=True,
                exact_native=True,
                complete_calls=3,
                conditional_pre_network_checks=3,
                executed_chemistry=False,
                carried_reference_forms=0,
                maximum_error_fraction=max(
                    row["normalized_max_error"] for rows in reports for row in rows.values()
                ),
            ),
            indent=2,
        )
        + "\n"
    )


def test_empty_feedback_projection_to_frozen_calcium(tmp_path):
    inputs = fixtures.projection_fixture()
    binding, parent = seed(inputs)
    previous = calcium_fixtures.fixture()
    old_binding, old_parent = calcium_checks.seed(previous)
    elapsed = inputs["elapsed_start_s"]
    for index in range(3):
        trial = advance(inputs, binding, parent, index, elapsed)
        target = calcium_checks.advance(previous, old_binding, old_parent, index, elapsed)
        exact(
            trial.candidate.pump.gated.material.values,
            ions.data(target.candidate.pump.gated.material.values),
        )
        exact(trial.current.values, ions.data(target.current.values))
        exact(trial.voltage.values, ions.data(target.voltage.values))
        archive(tmp_path, "projection-" + str(index), dict(network=trial, calcium=target))
        parent, old_parent, elapsed = (
            trial.candidate,
            target.candidate,
            trial.clock["elapsed_end_s"],
        )


def test_native_empty_growth_reaction_stack_refusal(tmp_path):
    inputs = fixtures.raw_reaction_fixture()
    folder, captured = isolated(tmp_path, "raw-empty-growth-reaction-stack", inputs)
    with pytest.raises((ValueError, joined.MissingCoupledState)):
        seed(inputs)
    assert captured["status"] == "source_refused"
    material = captured["history"][0]["material"]
    feedback = material["channel_capture"]["network_feedback"]
    assert material["failure"]["type"] == "ValueError" and not feedback["source_completed"]
    assert feedback["cache_after"]["reaction_rates"].shape == (1, 3)
    assert feedback["cache_after"]["delta_conc"] is None
    (folder / "raw-retention.json").write_text(
        json.dumps(
            dict(
                native_failure=material["failure"],
                model_scope_guard_refused=True,
                positive_chemistry_credit=False,
                dimension_repair=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("dependency", ("chemistry", "map_owner", "missing_controls"))
def test_complete_feedback_dependencies(dependency):
    data = (
        fixtures.raw_reaction_fixture()
        if dependency == "chemistry"
        else copy.deepcopy(fixtures.fixture())
    )
    if dependency == "map_owner":
        mapping = data["channel_definition"]["network"]["membrane_to_environment"]
        mapping[0] = (mapping[0] + 1) % len(mapping)
    if dependency == "missing_controls":
        del data["channel_definition"]["network"]["initial_controls"]["NaKATP_block"]
    with pytest.raises((ValueError, joined.MissingCoupledState)):
        seed(data)


@pytest.fixture(scope="module", autouse=True)
def runtime_receipt(tmp_path_factory):
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
    runtime = runtime_inventory()
    if cpu := os.environ.get("CELLS_NETWORK_JOIN_CPU"):
        assert runtime["measured_cpu_affinity"] == [int(cpu)]
    folder = root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "runtime.json").write_text(json.dumps(runtime, indent=2) + "\n")
