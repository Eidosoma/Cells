# ruff: noqa: E501
"""Held ordinary FULL/ECM INIT on explicitly supplied pre-setup owners.

Fresh setup, cold GRN and INIT-active gates, original clock, NaK, primary movers,
CaATP, network, steady/osmotic mechanics, deferred commit and field feedback are
separate from native seed/load, physical initializer, storage and display work.
The existing arithmetic and three-call material cap are unchanged.
"""
from cells.processes import betse_normal_ecm_molecule_lifecycle_owners as owners
from cells.processes import betse_normal_ecm_molecule_transport as transport
from dataclasses import dataclass, replace
from types import SimpleNamespace
import numpy as np
from cells.core import physiology_native_calendar as calendars
from cells.processes import betse_ecm_grn_join as network
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_mechanics_join as mechanics
from cells.processes import betse_normal_ecm_calcium_join as calcium
from cells.processes import betse_normal_ecm_catalog_join_source as common
from cells.processes import betse_normal_ecm_field_join as full
from cells.processes import betse_normal_ecm_init_phase_material as material_init
from cells.processes import betse_normal_ecm_molecule_lifecycle_mechanics as mechanical
from cells.processes import betse_normal_ecm_init_phase_pump as pump
from cells.processes import betse_normal_ecm_init_phase_setup as setup
from cells.processes import betse_normal_ecm_molecule_lifecycle_source as source
from cells.processes import betse_normal_ecm_run_lifecycle as lifecycle
from cells.processes import betse_normal_ion_join as ions
LAW_ID = 'betse_supplied_ECM_phase_general_transport_GRN_v1_5_0@1'
INPUT_KIND = 'cells.normal_ecm_molecule_owner_phase_inputs@1'
RateCache, Clock = (calcium.RateCache, calcium.Clock)
FIXED_FLAGS = dict(phase='INIT', solver='FULL', is_ecm=True, _run_sim=False, grn_enabled=True, molecules_enabled=False, Ca_dyn=False, fluid_flow=False, td_deform=False, sim_eosmosis=False, physical_initialization=False, cut_requested=False)

@dataclass(frozen=True)
class Declaration:
    inputs: object
    base: object
    calendar: object
    mechanics: object
    identity: str

@dataclass(frozen=True)
class Binding:
    declaration: Declaration
    material_binding: object
    voltage_binding: object
    inputs: object
    inputs_raw: object
    calcium: object
    catalog: object
    call_limit: int
    calendar: object
    mechanics: object
    setup_receipt: object
    identity: str

@dataclass(frozen=True)
class State:
    binding_identity: str
    network: object
    field: object
    rate_cache: RateCache
    nak_rate: RateCache
    mechanics: object
    stores: object
    clock: Clock
    history: tuple
    observations: tuple
    status: str
    identity: str

    @property
    def cursor(self):
        return self.clock.call_index

class InitRejected(RuntimeError):

    def __init__(self, error, partial):
        super().__init__(str(error))
        self.partial = ions.freeze(partial)

def base_bind(raw, field):
    return calcium.bind(dict(kind='cells.normal_ecm_calcium_join_inputs@1', case_id=raw['case_id'], case_role=raw['case_role'], field=field, calcium=raw['calcium']))

def declaration_record(value):
    return (LAW_ID, value.inputs, value.base.identity, value.calendar, value.mechanics.identity)

def bind(inputs):
    """Validate a pre-setup declaration; do not consume a random draw."""
    raw = ions.data(inputs)
    validate_owner_scope(raw)
    if set(raw) != {'kind', 'case_id', 'case_role', 'field', 'calcium', 'catalog', 'flags', 'time_profile', 'setup', 'mechanics_definition', 'mechanics_initial', 'sample_policy', 'stop_after_calls', 'owners'} or raw['kind'] != INPUT_KIND:
        raise ValueError('Require the separately owned ordinary INIT declaration')
    if set(raw['flags']) != set(FIXED_FLAGS) | {'alpha_NaK'}:
        raise ValueError('Require every ordinary INIT scope flag')
    for key, expected in expected_flags(raw).items():
        if type(raw['flags'][key]) is not type(expected) or raw['flags'][key] != expected:
            raise ValueError('Unsupported INIT scope flag: ' + key)
    if setup.real(raw['flags']['alpha_NaK'], 'alpha_NaK') < 0:
        raise ValueError('This declared maintained NaK producer admits nonnegative alpha')
    if raw['time_profile']['phase'] not in ('INIT', 'SIM'):
        raise ValueError('INIT cannot reuse a SIM phase profile')
    profile = lifecycle.profile(raw['time_profile'])[raw['time_profile']['phase'].lower()]
    calendar = calendars.bind(phase=raw['time_profile']['phase'], step_count=profile['step_count'], dt_s=profile['dt_s'], sample_stride=profile['sample_stride'], requested_duration_s=raw['time_profile'][raw['time_profile']['phase'].lower() + '_total_s'], provenance=raw['time_profile']['provenance'])
    limit = raw['stop_after_calls']
    if type(limit) is not int or not 0 <= limit <= min(3, calendar.step_count):
        raise ValueError('Require an original-calendar prefix within the unchanged three-call cap')
    if raw['sample_policy'] != 'calendar_eligibility_only_explicit_display_refusal':
        raise ValueError('Native display/storage remains held on the existing bounded field domain')
    base = base_bind(raw, raw['field'])
    cb = base.material_binding.geometry_binding.current_binding
    if not {'Na', 'K', 'Ca'} <= set(cb.ion_ids):
        raise ValueError('Require actual native Na/K/Ca primary roles')
    common.validate_catalog(raw['catalog'], list(cb.ion_ids), len(cb.membrane_ids))
    setup.validate(raw['setup'], base)
    if ions.data(raw['setup']['maps']['tissue_target_inds']) != ions.data(raw['catalog']['tissue_profiles']):
        raise ValueError('Cold catalog and setup finalizer must share the supplied tissue maps')
    mb = mechanical.bind(raw, SimpleNamespace(material_binding=base.material_binding, inputs=base.inputs, calendar=calendar))
    for row in base.inputs['steps']:
        packet = row['material']
        if packet['dt_s'] != calendar.dt_s or row['scheduled_controls'] is not None:
            raise ValueError('INIT owns phase dt and has no scheduled event overrides')
        if any((np.any(np.asarray(packet[key]) != 0) for key in ('supplied_pump_membrane_flux_mol_m2_s', 'supplied_late_membrane_flux_mol_m2_s'))):
            raise ValueError('Require actual NaK/CaATP/GRN producers; arbitrary extra flux is closed')
        if packet['runtime_temperature_K'] != base.material_binding.geometry_binding.definition['parameters']['configured_temperature_K']:
            raise ValueError('INIT starts from the configured core temperature')
        if not common.equal_tree(row['boundary_V'], base.inputs['bootstrap']['boundary_V']):
            raise ValueError('INIT has no fired voltage-boundary event')
        if any((value != 0 for value in row['boundary_V'].values())):
            raise ValueError('Fresh ordinary INIT retains the init_core zero voltage boundaries')
        if any((not np.array_equal(packet[key], np.ones(len(cb.membrane_ids))) for key in ('junction_block', 'channel_multiplier'))):
            raise ValueError('INIT setup controls cannot have competing per-call multipliers')
        if not np.array_equal(packet['boundary_mol_m3'], base.inputs['network']['initial_ion_boundary']):
            raise ValueError('Require the supplied setup ion-boundary owner')
    if base.inputs['bootstrap']['dt_s'] != calendar.dt_s:
        raise ValueError('Cold bootstrap and INIT material must share the source dt')
    result = Declaration(ions.freeze(raw), base, calendar, mb, '')
    return replace(result, identity=ions.digest(declaration_record(result)))

def binding_record(value):
    return (LAW_ID, value.declaration.identity, value.material_binding.identity, value.voltage_binding.identity, value.inputs, value.inputs_raw, value.calcium, value.catalog, value.call_limit, value.calendar, value.mechanics.identity, value.setup_receipt)

def verify_binding(binding):
    if type(binding) is not Binding or binding.identity != ions.digest(binding_record(binding)):
        raise ValueError('Require the complete unchanged post-setup INIT binding')
    if binding.declaration.identity != ions.digest(declaration_record(binding.declaration)):
        raise ValueError('Changed pre-setup declaration')
    calendars.validate(binding.calendar)
    if binding.calendar.identity != binding.declaration.calendar.identity or not common.equal_tree(binding.inputs_raw, binding.declaration.inputs):
        raise ValueError('Changed original INIT phase declaration or calendar')
    receipt = binding.setup_receipt
    if receipt['source_phase'] != binding.calendar.phase or receipt['legacy_run_sim'] is not (binding.calendar.phase == 'SIM') or receipt['event_finalization']['legacy_run_sim'] is not (binding.calendar.phase == 'SIM') or (receipt['event_finalization']['event_fire_calls'] != 0) or (receipt['event_finalization']['dynamic_noise_calls'] != 0):
        raise ValueError('Changed source INIT setup phase receipt')

def record(value):
    return tuple((getattr(value, key) for key in State.__dataclass_fields__ if key != 'identity'))

def state(binding, net, field, rate, nak_rate, mechanical_state, stores, clock, history=(), observations=(), status=None):
    if status is None:
        status = 'exhausted' if clock.call_index == binding.calendar.step_count else 'capped' if clock.call_index == binding.call_limit else 'ready'
    result = State(binding.identity, net, field, rate, nak_rate, mechanical_state, ions.freeze(stores), clock, tuple(history), tuple(observations), status, '')
    return replace(result, identity=ions.digest(record(result)))

def initialize(declaration, *, after_setup=None, after_cold=None, before_field=None, handler_observer=None):
    """Execute each admitted setup producer once; return the ready binding and state."""
    if declaration.calendar.phase != 'INIT':
        raise ValueError('Fresh entry is INIT only; SIM requires the actual completed INIT handoff')
    if type(declaration) is not Declaration or declaration.identity != ions.digest(declaration_record(declaration)):
        raise ValueError('Require unchanged pre-setup INIT declaration')
    raw = ions.data(declaration.inputs)
    ctx, receipt, cold = (None, None, None)
    stage = 'static_setup'
    try:
        receipt = setup.pre_cold(declaration.base, raw['setup'])
        if after_setup is not None:
            after_setup(ions.freeze(receipt))
        stage = 'effective_static_diffusion_guard'
        field = ions.data(raw['field'])
        field['definition']['ions']['membrane_diffusion_m2_s'] = ions.data(receipt['stores']['Dm_cells'])
        base = base_bind(raw, field)
        preliminary = Binding(declaration, base.material_binding, base.voltage_binding, base.inputs, ions.freeze(raw), base.calcium, ions.freeze(raw['catalog']), raw['stop_after_calls'], declaration.calendar, declaration.mechanics, ions.freeze(receipt), '')
        initial = material.state(base.material_binding, ions.data(base.inputs['initial']))
        ctx = owner_context(preliminary, [np.array(v, copy=True) for v in initial.values])
        policy = calcium.native_policy(ctx, preliminary)
        install_stores(ctx, receipt['stores'])
        del ctx.sim.rho_pump
        del ctx.sim.rho_channel
        ctx.p.dt = declaration.calendar.dt_s
        stage = 'cold'
        cached = owners.initialize(ctx, handler_observer)
        owners.validate_phase_cache(ctx, cached, 0, pre_late=True)
        cold = dict(network_cache=cached, material=source.material_values(ctx.sim), policy=policy, trace=source.clone(ctx.trace), source_phase=ctx.phase.kind, legacy_run_sim=ctx.p._run_sim, actual_cold_voltage_V=np.array(ctx.sim.vm, copy=True), clock=Clock(ions.freeze(calendars.window(declaration.calendar).event_label_s), 0, 0.0), rate_cache=RateCache(False, None), nak_rate=RateCache(False, None))
        stage = 'mechanics_entry'
        mechanical_state = mechanics.state(declaration.mechanics, raw['mechanics_initial'])
        ctx.sim.rho_pump = 1
        ctx.sim.rho_channel = 1
        if after_cold is not None:
            after_cold(ions.freeze(cold))
        stage = 'event_finalization'
        finalized = setup.finalize(ctx, raw['setup'])
        receipt = dict(receipt, cold=source.clone(cold), event_finalization=finalized, mechanics_entry=mechanical_state, entry_stores=setup.snapshot(ctx), setup_complete=True, physical_initializer_executed=False, initializer_cache_seam=raw['setup']['receipts']['initializer_cache'])
        binding = replace(preliminary, setup_receipt=ions.freeze(receipt))
        binding = replace(binding, identity=ions.digest(binding_record(binding)))
        initial = material.state(binding.material_binding, source.material_values(ctx.sim))
        controls = {key: source.clone(getattr(ctx.sim, key)) for key in ('gj_block', 'NaKATP_block')}
        owners.reset_storage(ctx)
        net = network._state(binding, initial, owners.cache(ctx), controls)
        arrays = calendars.window(binding.calendar)
        clock = Clock(ions.freeze(arrays.event_label_s), 0, 0.0)
        stage = 'bootstrap'
        prepared, fields = full.reconstruct(binding, net, binding.calendar.dt_s, ions.data(binding.inputs['bootstrap']['boundary_V']), 'bootstrap', before_field)
        result = state(binding, prepared, fields, RateCache(False, None), RateCache(False, None), mechanical_state, setup.snapshot(ctx), clock)
        verify(binding, result)
        return (binding, result)
    except Exception as error:
        raise InitRejected(error, dict(stage=stage, declaration=declaration, setup_receipt=receipt, cold=cold, inner_partial=getattr(error, 'partial', None), **phase_failure_snapshot(ctx, None))) from error

def check_rate(value, m, expected):
    if type(value) is not RateCache or type(value.present) is not bool or value.present is not expected:
        raise ValueError('INIT rate-cache presence differs from the actual producer epoch')
    if not value.present:
        if value.value is not None:
            raise ValueError('Absent INIT rate cache cannot contain fabricated values')
    elif not isinstance(value.value, np.ndarray) or value.value.shape != (m,) or value.value.dtype != np.float64 or value.value.flags.writeable or (not np.isfinite(value.value).all()):
        raise ValueError('Require the complete immutable source-written INIT rate cache')

def verify(binding, parent):
    verify_binding(binding)
    if type(parent) is not State or parent.binding_identity != binding.identity or parent.identity != ions.digest(record(parent)):
        raise ValueError('Require the unchanged complete INIT parent')
    index = parent.cursor
    if type(index) is not int or not 0 <= index <= binding.call_limit or index != parent.network.material.step_index or (index != parent.mechanics.step_index):
        raise ValueError('INIT material, clock, mechanics and bounded prefix must share one cursor')
    if parent.network.binding_identity != binding.identity or parent.network.identity != network._state(binding, parent.network.material, parent.network.network_cache, parent.network.controls).identity:
        raise ValueError('Changed INIT network parent')
    checked = material.state(binding.material_binding, ions.data(parent.network.material.values._asdict()), step_index=index)
    if checked.identity != parent.network.material.identity:
        raise ValueError('Changed actual INIT material parent')
    if type(parent.field) is not full.FieldStage or parent.field.binding_identity != binding.identity or parent.field.identity != ions.digest(full.field_record(parent.field)):
        raise ValueError('Require actual prior reconstructed full field')
    mechanics._verify(binding.mechanics, parent.mechanics)
    if parent.mechanics.sampled_steps:
        raise ValueError('Headless INIT cannot acquire native display completion credit')
    labels = calendars.window(binding.calendar).event_label_s
    if type(parent.clock) is not Clock or not isinstance(parent.clock.source_times_s, np.ndarray) or parent.clock.source_times_s.flags.writeable or (parent.clock.source_times_s.dtype != np.float64) or (not np.array_equal(parent.clock.source_times_s, labels)) or (parent.clock.material_dt_sum_s != index * binding.calendar.dt_s):
        raise ValueError('Require the complete original INIT calendar without rebasing')
    m = len(binding.material_binding.geometry_binding.current_binding.membrane_ids)
    check_rate(parent.rate_cache, m, binding.setup_receipt.get('entry_CaATP_present', False) or (index > 0 and binding.calcium['alpha_Ca'] > 0))
    check_rate(parent.nak_rate, m, binding.setup_receipt.get('entry_NaK_present', False) or index > 0)
    working = [np.array(v, copy=True) for v in parent.network.material.values]
    ctx = owner_context(binding, working)
    owners.validate_phase_cache(ctx, parent.network.network_cache, index)
    if len(parent.history) != index or len(parent.observations) != sum((bool(v) for v in calendars.window(binding.calendar, stop=index).sampled)):
        raise ValueError('Require one complete receipt per accepted INIT call and eligible observation')
    for j, row in enumerate(parent.history):
        if row['call_index'] != j or row['source_label_s'] != float(labels[j]) or row['dt_s'] != binding.calendar.dt_s or (row['material_dt_sum_s'] != (j + 1) * binding.calendar.dt_s):
            raise ValueError('Changed original INIT call receipt')
    for key in set(setup.STORES) - {'gj_block', 'NaKATP_block', 'div_u_osmo'}:
        if not common.equal_tree(parent.stores[key], binding.setup_receipt['entry_stores'][key]):
            raise ValueError('Changed INIT phase setup store: ' + key)
    for key in ('gj_block', 'NaKATP_block'):
        if not common.equal_tree(parent.stores[key], parent.network.controls[key]):
            raise ValueError('Changed source-written persistent INIT control')
    expected_status = 'exhausted' if index == binding.calendar.step_count else 'capped' if index == binding.call_limit else 'ready'
    if parent.status not in {expected_status, 'paused' if expected_status == 'ready' else expected_status}:
        raise ValueError('INIT status differs from the original phase/prefix cursor')

def advance(binding, parent, *, observer=None, before_nak=None, before_material=None, before_calcium=None, after_calcium=None, before_mechanics=None, after_mechanics=None, before_field=None, after_material=None, handler_observer=None, before_commit=None):
    verify(binding, parent)
    if parent.status != 'ready':
        raise ValueError('Require a ready INIT parent with an admitted source call')
    index, holder, stage = (parent.cursor, {}, 'before_call_observer')
    dt = binding.calendar.dt_s
    label = float(parent.clock.source_times_s[index])
    row = ions.data(binding.inputs['steps'][index])
    try:
        if observer is not None:
            observer('before_call', parent)
        stage = 'nak'
        nak, flux, proxy = pump.produce(binding, parent.network.material, ions.data(parent.stores), parent.nak_rate, before_nak)
        holder['nak'] = nak
        if not pump.finite(nak):
            raise ValueError('Nonfinite complete ordinary INIT NaK output')
        stores = ions.data(parent.stores)
        packet = dict(row['material'], supplied_pump_membrane_flux_mol_m2_s=flux, runtime_temperature_K=stores['T'], boundary_mol_m3=stores['c_env_bound'], channel_multiplier=np.broadcast_to(stores['rho_channel'], (len(flux[0]),)).copy(), junction_block=np.broadcast_to(stores['gj_block'], (len(flux[0]),)).copy(), electric_x_source=parent.field.environment.values.electric_x_source, electric_y_source=parent.field.environment.values.electric_y_source)
        forcing = material.drive(binding.material_binding, packet)
        incoming = dict(mode='material', definition=ions.data(binding.inputs['definition']), initial=ions.data(parent.network.material.values._asdict()), steps=[source.clone(packet)], calcium=ions.data(binding.calcium), rate_cache_before=ions.data(parent.rate_cache), clock=ions.data(parent.clock), catalog=ions.data(binding.catalog), network_cache=ions.data(parent.network.network_cache), nak_before=ions.data(nak['before']), source_phase=binding.calendar.phase, legacy_run_sim=binding.calendar.phase == 'SIM')
        holder['material_input'] = incoming
        stage = 'before_material'
        if before_material is not None:
            before_material(ions.freeze(incoming))

        def on_calcium(arrays):
            holder['stage'] = 'calcium'
            result, phase = calcium.calcium(binding, arrays, forcing, parent.rate_cache, parent.clock, before_calcium)
            holder.update(rate=result, calcium=phase)
            if after_calcium is not None:
                after_calcium(result, phase)

        def on_network(arrays):
            holder['stage'] = 'network'
            ctx = owner_context(binding, arrays, forcing)
            holder['ctx'] = ctx
            restore_owners(ctx, parent.network.network_cache, index)
            calcium.native_policy(ctx, binding)
            install_stores(ctx, stores)
            ctx.p.dt = dt
            ctx.sim.rate_NaKATP = proxy.copy()
            if holder['rate'].present:
                ctx.sim.rate_CaATP = holder['rate'].value.copy()
            ctx.trace.update(source_phase=binding.calendar.phase, legacy_run_sim=binding.calendar.phase == 'SIM')
            dispatch_owners(ctx, ions.data(binding.inputs['definition']), row['publication'], label, handler_observer)
            owners.validate_phase_cache(ctx, owners.cache(ctx), index + 1)

        def on_post_network(arrays):
            holder['stage'] = 'mechanics'
            ctx = holder['ctx']
            incoming_mech = mechanical.mechanics_input(binding, parent, ctx, index)
            holder['mechanics_input'] = ions.freeze(incoming_mech)
            if before_mechanics is not None:
                before_mechanics(ions.freeze(dict(mode='mechanics', definition=binding.mechanics.definition, initial=parent.mechanics.cache, steps=[incoming_mech])))
            try:
                trial = mechanics.step(binding.mechanics, parent.mechanics, incoming_mech)
            except Exception as error:
                holder['mechanics_failure'] = getattr(error, 'trial', None)
                raise
            holder['mechanics_trial'] = trial
            if after_mechanics is not None:
                after_mechanics(trial)
            holder['before_commit'] = ions.freeze(dict(mode='commit', definition=ions.data(binding.inputs['definition']), values_before=source.material_values(ctx.sim), initial=ions.data(parent.network.material.values._asdict()), steps=[source.clone(packet)], material_inputs=incoming, source_phase=binding.calendar.phase, legacy_run_sim=binding.calendar.phase == 'SIM'))
            if before_commit is not None:
                before_commit(holder['before_commit'])

        def failed(local):
            holder['material_partial'] = dict(frames=local.get('frames'), environment_records=local.get('environment_records'), trial=local.get('trial'), diagnostics=local.get('diagnostics'), failure=local.get('failure'), available_arrays={k: v.copy() for k, v in local.items() if isinstance(v, np.ndarray)})
        stage = 'material_calcium_network_mechanics'
        trial = material_init.step_init(binding.material_binding, parent.network.material, forcing, on_network=on_network, on_failure=failed, on_calcium=on_calcium, on_post_network=on_post_network)
        holder['material_trial'] = trial
        ctx = holder['ctx']
        candidate = network._state(binding, trial.candidate, owners.cache(ctx), ctx.trace['controls_after'])
        holder['material_candidate'] = candidate
        if after_material is not None:
            after_material(candidate, trial, ctx.trace, holder['calcium'])
        stage = 'field'
        prepared, fields = full.reconstruct(binding, candidate, dt, row['boundary_V'], 'field', before_field)
        stores = setup.snapshot(ctx)
        for key in ('gj_block', 'NaKATP_block'):
            stores[key] = source.clone(ctx.trace['controls_after'][key])
        stores['div_u_osmo'] = ions.data(holder['mechanics_trial'].candidate.cache['div_u_osmo'])
        sampled = bool(calendars.window(binding.calendar, start=index, stop=index + 1).sampled[0])
        receipt = ions.freeze(dict(call_index=index, source_label_s=label, dt_s=dt, material_dt_sum_s=(index + 1) * dt, incoming_identity=parent.identity, material_candidate_identity=candidate.identity, source_phase=binding.calendar.phase, legacy_run_sim=binding.calendar.phase == 'SIM', sample_eligible=sampled, event_fire_calls=0, protein_noise_calls=0))
        observations = parent.observations
        if sampled:
            observations += (ions.freeze(dict(call_index=index, source_label_s=label, elapsed_end_s=(index + 1) * dt, network=prepared, field=fields, mechanics=holder['mechanics_trial'].candidate, native_storage_called=False, display_completed=False)),)
        result = state(binding, prepared, fields, holder['rate'], RateCache(True, proxy), holder['mechanics_trial'].candidate, stores, Clock(parent.clock.source_times_s, index + 1, (index + 1) * dt), parent.history + (receipt,), observations)
        verify(binding, result)
        holder['accepted'] = result
        stage = 'after_call_observer'
        if observer is not None:
            observer('after_call', result)
        return (result, ions.freeze({key: value for key, value in holder.items() if key != 'ctx'} | dict(network=ctx.trace, field=fields, receipt=receipt)))
    except Exception as error:
        ctx = holder.get('ctx')
        raise InitRejected(error, dict(stage=stage, reached_stage=holder.get('stage'), call_index=index, parent=parent, available={key: value for key, value in holder.items() if key != 'ctx'}, inner_partial=getattr(error, 'partial', None), root_cause=dict(type=type(error).__name__, message=str(error)), **phase_failure_snapshot(ctx, parent.network.network_cache))) from error

def pause(binding, parent):
    verify(binding, parent)
    if parent.status != 'ready':
        raise ValueError('Only a ready unfinished INIT window can pause')
    result = replace(parent, status='paused', identity='')
    return replace(result, identity=ions.digest(record(result)))

def resume(binding, parent):
    verify(binding, parent)
    if parent.status != 'paused':
        raise ValueError('Require the original paused INIT parent')
    result = replace(parent, status='ready', identity='')
    return replace(result, identity=ions.digest(record(result)))

def run_window(binding, parent, *, stop, **callbacks):
    verify(binding, parent)
    if type(stop) is not int or not parent.cursor <= stop <= binding.call_limit:
        raise ValueError('Require a bounded stop on the unchanged original INIT calendar')
    current = resume(binding, parent) if parent.status == 'paused' else parent
    returned = []
    while current.cursor < stop:
        current, details = advance(binding, current, **callbacks)
        returned.append(details)
    if current.status == 'ready':
        current = pause(binding, current)
    return (current, tuple(returned))

def request_native_sample(binding, parent):
    verify(binding, parent)
    raise InitRejected(ValueError('Native display requires at least25 cells; this field domain admits at most16'), dict(stage='explicit_native_sample_refusal', parent=parent, observations=parent.observations, display_completed=False, native_storage_called=False))

def phase_failure_snapshot(ctx, supplied):
    return dict(owner_buffers=owners.available(ctx), supplied_owner_cache=supplied)

def expected_flags(raw):
    kind = raw['time_profile']['phase']
    if kind not in ('INIT', 'SIM'):
        raise ValueError('Require explicit native INIT/SIM phase selection')
    owner = raw['owners']['configuration']
    return dict(FIXED_FLAGS, phase=kind, _run_sim=kind == 'SIM', molecules_enabled=owner['general network']['implement network'], grn_enabled=owner['gene regulatory network settings']['gene regulatory network simulated'])

def validate_owner_scope(raw):
    transport.bind(raw['owners'])
    for actual, wanted in ((raw['owners']['field'], raw['field']), (raw['owners']['calcium'], raw['calcium']), (raw['owners']['handlers']['grn']['catalog'], raw['catalog'])):
        if not common.equal_tree(actual, wanted):
            raise ValueError('Phase physical/carrier/catalog declarations differ from actual owner inputs')
    if raw['setup']['channel_noise_level'] != 0 or raw['setup']['dynamic_noise'] != dict(enabled=False, level=0.0):
        raise ValueError('First supplied owner lifecycle closes static/dynamic noise while preserving complete stream/reset receipts')
    if any((value != 0 for key in ('global_options', 'scheduled_options') for value in raw['setup'][key].values())):
        raise ValueError('This phase composition requires the supplied no-intervention material seam')
    policy = raw['mechanics_definition']['policy']
    if any((policy[key] for key in ('deformation', 'deform_osmo', 'fluid_flow'))):
        raise ValueError('Enabled mechanics/osmotic/flow requires a separate complete two-owner coupling')
    for key in ('molecules_enabled', 'grn_enabled'):
        if policy[key] is not expected_flags(raw)[key]:
            raise ValueError('Supplied mechanics projection must declare the actual independent owner flags')
    if raw['time_profile']['phase'] == 'SIM' and lifecycle.profile(raw['time_profile'])['sim']['step_count'] != 3:
        raise ValueError('SIM retains the explicit existing three-call source domain')

def owner_context(binding, values, forcing=None):
    return owners.make_context(binding, ions.data(binding.inputs_raw['owners']), values, forcing, phase_kind=binding.calendar.phase)

def install_stores(ctx, stores):
    kind = ctx.phase.kind
    setup.install(ctx, stores)
    owners.phase(ctx, kind)

def restore_owners(ctx, saved, index):
    owners.validate_phase_cache(ctx, saved, index)
    return owners.restore(ctx, ions.data(saved))

def dispatch_owners(ctx, definition, publication, label, observer=None):
    result = owners.dispatch(ctx, definition, publication, label, observer)
    ctx.trace = dict(source_completed=True, source_phase=ctx.phase.kind, legacy_run_sim=ctx.p._run_sim, controls_after={key: source.clone(getattr(ctx.sim, key)) for key in ('gj_block', 'NaKATP_block')}, handlers=result['handlers'], source_order=result['order'], shared_after=result['shared_after'], publication_owner=result['publication_owner'])
    return ctx.trace
