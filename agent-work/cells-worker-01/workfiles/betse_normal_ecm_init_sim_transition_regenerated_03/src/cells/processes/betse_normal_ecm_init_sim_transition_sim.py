"""Private existing SIM composition with native retained-rate entry and NaK.

No shared body is patched. The phase handoff supplies actual incoming rate
caches explicitly; no fresh cold initialization is performed here.
"""

from types import SimpleNamespace

from cells.processes import betse_normal_ecm_event_mechanics as base
from cells.processes import betse_normal_ecm_init_sim_transition_pump as pump

Binding=base.Binding
State=base.State
bind=base.bind
verify_binding=base.verify_binding
verify=base.verify
event=base.event
full=base.full
source=base.source
sample=base.sample
Clock = base.Clock
EventFieldState = base.EventFieldState
EventJoinRejected = base.EventJoinRejected
NoiseCache = base.NoiseCache
RateCache = base.RateCache
_broadcast = base._broadcast
_context = base._context
_install_noise_cache = base._install_noise_cache
_noise_cache = base._noise_cache
calcium_component = base.calcium_component
calendars = base.calendars
catalog_component = base.catalog_component
event_material = base.event_material
events = base.events
ions = base.ions
joined_state = base.joined_state
material = base.material
network = base.network
np = base.np
random_source = base.random_source
record = base.record
runtime_material = base.runtime_material
validate_composition = base.validate_composition
validate_stores = base.validate_stores
CompositionRejected = base.CompositionRejected
mechanics = base.mechanics
mechanics_input = base.mechanics_input
sample_state = base.sample_state
state = base.state


def _advance_events(binding, parent, *, before_events=None, after_events=None, before_material=None, before_calcium=None, before_channels=None, before_network=None, before_noise=None, before_field=None, after_calcium=None, after_noise=None, after_material=None, on_mechanics=None, entry_ca_rate_present, nak_rate_before, alpha_NaK, before_nak=None):
    validate_composition(binding)
    if type(parent) is not EventFieldState or parent.binding_identity != binding.identity or parent.identity != ions.digest(record(parent)):
        raise ValueError('Require the unchanged owned event/channel/material parent')
    index = parent.network.material.step_index
    dt = binding.calendar.dt_s
    if index >= binding.call_limit:
        raise ValueError('Declared bounded normal-call prefix is complete')
    if type(parent.clock) is not Clock or not isinstance(parent.clock.source_times_s, np.ndarray) or parent.clock.source_times_s.dtype != np.float64 or (parent.clock.source_times_s.shape != (3,)) or parent.clock.source_times_s.flags.writeable or (parent.clock.call_index != index) or (parent.clock.material_dt_sum_s != index * dt) or (not np.array_equal(parent.clock.source_times_s, calendars.window(binding.calendar).event_label_s)):
        raise ValueError('Require original source labels and separate accumulated material dt')
    if type(parent.field) is not full.FieldStage or parent.field.binding_identity != binding.identity or parent.field.identity != ions.digest(full.field_record(parent.field)):
        raise ValueError('Require the actual preceding full field')
    rate = parent.rate_cache
    m = len(binding.material_binding.geometry_binding.current_binding.membrane_ids)
    if type(rate) is not RateCache or rate.present is not (entry_ca_rate_present or (binding.calcium['alpha_Ca'] > 0 and index > 0)) or (rate.value is not None if not rate.present else not isinstance(rate.value, np.ndarray) or rate.value.shape != (m,) or rate.value.dtype != np.float64 or rate.value.flags.writeable or (not np.isfinite(rate.value).all())):
        raise ValueError('Require actual CaATP rate absence or complete immutable source cache')
    stores = validate_stores(binding, ions.data(parent.event_stores))
    for key in ('gj_block', 'NaKATP_block'):
        if not source.equal_tree(parent.network.controls[key], stores[key]):
            raise ValueError('Event and GRN control owners differ at the actual parent epoch')
    stream = parent.noise_stream
    random_source.native_stream_manifest(stream)
    nc = parent.noise_cache
    if type(nc) is not NoiseCache or type(nc.present) is not bool or (nc.value is not None if not nc.present else not isinstance(nc.value, np.ndarray) or nc.value.dtype != np.float64 or nc.value.shape != (m,) or nc.value.flags.writeable or (not np.isfinite(nc.value).all())):
        raise ValueError('Require complete immutable actual protein-noise cache or absence')
    row = ions.data(binding.inputs['steps'][index])
    holder = dict(parent=parent)
    ctx = _context(binding, material.Values(*(np.array(v, copy=True) for v in parent.network.material.values)))
    try:
        source.restore(ctx, parent.network.network_cache)
        events.install_owner(ctx, ions.data(binding.event_owner), stores)
        _install_noise_cache(ctx, nc)
        ctx.phase.kind = 'SIM'
        entry = dict(mode='events', owner=ions.data(binding.event_owner), before=events.event_snapshot(ctx.sim), material_before=source.material_values(ctx.sim), clock=ions.data(parent.clock), source_time_s=float(parent.clock.source_times_s[index]), configured_temperature_K=ctx.p.T, dt_s=dt, ion_ids=list(ctx.ion_ids), valence=source.clone(ctx.sim.zs))
        holder['before_events'] = entry
        if before_events is not None:
            before_events(source.clone(entry))
        events.reset_fluxes(ctx.sim, ctx.p)
        holder['reset_return'] = source.material_values(ctx.sim)
        event = events.fire(ctx, float(parent.clock.source_times_s[index]))
        holder['events'] = event
        if after_events is not None:
            after_events(ions.freeze(event))
        stores = events.event_snapshot(ctx.sim)
        runtime, definition = runtime_material(binding, stores)
        lowered = material.state(runtime, source.material_values(ctx.sim), step_index=index)
        holder.update(runtime_binding=runtime, lowered_parent=lowered, definition=definition)
        pump_binding = SimpleNamespace(material_binding=runtime, inputs=dict(binding.inputs, definition=definition), inputs_raw={'flags': {'alpha_NaK': alpha_NaK}})
        pump_stores = dict(stores, rho_pump=1)
        nak_phase, nak_flux, nak_proxy = pump.produce(pump_binding, lowered, pump_stores, nak_rate_before, before_nak)
        holder['nak'] = nak_phase
        holder['nak_rate_after'] = calcium_component.RateCache(True, nak_proxy)
        if not pump.finite(nak_phase):
            raise ValueError('Nonfinite complete transitioned SIM NaK output')
        packet = dict(row['material'], runtime_temperature_K=float(stores['T']), boundary_mol_m3=source.clone(stores['c_env_bound']), junction_block=_broadcast(stores['gj_block'], m), channel_multiplier=_broadcast(stores['rho_channel'], m), electric_x_source=parent.field.environment.values.electric_x_source, electric_y_source=parent.field.environment.values.electric_y_source, supplied_pump_membrane_flux_mol_m2_s=nak_flux)
        forcing = material.drive(runtime, packet)
        material_input = dict(mode='material', definition=definition, initial=ions.data(lowered.values._asdict()), steps=[source.clone(packet)], calcium=ions.data(binding.calcium), rate_cache_before=ions.data(rate), clock=ions.data(parent.clock), catalog=ions.data(binding.catalog), network_cache=source.cache(ctx), event_stores=source.clone(stores), noise=ions.data(binding.noise), noise_stream_before=random_source.native_stream_manifest(stream), nak_before=nak_phase['before'])
        material_input['prospective_noise_draw'] = None
        material_input['prospective_noise_uniforms'] = None
        material_input['prospective_stream_after'] = random_source.native_stream_manifest(stream)
        if binding.noise['enabled'] == 1 and 'P' in ctx.ion_ids:
            preview, next_preview = random_source.sample_native(stream, binding.noise_binding, site='protein_flux', tick=index)
            material_input['prospective_noise_uniforms'] = preview.values.copy()
            material_input['prospective_noise_draw'] = random_source.draw_manifest(preview, binding.noise_binding)
            material_input['prospective_stream_after'] = random_source.native_stream_manifest(next_preview)
        material_input['prospective_draw_is_uncommitted'] = True
        holder['material_inputs'] = material_input
        if before_material is not None:
            before_material(source.clone(material_input))

        def on_calcium(arrays):
            result, phase = calcium_component.calcium(binding, arrays, forcing, rate, parent.clock, before_calcium)
            holder.update(rate=result, calcium=phase)
            if after_calcium is not None:
                after_calcium(result, phase)

        def on_network(arrays):
            current = _context(binding, arrays, runtime, forcing)
            holder['ctx'] = current
            source.restore(current, parent.network.network_cache)
            if any((value != index for value in current.channel_calls.values())):
                raise ValueError('Require actual channel cache counters at source clock epoch')
            events.install_owner(current, ions.data(binding.event_owner), stores)
            _install_noise_cache(current, nc)
            calcium_component.native_policy(current, binding)
            if holder['rate'].present:
                current.sim.rate_CaATP = holder['rate'].value.copy()
            current.sim.rate_NaKATP = nak_proxy.copy()
            source.run_dispatch(current, definition, row['publication'], float(parent.clock.source_times_s[index]), before_network, before_channels)

        def on_noise(arrays):
            current = holder['ctx']

            def noise_input(value):
                value.update(mode='noise', definition=source.clone(definition), noise=ions.data(binding.noise), dt_s=forcing.dt_s, source_time_s=float(parent.clock.source_times_s[index]), noise_cache_before=ions.data(nc))
                holder['before_noise'] = source.clone(value)
                if before_noise is not None:
                    before_noise(value)
            next_stream, phase = events.noise(current, stream, binding.noise_binding, index, ions.data(binding.noise), noise_input)
            expected = material_input['prospective_noise_draw']
            if expected is None:
                if phase['draws']:
                    raise ValueError('Disabled noise branch consumed an unexpected draw')
            elif len(phase['draws']) != 1 or phase['draws'][0] != expected:
                raise ValueError('Actual post-GRN draw differs from cloned incoming-stream condition')
            holder.update(noise_stream=next_stream, noise=phase)
            if after_noise is not None:
                after_noise(ions.freeze(phase))
            if on_mechanics is not None:
                on_mechanics(current)

        def failed(local):
            holder['material_partial'] = dict(frames=ions.data(tuple(local.get('frames', ()))), environment_records=ions.data(tuple(local.get('environment_records', ()))), trial=local.get('trial'), diagnostics=local.get('diagnostics'), failure=local.get('failure'), available_arrays={name: value.copy() for name, value in local.items() if isinstance(value, np.ndarray)})
        trial = event_material.step_after_events(runtime, lowered, forcing, on_network=on_network, on_failure=failed, on_calcium=on_calcium, on_noise=on_noise)
        current = holder['ctx']
        source.validate_cached_channels(current, source.cache(current))
        candidate = network._state(binding, trial.candidate, source.cache(current), current.trace['controls_after'])
        holder.update(material_parent=candidate, trial=trial, network=current.trace, post_material_cache=source.cache(current))
        if after_material is not None:
            after_material(candidate, trial, current.trace, holder['calcium'], holder['noise'])
        prepared, fields = full.reconstruct(binding, candidate, dt, source.clone(current.sim.bound_V), 'field', before_field)
        clock = Clock(parent.clock.source_times_s, index + 1, (index + 1) * dt)
        result = joined_state(binding, prepared, fields, holder['rate'], clock, events.event_snapshot(current.sim), holder['noise_stream'], _noise_cache(current))
        return (result, trial, ions.freeze(current.trace), holder['calcium'], holder['noise'], ions.freeze(dict(before_events=entry, events=event, reset_return=holder['reset_return'], runtime_material_declaration=definition, runtime_material_binding=runtime, lowered_parent=lowered, material_parent=candidate, post_material_cache=holder['post_material_cache'], initial_field=parent.field, fields=fields, clock_before=parent.clock, clock_after=clock, nak=nak_phase, nak_rate_after=holder['nak_rate_after'])))
    except Exception as error:
        current = holder.get('ctx', ctx)
        raise EventJoinRejected(error, dict(stage='event_material_network_noise_field', parent=parent, available={key: value for key, value in holder.items() if key != 'ctx'}, source_partial=getattr(error, 'partial', None), available_event_stores={name: source.clone(getattr(current.sim, name)) for name in events.EVENT_STORES if hasattr(current.sim, name)}, missing_event_stores=[name for name in events.EVENT_STORES if not hasattr(current.sim, name)], **catalog_component.failure_snapshot(current, parent.network.network_cache))) from error

def advance(binding, parent, *, before_mechanics=None, after_mechanics=None, **callbacks):
    holder = {}
    try:
        verify(binding, parent)
        index = parent.events.clock.call_index

        def on_mechanics(ctx):
            incoming = mechanics_input(binding, parent, ctx, index)
            holder['mechanics_input'] = ions.freeze(incoming)
            holder['actual_event_pressure'] = ions.freeze(event.events.event_snapshot(ctx.sim))
            if before_mechanics is not None:
                before_mechanics(dict(mode='mechanics', definition=binding.mechanics.definition, initial=ions.data(parent.mechanics.cache), steps=[incoming]))
            try:
                trial = mechanics.step(binding.mechanics, parent.mechanics, incoming)
            except Exception as error:
                holder['mechanics_failure'] = getattr(error, 'trial', None)
                raise
            holder['mechanics_trial'] = trial
            if after_mechanics is not None:
                after_mechanics(trial)
        returned = _advance_events(binding.events, parent.events, on_mechanics=on_mechanics, **callbacks)
        holder['complete_event_return'] = returned
        candidate = state(binding, returned[0], holder['mechanics_trial'].candidate, sample_state(binding, index))
        verify(binding, candidate)
        return (candidate, dict(event_return=returned, **holder, sample_state=candidate.sample_state))
    except Exception as error:
        raise CompositionRejected(error, dict(stage='event_noise_mechanics_material_field', parent=parent, available=holder, event_partial=getattr(error, 'partial', None), reason=str(error))) from error
