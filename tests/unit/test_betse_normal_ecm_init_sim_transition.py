"""Held conditional INIT->SIM handoffs, fresh references and preserved refusals."""

import json
import os
import subprocess
import sys
import traceback
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_init_sim_transition as transition
from cells.processes import betse_normal_ion_join as ions
from tests.unit import test_betse_normal_ecm_event_mechanics as common
from tests.unit import test_betse_normal_ecm_init_phase as initialized
from tests.unit.test_betse_fast_solver import archive_read
from validation.betse import betse_normal_ecm_init_phase_capture as sampling
from validation.betse import betse_normal_ecm_init_sim_transition_fixtures as fixtures
from validation.betse import betse_normal_ecm_run_lifecycle_compare as comparison
from validation.betse import betse_normal_grn_join_native as archives

MODES = ("nak", *common.MODES)
base, exact, lifecycle = common.base, common.exact, transition.lifecycle


@pytest.fixture(autouse=True)
def explicit_release():
    if os.environ.get("CELLS_INIT_SIM_TRANSITION_RELEASED") != "1":
        pytest.skip("Held transition source preparation; Chief must explicitly release this suite")


def root(tmp_path):
    return (
        Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path)))
        / "normal-ecm-init-sim-transition"
    )


def archive(tmp_path, name, value):
    return archives.write_archive(root(tmp_path) / name, ions.data(value))


def references(folder, inputs):
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(
        json.dumps(
            fixtures.initialization.events.plain(ions.data(inputs)),
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )
    result = []
    for level in (1, 2):
        output = folder / ("reference-" + str(level) + ".json")
        with (folder / ("reference-" + str(level) + ".stdout.log")).open("x") as stream:
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "validation.betse.betse_normal_ecm_init_sim_transition_reference",
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
        value = json.loads(output.read_text())
        assert value["production_imports_denied"] and not value["loaded_production_modules"]
        assert value["carried_reference_forms"] == 0
        assert value["decimal_precision"] == (100 if level == 1 else 160)
        assert value["source_phase"] == "SIM" and value["legacy_run_sim"] is True
        assert value["runtime"]["measured_cpu_affinity"] == sorted(os.sched_getaffinity(0))
        result.append(value)
    return result


def isolated(tmp_path, case, inputs, *, sim=False):
    folder = root(tmp_path) / (("SIM-native-" if sim else "reinitialize-native-") + case)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(
        json.dumps(
            fixtures.initialization.events.plain(ions.data(inputs)),
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )
    module = "validation.betse.betse_normal_ecm_init_sim_transition_native" + (
        "_sim" if sim else ""
    )
    with (folder / "native.stdout.log").open("x") as stream:
        subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                module,
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
    assert captured["production_imports_denied"] and not captured["loaded_production_modules"]
    return captured


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
    assert rows and max(r["normalized_max_error"] for r in report["fields"].values()) <= 1
    assert max(r["normalized_max_error"] for r in report["resolutions"].values()) <= 0.1


def supplied_init(tmp_path, case, *, stop=None):
    """Prepare an owned INIT input and retain any failure without granting INIT credit."""
    raw = declaration = binding = parent = details = None
    stage = "fixture"
    try:
        raw = fixtures.init_fixture(case)
        stage = "declaration_archive"
        archive(tmp_path, case + "-INIT-declaration-input", raw)
        stage = "bind"
        declaration = transition.init.bind(raw)
        stage = "initialize"
        binding, parent = transition.init.initialize(declaration)
        stage = "entry_archive"
        archive(tmp_path, case + "-INIT-entry", dict(binding=binding, parent=parent))
        while parent.status == "ready" and (stop is None or parent.cursor < stop):
            stage = "advance-" + str(parent.cursor)
            details = None
            parent, details = transition.init.advance(binding, parent)
            stage = "return_archive-" + str(parent.cursor)
            archive(
                tmp_path,
                case + "-INIT-return-" + str(parent.cursor),
                dict(parent=parent, details=details),
            )
        return binding, parent
    except Exception as error:
        sampling.record_failure(
            error,
            stage=stage,
            readers=dict(
                requested_case=lambda: case,
                stop=lambda: stop,
                raw=lambda: raw,
                declaration=lambda: declaration,
                binding=lambda: binding,
                parent=lambda: parent,
                details=lambda: details,
                partial=lambda original_error=error: getattr(original_error, "partial", None),
            ),
            retain=lambda payload: archive(tmp_path, case + "-INIT-failure", payload),
        )
        raise


def complete_init(tmp_path, case):
    binding, parent = supplied_init(tmp_path, case)
    complete = transition.prepare_complete(binding, parent)
    archive(tmp_path, case + "-complete-headless-INIT", complete)
    return complete


def phase_rules_input(raw, completed, reached):
    parent = completed.parent
    fields = reached["before_GRN_reinitialize"]["cells_fields"]
    names = completed.binding.material_binding.geometry_binding.current_binding.ion_ids
    return dict(
        mode="phase_rules",
        setup=raw["source_setup"],
        incoming=dict(
            membrane_diffusion_m2_s=parent.stores["Dm_cells"],
            D_free=parent.stores["D_free"],
            P_cells=parent.stores["P_cells"],
            mechanics=parent.mechanics.cache,
            rate_CaATP=parent.rate_cache,
            rate_NaKATP=parent.nak_rate,
        ),
        ion_ids=list(names),
        actual_static_uniforms=reached["post_static"]["channel_noise_factor"],
        environment_sites=len(parent.network.material.values.environment_mol_m3[0]),
        grid_index_groups={
            key: fields[key]["__transition_ndarray__"]
            for key in ("all_bound_mem_inds", "interior_bound_mem_inds", "ecm_inds_bound_cell")
        },
        cells=len(parent.network.material.values.cell_mol_m3[0]),
        mechanics_policy=raw["sim_composition_template"]["mechanics_definition"]["policy"],
        time_profile=raw["time_profile"],
        SIM_total_s=raw["time_profile"]["sim_total_s"],
        source_f_sweep_configured=any(
            isinstance(row, list) and row[5] == "f_sweep"
            for row in raw["sim_composition_template"]["event_inputs"]["event_owner"][
                "scheduled_options"
            ].values()
        ),
        INIT_call_count=parent.cursor,
    )


def phase_rows(reached, lower, target):
    actual = reached["post_static"]["available"]["simulator_fields"]
    rows, add = base.legacy.comparisons()
    for key in ("Dm_base", "Dm_scheduled", "Dm_cells", "D_env"):
        wanted = np.asarray(target[key])
        add(
            key,
            actual[key],
            wanted,
            lower[key],
            3e-20 + 6e-12 * abs(wanted),
            "unchanged ordinary ECM diffusion/setup budget",
        )
    for form in (lower, target):
        for key in ("P_base", "P_mod"):
            exact(actual[key], form[key])
        exact(ions.data(reached["entry_declaration"]["mechanical_entry"].cache), form["mechanics"])
        exact(ions.data(reached["post_static"]["rate_CaATP"]), form["rate_CaATP"])
        exact(ions.data(reached["post_static"]["rate_NaKATP"]), form["rate_NaKATP"])
        slope = reached["event_finalized"]["frequency_sweep_after"]["f slope"]
        if form["f_sweep_slope"] is not None:
            np.testing.assert_allclose(slope, form["f_sweep_slope"], rtol=6e-12, atol=3e-14)
    return rows


def check_sampling(parent, captured, forms, accepted):
    flags = [row["native_calendar_eligible"] for row in captured["sample_states"]]
    sampling.sampling_contract(
        source_labels=captured["source_times_s"].tolist(),
        native_flags=flags,
        reference_indices=[row["sample_indices"] for row in forms],
        native_rows=fixtures.initialization.events.plain(
            captured["sample_states"][: parent.cursor]
        ),
        owned_rows=fixtures.initialization.events.plain(ions.data(parent.run.history)),
        observation_indices=[row.call_index for row in parent.run.observations],
        completed_calls=parent.cursor,
    )
    for form in forms:
        exact(form["clock"]["source_times_s"], captured["source_times_s"])
    for observation in parent.run.observations:
        index = observation.call_index
        exact(ions.data(observation.state), ions.data(accepted[index].run.active))
        assert (
            observation.elapsed_end_s
            == captured["history"][index]["clock_after"]["material_dt_sum_s"]
        )
        assert (
            observation.native_write2storage_called is observation.native_display_completed is False
        )


@pytest.mark.parametrize("case", fixtures.CASES)
def test_retained_transition(tmp_path, case):
    complete = complete_init(tmp_path, case)
    init_digest = ions.digest(complete)
    raw = fixtures.fixture(case, complete)
    binding = transition.bind(raw)
    folder = root(tmp_path) / ("conditional-" + case)
    folder.mkdir(parents=True, exist_ok=False)
    seen, bootstrap = {}, []

    def setup_observer(stage, value):
        archive(tmp_path, case + "-setup-" + stage, value)
        seen[stage] = value

    def before_bootstrap(value):
        archive(tmp_path, case + "-bootstrap-input", value)
        bootstrap.extend(references(folder / "bootstrap", value))

    try:
        parent = transition.transition(
            binding, complete, observer=setup_observer, before_field=before_bootstrap
        )
    except Exception as error:
        archive(
            tmp_path,
            case + "-transition-failure",
            dict(
                complete=complete,
                declaration=raw,
                partial=getattr(error, "partial", None),
                error=str(error),
                traceback=traceback.format_exc(),
            ),
        )
        raise
    archive(tmp_path, case + "-SIM-entry", parent)
    assert ions.digest(complete) == init_digest
    assert parent.cursor == 0 and not parent.run.history and not parent.run.observations
    assert (
        parent.receipt["source_reinitialize_called"]
        and not parent.receipt["fresh_cold_owner_created"]
    )
    assert parent.receipt["original_INIT_clock"].call_index == complete.parent.cursor
    exact(ions.data(parent.run.active.events.rate_cache), ions.data(complete.parent.rate_cache))
    exact(ions.data(parent.nak_rate), ions.data(complete.parent.nak_rate))
    native_reinit = isolated(tmp_path, case, seen["before_GRN_reinitialize"])
    archive(tmp_path, case + "-native-reinitialize-return", native_reinit)
    assert native_reinit["status"] == "source_completed"
    exact(native_reinit["returned"]["material"], seen["GRN_reinitialized"]["available"]["material"])
    exact(
        native_reinit["returned"]["cache"], seen["GRN_reinitialized"]["available"]["catalog_cache"]
    )
    exact(native_reinit["owner_identity"], seen["GRN_reinitialized"]["owner_identity"])
    assert native_reinit["whole_native_phase_completed"] is False
    forms = references(folder / "phase_rules", phase_rules_input(raw, complete, seen))
    check(tmp_path, case + "-phase-rule-errors", folder / "phase_rules", phase_rows(seen, *forms))
    captured = isolated(tmp_path, case, seen["entry_declaration"]["native_SIM_inputs"], sim=True)
    archive(tmp_path, case + "-native-SIM-return", captured)
    assert captured["status"] == "source_completed" and len(captured["history"]) == 3
    assert captured["RNG_unchanged"]
    exact(parent.run.active.events.field.before, captured["bootstrap"]["before"])
    for section, value in base.field_output(parent.run.active.events.field).items():
        exact(value, captured["bootstrap"][section])
    check(
        tmp_path,
        case + "-bootstrap-errors",
        folder / "bootstrap",
        base.compare_field(
            parent.run_binding.composition.events, parent.run.active.events.field, *bootstrap
        ),
    )
    accepted = {}
    check_sampling(parent, captured, forms, accepted)
    for index, native_call in enumerate(captured["history"]):
        point = folder / ("point-" + str(index))
        point.mkdir()
        observed, answers = {}, {mode: [] for mode in MODES}

        def before(mode, point=point, observed=observed, answers=answers, index=index):
            def callback(incoming):
                archive(tmp_path, case + "-actual-" + mode + "-input-" + str(index), incoming)
                observed[mode] = ions.data(incoming)
                answers[mode].extend(references(point / mode, incoming))

            return callback

        previous = parent
        digest = ions.digest(previous)
        try:
            parent, returned = transition.run_window(
                binding,
                parent,
                stop=index + 1,
                **{"before_" + mode: before(mode) for mode in MODES},
            )
            context = returned[0]
            archive(
                tmp_path, case + "-SIM-return-" + str(index), dict(parent=parent, context=context)
            )
        except Exception as error:
            archive(
                tmp_path,
                case + "-SIM-failure-" + str(index),
                dict(
                    parent=previous,
                    partial=getattr(error, "partial", None),
                    error=str(error),
                    traceback=traceback.format_exc(),
                ),
            )
            raise
        assert ions.digest(previous) == digest and len(returned) == 1
        assert all(len(value) == 2 for value in answers.values())
        event_context = context["event_return"][-1]
        exact(observed["nak"], native_call["nak"]["before"])
        exact(event_context["nak"], native_call["nak"])
        exact(ions.data(parent.nak_rate), native_call["nak_rate_after"])
        check(
            tmp_path,
            case + "-nak-errors-" + str(index),
            point / "nak",
            initialized.nak_rows(event_context["nak"], *answers["nak"]),
        )
        comparison.compare_call(
            parent.run_binding.composition,
            previous.run.active,
            parent.run.active,
            context,
            native_call,
            captured,
            raw["sim_composition_template"]["event_inputs"],
            index,
            observed,
            answers,
            tmp_path,
            case,
            point,
            check,
        )
        accepted[index] = parent
        check_sampling(parent, captured, forms, accepted)
        assert (
            parent.source_init.identity == complete.identity
            and ions.digest(complete) == init_digest
        )
        if index < 2:
            assert parent.run.status == "paused"
    assert parent.run.status == "exhausted" and parent.cursor == 3
    archive(
        tmp_path,
        case + "-terminal-report",
        dict(
            fresh_reference_forms=58,
            native_conditional_captures=2,
            SIM_calls=3,
            retained_INIT_calls=complete.parent.cursor,
            inherited_scientific_passes=0,
            independently_carried_INIT_SIM_trajectory=False,
            native_pickle_load_display=False,
        ),
    )


def injected(*_args, **_kwargs):
    raise RuntimeError("Explicit held observer/producer exception specimen")


@pytest.mark.parametrize("case", fixtures.PREFIX_REFUSALS)
def test_prefix_refusal(tmp_path, case):
    if case == "failed_setup_prefix":
        declaration = transition.init.bind(fixtures.init_fixture(case))
        with pytest.raises(transition.init.InitRejected) as caught:
            transition.init.initialize(declaration, after_setup=injected)
        artifact = transition.prepare_failed_prefix(declaration, None, caught.value)
    elif case == "failed_material_prefix":
        binding, parent = supplied_init(tmp_path, case, stop=0)
        with pytest.raises(transition.init.InitRejected) as caught:
            transition.init.advance(binding, parent, before_material=injected)
        artifact = transition.prepare_failed_prefix(binding, parent, caught.value)
    elif case in ("paused_INIT", "capped_INIT"):
        binding, parent = supplied_init(tmp_path, case, stop=1 if case == "paused_INIT" else None)
        if case == "paused_INIT":
            parent = transition.init.pause(binding, parent)
        with pytest.raises(transition.TransitionRejected) as caught:
            transition.prepare_complete(binding, parent)
        archive(
            tmp_path, case + "-prefix-refusal", dict(parent=parent, partial=caught.value.partial)
        )
        return
    else:
        complete = complete_init(tmp_path, case)
        seen = {}

        def observer(stage, value):
            seen[stage] = value
            archive(tmp_path, case + "-reached-" + stage, value)

        binding = transition.bind(fixtures.fixture(case, complete))
        with pytest.raises(transition.TransitionRejected) as caught:
            transition.transition(binding, complete, observer=observer)
        archive(tmp_path, case + "-latent-owner-refusal", caught.value.partial)
        captured = isolated(tmp_path, case, seen["before_GRN_reinitialize"])
        assert captured["status"] == "source_completed"
        exact(
            captured["returned"]["cache"], seen["GRN_reinitialized"]["available"]["catalog_cache"]
        )
        assert captured["returned"]["cache"]["owner_fields"]["channels"] is False
        return
    archive(tmp_path, case + "-failed-INIT-artifact", artifact)
    assert type(artifact) is transition.FailedInitPrefix
    with pytest.raises(transition.TransitionRejected):
        transition.check_complete(artifact)


@pytest.mark.parametrize("case", fixtures.DEPENDENCIES)
def test_transition_dependency(tmp_path, case):
    complete = complete_init(tmp_path, case)
    raw = fixtures.fixture(case, complete)
    packet = raw["sim_composition_template"]["event_inputs"]
    flags = raw["flags"]
    changes = {
        "foreign_INIT_binding": lambda: raw.update(expected_init_binding_identity="foreign"),
        "foreign_world": lambda: packet["field"]["definition"]["environment_geometry_definition"][
            "world"
        ].update(xmax_m=999.0),
        "foreign_ion_axis": lambda: packet["field"]["definition"][
            "environment_geometry_definition"
        ]["current_definition"]["ions"]["ids"].reverse(),
        "wrong_SIM_clock": lambda: packet["calendar"].update(dt_s=packet["calendar"]["dt_s"] * 2),
        "legacy_flag_false": lambda: flags.update(_run_sim=False),
        "enabled_ER": lambda: packet["calcium"].update(Ca_dyn=True),
        "enabled_flow": lambda: flags.update(fluid_flow=True),
        "dynamic_deformation": lambda: flags.update(td_deform=True),
        "native_load_claim": lambda: flags.update(native_load=True),
        "missing_rng_provenance": lambda: raw["source_setup"].update(rng_provenance=""),
        "inferred_pickle_rng": lambda: raw["source_setup"].update(rng_mode="inferred_from_pickle"),
        "wrong_continuity_stream": lambda: raw["source_setup"].update(
            numpy_rng=fixtures.initialization.perturbations.native_stream_manifest(
                fixtures.initialization.perturbations.native_stream(9876)
            )
        ),
        "foreign_profile_targets": lambda: raw["source_setup"]["tissue_profiles"][0][
            "membrane_indices"
        ].append(9999),
        "arbitrary_supplied_pump": lambda: packet["field"]["steps"][0]["material"][
            "supplied_pump_membrane_flux_mol_m2_s"
        ][0].__setitem__(0, 1.0),
        "arbitrary_late_flux": lambda: packet["field"]["steps"][0]["material"][
            "supplied_late_membrane_flux_mol_m2_s"
        ][0].__setitem__(0, 1.0),
    }
    if case in changes:
        changes[case]()
        archive(tmp_path, case + "-poisoned-input", raw)
        with pytest.raises((ValueError, transition.TransitionRejected)):
            transition.transition(transition.bind(raw), complete)
    elif case == "changed_old_clock":
        artifact = replace(
            complete,
            parent=replace(complete.parent, clock=replace(complete.parent.clock, call_index=0)),
        )
        archive(tmp_path, case + "-poisoned-complete-INIT", artifact)
        with pytest.raises(ValueError):
            transition.check_complete(artifact)
    else:
        binding = transition.bind(raw)
        parent = transition.transition(binding, complete)
        receipt = ions.data(parent.receipt)
        if case == "changed_Ca_rate_presence":
            receipt["entry_ca_rate_present"] = False
        else:
            receipt["source_phase"] = "INIT"
        changed = transition.phase(
            binding, complete, parent.run_binding, parent.run, receipt, parent.nak_rate
        )
        archive(tmp_path, case + "-poisoned-SIM-receipt", changed)
        with pytest.raises(ValueError):
            transition.verify(binding, changed)


@pytest.mark.parametrize("case", fixtures.OBSERVER_CASES)
def test_transition_observer_failure(tmp_path, case):
    complete = complete_init(tmp_path, case)
    binding = transition.bind(fixtures.fixture(case, complete))
    parent = transition.transition(binding, complete)
    accepted_before = parent.cursor

    def observer(stage, value):
        archive(tmp_path, case + "-observed-" + stage + "-" + str(accepted_before), value)
        if stage == case:
            raise RuntimeError("Explicit " + stage + " observer failure")

    if case == "headless_observation":
        parent, _ = transition.advance(binding, parent)
        accepted_before = parent.cursor
    digest = ions.digest(parent)
    with pytest.raises(transition.TransitionRejected) as caught:
        transition.advance(binding, parent, observer=observer)
    archive(tmp_path, case + "-SIM-observer-failure", caught.value.partial)
    assert ions.digest(parent) == digest
    inner = caught.value.partial["inner_partial"]
    accepted = inner["accepted"]
    expected = accepted_before + (case != "before_call")
    assert accepted.status == "failed" and accepted.cursor == expected
    assert inner["automatic_retry"] is inner["native_pickle_called"] is False
