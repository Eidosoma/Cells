# ruff: noqa: E501
"""Headless accepted-call journals on actual supplied molecule54 INIT/SIM entries.

No cold setup, native physical initialization, event firing, display or persistence is added.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, replace

from cells.core import physiology_native_calendar as calendars
from cells.processes import betse_normal_ecm_molecule_run_lifecycle_component as composition
from cells.processes import betse_normal_ion_join as ions

LAW_ID = "betse_supplied_ECM_molecule_headless_phase_run_v1_5_0@1"
INPUT_KIND = "cells.normal_ecm_molecule_headless_run_inputs@1"
ENTRY_KIND = "cells.supplied_molecule_phase_entry_declaration@1"
STATUS = {"ready", "paused", "exhausted", "failed", "capped"}


@dataclass(frozen=True)
class Binding:
    composition: object
    inputs: object
    identity: str

    @property
    def calendar(self):
        return composition.calendar(self.composition)


@dataclass(frozen=True)
class CallReceipt:
    call_index: int
    source_label_s: float
    elapsed_start_s: float
    elapsed_end_s: float
    dt_s: float
    before_identity: str
    after_identity: str
    sample_eligible: bool


@dataclass(frozen=True)
class Observation:
    call_index: int
    source_label_s: float
    elapsed_end_s: float
    state: object
    native_write2storage_called: bool = False
    native_display_completed: bool = False
    mode: str = "headless_observation_at_native_sample_boundary"


@dataclass(frozen=True)
class RunState:
    binding_identity: str
    entry: object
    entry_receipt: object
    active: object
    history: tuple
    observations: tuple
    status: str
    identity: str

    @property
    def cursor(self):
        return composition.cursor(self.active)


class RunRejected(RuntimeError):
    def __init__(self, reason, partial):
        super().__init__(str(reason))
        self.partial = ions.freeze(partial)


def _real(value, name, *, positive=False):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or (value <= 0 if positive else value < 0)
    ):
        raise ValueError("Require finite source time-profile value: " + name)
    return float(value)


def profile(raw):
    keys = {
        "phase",
        "init_total_s",
        "init_dt_s",
        "init_sampling_s",
        "sim_total_s",
        "sim_dt_s",
        "sim_sampling_s",
        "provenance",
    }
    if (
        not isinstance(raw, Mapping)
        or set(raw) != keys
        or raw["phase"] not in ("INIT", "SIM")
        or (not isinstance(raw["provenance"], str))
        or (not raw["provenance"].strip())
    ):
        raise ValueError("Require the complete supplied native INIT/SIM time profile")
    result = {}
    for phase in ("init", "sim"):
        total = _real(raw[phase + "_total_s"], phase + "_total_s")
        dt = _real(raw[phase + "_dt_s"], phase + "_dt_s", positive=True)
        sampling = _real(raw[phase + "_sampling_s"], phase + "_sampling_s", positive=True)
        ratio = total / dt
        if not math.isfinite(ratio):
            raise ValueError("Native time-count division overflow")
        count = int(ratio)
        stride = sampling / dt
        if not math.isfinite(stride) or stride < 1:
            raise ValueError("Native sampling stride below one does not progress")
        result[phase] = dict(step_count=count, dt_s=dt, sample_stride=stride)
    return result


def _binding(binding):
    if type(binding) is not Binding or binding.identity != ions.digest(
        (LAW_ID, binding.composition.identity, binding.inputs)
    ):
        raise ValueError("Changed complete headless run binding")
    composition.verify_binding(binding.composition)
    calendars.validate(binding.calendar)


def _record(parent):
    return (
        parent.binding_identity,
        parent.entry,
        parent.entry_receipt,
        parent.active,
        parent.history,
        parent.observations,
        parent.status,
    )


def _state(binding, entry, receipt, active, history, observations, status):
    if status not in STATUS:
        raise ValueError("Unknown owned run state")
    value = RunState(
        binding.identity,
        entry,
        ions.freeze(receipt),
        active,
        tuple(history),
        tuple(observations),
        status,
        "",
    )
    return replace(value, identity=ions.digest(_record(value)))


def verify(binding, parent):
    _binding(binding)
    if (
        type(parent) is not RunState
        or parent.binding_identity != binding.identity
        or parent.identity != ions.digest(_record(parent))
        or (parent.status not in STATUS)
    ):
        raise ValueError("Require the complete unchanged owned lifecycle state")
    _entry(binding, parent.entry, parent.entry_receipt)
    composition.verify(binding.composition, parent.active)
    cursor = parent.cursor
    if (
        type(cursor) is not int
        or not 0 <= cursor <= binding.calendar.step_count
        or len(parent.history) != cursor
    ):
        raise ValueError("Lifecycle journal/cursor differ from accepted component calls")
    if cursor == binding.calendar.step_count and parent.status not in ("exhausted", "failed"):
        raise ValueError("A terminal source cursor cannot become ready or paused")
    previous = parent.entry.identity
    rows = calendars.window(binding.calendar)
    expected_samples = []
    for index, record in enumerate(parent.history):
        if (
            type(record) is not CallReceipt
            or type(record.call_index) is not int
            or any(
                (
                    type(value) is not float
                    for value in (
                        record.source_label_s,
                        record.elapsed_start_s,
                        record.elapsed_end_s,
                        record.dt_s,
                    )
                )
            )
            or (record.call_index != index)
            or (record.before_identity != previous)
            or (record.source_label_s != float(rows.event_label_s[index]))
            or (record.dt_s != binding.calendar.dt_s)
            or (record.elapsed_start_s != float(rows.elapsed_start_s[index]))
            or (record.elapsed_end_s != float(rows.elapsed_end_s[index]))
            or (record.sample_eligible is not bool(rows.sampled[index]))
        ):
            raise ValueError("Accepted source label/dt/owner journal changed")
        previous = record.after_identity
        if record.sample_eligible:
            expected_samples.append(index)
    if any((type(o) is not Observation for o in parent.observations)):
        raise ValueError("Require complete typed headless observations")
    if (
        previous != parent.active.identity
        or [o.call_index for o in parent.observations] != expected_samples
    ):
        raise ValueError("Lifecycle carry or observation ownership changed")
    for observation in parent.observations:
        index = observation.call_index
        if (
            type(observation) is not Observation
            or type(observation.call_index) is not int
            or type(observation.native_write2storage_called) is not bool
            or (type(observation.native_display_completed) is not bool)
            or (observation.state.identity != parent.history[index].after_identity)
            or (observation.source_label_s != parent.history[index].source_label_s)
            or (observation.elapsed_end_s != parent.history[index].elapsed_end_s)
            or observation.native_write2storage_called
            or observation.native_display_completed
            or (observation.mode != "headless_observation_at_native_sample_boundary")
        ):
            raise ValueError("Headless observation must retain its exact reached state and scope")
        composition.verify(binding.composition, observation.state)
    if parent.status == "exhausted" and cursor != binding.calendar.step_count:
        raise ValueError("Run marked exhausted before the last source call")
    actual = composition.phase_state(parent.active)
    if parent.status == "capped" and (
        actual.status != "capped" or cursor == binding.calendar.step_count
    ):
        raise ValueError("Capped run must retain an actual incomplete source cap")
    if actual.status == "capped" and parent.status not in ("capped", "failed"):
        raise ValueError("Actual source cap cannot be relabeled ready, paused or complete")
    return parent


def next_call(binding, parent):
    verify(binding, parent)
    if parent.status != "ready" or parent.cursor == binding.calendar.step_count:
        raise ValueError("Only a ready, nonterminal run can make its next source call")
    index = parent.cursor
    row = calendars.window(binding.calendar, start=index, stop=index + 1)
    return ions.freeze(
        dict(
            call_index=index,
            source_label_s=float(row.event_label_s[0]),
            elapsed_start_s=float(row.elapsed_start_s[0]),
            elapsed_end_s=float(row.elapsed_end_s[0]),
            dt_s=binding.calendar.dt_s,
            sample_eligible=bool(row.sampled[0]),
            original_calendar_identity=binding.calendar.identity,
        )
    )


def advance(binding, parent, *, observer=None, **callbacks):
    current = parent
    admitted = False
    attempted = {}
    stage = "admission"
    try:
        call = next_call(binding, parent)
        admitted = True
        attempted["call"] = call
        stage = "before_call_observer"
        if observer is not None:
            observer("before_call", dict(parent=parent, call=call))
        stage = "component_call"
        candidate, context = composition.advance(binding.composition, parent.active, **callbacks)
        attempted.update(component_candidate=candidate, component_context=context)
        record = CallReceipt(
            call["call_index"],
            call["source_label_s"],
            call["elapsed_start_s"],
            call["elapsed_end_s"],
            call["dt_s"],
            parent.active.identity,
            candidate.identity,
            call["sample_eligible"],
        )
        observations = parent.observations
        if record.sample_eligible:
            observations = (
                *observations,
                Observation(
                    record.call_index, record.source_label_s, record.elapsed_end_s, candidate
                ),
            )
        status = (
            "exhausted"
            if composition.cursor(candidate) == binding.calendar.step_count
            else "capped"
            if composition.phase_state(candidate).status == "capped"
            else "ready"
        )
        proposed = _state(
            binding,
            parent.entry,
            parent.entry_receipt,
            candidate,
            (*parent.history, record),
            observations,
            status,
        )
        attempted["run_candidate"] = proposed
        stage = "acceptance"
        verify(binding, proposed)
        current = proposed
        stage = "accepted_call_observer"
        if observer is not None:
            observer("accepted_call", dict(parent=current, context=context))
        if record.sample_eligible and observer is not None:
            stage = "headless_observation_observer"
            observer("headless_observation", current.observations[-1])
        return (current, ions.freeze(context))
    except Exception as error:
        failed = None
        if admitted and type(current) is RunState:
            failed = _state(
                binding,
                current.entry,
                current.entry_receipt,
                current.active,
                current.history,
                current.observations,
                "failed",
            )
        raise RunRejected(
            error,
            dict(
                stage=stage,
                caller_parent=parent,
                accepted=failed,
                attempt=attempted,
                component_partial=getattr(error, "partial", None),
                automatic_retry=False,
                native_pickle_called=False,
            ),
        ) from error


def pause(binding, parent):
    verify(binding, parent)
    if parent.status != "ready":
        raise ValueError("Pause only a ready run at an accepted call boundary")
    return _state(
        binding,
        parent.entry,
        parent.entry_receipt,
        parent.active,
        parent.history,
        parent.observations,
        "paused",
    )


def resume(binding, parent):
    verify(binding, parent)
    if parent.status != "paused":
        raise ValueError("Resume only an explicitly paused in-memory run")
    return _state(
        binding,
        parent.entry,
        parent.entry_receipt,
        parent.active,
        parent.history,
        parent.observations,
        "ready",
    )


def run_window(binding, parent, *, stop, observer=None, **callbacks):
    verify(binding, parent)
    if type(stop) is not int or not parent.cursor <= stop <= composition.call_limit(
        binding.composition
    ):
        raise ValueError("Window stop must retain the original source calendar/cursor")
    current = resume(binding, parent) if parent.status == "paused" else parent
    if current.status not in ("ready", "exhausted"):
        raise ValueError("Failed runs cannot resume or retry automatically")
    transitions = []
    try:
        while current.cursor < stop:
            current, context = advance(binding, current, observer=observer, **callbacks)
            transitions.append(context)
        if current.status == "ready":
            current = pause(binding, current)
        return (current, tuple(transitions))
    except RunRejected as error:
        raise RunRejected(
            error,
            dict(
                stage="window",
                accepted=error.partial["accepted"],
                window_start=parent,
                stop=stop,
                completed_transitions=tuple(transitions),
                failed_attempt=error.partial,
                automatic_retry=False,
            ),
        ) from error


def request_native_sample(binding, parent):
    verify(binding, parent)
    try:
        composition.sample(binding.composition, parent.active)
    except Exception as error:
        raise RunRejected(
            error,
            dict(
                stage="native_display_refusal",
                accepted=parent,
                component_partial=getattr(error, "partial", None),
                headless_observations=parent.observations,
                native_write2storage_called=False,
                native_display_completed=False,
            ),
        ) from error
    raise AssertionError("Inherited <=16/>=25 display refusal unexpectedly disappeared")


def bind(inputs, component_binding):
    raw = ions.data(inputs)
    if (
        set(raw)
        != {
            "kind",
            "case_id",
            "run_id",
            "component_binding_identity",
            "time_profile",
            "entry_mode",
            "observation_mode",
            "stop_policy",
            "persistence",
        }
        or raw["kind"] != INPUT_KIND
    ):
        raise ValueError("Require complete explicit molecule-aware headless phase run inputs")
    for name in ("case_id", "run_id"):
        if not isinstance(raw[name], str) or not raw[name].strip():
            raise ValueError("Explicit nonempty headless run identity required")
    composition.verify_binding(component_binding)
    if raw["component_binding_identity"] != component_binding.identity:
        raise ValueError("Run declaration is foreign to the actual post-setup phase binding")
    if raw["entry_mode"] != "supplied_molecule54_phase_entry" or raw["persistence"] != "none":
        raise ValueError(
            "Only an actual supplied phase entry without native persistence is admitted"
        )
    if (
        raw["observation_mode"] != "headless_only_native_display_refused"
        or raw["stop_policy"] != "accepted_call_boundaries_only"
    ):
        raise ValueError("Require headless observation and accepted-call stopping contracts")
    declared = profile(raw["time_profile"])
    phase = composition.kind(component_binding)
    actual = composition.calendar(component_binding)
    if raw["time_profile"]["phase"] != phase or not composition.source.equal_tree(
        raw["time_profile"], composition.profile(component_binding)
    ):
        raise ValueError("Run cannot replace, infer or rebase either original phase time profile")
    if declared[phase.lower()] != dict(
        step_count=actual.step_count, dt_s=actual.dt_s, sample_stride=actual.sample_stride
    ):
        raise ValueError("Run clock differs from actual source-truncated phase calendar")
    if phase == "SIM" and (
        actual.step_count != 3 or composition.call_limit(component_binding) != 3
    ):
        raise ValueError("SIM retains its original bounded three-call material domain")
    return Binding(
        component_binding, ions.freeze(raw), ions.digest((LAW_ID, component_binding.identity, raw))
    )


def entry_receipt(binding, entry, *, provenance, previous_phase=None):
    _binding(binding)
    if not isinstance(provenance, str) or not provenance.strip():
        raise ValueError("Declare supplied phase entry provenance")
    if previous_phase is not None:
        verify_completed_INIT(previous_phase)
        if (
            composition.kind(binding.composition) != "SIM"
            or entry.source_init.identity != previous_phase.complete_init.identity
        ):
            raise ValueError(
                "SIM source INIT is foreign to the supplied completed headless INIT run"
            )
    return ions.freeze(
        dict(
            kind=ENTRY_KIND,
            composition_binding_identity=binding.composition.identity,
            composition_state_identity=entry.identity,
            source_calendar_identity=binding.calendar.identity,
            source_call=0,
            phase=composition.kind(binding.composition),
            mode="supplied_molecule54_phase_entry",
            provenance=provenance,
            previous_phase=previous_phase,
            installed_native_initializer_called=False,
            native_load_called=False,
            physical_seed_claim=False,
            declaration_is_initialization_attestation=False,
        )
    )


def _entry(binding, entry, receipt):
    composition.verify(binding.composition, entry)
    actual = composition.phase_state(entry)
    if (
        actual.cursor != 0
        or actual.clock.call_index != 0
        or actual.clock.material_dt_sum_s != 0
        or (actual.mechanics.step_index != 0)
    ):
        raise ValueError(
            "Supplied phase entry must retain actual original zero counters; no implicit restart"
        )
    if (
        actual.history
        or actual.observations
        or actual.status not in ("ready", "exhausted", "capped")
    ):
        raise ValueError(
            "Require the complete fresh headless phase entry, not an evolved or paused prefix"
        )
    if not isinstance(receipt, Mapping) or not isinstance(receipt.get("provenance"), str):
        raise ValueError("Complete supplied phase entry association required")
    expected = entry_receipt(
        binding,
        entry,
        provenance=receipt["provenance"],
        previous_phase=receipt.get("previous_phase"),
    )
    if not composition.source.equal_tree(ions.data(receipt), ions.data(expected)):
        raise ValueError("Changed supplied entry phase, previous run, owner association or scope")


def begin(binding, entry, receipt):
    try:
        _binding(binding)
        _entry(binding, entry, receipt)
        status = (
            "exhausted"
            if entry.cursor == binding.calendar.step_count
            else "capped"
            if composition.phase_state(entry).status == "capped"
            else "ready"
        )
        return _state(binding, entry, receipt, entry, (), (), status)
    except Exception as error:
        raise RunRejected(
            error,
            dict(
                stage="supplied_entry",
                binding_identity=getattr(binding, "identity", None),
                supplied_entry=entry,
                supplied_receipt=receipt,
                native_initializer_called=False,
            ),
        ) from error


@dataclass(frozen=True)
class CompletedInitRun:
    binding: object
    run: object
    complete_init: object
    identity: str


def complete_record(value):
    return (
        LAW_ID,
        "complete_headless_INIT_run",
        value.binding.identity,
        value.run,
        value.complete_init,
    )


def complete_INIT(binding, parent):
    verify(binding, parent)
    if (
        composition.kind(binding.composition) != "INIT"
        or parent.status != "exhausted"
        or parent.cursor != binding.calendar.step_count
        or (parent.cursor != composition.call_limit(binding.composition))
    ):
        raise RunRejected(
            ValueError("Only an exhausted original complete INIT run may cross phases"),
            dict(stage="complete_INIT_run_admission", accepted=parent, automatic_retry=False),
        )
    complete = composition.lifecycle.prepare_complete(binding.composition, parent.active)
    value = CompletedInitRun(binding, parent, complete, "")
    return replace(value, identity=ions.digest(complete_record(value)))


def verify_completed_INIT(value):
    if type(value) is not CompletedInitRun or value.identity != ions.digest(complete_record(value)):
        raise ValueError("Changed complete headless INIT run artifact")
    verify(value.binding, value.run)
    if (
        composition.kind(value.binding.composition) != "INIT"
        or value.run.status != "exhausted"
        or value.run.cursor != value.binding.calendar.step_count
        or (value.run.cursor != composition.call_limit(value.binding.composition))
    ):
        raise ValueError("A failed, capped or paused prefix is not a complete INIT run")
    composition.lifecycle.check_complete(value.complete_init)
    if (
        value.complete_init.binding.identity != value.binding.composition.identity
        or value.complete_init.parent.identity != value.run.active.identity
    ):
        raise ValueError("INIT completion artifact is foreign to the actual accepted headless run")


def transition(
    init_binding,
    init_run,
    sim_component_binding,
    sim_run_inputs,
    *,
    provenance,
    observer=None,
    before_field=None,
):
    completed = None
    stage = "complete_INIT_run_admission"
    try:
        completed = complete_INIT(init_binding, init_run)
        stage = "SIM_run_declaration"
        binding = bind(sim_run_inputs, sim_component_binding)
        if composition.kind(binding.composition) != "SIM":
            raise ValueError("A phase handoff requires an explicit actual SIM transition binding")
        stage = "actual_retained_molecule54_transition"
        entry = composition.lifecycle.transition(
            sim_component_binding,
            completed.complete_init,
            observer=observer,
            before_field=before_field,
        )
        stage = "supplied_SIM_run_entry"
        receipt = entry_receipt(binding, entry, provenance=provenance, previous_phase=completed)
        return (binding, begin(binding, entry, receipt))
    except Exception as error:
        raise RunRejected(
            error,
            dict(
                stage=stage,
                accepted_INIT_run=init_run,
                completed_INIT=completed,
                component_partial=getattr(error, "partial", None),
                automatic_retry=False,
            ),
        ) from error
