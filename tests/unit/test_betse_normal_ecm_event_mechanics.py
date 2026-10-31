"""Deferred complete supplied-state histories, fixed references and refusal partials."""

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

from cells.processes import betse_normal_ecm_event_mechanics as joined
from cells.processes import betse_normal_ion_join as ions
from tests.unit import test_betse_normal_ecm_event_join as established
from tests.unit.test_betse_fast_solver import archive_read
from validation.betse import betse_mechanics_join_checks as mechanical_checks
from validation.betse import betse_normal_ecm_event_mechanics_fixtures as fixtures
from validation.betse import betse_normal_ecm_event_mechanics_native as native
from validation.betse.betse_normal_channel_join_runtime import inventory

base, catalog, exact = established.base, established.catalog, established.exact
MODES = ("events", "material", "calcium", "channels", "network", "noise", "mechanics", "field")


def root(tmp_path):
    return (
        Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path)))
        / "normal-ecm-event-mechanics"
    )


def archive(tmp_path, name, value):
    return native.archives.write_archive(root(tmp_path) / name, ions.data(value))


def references(folder, inputs):
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(
        json.dumps(fixtures.events.plain(ions.data(inputs)), indent=2, allow_nan=False) + "\n"
    )
    rows = []
    for level in (1, 2):
        path = folder / ("reference-" + str(level) + ".json")
        with (folder / ("reference-" + str(level) + ".stdout.log")).open("x") as stream:
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "validation.betse.betse_normal_ecm_event_mechanics_reference",
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
        assert row["runtime"]["measured_cpu_affinity"] == sorted(os.sched_getaffinity(0))
        rows.append(row)
    return rows


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
                "validation.betse.betse_normal_ecm_event_mechanics_native",
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
    assert (
        captured["production_imports_denied"]
        and not captured["loaded_production_modules"]
        and captured["RNG_unchanged"]
    )
    return folder, captured


def check(tmp_path, name, folder, rows):
    archive(tmp_path, name, dict(fields=rows, physical_global_conservation_credit=False))
    report = dict(
        fields={k: v["metric"] for k, v in rows.items()},
        resolutions={k: v["resolution"] for k, v in rows.items()},
        fresh_conditional_reference=True,
        carried_reference_forms=0,
        physical_global_conservation_credit=False,
    )
    (folder / "comparison.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    assert rows and max(v["normalized_max_error"] for v in report["fields"].values()) <= 1
    assert max(v["normalized_max_error"] for v in report["resolutions"].values()) <= 0.1


def mechanical_history(trial):
    return [
        dict(
            frames=ions.data(trial.frames),
            auxiliaries=ions.data(trial.auxiliaries),
            candidate=ions.data(trial.candidate.cache),
            sample=None,
            carried_cache=ions.data(trial.candidate.cache),
        )
    ]


def mechanical_rows(trial, captured, lower, target):
    rows, add = base.legacy.comparisons()
    actual = mechanical_checks.flat(mechanical_history(trial))
    native_values = mechanical_checks.flat(
        [
            {
                k: captured[k]
                for k in ("frames", "auxiliaries", "candidate", "sample", "carried_cache")
            }
        ]
    )
    lo, wanted = map(mechanical_checks.flat, (lower["history"], target["history"]))
    assert actual.keys() == native_values.keys() == lo.keys() == wanted.keys()
    for name, value in wanted.items():
        value = np.asarray(value)
        budget = mechanical_checks.budget(name, value)
        add(
            "owned/" + name,
            actual[name],
            value,
            lo[name],
            budget,
            "unchanged mechanics02 category budget",
        )
        add(
            "native/" + name,
            native_values[name],
            value,
            lo[name],
            budget,
            "unchanged mechanics02 category budget",
        )
        add(
            "correspondence/" + name,
            np.asarray(actual[name]) - np.asarray(native_values[name]),
            np.zeros_like(value),
            np.zeros_like(value),
            budget,
            "same independent mechanics02 budget",
        )
    return rows


def run_history(tmp_path, case):
    inputs = fixtures.fixture(case)
    incoming = inputs["event_inputs"]
    prep = root(tmp_path) / ("preparation-" + case)
    prep.mkdir(parents=True, exist_ok=False)
    (prep / "inputs-before-constructor.json").write_text(
        json.dumps(inputs, indent=2, allow_nan=False) + "\n"
    )
    cold_input = base.cold_inputs(incoming["field"])
    cold_input.update(
        catalog=incoming["catalog"],
        calcium_configuration=incoming["calcium"],
        bootstrap_dt_s=incoming["field"]["bootstrap"]["dt_s"],
    )
    cold = references(prep / "cold", cold_input)
    cold_returns, bootstrap = [], []

    def after_cold(value):
        archive(tmp_path, case + "-cold-return", value)
        cold_returns.append(value)

    def before_bootstrap(value):
        bootstrap.extend(references(prep / "bootstrap", value))

    parent = None
    try:
        binding = joined.bind(inputs)
        parent = joined.initialize(binding, after_cold=after_cold, before_field=before_bootstrap)
        archive(tmp_path, case + "-bootstrap-return", parent)
    except Exception as error:
        archive(
            tmp_path,
            case + "-constructor-failure",
            dict(
                parent=parent,
                inputs=inputs,
                partial=getattr(error, "partial", None),
                error=str(error),
                traceback=traceback.format_exc(),
            ),
        )
        raise
    folder, captured = isolated(tmp_path, inputs)
    assert (
        captured["status"] == "source_completed"
        and len(captured["history"]) == len(captured["mechanics_history"]) == 3
    )
    assert len(cold_returns) == 1 and len(bootstrap) == 2
    cold_parent = cold_returns[0]
    exact(cold_parent["network"].network_cache, captured["cold_cache"])
    exact(cold_parent["network"].material.values._asdict(), captured["cold_material"])
    for actual, key in (
        (cold_parent["policy"], "cold_policy"),
        (cold_parent["channel_trace"], "cold_trace"),
        (cold_parent["event_stores"], "cold_event_stores"),
    ):
        exact(actual, captured[key])
    check(
        tmp_path,
        case + "-cold-errors",
        prep / "cold",
        catalog.compare_cold(binding.events, cold_parent, *cold),
    )
    exact(parent.events.field.before, captured["bootstrap"]["before"])
    for section, value in base.field_output(parent.events.field).items():
        exact(value, captured["bootstrap"][section])
    exact(
        joined.event.random_source.native_stream_manifest(parent.events.noise_stream),
        captured["cold_noise_stream"],
    )
    exact(ions.data(parent.events.noise_cache), captured["cold_noise_cache"])
    check(
        tmp_path,
        case + "-bootstrap-errors",
        prep / "bootstrap",
        base.compare_field(binding.events, parent.events.field, *bootstrap),
    )
    states, contexts, observations, all_answers = [parent], [], [], []
    for index, native_call in enumerate(captured["history"]):
        point = prep / ("point-" + str(index))
        point.mkdir()
        observed = {}
        answers = {name: [] for name in MODES}

        def before(name, index=index, observed=observed, answers=answers, point=point):
            def callback(incoming):
                archive(tmp_path, case + "-actual-" + name + "-input-" + str(index), incoming)
                observed[name] = ions.data(incoming)
                answers[name].extend(references(point / name, incoming))

            return callback

        def after(name, index=index):
            def callback(*values):
                archive(tmp_path, case + "-" + name + "-return-" + str(index), values)

            return callback

        previous_digest = ions.digest(parent)
        try:
            candidate, context = joined.advance(
                binding,
                parent,
                before_events=before("events"),
                before_material=before("material"),
                before_calcium=before("calcium"),
                before_channels=before("channels"),
                before_network=before("network"),
                before_noise=before("noise"),
                before_mechanics=before("mechanics"),
                before_field=before("field"),
                after_events=after("events"),
                after_calcium=after("calcium"),
                after_noise=after("noise"),
                after_mechanics=after("mechanics"),
                after_material=after("material"),
            )
            archive(
                tmp_path,
                case + "-complete-return-" + str(index),
                dict(parent=parent, candidate=candidate, context=context),
            )
        except Exception as error:
            archive(
                tmp_path,
                case + "-complete-failure-" + str(index),
                dict(
                    parent=parent,
                    partial=getattr(error, "partial", None),
                    error=str(error),
                    traceback=traceback.format_exc(),
                ),
            )
            raise
        assert previous_digest == ions.digest(parent) and all(
            len(rows) == 2 for rows in answers.values()
        )
        inner, trial, feedback, calcium, noise, event_context = context["event_return"]
        exact(observed["events"], native_call["before_events"])
        exact(event_context["events"], native_call["events"])
        exact(event_context["reset_return"], native_call["reset_return"])
        packet = copy.deepcopy(observed["material"])
        packet.pop("prospective_noise_draw")
        exact(packet, native_call["material_before"])
        exact(observed["calcium"], native_call["calcium"]["before"])
        exact(observed["channels"], native_call["network"]["before_channels"])
        exact(observed["network"], native_call["network"]["before"])
        exact(observed["field"], native_call["field"]["before"])
        base.compare_native_material(trial, native_call)
        exact(feedback, native_call["network"])
        catalog.compare_calcium_native(calcium, native_call["calcium"])
        established.compare_noise_native(noise, native_call["noise"])
        exact(ions.data(inner.noise_cache), native_call["noise_cache_after"])
        exact(
            joined.event.random_source.native_stream_manifest(inner.noise_stream),
            native_call["noise_stream_after"],
        )
        exact(inner.event_stores, native_call["event_stores_after"])
        exact(inner.network.network_cache, native_call["post_material_cache"])
        exact(inner.network.material.values._asdict(), native_call["candidate"])
        exact(ions.data(inner.rate_cache), native_call["rate_cache_after"])
        exact(ions.data(parent.events.clock), native_call["clock_before"])
        exact(ions.data(inner.clock), native_call["clock_after"])
        for section, value in base.field_output(inner.field).items():
            exact(value, native_call["field"][section])
        mechanical = captured["mechanics_history"][index]
        assert mechanical["source_completed"] and mechanical["complete_available_buffers"]
        exact(context["mechanics_input"], mechanical["before"])
        exact(observed["mechanics"]["initial"], ions.data(parent.mechanics.cache))
        exact(context["mechanics_input"]["primary_cell_mM"], noise["after"]["cell_mol_m3"])
        exact(context["mechanics_input"]["primary_env_mM"], noise["after"]["environment_mol_m3"])
        exact(
            context["mechanics_input"]["pressure_Pa"], event_context["events"]["after"]["P_cells"]
        )
        exact(context["mechanics_input"]["temperature_K"], event_context["events"]["after"]["T"])
        exact(candidate.sample_state, captured["sample_states"][index])
        assert (
            not candidate.sample_state["display_completed"]
            and not candidate.mechanics.sampled_steps
        )
        assert candidate.mechanics.step_index == inner.clock.call_index == index + 1
        assert inner.clock.material_dt_sum_s == (index + 1) * incoming["calendar"]["dt_s"]
        preview = observed["material"]
        assert preview["prospective_draw_is_uncommitted"]
        exact(preview["noise_stream_before"], noise["stream_before"])
        exact(preview["prospective_stream_after"], noise["stream_after"])
        if noise["guard_active"]:
            assert len(noise["draws"]) == 1
            np.testing.assert_array_equal(
                preview["prospective_noise_uniforms"], noise["draws"][0]["values"]
            )
        else:
            assert not noise["draws"] and preview["prospective_noise_uniforms"] is None
        noise_comparison = dict(
            ions.data(noise),
            reference_input=observed["noise"],
            geometry=binding.events.material_binding.geometry_binding.geometry,
        )
        comparisons = (
            (
                "events",
                established.compare_events(
                    event_context["events"], event_context["reset_return"], *answers["events"]
                ),
            ),
            ("material", base.compare_material(trial, *answers["material"])),
            ("calcium", catalog.compare_calcium(calcium, *answers["calcium"])),
            ("channels", catalog.compare_channels(binding.events, feedback, *answers["channels"])),
            ("network", base.legacy.compare_local(feedback, *answers["network"])),
            ("noise", established.compare_noise(noise_comparison, *answers["noise"])),
            (
                "mechanics",
                mechanical_rows(context["mechanics_trial"], mechanical, *answers["mechanics"]),
            ),
            ("field", base.compare_field(binding.events, inner.field, *answers["field"])),
        )
        for mode, rows in comparisons:
            check(tmp_path, case + "-" + mode + "-errors-" + str(index), point / mode, rows)
        states.append(candidate)
        contexts.append(context)
        observations.append(observed)
        all_answers.append(answers)
        parent = candidate
    report = dict(
        completed=True,
        exact_native_event_material_field=True,
        complete_calls=3,
        mechanics_calls=3,
        cold_reference_forms=2,
        bootstrap_reference_forms=2,
        conditional_event_reference_forms=6,
        conditional_material_reference_forms=6,
        conditional_calcium_reference_forms=6,
        conditional_channel_reference_forms=6,
        conditional_network_reference_forms=6,
        conditional_noise_reference_forms=6,
        conditional_mechanics_reference_forms=6,
        conditional_field_reference_forms=6,
        total_fresh_reference_forms=52,
        carried_reference_forms=0,
        single_material_field_advance=True,
        actual_event_pressure_and_temperature=True,
        actual_post_noise_primary_and_post_GRN_molecules=True,
        previous_field_epoch=True,
        source_ER_disabled=True,
        held_zero_fluid_stores=True,
        dynamic_deformation_enabled=False,
        display_completed=False,
        native_calendar_sample_eligibility_preserved=True,
        complete_native_and_owned_partials_required=True,
        qualification_inherited=False,
        full_native_normal_solver_executed=False,
        physical_initialization_claim=False,
        physical_global_conservation_credit=False,
        retained_material_panel_accepted=False,
    )
    (folder / "comparison.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return binding, states, contexts, observations, all_answers, captured


@pytest.mark.parametrize("case", fixtures.CASES)
def test_event_mechanics_history(tmp_path, case):
    run_history(tmp_path, case)


@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_event_mechanics_raw(tmp_path, case):
    inputs = fixtures.raw_fixture(case)
    archive(tmp_path, case + "-raw-inputs", inputs)
    folder, captured = isolated(tmp_path, inputs)
    parent = None
    completed = 0
    try:
        binding = joined.bind(inputs)
        parent = joined.initialize(
            binding, after_cold=lambda value: archive(tmp_path, case + "-raw-cold-return", value)
        )
        for index in range(inputs["event_inputs"]["stop_after_calls"]):
            original = ions.digest(parent)
            try:
                candidate, context = joined.advance(
                    binding,
                    parent,
                    before_events=lambda value, index=index: archive(
                        tmp_path, case + "-raw-events-" + str(index), value
                    ),
                    after_noise=lambda value, index=index: archive(
                        tmp_path, case + "-raw-noise-" + str(index), value
                    ),
                    before_mechanics=lambda value, index=index: archive(
                        tmp_path, case + "-raw-mechanics-input-" + str(index), value
                    ),
                    after_mechanics=lambda value, index=index: archive(
                        tmp_path, case + "-raw-mechanics-return-" + str(index), value
                    ),
                )
            finally:
                assert original == ions.digest(parent)
            archive(
                tmp_path,
                case + "-raw-complete-return-" + str(index),
                dict(parent=parent, candidate=candidate, context=context),
            )
            parent = candidate
            completed += 1
    except joined.CompositionRejected as error:
        partial = ions.data(error.partial)
        archive(
            tmp_path,
            case + "-raw-full-partial",
            dict(
                parent=parent, partial=partial, error=str(error), traceback=traceback.format_exc()
            ),
        )
        assert partial["stage"] == "event_noise_mechanics_material_field"
        event_partial = partial["event_partial"]
        assert event_partial and event_partial["available_event_stores"]
        if case in ("zero_global_pulse_width", "radial_pressure_shape"):
            assert completed == 0 and captured["failure"]["stage"] == "events"
            exact(
                event_partial["available_event_stores"], captured["history"][0]["events"]["after"]
            )
            assert not partial["available"].get("mechanics_input")
        elif case == "GRN_refuses_before_noise":
            assert completed == 0 and captured["status"] == "source_refused"
            assert not partial["available"].get("mechanics_input")
            exact(
                captured["history"][0]["noise_stream_after"],
                inputs["event_inputs"]["prepared_rng"]["manifest"],
            )
        elif case == "late_negative_temperature":
            assert completed == 2 and event_partial["available_event_stores"]["T"] < 0
        elif case == "negative_Dm_source_return":
            # Same scheduled pulse and N3 source labels as the event-only raw
            # control; do not discard its first completed material/mechanics call.
            assert (
                completed == 1 and np.min(event_partial["available_event_stores"]["Dm_cells"]) < 0
            )
            assert parent.events.clock.call_index == parent.mechanics.step_index == 1
            assert np.isfinite(event_partial["available_event_stores"]["Dm_cells"]).all()
            assert str(error) == "Incomplete/nonfinite source array or domain: membrane diffusion"
            assert event_partial["available"]["events"]["source_completed"]
            expected = captured["history"][1]
            exact(event_partial["available"]["before_events"]["clock"], expected["clock_before"])
            assert event_partial["available"]["events"]["source_time_s"] == (
                1.5 * inputs["event_inputs"]["calendar"]["dt_s"]
            )
            exact(event_partial["available"]["events"]["stages"], expected["events"]["stages"])
            exact(event_partial["available_event_stores"], expected["events"]["after"])
            assert not partial["available"].get("mechanics_input")
        elif case == "mechanics_overflow_before_commit":
            assert completed == 0 and partial["available"]["mechanics_failure"] is not None
            assert event_partial["available"]["noise"]["source_completed"]
            assert event_partial["available"].get("material_parent") is None
            assert (
                captured["mechanics_history"]
                and captured["mechanics_history"][0]["complete_available_buffers"]
            )
            assert any(
                not np.isfinite(v).all()
                for k, v in captured["mechanics_history"][0]["candidate"].items()
                if not k.startswith("display_")
            )
        else:
            assert case == "protein_noise_large_limit" and completed < 3
            assert event_partial["available"].get("before_noise") or captured["noise_rows"]
        report = dict(
            positive_credit=False,
            completed_calls=completed,
            native_complete_calls=sum(bool(row["source_completed"]) for row in captured["history"]),
            native_status=captured["status"],
            native_failure_stage=None
            if captured["failure"] is None
            else captured["failure"]["stage"],
            port_stage=partial["stage"],
            full_native_partial_retained=True,
            full_owned_partial_retained=True,
            source_and_owned_endpoints_reported_separately=True,
            display_completed=False,
            physical_global_conservation_credit=False,
            qualification_inherited=False,
        )
        (folder / "raw-retention.json").write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n"
        )
    except Exception as error:
        archive(
            tmp_path,
            case + "-raw-unexpected-failure",
            dict(
                parent=parent,
                partial=getattr(error, "partial", None),
                error=str(error),
                traceback=traceback.format_exc(),
            ),
        )
        raise
    else:
        archive(tmp_path, case + "-raw-unexpected-return", dict(parent=parent, completed=completed))
        raise AssertionError(
            "Declared raw boundary was not reached; retain complete returned evidence"
        )


@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)
def test_event_mechanics_dependencies(tmp_path, dependency):
    inputs = fixtures.fixture("combined")
    archive(tmp_path, dependency + "-baseline-inputs", inputs)
    parent = None
    try:
        binding = joined.bind(inputs)
        parent = joined.initialize(binding)
        archive(tmp_path, dependency + "-baseline-parent", parent)
    except Exception as error:
        archive(
            tmp_path,
            dependency + "-unexpected-baseline-failure",
            dict(
                parent=parent,
                partial=getattr(error, "partial", None),
                error=str(error),
                traceback=traceback.format_exc(),
            ),
        )
        raise
    changed = copy.deepcopy(inputs)
    definition = changed["mechanics_definition"]
    geometry = definition["geometry"]
    layout = geometry["layout"]
    event_inputs = changed["event_inputs"]
    fragment = None

    def action():
        return joined.bind(changed)

    expected_type = (ValueError, AssertionError)
    if dependency == "foreign_cell_owners":
        geometry["cell_ids"][0] = "foreign"
        fragment = "owner order"
    elif dependency == "foreign_membrane_owners":
        layout["membrane_ids"][0] = "foreign"
        fragment = "owner order"
    elif dependency == "changed_cell_measure":
        layout["cell_volume_m3"][0] *= 2
        fragment = "cell_volume_m3"
    elif dependency == "changed_membrane_measure":
        layout["membrane_area_m2"][0] *= 2
        geometry["display_vertex_weights"] = (
            np.asarray(layout["sum_membranes"])
            * np.asarray(layout["membrane_area_m2"])[None, :]
            / np.asarray(layout["cell_area_m2"])[:, None]
        ).tolist()
        fragment = "membrane_area_m2"
    elif dependency == "changed_centres":
        layout["centers_m"][0][0] += 0.5
        fragment = "centers_m"
    elif dependency == "changed_environment_map":
        geometry["membrane_to_environment"][0] = 1
        fragment = "not equal"
    elif dependency == "wrong_phase_dt":
        definition["parameters"]["dt_s"] *= 2
        fragment = "same native phase dt"
    elif dependency in ("enabled_flow", "dynamic_deformation"):
        definition["policy"]["fluid_flow" if dependency == "enabled_flow" else "td_deform"] = True
        fragment = "disables flow and dynamic"
    elif dependency == "FAST":
        definition["policy"]["solver"] = "FAST"
        fragment = "explicit FULL booleans"
    elif dependency == "display_regime":
        definition["policy"]["display_regime"] = "global_quartic_conditional"
        fragment = "requires>=25"
    elif dependency == "physical_initialization":
        changed["physical_init"] = True
        fragment = "separately declared"
    elif dependency == "cut_requested":
        event_inputs["event_owner"]["event_cut"] = {"is_fired": False}
        fragment = "Cuts/remeshing"
    elif dependency == "missing_owner":
        event_inputs.pop("event_owner")
        fragment = "separately declared ECM event"
    elif dependency == "wrong_RNG_version":
        event_inputs["prepared_rng"]["manifest"]["numpy_version"] = "unowned"
        fragment = "recorded NumPy version"
    elif dependency == "competing_control_override":
        event_inputs["field"]["steps"][1]["material"]["runtime_temperature_K"] += 1
        fragment = "competing per-step overrides"
    elif dependency == "nonzero_disabled_flow":
        event_inputs["field"]["steps"][0]["material"]["velocity_x_m_s"][0][0] = 0.01
        fragment = "held-zero velocity"
    elif dependency == "changed_binding":
        malformed_binding = replace(
            binding, inputs=ions.freeze(dict(ions.data(binding.inputs), case_id="foreign"))
        )
        archive(tmp_path, dependency + "-malformed-binding", malformed_binding)

        def action():
            return joined.advance(malformed_binding, parent)

        fragment = "Changed complete event/mechanics binding"
    elif dependency == "changed_sample_state":
        malformed = joined.state(
            binding,
            parent.events,
            parent.mechanics,
            dict(ions.data(parent.sample_state), display_completed=True),
        )
        archive(tmp_path, dependency + "-malformed-parent", malformed)

        def action():
            return joined.advance(binding, malformed)

        fragment = "held, uncompleted display state"
    elif dependency in (
        "foreign_mechanics_parent",
        "changed_prior_field",
        "wrong_clock",
        "changed_event_store",
        "changed_noise_cache",
    ):
        ep = parent.events
        mp = parent.mechanics
        if dependency == "foreign_mechanics_parent":
            mp = replace(mp, binding_identity="0" * 64)
            fragment = "foreign state"
        else:
            stores = ions.data(ep.event_stores)
            clock = ep.clock
            fields = ep.field
            cache = ep.noise_cache
            if dependency == "changed_prior_field":
                fields = None
                fragment = "actual preceding full field"
            elif dependency == "wrong_clock":
                clock = joined.event.Clock(ep.clock.source_times_s, 1, 0.0)
                fragment = "same source call"
            elif dependency == "changed_event_store":
                stores["NaKATP_block"] = 0.25
                fragment = "control owners differ"
            else:
                cache = joined.event.NoiseCache(True, ions.freeze(np.zeros(1)))
                fragment = "immutable actual protein-noise cache"
            ep = joined.event.joined_state(
                binding.events,
                ep.network,
                fields,
                ep.rate_cache,
                clock,
                stores,
                ep.noise_stream,
                cache,
            )
        malformed = joined.state(binding, ep, mp, parent.sample_state)
        archive(tmp_path, dependency + "-malformed-parent", malformed)

        def action():
            return joined.advance(binding, malformed)
    else:
        assert dependency in ("sampled_display", "unsampled_display")
        count = 2 if dependency == "sampled_display" else 1
        for index in range(count):
            try:
                parent, context = joined.advance(binding, parent)
            except Exception as error:
                archive(
                    tmp_path,
                    dependency + "-sample-prefix-failure-" + str(index),
                    dict(
                        parent=parent,
                        partial=getattr(error, "partial", None),
                        error=str(error),
                        traceback=traceback.format_exc(),
                    ),
                )
                raise
            archive(
                tmp_path,
                dependency + "-sample-reached-" + str(index),
                dict(parent=parent, context=context),
            )
        assert parent.sample_state["native_calendar_eligible"] == (dependency == "sampled_display")

        def action():
            return joined.sample(binding, parent)

        fragment = "display refused"
    archive(tmp_path, dependency + "-malformed-inputs", changed)
    original = ions.digest(parent)
    with pytest.raises((ValueError, AssertionError, joined.CompositionRejected)) as caught:
        action()
    error = caught.value
    archive(
        tmp_path,
        dependency + "-refusal",
        dict(parent=parent, partial=getattr(error, "partial", None), error=str(error)),
    )
    assert original == ions.digest(parent)
    leaf = error
    while leaf.__cause__ is not None:
        leaf = leaf.__cause__
    assert isinstance(leaf, expected_type) and fragment in str(leaf)
    if dependency in ("sampled_display", "unsampled_display"):
        assert error.partial["stage"] == (
            "sample_display_domain" if dependency == "sampled_display" else "sample_clock"
        )
        assert not error.partial["display_completed"]
    (root(tmp_path) / ("dependency-" + dependency + ".json")).write_text(
        json.dumps(
            dict(
                baseline_admitted=True,
                intended_failure_reached=True,
                actual_leaf_type=type(leaf).__name__,
                actual_message=str(leaf),
                expected_fragment=fragment,
                source_failure_credit=False,
                display_completed=False,
            ),
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )


@pytest.mark.parametrize("corruption", fixtures.CORRUPTIONS)
def test_event_mechanics_corruptions(tmp_path, corruption):
    binding, states, contexts, observed, answers, captured = run_history(tmp_path, "combined")
    context = contexts[0]
    target = answers[0]["mechanics"][1]
    if corruption in ("wrong_PP", "wrong_displacement_axis"):
        actual = copy.deepcopy(
            mechanical_checks.flat(mechanical_history(context["mechanics_trial"]))
        )
        key = (
            next(k for k in actual if k.endswith(".PP") if corruption == "wrong_PP")
            if corruption == "wrong_PP"
            else next(k for k in actual if k.endswith(".d_cells_x"))
        )
        actual[key] = np.asarray(actual[key]) + 1.0
        expected = mechanical_checks.flat(target["history"])
        fractions = []
        for name, value in expected.items():
            budget = mechanical_checks.budget(name, np.asarray(value))
            fractions.extend(
                (abs(np.asarray(actual[name]) - np.asarray(value)) / budget).ravel().tolist()
            )
        assert max(fractions) > 1
        archive(
            tmp_path,
            corruption + "-mutated-output",
            dict(actual=actual, target=expected, maximum_error_over_budget=max(fractions)),
        )
    else:
        incoming = ions.data(context["mechanics_input"])
        if corruption == "end_field_epoch":
            incoming["electric_field_V_m"] = np.asarray(
                states[1].events.field.voltage.values.cell_field_xy_V_m
            ).T
        else:
            incoming["primary_cell_mM"] = ions.data(
                context["event_return"][4]["before"]["cell_mol_m3"]
            )
        archive(tmp_path, corruption + "-wrong-source-epoch", incoming)
        with pytest.raises(AssertionError):
            exact(incoming, captured["mechanics_history"][0]["before"])
    (root(tmp_path) / ("corruption-" + corruption + ".json")).write_text(
        json.dumps(
            dict(
                baseline_complete=True,
                intended_corruption_rejected=True,
                duplicate_baseline_positive_credit=False,
                scientific_budget_changed=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.fixture(scope="module", autouse=True)
def runtime_receipt(tmp_path_factory):
    row = inventory()
    if cpu := os.environ.get("CELLS_ECM_EVENT_MECHANICS_CPU"):
        assert row["measured_cpu_affinity"] == [int(cpu)]
    folder = root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "runtime.json").write_text(json.dumps(row, indent=2) + "\n")
