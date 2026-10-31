"""One supplied-state ECM event/noise/steady-mechanics call in native order.

Sampling eligibility is carried; display output is explicitly refused within
this inherited <=16-cell field domain. No physical seed or whole solver claim.
"""

from dataclasses import dataclass

from cells.processes import betse_mechanics_join as mechanics
from cells.processes import betse_normal_ecm_event_join as event
from cells.processes.betse_normal_ecm_event_join import (
    Clock,
    EventFieldState,
    EventJoinRejected,
    NoiseCache,
    RateCache,
    _broadcast,
    _context,
    _install_noise_cache,
    _noise_cache,
    calcium_component,
    calendars,
    catalog_component,
    event_material,
    events,
    full,
    ions,
    joined_state,
    material,
    network,
    np,
    random_source,
    record,
    runtime_material,
    source,
    validate_composition,
    validate_stores,
)


def _advance_events(
    binding,
    parent,
    *,
    before_events=None,
    after_events=None,
    before_material=None,
    before_calcium=None,
    before_channels=None,
    before_network=None,
    before_noise=None,
    before_field=None,
    after_calcium=None,
    after_noise=None,
    after_material=None,
    on_mechanics=None,
):
    validate_composition(binding)
    if (
        type(parent) is not EventFieldState
        or parent.binding_identity != binding.identity
        or parent.identity != ions.digest(record(parent))
    ):
        raise ValueError("Require the unchanged owned event/channel/material parent")
    index = parent.network.material.step_index
    dt = binding.calendar.dt_s
    if index >= binding.call_limit:
        raise ValueError("Declared bounded normal-call prefix is complete")
    if (
        type(parent.clock) is not Clock
        or not isinstance(parent.clock.source_times_s, np.ndarray)
        or parent.clock.source_times_s.dtype != np.float64
        or (parent.clock.source_times_s.shape != (3,))
        or parent.clock.source_times_s.flags.writeable
        or (parent.clock.call_index != index)
        or (parent.clock.material_dt_sum_s != index * dt)
        or (
            not np.array_equal(
                parent.clock.source_times_s, calendars.window(binding.calendar).event_label_s
            )
        )
    ):
        raise ValueError("Require original source labels and separate accumulated material dt")
    if (
        type(parent.field) is not full.FieldStage
        or parent.field.binding_identity != binding.identity
        or parent.field.identity != ions.digest(full.field_record(parent.field))
    ):
        raise ValueError("Require the actual preceding full field")
    rate = parent.rate_cache
    m = len(binding.material_binding.geometry_binding.current_binding.membrane_ids)
    if (
        type(rate) is not RateCache
        or rate.present is not (binding.calcium["alpha_Ca"] > 0 and index > 0)
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
        raise ValueError("Require actual CaATP rate absence or complete immutable source cache")
    stores = validate_stores(binding, ions.data(parent.event_stores))
    for key in ("gj_block", "NaKATP_block"):
        if not source.equal_tree(parent.network.controls[key], stores[key]):
            raise ValueError("Event and GRN control owners differ at the actual parent epoch")
    stream = parent.noise_stream
    random_source.native_stream_manifest(stream)
    nc = parent.noise_cache
    if (
        type(nc) is not NoiseCache
        or type(nc.present) is not bool
        or (
            nc.value is not None
            if not nc.present
            else not isinstance(nc.value, np.ndarray)
            or nc.value.dtype != np.float64
            or nc.value.shape != (m,)
            or nc.value.flags.writeable
            or (not np.isfinite(nc.value).all())
        )
    ):
        raise ValueError("Require complete immutable actual protein-noise cache or absence")
    row = ions.data(binding.inputs["steps"][index])
    holder = dict(parent=parent)
    ctx = _context(
        binding, material.Values(*(np.array(v, copy=True) for v in parent.network.material.values))
    )
    try:
        source.restore(ctx, parent.network.network_cache)
        events.install_owner(ctx, ions.data(binding.event_owner), stores)
        _install_noise_cache(ctx, nc)
        ctx.phase.kind = "SIM"
        entry = dict(
            mode="events",
            owner=ions.data(binding.event_owner),
            before=events.event_snapshot(ctx.sim),
            material_before=source.material_values(ctx.sim),
            clock=ions.data(parent.clock),
            source_time_s=float(parent.clock.source_times_s[index]),
            configured_temperature_K=ctx.p.T,
            dt_s=dt,
            ion_ids=list(ctx.ion_ids),
            valence=source.clone(ctx.sim.zs),
        )
        holder["before_events"] = entry
        if before_events is not None:
            before_events(source.clone(entry))
        events.reset_fluxes(ctx.sim, ctx.p)
        holder["reset_return"] = source.material_values(ctx.sim)
        event = events.fire(ctx, float(parent.clock.source_times_s[index]))
        holder["events"] = event
        if after_events is not None:
            after_events(ions.freeze(event))
        stores = events.event_snapshot(ctx.sim)
        runtime, definition = runtime_material(binding, stores)
        lowered = material.state(runtime, source.material_values(ctx.sim), step_index=index)
        holder.update(runtime_binding=runtime, lowered_parent=lowered, definition=definition)
        packet = dict(
            row["material"],
            runtime_temperature_K=float(stores["T"]),
            boundary_mol_m3=source.clone(stores["c_env_bound"]),
            junction_block=_broadcast(stores["gj_block"], m),
            channel_multiplier=_broadcast(stores["rho_channel"], m),
            electric_x_source=parent.field.environment.values.electric_x_source,
            electric_y_source=parent.field.environment.values.electric_y_source,
        )
        forcing = material.drive(runtime, packet)
        material_input = dict(
            mode="material",
            definition=definition,
            initial=ions.data(lowered.values._asdict()),
            steps=[source.clone(packet)],
            calcium=ions.data(binding.calcium),
            rate_cache_before=ions.data(rate),
            clock=ions.data(parent.clock),
            catalog=ions.data(binding.catalog),
            network_cache=source.cache(ctx),
            event_stores=source.clone(stores),
            noise=ions.data(binding.noise),
            noise_stream_before=random_source.native_stream_manifest(stream),
        )
        material_input["prospective_noise_draw"] = None
        material_input["prospective_noise_uniforms"] = None
        material_input["prospective_stream_after"] = random_source.native_stream_manifest(stream)
        if binding.noise["enabled"] == 1 and "P" in ctx.ion_ids:
            preview, next_preview = random_source.sample_native(
                stream, binding.noise_binding, site="protein_flux", tick=index
            )
            material_input["prospective_noise_uniforms"] = preview.values.copy()
            material_input["prospective_noise_draw"] = random_source.draw_manifest(
                preview, binding.noise_binding
            )
            material_input["prospective_stream_after"] = random_source.native_stream_manifest(
                next_preview
            )
        material_input["prospective_draw_is_uncommitted"] = True
        holder["material_inputs"] = material_input
        if before_material is not None:
            before_material(source.clone(material_input))

        def on_calcium(arrays):
            result, phase = calcium_component.calcium(
                binding, arrays, forcing, rate, parent.clock, before_calcium
            )
            holder.update(rate=result, calcium=phase)
            if after_calcium is not None:
                after_calcium(result, phase)

        def on_network(arrays):
            current = _context(binding, arrays, runtime, forcing)
            holder["ctx"] = current
            source.restore(current, parent.network.network_cache)
            if any((value != index for value in current.channel_calls.values())):
                raise ValueError("Require actual channel cache counters at source clock epoch")
            events.install_owner(current, ions.data(binding.event_owner), stores)
            _install_noise_cache(current, nc)
            calcium_component.native_policy(current, binding)
            if holder["rate"].present:
                current.sim.rate_CaATP = holder["rate"].value.copy()
            source.run_dispatch(
                current,
                definition,
                row["publication"],
                float(parent.clock.source_times_s[index]),
                before_network,
                before_channels,
            )

        def on_noise(arrays):
            current = holder["ctx"]

            def noise_input(value):
                value.update(
                    mode="noise",
                    definition=source.clone(definition),
                    noise=ions.data(binding.noise),
                    dt_s=forcing.dt_s,
                    source_time_s=float(parent.clock.source_times_s[index]),
                    noise_cache_before=ions.data(nc),
                )
                holder["before_noise"] = source.clone(value)
                if before_noise is not None:
                    before_noise(value)

            next_stream, phase = events.noise(
                current, stream, binding.noise_binding, index, ions.data(binding.noise), noise_input
            )
            expected = material_input["prospective_noise_draw"]
            if expected is None:
                if phase["draws"]:
                    raise ValueError("Disabled noise branch consumed an unexpected draw")
            elif len(phase["draws"]) != 1 or phase["draws"][0] != expected:
                raise ValueError(
                    "Actual post-GRN draw differs from cloned incoming-stream condition"
                )
            holder.update(noise_stream=next_stream, noise=phase)
            if after_noise is not None:
                after_noise(ions.freeze(phase))
            if on_mechanics is not None:
                on_mechanics(current)

        def failed(local):
            holder["material_partial"] = dict(
                frames=ions.data(tuple(local.get("frames", ()))),
                environment_records=ions.data(tuple(local.get("environment_records", ()))),
                trial=local.get("trial"),
                diagnostics=local.get("diagnostics"),
                failure=local.get("failure"),
                available_arrays={
                    name: value.copy()
                    for name, value in local.items()
                    if isinstance(value, np.ndarray)
                },
            )

        trial = event_material.step_after_events(
            runtime,
            lowered,
            forcing,
            on_network=on_network,
            on_failure=failed,
            on_calcium=on_calcium,
            on_noise=on_noise,
        )
        current = holder["ctx"]
        source.validate_cached_channels(current, source.cache(current))
        candidate = network._state(
            binding, trial.candidate, source.cache(current), current.trace["controls_after"]
        )
        holder.update(
            material_parent=candidate,
            trial=trial,
            network=current.trace,
            post_material_cache=source.cache(current),
        )
        if after_material is not None:
            after_material(candidate, trial, current.trace, holder["calcium"], holder["noise"])
        prepared, fields = full.reconstruct(
            binding, candidate, dt, source.clone(current.sim.bound_V), "field", before_field
        )
        clock = Clock(parent.clock.source_times_s, index + 1, (index + 1) * dt)
        result = joined_state(
            binding,
            prepared,
            fields,
            holder["rate"],
            clock,
            events.event_snapshot(current.sim),
            holder["noise_stream"],
            _noise_cache(current),
        )
        return (
            result,
            trial,
            ions.freeze(current.trace),
            holder["calcium"],
            holder["noise"],
            ions.freeze(
                dict(
                    before_events=entry,
                    events=event,
                    reset_return=holder["reset_return"],
                    runtime_material_declaration=definition,
                    runtime_material_binding=runtime,
                    lowered_parent=lowered,
                    material_parent=candidate,
                    post_material_cache=holder["post_material_cache"],
                    initial_field=parent.field,
                    fields=fields,
                    clock_before=parent.clock,
                    clock_after=clock,
                )
            ),
        )
    except Exception as error:
        current = holder.get("ctx", ctx)
        raise EventJoinRejected(
            error,
            dict(
                stage="event_material_network_noise_field",
                parent=parent,
                available={key: value for key, value in holder.items() if key != "ctx"},
                source_partial=getattr(error, "partial", None),
                available_event_stores={
                    name: source.clone(getattr(current.sim, name))
                    for name in events.EVENT_STORES
                    if hasattr(current.sim, name)
                },
                missing_event_stores=[
                    name for name in events.EVENT_STORES if not hasattr(current.sim, name)
                ],
                **catalog_component.failure_snapshot(current, parent.network.network_cache),
            ),
        ) from error


LAW_ID = "betse_normal_ecm_event_steady_mechanics_v1_5_0@1"
INPUT_KIND = "cells.normal_ecm_event_mechanics_inputs@1"


@dataclass(frozen=True)
class Binding:
    events: object
    mechanics: object
    inputs: object
    identity: str


@dataclass(frozen=True)
class State:
    binding_identity: str
    events: object
    mechanics: object
    sample_state: object
    identity: str


class CompositionRejected(RuntimeError):
    def __init__(self, reason, partial):
        super().__init__(str(reason))
        self.partial = ions.freeze(partial)


def state(binding, events_parent, mechanical, sample_state):
    return State(
        binding.identity,
        events_parent,
        mechanical,
        ions.freeze(sample_state),
        ions.digest((binding.identity, events_parent, mechanical, sample_state)),
    )


def bind(inputs):
    raw = ions.data(inputs)
    if (
        set(raw)
        != {
            "kind",
            "case_id",
            "event_inputs",
            "mechanics_definition",
            "mechanics_initial",
            "sample_policy",
        }
        or raw["kind"] != INPUT_KIND
    ):
        raise ValueError("Require a complete separately declared event/mechanics supplied state")
    if raw["sample_policy"] != "calendar_eligibility_only_explicit_display_refusal":
        raise ValueError("Field domain<=16 and quartic display requires>=25; sampling stays held")
    eb = event.bind(raw["event_inputs"])
    policy = raw["mechanics_definition"]["policy"]
    if policy["display_regime"] != "none":
        raise ValueError("Field domain<=16 and quartic display requires>=25; no display widening")
    mb = mechanics.bind(raw["mechanics_definition"])
    if not policy["is_ecm"] or policy["molecules_enabled"] or not policy["grn_enabled"]:
        raise ValueError("Require actual ECM GRN owner and no separate molecule handler")
    fb = eb
    definition = mb.definition
    cg = fb.material_binding.geometry_binding.definition["current_definition"]["geometry"]
    geometry = fb.material_binding.geometry_binding.definition["geometry"]
    mg = definition["geometry"]
    layout = mg["layout"]
    n, m = (len(cg["cell_ids"]), len(cg["membrane_ids"]))
    if not 1 <= n <= 16 or not 1 <= m <= 128:
        raise ValueError("Keep the frozen native ECM domain without widening")
    if mg["cell_ids"] != cg["cell_ids"] or layout["membrane_ids"] != cg["membrane_ids"]:
        raise ValueError("Mechanics must use the actual shared cell/membrane owner order")
    expected = dict(
        centers_m=geometry["cell_centres_m"],
        cell_volume_m3=geometry["cell_volume_m3"],
        membrane_area_m2=cg["membrane_area_m2"],
        cell_area_m2=cg["cell_area_m2"],
    )
    for key, value in expected.items():
        np.testing.assert_array_equal(np.asarray(layout[key]), np.asarray(value), err_msg=key)
    owner = np.asarray(cg["owner"], dtype=int)
    sm = np.eye(n)[owner].T
    np.testing.assert_array_equal(layout["sum_membranes"], sm)
    np.testing.assert_array_equal(np.asarray(layout["neighbors"])[:, 0], owner)
    g = fb.material_binding.geometry_binding.geometry
    if mg["environment_ids"] != ["native-grid/" + str(k) for k in range(len(g.grid_points_m))]:
        raise ValueError("Declare the native C-order environment owner axis")
    np.testing.assert_array_equal(mg["cell_to_environment"], g.cell_to_grid)
    np.testing.assert_array_equal(mg["membrane_to_environment"], g.membrane_to_grid)
    p = definition["parameters"]
    if (
        p["gas_constant_J_mol_K"] != fb.material_binding.kernel.R_J_mol_K
        or p["membrane_thickness_m"] != fb.material_binding.kernel.membrane_thickness_m
    ):
        raise ValueError("Use the actual shared pressure constants and membrane thickness")

    for packet in eb.inputs["steps"]:
        if packet["material"]["dt_s"] != p["dt_s"] or p["dt_s"] != eb.calendar.dt_s:
            raise ValueError("Require the same native phase dt for events, material and mechanics")
        for drive, cached in (("velocity_x_m_s", "u_env_x"), ("velocity_y_m_s", "u_env_y")):
            values = np.asarray(packet["material"][drive])
            if np.any(values != 0) or not np.array_equal(
                values, np.asarray(raw["mechanics_initial"][cached])
            ):
                raise ValueError("Disabled fluid needs shared held-zero velocity stores")
    mechanics.state(mb, raw["mechanics_initial"])
    return Binding(eb, mb, ions.freeze(raw), ions.digest((LAW_ID, eb.identity, mb.identity, raw)))


def verify(binding, parent):
    verify_binding(binding)
    if (
        type(parent) is not State
        or parent.binding_identity != binding.identity
        or parent.identity
        != ions.digest((binding.identity, parent.events, parent.mechanics, parent.sample_state))
    ):
        raise ValueError("Require the complete unchanged event/mechanics parent")
    mechanics._verify(binding.mechanics, parent.mechanics)
    if not (
        parent.events.clock.call_index
        == parent.events.network.material.step_index
        == parent.mechanics.step_index
    ):
        raise ValueError("Event/material/mechanics counters must name the same source call")
    index = parent.events.clock.call_index
    expected = initial_sample_state() if index == 0 else sample_state(binding, index - 1)
    if not source.equal_tree(parent.sample_state, expected) or parent.mechanics.sampled_steps:
        raise ValueError("Require exact native eligibility and held, uncompleted display state")


def verify_binding(binding):
    if type(binding) is not Binding or binding.identity != ions.digest(
        (LAW_ID, binding.events.identity, binding.mechanics.identity, binding.inputs)
    ):
        raise ValueError("Changed complete event/mechanics binding")
    event.validate_composition(binding.events)


def initial_sample_state():
    return dict(
        source_call=None,
        source_time_s=None,
        native_calendar_eligible=False,
        display_attempted=False,
        display_completed=False,
        display_status="before_first_call",
        maximum_field_cells=16,
        minimum_quartic_display_cells=25,
    )


def sample_state(binding, index):
    eligible = bool(calendars.window(binding.events.calendar).sampled[index])
    return dict(
        source_call=index,
        source_time_s=float(calendars.window(binding.events.calendar).event_label_s[index]),
        native_calendar_eligible=eligible,
        display_attempted=False,
        display_completed=False,
        display_status="held_separate_display_domain_required" if eligible else "not_eligible",
        maximum_field_cells=16,
        minimum_quartic_display_cells=25,
    )


def initialize(binding, *, after_cold=None, before_field=None):
    verify_binding(binding)
    mechanical = mechanics.state(binding.mechanics, ions.data(binding.inputs["mechanics_initial"]))
    try:
        initialized = event.initialize(
            binding.events, after_cold=after_cold, before_field=before_field
        )
        return state(
            binding,
            initialized,
            mechanical,
            initial_sample_state(),
        )
    except Exception as error:
        raise CompositionRejected(
            error,
            dict(
                stage="cold_or_bootstrap",
                mechanics_parent=mechanical,
                inputs=binding.inputs,
                event_partial=getattr(error, "partial", None),
            ),
        ) from error


def mechanics_input(binding, parent, ctx, index):
    geometry = binding.mechanics.definition["geometry"]
    previous = parent.events.field
    molecules = ctx.sim.grn.core.molecules
    names = list(molecules)
    return dict(
        receipt=dict(
            stage=mechanics.FIELD_STAGE,
            geometry_epoch=binding.mechanics.definition["provenance"]["geometry_epoch"],
            cell_ids=geometry["cell_ids"],
            environment_ids=geometry["environment_ids"],
            source_step=index,
            deferred_material_voltage_commit_done=False,
        ),
        clock_s=float(parent.events.clock.source_times_s[index]),
        dt_s=binding.events.calendar.dt_s,
        temperature_K=float(ctx.sim.T),
        pressure_Pa=np.array(ctx.sim.P_cells, copy=True),
        electric_field_V_m=np.asarray(previous.voltage.values.cell_field_xy_V_m).T,
        current_density_A_m2=np.asarray(previous.current.values.cell_current_xy_A_m2).T,
        charge_density_C_m3=previous.current.values.charge_density_C_m3,
        conductivity_S_m=binding.events.material_binding.geometry_binding.cache.sigma_S_m,
        primary_ids=list(binding.events.material_binding.geometry_binding.current_binding.ion_ids),
        primary_cell_mM=np.array(ctx.sim.cc_cells, copy=True),
        primary_env_mM=np.array(ctx.sim.cc_env, copy=True),
        molecule_ids=[],
        molecule_cell_mM=[],
        molecule_env_mM=[],
        grn_ids=names,
        grn_cell_mM=[np.array(molecules[name].c_cells, copy=True) for name in names],
        grn_env_mM=[np.array(molecules[name].c_env, copy=True) for name in names],
        sample=False,
    )


def advance(binding, parent, *, before_mechanics=None, after_mechanics=None, **callbacks):
    holder = {}
    try:
        verify(binding, parent)
        index = parent.events.clock.call_index

        def on_mechanics(ctx):
            incoming = mechanics_input(binding, parent, ctx, index)
            holder["mechanics_input"] = ions.freeze(incoming)
            holder["actual_event_pressure"] = ions.freeze(event.events.event_snapshot(ctx.sim))
            if before_mechanics is not None:
                before_mechanics(
                    dict(
                        mode="mechanics",
                        definition=binding.mechanics.definition,
                        initial=ions.data(parent.mechanics.cache),
                        steps=[incoming],
                    )
                )
            try:
                trial = mechanics.step(binding.mechanics, parent.mechanics, incoming)
            except Exception as error:
                holder["mechanics_failure"] = getattr(error, "trial", None)
                raise
            holder["mechanics_trial"] = trial
            if after_mechanics is not None:
                after_mechanics(trial)

        returned = _advance_events(
            binding.events, parent.events, on_mechanics=on_mechanics, **callbacks
        )
        holder["complete_event_return"] = returned
        candidate = state(
            binding, returned[0], holder["mechanics_trial"].candidate, sample_state(binding, index)
        )
        verify(binding, candidate)
        return candidate, dict(event_return=returned, **holder, sample_state=candidate.sample_state)
    except Exception as error:
        raise CompositionRejected(
            error,
            dict(
                stage="event_noise_mechanics_material_field",
                parent=parent,
                available=holder,
                event_partial=getattr(error, "partial", None),
                reason=str(error),
            ),
        ) from error


def sample(binding, parent):
    """Preserve the reached post-field state before explicit display refusal."""
    verify(binding, parent)
    stage = (
        "sample_display_domain"
        if parent.sample_state["native_calendar_eligible"]
        else "sample_clock"
    )
    raise CompositionRejected(
        ValueError("Field domain<=16 and quartic display requires>=25; display refused"),
        dict(
            stage=stage,
            parent=parent,
            sample_state=parent.sample_state,
            available_field=parent.events.field,
            available_mechanics=parent.mechanics,
            display_completed=False,
            physical_geometry_rebuilt=False,
        ),
    )
