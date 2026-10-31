"""Owned SIM events on actual supplied molecule54 owners; no physical initializer."""

from dataclasses import dataclass, replace
from types import SimpleNamespace

import numpy as np

from cells.core import physiology_native_calendar as calendars
from cells.processes import betse_ecm_grn_join as network
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_normal_ecm_event_join as event42
from cells.processes import betse_normal_ecm_event_join_source as events
from cells.processes import betse_normal_ecm_field_join as full
from cells.processes import betse_normal_ecm_molecule_lifecycle as leaf
from cells.processes import betse_normal_ecm_molecule_lifecycle_phase as phase
from cells.processes import betse_normal_ion_join as ions

LAW_ID = "betse_supplied_ECM_molecule_SIM_events_v1_5_0@1"
INPUT_KIND = "cells.normal_ecm_molecule_SIM_event_inputs@1"
SCOPE = dict(
    phase="SIM",
    solver="FULL",
    geometry_cutting=False,
    flow=False,
    active_mechanics=False,
    dynamic_noise=False,
    dynamic_gate_expansion=False,
    physical_initializer=False,
    native_storage=False,
)
MUTABLE_STORES = set(events.EVENT_STORES) | {"div_u_osmo"}


@dataclass(frozen=True)
class Binding:
    source_binding: object
    source_entry: object
    raw: object
    identity: str

    @property
    def base(self):
        return self.source_entry.phase_binding

    @property
    def material_binding(self):
        return self.base.material_binding

    @property
    def inputs(self):
        return self.base.inputs

    @property
    def catalog(self):
        return self.base.catalog

    @property
    def calendar(self):
        return self.base.calendar

    @property
    def call_limit(self):
        return self.base.call_limit


@dataclass(frozen=True)
class State:
    binding_identity: str
    network: object
    field: object
    rate_cache: object
    nak_rate: object
    mechanics: object
    stores: object
    clock: object
    history: tuple
    observations: tuple
    runtime_material_binding: object
    runtime_definition: object
    entry_receipt: object
    status: str
    identity: str

    @property
    def cursor(self):
        return self.clock.call_index


class EventsRejected(RuntimeError):
    def __init__(self, error, partial):
        super().__init__(str(error))
        self.partial = ions.freeze(partial)


def binding_record(value):
    return (LAW_ID, value.source_binding.identity, value.source_entry, value.raw)


def record(value):
    return tuple(getattr(value, key) for key in State.__dataclass_fields__ if key != "identity")


def state(
    binding,
    net,
    field,
    rate,
    nak,
    mechanical,
    stores,
    clock,
    history=(),
    observations=(),
    status=None,
    *,
    runtime_material_binding=None,
    runtime_definition=None,
    entry_receipt=None,
):
    if status is None:
        status = (
            "exhausted"
            if clock.call_index == binding.calendar.step_count
            else "capped"
            if clock.call_index == binding.call_limit
            else "ready"
        )
    value = State(
        binding.identity,
        net,
        field,
        rate,
        nak,
        mechanical,
        ions.freeze(stores),
        clock,
        tuple(history),
        tuple(observations),
        runtime_material_binding or binding.material_binding,
        ions.freeze(
            material.plain(
                runtime_definition
                if runtime_definition is not None
                else binding.inputs["definition"]
            )
        ),
        ions.freeze(entry_receipt),
        status,
        "",
    )
    return replace(value, identity=ions.digest(record(value)))


def verify_binding(binding):
    if type(binding) is not Binding or binding.identity != ions.digest(binding_record(binding)):
        raise ValueError("Require unchanged complete owned SIM-event binding")
    leaf.validate_binding(binding.source_binding)
    leaf.verify(binding.source_binding, binding.source_entry)
    entry = binding.source_entry.active
    if entry.cursor != 0 or entry.history or entry.observations or entry.status != "ready":
        raise ValueError("Event composition requires the actual fresh original SIM entry")
    if (
        binding.calendar.phase != "SIM"
        or binding.calendar.step_count != 3
        or binding.call_limit != 3
    ):
        raise ValueError("Retain the original separate bounded SIM N3 calendar")
    if set(binding.raw["scope"]) != set(SCOPE) or any(
        type(binding.raw["scope"][key]) is not type(expected)
        or binding.raw["scope"][key] != expected
        for key, expected in SCOPE.items()
    ):
        raise ValueError("Unsupported event composition scope expansion")
    if (
        binding.raw["source_binding_identity"] != binding.source_binding.identity
        or binding.raw["source_entry_identity"] != binding.source_entry.identity
    ):
        raise ValueError("Foreign actual source INIT/SIM association")
    event42.validate_owner(binding, ions.data(binding.raw["event_owner"]))
    original_owner = binding.base.setup_receipt["event_finalization"]["source_fields"]["owner"]
    for key in (
        "configured_environment",
        "tissue_default",
        "owners",
        "tissue_target_inds",
        "cell_target_inds",
        "env_target_inds",
    ):
        if not leaf.catalog.equal_tree(binding.raw["event_owner"][key], original_owner[key]):
            raise ValueError(
                "Event composition cannot replace actual configured source/profile owners: " + key
            )


def bind(inputs, source_binding, source_entry):
    raw = ions.data(inputs)
    if (
        set(raw)
        != {
            "kind",
            "case_id",
            "provenance",
            "source_binding_identity",
            "source_entry_identity",
            "scope",
            "event_owner",
        }
        or raw["kind"] != INPUT_KIND
    ):
        raise ValueError(
            "Require complete explicit separately supplied finalized SIM-event owner declaration"
        )
    if any(
        not isinstance(raw[key], str) or not raw[key].strip() for key in ("case_id", "provenance")
    ):
        raise ValueError("Declare supplied finalized event-owner provenance")
    value = Binding(source_binding, source_entry, ions.freeze(raw), "")
    value = replace(value, identity=ions.digest(binding_record(value)))
    verify_binding(value)
    return value


def working(binding, runtime=None, definition=None):
    base = binding.base
    inputs = ions.data(base.inputs)
    if definition is not None:
        inputs["definition"] = ions.data(definition)
    return SimpleNamespace(
        identity=binding.identity,
        material_binding=base.material_binding if runtime is None else runtime,
        voltage_binding=base.voltage_binding,
        inputs=ions.freeze(inputs),
        inputs_raw=base.inputs_raw,
        calcium=base.calcium,
        catalog=base.catalog,
        mechanics=base.mechanics,
        setup_receipt=base.setup_receipt,
        calendar=base.calendar,
        call_limit=base.call_limit,
    )


def snapshot(ctx):
    return dict(phase.setup.snapshot(ctx), **events.event_snapshot(ctx.sim))


def event_stores(stores):
    return {key: ions.data(stores[key]) for key in events.EVENT_STORES}


def begin(binding, *, before_entry_controls=None, after_entry_controls=None):
    ctx, before, after = None, None, None
    try:
        verify_binding(binding)
        original = binding.source_entry.active
        view = working(binding)
        ctx = phase.owner_context(
            view, [np.array(v, copy=True) for v in original.network.material.values]
        )
        phase.restore_owners(ctx, original.network.network_cache, 0)
        phase.install_stores(ctx, ions.data(original.stores))
        events.install_owner(
            ctx, ions.data(binding.raw["event_owner"]), event_stores(snapshot(ctx))
        )
        before = dict(
            mode="entry_controls",
            source_phase="SIM",
            legacy_run_sim=True,
            membranes=ctx.sim.mdl,
            global_options=ions.data(binding.raw["event_owner"]["global_options"]),
            controls={
                key: phase.source.clone(getattr(ctx.sim, key))
                for key in ("gj_block", "NaKATP_block")
            },
            owners=phase.owners.cache(ctx),
            native=phase.owners.conditional_input(
                ctx, "entry", ions.data(view.inputs["definition"]), 0.0
            ),
        )
        if before_entry_controls is not None:
            before_entry_controls(ions.freeze(before))
        from cells.processes.betse_normal_ecm_molecule_events_source import entry_controls

        entry_controls(ctx.sim, ctx.cells, ctx.p)
        after = dict(
            controls={
                key: phase.source.clone(getattr(ctx.sim, key))
                for key in ("gj_block", "NaKATP_block")
            },
            owners=phase.owners.cache(ctx),
        )
        receipt = dict(
            kind="cells.actual_SIM_event_control_entry@1",
            source_entry_identity=binding.source_entry.identity,
            before=before,
            after=after,
            source_control_initializations=1,
            native_physical_initializer_called=False,
            source_owner_cold_or_reinitialize_called=False,
        )
        if after_entry_controls is not None:
            after_entry_controls(ions.freeze(receipt))
        stores = snapshot(ctx)
        event42.validate_stores(binding, event_stores(stores))
        net = network._state(
            binding, original.network.material, phase.owners.cache(ctx), after["controls"]
        )
        value = state(
            binding,
            net,
            original.field,
            original.rate_cache,
            original.nak_rate,
            original.mechanics,
            stores,
            original.clock,
            entry_receipt=receipt,
        )
        verify(binding, value)
        return value
    except Exception as error:
        raise EventsRejected(
            error,
            dict(
                stage="supplied_SIM_event_entry",
                source_entry=getattr(binding, "source_entry", None),
                before_entry_controls=before,
                after_entry_controls=after,
                inner_partial=getattr(error, "partial", None),
                native_initializer_called=False,
                **failure_snapshot(ctx, None),
            ),
        ) from error


def verify(binding, parent):
    verify_binding(binding)
    if (
        type(parent) is not State
        or parent.binding_identity != binding.identity
        or parent.identity != ions.digest(record(parent))
    ):
        raise ValueError("Require complete immutable actual event/molecule parent")
    index = parent.cursor
    if (
        type(index) is not int
        or not 0 <= index <= binding.call_limit
        or index != parent.network.material.step_index
        or index != parent.mechanics.step_index
    ):
        raise ValueError("Event, molecule, material and held-mechanics epochs differ")
    receipt = parent.entry_receipt
    if (
        receipt["kind"] != "cells.actual_SIM_event_control_entry@1"
        or receipt["source_entry_identity"] != binding.source_entry.identity
        or receipt["source_control_initializations"] != 1
        or receipt["native_physical_initializer_called"]
        or receipt["source_owner_cold_or_reinitialize_called"]
    ):
        raise ValueError("Require the actual separate source control entry receipt")
    if not leaf.catalog.equal_tree(
        receipt["before"]["owners"], binding.source_entry.active.network.network_cache
    ):
        raise ValueError("Event entry must preserve the actual incoming warm owners")
    for key in ("gj_block", "NaKATP_block"):
        expected = (
            np.ones(len(binding.material_binding.geometry_binding.current_binding.membrane_ids))
            if binding.raw["event_owner"]["global_options"][key] != 0
            else 1
        )
        if not leaf.catalog.equal_tree(receipt["after"]["controls"][key], expected):
            raise ValueError("Configured source event control scalar/vector branch changed")
        if not leaf.catalog.equal_tree(
            receipt["before"]["controls"][key], binding.source_entry.active.network.controls[key]
        ):
            raise ValueError("Event entry controls must start from the actual warm source epoch")
    expected_cache = ions.data(binding.source_entry.active.network.network_cache)
    for key in ("gj_block", "NaKATP_block"):
        expected_cache["shared"][key] = receipt["after"]["controls"][key]
    if not leaf.catalog.equal_tree(receipt["after"]["owners"], expected_cache):
        raise ValueError("Only the two actual source control entries may change warm owner cache")
    if index == 0 and not leaf.catalog.equal_tree(
        parent.network.network_cache, receipt["after"]["owners"]
    ):
        raise ValueError("Initial event parent differs from its actual complete returned owners")
    if (
        type(parent.clock) is not phase.Clock
        or parent.clock.source_times_s.flags.writeable
        or parent.clock.source_times_s.dtype != np.float64
        or not np.array_equal(
            parent.clock.source_times_s, calendars.window(binding.calendar).event_label_s
        )
        or parent.clock.material_dt_sum_s != index * binding.calendar.dt_s
    ):
        raise ValueError("Original SIM labels and accumulated dt cannot be rebased")
    original = binding.source_entry.active
    if index == 0:
        for actual, wanted in (
            (parent.network.material.identity, original.network.material.identity),
            (parent.field.identity, original.field.identity),
            (parent.mechanics.identity, original.mechanics.identity),
        ):
            if actual != wanted:
                raise ValueError(
                    "Supplied initial event buffers cannot replace the actual retained SIM entry"
                )
        for key in ("rate_cache", "nak_rate"):
            if not leaf.catalog.equal_tree(
                ions.data(getattr(parent, key)), ions.data(getattr(original, key))
            ):
                raise ValueError(
                    "Supplied initial event rate cache differs from the actual source entry"
                )
    if set(parent.stores) != set(original.stores) | set(events.EVENT_STORES):
        raise ValueError("Require every setup and event store, including scalar presence")
    stores = event42.validate_stores(binding, event_stores(parent.stores))
    for key in set(original.stores) - MUTABLE_STORES:
        if not leaf.catalog.equal_tree(parent.stores[key], original.stores[key]):
            raise ValueError("Changed held setup store: " + key)
    runtime = parent.runtime_material_binding
    material.validate_binding(runtime)
    if runtime.geometry_binding.identity != binding.material_binding.geometry_binding.identity:
        raise ValueError("Changing event coefficients cannot change frozen geometry")
    expected, definition = event42.runtime_material(binding, stores)
    if runtime.identity != expected.identity or not leaf.catalog.equal_tree(
        material.plain(parent.runtime_definition), material.plain(definition)
    ):
        raise ValueError("Material binding must be legally lowered from actual event coefficients")
    checked = material.state(
        runtime, ions.data(parent.network.material.values._asdict()), step_index=index
    )
    if checked.identity != parent.network.material.identity:
        raise ValueError("Changed complete source material buffers")
    if (
        parent.network.binding_identity != binding.identity
        or parent.network.identity
        != network._state(
            binding, parent.network.material, parent.network.network_cache, parent.network.controls
        ).identity
    ):
        raise ValueError("Changed complete two-owner material/cache/control epoch")
    for key in ("gj_block", "NaKATP_block"):
        if not leaf.catalog.equal_tree(parent.network.controls[key], stores[key]):
            raise ValueError("Event and post-owner shared controls differ")
    view = working(binding, runtime, definition)
    ctx = phase.owner_context(
        view, [np.array(v, copy=True) for v in parent.network.material.values]
    )
    phase.restore_owners(ctx, parent.network.network_cache, index)
    for key in set(events.EVENT_STORES) & set(phase.owners.SHARED):
        if not leaf.catalog.equal_tree(
            parent.network.network_cache["shared"][key], parent.stores[key]
        ):
            raise ValueError("Shared/event duplicate stores differ at accepted epoch: " + key)
    phase.mechanics._verify(binding.base.mechanics, parent.mechanics)
    if parent.mechanics.sampled_steps:
        raise ValueError("Native display/storage completion is outside the held domain")
    m = len(binding.material_binding.geometry_binding.current_binding.membrane_ids)
    phase.check_rate(
        parent.rate_cache,
        m,
        binding.base.setup_receipt.get("entry_CaATP_present", False)
        or index > 0
        and binding.base.calcium["alpha_Ca"] > 0,
    )
    phase.check_rate(
        parent.nak_rate, m, binding.base.setup_receipt.get("entry_NaK_present", False) or index > 0
    )
    if (
        type(parent.field) is not full.FieldStage
        or parent.field.identity != ions.digest(full.field_record(parent.field))
        or parent.field.binding_identity
        != (original.field.binding_identity if index == 0 else binding.identity)
    ):
        raise ValueError("Require the complete actually preceding reconstructed field")
    samples = calendars.window(binding.calendar, stop=index).sampled
    if len(parent.history) != index or len(parent.observations) != sum(bool(v) for v in samples):
        raise ValueError("Require every actual accepted event call and eligible observation")
    for j, row in enumerate(parent.history):
        if (
            row["call_index"] != j
            or row["source_label_s"] != float(parent.clock.source_times_s[j])
            or row["dt_s"] != binding.calendar.dt_s
            or row["event_fire_calls"] != 1
            or row["pre_event_flux_reset_calls"] != 1
            or row["protein_noise_calls"] != 0
            or row["event_owner_identity"] != ions.digest(binding.raw["event_owner"])
        ):
            raise ValueError("Changed source event order, labels, owner or reset/noise counts")
        if [stage["stage"] for stage in row["event_trace"]["stages"]] != [
            "_fire_events_global",
            "_fire_events_tissue",
            "makeAllChanges",
        ] or not row["event_trace"]["source_completed"]:
            raise ValueError("Only complete actual event firing can enter the accepted journal")
        if row["event_trace"]["source_time_s"] != row["source_label_s"]:
            raise ValueError("Event source labels must match their accepted call")
    if index > 0 and (
        parent.history[-1]["after_network_identity"] != parent.network.identity
        or parent.history[-1]["after_field_identity"] != parent.field.identity
    ):
        raise ValueError("The final accepted receipt must retain its actual field/network state")
    for observation, j in zip(
        parent.observations, [j for j, flag in enumerate(samples) if flag], strict=True
    ):
        if (
            observation["call_index"] != j
            or observation["native_storage_called"]
            or observation["display_completed"]
        ):
            raise ValueError("Only headless observations at original native sample boundaries")
        net, field = observation["network"], observation["field"]
        if (
            net.identity != parent.history[j]["after_network_identity"]
            or field.identity != parent.history[j]["after_field_identity"]
            or net.binding_identity != binding.identity
            or net.identity
            != network._state(binding, net.material, net.network_cache, net.controls).identity
            or field.binding_identity != binding.identity
            or field.identity != ions.digest(full.field_record(field))
            or net.material.step_index != j + 1
        ):
            raise ValueError("Headless observation must retain the complete reached epoch")
    expected_status = (
        "exhausted"
        if index == binding.calendar.step_count
        else "capped"
        if index == binding.call_limit
        else "ready"
    )
    if parent.status not in {
        expected_status,
        "failed",
        "paused" if expected_status == "ready" else expected_status,
    }:
        raise ValueError("Actual source cursor and phase run status differ")
    return parent


def prepare_events(binding, parent, holder, before_events, after_events, event_observer):
    view = working(binding, parent.runtime_material_binding, parent.runtime_definition)
    ctx = phase.owner_context(
        view, [np.array(v, copy=True) for v in parent.network.material.values]
    )
    holder["ctx"] = ctx
    phase.restore_owners(ctx, parent.network.network_cache, parent.cursor)
    phase.install_stores(ctx, ions.data(parent.stores))
    events.install_owner(ctx, ions.data(binding.raw["event_owner"]), event_stores(parent.stores))
    entry = dict(
        mode="events",
        owner=ions.data(binding.raw["event_owner"]),
        before=events.event_snapshot(ctx.sim),
        material_before=phase.source.material_values(ctx.sim),
        clock=ions.data(parent.clock),
        source_time_s=float(parent.clock.source_times_s[parent.cursor]),
        configured_temperature_K=ctx.p.T,
        dt_s=binding.calendar.dt_s,
        ion_ids=list(ctx.ion_ids),
        valence=phase.source.clone(ctx.sim.zs),
        source_phase="SIM",
        legacy_run_sim=True,
        native=phase.owners.conditional_input(
            ctx,
            "entry",
            ions.data(view.inputs["definition"]),
            float(parent.clock.source_times_s[parent.cursor]),
        ),
        prepared_rng=ions.data(binding.base.setup_receipt["numpy_rng_after"]),
    )
    holder["before_events"] = entry
    holder["stage"] = "before_events"
    if before_events is not None:
        before_events(ions.freeze(entry))
    holder["stage"] = "flux_reset"
    events.reset_fluxes(ctx.sim, ctx.p)
    holder["reset_return"] = phase.source.material_values(ctx.sim)
    holder["stage"] = "events"
    result = events.fire(ctx, float(parent.clock.source_times_s[parent.cursor]), event_observer)
    holder["events"] = result
    if after_events is not None:
        after_events(ions.freeze(result))
    stores = snapshot(ctx)
    holder["post_event_stores"] = stores
    holder["stage"] = "event_coefficient_lowering"
    runtime, definition = event42.runtime_material(binding, event_stores(stores))
    lowered = material.state(
        runtime, phase.source.material_values(ctx.sim), step_index=parent.cursor
    )
    holder.update(runtime_binding=runtime, lowered_parent=lowered, definition=definition)
    return working(binding, runtime, definition), lowered, stores


def failure_snapshot(ctx, supplied):
    value = phase.phase_failure_snapshot(ctx, supplied)
    value["available_event_stores"] = (
        {}
        if ctx is None
        else {
            key: phase.source.clone(getattr(ctx.sim, key))
            for key in events.EVENT_STORES
            if hasattr(ctx.sim, key)
        }
    )
    value["missing_event_stores"] = (
        list(events.EVENT_STORES)
        if ctx is None
        else [key for key in events.EVENT_STORES if not hasattr(ctx.sim, key)]
    )
    return value


def advance(binding, parent, **callbacks):
    admitted = False
    try:
        verify(binding, parent)
        if parent.status != "ready":
            raise ValueError("Only an actual ready event run may advance; no failed-prefix retry")
        admitted = True
        from cells.processes.betse_normal_ecm_molecule_events_step import advance as source_advance

        return source_advance(binding, parent, **callbacks)
    except Exception as error:
        partial = getattr(error, "partial", None)
        accepted = parent if admitted else None
        if isinstance(partial, dict) or hasattr(partial, "get"):
            candidate = partial.get("available", {}).get("accepted")
            if type(candidate) is State:
                verify(binding, candidate)
                accepted = candidate
        if accepted is not None:
            accepted = replace(accepted, status="failed", identity="")
            accepted = replace(accepted, identity=ions.digest(record(accepted)))
        raise EventsRejected(
            error,
            dict(
                stage="source_call" if admitted else "admission",
                caller_parent=parent,
                accepted=accepted,
                source_partial=partial,
                automatic_retry=False,
                original_source_entry=getattr(binding, "source_entry", None),
            ),
        ) from error


def pause(binding, parent):
    verify(binding, parent)
    if parent.status != "ready":
        raise ValueError("Pause only at an accepted unfinished call boundary")
    value = replace(parent, status="paused", identity="")
    return replace(value, identity=ions.digest(record(value)))


def resume(binding, parent):
    verify(binding, parent)
    if parent.status != "paused":
        raise ValueError("Resume only the exact explicitly paused event parent")
    value = replace(parent, status="ready", identity="")
    return replace(value, identity=ions.digest(record(value)))


def run_window(binding, parent, *, stop, **callbacks):
    verify(binding, parent)
    if type(stop) is not int or not parent.cursor <= stop <= binding.call_limit:
        raise ValueError("Window must retain original SIM source calendar and bounded stop")
    current = resume(binding, parent) if parent.status == "paused" else parent
    if current.status not in ("ready", "exhausted"):
        raise ValueError("A failed or capped prefix cannot resume")
    contexts = []
    try:
        while current.cursor < stop:
            current, detail = advance(binding, current, **callbacks)
            contexts.append(detail)
        return (pause(binding, current) if current.status == "ready" else current, tuple(contexts))
    except EventsRejected as error:
        raise EventsRejected(
            error,
            dict(
                stage="window",
                accepted=error.partial["accepted"],
                window_start=parent,
                stop=stop,
                completed_transitions=tuple(contexts),
                failed_attempt=error.partial,
                automatic_retry=False,
            ),
        ) from error
