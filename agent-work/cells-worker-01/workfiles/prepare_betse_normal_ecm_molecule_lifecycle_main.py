"""Generate the immutable complete-INIT to dual-owner SIM boundary; source only."""
# ruff: noqa: E501 -- Literal source/ownership contracts.

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PARENT = Path(
    "/mnt/workspaces/Cells/betse-normal-ecm-init-sim-transition-prepared-20261031-02/source"
)
PREFIX = "betse_normal_ecm_molecule_lifecycle"

MAIN = """
@dataclass(frozen=True)
class Binding:
    inputs:object
    expected_init_identity:str
    declaration:object
    identity:str

@dataclass(frozen=True)
class SimPhase:
    binding_identity:str
    source_init:CompleteInit
    phase_binding:object
    active:object
    receipt:object
    identity:str
    @property
    def cursor(self):
        return self.active.cursor

def binding_record(value):
    return LAW_ID,value.inputs,value.expected_init_identity,value.declaration.identity

def bind(inputs):
    original=ions.data(inputs)
    if set(original)!={'kind','case_id','provenance','expected_init_binding_identity',
                       'sim_phase','source_setup','config_equality_receipt'} or original['kind']!=INPUT_KIND:
        raise ValueError('Require the separately declared retained dual-owner lifecycle boundary')
    for key in ('case_id','provenance','expected_init_binding_identity'):
        if not isinstance(original[key],str) or not original[key].strip():
            raise ValueError('Require explicit lifecycle association '+key)
    declaration=init.bind(original['sim_phase'])
    if declaration.calendar.phase!='SIM' or declaration.calendar.step_count!=3:
        raise ValueError('The new SIM phase must retain its independent original three-call calendar')
    raw=setup.legacy_setup_inputs(original)
    validate_setup_inputs(raw)
    if raw['source_setup']['static_noise_level']!=0:
        raise ValueError('The first lifecycle binding keeps the supplied no-static-noise material seam')
    value=Binding(ions.freeze(original),original['expected_init_binding_identity'],declaration,'')
    return replace(value,identity=ions.digest(binding_record(value)))

def validate_binding(binding):
    if type(binding) is not Binding or binding.identity!=ions.digest(binding_record(binding)):
        raise ValueError('Changed complete dual-owner lifecycle declaration')

def check_stable_owner_scope(binding,completed):
    old=ions.data(completed.binding.inputs_raw['owners'])
    new=ions.data(binding.inputs['sim_phase']['owners'])
    for role in owners.ROLES:
        key='general network' if role=='molecules' else 'gene regulatory network settings'
        flag='implement network' if role=='molecules' else 'gene regulatory network simulated'
        if old['configuration'][key][flag] is not new['configuration'][key][flag]:
            raise ValueError('Native flag changes retain or construct owners; this first boundary does not normalize latent owner transitions')
        before=old['handlers'][role]
        after=ions.data(new['handlers'][role])
        fault=new['transport']['raw_setup_fault'] if role=='molecules' else None
        if fault is not None:
            index=int(fault[-1])
            after['network']['configuration']['transporters'][index]['max rate']=before['network']['configuration']['transporters'][index]['max rate']
        if not catalog.equal_tree(before['network']['configuration'],after['network']['configuration']):
            raise ValueError('Changed or latent-null owner configuration requires its own complete source correspondence')
        if before['network']['cold_publish'] is not after['network']['cold_publish']:
            raise ValueError('Balance-once publication changes require explicit saved-initial charge accounting')
        if not catalog.equal_tree(before['catalog'],after['catalog']):
            raise ValueError('This phase-aware packet retains declared gates and changes their native phase activation only')
    old_parameters=completed.binding.material_binding.geometry_binding.definition['parameters']
    new_parameters=binding.inputs['sim_phase']['field']['definition']['environment_geometry_definition']['parameters']
    if old_parameters['configured_temperature_K']!=new_parameters['configured_temperature_K']:
        raise ValueError('Retained core temperature must agree with this supplied no-intervention phase declaration')

def phase_record(value):
    return LAW_ID,value.binding_identity,value.source_init.identity,value.phase_binding.identity,value.active,value.receipt

def phase(binding,completed,phase_binding,active,receipt):
    value=SimPhase(binding.identity,completed,phase_binding,active,ions.freeze(receipt),'')
    return replace(value,identity=ions.digest(phase_record(value)))

def transition(binding,completed,*,observer=None,before_field=None):
    ctx=None
    reached=None
    stage='complete_INIT_admission'
    try:
        validate_binding(binding)
        check_complete(completed)
        check_owners(binding,completed)
        check_stable_owner_scope(binding,completed)
        raw=ions.data(binding.inputs)
        stage='actual_retained_dual_owner_SIM_setup'
        ctx,template,mechanical,reached=setup.prepare(completed.binding,completed.parent,raw,observer)
        stage='actual_SIM_phase_declaration'
        declaration=init.bind(template['_phase_input'])
        base=declaration.base
        event=reached['event_finalized']
        receipt=dict(source_phase='SIM',legacy_run_sim=True,setup_complete=True,
            event_finalization=dict(legacy_run_sim=True,event_fire_calls=0,dynamic_noise_calls=0,
                python_rng_after=event['python_rng_after'],source_fields=event),
            numpy_rng_after=template['event_inputs']['prepared_rng']['manifest'],
            entry_stores=init.setup.snapshot(ctx),source_setup=reached,
            entry_CaATP_present=completed.parent.rate_cache.present,
            entry_NaK_present=completed.parent.nak_rate.present,
            source_init_identity=completed.identity,old_INIT_clock=ions.data(completed.parent.clock),
            source_cold_recapture=False,physical_initializer_executed=False,
            native_load_or_pickle=False)
        current=init.Binding(declaration,base.material_binding,base.voltage_binding,base.inputs,
            declaration.inputs,base.calcium,declaration.inputs['catalog'],declaration.inputs['stop_after_calls'],
            declaration.calendar,declaration.mechanics,ions.freeze(receipt),'')
        current=replace(current,identity=ions.digest(init.binding_record(current)))
        cache=owners.cache(ctx)
        owners.validate_phase_cache(ctx,cache,0)
        initial=material.state(current.material_binding,catalog.material_values(ctx.sim),step_index=0)
        controls={key:catalog.clone(getattr(ctx.sim,key)) for key in ('gj_block','NaKATP_block')}
        net=network._state(current,initial,cache,controls)
        stage='SIM_bootstrap'
        ready,field=fields.reconstruct(current,net,current.calendar.dt_s,
            ions.data(current.inputs['bootstrap']['boundary_V']),'bootstrap',before_field)
        clock=init.Clock(ions.freeze(init.calendars.window(current.calendar).event_label_s),0,0.0)
        active=init.state(current,ready,field,completed.parent.rate_cache,completed.parent.nak_rate,
            mechanical,init.setup.snapshot(ctx),clock)
        init.verify(current,active)
        receipt['new_SIM_clock']=ions.data(clock)
        result=phase(binding,completed,current,active,receipt)
        verify(binding,result)
        return result
    except Exception as error:
        raise TransitionRejected(error,dict(stage=stage,source_init=completed,source_setup=reached,
            available=owners.available(ctx),inner_partial=getattr(error,'partial',None),
            root_cause=dict(type=type(error).__name__,message=str(error)),automatic_retry=False)) from error

def verify(binding,parent):
    validate_binding(binding)
    if type(parent) is not SimPhase or parent.binding_identity!=binding.identity or parent.identity!=ions.digest(phase_record(parent)):
        raise ValueError('Changed actual INIT association or complete new SIM state')
    check_complete(parent.source_init)
    if parent.source_init.binding.identity!=binding.expected_init_identity or parent.phase_binding.calendar.phase!='SIM':
        raise ValueError('Foreign INIT parent or inferred phase profile')
    init.verify(parent.phase_binding,parent.active)
    if not catalog.equal_tree(parent.receipt['old_INIT_clock'],ions.data(parent.source_init.parent.clock)):
        raise ValueError('Changed original INIT clock association')
    if parent.active.cursor==0:
        for actual,wanted in ((parent.active.rate_cache,parent.source_init.parent.rate_cache),
                              (parent.active.nak_rate,parent.source_init.parent.nak_rate)):
            if not catalog.equal_tree(ions.data(actual),ions.data(wanted)):
                raise ValueError('Native phase entry must preserve actual rate attributes before a new producer call')

def advance(binding,parent,**kwargs):
    verify(binding,parent)
    try:
        active,detail=init.advance(parent.phase_binding,parent.active,**kwargs)
        result=phase(binding,parent.source_init,parent.phase_binding,active,parent.receipt)
        verify(binding,result)
        return result,detail
    except Exception as error:
        raise TransitionRejected(error,dict(stage='SIM_accepted_call',parent=parent,
            inner_partial=getattr(error,'partial',None),automatic_retry=False)) from error

def pause(binding,parent):
    verify(binding,parent)
    return phase(binding,parent.source_init,parent.phase_binding,
                 init.pause(parent.phase_binding,parent.active),parent.receipt)

def resume(binding,parent):
    verify(binding,parent)
    return phase(binding,parent.source_init,parent.phase_binding,
                 init.resume(parent.phase_binding,parent.active),parent.receipt)
"""


def fn(tree, name):
    return copy.deepcopy(
        next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    )


def main():
    original = ast.parse(
        (PARENT / "src/cells/processes/betse_normal_ecm_init_sim_transition.py").read_text()
    )
    tree = ast.parse('''
"""Held supplied cold/INIT/retained dual-owner SIM lifecycle with active transporters.

Complete headless INIT is distinct from failed, paused or capped prefixes.
Every phase keeps its own source labels, material dt, caches and journal.
This new source proposal carries no scientific result or native persistence claim.
"""
from dataclasses import dataclass,replace
import numpy as np
from cells.processes import betse_ecm_grn_join as network
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_normal_ecm_catalog_join_source as catalog
from cells.processes import betse_normal_ecm_field_join as fields
from cells.processes import betse_normal_ecm_molecule_lifecycle_phase as init
from cells.processes import betse_normal_ecm_molecule_lifecycle_owners as owners
from cells.processes import betse_normal_ecm_molecule_lifecycle_setup as setup
from cells.processes import betse_normal_ion_join as ions
LAW_ID='betse_supplied_ECM_general_transport_INIT_to_SIM_v1_5_0@1'
INPUT_KIND='cells.normal_ecm_molecule_lifecycle_inputs@1'
''')
    names = {
        "CompleteInit",
        "FailedInitPrefix",
        "TransitionRejected",
        "complete_record",
        "prepare_complete",
        "prepare_failed_prefix",
        "check_complete",
    }
    tree.body.extend(
        copy.deepcopy(n)
        for n in original.body
        if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names
    )
    oldbind = fn(original, "bind")
    start = next(
        i
        for i, n in enumerate(oldbind.body)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "cfg"
    )
    stop = next(
        i
        for i, n in enumerate(oldbind.body)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "packet"
    )
    validate = ast.parse("def validate_setup_inputs(raw):\n    pass").body[0]
    validate.body = oldbind.body[start:stop]
    tree.body.append(validate)
    check = fn(original, "check_owners")
    check.body[0] = ast.parse("raw=setup.legacy_setup_inputs(binding.inputs)").body[0]
    tree.body.append(check)
    tree.body += ast.parse(MAIN).body
    path = ROOT / "src/cells/processes" / (PREFIX + ".py")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "# ruff: noqa: E501\n" + ast.unparse(ast.fix_missing_locations(tree)) + "\n"
    compile(text, str(path), "exec")
    with path.open("x") as stream:
        stream.write(text)
    print(str(path))


if __name__ == "__main__":
    main()
