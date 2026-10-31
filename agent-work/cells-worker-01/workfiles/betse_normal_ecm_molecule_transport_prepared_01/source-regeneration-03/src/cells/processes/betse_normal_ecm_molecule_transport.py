# ruff: noqa: E501, F841, B007, B905
"""Ordinary ECM material/CaATP with distinct native general and GRN owners.

Supplied physical/setup fields are explicit. General and GRN source flags are
independent. Native publication overwrites, role caches, boundary/control carry
and full current/field feedback remain owned. This feature is held and unrun.
"""
from cells.processes import betse_normal_ecm_molecule_dispatch as prior
from cells.processes import betse_network_transport as transport_component
from cells.processes import betse_normal_transporter_source as transporter_source
from dataclasses import dataclass, replace
import numpy as np
from cells.processes import betse_ecm_grn_join as network
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_normal_ecm_calcium_join as calcium
from cells.processes import betse_normal_ecm_catalog_join_source as qualified
from cells.processes import betse_normal_ecm_field_join as full
from cells.processes import betse_normal_ecm_molecule_transport_runtime as runtime
from cells.processes import betse_normal_ion_join as ions
LAW_ID = 'betse_supplied_FULL_ECM_general_transport_then_GRN_v1_5_0@1'
INPUT_KIND = 'cells.normal_ecm_general_molecule_transport_inputs@1'
FLAGS = dict(solver='FULL', is_ecm=True, Ca_dyn=False, fluid_flow=False, td_deform=False, sim_eosmosis=False, dynamic_noise=0, deform_osmo=False, deformation=False)

@dataclass(frozen=True)
class Binding:
    component: object
    inputs: object
    identity: str

@dataclass(frozen=True)
class State:
    binding_identity: str
    material: object
    field: object
    owners: object
    controls: object
    rate_cache: object
    clock: object
    identity: str

    @property
    def cursor(self):
        return self.material.step_index

class NativeConfigurationObstructed(ValueError):
    pass

class DispatchRejected(RuntimeError):

    def __init__(self, error, partial):
        super().__init__(str(error))
        self.partial = ions.freeze(partial)

def binding_record(value):
    return (LAW_ID, value.component.identity, value.inputs)

def bind(inputs):
    raw = ions.data(inputs)
    if not isinstance(raw, dict) or raw.get('kind') != INPUT_KIND or 'transport' not in raw:
        raise ValueError('Require the separate complete ECM general-transporter declaration')
    lower = qualified.clone(raw)
    transport = lower.pop('transport')
    lower['kind'] = prior.INPUT_KIND
    if raw['configuration']['general network'] is None:
        raise NativeConfigurationObstructed('Absent general network leaves molecules_enabled unwritten')
    general = raw['handlers']['molecules']['network']['configuration']
    lower['handlers']['molecules']['network']['configuration'].pop('transporters', None)
    lower['configuration']['general network'].pop('transporters', None)
    base = prior.bind(lower)
    expected = dict(general, channels=raw['handlers']['molecules']['catalog']['populations'], **{'implement network': raw['configuration']['general network']['implement network']})
    if not qualified.equal_tree(raw['configuration']['general network'], expected):
        raise ValueError('Native general configuration and configured transporter owner differ')
    if not isinstance(transport, dict) or set(transport) != {'membrane_volume_m3', 'raw_setup_fault'}:
        raise ValueError('Require explicit native membrane wedge volumes and raw-fault declaration')
    external = base.component.inputs['definition']['environment_geometry_definition']
    cg = external['current_definition']['geometry']
    area = np.asarray(cg['membrane_area_m2'], np.float64)
    owner = np.asarray(cg['owner'], np.int64)
    mids = np.asarray(external['geometry']['membrane_midpoints_m'], np.float64)
    centres = np.asarray(external['geometry']['cell_centres_m'], np.float64)
    rads = mids - centres[owner]
    radius = np.sqrt(rads[:, 0] ** 2 + rads[:, 1] ** 2)
    volume = np.asarray(transport['membrane_volume_m3'], np.float64)
    if volume.shape != area.shape or not np.isfinite(volume).all() or np.any(volume <= 0) or (not np.array_equal(volume, 0.5 * radius * area)):
        raise ValueError('Require source mem_vol=0.5*R_rads*mem_sa on the actual supplied geometry')
    rows = general.get('transporters')
    if rows is not None and (not isinstance(rows, list) or len(rows) > 3):
        raise ValueError('Require at most three ordered native general-owner transporters')
    fault = transport['raw_setup_fault']
    if fault not in (None, 'missing_max_rate_0', 'missing_max_rate_1'):
        raise ValueError('Unknown separately declared raw transporter setup fault')
    admitted = qualified.clone(rows or [])
    if fault is not None:
        index = int(fault[-1])
        if not raw['configuration']['general network']['implement network'] or index >= len(admitted) or 'max rate' in admitted[index]:
            raise ValueError('Raw setup fault must be the literal absent max rate in an enabled owner')
        admitted[index]['max rate'] = 1e-09
    for row in admitted:
        if row.get('apply to') != 'all' or row.get('ignore ECM') is not False:
            raise ValueError('First ECM transporter seam requires all targets and the declared stored ignore flag False')
        if row.get('standard free energy') != 'None' and (not (type(row.get('standard free energy')) in (int, float) and np.isfinite(row['standard free energy']))):
            raise ValueError("Native standard energy must be finite or literal 'None'")
    if admitted:
        ids = tuple(external['current_definition']['ions']['ids'])
        products = general['biomolecules']
        species = ids + tuple((row['name'] for row in products))
        zs = tuple(external['current_definition']['ions']['valence']) + tuple((row['z'] for row in products))
        transport_component.bind(admitted, species, transporter_source.integer_valences(zs), [0] * len(admitted), [1] * len(admitted), [True, True], area_m2=[1.0] * len(admitted), temperature_K=external['parameters']['configured_temperature_K'])
    value = Binding(base.component, ions.freeze(raw), '')
    return replace(value, identity=ions.digest(binding_record(value)))

def state_record(value):
    return (value.binding_identity, value.material, value.field, value.owners, value.controls, value.rate_cache, value.clock)

def state(binding, parent, field, owners, controls, rate, clock):
    value = State(binding.identity, parent, field, ions.freeze(owners), ions.freeze(controls), rate, clock, '')
    return replace(value, identity=ions.digest(state_record(value)))

def verify(binding, parent):
    if type(binding) is not Binding or binding.identity != ions.digest(binding_record(binding)):
        raise ValueError('Changed dual-owner composition declaration')
    if type(parent) is not State or parent.binding_identity != binding.identity or parent.identity != ions.digest(state_record(parent)):
        raise ValueError('Changed complete primary/field/dual-owner state')
    checked = material.state(binding.component.material_binding, parent.material.values._asdict(), step_index=parent.cursor)
    if checked.identity != parent.material.identity or parent.clock.call_index != parent.cursor or (not 0 <= parent.cursor <= 3):
        raise ValueError('Original bounded source material and clock epochs differ')
    dt = binding.component.inputs['bootstrap']['dt_s']
    if type(parent.clock) is not calcium.Clock or not isinstance(parent.clock.source_times_s, np.ndarray) or parent.clock.source_times_s.dtype != np.float64 or parent.clock.source_times_s.flags.writeable or (not np.array_equal(parent.clock.source_times_s, np.linspace(0, 3 * dt, 3))) or (parent.clock.material_dt_sum_s != parent.cursor * dt):
        raise ValueError('Changed original source labels or accumulated material time')
    if type(parent.field) is not full.FieldStage or parent.field.binding_identity != binding.component.identity or parent.field.identity != ions.digest(full.field_record(parent.field)):
        raise ValueError('Require the actual complete preceding field state')
    expected = bool(binding.component.calcium['alpha_Ca'] > 0 and parent.cursor > 0)
    rate = parent.rate_cache
    if type(rate) is not calcium.RateCache or rate.present is not expected or (rate.value is not None if not expected else not isinstance(rate.value, np.ndarray) or rate.value.shape != (len(binding.component.material_binding.geometry_binding.current_binding.membrane_ids),) or rate.value.dtype != np.float64 or rate.value.flags.writeable or (not np.isfinite(rate.value).all())):
        raise ValueError('CaATP cache must match its actual source writer epoch')
    flags = dict(molecules=binding.inputs['configuration']['general network']['implement network'], grn=binding.inputs['configuration']['gene regulatory network settings']['gene regulatory network simulated'])
    if not qualified.equal_tree(parent.owners['enabled'], flags):
        raise ValueError('Changed active source flags')
    for role in runtime.ROLES:
        saved = parent.owners['handlers'][role]
        if (saved is not None) is not flags[role]:
            raise ValueError('Enabled owner must be complete; disabled owner must be absent')
        if saved is not None and saved['role'] != role:
            raise ValueError('General and GRN owners cannot be interchanged')
    for key in runtime.PUBLICATIONS:
        if not qualified.equal_tree(parent.owners['wire']['simulator_fields'][key], parent.owners['shared'][key]):
            raise ValueError('Field projection and actual shared publication epoch differ')
    pubs = parent.owners['wire']['simulator_fields']
    for actual, wanted in ((parent.field.before['current']['extra_charge_C_m3'], pubs['extra_rho_cells']), (parent.field.before['current']['extra_current_A_m2'], pubs['extra_J_mem']), (parent.field.before['environment']['extra_environment_charge_C_m3'], pubs['extra_rho_env']), (parent.field.before['environment']['extra_environment_current_xy'], np.column_stack((pubs['extra_Jenv_x'], pubs['extra_Jenv_y'])))):
        if not qualified.equal_tree(actual, wanted):
            raise ValueError('Shared network publications differ from their actual field epoch')
    runtime.validate_transport_cache(binding, parent)

def initialize(binding, *, observer=None, before_field=None):
    ctx = None
    stage = 'entry'
    try:
        if type(binding) is not Binding or binding.identity != ions.digest(binding_record(binding)):
            raise ValueError('Changed supplied dual-owner binding')
        component = binding.component
        original = material.state(component.material_binding, ions.data(component.inputs['initial']))
        working = material.Values(*(np.array(v, copy=True) for v in original.values))
        ctx = runtime.make_context(component, ions.data(binding.inputs), working)
        stage = 'native_handler_setup'
        owners = runtime.initialize(ctx, observer)
        initial = material.state(component.material_binding, qualified.material_values(ctx.sim))
        controls = {key: qualified.clone(getattr(ctx.sim, key)) for key in ('gj_block', 'NaKATP_block')}
        net = network._state(component, initial, owners, controls)
        stage = 'bootstrap'
        dt = component.inputs['bootstrap']['dt_s']
        prepared, field = full.reconstruct(component, net, dt, ions.data(component.inputs['bootstrap']['boundary_V']), 'bootstrap', before_field)
        result = state(binding, prepared.material, field, owners, controls, calcium.RateCache(False, None), calcium.Clock(ions.freeze(np.linspace(0, 3 * dt, 3)), 0, 0.0))
        verify(binding, result)
        return result
    except Exception as error:
        raise DispatchRejected(error, dict(stage=stage, available=runtime.available(ctx), inner_partial=getattr(error, 'partial', None), root_cause=dict(type=type(error).__name__, message=str(error)), automatic_retry=False)) from error

def advance(binding, parent, *, before_material=None, before_calcium=None, handler_observer=None, before_commit=None, before_field=None):
    verify(binding, parent)
    ctx = None
    holder = {}
    stage = 'material_input'
    component = binding.component
    index = parent.cursor
    if index >= 3:
        raise ValueError('Original three-call material domain exhausted')
    row = ions.data(component.inputs['steps'][index])
    packet = dict(row['material'], junction_block=ions.data(parent.controls['gj_block']), electric_x_source=parent.field.environment.values.electric_x_source, electric_y_source=parent.field.environment.values.electric_y_source)
    forcing = material.drive(component.material_binding, packet)
    incoming = dict(mode='material', definition=ions.data(component.inputs['definition']), initial=ions.data(parent.material.values._asdict()), steps=[qualified.clone(packet)], calcium=ions.data(component.calcium), rate_cache_before=parent.rate_cache, clock=parent.clock, dual_owner_cache=parent.owners)
    try:
        if before_material is not None:
            before_material(ions.freeze(incoming))

        def on_calcium(arrays):
            holder['rate'], holder['calcium'] = calcium.calcium(component, arrays, forcing, parent.rate_cache, parent.clock, before_calcium)

        def on_network(arrays):
            nonlocal ctx, stage
            stage = 'general_then_GRN'
            ctx = runtime.make_context(component, ions.data(binding.inputs), arrays, forcing)
            runtime.restore(ctx, ions.data(parent.owners))
            ctx.sim.gj_block = qualified.clone(parent.controls['gj_block'])
            ctx.sim.NaKATP_block = qualified.clone(parent.controls['NaKATP_block'])
            ctx.sim.rho_channel = np.array(forcing.channel_multiplier, copy=True)
            ctx.sim.c_env_bound = np.array(forcing.boundary_mol_m3, copy=True)
            if holder['rate'].present:
                ctx.sim.rate_CaATP = holder['rate'].value.copy()
            holder['dispatch'] = runtime.dispatch(ctx, ions.data(component.inputs['definition']), row['publication'], float(parent.clock.source_times_s[index]), handler_observer)
            holder['before_commit'] = ions.freeze(dict(mode='commit', definition=ions.data(component.inputs['definition']), values_before=qualified.material_values(ctx.sim), initial=ions.data(parent.material.values._asdict()), steps=[qualified.clone(packet)], material_inputs=incoming))
            if before_commit is not None:
                before_commit(holder['before_commit'])

        def failed(local):
            holder['material_partial'] = dict(frames=tuple(local.get('frames', ())), environment_records=tuple(local.get('environment_records', ())))
        trial = calcium._material_step(component.material_binding, parent.material, forcing, on_network=on_network, on_failure=failed, on_calcium=on_calcium)
        holder['trial'] = trial
        owners = runtime.cache(ctx)
        controls = {key: qualified.clone(getattr(ctx.sim, key)) for key in ('gj_block', 'NaKATP_block')}
        net = network._state(component, trial.candidate, owners, controls)
        stage = 'field'
        prepared, field = full.reconstruct(component, net, forcing.dt_s, row['boundary_V'], 'field', before_field)
        result = state(binding, prepared.material, field, owners, controls, holder['rate'], calcium.Clock(parent.clock.source_times_s, index + 1, parent.clock.material_dt_sum_s + forcing.dt_s))
        verify(binding, result)
        return (result, ions.freeze(holder))
    except Exception as error:
        raise DispatchRejected(error, dict(stage=stage, parent=parent, available=runtime.available(ctx), holder=holder, inner_partial=getattr(error, 'partial', None), root_cause=dict(type=type(error).__name__, message=str(error)), automatic_retry=False)) from error
