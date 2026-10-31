# ruff: noqa: E731
"""Prospective ordinary INIT qualification; no collection/execution during preparation."""

import copy
import json
import os
import subprocess
import sys
import traceback
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_init_phase as joined
from cells.processes import betse_normal_ion_join as ions
from tests.unit import test_betse_normal_ecm_catalog_join as catalog
from tests.unit import test_betse_normal_ecm_event_mechanics as common
from tests.unit.test_betse_fast_solver import archive_read
from validation.betse import betse_normal_ecm_init_phase_capture as capture_evidence
from validation.betse import betse_normal_ecm_init_phase_fixtures as fixtures
from validation.betse import betse_normal_ecm_init_phase_native as native

base, exact = catalog.base, catalog.exact
MODES = ("nak", "material", "calcium", "channels", "network", "mechanics", "field")


@pytest.fixture(autouse=True)
def explicit_release():
    if os.environ.get("CELLS_INIT_PHASE_RELEASED") != "1":
        pytest.skip("Held source preparation; Chief must explicitly release this independent suite")


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "normal-ecm-init-phase"


def archive(tmp_path, name, value):
    return native.archives.write_archive(root(tmp_path) / name, ions.data(value))


def references(folder, inputs):
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(
        json.dumps(fixtures.events.plain(ions.data(inputs)), indent=2, allow_nan=False) + "\n"
    )
    answers = []
    for level in (1, 2):
        output = folder / ("reference-" + str(level) + ".json")
        with (folder / ("reference-" + str(level) + ".stdout.log")).open("x") as stream:
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "validation.betse.betse_normal_ecm_init_phase_reference",
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
        answer = json.loads(output.read_text())
        assert answer["production_imports_denied"] and not answer["loaded_production_modules"]
        assert answer["decimal_precision"] == (100 if level == 1 else 160)
        assert answer["carried_reference_forms"] == 0 and answer["source_phase"] == "INIT"
        answers.append(answer)
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
                "validation.betse.betse_normal_ecm_init_phase_native",
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
    captured = archive_read(folder / "native")
    # The CLI writes full raw source return before these runtime assertions.
    archive(tmp_path, inputs["case_id"] + "-native-return-before-assertions", captured)
    assert captured["production_imports_denied"] and not captured["loaded_production_modules"]
    assert captured["RNG_unchanged"] and captured["Python_RNG_unchanged"]
    return folder, captured


def check(tmp_path, name, folder, rows):
    archive(tmp_path, name, dict(fields=rows, physical_global_conservation_credit=False))
    report = dict(
        fields={k: v["metric"] for k, v in rows.items()},
        resolutions={k: v["resolution"] for k, v in rows.items()},
        fresh_conditional_reference=True,
        carried_reference_forms=0,
    )
    (folder / "comparison.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    assert rows and max(v["normalized_max_error"] for v in report["fields"].values()) <= 1
    assert max(v["normalized_max_error"] for v in report["resolutions"].values()) <= 0.1


def compare_sampling(binding, parent, captured, cold_forms, accepted_states):
    """Compare eligibility independently and compare every complete selected payload."""
    labels = captured["source_times_s"].tolist()
    native_flags = fixtures.events.plain(captured["source_calendar"]["sampled"])
    references = [row["sample_indices"] for row in cold_forms]
    result = capture_evidence.sampling_contract(
        source_labels=labels,
        native_flags=native_flags,
        reference_indices=references,
        native_rows=fixtures.events.plain(captured["sample_states"][: parent.cursor]),
        owned_rows=fixtures.events.plain(ions.data(parent.history)),
        observation_indices=[row["call_index"] for row in parent.observations],
        completed_calls=parent.cursor,
    )
    for form in cold_forms:
        np.testing.assert_array_equal(form["clock"]["source_times_s"], captured["source_times_s"])
    for observation in parent.observations:
        index = observation["call_index"]
        accepted = accepted_states[index]
        source = captured["history"][index]
        np.testing.assert_array_equal(observation["source_label_s"], labels[index])
        exact(ions.data(observation["network"]), ions.data(accepted.network))
        exact(ions.data(observation["field"]), ions.data(accepted.field))
        exact(ions.data(observation["mechanics"]), ions.data(accepted.mechanics))
        exact(observation["network"].material.values._asdict(), source["candidate"])
        exact(observation["network"].network_cache, source["post_material_cache"])
        exact(observation["mechanics"].cache, captured["mechanics_history"][index]["candidate"])
        for section, value in base.field_output(observation["field"]).items():
            exact(value, source["field"][section])
        assert (
            observation["native_storage_called"] is False
            and observation["display_completed"] is False
        )
    return result


def setup_rows(actual, lower, target):
    rows, add = base.legacy.comparisons()
    for key in ("Dm_base", "Dm_scheduled", "Dm_cells", "channel_noise_factor"):
        wanted = np.asarray(target[key])
        # Existing ECM diffusion budget, and existing bounded scalar/gate floor.
        floor = 3e-14 if key == "channel_noise_factor" else 3e-20
        add(
            key,
            actual["stores"][key],
            wanted,
            lower[key],
            floor + 6e-12 * abs(wanted),
            "unchanged component budget",
        )
    return rows


def nak_rows(actual, lower, target):
    rows, add = base.legacy.comparisons()
    for key in ("applied_flux", "raw_rate_proxy"):
        wanted = np.asarray(target[key])
        add(
            key,
            actual[key],
            wanted,
            lower[key],
            2e-18 + 2e-11 * abs(wanted),
            "existing maintained-pump preflight budget",
        )
    return rows


def material_rows(trial, lower, target):
    # The added INIT receipt repeats the same post-network primary buffers.
    # Native correspondence checks it in full; the common material comparator
    # sees its original unmodified columns and exclusions.
    projected = SimpleNamespace(
        frames=[f for f in trial.frames if f.stage != "INIT_post_network"],
        environment_records=trial.environment_records,
        candidate=trial.candidate,
        diagnostics=trial.diagnostics,
    )
    return base.compare_material(projected, lower, target)


@pytest.mark.parametrize("case", fixtures.CASES)
def test_init_history(tmp_path, case):
    inputs = fixtures.fixture(case)
    archive(tmp_path, case + "-inputs-before-any-evaluation", inputs)
    # Complete native source result is archived before any model/reference
    # correspondence assertion; later failures cannot discard reached buffers.
    folder, captured = isolated(tmp_path, inputs)
    prep = root(tmp_path) / ("preparation-" + case)
    prep.mkdir(parents=True, exist_ok=False)
    entry, answers = {}, {}

    def after_setup(value):
        archive(tmp_path, case + "-setup-return-before-cold", value)
        entry["setup"] = value
        ids = inputs["field"]["definition"]["environment_geometry_definition"][
            "current_definition"
        ]["ions"]["ids"]
        answers["setup"] = references(
            prep / "setup", dict(mode="setup", setup_return=value, ion_ids=ids)
        )
        effective = copy.deepcopy(inputs["field"])
        effective["definition"]["ions"]["membrane_diffusion_m2_s"] = value["stores"]["Dm_cells"]
        cold_input = base.cold_inputs(effective)
        cold_input.update(
            catalog=inputs["catalog"],
            calcium_configuration=inputs["calcium"],
            bootstrap_dt_s=effective["bootstrap"]["dt_s"],
            time_profile=inputs["time_profile"],
        )
        answers["cold"] = references(prep / "cold", cold_input)

    def after_cold(value):
        archive(tmp_path, case + "-cold-return-before-finalization", value)
        entry["cold"] = value

    def bootstrap(value):
        archive(tmp_path, case + "-bootstrap-input", value)
        answers["bootstrap"] = references(prep / "bootstrap", value)

    try:
        binding, parent = joined.initialize(
            joined.bind(inputs),
            after_setup=after_setup,
            after_cold=after_cold,
            before_field=bootstrap,
        )
        archive(
            tmp_path,
            case + "-initialized-return-before-comparison",
            dict(binding=binding, parent=parent),
        )
    except Exception as error:
        archive(
            tmp_path,
            case + "-initialization-failure",
            dict(
                inputs=inputs,
                entry=entry,
                error=str(error),
                traceback=traceback.format_exc(),
                partial=getattr(error, "partial", None),
            ),
        )
        raise
    exact(entry["setup"], captured["setup_pre"])
    exact(binding.setup_receipt["event_finalization"], captured["event_finalization"])
    cold = entry["cold"]
    exact(cold["network_cache"], captured["cold_cache"])
    exact(cold["material"], captured["cold_material"])
    exact(cold["policy"], captured["cold_policy"])
    exact(cold["trace"], captured["cold_trace"])
    assert cold["source_phase"] == "INIT" and cold["legacy_run_sim"] is False
    cold_view = dict(
        network=SimpleNamespace(network_cache=cold["network_cache"]),
        policy=cold["policy"],
        clock=cold["clock"],
        rate_cache=cold["rate_cache"],
    )
    check(
        tmp_path,
        case + "-setup-errors",
        prep / "setup",
        setup_rows(entry["setup"], *answers["setup"]),
    )
    check(
        tmp_path,
        case + "-cold-errors",
        prep / "cold",
        catalog.compare_cold(binding, cold_view, *answers["cold"]),
    )
    check(
        tmp_path,
        case + "-bootstrap-errors",
        prep / "bootstrap",
        base.compare_field(binding, parent.field, *answers["bootstrap"]),
    )
    exact(parent.network.material.values._asdict(), captured["bootstrap"]["candidate"])
    np.testing.assert_array_equal(parent.clock.source_times_s, captured["source_times_s"])
    accepted_states = {}
    compare_sampling(binding, parent, captured, answers["cold"], accepted_states)
    initial_setup_identity = ions.digest(binding.setup_receipt)
    assert (
        captured["status"] == "source_completed"
        and len(captured["history"]) == inputs["stop_after_calls"]
    )
    for index, native_call in enumerate(captured["history"]):
        point = prep / ("point-" + str(index))
        point.mkdir()
        observed, forms = {}, {mode: [] for mode in MODES}

        def before(mode, index=index, observed=observed, forms=forms, point=point):
            def callback(incoming):
                archive(
                    tmp_path,
                    case + "-call-" + str(index) + "-" + mode + "-input-before-reference",
                    incoming,
                )
                observed[mode] = ions.data(incoming)
                forms[mode].extend(references(point / mode, incoming))

            return callback

        previous_digest = ions.digest(parent)
        try:
            candidate, returns = joined.run_window(
                binding,
                parent,
                stop=index + 1,
                before_nak=before("nak"),
                before_material=before("material"),
                before_calcium=before("calcium"),
                before_channels=before("channels"),
                before_network=before("network"),
                before_mechanics=before("mechanics"),
                before_field=before("field"),
            )
            details = returns[0]
            archive(
                tmp_path,
                case + "-call-" + str(index) + "-full-return-before-comparison",
                dict(parent=parent, candidate=candidate, details=details),
            )
        except Exception as error:
            archive(
                tmp_path,
                case + "-call-" + str(index) + "-failure",
                dict(
                    parent=parent,
                    observed=observed,
                    error=str(error),
                    traceback=traceback.format_exc(),
                    partial=getattr(error, "partial", None),
                ),
            )
            raise
        assert (
            previous_digest == ions.digest(parent)
            and ions.digest(binding.setup_receipt) == initial_setup_identity
        )
        assert all(len(value) == 2 for value in forms.values())
        exact(details["nak"], native_call["nak"])
        exact(observed["material"], native_call["material_before"])
        exact(observed["calcium"], native_call["calcium"]["before"])
        exact(observed["channels"], native_call["network"]["before_channels"])
        exact(observed["network"], native_call["network"]["before"])
        exact(observed["field"], native_call["field"]["before"])
        base.compare_native_material(details["material_trial"], native_call)
        exact(details["network"], native_call["network"])
        catalog.compare_calcium_native(details["calcium"], native_call["calcium"])
        mechanical = captured["mechanics_history"][index]
        exact(observed["mechanics"]["steps"][0], mechanical["before"])
        exact(candidate.mechanics.cache, mechanical["candidate"])
        exact(candidate.network.material.values._asdict(), native_call["candidate"])
        exact(candidate.network.network_cache, native_call["post_material_cache"])
        exact(candidate.stores, native_call["phase_stores_after"])
        exact(ions.data(candidate.rate_cache), native_call["rate_cache_after"])
        exact(ions.data(candidate.clock), native_call["clock_after"])
        for section, value in base.field_output(candidate.field).items():
            exact(value, native_call["field"][section])
        for row in inputs["catalog"]["populations"] or []:
            name = row["name"]
            count = index + 1 if row.get("init active", True) else 0
            assert candidate.network.network_cache["channel_calls"][name] == count
            if not row.get("init active", True):
                exact(
                    candidate.network.network_cache["wire"]["channel_fields"][name],
                    cold["network_cache"]["initial_channel_fields"][name],
                )
        comparisons = (
            ("nak", nak_rows(details["nak"], *forms["nak"])),
            ("material", material_rows(details["material_trial"], *forms["material"])),
            ("calcium", catalog.compare_calcium(details["calcium"], *forms["calcium"])),
            ("channels", catalog.compare_channels(binding, details["network"], *forms["channels"])),
            ("network", base.legacy.compare_local(details["network"], *forms["network"])),
            (
                "mechanics",
                common.mechanical_rows(details["mechanics_trial"], mechanical, *forms["mechanics"]),
            ),
            ("field", base.compare_field(binding, candidate.field, *forms["field"])),
        )
        for mode, rows in comparisons:
            check(tmp_path, case + "-" + str(index) + "-" + mode + "-errors", point / mode, rows)
        assert candidate.cursor == candidate.mechanics.step_index == index + 1
        assert (
            candidate.history[-1]["event_fire_calls"]
            == candidate.history[-1]["protein_noise_calls"]
            == 0
        )
        accepted_states[index] = candidate
        compare_sampling(binding, candidate, captured, answers["cold"], accepted_states)
        parent = candidate
    assert parent.cursor == fixtures.expected_calls(case)
    assert parent.status == (
        "exhausted" if parent.cursor == binding.calendar.step_count else "capped"
    )
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                completed=True,
                source_phase="INIT",
                original_step_count=binding.calendar.step_count,
                complete_calls=parent.cursor,
                independent_reference_forms=6 + 14 * parent.cursor,
                carried_reference_forms=0,
                native_storage_called=False,
                display_completed=False,
                whole_physical_initializer_credit=False,
                inherited_passes=0,
            ),
            indent=2,
        )
        + "\n"
    )


RAW_EXPECTATIONS = {
    "negative_static_Dm": ("effective_static_diffusion_guard", "membrane diffusion"),
    "NaK_nonfinite": ("nak", "Nonfinite complete ordinary INIT NaK output"),
    "CaATP_nonfinite": (
        "material_calcium_network_mechanics",
        "Nonfinite literal native ECM material trial",
    ),
    "GRN_negative": ("material_calcium_network_mechanics", "Network concentration of"),
    "mechanics_nonfinite": (
        "material_calcium_network_mechanics",
        "Nonfinite complete mechanics output",
    ),
}


@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_init_raw_refusal(tmp_path, case):
    inputs = fixtures.raw_fixture(case)
    archive(tmp_path, case + "-raw-inputs", inputs)
    _, captured = isolated(tmp_path, inputs)
    parent, observed = None, {}

    def before(mode):
        def callback(value):
            observed[mode] = value
            archive(tmp_path, case + "-raw-" + mode + "-before-first-call", value)

        return callback

    with pytest.raises(joined.InitRejected) as caught:
        try:
            binding, parent = joined.initialize(
                joined.bind(inputs),
                after_setup=before("setup"),
                after_cold=before("cold"),
                before_field=before("bootstrap"),
            )
            joined.advance(
                binding,
                parent,
                before_nak=before("nak"),
                before_material=before("material"),
                before_calcium=before("calcium"),
                before_network=before("network"),
                before_mechanics=before("mechanics"),
            )
        except Exception as error:
            archive(
                tmp_path,
                case + "-raw-failure-before-assertions",
                dict(
                    parent=parent,
                    observed=observed,
                    error=str(error),
                    traceback=traceback.format_exc(),
                    partial=getattr(error, "partial", None),
                    native=captured,
                ),
            )
            raise
    error = caught.value
    stage, cause = RAW_EXPECTATIONS[case]
    assert error.partial["stage"] == stage and cause in str(error)
    if case == "negative_static_Dm":
        exact(error.partial["setup_receipt"], captured["setup_pre"])
        assert "cold" not in observed and np.any(
            np.asarray(observed["setup"]["stores"]["Dm_cells"]) < 0
        )
    else:
        assert parent is not None and parent.cursor == 0
        assert (
            error.partial["call_index"] == 0 and error.partial["parent"].identity == parent.identity
        )
        if case in ("NaK_nonfinite", "GRN_negative"):
            assert "mechanics" not in observed
        if case == "NaK_nonfinite":
            exact(error.partial["available"]["nak"], captured["history"][0]["nak"])
            assert not joined.pump.finite(error.partial["available"]["nak"])
        elif case == "CaATP_nonfinite":
            # Native commits the same nonfinite call-0 material and clips only
            # bulk Ca; this adapter must reject that whole trial before field
            # or acceptance. Native's subsequent call-1 Ca refusal is distinct.
            available = error.partial["available"]
            material = available["material_partial"]
            trial = material["trial"]
            assert error.partial["reached_stage"] == "mechanics"
            assert material["failure"] is None and not material["diagnostics"]["finite"]
            assert not parent.history and not parent.observations
            assert not {"material_trial", "material_candidate", "field", "accepted"} & set(
                available
            )
            assert error.partial["capture_errors"] == ()
            assert len(captured["history"]) == len(captured["calcium_rows"]) == 2
            first, later = captured["history"]
            assert first["source_completed"] is True and later["source_completed"] is False
            assert captured["failure"]["stage"] == "calcium"
            assert captured["failure"]["type"] == "BetseSimUnstableException"
            assert "no_negs" in captured["failure"]["traceback"]
            initial_ca, later_ca = captured["calcium_rows"]
            assert initial_ca["before"]["clock"]["call_index"] == 0
            assert later_ca["before"]["clock"]["call_index"] == 1
            assert initial_ca["helper_returned"] and initial_ca["source_completed"]
            assert initial_ca["helper"]["finite"] is True
            assert not later_ca["helper_returned"] and later_ca["source_exception_observed"]
            assert not later_ca["source_completed"] and not later_ca["helper"]["finite"]
            exact(available["calcium"]["helper"], initial_ca["helper"])

            def same_array(actual, expected):
                actual, expected = np.asarray(actual), np.asarray(expected)
                assert actual.dtype == expected.dtype and actual.shape == expected.shape
                assert actual.tobytes(order="C") == expected.tobytes(order="C")

            assert len(trial.frames) == len(material["frames"]) == len(first["frames"]) == 47
            for actual, raw, expected in zip(
                trial.frames, material["frames"], first["frames"], strict=True
            ):
                assert (actual.stage, actual.ion_id) == raw[:2] == (
                    expected["stage"], expected["ion_id"]
                )
                assert len(actual.values) == 12 and set(actual.values._fields) == set(
                    expected["values"]
                )
                for name, value, raw_value in zip(
                    actual.values._fields, actual.values, raw[2], strict=True
                ):
                    same_array(value, raw_value)
                    same_array(value, expected["values"][name])
            assert len(trial.environment_records) == len(first["environment_records"]) == 5
            for actual, expected in zip(
                trial.environment_records, first["environment_records"], strict=True
            ):
                assert actual.ion_id == expected["ion_id"]
                assert set(actual._fields) == set(expected)
                for name in actual._fields[1:]:
                    same_array(getattr(actual, name), expected[name])
            assert set(trial.candidate.values._fields) == set(first["material_candidate"])
            for name, value in trial.candidate.values._asdict().items():
                same_array(value, first["material_candidate"][name])
            nonfinite = [
                index
                for index, frame in enumerate(trial.frames)
                if any(not np.isfinite(value).all() for value in frame.values)
            ]
            assert nonfinite[0] == 41
            first_bad = trial.frames[41]
            assert (first_bad.stage, first_bad.ion_id) == ("membrane_commit", "Ca")
            calcium_index = inputs["field"]["definition"]["environment_geometry_definition"][
                "current_definition"
            ]["ions"]["ids"].index("Ca")
            assert np.isneginf(first_bad.values.cell_mol_m3[calcium_index]).all()
            assert np.isneginf(first_bad.values.membrane_mol_m3[calcium_index]).all()
            assert np.all(trial.candidate.values.cell_mol_m3[calcium_index] == 0)
            assert np.isneginf(trial.candidate.values.membrane_mol_m3[calcium_index]).all()
        elif case == "GRN_negative":
            assert (
                captured["failure"] is not None
                and "Network concentration of" in captured["failure"]["message"]
            )
        elif case == "mechanics_nonfinite":
            assert error.partial["available"]["mechanics_failure"] is not None
            assert error.partial["reached_stage"] == "mechanics"


@pytest.mark.parametrize("when", fixtures.OBSERVER_CASES)
def test_init_observer_retention(tmp_path, when):
    inputs = fixtures.fixture("active")
    inputs["case_id"] = "observer-" + when
    _, captured = isolated(tmp_path, inputs)
    binding, parent = joined.initialize(joined.bind(inputs))
    cause = "INIT observer exact cause at " + when

    def observer(stage, value):
        archive(tmp_path, when + "-call-0-observer-" + stage, value)
        if stage == when:
            raise RuntimeError(cause)

    with pytest.raises(joined.InitRejected) as caught:
        try:
            joined.advance(binding, parent, observer=observer)
        except Exception as error:
            archive(
                tmp_path,
                when + "-call-0-retained-exception",
                dict(
                    parent=parent,
                    partial=getattr(error, "partial", None),
                    traceback=traceback.format_exc(),
                ),
            )
            raise
    error = caught.value
    assert str(error) == cause and error.partial["root_cause"] == dict(
        type="RuntimeError", message=cause
    )
    assert error.partial["stage"] == when + "_observer" and parent.cursor == 0
    if when == "after_call":
        accepted = error.partial["available"]["accepted"]
        assert accepted.cursor == 1
        exact(accepted.network.material.values._asdict(), captured["history"][0]["candidate"])
    else:
        assert not error.partial["available"]


@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)
def test_init_dependency_refusal(tmp_path, dependency):
    inputs = fixtures.fixture("inactive_dynamic_gate")
    inputs["case_id"] = dependency
    flags = {
        "legacy_run_sim": "_run_sim",
        "enabled_ER": "Ca_dyn",
        "enabled_flow": "fluid_flow",
        "dynamic_deformation": "td_deform",
        "electroosmosis": "sim_eosmosis",
        "general_molecules": "molecules_enabled",
        "physical_initializer": "physical_initialization",
        "cut_requested": "cut_requested",
    }
    stage = "bind"
    expected = ""
    action = None
    if dependency in flags:
        key = flags[dependency]
        inputs["flags"][key] = True
        expected = "Unsupported INIT scope flag: " + key
    elif dependency == "SIM_phase":
        inputs["time_profile"]["phase"] = "SIM"
        expected = "INIT cannot reuse a SIM phase profile"
    elif dependency == "GRN_off_unqualified":
        inputs["flags"]["grn_enabled"] = False
        expected = "Unsupported INIT scope flag: grn_enabled"
    elif dependency == "FAST_solver":
        inputs["flags"]["solver"] = "FAST"
        expected = "Unsupported INIT scope flag: solver"
    elif dependency == "missing_setup_receipt":
        inputs["setup"]["receipts"].pop("init_core")
        expected = "Declare supplied tissue, core and conditional initializer-cache seams"
    elif dependency == "missing_numpy_Gaussian_cache":
        inputs["setup"]["numpy_rng"]["state"].pop()
        expected = "Require complete MT19937"
    elif dependency == "wrong_numpy_version":
        inputs["setup"]["numpy_rng"]["numpy_version"] = "unqualified"
        expected = "Native replay requires the recorded NumPy version"
    elif dependency == "wrong_python_version":
        inputs["setup"]["python_rng"]["python_version"] = [0, 0, 0]
        expected = "Python shuffle law/version/state identity differs"
    elif dependency == "foreign_tissue_map":
        inputs["setup"]["maps"]["tissue_target_inds"]["all"] = [0]
        expected = "Cold catalog and setup finalizer must share the supplied tissue maps"
    elif dependency == "wrong_dt":
        inputs["time_profile"]["init_dt_s"] *= 2
        inputs["time_profile"]["init_total_s"] *= 2
        inputs["time_profile"]["init_sampling_s"] *= 2
        expected = "Require the same native phase dt for events, material and mechanics"
    elif dependency in ("nonzero_supplied_pump", "nonzero_late_flux"):
        key = (
            "supplied_pump_membrane_flux_mol_m2_s"
            if dependency == "nonzero_supplied_pump"
            else "supplied_late_membrane_flux_mol_m2_s"
        )
        inputs["field"]["steps"][0]["material"][key][0][0] = 1e-8
        expected = "Require actual NaK/CaATP/GRN producers"
    elif dependency == "nonzero_flow":
        inputs["field"]["steps"][0]["material"]["velocity_x_m_s"][0][0] = 1e-8
        expected = "Disabled fluid needs shared held-zero velocity stores"
    elif dependency == "display_enabled":
        inputs["mechanics_definition"]["policy"]["display_regime"] = "global_quartic_conditional"
        expected = "Keep native display held on the existing field domain"
    elif dependency == "nonprogressing_sampling":
        inputs["time_profile"]["init_sampling_s"] = 0.5 * inputs["time_profile"]["init_dt_s"]
        expected = "Native sampling stride below one does not progress"
    else:
        stage = "parent"
        binding, parent = joined.initialize(joined.bind(inputs))
        archive(tmp_path, dependency + "-unmodified-parent", dict(binding=binding, parent=parent))
        net, fields, rate, mech, stores, clock = (
            parent.network,
            parent.field,
            parent.rate_cache,
            parent.mechanics,
            ions.data(parent.stores),
            parent.clock,
        )
        if dependency == "foreign_parent":
            action = lambda: joined.verify(binding, SimpleNamespace(cursor=0))
            expected = "Require the unchanged complete INIT parent"
        elif dependency == "changed_clock":
            clock = joined.Clock(ions.freeze(parent.clock.source_times_s + 1e-9), 0, 0.0)
            expected = "Require the complete original INIT calendar without rebasing"
        elif dependency == "rebound_count":
            calendar = joined.calendars.bind(
                phase="INIT",
                step_count=4,
                dt_s=binding.calendar.dt_s,
                provenance="foreign rebased calendar",
            )
            changed = replace(binding, calendar=calendar, identity="")
            changed = replace(changed, identity=ions.digest(joined.binding_record(changed)))
            action = lambda: joined.verify(changed, parent)
            expected = "Changed original INIT phase declaration or calendar"
        elif dependency in ("inactive_count_forgery", "inactive_cold_gate_forgery"):
            cache = copy.deepcopy(ions.data(net.network_cache))
            name = inputs["catalog"]["populations"][0]["name"]
            if dependency == "inactive_count_forgery":
                cache["channel_calls"][name] = 1
                expected = "INIT channel count differs from its active flag and source epoch"
            else:
                fields_now = cache["wire"]["channel_fields"][name]["core_fields"]
                fields_now["m"] = np.asarray(fields_now["m"]) + 0.125
                expected = "INIT-inactive population must retain its complete cold private state"
            net = joined.network._state(binding, net.material, cache, net.controls)
        elif dependency == "changed_setup_store":
            stores["channel_noise_factor"] = np.asarray(stores["channel_noise_factor"]) + 0.125
            expected = "Changed INIT phase setup store: channel_noise_factor"
        elif dependency == "changed_rate_presence":
            rate = joined.RateCache(True, ions.freeze(np.zeros_like(parent.stores["CaATP_block"])))
            expected = "INIT rate-cache presence differs from the actual producer epoch"
        elif dependency == "changed_previous_field":
            fields = replace(fields, identity="foreign")
            expected = "Require actual prior reconstructed full field"
        elif dependency == "changed_mechanics_parent":
            mech = replace(mech, step_index=1)
            expected = "INIT material, clock, mechanics and bounded prefix must share one cursor"
        elif dependency == "changed_phase_receipt":
            receipt = ions.data(binding.setup_receipt)
            receipt["event_finalization"]["legacy_run_sim"] = True
            changed = replace(binding, setup_receipt=ions.freeze(receipt), identity="")
            changed = replace(changed, identity=ions.digest(joined.binding_record(changed)))
            action = lambda: joined.verify(changed, parent)
            expected = "Changed source INIT setup phase receipt"
        elif dependency == "native_sample_refusal":
            action = lambda: joined.request_native_sample(binding, parent)
            expected = "Native display requires at least25 cells"
        else:
            raise AssertionError("Unimplemented declared INIT dependency control: " + dependency)
        if action is None:
            changed_parent = joined.state(
                binding,
                net,
                fields,
                rate,
                parent.nak_rate,
                mech,
                stores,
                clock,
                parent.history,
                parent.observations,
                parent.status,
            )
            action = lambda: joined.verify(binding, changed_parent)
    challenged = {
        name: value
        for name, value in locals().copy().items()
        if name in {"binding", "parent", "changed", "changed_parent"}
    }
    archive(
        tmp_path,
        dependency + "-rejected-inputs-before-check",
        dict(stage=stage, inputs=inputs, expected=expected, challenged=challenged),
    )
    if action is None:
        action = lambda: joined.bind(inputs)
    with pytest.raises((ValueError, joined.InitRejected)) as caught:
        try:
            action()
        except Exception as error:
            archive(
                tmp_path,
                dependency + "-exact-refusal",
                dict(
                    type=type(error).__name__,
                    cause=str(error),
                    partial=getattr(error, "partial", None),
                    traceback=traceback.format_exc(),
                ),
            )
            raise
    assert expected and expected in str(caught.value)
