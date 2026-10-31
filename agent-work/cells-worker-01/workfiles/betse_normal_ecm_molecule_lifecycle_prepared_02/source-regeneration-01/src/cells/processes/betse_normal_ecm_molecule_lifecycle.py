# ruff: noqa: E501
"""Held supplied cold/INIT/retained dual-owner SIM lifecycle with active transporters.

Complete headless INIT is distinct from failed, paused or capped prefixes.
Every phase keeps its own source labels, material dt, caches and journal.
This new source proposal carries no scientific result or native persistence claim.
"""
from dataclasses import dataclass, replace
import numpy as np
from cells.processes import betse_ecm_grn_join as network
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_normal_ecm_catalog_join_source as catalog
from cells.processes import betse_normal_ecm_field_join as fields
from cells.processes import betse_normal_ecm_molecule_lifecycle_phase as init
from cells.processes import betse_normal_ecm_molecule_lifecycle_owners as owners
from cells.processes import betse_normal_ecm_molecule_lifecycle_setup as setup
from cells.processes import betse_normal_ion_join as ions
LAW_ID = 'betse_supplied_ECM_general_transport_INIT_to_SIM_v1_5_0@1'
INPUT_KIND = 'cells.normal_ecm_molecule_lifecycle_inputs@1'

@dataclass(frozen=True)
class CompleteInit:
    binding: object
    parent: object
    scope: str
    identity: str

@dataclass(frozen=True)
class FailedInitPrefix:
    binding: object
    accepted: object
    failure: object
    identity: str

class TransitionRejected(RuntimeError):

    def __init__(self, error, partial):
        super().__init__(str(error))
        self.partial = ions.freeze(partial)

def complete_record(value):
    return (LAW_ID, 'complete_headless_INIT', value.binding.identity, value.parent, value.scope)

def prepare_complete(binding, parent):
    init.verify(binding, parent)
    if parent.status != 'exhausted' or parent.cursor != binding.calendar.step_count or parent.cursor != binding.call_limit:
        raise TransitionRejected(ValueError('Only an exhausted complete headless INIT may prepare a normal handoff'), dict(stage='INIT_completion_admission', parent=parent, original_count=binding.calendar.step_count, native_phase_completion_attested=False))
    value = CompleteInit(binding, parent, 'complete_headless_source_subset_no_native_persistence', '')
    return replace(value, identity=ions.digest(complete_record(value)))

def prepare_failed_prefix(binding, accepted, error):
    if type(error) is not init.InitRejected or (not isinstance(error.partial, dict) and (not hasattr(error.partial, 'keys'))):
        raise ValueError('Require the actual retained INIT refusal with complete partial evidence')
    if accepted is None:
        if type(binding) is not init.Declaration or binding.identity != ions.digest(init.declaration_record(binding)) or error.partial.get('declaration') is None or (error.partial['declaration'].identity != binding.identity):
            raise ValueError('A setup failure requires its actual pre-setup INIT declaration')
    else:
        init.verify(binding, accepted)
    original = error.partial.get('parent')
    completed = error.partial.get('available', {}).get('accepted')
    if accepted is not None and (not any((type(candidate) is init.State and candidate.identity == accepted.identity for candidate in (original, completed)))):
        raise ValueError('Failed INIT prefix is foreign to its actually accepted parent')
    failure = ions.freeze(dict(type=type(error).__name__, message=str(error), partial=error.partial, native_pickle_or_load_attested=False, automatic_retry=False))
    value = FailedInitPrefix(binding, accepted, failure, '')
    return replace(value, identity=ions.digest((LAW_ID, 'failed_INIT_prefix', binding.identity, accepted, failure)))

def check_complete(value):
    if type(value) is FailedInitPrefix:
        raise TransitionRejected(ValueError('Failed INIT prefixes cannot enter the normal SIM transition'), dict(stage='failed_prefix_transition_refusal', failed_prefix=value, native_pickle_or_completion_inferred=False))
    if type(value) is not CompleteInit or value.identity != ions.digest(complete_record(value)):
        raise ValueError('Require the unchanged explicit complete-headless INIT artifact')
    init.verify(value.binding, value.parent)
    if value.parent.status != 'exhausted' or value.parent.cursor != value.binding.calendar.step_count:
        raise ValueError('Changed INIT completion cursor or disposition')

def validate_setup_inputs(raw):
    cfg = raw['source_setup']
    if set(cfg) != {'kind', 'provenance', 'rng_mode', 'rng_provenance', 'numpy_rng', 'python_rng', 'environment_diffusion', 'tissue_profiles', 'cbnd', 'static_noise_level', 'frequency_sweep'} or cfg['kind'] != 'cells.supplied_SIM_reinitialization_seams@1':
        raise ValueError('Require every source SIM setup seam and process RNG owner')
    if cfg['rng_mode'] not in ('supplied_SIM_process_stream', 'same_process_no_unowned_draws'):
        raise ValueError('Never infer process RNG continuity from native pickle data')
    for key in ('provenance', 'rng_provenance'):
        if not isinstance(cfg[key], str) or not cfg[key].strip():
            raise ValueError('Require explicit conditional source setup provenance')
    setup.numpy_restore(cfg['numpy_rng'])
    setup.init_setup.python_restore(cfg['python_rng'])
    setup.init_setup.real(cfg['static_noise_level'], 'SIM static noise')
    if set(cfg['frequency_sweep']) != {'f start', 'f stop', 'f slope'}:
        raise ValueError('Require the actual SIM frequency factory inputs')
    for key, value in cfg['frequency_sweep'].items():
        if value is not None or key != 'f slope':
            setup.init_setup.real(value, key)
    equality = raw['config_equality_receipt']
    if set(equality) != {'general_before', 'general_after', 'world_before', 'world_after', 'provenance'} or equality['general_before'] != equality['general_after'] or equality['world_before'] != equality['world_after']:
        raise ValueError('Native seed compatibility compares both general and world options; supplied equality receipt differs')
    if not isinstance(equality['provenance'], str) or not equality['provenance'].strip():
        raise ValueError('Config equality is supplied association, not a native loader attestation')

def check_owners(binding, completed):
    raw = setup.legacy_setup_inputs(binding.inputs)
    if binding.expected_init_identity != completed.binding.identity:
        raise ValueError('Transition declaration belongs to another INIT binding')
    old = completed.binding.material_binding.geometry_binding.definition
    new = raw['sim_composition_template']['event_inputs']['field']['definition']['environment_geometry_definition']
    if not catalog.equal_tree(old['geometry'], new['geometry']) or not catalog.equal_tree(old['world'], new['world']) or (not catalog.equal_tree(old['current_definition']['geometry'], new['current_definition']['geometry'])) or (not catalog.equal_tree(old['current_definition']['ions'], new['current_definition']['ions'])):
        raise ValueError('Transition may not replace retained ionic, cell, membrane or environment owners')
    cfg = raw['source_setup']
    if cfg['rng_mode'] == 'same_process_no_unowned_draws':
        receipt = completed.binding.setup_receipt
        if cfg['numpy_rng'] != ions.data(receipt['numpy_rng_after']) or cfg['python_rng'] != ions.data(receipt['event_finalization']['python_rng_after']):
            raise ValueError('Declared same-process continuity differs from actual post-INIT setup streams')
    cg = new['current_definition']['geometry']
    names = new['current_definition']['ions']['ids']
    m, n, e = (len(cg['membrane_ids']), len(cg['cell_ids']), len(completed.parent.network.material.values.environment_mol_m3[0]))
    denv = cfg['environment_diffusion']
    if set(denv) != {'adherens_multiplier', 'tight_junction_multiplier', 'environment_in_cluster_indices', 'tight_junction_relative', 'provenance'}:
        raise ValueError('Require explicit retained-core initDenv inputs and provenance')
    for key in ('adherens_multiplier', 'tight_junction_multiplier'):
        setup.init_setup.real(denv[key], key)
    if len(denv['tight_junction_relative']) != len(names) or any((type(j) is not int or not 0 <= j < e for j in denv['environment_in_cluster_indices'])):
        raise ValueError('Require complete owned initDenv ion/environment axes')
    profiles = cfg['tissue_profiles']
    if not isinstance(profiles, list) or not profiles or len({r['name'] for r in profiles}) != len(profiles):
        raise ValueError('Require ordered unique supplied tissue selector outputs')
    maps = {}
    for row in profiles:
        if set(row) != {'name', 'cell_indices', 'membrane_indices', 'diffusion_m2_s', 'provenance'} or set(row['diffusion_m2_s']) != {'Dm_' + role for role in setup.ROLES}:
            raise ValueError('Require every literal native tissue permeability field')
        if any((type(j) is not int or not 0 <= j < n for j in row['cell_indices'])) or any((type(j) is not int or not 0 <= j < m for j in row['membrane_indices'])):
            raise ValueError('Foreign supplied source profile selector output')
        for value in row['diffusion_m2_s'].values():
            setup.init_setup.real(value, 'profile Dm')
        maps[row['name']] = row['membrane_indices']
    if maps != raw['sim_composition_template']['event_inputs']['catalog']['tissue_profiles']:
        raise ValueError('Retained GRN and new tissue/event profiles must share actual supplied targets')
    if cfg['cbnd'] is not None and (set(cfg['cbnd']) != set(names) or any((not np.isfinite(v) for v in cfg['cbnd'].values()))):
        raise ValueError('Require every native configured ionic boundary override')

@dataclass(frozen=True)
class Binding:
    inputs: object
    expected_init_identity: str
    declaration: object
    identity: str

@dataclass(frozen=True)
class SimPhase:
    binding_identity: str
    source_init: CompleteInit
    phase_binding: object
    active: object
    receipt: object
    identity: str

    @property
    def cursor(self):
        return self.active.cursor

def binding_record(value):
    return (LAW_ID, value.inputs, value.expected_init_identity, value.declaration.identity)

def bind(inputs):
    original = ions.data(inputs)
    if set(original) != {'kind', 'case_id', 'provenance', 'expected_init_binding_identity', 'sim_phase', 'source_setup', 'config_equality_receipt'} or original['kind'] != INPUT_KIND:
        raise ValueError('Require the separately declared retained dual-owner lifecycle boundary')
    for key in ('case_id', 'provenance', 'expected_init_binding_identity'):
        if not isinstance(original[key], str) or not original[key].strip():
            raise ValueError('Require explicit lifecycle association ' + key)
    declaration = init.bind(original['sim_phase'])
    if declaration.calendar.phase != 'SIM' or declaration.calendar.step_count != 3:
        raise ValueError('The new SIM phase must retain its independent original three-call calendar')
    raw = setup.legacy_setup_inputs(original)
    validate_setup_inputs(raw)
    if raw['source_setup']['static_noise_level'] != 0:
        raise ValueError('The first lifecycle binding keeps the supplied no-static-noise material seam')
    value = Binding(ions.freeze(original), original['expected_init_binding_identity'], declaration, '')
    return replace(value, identity=ions.digest(binding_record(value)))

def validate_binding(binding):
    if type(binding) is not Binding or binding.identity != ions.digest(binding_record(binding)):
        raise ValueError('Changed complete dual-owner lifecycle declaration')

def check_stable_owner_scope(binding, completed):
    old = ions.data(completed.binding.inputs_raw['owners'])
    new = ions.data(binding.inputs['sim_phase']['owners'])
    for role in owners.ROLES:
        key = 'general network' if role == 'molecules' else 'gene regulatory network settings'
        flag = 'implement network' if role == 'molecules' else 'gene regulatory network simulated'
        if old['configuration'][key][flag] is not new['configuration'][key][flag]:
            raise ValueError('Native flag changes retain or construct owners; this first boundary does not normalize latent owner transitions')
        before = old['handlers'][role]
        after = ions.data(new['handlers'][role])
        fault = new['transport']['raw_setup_fault'] if role == 'molecules' else None
        if fault is not None:
            index = int(fault[-1])
            after['network']['configuration']['transporters'][index]['max rate'] = before['network']['configuration']['transporters'][index]['max rate']
        if not catalog.equal_tree(before['network']['configuration'], after['network']['configuration']):
            raise ValueError('Changed or latent-null owner configuration requires its own complete source correspondence')
        if before['network']['cold_publish'] is not after['network']['cold_publish']:
            raise ValueError('Balance-once publication changes require explicit saved-initial charge accounting')
        if not catalog.equal_tree(before['catalog'], after['catalog']):
            raise ValueError('This phase-aware packet retains declared gates and changes their native phase activation only')
    old_parameters = completed.binding.material_binding.geometry_binding.definition['parameters']
    new_parameters = binding.inputs['sim_phase']['field']['definition']['environment_geometry_definition']['parameters']
    if old_parameters['configured_temperature_K'] != new_parameters['configured_temperature_K']:
        raise ValueError('Retained core temperature must agree with this supplied no-intervention phase declaration')

def phase_record(value):
    return (LAW_ID, value.binding_identity, value.source_init.identity, value.phase_binding.identity, value.active, value.receipt)

def phase(binding, completed, phase_binding, active, receipt):
    value = SimPhase(binding.identity, completed, phase_binding, active, ions.freeze(receipt), '')
    return replace(value, identity=ions.digest(phase_record(value)))

def transition(binding, completed, *, observer=None, before_field=None):
    ctx = None
    reached = None
    stage = 'complete_INIT_admission'
    try:
        validate_binding(binding)
        check_complete(completed)
        check_owners(binding, completed)
        check_stable_owner_scope(binding, completed)
        raw = ions.data(binding.inputs)
        stage = 'actual_retained_dual_owner_SIM_setup'
        ctx, template, mechanical, reached = setup.prepare(completed.binding, completed.parent, raw, observer)
        stage = 'actual_SIM_phase_declaration'
        declaration = init.bind(template['_phase_input'])
        base = declaration.base
        event = reached['event_finalized']
        receipt = dict(source_phase='SIM', legacy_run_sim=True, setup_complete=True, event_finalization=dict(legacy_run_sim=True, event_fire_calls=0, dynamic_noise_calls=0, python_rng_after=event['python_rng_after'], source_fields=event), numpy_rng_after=template['event_inputs']['prepared_rng']['manifest'], entry_stores=init.setup.snapshot(ctx), source_setup=reached, entry_CaATP_present=completed.parent.rate_cache.present, entry_NaK_present=completed.parent.nak_rate.present, source_init_identity=completed.identity, old_INIT_clock=ions.data(completed.parent.clock), source_cold_recapture=False, physical_initializer_executed=False, native_load_or_pickle=False)
        current = init.Binding(declaration, base.material_binding, base.voltage_binding, base.inputs, declaration.inputs, base.calcium, declaration.inputs['catalog'], declaration.inputs['stop_after_calls'], declaration.calendar, declaration.mechanics, ions.freeze(receipt), '')
        current = replace(current, identity=ions.digest(init.binding_record(current)))
        cache = owners.cache(ctx)
        owners.validate_phase_cache(ctx, cache, 0)
        initial = material.state(current.material_binding, catalog.material_values(ctx.sim), step_index=0)
        controls = {key: catalog.clone(getattr(ctx.sim, key)) for key in ('gj_block', 'NaKATP_block')}
        net = network._state(current, initial, cache, controls)
        stage = 'SIM_bootstrap'
        ready, field = fields.reconstruct(current, net, current.calendar.dt_s, ions.data(current.inputs['bootstrap']['boundary_V']), 'bootstrap', before_field)
        clock = init.Clock(ions.freeze(init.calendars.window(current.calendar).event_label_s), 0, 0.0)
        active = init.state(current, ready, field, completed.parent.rate_cache, completed.parent.nak_rate, mechanical, init.setup.snapshot(ctx), clock)
        init.verify(current, active)
        receipt['new_SIM_clock'] = ions.data(clock)
        result = phase(binding, completed, current, active, receipt)
        verify(binding, result)
        return result
    except Exception as error:
        raise TransitionRejected(error, dict(stage=stage, source_init=completed, source_setup=reached, available=owners.available(ctx), inner_partial=getattr(error, 'partial', None), root_cause=dict(type=type(error).__name__, message=str(error)), automatic_retry=False)) from error

def verify(binding, parent):
    validate_binding(binding)
    if type(parent) is not SimPhase or parent.binding_identity != binding.identity or parent.identity != ions.digest(phase_record(parent)):
        raise ValueError('Changed actual INIT association or complete new SIM state')
    check_complete(parent.source_init)
    if parent.source_init.binding.identity != binding.expected_init_identity or parent.phase_binding.calendar.phase != 'SIM':
        raise ValueError('Foreign INIT parent or inferred phase profile')
    init.verify(parent.phase_binding, parent.active)
    if not catalog.equal_tree(parent.receipt['old_INIT_clock'], ions.data(parent.source_init.parent.clock)):
        raise ValueError('Changed original INIT clock association')
    if parent.active.cursor == 0:
        for actual, wanted in ((parent.active.rate_cache, parent.source_init.parent.rate_cache), (parent.active.nak_rate, parent.source_init.parent.nak_rate)):
            if not catalog.equal_tree(ions.data(actual), ions.data(wanted)):
                raise ValueError('Native phase entry must preserve actual rate attributes before a new producer call')

def advance(binding, parent, **kwargs):
    verify(binding, parent)
    try:
        active, detail = init.advance(parent.phase_binding, parent.active, **kwargs)
        result = phase(binding, parent.source_init, parent.phase_binding, active, parent.receipt)
        verify(binding, result)
        return (result, detail)
    except Exception as error:
        raise TransitionRejected(error, dict(stage='SIM_accepted_call', parent=parent, inner_partial=getattr(error, 'partial', None), automatic_retry=False)) from error

def pause(binding, parent):
    verify(binding, parent)
    return phase(binding, parent.source_init, parent.phase_binding, init.pause(parent.phase_binding, parent.active), parent.receipt)

def resume(binding, parent):
    verify(binding, parent)
    return phase(binding, parent.source_init, parent.phase_binding, init.resume(parent.phase_binding, parent.active), parent.receipt)
