"""Deferred headless lifecycle checks on supplied entries and unchanged component equations."""

import copy
import json
import os
import subprocess
import sys
import traceback
from dataclasses import replace
from pathlib import Path

import pytest

from cells.core import physiology_native_calendar as calendars
from cells.processes import betse_normal_ecm_run_lifecycle as run
from cells.processes import betse_normal_ion_join as ions
from tests.unit import test_betse_normal_ecm_event_mechanics as inherited
from tests.unit.test_betse_fast_solver import archive_read
from validation.betse import betse_normal_ecm_run_lifecycle_compare as comparison
from validation.betse import betse_normal_ecm_run_lifecycle_fixtures as fixtures
from validation.betse import betse_normal_ecm_run_lifecycle_native as native
from validation.betse.betse_normal_channel_join_runtime import inventory

MODES = inherited.MODES
exact, base, catalog = inherited.exact, inherited.base, inherited.catalog


def root(tmp):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp))) / "normal-ecm-run-lifecycle"


def archive(tmp, name, value):
    return native.component.archives.write_archive(root(tmp) / name, ions.data(value))


def references(folder, inputs):
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(
        json.dumps(fixtures.composition.events.plain(ions.data(inputs)), indent=2, allow_nan=False)
        + "\n"
    )
    result = []
    for level in (1, 2):
        path = folder / ("reference-" + str(level) + ".json")
        with (folder / ("reference-" + str(level) + ".stdout.log")).open("x") as stream:
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "validation.betse.betse_normal_ecm_run_lifecycle_reference",
                    "--inputs",
                    str(folder / "inputs.json"),
                    "--output",
                    str(path),
                    "--refinement",
                    str(level),
                ],
                check=True,
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=180,
            )
        row = json.loads(path.read_text())
        assert row["production_imports_denied"] and not row["loaded_production_modules"]
        assert (
            row["decimal_precision"] == (100 if level == 1 else 160)
            and row["carried_reference_forms"] == 0
        )
        assert row["runtime"]["measured_cpu_affinity"] == sorted(os.sched_getaffinity(0))
        result.append(row)
    return result


def isolated(tmp, case, inputs, *, clock_only=False):
    folder = root(tmp) / ("isolated-" + case)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(json.dumps(inputs, indent=2, allow_nan=False) + "\n")
    command = [
        sys.executable,
        "-B",
        "-m",
        "validation.betse.betse_normal_ecm_run_lifecycle_native",
        "--inputs",
        str(folder / "inputs.json"),
        "--output",
        str(folder / "native"),
    ]
    if clock_only:
        command.append("--clock-only")
    with (folder / "native.stdout.log").open("x") as stream:
        subprocess.run(command, check=True, stdout=stream, stderr=subprocess.STDOUT, timeout=180)
    captured = archive_read(folder / "native")
    assert (
        captured["production_imports_denied"]
        and not captured["loaded_production_modules"]
        and captured["RNG_unchanged"]
    )
    return folder, captured


def check(tmp, name, folder, rows):
    archive(tmp, name, dict(fields=rows, physical_global_conservation_credit=False))
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


def supplied_entry(tmp, inputs, *, cold_callback=None, bootstrap_callback=None):
    binding = None
    entry = None
    try:
        binding = run.bind(inputs)
        # Caller-owned component preparation is explicit and precedes begin.
        # No native full init/seed/load is called or attested by this helper.
        entry = run.composition.initialize(
            binding.composition, after_cold=cold_callback, before_field=bootstrap_callback
        )
        archive(tmp, inputs["case_id"] + "-supplied-entry", entry)
        receipt = run.entry_receipt(
            binding,
            entry,
            provenance="Caller component cold/bootstrap subset; not native init/load attestation",
        )
        archive(tmp, inputs["case_id"] + "-entry-receipt", receipt)
        return binding, entry, receipt
    except Exception as error:
        archive(
            tmp,
            inputs["case_id"] + "-supplied-entry-failure",
            dict(
                binding=binding,
                entry=entry,
                inputs=inputs,
                partial=getattr(error, "partial", None),
                error=str(error),
                traceback=traceback.format_exc(),
            ),
        )
        raise


@pytest.mark.parametrize("case", fixtures.CASES)
def test_headless_history(tmp_path, case):
    inputs = fixtures.fixture(case)
    ei = inputs["composition_inputs"]["event_inputs"]
    prep = root(tmp_path) / ("preparation-" + case)
    prep.mkdir(parents=True, exist_ok=False)
    (prep / "inputs-before-preparation.json").write_text(
        json.dumps(inputs, indent=2, allow_nan=False) + "\n"
    )
    cold_input = base.cold_inputs(ei["field"])
    cold_input.update(
        catalog=ei["catalog"],
        calcium_configuration=ei["calcium"],
        bootstrap_dt_s=ei["field"]["bootstrap"]["dt_s"],
    )
    cold = references(prep / "cold", cold_input)
    cold_returns = []
    bootstrap = []

    def after_cold(value):
        archive(tmp_path, case + "-caller-cold-return", value)
        cold_returns.append(value)

    def before_bootstrap(value):
        bootstrap.extend(references(prep / "bootstrap", value))

    binding, entry, receipt = supplied_entry(
        tmp_path, inputs, cold_callback=after_cold, bootstrap_callback=before_bootstrap
    )
    entry_digest = ions.digest(entry)
    parent = run.begin(binding, entry, receipt)
    archive(tmp_path, case + "-begin-return", parent)
    assert entry_digest == ions.digest(entry) and not parent.history and not parent.observations
    folder, capture = isolated(tmp_path, case, inputs)
    captured = capture["composition"]
    clock = capture["clock"]
    assert captured["status"] == "source_completed" and len(captured["history"]) == 3
    assert capture["native_full_phase_completed"] is False
    assert len(cold_returns) == 1 and len(bootstrap) == 2
    cold_parent = cold_returns[0]
    exact(cold_parent["network"].network_cache, captured["cold_cache"])
    exact(cold_parent["network"].material.values._asdict(), captured["cold_material"])
    for actual, name in (
        (cold_parent["policy"], "cold_policy"),
        (cold_parent["channel_trace"], "cold_trace"),
        (cold_parent["event_stores"], "cold_event_stores"),
    ):
        exact(actual, captured[name])
    check(
        tmp_path,
        case + "-cold-errors",
        prep / "cold",
        catalog.compare_cold(binding.composition.events, cold_parent, *cold),
    )
    exact(entry.events.field.before, captured["bootstrap"]["before"])
    for section, value in base.field_output(entry.events.field).items():
        exact(value, captured["bootstrap"][section])
    check(
        tmp_path,
        case + "-bootstrap-errors",
        prep / "bootstrap",
        base.compare_field(binding.composition.events, entry.events.field, *bootstrap),
    )
    exact(
        run.composition.event.random_source.native_stream_manifest(entry.events.noise_stream),
        captured["cold_noise_stream"],
    )
    exact(ions.data(entry.events.noise_cache), captured["cold_noise_cache"])
    exact(calendars.window(binding.calendar).event_label_s, clock["source_labels_s"])
    assert calendars.window(binding.calendar).sampled.tolist() == clock["sampled"]
    active = {"index": None}
    points = {}
    before_calls = []
    accepted_calls = []

    def observer(stage, value):
        if stage == "before_call":
            index = value["call"]["call_index"]
            active["index"] = index
            before_calls.append(index)
            point = prep / ("point-" + str(index))
            point.mkdir()
            points[index] = dict(
                point=point, parent=value["parent"], observed={}, answers={m: [] for m in MODES}
            )
        else:
            index = active["index"]
        archive(tmp_path, case + "-" + stage + "-" + str(index), value)
        if stage == "accepted_call":
            accepted_calls.append(index)
            slot = points[index]
            assert all(len(rows) == 2 for rows in slot["answers"].values())
            comparison.compare_call(
                binding.composition,
                slot["parent"].active,
                value["parent"].active,
                value["context"],
                captured["history"][index],
                captured,
                ei,
                index,
                slot["observed"],
                slot["answers"],
                tmp_path,
                case,
                slot["point"],
                check,
            )
        elif stage == "headless_observation":
            assert value.native_write2storage_called is value.native_display_completed is False
            assert value.state.identity == points[index]["candidate_identity"]

    def before(mode):
        def callback(value):
            index = active["index"]
            slot = points[index]
            archive(tmp_path, case + "-actual-" + mode + "-input-" + str(index), value)
            slot["observed"][mode] = ions.data(value)
            slot["answers"][mode].extend(references(slot["point"] / mode, value))

        return callback

    # Register the accepted identity before forwarding the observer so even a
    # failing comparison retains the complete new run and component context.
    def observe(stage, value):
        if stage == "accepted_call":
            points[active["index"]]["candidate_identity"] = value["parent"].active.identity
        observer(stage, value)

    callbacks = {("before_" + mode): before(mode) for mode in MODES}
    try:
        for stop in fixtures.stops(case):
            old = parent
            digest = ions.digest(old)
            parent, contexts = run.run_window(
                binding, parent, stop=stop, observer=observe, **callbacks
            )
            archive(
                tmp_path,
                case + "-window-return-" + str(stop),
                dict(parent=parent, contexts=contexts),
            )
            assert digest == ions.digest(old) and parent.cursor == stop
            assert parent.status == ("exhausted" if stop == 3 else "paused")
    except Exception as error:
        archive(
            tmp_path,
            case + "-full-lifecycle-failure",
            dict(
                parent=parent,
                partial=getattr(error, "partial", None),
                error=str(error),
                traceback=traceback.format_exc(),
            ),
        )
        raise
    assert before_calls == accepted_calls == [0, 1, 2] and len(parent.history) == 3
    assert len(parent.observations) == sum(clock["sampled"])
    assert all(
        obs.state.identity == parent.history[obs.call_index].after_identity
        for obs in parent.observations
    )
    assert parent.history[-1].elapsed_end_s == 3 * binding.calendar.dt_s
    assert parent.active.events.clock.material_dt_sum_s == 3 * binding.calendar.dt_s
    direct = entry
    for index in range(3):
        try:
            direct, context = run.composition.advance(binding.composition, direct)
        except Exception as error:
            archive(
                tmp_path,
                case + "-direct-baseline-failure-" + str(index),
                dict(
                    parent=direct,
                    partial=getattr(error, "partial", None),
                    error=str(error),
                    traceback=traceback.format_exc(),
                ),
            )
            raise
        archive(
            tmp_path,
            case + "-direct-baseline-return-" + str(index),
            dict(candidate=direct, context=context),
        )
    exact(ions.data(parent.active), ions.data(direct))
    assert entry_digest == ions.digest(entry)
    terminal, contexts = run.run_window(binding, parent, stop=3)
    assert terminal.identity == parent.identity and not contexts
    report = dict(
        completed=True,
        owned_run_exhausted=True,
        complete_calls=3,
        delegated_calls=3,
        direct_baseline_calls=3,
        source_labels_dt_samples_exact=True,
        original_calendar_preserved_across_windows=True,
        complete_component_caches_and_state_carried=True,
        duplicate_baseline_new_case_credit=False,
        cold_reference_forms=2,
        bootstrap_reference_forms=2,
        total_fresh_reference_forms=52,
        conditional_reference_forms_per_mode=6,
        conditional_modes=list(MODES),
        carried_reference_forms=0,
        supplied_initialization_explicit=True,
        headless_observations_only=True,
        native_display_completed=False,
        native_init_load_run_sim_core_write2storage_pickle_called=False,
        native_full_phase_completed=False,
        physical_initialization_claim=False,
        physical_global_conservation_credit=False,
        qualification_inherited=False,
    )
    (folder / "comparison.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_headless_raw(tmp_path, case):
    inputs = fixtures.raw_fixture(case)
    archive(tmp_path, case + "-raw-inputs", inputs)
    folder, captured = isolated(tmp_path, case, inputs)
    binding, entry, receipt = supplied_entry(tmp_path, inputs)
    parent = run.begin(binding, entry, receipt)
    original = ions.digest(parent)
    try:
        run.run_window(
            binding,
            parent,
            stop=3,
            observer=lambda stage, value: archive(
                tmp_path,
                case
                + "-raw-"
                + stage
                + "-"
                + str(
                    value["call"]["call_index"]
                    if stage == "before_call"
                    else value["parent"].cursor
                    if stage == "accepted_call"
                    else value.call_index
                ),
                value,
            ),
        )
    except run.RunRejected as error:
        partial = error.partial
        archive(tmp_path, case + "-complete-run-refusal", partial)
        accepted = partial["accepted"]
        assert accepted.status == "failed" and accepted.cursor == (
            2 if case == "late_negative_temperature" else 0
        )
        assert original == ions.digest(parent) and not partial["automatic_retry"]
        failed = partial["failed_attempt"]
        assert failed["component_partial"] and failed["caller_parent"]
        assert captured["composition"]["history"]
        component_partial = ions.data(failed["component_partial"])
        assert component_partial["stage"] == "event_noise_mechanics_material_field"
        event_partial = component_partial["event_partial"]
        assert event_partial["stage"] == "event_material_network_noise_field"
        assert event_partial["available_event_stores"]
        source = captured["composition"]
        leaf = error
        while leaf.__cause__ is not None:
            leaf = leaf.__cause__
        assert failed["stage"] == "component_call"
        assert failed["attempt"]["call"]["call_index"] == accepted.cursor
        if case == "events_zero_width":
            witness = "events_zero_width_store_equality"
            assert type(leaf) is ZeroDivisionError and "division by zero" in str(leaf)
            assert accepted.cursor == 0 and source["status"] == "source_refused"
            assert source["failure"]["stage"] == "events"
            assert source["failure"]["type"] == "ZeroDivisionError"
            exact(event_partial["available_event_stores"], source["history"][0]["events"]["after"])
            assert not event_partial["available"].get("noise")
            assert not component_partial["available"].get("mechanics_input")
        elif case == "network_refuses":
            witness = "GRN_refusal_before_noise_unchanged_RNG"
            assert type(leaf).__name__ == "BetseSimUnstableException"
            assert "Your simulation has become unstable" in str(leaf)
            assert accepted.cursor == 0 and source["status"] == "source_refused"
            assert source["failure"]["stage"] == "material_network"
            assert source["failure"]["type"] == type(leaf).__name__
            assert not event_partial["available"].get("noise")
            assert not event_partial["available"].get("before_noise")
            assert not component_partial["available"].get("mechanics_input")
            declared_rng = inputs["composition_inputs"]["event_inputs"]["prepared_rng"]["manifest"]
            exact(source["history"][0]["noise_stream_after"], declared_rng)
            exact(
                run.composition.event.random_source.native_stream_manifest(
                    accepted.active.events.noise_stream
                ),
                declared_rng,
            )
            exact(
                event_partial["catalog_trace"]["before"], source["history"][0]["network"]["before"]
            )
        elif case == "late_negative_temperature":
            witness = "negative_event_temperature_call2_before_material_drive"
            assert type(leaf) is ValueError
            assert str(leaf) == "Require explicit finite source scalar: runtime_temperature_K"
            assert accepted.cursor == 2 and event_partial["available_event_stores"]["T"] < 0
            assert event_partial["available"]["events"]["source_completed"] is True
            assert (
                event_partial["available"]["before_events"]["source_time_s"]
                == parent.entry.events.clock.source_times_s[2]
            )
            exact(event_partial["available_event_stores"], source["history"][2]["events"]["after"])
            assert not component_partial["available"].get("mechanics_input")
        else:
            assert case == "mechanics_overflow"
            witness = "nonfinite_mechanics_trial_before_material_commit"
            assert type(leaf) is run.composition.mechanics.MechanicsRejected
            assert str(leaf) == "Nonfinite complete mechanics output"
            assert (
                accepted.cursor == 0
                and component_partial["available"]["mechanics_failure"] is not None
            )
            assert event_partial["available"]["noise"]["source_completed"] is True
            assert event_partial["available"].get("material_parent") is None
            trial = component_partial["available"]["mechanics_failure"]
            assert any(
                not inherited.np.isfinite(value).all()
                for value in trial["candidate"]["cache"].values()
            )
            assert (
                source["mechanics_history"]
                and source["mechanics_history"][0]["complete_available_buffers"]
            )
            assert any(
                not inherited.np.isfinite(value).all()
                for key, value in source["mechanics_history"][0]["candidate"].items()
                if not key.startswith("display_")
            )
        archive(
            tmp_path,
            case + "-case-specific-boundary",
            dict(
                component_partial=component_partial,
                native_capture=source,
                named_cause_type=type(leaf).__name__,
                named_cause_message=str(leaf),
                witness=witness,
            ),
        )
        with pytest.raises(ValueError):
            run.resume(binding, accepted)
        with pytest.raises(ValueError):
            run.run_window(binding, accepted, stop=3)
        report = dict(
            positive_credit=False,
            last_accepted_calls=accepted.cursor,
            full_run_and_component_partials_retained=True,
            no_automatic_retry=True,
            native_display_completed=False,
            native_full_phase_completed=False,
            native_source_status=captured["composition"]["status"],
            case_specific_witness=witness,
            case_specific_boundary_verified=True,
            named_cause_type=type(leaf).__name__,
            named_cause_message=str(leaf),
            physical_global_conservation_credit=False,
        )
        (folder / "raw-retention.json").write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n"
        )
    else:
        raise AssertionError("Declared raw refusal not reached; preserve all returned evidence")


@pytest.mark.parametrize("stage", fixtures.OBSERVER_FAILURES)
def test_headless_observer_failure(tmp_path, stage):
    inputs = fixtures.fixture("continuous")
    inputs["case_id"] = "observer-" + stage
    binding, entry, receipt = supplied_entry(tmp_path, inputs)
    parent = run.begin(binding, entry, receipt)
    original = ions.digest(parent)

    def fail(name, value):
        call_index = (
            value["call"]["call_index"]
            if name == "before_call"
            else value["parent"].cursor - 1
            if name == "accepted_call"
            else value.call_index
        )
        archive(tmp_path, stage + "-reached-" + name + "-" + str(call_index), value)
        if name == stage:
            raise RuntimeError("Declared observer failure")

    with pytest.raises(run.RunRejected) as caught:
        run.run_window(binding, parent, stop=3, observer=fail)
    partial = caught.value.partial
    archive(tmp_path, stage + "-full-failure", partial)
    leaf = caught.value
    while leaf.__cause__ is not None:
        leaf = leaf.__cause__
    assert type(leaf) is RuntimeError and str(leaf) == "Declared observer failure"
    accepted = partial["accepted"]
    expected = {"before_call": 0, "accepted_call": 1, "headless_observation": 2}[stage]
    assert (
        accepted.cursor == expected
        and accepted.status == "failed"
        and original == ions.digest(parent)
    )
    attempt = partial["failed_attempt"]["attempt"]
    assert ("component_candidate" in attempt) == (expected > 0)
    assert ("component_context" in attempt) == (expected > 0)
    assert (
        accepted.active.events.clock.call_index == accepted.active.mechanics.step_index == expected
    )
    with pytest.raises(ValueError):
        run.resume(binding, accepted)
    (root(tmp_path) / ("observer-" + stage + ".json")).write_text(
        json.dumps(
            dict(
                expected_failure_reached=True,
                actual_leaf_type=type(leaf).__name__,
                actual_leaf_message=str(leaf),
                expected_accepted_calls=expected,
                actual_accepted_calls=accepted.cursor,
                full_reached_candidate_retained=True,
                no_automatic_retry=True,
                source_failure_credit=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)
def test_headless_dependencies(tmp_path, dependency):
    inputs = fixtures.fixture("continuous")
    inputs["case_id"] = "dependency-" + dependency
    binding, entry, receipt = supplied_entry(tmp_path, inputs)
    parent = run.begin(binding, entry, receipt)
    archive(
        tmp_path,
        dependency + "-baseline",
        dict(binding=binding, entry=entry, parent=parent, receipt=receipt),
    )
    changed = copy.deepcopy(inputs)
    profile = changed["time_profile"]
    source = changed["composition_inputs"]["event_inputs"]

    def action():
        return run.bind(changed)

    fragment = None
    if dependency == "INIT_execution":
        profile["phase"] = "INIT"
        fragment = "INIT execution stays closed"
    elif dependency == "profile_count":
        profile["sim_total_s"] = 2 * profile["sim_dt_s"]
        fragment = "original SIM/N3 component calendar"
    elif dependency == "profile_dt":
        profile["sim_dt_s"] *= 2
        profile["sim_total_s"] = 3 * profile["sim_dt_s"]
        fragment = "original SIM/N3 component calendar"
    elif dependency == "profile_stride":
        profile["sim_sampling_s"] = 2 * profile["sim_dt_s"]
        fragment = "original SIM/N3 component calendar"
    elif dependency == "nonprogress_stride":
        profile["sim_sampling_s"] = 0.5 * profile["sim_dt_s"]
        fragment = "does not progress"
    elif dependency == "partial_component":
        source["stop_after_calls"] = 2
        fragment = "original SIM/N3 component calendar"
    elif dependency == "native_load":
        changed["entry_mode"] = "native_load"
        fragment = "separate qualified ownership"
    elif dependency == "native_persistence":
        changed["persistence"] = "pickle"
        fragment = "separate qualified ownership"
    elif dependency == "native_display":
        changed["observation_mode"] = "native_display"
        fragment = "headless observations"
    else:
        if dependency == "missing_entry":

            def action():
                return run.begin(binding, None, receipt)

            fragment = "unchanged event/mechanics parent"
        elif dependency == "foreign_entry":
            changed["composition_inputs"]["case_id"] = "foreign-composition"
            foreign = run.bind(changed)

            def action():
                return run.begin(foreign, entry, receipt)

            fragment = "unchanged event/mechanics parent"
        elif dependency == "entry_already_advanced":
            advanced, context = run.composition.advance(binding.composition, entry)
            archive(tmp_path, dependency + "-advanced", dict(candidate=advanced, context=context))

            def action():
                return run.begin(binding, advanced, receipt)

            fragment = "source counters zero"
        elif dependency == "receipt_mismatch":
            malformed = dict(ions.data(receipt), source_calendar_identity="0" * 64)

            def action():
                return run.begin(binding, entry, malformed)

            fragment = "initialization association/scope changed"
        elif dependency in ("entry_field_missing", "entry_cache_missing"):
            ep = entry.events
            net = ep.network
            fields = ep.field
            if dependency == "entry_field_missing":
                fields = None
                fragment = "complete supplied bootstrap fields"
            else:
                net = replace(net, network_cache=None)
                fragment = "complete supplied network/channel caches"
            ep = run.composition.event.joined_state(
                binding.composition.events,
                net,
                fields,
                ep.rate_cache,
                ep.clock,
                ep.event_stores,
                ep.noise_stream,
                ep.noise_cache,
            )
            malformed = run.composition.state(
                binding.composition, ep, entry.mechanics, entry.sample_state
            )
            forged_receipt = run.entry_receipt(
                binding, malformed, provenance="Declared malformed association control"
            )
            archive(tmp_path, dependency + "-malformed-entry", malformed)

            def action():
                return run.begin(binding, malformed, forged_receipt)
        elif dependency == "changed_binding":
            malformed = replace(
                binding, inputs=ions.freeze(dict(ions.data(binding.inputs), run_id="foreign"))
            )

            def action():
                return run.verify(malformed, parent)

            fragment = "Changed complete headless run binding"
        elif dependency == "changed_state":
            malformed = replace(parent, status="paused")

            def action():
                return run.verify(binding, malformed)

            fragment = "unchanged owned lifecycle state"
        elif dependency in ("changed_journal", "rebased_label"):
            count = 2 if dependency == "rebased_label" else 1
            reached, contexts = run.run_window(binding, parent, stop=count)
            archive(tmp_path, dependency + "-reached", dict(parent=reached, contexts=contexts))
            journal = list(reached.history)
            index = count - 1
            journal[index] = (
                replace(journal[index], source_label_s=0.0)
                if dependency == "rebased_label"
                else replace(journal[index], dt_s=2 * journal[index].dt_s)
            )
            malformed = run._state(
                binding,
                reached.entry,
                reached.entry_receipt,
                reached.active,
                journal,
                reached.observations,
                reached.status,
            )

            def action():
                return run.verify(binding, malformed)

            fragment = "source label/dt/owner journal changed"
        elif dependency == "stop_before_cursor":
            reached, contexts = run.run_window(binding, parent, stop=1)
            archive(tmp_path, dependency + "-reached", dict(parent=reached, contexts=contexts))

            def action():
                return run.run_window(binding, reached, stop=0)

            fragment = "original source calendar/cursor"
        elif dependency == "boolean_stop":

            def action():
                return run.run_window(binding, parent, stop=True)

            fragment = "original source calendar/cursor"
        else:
            assert dependency == "terminal_step"
            reached, contexts = run.run_window(binding, parent, stop=3)
            archive(tmp_path, dependency + "-reached", dict(parent=reached, contexts=contexts))

            def action():
                return run.advance(binding, reached)

            fragment = "ready, nonterminal run"
    archive(tmp_path, dependency + "-malformed-inputs", changed)
    with pytest.raises((ValueError, run.RunRejected)) as caught:
        action()
    archive(
        tmp_path,
        dependency + "-refusal",
        dict(error=str(caught.value), partial=getattr(caught.value, "partial", None)),
    )
    leaf = caught.value
    while leaf.__cause__ is not None:
        leaf = leaf.__cause__
    assert type(leaf) is ValueError and fragment in str(leaf)
    (root(tmp_path) / ("dependency-" + dependency + ".json")).write_text(
        json.dumps(
            dict(
                baseline_admitted=True,
                intended_refusal_reached=True,
                actual_leaf_type=type(leaf).__name__,
                actual_message=str(leaf),
                expected_fragment=fragment,
                source_failure_credit=False,
                native_initializer_or_persistence_credit=False,
            ),
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )


@pytest.mark.parametrize("case", fixtures.CLOCK_CASES)
def test_headless_clock_source(tmp_path, case):
    profile = fixtures.clock_fixture(case)
    folder, captured = isolated(tmp_path, "clock-" + case, profile, clock_only=True)
    clock = captured["clock"]
    declared = run.profile(profile)[profile["phase"].lower()]
    calendar = calendars.from_duration(
        phase=profile["phase"],
        requested_duration_s=profile[profile["phase"].lower() + "_total_s"],
        dt_s=declared["dt_s"],
        sample_stride=declared["sample_stride"],
        provenance=profile["provenance"],
    )
    rows = calendars.window(calendar)
    assert calendar.step_count == clock["step_count"] == declared["step_count"]
    exact(rows.event_label_s, clock["source_labels_s"])
    assert rows.sampled.tolist() == clock["sampled"] and bool(rows.events_enabled.all()) == (
        profile["phase"] == "SIM" or not len(rows.events_enabled)
    )
    assert (
        clock["installed_native_function_calls"] == 0 and clock["material_solver_executed"] is False
    )
    assert clock["complete_captured_source_function_bodies"] == ["SimPhase._init_kludge_time"]
    assert clock["extracted_statement_slices"] == [
        "Parameters.load.time_counts",
        "Simulator._plot_loop.clock_and_sampling",
    ]
    if case == "duration_truncation":
        assert calendar.step_count == 2
    (folder / "clock-comparison.json").write_text(
        json.dumps(
            dict(
                source_time_profile_exact=True,
                source_labels_samples_exact=True,
                no_material_solver_executed=True,
                native_full_INIT_or_SIM_phase_executed=False,
                complete_captured_body_and_extracted_slice_distinguished=True,
            ),
            indent=2,
        )
        + "\n"
    )


def test_headless_display_refusal(tmp_path):
    inputs = fixtures.fixture("continuous")
    binding, entry, receipt = supplied_entry(tmp_path, inputs)
    parent = run.begin(binding, entry, receipt)
    parent, contexts = run.run_window(binding, parent, stop=2)
    archive(tmp_path, "sample-reached-before-refusal", dict(parent=parent, contexts=contexts))
    original = ions.digest(parent)
    with pytest.raises(run.RunRejected) as caught:
        run.request_native_sample(binding, parent)
    archive(tmp_path, "full-display-refusal", caught.value.partial)
    assert (
        original == ions.digest(parent)
        and caught.value.partial["accepted"].identity == parent.identity
    )
    assert (
        caught.value.partial["native_write2storage_called"]
        is caught.value.partial["native_display_completed"]
        is False
    )
    assert caught.value.partial["component_partial"]["stage"] == "sample_display_domain"
    (root(tmp_path) / "display-refusal.json").write_text(
        json.dumps(
            dict(
                reached_state_retained=True,
                native_display_completed=False,
                native_write2storage_called=False,
                source_failure_credit=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.fixture(scope="module", autouse=True)
def runtime_receipt(tmp_path_factory):
    row = inventory()
    if cpu := os.environ.get("CELLS_ECM_RUN_LIFECYCLE_CPU"):
        assert row["measured_cpu_affinity"] == [int(cpu)]
    folder = root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "runtime.json").write_text(json.dumps(row, indent=2) + "\n")
