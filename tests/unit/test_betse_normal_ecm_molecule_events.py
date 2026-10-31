"""Held source-event/actual-molecule conditionals; never collected in preparation."""

import os
from dataclasses import replace

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_molecule_events as joined
from cells.processes import betse_normal_ecm_molecule_lifecycle as leaf
from cells.processes import betse_normal_ion_join as ions
from tests.unit import test_betse_normal_ecm_catalog_join as catalog
from tests.unit import test_betse_normal_ecm_field_join as fields
from tests.unit import test_betse_normal_ecm_init_phase as initialized
from tests.unit import test_betse_normal_ecm_molecule_events_capture as capture
from tests.unit import test_betse_normal_ecm_molecule_events_comparisons as compare
from tests.unit import test_betse_normal_ecm_molecule_transport as transported
from validation.betse import betse_normal_ecm_molecule_events_fixtures as fixtures
from validation.betse import betse_normal_ecm_molecule_failure_checks as failures

archive, refs, native, check = capture.archive, capture.references, capture.isolated, capture.check
MODES = ("nak", "material", "calcium", "mechanics", "commit", "field")
exact = fields.exact


@pytest.fixture(autouse=True)
def explicit_release():
    if os.environ.get("CELLS_ECM_MOLECULE_EVENTS_RELEASED") != "1":
        pytest.skip("Held source proposal; Chief must independently review and explicitly release")


def retained(tmp, name, operation, **readers):
    return failures.retained_call(
        operation,
        stage=name,
        readers={key: lambda value=value: value for key, value in readers.items()},
        retain=lambda value: archive(tmp, name + "-outcome", value),
    )


def source_entry(tmp, case):
    selected = fixtures.selected(case)
    raw = fixtures.source.init_fixture(selected)
    archive(tmp, case + "-source-INIT-input", raw)
    declaration = leaf.init.bind(raw)
    ib, parent = retained(
        tmp,
        case + "-source-INIT-setup",
        lambda: leaf.init.initialize(declaration),
        declaration=declaration,
    )
    parent, _ = retained(
        tmp,
        case + "-source-INIT-history",
        lambda: leaf.init.run_window(ib, parent, stop=ib.calendar.step_count),
        parent=parent,
    )
    complete = leaf.prepare_complete(ib, parent)
    raw = fixtures.source.fixture(selected, complete)
    archive(tmp, case + "-source-SIM-input", raw)
    binding = leaf.bind(raw)
    entry = retained(
        tmp,
        case + "-source-SIM-transition",
        lambda: leaf.transition(binding, complete),
        complete=complete,
    )
    archive(tmp, case + "-actual-source-SIM-entry", dict(binding=binding, entry=entry))
    return binding, entry


def initial(tmp, case, *, checked=False, before_entry_controls=None, after_entry_controls=None):
    source, entry = source_entry(tmp, case)
    raw = fixtures.declaration(case, source, entry)
    archive(tmp, case + "-event-declaration-before-bind", raw)
    binding = joined.bind(raw, source, entry)
    folder = capture.root(tmp) / (case + "-entry-controls")
    folder.mkdir(parents=True, exist_ok=False)
    seen = {}

    def before(value):
        seen["before"] = value
        archive(tmp, case + "-entry-controls-input", value)
        if checked:
            seen["forms"] = refs(folder / "reference", value)
            seen["native"] = native(folder / "native", value)
        if before_entry_controls is not None:
            before_entry_controls(value)

    def after(value):
        seen["after"] = value
        archive(tmp, case + "-entry-controls-return", value)
        if after_entry_controls is not None:
            after_entry_controls(value)

    parent = retained(
        tmp,
        case + "-event-begin",
        lambda: joined.begin(binding, before_entry_controls=before, after_entry_controls=after),
        source_entry=entry,
    )
    archive(tmp, case + "-event-entry", dict(binding=binding, parent=parent))
    if checked:
        assert (
            seen["native"]["status"] == "source_completed" and not seen["native"]["capture_errors"]
        )
        exact(seen["after"]["after"]["controls"], seen["native"]["returned"]["controls"])
        for form in seen["forms"]:
            exact(seen["after"]["after"]["controls"], form["controls"])
        assert seen["after"]["source_control_initializations"] == 1
    assert binding.source_entry is entry and parent.cursor == 0
    return binding, parent


def checked_calls(tmp, case, binding, parent):
    folder = capture.root(tmp) / (case + "-calls")
    folder.mkdir()
    clock = refs(
        folder / "clock",
        dict(
            mode="clock",
            time_profile=ions.data(binding.base.inputs_raw["time_profile"]),
            source_phase="SIM",
        ),
    )
    while parent.status == "ready":
        index = parent.cursor
        point = folder / ("call-" + str(index))
        point.mkdir()
        answers, observed, captured = {}, {}, {}

        def before(
            mode, index=index, point=point, answers=answers, observed=observed, captured=captured
        ):
            def callback(value):
                incoming = dict(ions.data(value), source_phase="SIM", legacy_run_sim=True)
                archive(tmp, case + "-" + str(index) + "-" + mode + "-input", incoming)
                observed[mode] = incoming
                answers[mode] = refs(point / mode, incoming)
                if mode == "events":
                    captured["events"] = native(point / "event-native", incoming)

            return callback

        def handler(
            role,
            stage,
            value,
            index=index,
            point=point,
            answers=answers,
            observed=observed,
            captured=captured,
        ):
            archive(tmp, case + "-" + str(index) + "-" + role + "-" + stage, value)
            if role == "all":
                captured["owners"] = native(point / "owner-native", value)
            elif stage in ("channels", "network", "transporters"):
                key = role + "-" + stage
                observed[key] = ions.data(value)
                answers[key] = refs(point / key, value)

        previous = parent
        digest = ions.digest(previous)
        parent, detail = retained(
            tmp,
            case + "-advance-" + str(index),
            lambda previous=previous: joined.advance(
                binding,
                previous,
                before_events=before("events"),
                handler_observer=handler,
                **{"before_" + mode: before(mode) for mode in MODES},
            ),
            parent=previous,
        )
        archive(tmp, case + "-return-" + str(index), dict(parent=parent, detail=detail))
        assert ions.digest(previous) == digest and parent.cursor == index + 1
        event = captured["events"]
        assert event["status"] == "source_completed" and not event["capture_errors"]
        exact(detail["events"], event["events"])
        exact(detail["reset_return"], event["reset_return"])
        check(
            tmp,
            case + "-" + str(index) + "-event-errors",
            point / "events",
            compare.compare_events(detail["events"], detail["reset_return"], *answers["events"]),
        )
        view = joined.working(binding, parent.runtime_material_binding, parent.runtime_definition)
        compare.check_handlers(
            tmp,
            case + "-" + str(index),
            point,
            view,
            parent,
            detail,
            answers,
            captured["owners"],
            observed,
        )
        for mode, rows in (
            ("nak", initialized.nak_rows(detail["nak"], *answers["nak"])),
            ("material", transported.prefix_rows(detail["material_trial"], *answers["material"])),
            ("calcium", catalog.compare_calcium(detail["calcium"], *answers["calcium"])),
            ("commit", transported.commit_rows(detail["material_trial"], *answers["commit"])),
            ("field", fields.compare_field(view, parent.field, *answers["field"])),
        ):
            check(tmp, case + "-" + str(index) + "-" + mode, point / mode, rows)
        for form in answers["mechanics"]:
            exact(
                ions.data(detail["mechanics_trial"].candidate.cache),
                form["history"][0]["candidate"],
            )
        compare.sample_contract(view, parent, clock)
        assert (
            parent.history[-1]["event_fire_calls"]
            == parent.history[-1]["pre_event_flux_reset_calls"]
            == 1
        )
    return parent


@pytest.mark.parametrize("case", fixtures.CASES)
def test_actual_SIM_events(tmp_path, case):
    binding, entry = initial(tmp_path, case, checked=True)
    original = ions.digest(binding.source_entry)
    parent = checked_calls(tmp_path, case, binding, entry)
    duplicate = entry
    for stop in (1, 2, 3):
        duplicate, _ = joined.run_window(binding, duplicate, stop=stop)
    exact(ions.data(parent), ions.data(duplicate))
    assert (
        parent.status == "exhausted"
        and parent.cursor == 3
        and ions.digest(binding.source_entry) == original
    )
    assert all(
        parent.history[j]["source_label_s"]
        == float(binding.source_entry.active.clock.source_times_s[j])
        for j in range(3)
    )
    if case == "voltage_same_edge":
        assert parent.history[1]["event_trace"]["after"]["bound_V"]["R"] <= 0
    if case == "NaK_shape":
        assert np.asarray(parent.history[0]["event_trace"]["after"]["NaKATP_block"]).shape == ()
    for role in leaf.owners.ROLES:
        active = parent.network.network_cache["enabled"][role]
        assert (parent.network.network_cache["handlers"][role] is not None) is active
    archive(
        tmp_path,
        case + "-summary",
        dict(
            accepted_SIM_calls=3,
            source_INIT_preparation_accuracy_credit=0,
            duplicate_window_calls=3,
            duplicate_window_accuracy_credit=0,
            native_events_local=True,
            native_storage_called=False,
            independently_carried_trajectory=False,
            physical_global_conservation_credit=False,
        ),
    )


@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_actual_source_partial(tmp_path, case):
    binding, parent = initial(tmp_path, case)
    captured = []

    def before(value):
        archive(tmp_path, case + "-raw-event-input-" + str(parent.cursor), value)
        captured.append(
            native(capture.root(tmp_path) / (case + "-raw-native-" + str(parent.cursor)), value)
        )

    with pytest.raises(joined.EventsRejected) as caught:
        while parent.status == "ready":
            previous = parent
            parent, _ = retained(
                tmp_path,
                case + "-raw-step-" + str(previous.cursor),
                lambda previous=previous: joined.advance(binding, previous, before_events=before),
                parent=previous,
            )
    partial = caught.value.partial
    failed = partial["accepted"]
    joined.verify(binding, failed)
    assert failed.status == "failed"
    assert failed.cursor == (0 if case == "zero_global_pulse_width" else 1)
    reached = partial["source_partial"]
    exact(reached["available_event_stores"], captured[-1]["events"]["after"])
    if case == "zero_global_pulse_width":
        assert captured[-1]["status"] == "source_refused"
        assert failures.exception_chain(caught.value)[-1]["type"] == "ZeroDivisionError"
    else:
        assert (
            captured[-1]["status"] == "source_completed"
            and reached["available"]["events"]["source_completed"]
        )
    archive(tmp_path, case + "-source-failure-prefix", dict(partial=partial, captured=captured))


@pytest.mark.parametrize("case", fixtures.OBSERVER_CASES)
def test_complete_observer_prefix(tmp_path, case):
    def fail(value):
        raise RuntimeError("Declared entry observer failure")

    if case in ("entry_before", "entry_after"):
        with pytest.raises(joined.EventsRejected) as caught:
            initial(
                tmp_path,
                case,
                **{
                    "before_entry_controls"
                    if case == "entry_before"
                    else "after_entry_controls": fail
                },
            )
        assert caught.value.partial["source_entry"].cursor == 0
        assert caught.value.partial["before_entry_controls"] is not None
        return
    binding, parent = initial(tmp_path, case)

    def observer(stage, value):
        if stage == case:
            raise RuntimeError("Declared outer source-call observer failure")

    def after_global(value):
        if value["stage"] == "_fire_events_global":
            raise RuntimeError("Declared event-stage observer failure")

    def after_molecules(role, stage, value):
        if role == "molecules" and stage == "returned":
            raise RuntimeError("Declared actual general-owner-return observer failure")

    with pytest.raises(joined.EventsRejected) as caught:
        retained(
            tmp_path,
            case + "-observer",
            lambda: joined.advance(
                binding,
                parent,
                observer=observer,
                before_events=fail if case == "before_events" else None,
                after_events=fail if case == "after_events" else None,
                event_observer=after_global if case == "after_global" else None,
                handler_observer=after_molecules if case == "after_molecules" else None,
            ),
            parent=parent,
        )
    partial = caught.value.partial
    failed = partial["accepted"]
    joined.verify(binding, failed)
    assert failed.status == "failed" and failed.cursor == (1 if case == "after_call" else 0)
    assert partial["source_partial"] is not None
    archive(tmp_path, case + "-observer-prefix", partial)


@pytest.mark.parametrize("case", fixtures.DEPENDENCIES)
def test_event_dependency(tmp_path, case):
    source, entry = source_entry(tmp_path, case)
    raw = fixtures.declaration(case, source, entry)
    challenge = {}
    if case in (
        "foreign_source_binding",
        "foreign_source_entry",
        "advanced_source_entry",
        "wrong_scope",
        "cut_requested",
        "foreign_profile",
        "changed_configured_environment",
        "unsupported_callback",
        "native_storage_claim",
    ):
        if case == "foreign_source_binding":
            raw["source_binding_identity"] = "foreign"
        elif case == "foreign_source_entry":
            raw["source_entry_identity"] = "foreign"
        elif case == "advanced_source_entry":
            entry, _ = leaf.advance(source, entry)
        elif case == "wrong_scope":
            raw["scope"]["flow"] = True
        elif case == "native_storage_claim":
            raw["scope"]["native_storage"] = True
        elif case == "cut_requested":
            raw["event_owner"]["event_cut"] = {"is_fired": False}
        elif case == "foreign_profile":
            raw["event_owner"]["tissue_target_inds"]["all"] = []
        elif case == "changed_configured_environment":
            raw["event_owner"]["configured_environment"]["Na"] *= 2
        else:
            raw["event_owner"]["callbacks"]["Namem"]["dynamic"]["kind"] = "bitmap"

        def action():
            return joined.bind(raw, source, entry)

        challenge.update(source=source, entry=entry, raw=raw)
    else:
        binding = joined.bind(raw, source, entry)
        parent = joined.begin(binding)
        if case == "changed_binding":
            binding = replace(binding, identity="foreign")
        elif case in ("changed_event_trace", "stop_before_cursor"):
            parent, _ = joined.advance(binding, parent)
        if case in (
            "changed_clock",
            "changed_event_trace",
            "changed_event_store",
            "changed_entry_receipt",
            "changed_entry_material",
            "missing_owner_cache",
            "changed_transporter_flux",
            "missing_event_store",
        ):
            changed = parent
            if case == "changed_clock":
                changed = replace(changed, clock=phase_clock(changed, 1))
            elif case == "changed_event_trace":
                history = ions.data(changed.history)
                history[0]["event_fire_calls"] = 0
                changed = replace(changed, history=ions.freeze(history))
            elif case in ("changed_event_store", "missing_event_store"):
                stores = ions.data(changed.stores)
                if case == "missing_event_store":
                    del stores["Dm_scheduled"]
                else:
                    stores["D_env_weight"] = np.zeros_like(stores["D_env_weight"])
                changed = replace(changed, stores=ions.freeze(stores))
            elif case == "changed_entry_receipt":
                receipt = ions.data(changed.entry_receipt)
                receipt["source_control_initializations"] = 2
                changed = replace(changed, entry_receipt=ions.freeze(receipt))
            elif case == "changed_entry_material":
                values = ions.data(changed.network.material.values._asdict())
                values["cell_mol_m3"] = np.asarray(values["cell_mol_m3"]) * 1.01
                mat = joined.material.state(changed.runtime_material_binding, values, step_index=0)
                net = joined.network._state(
                    binding, mat, changed.network.network_cache, changed.network.controls
                )
                changed = replace(changed, network=net)
            else:
                saved = ions.data(changed.network.network_cache)
                if case == "missing_owner_cache":
                    saved["handlers"]["molecules"] = None
                else:
                    fields = saved["handlers"]["molecules"]["cache"]["wire"]["transporter_fields"]
                    fields[next(iter(fields))]["flux"] = np.zeros(1)
                net = joined.network._state(
                    binding, changed.network.material, saved, changed.network.controls
                )
                changed = replace(changed, network=net)
            changed = replace(changed, identity="")
            changed = replace(changed, identity=ions.digest(joined.record(changed)))
            challenge["changed"] = changed

            def action():
                return joined.verify(binding, changed)
        elif case == "failed_resume":

            def fail(stage, value):
                raise RuntimeError("Declared pre-call failure")

            with pytest.raises(joined.EventsRejected) as caught:
                retained(
                    tmp_path,
                    case + "-failure",
                    lambda: joined.advance(binding, parent, observer=fail),
                    parent=parent,
                )
            parent = caught.value.partial["accepted"]

            def action():
                return joined.resume(binding, parent)
        elif case in ("boolean_stop", "stop_before_cursor", "stop_past_cap"):
            stop = True if case == "boolean_stop" else 0 if case == "stop_before_cursor" else 4

            def action():
                return joined.run_window(binding, parent, stop=stop)
        else:

            def action():
                return joined.verify(binding, parent)

        challenge.update(binding=binding, parent=parent)
    archive(tmp_path, case + "-challenged-input-before-classification", challenge)
    with pytest.raises((ValueError, joined.EventsRejected)):
        retained(tmp_path, case + "-dependency", action, challenge=challenge)


def phase_clock(parent, index):
    return joined.phase.Clock(
        parent.clock.source_times_s, index, index * parent.clock.material_dt_sum_s
    )
