"""Held deterministic event checkpoint continuity on retained phase owners.

Metadata checks execute no model. Actual entry/transition/events/RNG/checkpoint
validation requires both existing Root releases. No native/reference parity or
independent biological-case credit is conferred by these conditional branches.
"""

import argparse
import copy
import os
import struct
import sys
from pathlib import Path

from validation.betse import betse_normal_ecm_molecule_global_event_checkpoint as global_events
from validation.betse import betse_normal_ecm_molecule_membrane_event_checkpoint as membrane_events
from validation.betse import (
    betse_normal_ecm_molecule_published_global_checkpoint as published_global,
)
from validation.betse.betse_normal_ecm_init_phase_capture import record_failure
from validation.source_snapshot import write_json

RELEASES = ("CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED", "CELLS_ECM_MOLECULE_EVENTS_RELEASED")
TEMPERATURE_SCENARIOS = ("temperature", "no_events", "temperature_boundaries")
SCENARIOS = TEMPERATURE_SCENARIOS + global_events.SCENARIOS + membrane_events.SCENARIOS
CUTS = (1, 2)
STAGES = ("_fire_events_global", "_fire_events_tissue", "makeAllChanges")
SOURCE_FILES = (
    "src/cells/processes/betse_normal_ecm_molecule_events.py",
    "src/cells/processes/betse_normal_ecm_molecule_events_step.py",
    "src/cells/processes/betse_normal_ecm_molecule_events_material.py",
    "src/cells/processes/betse_normal_ecm_molecule_events_pump.py",
    "src/cells/processes/betse_normal_ecm_molecule_events_source.py",
    "validation/betse/betse_normal_ecm_molecule_events_fixtures.py",
    "validation/betse/betse_normal_ecm_molecule_event_checkpoint.py",
    "tests/unit/test_betse_normal_ecm_molecule_event_checkpoint.py",
    "validation/betse/betse_normal_ecm_molecule_global_event_checkpoint.py",
    "tests/unit/test_betse_normal_ecm_molecule_global_event_checkpoint.py",
    "validation/betse/betse_normal_ecm_molecule_membrane_event_checkpoint.py",
    "tests/unit/test_betse_normal_ecm_molecule_membrane_event_checkpoint.py",
    "src/cells/processes/betse_normal_ecm_molecule_event_owner.py",
    "tests/unit/test_betse_normal_ecm_molecule_event_owner.py",
    "validation/betse/betse_normal_ecm_molecule_published_global_checkpoint.py",
    "tests/unit/test_betse_normal_ecm_molecule_published_global_checkpoint.py",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def boundary(time, onset, release):
    if time < onset:
        return "before_onset"
    if time == onset:
        return "onset"
    if time < release:
        return "active"
    if time == release:
        return "release"
    return "after_release"


def program(raw, scenario, labels):
    """Declare controls only; no pulse evaluation or state initialization.

    Original temperature and no-events fixtures are copied unchanged. The
    boundary control moves only the two declared pulse times onto original
    source labels, retaining the same amplitude, width and source law. It is a
    configuration control, not a new biological specimen or tolerance.
    """
    require(scenario in SCENARIOS and len(labels) == 3, "Original bounded N3 scenario required")
    if scenario in global_events.SCENARIOS:
        return global_events.program(raw, scenario, labels)
    value = copy.deepcopy(raw)
    owner = value["event_owner"]
    glob, sched = owner["global_options"], owner["scheduled_options"]
    require(
        all(v == 0 for k, v in glob.items() if k != "T_change")
        and all(v == 0 for v in sched.values())
        and not owner["callbacks"]
        and owner["voltage"] is None,
        "Only the existing temperature pulse is supported",
    )
    if scenario == "no_events":
        require(glob["T_change"] == 0, "Use the existing zero-event fixture")
    else:
        row = glob["T_change"]
        require(
            type(row) is list and len(row) == 4 and row[0] < row[1] and row[2] > 0,
            "Use the existing nondegenerate temperature configuration",
        )
        if scenario == "temperature_boundaries":
            row[:2] = [labels[1], labels[2]]
            owner["handler_fields"].update(tonT=row[0], toffT=row[1])
            value["provenance"] += "; explicit onset/release source-label control"
    return value


def check_observation(value, anchor):
    """Check source ownership, once-per-call application and sampling metadata.

    This checks observations, not parent admission. Existing event/run verifiers
    and complete checkpoint fingerprints still decide actual state ownership.
    """
    for key in (
        "event_binding",
        "source_binding",
        "source_entry",
        "source_INIT",
        "calendar",
        "event_owner",
        "owned_RNG",
        "phase",
    ):
        require(value[key] == anchor[key], "Changed event/phase ownership: " + key)
    require(value["phase"] == "SIM", "Event execution requires SIM ownership")
    cursor = value["cursor"]
    require(
        type(cursor) is int and 0 <= cursor <= 3 and len(value["rows"]) == cursor,
        "Event journal must cover every accepted call exactly once",
    )
    previous = anchor["entry_state"]
    for index, row in enumerate(value["rows"]):
        require(
            type(row["call_index"]) is int and row["call_index"] == index,
            "Duplicate/omitted/reordered event application",
        )
        require(
            type(row["label"]) is float
            and struct.pack("<d", row["label"]) == struct.pack("<d", anchor["labels"][index]),
            "Event clock was changed or rebased",
        )
        require(
            row["event_owner"] == anchor["event_owner"]
            and row["phase"] == "SIM"
            and row["legacy_run_sim"] is True,
            "Changed event/phase owner in journal",
        )
        require(
            type(row["event_fire_calls"]) is int
            and row["event_fire_calls"] == 1
            and type(row["flux_resets"]) is int
            and row["flux_resets"] == 1
            and type(row["noise_calls"]) is int
            and row["noise_calls"] == 0,
            "Event/reset/noise application count changed",
        )
        require(
            tuple(row["stages"]) == STAGES and row["source_completed"] is True,
            "Missing/duplicate source event stage",
        )
        require(row["before_state"] == previous, "Changed accepted event parent chain")
        previous = row["after_state"]
        if anchor["scenario"] == "no_events":
            require(
                row["T_before"] == row["T_after"] == anchor["entry_T"],
                "Zero-event control changed temperature",
            )
    require(previous == value["active_state"], "Omitted or unjournaled event application")
    require(
        value["samples"] == [i for i in anchor["samples"] if i < cursor],
        "Changed calendar sampling/duplicate or omitted observation",
    )
    if cursor == 3 and anchor["scenario"] in ("temperature", "temperature_boundaries"):
        require(
            len({r["T_after"] for r in value["rows"]}) > 1,
            "Temperature event had no reached effect",
        )
    if anchor["scenario"] in global_events.SCENARIOS:
        global_events.check_stores(value, anchor)
    if anchor["scenario"] in membrane_events.SCENARIOS:
        global_events.check_stores(value, anchor)
        membrane_events.check_stores(value, anchor)
    if anchor.get("preparation_route") == published_global.ROUTE:
        for key in (
            "source_publication",
            "source_configuration",
            "source_event_finalized",
            "source_publication_epoch",
            "declared_intervention",
        ):
            require(value[key] == anchor[key], "Changed explicit global route association: " + key)
        if anchor["scenario"] in TEMPERATURE_SCENARIOS:
            global_events.check_stores(value, anchor)
    return value


def actual_continuity(
    directory, *, scenario, cut, event_owner_inputs=None, preparation_route="legacy"
):
    """Prospective real continuity check; every branch/verification is work."""
    require(
        all(os.environ.get(name) == "1" for name in RELEASES),
        "Held event continuity: both existing Root releases are required",
    )
    require(__debug__ and sys.flags.optimize == 0, "Assertions must be enabled")
    require(
        scenario in SCENARIOS and type(cut) is int and cut in CUTS,
        "Bounded event case/cut required",
    )
    membrane = scenario in membrane_events.SCENARIOS
    require(preparation_route in ("legacy", published_global.ROUTE), "Unknown preparation route")
    explicit_global = preparation_route == published_global.ROUTE
    if explicit_global:
        published_global.check_route(scenario)
    require(
        explicit_global or membrane or event_owner_inputs is None,
        "Explicit typed event-owner inputs require the targeted preparation route",
    )
    store_observations = membrane or explicit_global or scenario in global_events.SCENARIOS
    from cells.processes import betse_normal_ecm_molecule_checkpoint as checkpoint
    from cells.processes import betse_normal_ecm_molecule_event_owner as owner_bridge
    from cells.processes import betse_normal_ecm_molecule_events as events
    from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run
    from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation
    from validation.betse import betse_normal_ecm_molecule_events_fixtures as fixtures
    from validation.betse.betse_normal_ecm_molecule_handoff_run_plugin import Calls

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    attempts = []
    (directory / "operations").mkdir()
    take = preparation._retainer(directory / "operations", attempts)
    initial_binding = initial = sim_binding = sim = binding = parent = prefix = paused = loaded = (
        None
    )
    original = raw = component = entry = baseline = continued = saved = intervention = None
    stream = calls = None
    accounting = {}

    def retain_failure(error, stage):
        return record_failure(
            error,
            stage=stage,
            readers=dict(
                INIT_binding=lambda: initial_binding,
                INIT_parent=lambda: initial,
                SIM_binding=lambda: sim_binding,
                SIM_parent=lambda: sim,
                original_event_declaration=lambda: original,
                explicit_event_owner_inputs=lambda: event_owner_inputs,
                declared_global_intervention=lambda: intervention,
                event_program=lambda: raw,
                event_component=lambda: component,
                event_binding=lambda: binding,
                event_component_entry=lambda: entry,
                event_entry=lambda: parent,
                prefix=lambda: prefix,
                paused=lambda: paused,
                loaded=lambda: None if loaded is None else (loaded.binding, loaded.parent),
                baseline=lambda: baseline,
                continued=lambda: continued,
                attempts=lambda: attempts,
                invocation_accounting=lambda: accounting,
                partial=lambda: getattr(error, "partial", None),
            ),
            retain=lambda value: preparation.archives.write_archive(
                directory / "failure", run.ions.data(value)
            ),
        )

    def checkpoint_call(name, operation):
        # The checkpoint records retain complete arrays/graphs and both nested
        # ownership attempts. Archive the receipt with its Path as a string.
        event = dict(operation=name, numerical_work_possible=True, status="attempted")
        attempts.append(event)
        try:
            value = operation()
        except BaseException:
            event["status"] = "refused"
            raise
        event["status"] = "returned"
        receipt = value.receipt if type(value) is checkpoint.Loaded else value
        try:
            preparation.archives.write_archive(
                directory / "operations" / name,
                dict(receipt=dict(vars(receipt), directory=str(receipt.directory))),
            )
        except BaseException:
            event["status"] = "retention_refused"
            raise
        return value

    try:
        stream = (directory / "invocations.jsonl").open("x")
        calls = (
            membrane_events.observer(Calls, stream, events.events.__file__, directory)
            if membrane
            else global_events.observer(Calls, stream, events.events.__file__, directory)
            if store_observations
            else Calls(stream)
        )
        calls.start()
        if membrane or explicit_global:
            take(
                "required-typed-event-owner-inputs",
                lambda: owner_bridge.check_inputs(event_owner_inputs),
                supplied=event_owner_inputs,
            )
        initial_binding, initial = preparation.prepare_INIT(
            directory / "INIT", "zero_INIT_calls", attempts
        )
        sim_binding, sim = (
            published_global.prepare_sim(
                directory / "SIM",
                initial_binding,
                initial,
                attempts,
                scenario=scenario,
                event_owner_inputs=event_owner_inputs,
            )
            if explicit_global
            else membrane_events.prepare_sim(
                directory / "SIM",
                initial_binding,
                initial,
                attempts,
                scenario=scenario,
                event_owner_inputs=event_owner_inputs,
            )
            if membrane
            else preparation.prepare_SIM(directory / "SIM", initial_binding, initial, attempts)
        )
        labels = tuple(float(t) for t in sim.active.active.clock.source_times_s)
        if explicit_global:
            original, intervention = take(
                "declared-global-intervention-on-actual-publication",
                lambda: published_global.declaration(
                    sim_binding.composition,
                    sim.active,
                    scenario=scenario,
                    labels=labels,
                    dt=sim.active.phase_binding.calendar.dt_s,
                ),
            )
        else:
            original = take(
                "existing-event-fixture",
                lambda: (
                    membrane_events.declaration(sim_binding.composition, sim.active, scenario)
                    if membrane
                    else fixtures.declaration(
                        "combined"
                        if scenario in global_events.SCENARIOS
                        else "no_events"
                        if scenario == "no_events"
                        else "temperature",
                        sim_binding.composition,
                        sim.active,
                    )
                ),
            )
        raw = take(
            "explicit-event-program",
            lambda: (
                original if membrane or explicit_global else program(original, scenario, labels)
            ),
            original=original,
        )
        component = take(
            "event-binding", lambda: events.bind(raw, sim_binding.composition, sim.active), raw=raw
        )
        entry = take("actual-event-entry", lambda: events.begin(component), binding=component)
        declared = take(
            "event-run-declaration",
            lambda: preparation.fixtures.declaration("zero_INIT_calls", component),
        )
        binding = take(
            "event-run-binding", lambda: run.bind(declared, component), declared=declared
        )
        receipt = take(
            "event-run-receipt",
            lambda: run.entry_receipt(
                binding,
                entry,
                provenance="Actual existing deterministic event entry; no synthetic admission",
                previous_phase=sim.entry_receipt["previous_phase"],
            ),
        )
        parent = take(
            "event-run-begin",
            lambda: run.begin(binding, entry, receipt),
            entry=entry,
            receipt=receipt,
        )
        fp = checkpoint.codec.fingerprint

        def stamp(value):
            array = isinstance(value, events.np.ndarray)
            scalar = isinstance(value, events.np.generic)
            return dict(
                fingerprint=fp(value),
                category="array" if array else "numpy_scalar" if scalar else "scalar",
                shape=list(value.shape) if array or scalar else [],
                dtype=value.dtype.str if array or scalar else None,
            )

        arrays = take("original-event-calendar", lambda: run.calendars.window(binding.calendar))
        anchor = dict(
            scenario=scenario,
            phase="SIM",
            event_binding=component.identity,
            source_binding=component.source_binding.identity,
            source_entry=component.source_entry.identity,
            source_INIT=component.source_entry.source_init.identity,
            calendar=binding.calendar.identity,
            event_owner=run.ions.digest(component.raw["event_owner"]),
            entry_state=entry.identity,
            labels=list(labels),
            samples=[i for i, v in enumerate(arrays.sampled) if v],
            entry_T=fp(entry.stores["T"]),
            owned_RNG=fp(
                (
                    component.base.setup_receipt["numpy_rng_after"],
                    component.base.setup_receipt["event_finalization"]["python_rng_after"],
                )
            ),
        )
        if explicit_global:
            anchor.update(
                preparation_route=preparation_route,
                **take(
                    "original-published-global-association",
                    lambda: published_global.association(component, intervention),
                ),
            )
        if store_observations:
            anchor.update(
                global_options=run.ions.data(component.raw["event_owner"]["global_options"]),
                entry_global={key: stamp(entry.stores[key]) for key in global_events.STORES},
            )
        if membrane:
            actual_owner = component.raw["event_owner"]
            cb = component.material_binding.geometry_binding.current_binding
            anchor.update(
                scheduled_options=run.ions.data(actual_owner["scheduled_options"]),
                callback_identity=fp(actual_owner["callbacks"]),
                callback_authority=fp(
                    component.base.setup_receipt["event_finalization"]["source_fields"][
                        "constant_callback_authority"
                    ]
                ),
                ion_ids=list(cb.ion_ids),
                membrane_count=len(cb.membrane_ids),
                targets={
                    key: list(actual_owner["handler_fields"]["targets_" + suffix])
                    for key, suffix in membrane_events.MEMBRANE_KEYS.items()
                    if actual_owner["scheduled_options"][key] != 0
                },
                entry_membrane={key: stamp(entry.stores[key]) for key in membrane_events.STORES},
            )

        def observation(current_binding, current):
            run.verify(
                current_binding, current
            )  # Count this actual numerical ownership validation.
            owner = current_binding.composition
            value = dict(
                phase=run.composition.kind(owner),
                event_binding=owner.identity,
                source_binding=owner.source_binding.identity,
                source_entry=owner.source_entry.identity,
                source_INIT=owner.source_entry.source_init.identity,
                calendar=current_binding.calendar.identity,
                event_owner=run.ions.digest(owner.raw["event_owner"]),
                cursor=current.cursor,
                active_state=current.active.identity,
                samples=[o.call_index for o in current.observations],
                owned_RNG=fp(
                    (
                        owner.base.setup_receipt["numpy_rng_after"],
                        owner.base.setup_receipt["event_finalization"]["python_rng_after"],
                    )
                ),
                rows=[],
            )
            if explicit_global:
                value.update(published_global.association(owner, intervention))
            if store_observations:
                active = current.active
                value.update(
                    global_options=run.ions.data(owner.raw["event_owner"]["global_options"]),
                    post_owner_controls={
                        key: stamp(active.stores[key]) for key in ("gj_block", "NaKATP_block")
                    },
                    transport=dict(
                        material=fp(active.network.material),
                        rate=fp(active.rate_cache),
                        NaK_rate=fp(active.nak_rate),
                        field=fp(active.field),
                        runtime_binding=fp(active.runtime_material_binding),
                        runtime_definition=fp(active.runtime_definition),
                        owner_caches=fp(active.network.network_cache),
                        all_stores=fp(active.stores),
                    ),
                )
            if membrane:
                value.update(
                    scheduled_options=run.ions.data(owner.raw["event_owner"]["scheduled_options"]),
                    callback_identity=fp(owner.raw["event_owner"]["callbacks"]),
                    callback_authority=fp(
                        owner.base.setup_receipt["event_finalization"]["source_fields"][
                            "constant_callback_authority"
                        ]
                    ),
                    post_owner_membrane={
                        key: stamp(current.active.stores[key]) for key in membrane_events.STORES
                    },
                )
            for outer, inner in zip(current.history, current.active.history, strict=True):
                trace = inner["event_trace"]
                require(
                    trace["source_time_s"] == outer.source_label_s,
                    "Actual event/phase source clocks differ",
                )
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
                if store_observations:
                    value["rows"][-1].update(
                        global_before={
                            key: stamp(trace["before"][key]) for key in global_events.STORES
                        },
                        global_after={
                            key: stamp(trace["stages"][0]["state"][key])
                            for key in global_events.STORES
                        },
                        events_after={
                            key: stamp(trace["after"][key]) for key in global_events.STORES
                        },
                    )
                if membrane:
                    value["rows"][-1]["membrane"] = membrane_events.observe_row(
                        trace, anchor, stamp, fp
                    )
            return check_observation(value, anchor)

        rng_before = take("actual-process-RNG-before", checkpoint._rng_identity)
        untouched = fp((binding, parent))
        baseline = preparation.accepted_prefix(
            directory / "uninterrupted", binding, parent, attempts, calls=3
        )
        prefix = preparation.accepted_prefix(
            directory / "prefix", binding, parent, attempts, calls=cut
        )
        require(
            fp((binding, parent)) == untouched, "Branch execution changed its retained caller input"
        )
        paused = take("pause-event-prefix", lambda: run.pause(binding, prefix), parent=prefix)
        saved = checkpoint_call(
            "checkpoint-save",
            lambda: checkpoint.save_checkpoint(
                directory / "checkpoint",
                binding,
                paused,
                expected_phase="SIM",
                expected_parent_identity=paused.identity,
            ),
        )
        loaded = checkpoint_call(
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
        require(
            fp((loaded.binding, loaded.parent)) == fp((binding, paused)),
            "Loaded full event/owner/calendar/RNG graph differs",
        )
        require(
            loaded.parent.status == "paused" and loaded.parent.cursor == cut,
            "Load changed paused prefix status/cursor",
        )
        prefix_observation = take(
            "loaded-prefix-observation", lambda: observation(loaded.binding, loaded.parent)
        )
        resumed = take(
            "resume-event-prefix",
            lambda: run.resume(loaded.binding, loaded.parent),
            parent=loaded.parent,
        )
        require(
            fp((loaded.binding, resumed)) == fp((binding, prefix)),
            "Resume changed state beyond its paused status",
        )
        continued = preparation.accepted_prefix(
            directory / "continued", loaded.binding, resumed, attempts, calls=3 - cut
        )
        baseline_observation = take("baseline-observation", lambda: observation(binding, baseline))
        continued_observation = take(
            "continued-observation", lambda: observation(loaded.binding, continued)
        )
        require(
            baseline_observation == continued_observation,
            "Event application/owner/sampling continuation differs",
        )
        require(
            fp((binding, baseline)) == fp((loaded.binding, continued)),
            "Uninterrupted and loaded full state differ",
        )
        require(
            continued.status == baseline.status == "exhausted",
            "Failed/paused/capped prefix is not completion",
        )
        rng_after = take("actual-process-RNG-after", checkpoint._rng_identity)
        require(
            rng_before == rng_after,
            "Deterministic event/checkpoint work consumed unowned process RNG",
        )
        options = component.raw["event_owner"]["global_options"]
        pulse = next((options[key] for key in global_events.GLOBAL_ORDER if options[key] != 0), 0)
        if membrane and pulse == 0:
            scheduled = component.raw["event_owner"]["scheduled_options"]
            pulse = next(
                scheduled[key] for key in membrane_events.MEMBRANE_KEYS if scheduled[key] != 0
            )
        boundaries = (
            ["zero_configured_event"] * 3
            if scenario == "no_events"
            else [boundary(t, pulse[0], pulse[1]) for t in labels]
        )
        expected = (
            ["before_onset", "onset", "release"]
            if scenario in ("temperature_boundaries", "global_boundaries", "membrane_boundaries")
            else ["before_onset", "active", "after_release"]
            if scenario != "no_events"
            else ["zero_configured_event"] * 3
        )
        require(boundaries == expected, "The declared onset/release control was not traversed")
        result = dict(
            status="conditional_event_continuity_returned",
            scenario=scenario,
            cut=cut,
            anchor=anchor,
            boundaries=boundaries,
            prefix=prefix_observation,
            final=continued_observation,
            source_event_dispatches=6,
            configured_temperature_event=options["T_change"] != 0,
            restored_exact=True,
            checkpoint=saved.identity,
            independent_biological_cases=0,
            native_source_equivalence=False,
            scientific_acceptance=False,
        )
        if explicit_global:
            result.update(preparation_route=preparation_route, declared_intervention=intervention)
    except BaseException as error:
        retain_failure(error, "actual_event_checkpoint_continuity")
        raise
    finally:
        primary = sys.exception()
        recovery_error = None
        try:
            if calls is not None:
                accounting = calls.stop()
        except BaseException as secondary:
            if primary is not None:
                primary.add_note("Invocation accounting also failed: " + repr(secondary))
            else:
                recovery_error = secondary
        try:
            if stream is not None:
                stream.close()
        except BaseException as secondary:
            if primary is not None:
                primary.add_note("Invocation stream close also failed: " + repr(secondary))
            elif recovery_error is None:
                recovery_error = secondary
        try:
            write_json(
                directory / "attempts.json",
                dict(
                    attempts=attempts,
                    invocation_accounting=accounting,
                    accounting=(
                        "Each actual setup/verification/RNG/event/timestep/checkpoint request "
                        "counts; "
                        "nested ownership work is in checkpoint operation records and the "
                        "existing invocation profiler. Branches and controls carry no "
                        "independent biological credit."
                    ),
                ),
            )
        except BaseException as secondary:
            if primary is None:
                if recovery_error is None:
                    recovery_error = secondary
            else:
                primary.add_note("Attempt journal also failed: " + repr(secondary))
        if primary is None and recovery_error is not None:
            retain_failure(recovery_error, "event_checkpoint_accounting")
            raise recovery_error
    try:
        require(
            accounting.get("profile_intact") and accounting.get("active_invocations") == 0,
            "Actual invocation accounting is incomplete",
        )
        require(
            accounting["counts"].get("cells.processes.betse_normal_ecm_event_join_source.fire")
            == 6,
            "Real event dispatches differ from both complete branch histories",
        )
        result["invocation_accounting"] = accounting
        if store_observations:
            result["global_source_pulses"] = global_events.check_pulses(
                accounting, anchor["global_options"], labels
            )
        if membrane:
            result["membrane_source_callbacks_pulses"] = membrane_events.check_calls(
                accounting, anchor
            )
        write_json(directory / "result.json", result)
    except BaseException as error:
        retain_failure(error, "event_checkpoint_result_validation_or_publication")
        raise
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, required=True)
    parser.add_argument("--cut", choices=CUTS, type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--preparation-route", choices=("legacy", published_global.ROUTE), default="legacy"
    )
    args = parser.parse_args()
    actual_continuity(
        args.output, scenario=args.scenario, cut=args.cut, preparation_route=args.preparation_route
    )


if __name__ == "__main__":
    main()
