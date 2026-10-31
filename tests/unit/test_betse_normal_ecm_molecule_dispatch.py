"""Held dual native-owner conditionals, source books and independent flag controls."""

import copy
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_molecule_dispatch as dispatch
from cells.processes import betse_normal_ion_join as ions
from tests.unit import test_betse_ecm_grn_join as chemistry
from tests.unit import test_betse_normal_ecm_catalog_join as catalog
from tests.unit import test_betse_normal_ecm_field_join as field_checks
from tests.unit.test_betse_fast_solver import archive_read
from validation.betse import betse_ecm_transport_checks as material_checks
from validation.betse import betse_normal_ecm_molecule_dispatch_fixtures as fixtures
from validation.betse import betse_normal_ecm_molecule_failure_checks as failure_checks
from validation.betse import betse_normal_grn_join_native as archives

exact = field_checks.exact


@pytest.fixture(autouse=True)
def explicit_release():
    if os.environ.get("CELLS_ECM_MOLECULE_DISPATCH_RELEASED") != "1":
        pytest.skip("Held general-molecule source preparation; Chief must explicitly release")


def root(tmp_path):
    return (
        Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path)))
        / "normal-ecm-molecule-dispatch"
    )


def archive(tmp_path, name, value):
    return archives.write_archive(root(tmp_path) / name, ions.data(value))


def references(folder, inputs):
    folder.mkdir(parents=True, exist_ok=False)
    # Existing explicit JSON lowering preserves all actual numeric fields.
    from validation.betse.betse_normal_ecm_event_join_fixtures import plain as json_values

    (folder / "inputs.json").write_text(
        json.dumps(json_values(ions.data(inputs)), indent=2, allow_nan=False) + "\n"
    )
    results = []
    for level in (1, 2):
        output = folder / ("reference-" + str(level) + ".json")
        with (folder / ("reference-" + str(level) + ".stdout.log")).open("x") as stream:
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "validation.betse.betse_normal_ecm_molecule_dispatch_reference",
                    "--inputs",
                    str(folder / "inputs.json"),
                    "--output",
                    str(output),
                    "--refinement",
                    str(level),
                ],
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=180,
            )
        result = json.loads(output.read_text())
        assert result["production_imports_denied"] and not result["loaded_production_modules"]
        assert result["carried_reference_forms"] == 0 and result["decimal_precision"] == (
            100 if level == 1 else 160
        )
        assert result["runtime"]["measured_cpu_affinity"] == sorted(os.sched_getaffinity(0))
        results.append(result)
    return results


def isolated(folder, inputs):
    from validation.betse.betse_normal_ecm_event_join_fixtures import plain as json_values

    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(
        json.dumps(json_values(ions.data(inputs)), indent=2, allow_nan=False) + "\n"
    )
    with (folder / "native.stdout.log").open("x") as stream:
        subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "validation.betse.betse_normal_ecm_molecule_dispatch_native",
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
    value = archive_read(folder / "native")
    assert value["production_imports_denied"] and not value["loaded_production_modules"]
    return value


def check(tmp_path, name, folder, rows):
    archive(tmp_path, name, dict(fields=rows, physical_global_conservation_credit=False))
    report = dict(
        fields={key: row["metric"] for key, row in rows.items()},
        resolutions={key: row["resolution"] for key, row in rows.items()},
        fresh_conditional_reference=True,
        carried_reference_forms=0,
        physical_global_conservation_credit=False,
    )
    (folder / "comparison.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    assert rows and max(row["normalized_max_error"] for row in report["fields"].values()) <= 1
    assert max(row["normalized_max_error"] for row in report["resolutions"].values()) <= 0.1


def cold_input(raw, role):
    field = raw["field"]
    names = field["definition"]["environment_geometry_definition"]["current_definition"]["ions"][
        "ids"
    ]
    return dict(
        mode="cold_initialization",
        owner_role=role,
        network=raw["handlers"][role]["network"],
        catalog=raw["handlers"][role]["catalog"],
        material_declaration=field["definition"],
        ion_ids=names,
        cells=len(field["initial"]["cell_mol_m3"][0]),
        membranes=len(field["initial"]["voltage_V"]),
        environment_sites=len(field["initial"]["environment_mol_m3"][0]),
        calcium_configuration=raw["calcium"],
        bootstrap_dt_s=field["bootstrap"]["dt_s"],
    )


def prefix_rows(trial, lower, target):
    rows, add = chemistry.comparisons()
    assert len(lower["frames"]) == len(target["frames"])
    actual = trial.frames[: len(target["frames"])]
    for index, (frame, wanted) in enumerate(zip(actual, target["frames"], strict=True)):
        assert (frame.stage, frame.ion_id) == (wanted["stage"], wanted["ion_id"])
        for key, value in wanted["values"].items():
            add(
                f"frame_{index}.{key}",
                frame.values._asdict()[key],
                value,
                lower["frames"][index]["values"][key],
                material_checks.budget(key, np.asarray(value)),
                "unchanged ECM material budget",
            )
    for index, wanted in enumerate(target["environment_records"]):
        actual = trial.environment_records[index]._asdict()
        for key, value in wanted.items():
            if key == "ion_id":
                continue
            add(
                f"environment_{index}.{key}",
                actual[key],
                value,
                lower["environment_records"][index][key],
                material_checks.budget(key, np.asarray(value)),
                "unchanged ECM material budget",
            )
    return rows


def commit_rows(trial, lower, target):
    rows, add = chemistry.comparisons()
    # Every deferred source frame, candidate and original amount ledger is
    # independently recomputed from the saved pre-commit conditional buffers.
    actual_frames = trial.frames[-len(target["frames"]) :] if target["frames"] else ()
    assert len(actual_frames) == len(target["frames"])
    for index, (frame, wanted) in enumerate(zip(actual_frames, target["frames"], strict=True)):
        assert (frame.stage, frame.ion_id) == (wanted["stage"], wanted["ion_id"])
        for key, value in wanted["values"].items():
            add(
                f"commit_frame_{index}.{key}",
                frame.values._asdict()[key],
                value,
                lower["frames"][index]["values"][key],
                material_checks.budget(key, np.asarray(value)),
                "unchanged ECM material budget",
            )
    for key, value in target["candidate"].items():
        add(
            "candidate." + key,
            trial.candidate.values._asdict()[key],
            value,
            lower["candidate"][key],
            material_checks.budget(key, np.asarray(value)),
            "unchanged ECM candidate budget",
        )
    for key in material_checks.LEDGERS:
        value = target["ledgers"][key]
        add(
            "ledger." + key,
            trial.diagnostics[key],
            value,
            lower["ledgers"][key],
            material_checks.budget(key, np.asarray(value)),
            "unchanged ECM source-effective ledger budget",
        )
    return rows


@pytest.mark.parametrize("case", fixtures.CASES)
def test_two_owner_history(tmp_path, case):
    raw = fixtures.fixture(case)
    binding = dispatch.bind(raw)
    archive(tmp_path, case + "-inputs-before-setup", raw)
    folder = root(tmp_path) / case
    folder.mkdir(parents=True, exist_ok=False)
    enabled = dict(
        molecules=raw["configuration"]["general network"]["implement network"],
        grn=raw["configuration"]["gene regulatory network settings"][
            "gene regulatory network simulated"
        ],
    )
    captured = {}
    cold = {}
    boot = []
    forms_count = 0
    cold_material = copy.deepcopy(raw["field"]["initial"])

    def setup_observer(role, stage, value):
        archive(tmp_path, case + "-" + role + "-" + stage, value)
        if stage == "after_setup":
            cold_material.clear()
            cold_material.update(ions.data(value["material"]))
        if role == "all":
            captured["setup"] = isolated(folder / "native-setup", value)
            for owner in dispatch.runtime.ROLES:
                if enabled[owner]:
                    cold[owner] = references(folder / ("cold-" + owner), cold_input(raw, owner))

    def before_boot(value):
        boot.extend(references(folder / "bootstrap", value))

    try:
        parent = dispatch.initialize(binding, observer=setup_observer, before_field=before_boot)
    except Exception as error:
        archive(
            tmp_path,
            case + "-setup-failure",
            dict(partial=getattr(error, "partial", None), traceback=traceback.format_exc()),
        )
        raise
    archive(tmp_path, case + "-bootstrap-return", parent)
    native = captured["setup"]
    assert native["status"] == "source_completed"
    # Compare the actual source-cold buffers before bootstrap voltage changes.
    exact(native["returned"]["material"], cold_material)
    for role in dispatch.runtime.ROLES:
        saved = parent.owners["handlers"][role]
        if enabled[role]:
            exact(ions.data(saved["cache"]), native["returned"]["handlers"][role])
            check(
                tmp_path,
                case + "-" + role + "-cold-errors",
                folder / ("cold-" + role),
                chemistry.compare_cold(
                    binding.component, SimpleNamespace(network_cache=saved["cache"]), *cold[role]
                ),
            )
        else:
            assert saved is native["returned"]["handlers"][role] is None
    for key in dispatch.runtime.PUBLICATIONS:
        if not any(enabled.values()):
            exact(parent.owners["shared"][key], raw["shared_initial"][key])
    check(
        tmp_path,
        case + "-bootstrap-errors",
        folder / "bootstrap",
        field_checks.compare_field(binding.component, parent.field, *boot),
    )
    forms_count += 2 + 2 * sum(enabled.values())
    for index in range(3):
        point = folder / ("point-" + str(index))
        point.mkdir()
        answers = {}
        native_call = {}
        observed = {}
        previous = parent
        digest = ions.digest(previous)

        def before(mode, index=index, observed=observed, answers=answers, point=point):
            def callback(value):
                archive(tmp_path, case + "-" + mode + "-before-" + str(index), value)
                observed[mode] = ions.data(value)
                answers[mode] = references(point / mode, value)

            return callback

        def handler(
            role,
            stage,
            value,
            index=index,
            native_call=native_call,
            point=point,
            observed=observed,
            answers=answers,
        ):
            archive(tmp_path, case + "-" + role + "-" + stage + "-" + str(index), value)
            if role == "all":
                native_call["result"] = isolated(point / "native-dispatch", value)
            elif stage in ("channels", "network"):
                key = role + "-" + stage
                observed[key] = ions.data(value)
                answers[key] = references(point / key, value)

        try:
            parent, details = dispatch.advance(
                binding,
                parent,
                before_material=before("material"),
                before_calcium=before("calcium"),
                handler_observer=handler,
                before_commit=before("commit"),
                before_field=before("field"),
            )
            archive(
                tmp_path, case + "-accepted-" + str(index), dict(parent=parent, details=details)
            )
        except Exception as error:
            archive(
                tmp_path,
                case + "-failure-" + str(index),
                dict(
                    parent=previous,
                    partial=getattr(error, "partial", None),
                    traceback=traceback.format_exc(),
                ),
            )
            raise
        assert ions.digest(previous) == digest and parent.cursor == index + 1
        native = native_call["result"]
        assert native["status"] == "source_completed"
        exact(observed["commit"]["values_before"], native["returned"]["material"])
        exact(ions.data(details["dispatch"]["shared_after"]), native["returned"]["shared"])
        expected_order = [role for role in dispatch.runtime.ROLES if enabled[role]]
        assert [
            row["role"] for row in details["dispatch"]["order"] if row["stage"] == "before_dispatch"
        ] == expected_order
        for role in dispatch.runtime.ROLES:
            saved = parent.owners["handlers"][role]
            if enabled[role]:
                exact(ions.data(saved["cache"]), native["returned"]["handlers"][role])
                feedback = details["dispatch"]["handlers"][role]
                check(
                    tmp_path,
                    case + "-" + role + "-channels-errors-" + str(index),
                    point / (role + "-channels"),
                    catalog.compare_channels(
                        binding.component, feedback, *answers[role + "-channels"]
                    ),
                )
                check(
                    tmp_path,
                    case + "-" + role + "-network-errors-" + str(index),
                    point / (role + "-network"),
                    chemistry.compare_local(feedback, *answers[role + "-network"]),
                )
            else:
                assert saved is native["returned"]["handlers"][role] is None
        if raw["field"]["steps"][index]["publication"] and expected_order:
            assert parent.owners["publication_owner"] == expected_order[-1]
        else:
            assert parent.owners["publication_owner"] == previous.owners["publication_owner"]
            exact(
                parent.owners["wire"]["simulator_fields"],
                previous.owners["wire"]["simulator_fields"],
            )
        check(
            tmp_path,
            case + "-material-prefix-errors-" + str(index),
            point / "material",
            prefix_rows(details["trial"], *answers["material"]),
        )
        check(
            tmp_path,
            case + "-calcium-errors-" + str(index),
            point / "calcium",
            catalog.compare_calcium(details["calcium"], *answers["calcium"]),
        )
        check(
            tmp_path,
            case + "-commit-errors-" + str(index),
            point / "commit",
            commit_rows(details["trial"], *answers["commit"]),
        )
        check(
            tmp_path,
            case + "-field-errors-" + str(index),
            point / "field",
            field_checks.compare_field(binding.component, parent.field, *answers["field"]),
        )
        forms_count += 8 + 4 * sum(enabled.values())
    archive(
        tmp_path,
        case + "-summary",
        dict(
            completed_calls=3,
            fresh_reference_forms=forms_count,
            native_conditional_captures=4,
            independently_carried_trajectory=False,
            no_ER_enablement=True,
            shared_publications_summed=False,
            global_conservation_credit=False,
        ),
    )


@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_original_molecule_failure(tmp_path, case):
    raw = fixtures.fixture(case)
    archive(tmp_path, case + "-inputs-before-setup", raw)
    binding = dispatch.bind(raw)
    setup = []

    def setup_observer(role, stage, value):
        archive(tmp_path, case + "-setup-" + role + "-" + stage, value)
        if role == "all":
            setup.append(isolated(root(tmp_path) / (case + "-native-setup"), value))

    parent = failure_checks.retained_call(
        lambda: dispatch.initialize(binding, observer=setup_observer),
        stage="raw_baseline_initialize",
        readers=dict(inputs=lambda: raw, native=lambda: setup),
        retain=lambda value: archive(tmp_path, case + "-baseline-outcome", value),
    )
    assert len(setup) == 1 and setup[0]["status"] == "source_completed"
    captured = []

    def observe(role, stage, value):
        archive(tmp_path, case + "-" + role + "-" + stage, value)
        if role == "all":
            captured.append(isolated(root(tmp_path) / (case + "-native-dispatch"), value))

    parent_digest = ions.digest(parent)
    with pytest.raises(dispatch.DispatchRejected) as caught:
        failure_checks.retained_call(
            lambda: dispatch.advance(binding, parent, handler_observer=observe),
            stage="raw_molecule_dispatch",
            readers=dict(inputs=lambda: raw, parent=lambda: parent, native=lambda: captured),
            retain=lambda value: archive(tmp_path, case + "-dispatch-outcome", value),
        )
    archive(
        tmp_path,
        case + "-original-failure",
        dict(parent=parent, partial=caught.value.partial, native=captured),
    )
    assert ions.digest(parent) == parent_digest and parent.cursor == 0
    assert len(captured) == 1
    failure_checks.assert_molecule_refusal(
        case,
        caught.value,
        captured[0],
        ions.data(caught.value.partial),
        ions.data(parent),
        exact=exact,
        transport=False,
        ion_ids=raw["field"]["definition"]["environment_geometry_definition"]["current_definition"][
            "ions"
        ]["ids"],
    )


@pytest.mark.parametrize("case", fixtures.DEPENDENCIES)
def test_two_owner_dependency(tmp_path, case):
    raw = fixtures.fixture(case)
    conf = raw["configuration"]
    flags = raw["flags"]
    changes = {
        "absent_general_network": lambda: conf.update({"general network": None}),
        "missing_implement_flag": lambda: conf["general network"].pop("implement network"),
        "foreign_implement_flag": lambda: conf["general network"].update({"implement network": 1}),
        "GRN_flag_missing": lambda: conf["gene regulatory network settings"].clear(),
        "GRN_flag_not_bool": lambda: conf["gene regulatory network settings"].update(
            {"gene regulatory network simulated": 1}
        ),
        "enabled_ER": lambda: flags.update(Ca_dyn=True),
        "enabled_flow": lambda: flags.update(fluid_flow=True),
        "FAST": lambda: flags.update(solver="FAST"),
        "noise_requires_owner": lambda: flags.update(dynamic_noise=1),
        "osmotic_requires_both_owners": lambda: flags.update(deform_osmo=True),
        "foreign_general_config": lambda: conf["general network"].update(
            {"time dilation factor": 99.0}
        ),
        "foreign_profile_owner": lambda: raw["handlers"]["molecules"]["catalog"][
            "tissue_profiles"
        ].update(foreign=[0]),
        "missing_shared_charge": lambda: raw["shared_initial"].pop("extra_rho_cells"),
    }
    if case in changes:
        changes[case]()
        archive(tmp_path, case + "-poisoned-input", raw)
        with pytest.raises(ValueError):
            dispatch.bind(raw)
        return
    if case == "fabricated_disabled_owner":
        raw["configuration"]["general network"]["implement network"] = False
    archive(tmp_path, case + "-baseline-inputs", raw)
    binding = dispatch.bind(raw)
    parent = failure_checks.retained_call(
        lambda: dispatch.initialize(binding),
        stage="dependency_baseline_initialize",
        readers=dict(inputs=lambda: raw),
        retain=lambda value: archive(tmp_path, case + "-baseline-outcome", value),
    )
    owners = ions.data(parent.owners)
    field = parent.field
    rate = parent.rate_cache
    if case == "foreign_general_cache_role":
        owners["handlers"]["molecules"]["role"] = "grn"
    elif case == "swapped_handler_caches":
        owners["handlers"]["molecules"], owners["handlers"]["grn"] = (
            owners["handlers"]["grn"],
            owners["handlers"]["molecules"],
        )
    elif case == "missing_general_cache":
        owners["handlers"]["molecules"] = None
    elif case == "fabricated_disabled_owner":
        owners["handlers"]["molecules"] = copy.deepcopy(owners["handlers"]["grn"])
    elif case == "changed_publication_projection":
        owners["wire"]["simulator_fields"]["extra_rho_cells"][0] += 1.0
    elif case == "changed_shared_epoch":
        owners["wire"]["simulator_fields"]["extra_rho_cells"][0] += 1.0
        owners["shared"]["extra_rho_cells"][0] += 1.0
    elif case == "changed_field_owner":
        field = dispatch.full.FieldStage(
            "foreign", field.before, field.current, field.environment, field.voltage, ""
        )
        from dataclasses import replace

        field = replace(field, identity=ions.digest(dispatch.full.field_record(field)))
    elif case == "changed_Ca_cache":
        rate = dispatch.calcium.RateCache(
            True, ions.freeze(np.zeros_like(parent.material.values.voltage_V))
        )
    changed = dispatch.state(
        binding, parent.material, field, owners, parent.controls, rate, parent.clock
    )
    archive(tmp_path, case + "-poisoned-state", changed)
    with pytest.raises(ValueError):
        dispatch.verify(binding, changed)
