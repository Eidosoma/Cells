"""Prepared normal ECM modern catalog + source CaATP + complete field feedback.

This is a separate owned composition. CaATP and field kernels stay unchanged;
original modern gates execute inside the real configured GRN dispatcher.
"""

from dataclasses import dataclass, replace

import numpy as np

from cells.processes import betse_ecm_grn_join as network
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_normal_ecm_calcium_join as calcium_component
from cells.processes import betse_normal_ecm_catalog_join_source as source
from cells.processes import betse_normal_ecm_field_join as full
from cells.processes import betse_normal_ion_join as ions

LAW_ID = "betse_normal_ecm_catalog_CaATP_field_join_v1_5_0@1"
freeze = ions.freeze
Values = material.Values
RateCache, Clock = calcium_component.RateCache, calcium_component.Clock
native_policy, calcium = calcium_component.native_policy, calcium_component.calcium
_material_step = calcium_component._material_step


@dataclass(frozen=True)
class Binding:
    material_binding: object
    voltage_binding: object
    inputs: object
    calcium: object
    catalog: object
    call_limit: int
    identity: str


@dataclass(frozen=True)
class CatalogFieldState:
    binding_identity: str
    network: object
    field: object
    rate_cache: RateCache
    clock: Clock
    identity: str


class CatalogJoinRejected(RuntimeError):
    def __init__(self, error, partial):
        super().__init__(str(error))
        self.partial = freeze(partial)


def bind(raw):
    raw = ions.data(raw)
    if (
        set(raw)
        != {"kind", "case_id", "case_role", "field", "calcium", "catalog", "stop_after_calls"}
        or raw["kind"] != "cells.normal_ecm_catalog_join_inputs@1"
    ):
        raise ValueError("Require a separately owned ECM catalog composition")
    base = calcium_component.bind(
        dict(
            kind="cells.normal_ecm_calcium_join_inputs@1",
            case_id=raw["case_id"],
            case_role=raw["case_role"],
            field=raw["field"],
            calcium=raw["calcium"],
        )
    )
    cb = base.material_binding.geometry_binding.current_binding
    source.validate_catalog(raw["catalog"], list(cb.ion_ids), len(cb.membrane_ids))
    if type(raw["stop_after_calls"]) is not int or not 1 <= raw["stop_after_calls"] <= 3:
        raise ValueError("Require a bounded prefix of the original three-call normal source clock")
    result = Binding(
        base.material_binding,
        base.voltage_binding,
        base.inputs,
        base.calcium,
        freeze(raw["catalog"]),
        raw["stop_after_calls"],
        "",
    )
    return replace(result, identity=ions.digest(composition_record(result)))


def composition_record(binding):
    return (
        LAW_ID,
        binding.material_binding.identity,
        binding.voltage_binding.identity,
        binding.inputs,
        binding.calcium,
        binding.catalog,
        binding.call_limit,
    )


def validate_composition(binding):
    if type(binding) is not Binding or binding.identity != ions.digest(composition_record(binding)):
        raise ValueError("Require the unchanged owned ECM catalog binding")


def failure_snapshot(ctx, supplied):
    result = network._failure_snapshot(ctx, supplied)
    if ctx is not None:
        try:
            result["catalog_cache"] = source.cache(ctx)
        except Exception as error:
            result["catalog_capture_error"] = dict(type=type(error).__name__, message=str(error))
        result["catalog_trace"] = source.clone(ctx.trace)
    return result


def record(parent):
    return (parent.binding_identity, parent.network, parent.field, parent.rate_cache, parent.clock)


def joined_state(binding, network, fields, rate_cache, clock):
    result = CatalogFieldState(binding.identity, network, fields, rate_cache, clock, "")
    return replace(result, identity=ions.digest(record(result)))


def initialize(binding, *, after_cold=None, before_field=None):
    validate_composition(binding)
    parent = material.state(binding.material_binding, ions.data(binding.inputs["initial"]))
    working = Values(*(np.array(v, copy=True) for v in parent.values))
    ctx = network.make_context(binding, working, ions.data(binding.inputs["network"]))
    source.configure(ctx, ions.data(binding.catalog))
    policy = native_policy(ctx, binding)
    try:
        cached = source.cold(ctx)
    except Exception as error:
        raise CatalogJoinRejected(
            error, dict(stage="cold", policy=policy, **failure_snapshot(ctx, None))
        ) from error
    parent = material.state(binding.material_binding, source.material_values(ctx.sim))
    initial = network._state(
        binding, parent, cached, ions.data(binding.inputs["network"])["initial_controls"]
    )
    dt = binding.inputs["bootstrap"]["dt_s"]
    clock = Clock(ions.freeze(np.linspace(0, 3 * dt, 3)), 0, 0.0)
    rate = RateCache(False, None)
    if after_cold is not None:
        after_cold(
            freeze(
                dict(
                    network=initial,
                    policy=policy,
                    rate_cache=rate,
                    clock=clock,
                    channel_trace=ctx.trace,
                )
            )
        )
    try:
        source.validate_cached_channels(ctx, cached)
    except Exception as error:
        raise CatalogJoinRejected(
            error, dict(stage="cold_cache_guard", catalog_cache=cached, channel_trace=ctx.trace)
        ) from error
    try:
        prepared, fields = full.reconstruct(
            binding,
            initial,
            dt,
            ions.data(binding.inputs["bootstrap"]["boundary_V"]),
            "bootstrap",
            before_field,
        )
    except full.FieldJoinRejected as error:
        raise CatalogJoinRejected(
            error, dict(stage="bootstrap", partial=error.partial, rate_cache=rate, clock=clock)
        ) from error
    return joined_state(binding, prepared, fields, rate, clock)


def advance(
    binding,
    parent,
    *,
    before_material=None,
    before_calcium=None,
    before_network=None,
    before_channels=None,
    before_field=None,
    after_calcium=None,
    after_material=None,
):
    validate_composition(binding)
    if (
        type(parent) is not CatalogFieldState
        or parent.binding_identity != binding.identity
        or parent.identity != ions.digest(record(parent))
    ):
        raise ValueError("Require the unchanged owned calcium/field parent")
    fields = parent.field
    if (
        type(fields) is not full.FieldStage
        or fields.binding_identity != binding.identity
        or fields.identity != ions.digest(full.field_record(fields))
    ):
        raise ValueError("Require the actual previous reconstructed full field")
    rate = parent.rate_cache
    m = len(binding.material_binding.geometry_binding.current_binding.membrane_ids)
    if (
        type(rate) is not RateCache
        or type(rate.present) is not bool
        or (
            rate.value is not None
            if not rate.present
            else not isinstance(rate.value, np.ndarray)
            or rate.value.shape != (m,)
            or rate.value.dtype != np.float64
            or rate.value.flags.writeable
            or (not np.isfinite(rate.value).all())
        )
    ):
        raise ValueError(
            "Require actual rate-cache absence or complete immutable source-written rate"
        )
    index = parent.network.material.step_index
    if index >= binding.call_limit:
        raise ValueError("Declared bounded normal-call prefix is complete")
    expected_rate_present = binding.calcium["alpha_Ca"] > 0 and index > 0
    if rate.present is not expected_rate_present:
        raise ValueError(
            "Require actual rate-cache absence or complete immutable source-written rate"
        )
    dt = binding.inputs["bootstrap"]["dt_s"]
    if (
        type(parent.clock) is not Clock
        or not isinstance(parent.clock.source_times_s, np.ndarray)
        or parent.clock.source_times_s.dtype != np.float64
        or (parent.clock.source_times_s.shape != (3,))
        or parent.clock.source_times_s.flags.writeable
        or (parent.clock.call_index != index)
        or (parent.clock.material_dt_sum_s != index * dt)
        or (not np.array_equal(parent.clock.source_times_s, np.linspace(0, 3 * dt, 3)))
    ):
        raise ValueError("Require original normal time vector and accumulated material dt")
    row = ions.data(binding.inputs["steps"][index])
    control = (
        ions.data(parent.network.controls)
        if row["scheduled_controls"] is None
        else row["scheduled_controls"]
    )
    packet = dict(
        row["material"],
        junction_block=control["gj_block"],
        electric_x_source=fields.environment.values.electric_x_source,
        electric_y_source=fields.environment.values.electric_y_source,
    )
    forcing = material.drive(binding.material_binding, packet)
    material_inputs = dict(
        mode="material",
        definition=ions.data(binding.inputs["definition"]),
        initial=ions.data(parent.network.material.values._asdict()),
        # Match the native incoming declaration, before Drive's array coercion.
        # The validated immutable forcing remains the numerical input below.
        steps=[source.clone(packet)],
        calcium=ions.data(binding.calcium),
        rate_cache_before=ions.data(rate),
        clock=ions.data(parent.clock),
        catalog=ions.data(binding.catalog),
        network_cache=ions.data(parent.network.network_cache),
    )
    if before_material is not None:
        before_material(material_inputs)
    holder = {}

    def on_calcium(arrays):
        try:
            result, phase = calcium(binding, arrays, forcing, rate, parent.clock, before_calcium)
        except calcium_component.CalciumJoinRejected as error:
            holder["calcium_failure"] = error.partial
            raise
        holder.update(rate=result, calcium=phase)
        if after_calcium is not None:
            after_calcium(result, phase)

    def on_network(arrays):
        ctx = network.make_context(binding, arrays, ions.data(binding.inputs["network"]), forcing)
        source.configure(ctx, ions.data(binding.catalog))
        holder["ctx"] = ctx
        source.restore(ctx, parent.network.network_cache)
        if any(value != index for value in ctx.channel_calls.values()):
            raise ValueError("Require channel cache counters at the actual material clock epoch")

        native_policy(ctx, binding)
        if holder["rate"].present:
            ctx.sim.rate_CaATP = holder["rate"].value.copy()
        ctx.sim.gj_block = np.asarray(control["gj_block"], np.float64).copy()
        ctx.sim.NaKATP_block = np.asarray(control["NaKATP_block"], np.float64).copy()
        source.run_dispatch(
            ctx,
            ions.data(binding.inputs["definition"]),
            row["publication"],
            float(parent.clock.source_times_s[index]),
            before_network,
            before_channels,
        )

    def failed(local):
        holder["material_partial"] = dict(
            frames=ions.data(tuple(local.get("frames", ()))),
            environment_records=ions.data(tuple(local.get("environment_records", ()))),
            trial=local.get("trial"),
            diagnostics=local.get("diagnostics"),
            failure=local.get("failure"),
            available_arrays={
                name: value.copy() for name, value in local.items() if isinstance(value, np.ndarray)
            },
        )

    try:
        trial = _material_step(
            binding.material_binding,
            parent.network.material,
            forcing,
            on_network=on_network,
            on_failure=failed,
            on_calcium=on_calcium,
        )
        ctx = holder["ctx"]
        source.validate_cached_channels(ctx, source.cache(ctx))
        candidate = network._state(
            binding, trial.candidate, source.cache(ctx), ctx.trace["controls_after"]
        )
    except Exception as error:
        ctx = holder.get("ctx")
        raise CatalogJoinRejected(
            error,
            dict(
                stage="material_calcium_network",
                parent=parent,
                inputs=material_inputs,
                material=holder.get("material_partial"),
                calcium=holder.get("calcium"),
                calcium_failure=holder.get("calcium_failure"),
                network=None if ctx is None else ctx.trace,
                inner_partial=getattr(error, "partial", None),
                **failure_snapshot(ctx, parent.network.network_cache),
            ),
        ) from error
    if after_material is not None:
        after_material(candidate, trial, ctx.trace, holder["calcium"])
    try:
        prepared, next_fields = full.reconstruct(
            binding, candidate, forcing.dt_s, row["boundary_V"], "field", before_field
        )
    except full.FieldJoinRejected as error:
        raise CatalogJoinRejected(
            error,
            dict(
                stage="field",
                parent=parent,
                material_parent=candidate,
                trial=trial,
                calcium=holder["calcium"],
                network=ctx.trace,
                partial=error.partial,
            ),
        ) from error
    clock = Clock(parent.clock.source_times_s, index + 1, (index + 1) * dt)
    result = joined_state(binding, prepared, next_fields, holder["rate"], clock)
    return (
        result,
        trial,
        freeze(ctx.trace),
        holder["calcium"],
        dict(
            material_parent=candidate,
            initial_field=fields,
            fields=next_fields,
            clock_before=parent.clock,
            clock_after=clock,
        ),
    )
