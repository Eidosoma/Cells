"""Prepare a held selected-temporal original-source and restart comparison.

No parent is obtained from a fixture or reconstructed by this preparer. Actual
execution needs an exhausted retained typed INIT parent, exact external parent
identities, genuine supplied event inputs and the existing releases. Metadata
can report the missing authorities and callback ABI without entering a model.
"""

import sys
from pathlib import Path

from cells.processes import betse_normal_ecm_molecule_checkpoint as checkpoint
from cells.processes import betse_normal_ecm_molecule_event_owner as bridge
from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run
from validation import source_snapshot as snapshot
from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation
from validation.betse import betse_normal_ecm_molecule_event_checkpoint as event_checks
from validation.betse import betse_normal_ecm_molecule_periodic_checkpoint as periodic
from validation.betse import betse_normal_ecm_molecule_sweep_checkpoint as sweep
from validation.betse import betse_normal_ecm_molecule_temporal_config_checkpoint as selected
from validation.betse import betse_normal_ecm_molecule_temporal_reference as reference
from validation.betse.betse_normal_ecm_init_phase_capture import record_failure
from validation.betse.betse_normal_ecm_molecule_handoff_run_plugin import Calls

OWNED = (
    "validation/betse/betse_normal_ecm_molecule_temporal_reference.py",
    "validation/betse/betse_normal_ecm_molecule_temporal_continuity.py",
    "tests/unit/test_betse_normal_ecm_molecule_temporal_reference.py",
    "tests/unit/test_betse_normal_ecm_molecule_temporal_continuity.py",
)
READERS = (
    "validation/perturbations/time_modulation_native.py",
    "validation/perturbations/time_modulation_reference.py",
)
require = reference.require


def ref(path):
    path = Path(path).resolve(strict=True)
    return dict(path=str(path), sha256=snapshot.digest(path))


def request(configuration, scenario, cut):
    configured = selected.temporal.check_configuration(configuration)
    choices = periodic.SCENARIOS if configured["family"] == "periodic" else sweep.SCENARIOS
    require(
        scenario in choices and type(cut) is int and cut in (1, 2),
        "Original selected temporal scenario and cut required",
    )
    return dict(configuration=lifecycle.ions.data(configured), scenario=scenario, cut=cut)


def preflight(
    init_binding,
    init_parent,
    event_owner_inputs,
    *,
    expected_binding_identity,
    expected_parent_identity,
):
    """Structural prerequisites only, never a substitute for run.verify."""
    require(
        type(init_binding) is run.Binding
        and type(init_binding.composition) is lifecycle.init.Binding,
        "Missing actual retained INIT binding; fixture/supplied dictionaries are not parents",
    )
    require(
        type(init_parent) is run.RunState and type(init_parent.active) is lifecycle.init.State,
        "Missing actual retained INIT run parent",
    )
    owner, active = init_binding.composition, init_parent.active
    calendar = owner.calendar
    require(
        type(calendar) is run.calendars.NativePhaseCalendar
        and calendar.phase == "INIT"
        and type(calendar.step_count) is int
        and 0 <= calendar.step_count <= 3,
        "Foreign INIT phase/calendar authority",
    )
    require(
        type(expected_binding_identity) is str
        and bool(expected_binding_identity)
        and type(expected_parent_identity) is str
        and bool(expected_parent_identity)
        and init_binding.identity == init_parent.binding_identity == expected_binding_identity
        and init_parent.identity == expected_parent_identity
        and active.binding_identity == owner.identity,
        "Foreign expected INIT binding/parent",
    )
    require(
        type(active.clock) is lifecycle.init.Clock
        and type(active.clock.call_index) is int
        and active.clock.call_index == calendar.step_count == owner.call_limit
        and init_parent.status == active.status == "exhausted",
        "Failed/paused/capped/incomplete INIT is not a transition parent",
    )
    supplied = bridge.check_inputs(event_owner_inputs, expected_INIT=owner.identity)
    require(
        supplied.source_geometry_binding_identity
        == owner.material_binding.geometry_binding.identity,
        "Foreign actual INIT geometry/event-input authority",
    )
    return dict(
        binding=init_binding.identity,
        parent=init_parent.identity,
        source_INIT=owner.identity,
        cursor=active.clock.call_index,
        phase="INIT",
        numeric_admission=False,
        required_next="existing run ownership validation and complete_INIT",
    )


def prepare(
    repository,
    directory,
    *,
    source_selection,
    configuration,
    scenario,
    cut,
    native_root=reference.NATIVE_ROOT,
):
    """One-way checkout snapshot and explicit held prerequisites, no admission."""
    declared = request(configuration, scenario, cut)
    selection_path = Path(source_selection).resolve(strict=True)
    previous = snapshot.verify(
        selection_path.parent, manifest_sha256=snapshot.digest(selection_path)
    )
    files = {name: row["checkout_path"] for name, row in previous["files"].items()}
    require(
        all(name == value for name, value in files.items()),
        "Historical source overlays are refused",
    )
    files.update({name: name for name in (*OWNED, *READERS)})
    repository = Path(repository).resolve(strict=True)
    directory = Path(directory).absolute()
    resolved = directory.resolve()
    require(
        not resolved.is_relative_to(repository)
        and not resolved.is_relative_to(selection_path.parent),
        "Preparation output must be outside checkout and frozen source selection",
    )
    directory.mkdir(parents=True, exist_ok=False)
    try:
        manifest = snapshot.freeze(repository, directory / "source", files)
        producer = checkpoint.producer_identity()
        for name, pin in producer["source_hashes"].items():
            require(
                manifest["files"].get("src/cells/" + name, {}).get("sha256") == pin,
                "Source selection omits or changes the actual checkpoint producer: " + name,
            )
        plan = reference.source_plan(native_root)
        source_delta = {
            name: dict(
                previous=previous["files"].get(name, {}).get("sha256"), candidate=row["sha256"]
            )
            for name, row in manifest["files"].items()
            if row["sha256"] != previous["files"].get(name, {}).get("sha256")
        }
        inputs = dict(
            kind="cells.held_selected_temporal_paired_continuity@1",
            request=declared,
            snapshot=ref(directory / "source/SNAPSHOT.json"),
            selection_only=ref(selection_path),
            source_delta=source_delta,
            source_plan=plan,
            expected_checkpoint_producer=producer,
            parent_authority=dict(
                supplied=False,
                INIT_binding=None,
                INIT_parent=None,
                typed_event_Inputs=None,
                admission=False,
            ),
            held=True,
            automatic_launch=False,
            actual_runs=0,
            independent_biological_cases=0,
            required_releases=reference.RELEASES,
            source_runtime_review="Root pending",
            numerical_prerequisites=[
                "actual exhausted retained INIT and matching typed Inputs",
                "existing numeric ownership/complete_INIT admission",
                "compatible actual callback and observer result ABI",
                "Root source/runtime review, releases and resource/launch plan",
            ],
            missing_now=["no actual INIT/SIM parent or input authority supplied"]
            + ([] if plan["callback_abi"]["compatible"] else ["callback_result_ABI"]),
            real_scientific_resource_plan=None,
            scope="original selected stores/factory/time-law slice plus full owned run restart; "
            "not full native Parameters/YAML/physical or biological admission",
        )
        snapshot.write_json(directory / "inputs.json", inputs)
        return inputs
    except BaseException as error:
        record_failure(
            error,
            stage="prepare-selected-temporal-continuity",
            readers={"request": lambda: declared, "source_selection": lambda: str(selection_path)},
            retain=lambda v: snapshot.write_json(directory / "failure.json", v),
        )
        raise


def observe(binding, parent, anchor):
    """Reuse actual ownership/journal checks and retain complete state seals."""
    run.verify(binding, parent)
    component = binding.composition
    fp = checkpoint.codec.fingerprint
    value = dict(
        phase=run.composition.kind(component),
        event_binding=component.identity,
        source_binding=component.source_binding.identity,
        source_entry=component.source_entry.identity,
        source_INIT=component.source_entry.source_init.identity,
        calendar=binding.calendar.identity,
        event_owner=run.ions.digest(component.raw["event_owner"]),
        cursor=parent.cursor,
        active_state=parent.active.identity,
        samples=[o.call_index for o in parent.observations],
        owned_RNG=fp(
            (
                component.base.setup_receipt["numpy_rng_after"],
                component.base.setup_receipt["event_finalization"]["python_rng_after"],
            )
        ),
        rows=[],
    )
    for outer, inner in zip(parent.history, parent.active.history, strict=True):
        trace = inner["event_trace"]
        require(trace["source_time_s"] == outer.source_label_s, "Changed event/phase source clock")
        value["rows"].append(
            dict(
                call_index=outer.call_index,
                label=outer.source_label_s,
                phase=inner["source_phase"],
                legacy_run_sim=inner["legacy_run_sim"],
                event_owner=inner["event_owner_identity"],
                event_fire_calls=inner["event_fire_calls"],
                flux_resets=inner["pre_event_flux_reset_calls"],
                noise_calls=inner["protein_noise_calls"],
                stages=[s["stage"] for s in trace["stages"]],
                source_completed=trace["source_completed"],
                before_state=outer.before_identity,
                after_state=outer.after_identity,
                T_before=fp(trace["before"]["T"]),
                T_after=fp(trace["after"]["T"]),
            )
        )
    event_checks.check_observation(value, anchor)
    value.update(
        full_graph=fp((binding, parent)),
        source_publication=fp(component.source_entry.receipt),
        full_event_owner=fp(component.raw["event_owner"]),
        all_stores=fp(parent.active.stores),
        material_owner_caches=fp(parent.active.network),
        rate_cache=fp(parent.active.rate_cache),
        field=fp(parent.active.field),
        runtime_definition=fp(parent.active.runtime_definition),
    )
    return value


def _checkpoint_call(take, name, operation):
    # Receipt has an operational Path, converted explicitly; the scientific
    # binding/state graph remains in its existing closed checkpoint codec.
    returned = None

    def perform():
        nonlocal returned
        returned = operation()
        receipt = returned.receipt if type(returned) is checkpoint.Loaded else returned
        require(
            type(receipt) is checkpoint.Receipt
            and type(receipt.verification_attempts) is int
            and receipt.verification_attempts > 0,
            "Require the actual checkpoint receipt and recorded ownership attempts",
        )
        return dict(
            receipt=dict(vars(receipt), directory=str(receipt.directory)),
            nested_ownership_verification_requests=receipt.verification_attempts,
            nested_invocations_retained_by_profiler=True,
            independent_cases=0,
        )

    take(name, perform)
    return returned


def compare_dispatches(accounting, paired):
    """Link real branch callback returns to the paired source/oracle samples."""
    family = paired["family"]
    groups = accounting[("periodic" if family == "periodic" else "sweep") + "_dispatches"]
    require(len(groups) == 6, "Both complete branch callback histories required")
    rows = paired["rows"]
    expected = {
        (row["key"], sample["label"].hex()): sample["candidate"]
        for row in rows
        for sample in row["samples"]
    }
    require(len(expected) == 3 * len(rows), "Duplicate source probe key/clock sample")
    count = 0
    for index, group in enumerate(groups):
        require(
            group["label"].hex() == paired["labels"][index % 3].hex(),
            "Actual branch source label differs from paired reference",
        )
        active = [
            event
            for event in group["events"]
            if event["operation"] == "callback" and event["kind"] != "constant"
        ]
        require(
            [event["key"] for event in active] == [row["key"] for row in rows],
            "Actual temporal callback omitted, duplicated or reordered",
        )
        for event in active:
            value = expected[(event["key"], group["label"].hex())]
            require(
                event["returned"]
                and type(event["value"]) is float
                and event["value"].hex() == value["hex"]
                and event["value_shape"] == value["shape"]
                and event["value_dtype"] == value["dtype"],
                "Actual callback differs from paired original/reference sample",
            )
            count += 1
    return dict(
        actual_callback_returns_matched=count,
        independent_cases=0,
        constants_checked_by_existing_observer=True,
    )


def actual_continuity(
    directory,
    *,
    init_binding=None,
    init_parent=None,
    event_owner_inputs=None,
    expected_binding_identity=None,
    expected_parent_identity=None,
    expected_producer=None,
    configuration,
    scenario,
    cut,
    native_root=reference.NATIVE_ROOT,
):
    """Gated existing producers only; never call prepare_INIT or infer a parent."""
    reference.released()
    declared = request(configuration, scenario, cut)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "operations").mkdir()
    attempts, accounting = [], {}
    retain = preparation._retainer(directory / "operations", attempts)
    calls = stream = None
    values = dict(
        init_binding=init_binding,
        init_parent=init_parent,
        event_owner_inputs=event_owner_inputs,
        request=declared,
        expected_binding_identity=expected_binding_identity,
        expected_parent_identity=expected_parent_identity,
    )

    def take(name, operation, **readers):
        if calls is not None:
            calls.stage = name
        return retain(name, operation, **readers)

    try:
        take(
            "required-actual-INIT-parent",
            lambda: preflight(
                init_binding,
                init_parent,
                event_owner_inputs,
                expected_binding_identity=expected_binding_identity,
                expected_parent_identity=expected_parent_identity,
            ),
            **values,
        )
        take("required-callback-result-ABI", reference.require_abi)

        def producer_matches():
            require(
                type(expected_producer) is dict
                and checkpoint.producer_identity() == expected_producer,
                "Missing or foreign reviewed source/runtime producer for selected route",
            )
            return dict(producer_matches=True, scientific_admission=False)

        take("required-source-runtime-producer", producer_matches)
        family = declared["configuration"]["family"]
        producer = periodic if family == "periodic" else sweep
        stream = (directory / "invocations.jsonl").open("x")
        calls = producer.observer(Calls, stream, run.composition.events.events.__file__, directory)
        calls.start()
        take("actual-retained-INIT-verification", lambda: run.verify(init_binding, init_parent))
        sim_binding, sim = selected.prepare_sim(
            directory / "SIM",
            init_binding,
            init_parent,
            attempts,
            scenario=scenario,
            event_owner_inputs=event_owner_inputs,
            configuration=configuration,
        )
        values.update(sim_binding=sim_binding, sim=sim)
        labels = tuple(float(t) for t in sim.active.active.clock.source_times_s)
        source_comparison = reference.paired_compare(
            directory / "original-source",
            sim_binding.composition,
            sim.active,
            expected_binding_identity=sim_binding.composition.identity,
            expected_entry_identity=sim.active.identity,
            labels=labels,
            root=native_root,
        )
        raw = take(
            "actual-selected-event-declaration",
            lambda: selected.declaration(sim_binding.composition, sim.active, scenario),
        )
        component = take(
            "event-binding",
            lambda: run.composition.events.bind(raw, sim_binding.composition, sim.active),
        )
        entry = take("actual-event-entry", lambda: run.composition.events.begin(component))
        run_inputs = take(
            "existing-event-run-declaration",
            lambda: preparation.fixtures.declaration("zero_INIT_calls", component),
        )
        binding = take("event-run-binding", lambda: run.bind(run_inputs, component))
        receipt = take(
            "event-run-receipt",
            lambda: run.entry_receipt(
                binding,
                entry,
                provenance="Actual selected temporal event entry; no fabricated source parent",
                previous_phase=sim.entry_receipt["previous_phase"],
            ),
        )
        parent = take("event-run-begin", lambda: run.begin(binding, entry, receipt))
        values.update(binding=binding, parent=parent)
        fp = checkpoint.codec.fingerprint
        untouched = fp((binding, parent))
        arrays = take("original-calendar-window", lambda: run.calendars.window(binding.calendar))
        owner = component.raw["event_owner"]
        cb = component.material_binding.geometry_binding.current_binding
        anchor = dict(
            scenario=scenario,
            preparation_route=selected.ROUTE,
            phase="SIM",
            event_binding=component.identity,
            source_binding=component.source_binding.identity,
            source_entry=component.source_entry.identity,
            source_INIT=component.source_entry.source_init.identity,
            calendar=binding.calendar.identity,
            event_owner=run.ions.digest(owner),
            entry_state=entry.identity,
            labels=list(labels),
            samples=[i for i, sampled in enumerate(arrays.sampled) if sampled],
            owned_RNG=fp(
                (
                    component.base.setup_receipt["numpy_rng_after"],
                    component.base.setup_receipt["event_finalization"]["python_rng_after"],
                )
            ),
            entry_T=fp(entry.stores["T"]),
            scheduled_options=run.ions.data(owner["scheduled_options"]),
            callbacks=run.ions.data(owner["callbacks"]),
            ion_ids=list(cb.ion_ids),
            targets={
                key: list(owner["handler_fields"]["targets_" + suffix])
                for key, suffix in sweep.membrane.MEMBRANE_KEYS.items()
                if owner["scheduled_options"][key] != 0
            },
        )
        rng_before = take("actual-global-RNG-before", checkpoint._rng_identity)
        baseline = preparation.accepted_prefix(
            directory / "uninterrupted", binding, parent, attempts, calls=3
        )
        prefix = preparation.accepted_prefix(
            directory / "prefix", binding, parent, attempts, calls=cut
        )
        require(fp((binding, parent)) == untouched, "Branch mutated its caller's retained graph")
        paused = take("pause-prefix", lambda: run.pause(binding, prefix))
        values.update(baseline=baseline, prefix=prefix, paused=paused)
        saved = _checkpoint_call(
            take,
            "checkpoint-save",
            lambda: checkpoint.save_checkpoint(
                directory / "checkpoint",
                binding,
                paused,
                expected_phase="SIM",
                expected_parent_identity=paused.identity,
            ),
        )
        loaded = _checkpoint_call(
            take,
            "checkpoint-load",
            lambda: checkpoint.load_checkpoint(
                directory / "checkpoint",
                binding=binding,
                expected_phase="SIM",
                expected_parent_identity=paused.identity,
                expected_checkpoint_identity=saved.identity,
                evidence_directory=directory / "load",
            ),
        )
        values["loaded_parent"] = loaded.parent
        require(
            fp((loaded.binding, loaded.parent)) == fp((binding, paused))
            and loaded.parent.status == "paused"
            and loaded.parent.cursor == cut,
            "Restored full graph or paused status/cursor differs",
        )
        take("loaded-prefix-observation", lambda: observe(loaded.binding, loaded.parent, anchor))
        resumed = take("resume-prefix", lambda: run.resume(loaded.binding, loaded.parent))
        require(
            fp((loaded.binding, resumed)) == fp((binding, prefix)),
            "Resume changed more than paused disposition",
        )
        continued = preparation.accepted_prefix(
            directory / "continued", loaded.binding, resumed, attempts, calls=3 - cut
        )
        values["continued"] = continued
        before = take("uninterrupted-observation", lambda: observe(binding, baseline, anchor))
        after = take("restored-observation", lambda: observe(loaded.binding, continued, anchor))
        require(
            before == after and baseline.status == continued.status == "exhausted",
            "Uninterrupted/restored complete graph, owners, events or sampling differ",
        )
        require(
            rng_before == take("actual-global-RNG-after", checkpoint._rng_identity),
            "Temporal comparison/checkpoint consumed unowned process RNG",
        )
        result = dict(
            status="conditional_source_and_continuity_checks_passed",
            request=declared,
            anchor=anchor,
            original_source_comparison=source_comparison,
            baseline=before,
            continued=after,
            independent_biological_cases=0,
            complete_native_or_physical_admission=False,
        )
    except BaseException as error:
        record_failure(
            error,
            stage="selected-temporal-continuity",
            readers={
                **{name: lambda value=value: value for name, value in values.items()},
                "attempts": lambda: attempts,
                "partial": lambda error=error: getattr(error, "partial", None),
            },
            retain=lambda v: preparation.archives.write_archive(
                directory / "failure", run.ions.data(v)
            ),
        )
        raise
    finally:
        primary, recovery = sys.exception(), None
        try:
            if calls is not None:
                accounting = calls.stop()
        except BaseException as secondary:
            recovery = secondary
        try:
            if stream is not None:
                stream.close()
            snapshot.write_json(
                directory / "attempts.json",
                dict(
                    attempts=attempts,
                    invocation_accounting=accounting,
                    scope=(
                        "All setup, verification, reference, factory, RNG, timestep and nested "
                        "checkpoint requests are work; overlapping counts are not biological cases."
                    ),
                ),
            )
        except BaseException as secondary:
            recovery = recovery or secondary
        if recovery is not None:
            if primary is not None:
                primary.add_note("Temporal continuation accounting also failed: " + repr(recovery))
            else:
                raise recovery
    try:
        require(
            accounting.get("profile_intact") and accounting.get("active_invocations") == 0,
            "Incomplete invocation accounting",
        )
        result["callback_and_pulse_work"] = producer.check_calls(accounting, anchor)
        result["original_source_dispatch_comparison"] = compare_dispatches(
            accounting, source_comparison
        )
        result["invocation_accounting"] = accounting
        snapshot.write_json(directory / "result.json", result)
    except BaseException as error:
        record_failure(
            error,
            stage="selected-temporal-result-publication",
            readers={"result": lambda: result},
            retain=lambda v: preparation.archives.write_archive(
                directory / "result-failure", run.ions.data(v)
            ),
        )
        raise
    return result
