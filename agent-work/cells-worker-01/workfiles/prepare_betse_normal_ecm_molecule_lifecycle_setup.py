"""Prepare real retained dual-owner SIM setup using frozen transition bodies."""
# ruff: noqa: E501 -- Literal metadata/ownership adapters; no science is evaluated.

import ast
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PARENT = Path(
    "/mnt/workspaces/Cells/betse-normal-ecm-init-sim-transition-prepared-20261031-02/source"
)
PREFIX = "betse_normal_ecm_molecule_lifecycle"

HELPERS = """
def legacy_setup_inputs(raw):
    result=ions.data(raw)
    current=ions.data(raw['sim_phase'])
    setup=current['setup']
    event_owner=dict(global_options=setup['global_options'],scheduled_options=setup['scheduled_options'],
        handler_fields={},callbacks={},
        tissue_target_inds=setup['maps']['tissue_target_inds'],
        cell_target_inds=setup['maps']['cell_target_inds'],env_target_inds=setup['maps']['env_target_inds'])
    result['flags']=current['flags']
    result['time_profile']=current['time_profile']
    result['sim_composition_template']=dict(
        event_inputs=dict(field=current['field'],calcium=current['calcium'],catalog=current['catalog'],event_owner=event_owner),
        mechanics_definition=current['mechanics_definition'],mechanics_initial=current['mechanics_initial'])
    result['_phase_input']=current
    return result

def available(ctx):
    return owners.available(ctx)

def encoded(value):
    if isinstance(value,(np.ndarray,np.generic)):
        a=np.asarray(value)
        return dict(__native_buffer__=a.tolist(),dtype=a.dtype.str,shape=list(a.shape))
    if isinstance(value,dict) or hasattr(value,'items'):
        return {k:encoded(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):
        return [encoded(v) for v in value]
    return value

def reinitialize_owners(ctx,init_binding,init_parent,new_raw,observe):
    actual={}
    old_raw=ions.data(init_binding.inputs_raw['owners'])
    old_cache=ions.data(init_parent.network.network_cache)
    for role in owners.ROLES:
        obj=getattr(ctx.sim,role,None)
        actual[role]=None if obj is None else dict(owner=obj,core=obj.core,
            molecules=dict(obj.core.molecules),channels=dict(obj.core.channels),
            transporters=dict(obj.core.transporters))
    # The raw native configuration changes, while actual old objects remain.
    dyna=ctx.phase.dyna
    for role in owners.ROLES:
        view=ctx.views[role]
        view.definition=ions.data(new_raw['handlers'][role]['network'])
        catalog.configure(view,ions.data(new_raw['handlers'][role]['catalog']))
    ctx.phase.dyna=ctx.sim.dyna=dyna
    ctx.raw=ions.data(new_raw)
    ctx.p.network_config=ions.data(new_raw['configuration']['general network'])
    ctx.p.grn=SimpleNamespace(conf=catalog.clone(ctx.views['grn'].definition['configuration']))
    ctx.p.molecules_enabled=ctx.enabled['molecules']
    ctx.p.grn_enabled=ctx.enabled['grn']
    owners.phase(ctx,'SIM')

    def hook(role,stage,value):
        if role=='all':
            # Current numeric buffers plus actual old configuration/cache, never a cold recapture.
            inputs=owners.conditional_input(ctx,'reinitialize')
            inputs['incoming_owners']=encoded(old_cache)
            inputs['old_raw']=old_raw
            inputs['mode']='reinitialize'
            inputs['source_cold_recapture']=False
            observe('before_dual_reinitialize',inputs)
        else:
            observe('owner_'+role+'_'+stage,value)
    owners.initialize(ctx,hook)
    identity={}
    for role in owners.ROLES:
        old=actual[role]
        obj=getattr(ctx.sim,role,None)
        if not ctx.enabled[role]:
            if old is not None or obj is not None:
                raise ValueError('Disabled latent owner is preserved by native source but outside this first lifecycle representation')
            identity[role]=dict(enabled=False,owner_absent=True)
            continue
        identity[role]=dict(enabled=True,owner_retained=obj is old['owner'],core_retained=obj.core is old['core'],
            molecule_objects_retained={k:obj.core.molecules.get(k) is v for k,v in old['molecules'].items()},
            channel_objects_rebuilt={k:v is not old['channels'].get(k) for k,v in obj.core.channels.items()},
            transporter_objects_rebuilt={k:v is not old['transporters'].get(k) for k,v in obj.core.transporters.items()},
            transporter_fluxes_after={k:catalog.clone(v.flux) for k,v in obj.core.transporters.items()},
            read_substances_called=False,fresh_cold_owner_created=False)
        cfg=ctx.views[role].definition['configuration']
        for key in ('transporters','channels','modulators','reactions'):
            configuration=ctx.views[role].catalog['populations'] if key=='channels' else cfg.get(key)
            if configuration is None and getattr(obj.core,key):
                raise ValueError('Native null configuration retains latent '+role+'/'+key+'; complete actual buffers are retained, not normalized')
    observe('dual_owners_reinitialized',dict(available=available(ctx),owner_identity=identity,
        carried_gate_voltage_V=ctx.sim.vm.copy(),source_cold_recapture=False))
    return identity

def conditional_sim_input(ctx,template,raw):
    return dict(kind='cells.actual_dual_owner_SIM_phase_entry@1',
        owners=owners.conditional_input(ctx,'entry'),phase_input=ions.data(template['_phase_input']),
        setup_fields=ions.data(template),source_phase='SIM',legacy_run_sim=True,
        source_cold_recapture=False,native_load_or_pickle=False)

def phase_input_after_setup(ctx,template,raw,mechanical_initial):
    result=ions.data(raw['_phase_input'])
    field=ions.data(template['event_inputs']['field'])
    result['field']=field
    result['catalog']=ions.data(template['event_inputs']['catalog'])
    result['mechanics_initial']=ions.data(mechanical_initial)
    result['owners']['field']=ions.data(field)
    result['owners']['calcium']=ions.data(result['calcium'])
    for role in owners.ROLES:
        definition=result['owners']['handlers'][role]['network']
        definition['initial_controls']=ions.data(field['network']['initial_controls'])
        definition['initial_ion_boundary']=ions.data(field['network']['initial_ion_boundary'])
    result['owners']['handlers']['grn']['network']=ions.data(field['network'])
    ctx.raw=ions.data(result['owners'])
    for role in owners.ROLES:
        ctx.views[role].definition=ions.data(ctx.raw['handlers'][role]['network'])
    return result
"""


def function(tree, name):
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def main():
    tree = ast.parse(
        (PARENT / "src/cells/processes/betse_normal_ecm_init_sim_transition_setup.py")
        .read_text()
        .replace("betse_normal_ecm_init_sim_transition_source", PREFIX + "_source")
    )
    tree.body[1:1] = ast.parse(
        "from cells.processes import betse_normal_ecm_molecule_lifecycle_owners as owners"
    ).body
    tree.body = [
        n
        for n in tree.body
        if not (
            isinstance(n, ast.FunctionDef)
            and n.name in ("available", "conditional_reinitialize_input", "conditional_sim_input")
        )
        and not (
            isinstance(n, ast.ImportFrom) and any(a.name == "betse_ecm_grn_join" for a in n.names)
        )
    ]
    prepare = function(tree, "prepare")
    prepare.body.insert(1, ast.parse("raw=legacy_setup_inputs(raw)").body[0])
    block = next(n for n in prepare.body if isinstance(n, ast.Try)).body
    block[1:7] = ast.parse("""
ctx=owners.make_context(temporary,ions.data(init_binding.inputs_raw['owners']),
    [np.array(v,copy=True) for v in init_parent.network.material.values],phase_kind='INIT')
owners.restore(ctx,ions.data(init_parent.network.network_cache))
""").body
    block[:] = [
        n
        for n in block
        if not (
            isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Call)
            and ast.unparse(n.value.func) == "catalog.configure"
        )
    ]
    for n in block:
        if not isinstance(n, ast.Assign):
            continue
        target = ast.unparse(n.targets[0])
        if target == "p.molecules_enabled":
            n.value = ast.parse("ctx.enabled['molecules']", mode="eval").body
        elif target == "p.grn_enabled":
            n.value = ast.parse("ctx.enabled['grn']", mode="eval").body
    start = next(
        i
        for i, n in enumerate(block)
        if isinstance(n, ast.Assign)
        and ast.unparse(n.targets[0]) == "stage"
        and isinstance(n.value, ast.Constant)
        and n.value.value == "retained_GRN_reinitialize"
    )
    stop = next(
        i
        for i, n in enumerate(block)
        if isinstance(n, ast.Assign)
        and ast.unparse(n.targets[0]) == "stage"
        and isinstance(n.value, ast.Constant)
        and n.value.value == "SIM_mechanics_entry"
    )
    block[start:stop] = ast.parse("""
stage='retained_general_then_GRN_reinitialize'
identity=reinitialize_owners(ctx,init_binding,init_parent,raw['_phase_input']['owners'],observe)
""").body

    class Reset(ast.NodeTransformer):
        def visit_Call(self, node):
            if ast.unparse(node.func) == "source.clear_storage":
                return ast.parse("owners.reset_storage(ctx)", mode="eval").body
            return self.generic_visit(node)

    Reset().visit(prepare)
    index = next(
        i
        for i, n in enumerate(block)
        if isinstance(n, ast.Expr)
        and isinstance(n.value, ast.Call)
        and ast.unparse(n.value.func) == "observe"
        and n.value.args
        and isinstance(n.value.args[0], ast.Constant)
        and n.value.args[0].value == "entry_declaration"
    )
    block[index:index] = ast.parse("""
template['_phase_input']=phase_input_after_setup(ctx,template,raw,initial_mechanics)
""").body
    tree.body += ast.parse(HELPERS).body
    path = ROOT / "src/cells/processes" / (PREFIX + "_setup.py")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "# ruff: noqa: E501\n" + ast.unparse(ast.fix_missing_locations(tree)) + "\n"
    compile(text, str(path), "exec")
    with path.open("x") as stream:
        stream.write(text)
    print(str(path))


if __name__ == "__main__":
    main()
