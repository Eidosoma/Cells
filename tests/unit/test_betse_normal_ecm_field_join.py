"""Prepared full normal ECM field feedback; no qualification during preparation."""

import copy
import json
import os
import subprocess
import sys
import traceback
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_field_join as joined
from cells.processes import betse_normal_ion_join as ions
from tests.unit import test_betse_ecm_grn_join as legacy
from tests.unit.test_betse_fast_solver import archive_read
from validation.betse import betse_ecm_transport_checks as material_checks
from validation.betse import betse_environment_field_checks as field_checks
from validation.betse import betse_normal_ecm_field_join_fixtures as fixtures
from validation.betse import betse_normal_ecm_field_join_native as native
from validation.betse.betse_normal_channel_join_runtime import inventory

exact = legacy.old.exact_nested


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "normal-ecm-field-join"


def archive(tmp_path, name, value):
    return native.archives.write_archive(root(tmp_path) / name, ions.data(value))


def references(folder, inputs):
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(
        json.dumps(legacy.old.old.plain(ions.data(inputs)), indent=2, allow_nan=False) + "\n"
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
                    "validation.betse.betse_normal_ecm_field_join_reference",
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


def isolated(tmp_path, inputs):
    folder = root(tmp_path) / ("isolated-" + inputs["case_id"])
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(json.dumps(inputs, indent=2, allow_nan=False) + "\n")
    with (folder / "native.stdout.log").open("x") as stream:
        subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "validation.betse.betse_normal_ecm_field_join_native",
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


def check(tmp_path, name, folder, rows):
    # Full arrays precede every numerical assertion, including self-resolution.
    archive(tmp_path, name, dict(fields=rows, physical_global_conservation_credit=False))
    result = dict(
        fields={k: v["metric"] for k, v in rows.items()},
        resolutions={k: v["resolution"] for k, v in rows.items()},
        fresh_conditional_reference=True,
        carried_reference_forms=0,
        physical_global_conservation_credit=False,
    )
    (folder / "comparison.json").write_text(json.dumps(result, indent=2) + "\n")
    assert rows and max(v["normalized_max_error"] for v in result["fields"].values()) <= 1
    assert max(v["normalized_max_error"] for v in result["resolutions"].values()) <= 0.1


def field_output(stage):
    return dict(
        current=dict(values=stage.current.values._asdict()),
        environment=dict(
            values=stage.environment.values._asdict(),
            current_hodge=stage.environment.current_hodge._asdict(),
            smoothing_hodge=None,
        ),
        voltage=dict(values=stage.voltage.values._asdict()),
    )


def compare_field(binding, stage, lower, target):
    rows, add = legacy.comparisons()
    raw = stage.before["definition"]["environment_geometry_definition"]
    cg = raw["current_definition"]["geometry"]
    e = len(target["geometry"]["grid_points_m"])
    factor = (
        128
        * np.finfo(float).eps
        * (
            len(raw["current_definition"]["ions"]["ids"])
            + len(cg["cell_ids"])
            + len(cg["membrane_ids"])
            + e
            + 64
        )
    )
    actual = field_output(stage)
    for section in ("current", "environment", "voltage"):
        values = field_checks.flat(actual[section]["values"])
        wanted = field_checks.flat(target[section]["values"])
        lo = field_checks.flat(lower[section]["values"])
        gross = field_checks.flat(target[section]["gross"])
        assert values.keys() == wanted.keys() == lo.keys() == gross.keys()
        for key, value in wanted.items():
            floor = (
                1e-30
                if section == "current" or key.endswith(("charge_C_m3", "charge_C_m2"))
                else 3e-18
                if key == "magnetic_field_source"
                else 3e-14
                if key.endswith("_V")
                else 3e-13
            )
            add(
                section + "/" + key,
                values[key],
                value,
                lo[key],
                floor + factor * np.asarray(gross[key]),
                "source field/current/voltage",
            )
    for key, value in target["environment"]["current_hodge"].items():
        add(
            "hodge/" + key,
            actual["environment"]["current_hodge"][key],
            value,
            lower["environment"]["current_hodge"][key],
            3e-13 + factor * np.asarray(target["environment"]["hodge_gross"][key]),
            "source HH intermediate",
        )
    gb = binding.material_binding.geometry_binding
    for key, value in target["cache"].items():
        wanted = np.asarray(value)
        add(
            "fixed_cache/" + key,
            getattr(gb.cache, key),
            value,
            lower["cache"][key],
            3e-14 + factor * abs(wanted),
            "source initializer cache",
        )
    for key in ("membrane_to_grid", "cell_to_grid", "index_ij", "shape"):
        np.testing.assert_array_equal(getattr(gb.geometry, key), target["geometry"][key])
    for key in (
        "dirichlet_inverse_m2",
        "neumann_inverse_m2",
        "dirichlet_laplacian_per_m2",
        "neumann_laplacian_per_m2",
    ):
        wanted = np.asarray(target["geometry"][key])
        add(
            "operator/" + key,
            getattr(gb.geometry, key),
            wanted,
            lower["geometry"][key],
            3e-13 + 6e-12 * abs(wanted),
            "source derived operator",
        )
    return rows


def compare_material(trial, lower, target):
    lower, target = lower["history"][0], target["history"][0]

    # The ordinary conditional oracle has no molecule-induced voltage nonce.
    # Test all pre-GRN buffers and all post-GRN ionic/flux/GJ-field buffers;
    # the separate actual pre-GRN reference and native trace test both nonces.
    def ordinary(row):
        out = copy.deepcopy(ions.data(row))
        out["frames"] = [frame for frame in out["frames"] if frame["stage"] != "ecm_grn_dispatch"]
        return material_checks.columns(out)

    observed = dict(
        frames=ions.data(trial.frames),
        environment_records=ions.data(trial.environment_records),
        candidate=trial.candidate.values._asdict(),
        ledgers=trial.diagnostics,
    )
    actual, lo, wanted = ordinary(observed), ordinary(lower), ordinary(target)
    rows, add = legacy.comparisons()
    assert actual.keys() == lo.keys() == wanted.keys()
    dispatch = next(
        i for i, frame in enumerate(observed["frames"]) if frame["stage"] == "ecm_grn_dispatch"
    )
    for key, value in wanted.items():
        leaf = key.rsplit(".", 1)[-1]
        after = (
            key.startswith("candidate.")
            or key.startswith("frame_")
            and int(key.split(".")[0][6:]) >= dispatch
        )
        if (
            leaf == "source_voltage_nonce_delta_V"
            or after
            and leaf in ("voltage_V", "junction_voltage_V")
        ):
            continue
        add(
            key,
            actual[key],
            value,
            lo[key],
            material_checks.budget(key, np.asarray(value)),
            "unchanged ECM material budget",
        )
    return rows


def compare_native_material(trial, captured):
    assert len(trial.frames) == len(captured["frames"])
    for actual, expected in zip(trial.frames, captured["frames"], strict=True):
        assert (actual.stage, actual.ion_id) == (expected["stage"], expected["ion_id"])
        exact(actual.values._asdict(), expected["values"])
    for actual, expected in zip(
        trial.environment_records, captured["environment_records"], strict=True
    ):
        exact(actual._asdict(), expected)
    exact(trial.candidate.values._asdict(), captured["material_candidate"])


def cold_inputs(inputs):
    return dict(
        mode="cold_initialization",
        network=inputs["network"],
        material_declaration=inputs["definition"],
        ion_ids=inputs["definition"]["environment_geometry_definition"]["current_definition"][
            "ions"
        ]["ids"],
        cells=len(inputs["initial"]["cell_mol_m3"][0]),
        membranes=len(inputs["initial"]["voltage_V"]),
        environment_sites=len(inputs["initial"]["environment_mol_m3"][0]),
    )


@pytest.mark.parametrize("case", fixtures.CASES)
def test_normal_ecm_field_history(tmp_path, case):
    inputs = fixtures.fixture(case)
    prep = root(tmp_path) / ("preparation-" + case)
    prep.mkdir(parents=True, exist_ok=False)
    (prep / "inputs-before-constructor.json").write_text(json.dumps(inputs, indent=2) + "\n")
    cold = references(prep / "cold", cold_inputs(inputs))
    cold_parents, bootstrap = [], []

    def after_cold(parent):
        archive(tmp_path, case + "-cold-return-before-bootstrap", dict(parent=parent))
        cold_parents.append(parent)

    def before_bootstrap(before):
        bootstrap.extend(references(prep / "bootstrap", before))

    try:
        binding = joined.bind(inputs)
        parent = joined.initialize(binding, after_cold=after_cold, before_field=before_bootstrap)
        archive(tmp_path, case + "-bootstrap-return", dict(parent=parent))
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
    assert len(cold_parents) == 1 and len(bootstrap) == 2
    for key, value in captured["geometry"].items():
        exact(getattr(binding.material_binding.geometry_binding.geometry, key), value)
    exact(binding.material_binding.geometry_binding.cache._asdict(), captured["initializer_cache"])
    exact(cold_parents[0].network_cache, captured["cold_cache"])
    exact(cold_parents[0].material.values._asdict(), captured["cold_material"])
    check(
        tmp_path,
        case + "-cold-errors",
        prep / "cold",
        legacy.compare_cold(binding, cold_parents[0], *cold),
    )
    exact(parent.field.before, captured["bootstrap"]["before"])
    for section, values in field_output(parent.field).items():
        exact(values, captured["bootstrap"][section])
    exact(parent.network.material.values._asdict(), captured["bootstrap"]["candidate"])
    check(
        tmp_path,
        case + "-bootstrap-errors",
        prep / "bootstrap",
        compare_field(binding, parent.field, *bootstrap),
    )
    fixed = ions.digest(binding.material_binding.geometry_binding.cache)
    for index, native_call in enumerate(captured["history"]):
        point = prep / ("point-" + str(index))
        point.mkdir()
        answers = {name: [] for name in ("material", "network", "field")}
        observed = {}

        def before(name, observed=observed, answers=answers, point=point):
            def callback(incoming):
                observed[name] = ions.data(incoming)
                answers[name].extend(references(point / name, incoming))

            return callback

        def after_material(candidate, trial, feedback, index=index, parent=parent):
            archive(
                tmp_path,
                case + "-material-return-before-field-" + str(index),
                dict(parent=parent, candidate=candidate, trial=trial, network=feedback),
            )

        digest = ions.digest(parent)
        try:
            candidate, trial, feedback, context = joined.advance(
                binding,
                parent,
                before_material=before("material"),
                before_network=before("network"),
                before_field=before("field"),
                after_material=after_material,
            )
            archive(
                tmp_path,
                case + "-complete-return-" + str(index),
                dict(
                    parent=parent,
                    candidate=candidate,
                    trial=trial,
                    network=feedback,
                    context=context,
                ),
            )
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
        assert digest == ions.digest(parent) and all(len(value) == 2 for value in answers.values())
        assert fixed == ions.digest(binding.material_binding.geometry_binding.cache)
        exact(observed["material"], native_call["material_before"])
        exact(observed["network"], native_call["network"]["before"])
        exact(observed["field"], native_call["field"]["before"])
        compare_native_material(trial, native_call)
        exact(feedback, native_call["network"])
        # The normal public cache contains ionic views. Compare after material
        # commit, separately from the pre-commit run_dispatch cache snapshot.
        exact(context["material_parent"].network_cache, native_call["post_material_cache"])
        exact(candidate.network.network_cache, native_call["post_material_cache"])
        for section, values in field_output(candidate.field).items():
            exact(values, native_call["field"][section])
        exact(candidate.network.material.values._asdict(), native_call["candidate"])
        for key in (
            "junction_voltage_V",
            "junction_field_source",
            "junction_field_xy_source",
            "gap_open",
        ):
            np.testing.assert_array_equal(
                getattr(candidate.network.material.values, key),
                getattr(context["material_parent"].material.values, key),
            )
        check(
            tmp_path,
            case + "-material-errors-" + str(index),
            point / "material",
            compare_material(trial, *answers["material"]),
        )
        check(
            tmp_path,
            case + "-network-errors-" + str(index),
            point / "network",
            legacy.compare_local(feedback, *answers["network"]),
        )
        check(
            tmp_path,
            case + "-field-errors-" + str(index),
            point / "field",
            compare_field(binding, candidate.field, *answers["field"]),
        )
        parent = candidate
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                completed=True,
                exact_native=True,
                complete_calls=3,
                case_role=inputs["case_role"],
                cold_reference_forms=2,
                bootstrap_reference_forms=2,
                conditional_material_reference_forms=6,
                conditional_network_reference_forms=6,
                conditional_field_reference_forms=6,
                carried_reference_forms=0,
                full_native_field_suffix=True,
                old_field_seam_removed=True,
                initialization_boundary_explicit=True,
                stale_gap_caches_preserved=True,
                retained_material_panel_accepted=False,
                retained_material_checks_passed=39,
                retained_material_checks_total=40,
                physical_global_conservation_credit=False,
                independent_trajectory=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_normal_ecm_field_raw_partial(tmp_path, case):
    inputs = fixtures.raw_fixture(case)
    archive(tmp_path, case + "-raw-inputs", inputs)
    folder, captured = isolated(tmp_path, inputs)
    completed = []
    parent = None

    def after_cold(value):
        archive(tmp_path, case + "-raw-cold-return", dict(parent=value))

    def after_material(candidate, trial, feedback):
        archive(
            tmp_path,
            case + "-raw-material-return-" + str(len(completed)),
            dict(candidate=candidate, trial=trial, network=feedback),
        )

    try:
        binding = joined.bind(inputs)
        parent = joined.initialize(binding, after_cold=after_cold)
        archive(tmp_path, case + "-raw-bootstrap-return", dict(parent=parent))
        for index in range(3):
            candidate, trial, feedback, context = joined.advance(
                binding, parent, after_material=after_material
            )
            archive(
                tmp_path,
                case + "-raw-complete-return-" + str(index),
                dict(
                    parent=parent,
                    candidate=candidate,
                    trial=trial,
                    network=feedback,
                    context=context,
                ),
            )
            completed.append((candidate, trial, feedback, context))
            parent = candidate
    except joined.FieldJoinRejected as error:
        archive(
            tmp_path,
            case + "-raw-available-partial",
            dict(
                parent=parent,
                partial=error.partial,
                error=str(error),
                traceback=traceback.format_exc(),
            ),
        )
        strict = case.startswith("bootstrap_")
        observed_failure_stage = error.partial["stage"]
        if strict:
            assert not completed and error.partial["stage"] == "bootstrap"
            assert (
                captured["bootstrap"]["source_completed"]
                and not captured["bootstrap"]["all_fields_finite"]
            )
            rejected = error.partial["rejected_trial"]
            assert rejected is not None
            section = "current" if case == "bootstrap_current_overflow" else "environment"
            exact(rejected.values._asdict(), captured["bootstrap"][section]["values"])
        else:
            assert captured["status"] == "source_refused"
            actual = error.partial["partial"]
            observed_failure_stage = actual["stage"]
            source = captured["history"][len(completed)]
            if case.endswith("network_negative"):
                assert not completed and actual["stage"] == "network"
                exact(actual["network"], source["network"])
            else:
                # Historical case ID retained: call3 refuses in GRN before material commit.
                assert len(completed) == 2 and actual["stage"] == "network"
                assert len(captured["history"]) == 3
                assert all(row["source_completed"] for row in captured["history"][:2])
                assert not source["source_completed"]
                assert not actual["network"]["source_completed"]
                assert captured["failure"]["stage"] == "material_network"
                exact(actual["network"], source["network"])
                assert actual["material"]["trial"] is None
                assert 0 < len(actual["material"]["frames"]) == len(source["frames"])
                for frame, expected in zip(
                    actual["material"]["frames"], source["frames"], strict=True
                ):
                    assert (frame["stage"], frame["ion_id"]) == (
                        expected["stage"],
                        expected["ion_id"],
                    )
                    exact(frame["values"], expected["values"])
                exact(actual["material"]["environment_records"], source["environment_records"])
            for result, source in zip(completed, captured["history"], strict=False):
                candidate, trial, feedback, context = result
                compare_native_material(trial, source)
                exact(feedback, source["network"])
                exact(candidate.network.material.values._asdict(), source["candidate"])
    except Exception as error:
        archive(
            tmp_path,
            case + "-raw-unexpected-refusal",
            dict(
                parent=parent,
                error=str(error),
                traceback=traceback.format_exc(),
                partial=getattr(error, "partial", None),
            ),
        )
        raise
    else:
        archive(tmp_path, case + "-raw-unexpected-complete", dict(parent=parent))
        raise AssertionError("Declared raw source or strict finite limit was not reached")
    (folder / "raw-retention.json").write_text(
        json.dumps(
            dict(
                positive_credit=False,
                completed_calls=len(completed),
                historical_fixture_id=case,
                observed_component_failure_stage=observed_failure_stage,
                observed_native_failure_stage=captured["failure"]["stage"],
                material_overflow_qualified=False,
                strict_finite_guard_distinct_from_native_exception=strict,
                complete_native_raw_buffers_retained=True,
                complete_available_port_partial_retained=True,
                physical_global_conservation_credit=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)
def test_normal_ecm_field_dependencies(tmp_path, dependency):
    inputs = fixtures.fixture()
    archive(tmp_path, dependency + "-baseline-inputs-before-constructor", inputs)
    try:
        binding = joined.bind(inputs)
        parent = joined.initialize(
            binding,
            after_cold=lambda value: archive(
                tmp_path, dependency + "-baseline-cold-return", dict(parent=value)
            ),
        )
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
        ECM_disabled="Require the original enabled ECM field branch",
        fluid="ECM network fluid coupling requires separate state",
        charged_cold="Charged ECM cold compensation is separately scoped",
        missing_field_state="Require the actual prior reconstructed field",
        changed_field_output="Require the actual prior reconstructed field",
        supplied_operator="Derive field operators and coefficients from original declarations",
        supplied_old_field="Old electric fields must come from the actual preceding field stage",
        missing_cache="Require complete ECM GRN owner cache",
        missing_default="Missing source-initialized ECM gene fields",
        nonpositive_capacitance="Require finite positive voltage parameter: capacitance_F_m2",
    )
    if dependency in (
        "missing_cache",
        "missing_default",
        "missing_field_state",
        "changed_field_output",
    ):
        if dependency.startswith("missing_") and dependency != "missing_field_state":
            cached = ions.data(parent.network.network_cache)
            if dependency == "missing_cache":
                cached["kind"] = "missing"
            else:
                del cached["wire"]["molecule_fields"]["X"]["Dm"]
            net = joined._state(binding, parent.network.material, cached, parent.network.controls)
            changed = joined.state(binding, net, parent.field)
        else:
            bad = (
                None if dependency == "missing_field_state" else replace(parent.field, voltage=None)
            )
            changed = joined.state(binding, parent.network, bad)
        archive(
            tmp_path,
            dependency + "-malformed-parent-before-call",
            dict(inputs=inputs, parent=changed),
        )
        with pytest.raises((ValueError, joined.FieldJoinRejected)) as caught:
            joined.advance(binding, changed)
        archive(
            tmp_path, dependency + "-partial", dict(partial=getattr(caught.value, "partial", None))
        )
    else:
        changed = copy.deepcopy(inputs)
        if dependency == "ECM_disabled":
            changed["definition"]["environment_geometry_definition"]["is_ecm"] = False
        elif dependency == "fluid":
            changed["definition"]["parameters"]["fluid_flow"] = True
        elif dependency == "charged_cold":
            changed["network"]["cold_publish"] = True
        elif dependency == "supplied_operator":
            changed["field_parameters"]["inverse_m2"] = [[1.0]]
        elif dependency == "supplied_old_field":
            changed["steps"][0]["material"]["electric_x_source"] = [[0.0]]
        else:
            changed["field_parameters"]["capacitance_F_m2"] = 0.0
        archive(tmp_path, dependency + "-malformed-inputs-before-call", changed)
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
                actual_leaf_type=type(leaf).__name__,
                source_failure_credit=False,
                expected_message=messages[dependency],
                actual_message=str(leaf),
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.fixture(scope="module", autouse=True)
def runtime_receipt(tmp_path_factory):
    row = inventory()
    if cpu := os.environ.get("CELLS_NORMAL_ECM_FIELD_CPU"):
        assert row["measured_cpu_affinity"] == [int(cpu)]
    folder = root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "runtime.json").write_text(json.dumps(row, indent=2) + "\n")
