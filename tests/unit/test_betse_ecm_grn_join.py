"""Prepared genuine ECM GRN checks; no scientific execution in preparation."""

import copy
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_ecm_grn_join as joined
from cells.processes import betse_normal_ion_join as ions
from tests.unit import test_betse_normal_grn_join as old
from tests.unit.test_betse_fast_solver import archive_read
from validation.betse import betse_ecm_grn_fixtures as fixtures
from validation.betse import betse_ecm_grn_native as native
from validation.betse.betse_normal_channel_join_runtime import inventory


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "ecm-grn"


def archive(tmp_path, name, value):
    return native.archives.write_archive(root(tmp_path) / name, ions.data(value))


def isolated(tmp_path, inputs):
    folder = root(tmp_path) / ("isolated-" + inputs["case_id"])
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    with (folder / "native.stdout.log").open("x") as stream:
        subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "validation.betse.betse_ecm_grn_native",
                "--inputs",
                str(folder / "inputs.json"),
                "--output",
                str(folder / "native"),
            ],
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=180,
        )
    result = archive_read(folder / "native")
    assert result["production_imports_denied"] and not result["loaded_production_modules"]
    assert result["RNG_unchanged"]
    return folder, result


def references(folder, inputs):
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(
        json.dumps(old.old.plain(ions.data(inputs)), indent=2, allow_nan=False) + "\n"
    )
    answers = []
    for level in (1, 2):
        path = folder / ("reference-" + str(level) + ".json")
        with (folder / ("reference-" + str(level) + ".stdout.log")).open("x") as stream:
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "validation.betse.betse_ecm_grn_reference",
                    "--inputs",
                    str(folder / "inputs.json"),
                    "--output",
                    str(path),
                    "--refinement",
                    str(level),
                ],
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=180,
            )
        row = json.loads(path.read_text())
        assert row["production_imports_denied"] and not row["loaded_production_modules"]
        assert (
            row["decimal_precision"] == (100 if level == 1 else 160)
            and row["carried_reference_forms"] == 0
        )
        answers.append(row)
    return answers


def comparisons():
    rows = {}

    def add(name, actual, target, lower, budget, unit):
        a, b = np.asarray(actual, np.float64), np.asarray(target, np.float64)
        budget = np.broadcast_to(budget, a.shape)
        rows[name] = dict(
            actual=a,
            target=b,
            lower=np.asarray(lower),
            error=abs(a - b),
            budget=budget,
            unit=unit,
            metric=old.old.metric(a, b, budget),
            resolution=old.old.metric(lower, b, budget),
        )

    return rows, add


def check(tmp_path, name, folder, rows):
    archive(tmp_path, name, dict(fields=rows, physical_conservation_credit=False))
    result = dict(
        fields={k: v["metric"] for k, v in rows.items()},
        resolutions={k: v["resolution"] for k, v in rows.items()},
        fresh_conditional_reference=True,
        physical_global_conservation_credit=False,
    )
    (folder / "comparison.json").write_text(json.dumps(result, indent=2) + "\n")
    assert rows and max(v["normalized_max_error"] for v in result["fields"].values()) <= 1
    assert max(v["normalized_max_error"] for v in result["resolutions"].values()) <= 0.1


def compare_cold(binding, parent, lower, target):
    rows, add = comparisons()
    wire = parent.network_cache["wire"]
    assert dict(wire["owner_fields"]) == target["owner_fields"]
    assert wire["core_fields"]["charge_has_been_balanced"] is target["charge_has_been_balanced"]
    for name, fields in target["molecule_fields"].items():
        for key, wanted in fields.items():
            actual = wire["molecule_fields"][name][key]
            if wanted is None or type(wanted) is bool:
                assert actual is wanted
            else:
                np.testing.assert_array_equal(actual, wanted)
                add(
                    name + "/" + key,
                    actual,
                    wanted,
                    lower["molecule_fields"][name][key],
                    3e-13,
                    "source field",
                )
    add(
        "reaction_matrix",
        wire["core_fields"]["reaction_matrix"],
        target["reaction_matrix"],
        lower["reaction_matrix"],
        1e-25,
        "stoichiometry",
    )
    for key, value in target["simulator_fields"].items():
        np.testing.assert_array_equal(wire["simulator_fields"][key], value)
        add(
            key,
            wire["simulator_fields"][key],
            value,
            lower["simulator_fields"][key],
            1e-25,
            "source publication",
        )
    g = binding.material_binding.geometry_binding.geometry
    expected = target["independent_geometry"]
    for key in ("membrane_to_grid", "cell_to_grid"):
        np.testing.assert_array_equal(getattr(g, key), expected[key])
    for key in (
        "membrane_divergence_map_m2",
        "membrane_area_per_site_m2",
        "true_environment_volume_m3",
    ):
        wanted = np.asarray(expected[key])
        add(
            "grid/" + key,
            getattr(g, key),
            wanted,
            lower["independent_geometry"][key],
            3e-13 + 6e-12 * abs(wanted),
            "declared geometry",
        )
    return rows


def compare_local(feedback, lower, target):
    before = feedback["before"]
    actual = feedback["cache_after"]["wire"]
    n, m = len(before["molecular_geometry"]["cell_volume_m3"]), len(before["gap_open"])
    e = len(before["values_before"]["environment_mol_m3"][0])
    factor = 128 * np.finfo(float).eps * (len(before["ion_ids"]) + 2 + n + m + e + 64)
    rows, add = comparisons()
    for key in ("growth_rates", "reaction_rates", "all_rates"):
        wanted = np.asarray(target["rhs"][key])
        add(
            "rhs/" + key,
            feedback["rhs"][key],
            wanted,
            lower["rhs"][key],
            2e-14 + 5e-12 * abs(wanted),
            "mM/s",
        )
    add(
        "delta",
        actual["core_fields"]["delta_conc"],
        target["delta_conc"],
        lower["delta_conc"],
        6e-14 + 5e-12 * np.asarray(target["delta_gross"]),
        "mM/s",
    )
    volumes = np.asarray(before["molecular_geometry"]["cell_volume_m3"])
    for name, wanted in target["molecules_after"].items():
        fields = actual["molecule_fields"][name]
        for key in ("c_cells", "cc_at_mem", "c_env", "f_mem", "f_gj", "fenvx", "fenvy"):
            floor = 1e-18 if key.startswith("f") else 3e-13
            budget = floor + factor * np.asarray(target["gross_molecules"][name][key])
            add(
                name + "/" + key,
                fields[key],
                wanted[key],
                lower["molecules_after"][name][key],
                budget,
                "mol/m2/s" if key.startswith("f") else "mol/m3",
            )
        book = target["balances"][name]
        previous = before["molecule_states_before"][name]
        volume = book["site_volume_m3"]
        old_amount = (
            np.sum(np.asarray(previous["c_cells"]) * volumes) + np.sum(previous["c_env"]) * volume
        )
        new_amount = np.sum(fields["c_cells"] * volumes) + np.sum(fields["c_env"]) * volume
        keys = (
            "chemical_source_mol",
            "directed_GJ_change_mol",
            "fast_exchange_defect_mol",
            "boundary_clamp_change_mol",
            "collocated_transport_change_mol",
            "smoothing_change_mol",
        )
        expected_terms = sum(book[k] for k in keys)
        gross = (
            sum(abs(book[k]) for k in keys)
            + abs(book["initial_amount_mol"])
            + abs(book["final_amount_mol"])
        )
        gross += book["native_true_volume_gross_mol"]
        budget = factor * gross + 3e-13 * (
            np.sum(volumes)
            + e * volume
            + np.sum(target["independent_geometry"]["true_environment_volume_m3"])
        )
        add(
            name + "/source_effective_amount",
            new_amount - old_amount - expected_terms,
            book["source_effective_residual_mol"],
            lower["balances"][name]["source_effective_residual_mol"],
            budget,
            "mol",
        )
        true_volume = np.asarray(target["independent_geometry"]["true_environment_volume_m3"])
        delta = np.sum((fields["c_cells"] - previous["c_cells"]) * volumes) + np.sum(
            (fields["c_env"] - previous["c_env"]) * true_volume
        )
        add(
            name + "/native_true_volume_change",
            delta,
            book["native_true_volume_total_change_mol"],
            lower["balances"][name]["native_true_volume_total_change_mol"],
            budget,
            "mol; no physical conservation credit",
        )
    for key, gross_key, unit in (
        ("extra_rho_cells", "extra_rho_gross", "C/m3"),
        ("extra_rho_env", "extra_rho_env_gross", "C/m3"),
        ("extra_J_mem", "extra_J_gross", "A/m2"),
        ("extra_Jenv_x", "extra_Jenv_x_gross", "A/m2"),
        ("extra_Jenv_y", "extra_Jenv_y_gross", "A/m2"),
    ):
        add(
            key,
            actual["core_fields"][key],
            target[key],
            lower[key],
            (1e-25 if "rho" in key else 1e-30) + factor * np.asarray(target[gross_key]),
            unit,
        )
        if before["substances_affect_charge"]:
            np.testing.assert_array_equal(
                actual["simulator_fields"][key], actual["core_fields"][key]
            )
        else:
            np.testing.assert_array_equal(
                actual["simulator_fields"][key], before["simulator_fields_before"][key]
            )
    for key in ("gj_block", "NaKATP_block"):
        add(
            "control/" + key,
            feedback["controls_after"][key],
            target["controls_after"][key],
            lower["controls_after"][key],
            3e-14 + 5e-12 * abs(np.asarray(target["controls_after"][key])),
            "factor",
        )
    np.testing.assert_array_equal(feedback["values_after"]["voltage_V"], target["voltage_after_V"])
    np.testing.assert_array_equal(
        feedback["values_after"]["junction_voltage_V"], target["junction_voltage_after_V"]
    )
    return rows


@pytest.mark.parametrize("case", fixtures.CASES)
def test_ecm_grn_history(tmp_path, case):
    inputs = fixtures.fixture(case)
    prep = root(tmp_path) / ("preparation-" + case)
    prep.mkdir(parents=True, exist_ok=False)
    (prep / "inputs-before-constructor.json").write_text(json.dumps(inputs, indent=2) + "\n")
    ids = inputs["definition"]["environment_geometry_definition"]["current_definition"]["ions"][
        "ids"
    ]
    cold_inputs = dict(
        mode="cold_initialization",
        network=inputs["network"],
        material_declaration=inputs["definition"],
        ion_ids=ids,
        cells=len(inputs["initial"]["cell_mol_m3"][0]),
        membranes=len(inputs["initial"]["voltage_V"]),
        environment_sites=len(inputs["initial"]["environment_mol_m3"][0]),
    )
    cold = references(prep / "cold", cold_inputs)
    try:
        binding = joined.bind(inputs)
        parent = joined.initialize(binding)
    except Exception as error:
        archive(
            tmp_path,
            case + "-unexpected-cold",
            dict(
                error=str(error),
                traceback=traceback.format_exc(),
                partial=getattr(error, "partial", None),
            ),
        )
        raise
    folder, captured = isolated(tmp_path, inputs)
    assert captured["status"] == "source_completed" and len(captured["history"]) == 3
    old.exact_nested(parent.network_cache, captured["cold_cache"])
    check(
        tmp_path,
        case + "-cold-errors",
        prep / "cold",
        compare_cold(binding, parent, cold[0], cold[1]),
    )
    for index, source in enumerate(captured["history"]):
        point = prep / ("point-" + str(index))
        answers = []

        def observer(before, point=point, answers=answers):
            answers.extend(references(point, before))

        digest = ions.digest(parent)
        try:
            candidate, trial, feedback = joined.advance(binding, parent, before_network=observer)
        except Exception as error:
            archive(
                tmp_path,
                case + "-unexpected-call-" + str(index),
                dict(
                    parent=parent,
                    error=str(error),
                    traceback=traceback.format_exc(),
                    partial=getattr(error, "partial", None),
                ),
            )
            raise
        archive(
            tmp_path,
            case + "-call-" + str(index),
            dict(parent=parent, candidate=candidate, trial=trial, network=feedback),
        )
        assert digest == ions.digest(parent) and len(answers) == 2
        for actual, expected in zip(trial.frames, source["frames"], strict=True):
            assert (actual.stage, actual.ion_id) == (expected["stage"], expected["ion_id"])
            old.exact_nested(actual.values._asdict(), expected["values"])
        old.exact_nested(trial.candidate.values._asdict(), source["candidate"])
        for actual, expected in zip(
            trial.environment_records, source["environment_records"], strict=True
        ):
            old.exact_nested(actual._asdict(), expected)
        old.exact_nested(feedback, source["network"])
        old.exact_nested(candidate.network_cache, source["network"]["cache_after"])
        assert feedback["source_completed"] and feedback["completed_transports"] == 2
        assert (
            feedback["before"]["owner"]["actual_core_identity"]
            and feedback["before"]["owner"]["grn_enabled"]
        )
        assert (
            not feedback["before"]["owner"]["molecules_enabled"]
            and not feedback["before"]["owner"]["standalone_sim_grn"]
        )
        expected = (
            ("clear_run_loop",)
            + (("run_loop_modulators",) if inputs["network"]["configuration"]["modulators"] else ())
            + ("run_loop",)
        )
        assert tuple(feedback["dispatch_stages"]) == expected
        check(
            tmp_path,
            case + "-local-errors-" + str(index),
            point,
            compare_local(feedback, answers[0], answers[1]),
        )
        parent = candidate
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                completed=True,
                exact_native=True,
                complete_calls=3,
                conditional_pre_network_checks=3,
                cold_reference_forms=2,
                warm_reference_forms=6,
                carried_reference_forms=0,
                genuine_ecm_grn=True,
                complete_public_cache_carry=True,
                case_role=inputs["case_role"],
                retained_material_panel_accepted=False,
                retained_material_checks_passed=39,
                retained_material_checks_total=40,
                physical_global_conservation_credit=False,
                field_solver_executed=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_ecm_grn_partial_failure(tmp_path, case):
    inputs = fixtures.raw_fixture(case)
    archive(tmp_path, case + "-inputs", inputs)
    folder, captured = isolated(tmp_path, inputs)
    assert captured["status"] == "source_refused"
    cold = case.startswith("cold_")
    expected = "KeyError" if cold else "BetseSimUnstableException"
    assert captured["failure"]["type"] == expected
    try:
        binding = joined.bind(inputs)
        parent = joined.initialize(binding)
        digest = ions.digest(parent)
        joined.advance(binding, parent)
    except joined.ECMNetworkRejected as error:
        archive(
            tmp_path,
            case + "-partial",
            dict(partial=error.partial, error=str(error), traceback=traceback.format_exc()),
        )
        leaf = error
        while leaf.__cause__ is not None:
            leaf = leaf.__cause__
        assert type(leaf).__name__ == expected and str(leaf) == captured["failure"]["message"]
        if cold:
            old.exact_nested(error.partial["cache"], captured["cold_failure"])
            assert not captured["history"]
        else:
            assert digest == ions.digest(parent)
            feedback = error.partial["network"]
            old.exact_nested(feedback, captured["history"][0]["network"])
            assert feedback["completed_transports"] == (
                0 if case == "first_environment_negative" else 1
            )
            assert not feedback["source_completed"]
            assert any(
                frame["stage"] == "environment_mix" and np.any(frame["fields"]["cX_env_o"] < 0)
                for frame in feedback["mover_frames"]
            )
    except Exception as error:
        archive(
            tmp_path,
            case + "-unexpected-refusal",
            dict(error=str(error), traceback=traceback.format_exc()),
        )
        raise
    else:
        raise AssertionError("Intended native ECM refusal was not reached")
    (folder / "raw-retention.json").write_text(
        json.dumps(
            dict(
                source_refused=True,
                source_type=expected,
                cold_initialization_failure=cold,
                exact_native_partial=True,
                partial_ecm_state_preserved=True,
                completed_transports=0 if cold or case == "first_environment_negative" else 1,
                positive_credit=False,
                physical_conservation_credit=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)
def test_ecm_grn_dependencies(tmp_path, dependency):
    inputs = fixtures.fixture()
    try:
        binding = joined.bind(inputs)
        parent = joined.initialize(binding)
    except Exception as error:
        archive(
            tmp_path,
            dependency + "-unexpected-valid-admission",
            dict(
                error=str(error),
                traceback=traceback.format_exc(),
                partial=getattr(error, "partial", None),
            ),
        )
        raise
    archive(tmp_path, dependency + "-valid-admission", dict(binding=binding, parent=parent))
    messages = dict(
        wrong_owner="Require a complete genuine ECM GRN declaration",
        mitochondria="ECM GRN mitochondria/fluid/cuts/standalone require separate state",
        fluid="ECM network fluid coupling requires separate state",
        charged_cold="Charged ECM cold compensation is separately scoped",
        missing_cache="Require complete ECM GRN owner cache",
        missing_default="Missing source-initialized ECM gene fields",
        missing_coefficients="Require owned ECM molecular grid coefficients",
        prepared_mapping="Require owned in-grid TJ indices",
    )
    if dependency in ("missing_cache", "missing_default", "missing_coefficients"):
        raw = ions.data(parent.network_cache)
        if dependency == "missing_cache":
            raw["kind"] = "missing"
        elif dependency == "missing_default":
            del raw["wire"]["molecule_fields"]["X"]["Dm"]
        else:
            del raw["coefficient_fields"]["D_env_weight"]
        changed = joined._state(binding, parent.material, raw, parent.controls)
        archive(
            tmp_path,
            dependency + "-malformed-parent-before-call",
            dict(parent=changed, supplied_cache=raw, inputs=inputs),
        )
        with pytest.raises(joined.ECMNetworkRejected) as caught:
            joined.advance(binding, changed)
        archive(tmp_path, dependency + "-available-partial", dict(partial=caught.value.partial))
        if dependency in ("missing_cache", "missing_default"):
            partial = caught.value.partial
            assert partial["cache"] is None
            assert partial["available_context"]["owner_available"] is False
            assert partial["available_context"]["core_available"] is False
            assert partial["available_context"]["complete_owner_cache_claimed"] is False
            assert not partial["capture_errors"]
            old.exact_nested(partial["supplied_cache"], raw)
            assert partial["available_context"]["wire"]["owner_fields"] == {}
    else:
        changed = copy.deepcopy(inputs)
        if dependency == "wrong_owner":
            changed["network"]["owner"] = "molecules"
        elif dependency == "mitochondria":
            changed["network"]["scope"]["mitochondria"] = True
        elif dependency == "fluid":
            changed["definition"]["parameters"]["fluid_flow"] = True
        elif dependency == "charged_cold":
            changed["network"]["cold_publish"] = True
        else:
            changed["network"]["grid_index_groups"]["all_bound_mem_inds"] = [999]
        archive(tmp_path, dependency + "-inputs", changed)
        with pytest.raises(ValueError) as caught:
            joined.bind(changed)
    leaf = caught.value
    while leaf.__cause__ is not None:
        leaf = leaf.__cause__
    archive(tmp_path, dependency + "-refusal", dict(type=type(leaf).__name__, message=str(leaf)))
    assert type(leaf) is ValueError and str(leaf) == messages[dependency]
    (root(tmp_path) / ("dependency-" + dependency + ".json")).write_text(
        json.dumps(
            dict(
                baseline_admitted=True,
                intended_failure_reached=True,
                actual_leaf_type="ValueError",
                expected_message=messages[dependency],
                actual_message=str(leaf),
                source_failure_credit=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.fixture(scope="module", autouse=True)
def runtime_receipt(tmp_path_factory):
    row = inventory()
    if cpu := os.environ.get("CELLS_ECM_GRN_CPU"):
        assert row["measured_cpu_affinity"] == [int(cpu)]
    folder = root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "runtime.json").write_text(json.dumps(row, indent=2) + "\n")
