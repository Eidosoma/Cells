"""Headless in-memory SIM/N3 lifecycle on explicitly supplied component entry.

This coordinator calls the existing composition once per accepted call. It does
not run native seed/init/load, native write2storage, display or pickle methods.
Source labels and update dt remain separate; pause windows retain the original
calendar and complete source-owned caches.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, replace

from cells.core import physiology_native_calendar as calendars
from cells.processes import betse_normal_ecm_event_mechanics as composition
from cells.processes import betse_normal_ion_join as ions

LAW_ID = "betse_normal_ecm_headless_supplied_SIM_run_v1_5_0@1"
INPUT_KIND = "cells.normal_ecm_headless_run_inputs@1"
ENTRY_KIND = "cells.supplied_component_phase_entry_declaration@1"
STATUS = {"ready", "paused", "exhausted", "failed"}


@dataclass(frozen=True)
class Binding:
    composition: object
    inputs: object
    identity: str

    @property
    def calendar(self):
        return self.composition.events.calendar


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
        return self.active.events.clock.call_index


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
        or not isinstance(raw["provenance"], str)
        or not raw["provenance"].strip()
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


def bind(inputs):
    raw = ions.data(inputs)
    if (
        set(raw)
        != {
            "kind",
            "case_id",
            "run_id",
            "composition_inputs",
            "time_profile",
            "entry_mode",
            "observation_mode",
            "stop_policy",
            "persistence",
        }
        or raw["kind"] != INPUT_KIND
    ):
        raise ValueError("Require a complete separate headless lifecycle declaration")
    for name in ("case_id", "run_id"):
        if not isinstance(raw[name], str) or not raw[name].strip():
            raise ValueError("Require explicit lifecycle identity: " + name)
    if (
        raw["entry_mode"] != "supplied_component_cold_bootstrap_subset"
        or raw["persistence"] != "none"
    ):
        raise ValueError("Native seed/init/load/persistence require separate qualified ownership")
    if (
        raw["observation_mode"] != "headless_only_native_display_refused"
        or raw["stop_policy"] != "accepted_call_boundaries_only"
    ):
        raise ValueError("Require headless observations and stopping at accepted call boundaries")
    time = profile(raw["time_profile"])
    if raw["time_profile"]["phase"] != "SIM":
        raise ValueError(
            "This inherited composition admits SIM/N3 only; INIT execution stays closed"
        )
    joined = composition.bind(raw["composition_inputs"])
    expected = time["sim"]
    calendar = joined.events.calendar
    if (
        joined.events.call_limit != 3
        or calendar.phase != "SIM"
        or calendar.step_count != 3
        or expected
        != dict(
            step_count=calendar.step_count, dt_s=calendar.dt_s, sample_stride=calendar.sample_stride
        )
    ):
        raise ValueError(
            "Native truncated count/dt/stride must match the original SIM/N3 component calendar"
        )
    return Binding(joined, ions.freeze(raw), ions.digest((LAW_ID, joined.identity, raw)))


def _binding(binding):
    if type(binding) is not Binding or binding.identity != ions.digest(
        (LAW_ID, binding.composition.identity, binding.inputs)
    ):
        raise ValueError("Changed complete headless run binding")
    composition.verify_binding(binding.composition)
    calendars.validate(binding.calendar)


def entry_receipt(binding, entry, *, provenance):
    """Declare association of supplied state; this does not attest native init calls."""
    _binding(binding)
    if not isinstance(provenance, str) or not provenance.strip():
        raise ValueError("Declare supplied entry provenance")
    return ions.freeze(
        dict(
            kind=ENTRY_KIND,
            composition_binding_identity=binding.composition.identity,
            composition_state_identity=entry.identity,
            source_calendar_identity=binding.calendar.identity,
            source_call=0,
            phase="SIM",
            mode="supplied_component_cold_bootstrap_subset",
            provenance=provenance,
            installed_native_initializer_called=False,
            native_load_called=False,
            physical_seed_claim=False,
            declaration_is_initialization_attestation=False,
        )
    )


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


def _entry(binding, entry, receipt):
    composition.verify(binding.composition, entry)
    ep = entry.events
    if (
        type(ep) is not composition.event.EventFieldState
        or ep.binding_identity != binding.composition.events.identity
        or ep.identity != ions.digest(composition.event.record(ep))
    ):
        raise ValueError("Require the complete supplied event/network/noise entry owner")
    if (
        type(ep.field) is not composition.full.FieldStage
        or ep.field.binding_identity != binding.composition.events.identity
        or ep.field.identity != ions.digest(composition.full.field_record(ep.field))
    ):
        raise ValueError("Require complete supplied bootstrap fields")
    if not isinstance(ep.network.network_cache, Mapping) or "wire" not in ep.network.network_cache:
        raise ValueError("Require complete supplied network/channel caches")
    if (
        type(ep.clock.call_index) is not int
        or ep.clock.call_index != 0
        or ep.clock.material_dt_sum_s != 0.0
        or entry.mechanics.step_index != 0
    ):
        raise ValueError(
            "Fresh phase entry must have source counters zero; no implicit restart/reset"
        )
    if not isinstance(receipt, Mapping) or not isinstance(receipt.get("provenance"), str):
        raise ValueError("Require a complete supplied initialization declaration")
    expected = entry_receipt(binding, entry, provenance=receipt["provenance"])
    if not composition.source.equal_tree(receipt, expected):
        raise ValueError("Supplied initialization association/scope changed")


def begin(binding, entry, receipt):
    try:
        _binding(binding)
        _entry(binding, entry, receipt)
        # These empty histories belong to this headless coordinator. Native
        # clear_storage/init_dynamics/bootstrap are not called by begin().
        return _state(binding, entry, receipt, entry, (), (), "ready")
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


def verify(binding, parent):
    _binding(binding)
    if (
        type(parent) is not RunState
        or parent.binding_identity != binding.identity
        or parent.identity != ions.digest(_record(parent))
        or parent.status not in STATUS
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
                type(value) is not float
                for value in (
                    record.source_label_s,
                    record.elapsed_start_s,
                    record.elapsed_end_s,
                    record.dt_s,
                )
            )
            or record.call_index != index
            or record.before_identity != previous
            or record.source_label_s != float(rows.event_label_s[index])
            or record.dt_s != binding.calendar.dt_s
            or record.elapsed_start_s != float(rows.elapsed_start_s[index])
            or record.elapsed_end_s != float(rows.elapsed_end_s[index])
            or record.sample_eligible is not bool(rows.sampled[index])
        ):
            raise ValueError("Accepted source label/dt/owner journal changed")
        previous = record.after_identity
        if record.sample_eligible:
            expected_samples.append(index)
    if any(type(o) is not Observation for o in parent.observations):
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
            or type(observation.native_display_completed) is not bool
            or observation.state.identity != parent.history[index].after_identity
            or observation.source_label_s != parent.history[index].source_label_s
            or observation.elapsed_end_s != parent.history[index].elapsed_end_s
            or observation.native_write2storage_called
            or observation.native_display_completed
            or observation.mode != "headless_observation_at_native_sample_boundary"
        ):
            raise ValueError("Headless observation must retain its exact reached state and scope")
        composition.verify(binding.composition, observation.state)
    if parent.status == "exhausted" and cursor != binding.calendar.step_count:
        raise ValueError("Run marked exhausted before the last source call")
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
            if candidate.events.clock.call_index == binding.calendar.step_count
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
        # The full call is accepted before notification. An observer error
        # retains this accepted candidate and cannot cause an automatic retry.
        stage = "accepted_call_observer"
        if observer is not None:
            observer("accepted_call", dict(parent=current, context=context))
        if record.sample_eligible and observer is not None:
            stage = "headless_observation_observer"
            observer("headless_observation", current.observations[-1])
        return current, ions.freeze(context)
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
    if type(stop) is not int or not parent.cursor <= stop <= binding.calendar.step_count:
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
        return current, tuple(transitions)
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
