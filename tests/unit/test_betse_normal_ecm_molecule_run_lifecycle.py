"""Held headless molecule runs; conditional science remains entirely prospective."""

import os
from dataclasses import replace
from types import SimpleNamespace

import pytest

from cells.processes import betse_normal_ecm_molecule_lifecycle as leaf
from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run
from cells.processes import betse_normal_ion_join as ions
from tests.unit import test_betse_ecm_grn_join as chemistry
from tests.unit import test_betse_normal_ecm_catalog_join as catalog
from tests.unit import test_betse_normal_ecm_field_join as fields
from tests.unit import test_betse_normal_ecm_init_phase as initialized
from tests.unit import test_betse_normal_ecm_init_sim_transition as transitioned
from tests.unit import test_betse_normal_ecm_molecule_run_lifecycle_capture as capture
from tests.unit import test_betse_normal_ecm_molecule_run_lifecycle_comparisons as compare
from tests.unit import test_betse_normal_ecm_molecule_transport as transported
from validation.betse import betse_normal_ecm_molecule_failure_checks as failures
from validation.betse import betse_normal_ecm_molecule_run_lifecycle_fixtures as fixtures

MODES = ("nak", "material", "calcium", "mechanics", "commit", "field")
archive, check, refs, native = (
    capture.archive,
    capture.check,
    capture.references,
    capture.isolated,
)
exact = fields.exact


@pytest.fixture(autouse=True)
def explicit_release():
    if os.environ.get("CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED") != "1":
        pytest.skip("Held source proposal; Chief must explicitly release this suite")


def retained(tmp, name, operation, **readers):
    return failures.retained_call(
        operation,
        stage=name,
        readers={key: lambda value=value: value for key, value in readers.items()},
        retain=lambda value: archive(tmp, name + "-outcome", value),
    )


def retained_preparation(tmp, name, operation, **readers):
    """Retain the exact preparation request before any evolving call."""
    archive(tmp, name + "-request", readers)
    return retained(tmp, name, operation, **readers)


def initial(tmp, case, *, checked=False):
    raw = fixtures.init_inputs(case)
    archive(tmp, case + "-INIT-raw", raw)
    declaration = leaf.init.bind(raw)
    seen, forms = ({}, {})
    folder = capture.root(tmp) / (case + "-entry")
    folder.mkdir(parents=True, exist_ok=False)

    def setup(value):
        seen["setup"] = value
        archive(tmp, case + "-setup", value)
        if checked:
            ids = declaration.base.material_binding.geometry_binding.current_binding.ion_ids
            forms["setup"] = refs(
                folder / "setup",
                dict(mode="setup", setup_return=value, ion_ids=list(ids), source_phase="INIT"),
            )

    def cold(value):
        seen["cold"] = value
        archive(tmp, case + "-cold", value)

    def handler(role, stage, value):
        archive(tmp, case + "-cold-" + role + "-" + stage, value)
        if checked and role == "all":
            seen["native"] = native(folder / "native", value)

    def bootstrap(value):
        archive(tmp, case + "-INIT-bootstrap-input", value)
        if checked:
            forms["field"] = refs(folder / "field", dict(ions.data(value), source_phase="INIT"))

    binding, entry = retained(
        tmp,
        case + "-actual-INIT-setup",
        lambda: leaf.init.initialize(
            declaration,
            after_setup=setup,
            after_cold=cold,
            handler_observer=handler,
            before_field=bootstrap,
        ),
        declaration=declaration,
    )
    declared = fixtures.declaration(case, binding)
    outer = run.bind(declared, binding)
    receipt = run.entry_receipt(
        outer,
        entry,
        provenance="Actual supplied molecule54 setup return; begin performs no setup producer",
    )
    parent = run.begin(outer, entry, receipt)
    archive(tmp, case + "-INIT-begin", dict(binding=outer, parent=parent))
    assert parent.active is entry and parent.entry is entry and (parent.cursor == 0)
    if checked:
        check(
            tmp,
            case + "-setup-errors",
            folder / "setup",
            initialized.setup_rows(seen["setup"], *forms["setup"]),
        )
        check(
            tmp,
            case + "-INIT-bootstrap-errors",
            folder / "field",
            fields.compare_field(binding, entry.field, *forms["field"]),
        )
        actual = seen["cold"]
        captured = seen["native"]
        assert captured["status"] == "source_completed"
        exact(actual["material"], captured["returned"]["material"])
        for role in leaf.owners.ROLES:
            saved = actual["network_cache"]["handlers"][role]
            if saved is None:
                assert captured["returned"]["handlers"][role] is None
                continue
            exact(saved["cache"], captured["returned"]["handlers"][role])
            incoming = transported.cold_input(raw["owners"], role)
            incoming.update(source_phase="INIT", time_profile=raw["time_profile"])
            answer = refs(folder / role, incoming)
            check(
                tmp,
                case + "-cold-" + role,
                folder / role,
                chemistry.compare_cold(
                    binding, SimpleNamespace(network_cache=saved["cache"]), *answer
                ),
            )
    return (outer, parent)


def actual_binding(binding, parent):
    return (
        binding.composition
        if run.composition.kind(binding.composition) == "INIT"
        else parent.active.phase_binding
    )


def checked_calls(tmp, name, binding, parent):
    folder = capture.root(tmp) / name
    folder.mkdir(parents=True, exist_ok=False)
    phase_binding = actual_binding(binding, parent)
    kind = run.composition.kind(binding.composition)
    clock = refs(
        folder / "clock",
        dict(
            mode="clock", time_profile=phase_binding.inputs_raw["time_profile"], source_phase=kind
        ),
    )
    while parent.status == "ready":
        index = parent.cursor
        point = folder / ("call-" + str(index))
        point.mkdir()
        answers, observed, captured = ({}, {}, {})

        def before(mode, index=index, point=point, answers=answers, observed=observed):

            def callback(value):
                incoming = dict(ions.data(value), source_phase=kind, legacy_run_sim=kind == "SIM")
                archive(tmp, name + "-" + str(index) + "-" + mode + "-input", incoming)
                observed[mode] = incoming
                answers[mode] = refs(point / mode, incoming)

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
            archive(tmp, name + "-" + str(index) + "-" + role + "-" + stage, value)
            if role == "all":
                captured["native"] = native(point / "native", value)
            elif stage in ("channels", "network", "transporters"):
                key = role + "-" + stage
                observed[key] = ions.data(value)
                answers[key] = refs(point / key, value)

        previous = parent
        digest = ions.digest(parent)
        parent, detail = retained(
            tmp,
            name + "-advance-" + str(index),
            lambda previous=previous: run.advance(
                binding,
                previous,
                handler_observer=handler,
                **{"before_" + mode: before(mode) for mode in MODES},
            ),
            parent=previous,
        )
        archive(tmp, name + "-return-" + str(index), dict(parent=parent, detail=detail))
        assert ions.digest(previous) == digest and parent.cursor == index + 1
        actual = run.composition.phase_state(parent.active)
        compare.check_handlers(
            tmp,
            name + "-" + str(index),
            point,
            phase_binding,
            actual,
            detail,
            answers,
            captured["native"],
            observed,
        )
        for mode, rows in (
            ("nak", initialized.nak_rows(detail["nak"], *answers["nak"])),
            ("material", transported.prefix_rows(detail["material_trial"], *answers["material"])),
            ("calcium", catalog.compare_calcium(detail["calcium"], *answers["calcium"])),
            ("commit", transported.commit_rows(detail["material_trial"], *answers["commit"])),
            ("field", fields.compare_field(phase_binding, actual.field, *answers["field"])),
        ):
            check(tmp, name + "-" + str(index) + "-" + mode, point / mode, rows)
        for form in answers["mechanics"]:
            exact(
                ions.data(detail["mechanics_trial"].candidate.cache),
                form["history"][0]["candidate"],
            )
        compare.sample_contract(phase_binding, actual, clock)
        assert len(parent.history) == parent.cursor
        assert [o.call_index for o in parent.observations] == [
            o["call_index"] for o in actual.observations
        ]
        assert all(
            (
                o.state.identity == parent.history[o.call_index].after_identity
                for o in parent.observations
            )
        )
    compare.sample_contract(phase_binding, run.composition.phase_state(parent.active), clock)
    return parent


def duplicate_windows(tmp, binding, entry, case, phase):
    current = entry
    for index, stop in enumerate(fixtures.stops(case, binding.calendar.step_count)):
        current, _ = retained_preparation(
            tmp,
            case + "-" + phase + "-duplicate-window-" + str(index),
            lambda current=current, stop=stop: run.run_window(binding, current, stop=stop),
            binding=binding,
            parent=current,
            stop=stop,
        )
    assert current.status == "exhausted"
    return current


@pytest.mark.parametrize("case", fixtures.CASES)
def test_complete_run(tmp_path, case):
    init_binding, entry = initial(tmp_path, case, checked=True)
    original = ions.digest(entry)
    init_run = checked_calls(tmp_path, case + "-INIT", init_binding, entry)
    assert init_run.status == "exhausted" and ions.digest(entry) == original
    duplicate = duplicate_windows(tmp_path, init_binding, entry, case, "INIT")
    exact(ions.data(duplicate), ions.data(init_run))
    completed = run.complete_INIT(init_binding, init_run)
    archive(tmp_path, case + "-complete-INIT-run", completed)
    raw = fixtures.sim_inputs(case, completed.complete_init)
    archive(tmp_path, case + "-SIM-input", raw)
    component = leaf.bind(raw)
    declared = fixtures.declaration(case, component)
    folder = capture.root(tmp_path) / (case + "-transition")
    folder.mkdir()
    seen, bootstrap = ({}, [])

    def observer(stage, value):
        seen[stage] = value
        archive(tmp_path, case + "-transition-" + stage, value)

    def field(value):
        bootstrap.extend(refs(folder / "bootstrap", dict(ions.data(value), source_phase="SIM")))

    binding, parent = retained(
        tmp_path,
        case + "-headless-handoff",
        lambda: run.transition(
            init_binding,
            init_run,
            component,
            declared,
            provenance="Actual complete headless INIT run and retained molecule54 transition",
            observer=observer,
            before_field=field,
        ),
        init_run=init_run,
        completed=completed,
    )
    archive(tmp_path, case + "-SIM-begin", dict(binding=binding, parent=parent))
    assert (
        parent.cursor == 0 and parent.entry_receipt["previous_phase"].identity == completed.identity
    )
    assert parent.active.source_init.identity == completed.complete_init.identity
    native_return = native(folder / "native", seen["before_dual_reinitialize"])
    actual = seen["dual_owners_reinitialized"]["available"]
    assert native_return["status"] == "source_completed"
    exact(actual["material"], native_return["returned"]["material"])
    for role in leaf.owners.ROLES:
        saved = actual["owners"]["handlers"][role]
        exact(
            None if saved is None else saved["cache"], native_return["returned"]["handlers"][role]
        )
        identity = seen["dual_owners_reinitialized"]["owner_identity"][role]
        if saved is not None:
            assert (
                identity["owner_retained"]
                and identity["core_retained"]
                and all(identity["molecule_objects_retained"].values())
            )
            assert all(identity["transporter_objects_rebuilt"].values()) and all(
                (v is None for v in identity["transporter_fluxes_after"].values())
            )
    forms = refs(
        folder / "phase-rules", compare.phase_rules_input(raw, completed.complete_init, seen)
    )
    adjusted = dict(seen)
    adjusted["post_static"] = dict(
        seen["post_static"],
        available=dict(
            seen["post_static"]["available"],
            simulator_fields=seen["post_static"]["available"]["simulator_arrays"],
        ),
    )
    check(
        tmp_path,
        case + "-phase-rules-errors",
        folder / "phase-rules",
        transitioned.phase_rows(adjusted, *forms),
    )
    check(
        tmp_path,
        case + "-SIM-bootstrap-errors",
        folder / "bootstrap",
        fields.compare_field(parent.active.phase_binding, parent.active.active.field, *bootstrap),
    )
    sim_entry = parent
    init_digest = ions.digest(init_run)
    parent = checked_calls(tmp_path, case + "-SIM", binding, parent)
    duplicate = duplicate_windows(tmp_path, binding, sim_entry, case, "SIM")
    exact(ions.data(parent), ions.data(duplicate))
    assert (
        parent.cursor == 3
        and parent.status == "exhausted"
        and (ions.digest(init_run) == init_digest)
    )
    assert parent.entry_receipt["previous_phase"].run.identity == init_run.identity
    archive(
        tmp_path,
        case + "-summary",
        dict(
            INIT_calls=init_run.cursor,
            SIM_calls=3,
            full_phase_carry=True,
            duplicate_window_baseline_new_credit=0,
            native_storage_called=False,
            independently_carried_reference_trajectory=False,
            physical_global_conservation_credit=False,
        ),
    )


@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_retained_source_failure(tmp_path, case):
    binding, parent = initial(tmp_path, case)
    seen = {}
    folder = capture.root(tmp_path) / (case + "-raw")
    folder.mkdir()
    if case.startswith("warm_"):
        init_run, _ = retained_preparation(
            tmp_path,
            case + "-warm-INIT-preparation",
            lambda: run.run_window(binding, parent, stop=binding.calendar.step_count),
            binding=binding,
            parent=parent,
            stop=binding.calendar.step_count,
        )
        complete = run.complete_INIT(binding, init_run)
        raw = fixtures.sim_inputs(case, complete.complete_init)
        component = leaf.bind(raw)
        with pytest.raises(run.RunRejected) as caught:
            retained(
                tmp_path,
                case + "-warm",
                lambda: run.transition(
                    binding,
                    init_run,
                    component,
                    fixtures.declaration(case, component),
                    provenance="Declared warm raw failure",
                    observer=lambda stage, value: seen.update({stage: value}),
                ),
                parent=init_run,
                binding=binding,
                component=component,
                raw=raw,
                seen=seen,
            )
        error = caught.value
        captured = native(folder / "native", seen["before_dual_reinitialize"])
        assert (
            captured["status"] == "source_refused"
            and failures.exception_chain(error)[-1]["type"] == "KeyError"
        )
        assert captured["failure"]["type"] == "KeyError"
        assert (
            failures.exception_chain(error)[-1]["message"]
            == captured["failure"]["message"]
            == "'max rate'"
        )
        component_partial = error.partial["component_partial"]
        inner = component_partial["inner_partial"]
        exact(inner["available"]["partial_wires"], captured["partial_buffers"]["partial_wires"])
        assert not component_partial["automatic_retry"] and not error.partial["automatic_retry"]
        assert error.partial["accepted_INIT_run"].identity == init_run.identity
    else:

        def handler(role, stage, value):
            if role == "all":
                seen["native"] = native(folder / "native", value)

        with pytest.raises(run.RunRejected) as caught:
            retained(
                tmp_path,
                case + "-advance",
                lambda: run.advance(binding, parent, handler_observer=handler),
                parent=parent,
            )
        error = caught.value
        assert [r["type"] for r in failures.exception_chain(error)] == [
            "RunRejected",
            "InitRejected",
            "ECMTransportRejected",
            "BetseSimUnstableException",
        ]
        failed = error.partial["accepted"]
        run.verify(binding, failed)
        assert failed.status == "failed" and failed.cursor == parent.cursor == 0
        partial = error.partial["component_partial"]
        assert (
            partial["reached_stage"] == "network" and seen["native"]["status"] == "source_refused"
        )
        exact(partial["owner_buffers"]["material"], seen["native"]["partial_buffers"]["material"])
        exact(
            partial["owner_buffers"]["partial_wires"],
            seen["native"]["partial_buffers"]["partial_wires"],
        )
        native_return = seen["native"]
        chain = failures.exception_chain(error)
        message = (
            "Network concentration of X in cells below zero! Your simulation has become unstable."
        )
        assert chain[-1]["message"] == native_return["failure"]["message"] == message
        assert native_return["failure"]["type"] == "BetseSimUnstableException"
        assert native_return["failure_capture"]
        assert partial["root_cause"]["type"] == "ECMTransportRejected"
        assert partial["stage"] == "material_calcium_network_mechanics"
        assert partial["call_index"] == 0
        buffers = partial["owner_buffers"]
        exact(buffers["source_order"], native_return["order"])
        role = "molecules" if "general" in case else "grn"
        trace = buffers["traces"][role]
        target = [row for row in trace["mover_frames"] if row["species"] == "X"]
        assert target[-1]["stage"] == "environment_mix"
        assert any(value < 0 for value in target[-1]["fields"]["cX_cells"])
        for owner in leaf.owners.ROLES:
            for key in (
                "molecule_frames", "mover_frames", "channel_events", "rhs", "control_writes"
            ):
                exact(buffers["traces"][owner][key], native_return["traces"][owner][key])
        general = buffers["traces"]["molecules"]["transporter_frames"]
        exact(general, native_return["traces"]["molecules"]["transporter_frames"])
        raw = binding.composition.inputs_raw
        configured = raw["owners"]["handlers"]["molecules"]["network"]["configuration"][
            "transporters"
        ]
        assert [(row["stage"], row["name"]) for row in general] == [
            (stage, row["name"])
            for row in configured
            for stage in ("before", "flux", "current", "reactant_commit", "product_commit", "after")
        ]
        ion_ids = raw["field"]["definition"]["environment_geometry_definition"][
            "current_definition"
        ]["ions"]["ids"]
        assert [(row["stage"], row["species"]) for row in trace["molecule_frames"]] == (
            [("molecule_intra", "X"), ("molecule_intra", "Y"), ("rhs_ready", None)]
            + [("chemical_commit", ion) for ion in ion_ids]
            + [("chemical_commit", "X"), ("transport_before", "X")]
        )
    archive(
        tmp_path,
        case + "-complete-failure-prefix",
        dict(partial=error.partial, chain=failures.exception_chain(error), native=seen),
    )


@pytest.mark.parametrize("case", fixtures.OBSERVER_CASES)
def test_observer_failure_prefix(tmp_path, case):
    binding, parent = initial(tmp_path, case)
    if case == "headless_observation":
        parent, _ = retained_preparation(
            tmp_path,
            case + "-observer-preparation",
            lambda: run.advance(binding, parent),
            binding=binding,
            parent=parent,
        )
    prior = parent
    seen = {}

    def observer(stage, value):
        seen[stage] = value
        if stage == case:
            raise RuntimeError("Declared headless observer failure")

    def phase_observer(stage, value):
        seen["phase_" + stage] = value
        if stage == "after_call":
            raise RuntimeError("Declared leaf observer failure after actual leaf acceptance")

    with pytest.raises(run.RunRejected) as caught:
        retained(
            tmp_path,
            case + "-observer",
            lambda: run.advance(
                binding,
                parent,
                observer=None if case == "phase_after_call" else observer,
                phase_observer=phase_observer if case == "phase_after_call" else None,
            ),
            parent=prior,
        )
    partial = caught.value.partial
    failed = partial["accepted"]
    run.verify(binding, failed)
    assert failed.status == "failed"
    assert failed.cursor == prior.cursor + (case in ("accepted_call", "headless_observation"))
    if case == "phase_after_call":
        assert seen["phase_after_call"].cursor == prior.cursor + 1
        assert (
            partial["component_partial"]["available"]["accepted"].identity
            == seen["phase_after_call"].identity
        )
    archive(tmp_path, case + "-observer-prefix", dict(partial=partial, seen=seen))


@pytest.mark.parametrize("case", fixtures.PREFIX_CASES)
def test_incomplete_INIT_handoff(tmp_path, case):
    binding, parent = initial(tmp_path, case)
    if case == "failed_INIT":
        with pytest.raises(run.RunRejected) as failure:
            retained(
                tmp_path, case + "-source", lambda: run.advance(binding, parent), parent=parent
            )
        parent = failure.value.partial["accepted"]
    else:
        parent, _ = retained_preparation(
            tmp_path,
            case + "-incomplete-INIT-preparation",
            lambda: run.run_window(binding, parent, stop=1 if case == "paused_INIT" else 3),
            binding=binding,
            parent=parent,
            stop=1 if case == "paused_INIT" else 3,
        )
    with pytest.raises(run.RunRejected) as caught:
        retained(
            tmp_path,
            case + "-completion",
            lambda: run.complete_INIT(binding, parent),
            parent=parent,
        )
    archive(tmp_path, case + "-handoff-refused", caught.value.partial)


@pytest.mark.parametrize("case", fixtures.DEPENDENCIES)
def test_run_dependency(tmp_path, case):
    binding, parent = initial(tmp_path, "capped_INIT" if case == "stop_past_cap" else case)
    raw = fixtures.declaration(case, binding.composition)
    action = None
    challenge = {}
    if case in (
        "foreign_component_binding",
        "changed_time_profile",
        "wrong_phase",
        "native_persistence",
        "native_display",
        "invalid_stop_policy",
    ):
        if case == "foreign_component_binding":
            raw["component_binding_identity"] = "foreign"
        elif case == "changed_time_profile":
            raw["time_profile"]["sim_dt_s"] *= 2
        elif case == "wrong_phase":
            raw["time_profile"]["phase"] = "SIM"
        elif case == "native_persistence":
            raw["persistence"] = "pickle"
        elif case == "native_display":
            raw["observation_mode"] = "native_display"
        else:
            raw["stop_policy"] = "arbitrary_time"

        def action():
            return run.bind(raw, binding.composition)
    elif case in ("foreign_entry", "entry_advanced", "entry_paused", "entry_receipt_changed"):
        entry = parent.active
        if case == "foreign_entry":
            entry = replace(entry, binding_identity="foreign")
        elif case == "entry_advanced":
            entry, _ = retained_preparation(
                tmp_path,
                case + "-advanced-entry-preparation",
                lambda: leaf.init.advance(binding.composition, entry),
                binding=binding.composition,
                parent=entry,
            )
        elif case == "entry_paused":
            entry = leaf.init.pause(binding.composition, entry)
        receipt = run.entry_receipt(binding, entry, provenance="Explicit challenged entry")
        if case == "entry_receipt_changed":
            receipt = ions.freeze(dict(ions.data(receipt), phase="SIM"))
        challenge.update(entry=entry, receipt=receipt)

        def action():
            return run.begin(binding, entry, receipt)
    elif case in ("missing_owner_cache", "changed_transporter_cache"):
        active = parent.active
        saved = ions.data(active.network.network_cache)
        if case == "missing_owner_cache":
            saved["handlers"]["molecules"] = None
        else:
            saved["handlers"]["molecules"]["cache"]["wire"]["transporter_fields"] = {}
        net = leaf.network._state(
            binding.composition, active.network.material, saved, active.network.controls
        )
        active = replace(active, network=net, identity="")
        active = replace(active, identity=ions.digest(leaf.init.record(active)))
        changed = run._state(
            binding,
            parent.entry,
            parent.entry_receipt,
            active,
            parent.history,
            parent.observations,
            parent.status,
        )
        challenge["changed_run"] = changed

        def action():
            return run.verify(binding, changed)
    elif case in ("changed_binding", "changed_run"):
        if case == "changed_binding":
            binding = replace(binding, identity="foreign")
        else:
            parent = replace(parent, status="paused")

        def action():
            return run.verify(binding, parent)
    elif case in ("changed_journal", "rebased_source_label", "changed_observation"):
        stop = 2 if case == "changed_observation" else 1
        parent, _ = retained_preparation(
            tmp_path,
            case + "-journal-preparation",
            lambda: run.run_window(binding, parent, stop=stop),
            binding=binding,
            parent=parent,
            stop=stop,
        )
        history = list(parent.history)
        observations = list(parent.observations)
        if case == "changed_journal":
            history[0] = replace(history[0], dt_s=history[0].dt_s * 2)
        elif case == "rebased_source_label":
            history[0] = replace(history[0], source_label_s=1e-06)
        else:
            observations[0] = replace(observations[0], native_write2storage_called=True)
        changed = run._state(
            binding,
            parent.entry,
            parent.entry_receipt,
            parent.active,
            history,
            observations,
            parent.status,
        )
        challenge["changed_run"] = changed

        def action():
            return run.verify(binding, changed)
    elif case in ("foreign_previous_phase", "changed_completed_INIT"):
        parent, _ = retained_preparation(
            tmp_path,
            case + "-completed-INIT-preparation",
            lambda: run.run_window(binding, parent, stop=3),
            binding=binding,
            parent=parent,
            stop=3,
        )
        completed = run.complete_INIT(binding, parent)
        if case == "changed_completed_INIT":
            changed = replace(completed, identity="foreign")
            challenge["changed_completed_INIT"] = changed

            def action():
                return run.verify_completed_INIT(changed)
        else:
            other_binding, other = initial(tmp_path, "one_INIT_call")
            other, _ = retained_preparation(
                tmp_path,
                case + "-foreign-INIT-preparation",
                lambda: run.run_window(other_binding, other, stop=1),
                binding=other_binding,
                parent=other,
                stop=1,
            )
            foreign = run.complete_INIT(other_binding, other)
            component = leaf.bind(fixtures.sim_inputs(case, completed.complete_init))
            entry = retained_preparation(
                tmp_path,
                case + "-foreign-transition-preparation",
                lambda: leaf.transition(component, completed.complete_init),
                component=component,
                completed=completed.complete_init,
            )
            sim = run.bind(fixtures.declaration(case, component), component)
            challenge.update(completed=completed, foreign=foreign, entry=entry, binding=sim)

            def action():
                return run.entry_receipt(
                    sim, entry, provenance="Challenged prior run", previous_phase=foreign
                )
    elif case in ("boolean_stop", "stop_before_cursor", "stop_past_cap", "terminal_step"):
        if case == "stop_before_cursor":
            parent, _ = retained_preparation(
                tmp_path,
                case + "-stop-cursor-preparation",
                lambda: run.advance(binding, parent),
                binding=binding,
                parent=parent,
            )
        elif case == "terminal_step":
            parent, _ = retained_preparation(
                tmp_path,
                case + "-terminal-preparation",
                lambda: run.run_window(binding, parent, stop=3),
                binding=binding,
                parent=parent,
                stop=3,
            )
        if case == "terminal_step":

            def action():
                return run.advance(binding, parent)
        else:
            stop = True if case == "boolean_stop" else 0 if case == "stop_before_cursor" else 4
            challenge["stop"] = stop

            def action():
                return run.run_window(binding, parent, stop=stop)
    elif case == "failed_resume":

        def observer(stage, value):
            raise RuntimeError("Declared before-call observer failure")

        with pytest.raises(run.RunRejected) as caught:
            retained(
                tmp_path,
                case + "-fail",
                lambda: run.advance(binding, parent, observer=observer),
                parent=parent,
            )
        parent = caught.value.partial["accepted"]

        def action():
            return run.resume(binding, parent)

    assert action is not None
    archive(
        tmp_path,
        case + "-challenged-run-input",
        dict(binding=binding, parent=parent, raw=raw, challenge=challenge),
    )
    with pytest.raises((ValueError, run.RunRejected)) as caught:
        retained(
            tmp_path,
            case + "-dependency",
            action,
            binding=binding,
            parent=parent,
            raw=raw,
            challenge=challenge,
        )
    archive(
        tmp_path,
        case + "-dependency-refusal",
        dict(
            type=type(caught.value).__name__,
            message=str(caught.value),
            partial=getattr(caught.value, "partial", None),
        ),
    )
