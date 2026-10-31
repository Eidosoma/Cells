"""Generate new owned source files from explicit frozen parents; no science import."""
# ruff: noqa: E501 -- Literal generated source and provenance strings.

import ast
import copy
import hashlib
from pathlib import Path

ROOT = Path("/home/robert/Cells")
BASE = Path("/mnt/workspaces/Cells")
PARENT = BASE / "betse-normal-ecm-molecule-dispatch-prepared-20261031-01/source"
TRANSPORTER = BASE / "betse-normal-transporter-prepared-20261030-03/source"
OLD = "betse_normal_ecm_molecule_dispatch"
NEW = "betse_normal_ecm_molecule_transport"
PROCESS = "src/cells/processes/"


def function(tree, name):
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def write(name, tree):
    path = ROOT / PROCESS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        "# ruff: noqa: E501, F841, B007, B905\n"
        + ast.unparse(ast.fix_missing_locations(tree))
        + "\n"
    )
    compile(text, str(path), "exec")
    with path.open("x") as stream:
        stream.write(text)
    print(str(path))


SOURCE_ADDITIONS = """
def transporter_fields(net):
    return {} if net is None else {
        name: qualified.public(obj) for name, obj in net.transporters.items()
    }

def wire(owner, sim):
    core = getattr(owner, 'core', None) if owner is not None else None
    aliases = {'cell_concs','mem_concs','env_concs','bound_concs','mit_concs'}
    objects = {'molecules','reactions','reactions_env','reactions_mit','modulators',
               'channels','mit','molecule_frames','mover_frames','rhs',
               'transporters','transporter_frames'}
    return dict(
        owner_fields={} if owner is None else qualified.public(owner, {'core'}),
        core_fields={} if core is None else qualified.public(core, aliases | objects),
        molecule_fields={} if core is None else {k:qualified.public(v) for k,v in core.molecules.items()},
        reaction_fields={} if core is None else {k:qualified.public(v) for k,v in core.reactions.items()},
        modulator_fields={} if core is None else {k:qualified.public(v) for k,v in core.modulators.items()},
        channel_fields={} if core is None else channel_fields(core),
        transporter_fields=transporter_fields(core),
        ion_boundary_state=clone(sim.c_env_bound),
        simulator_fields={k:clone(getattr(sim,k)) for k in (
            'extra_rho_cells','extra_rho_env','extra_J_mem','extra_Jenv_x','extra_Jenv_y'
        ) if hasattr(sim,k)},
    )

def validate_cached_transporters(ctx, incoming):
    config = ctx.definition['configuration'].get('transporters')
    expected = [r['name'] for r in config or []]
    fields = incoming['wire']['transporter_fields']
    initial = incoming['initial_transporter_fields']
    if list(fields) != expected or list(initial) != expected:
        raise ValueError('Require every ordered general-owner transporter and initial metadata')
    if incoming['wire']['owner_fields'].get('transporters') is not (config is not None):
        raise ValueError('Changed native general-owner transporter dispatch flag')
    for name in expected:
        current, origin = fields[name], initial[name]
        if set(current) != set(origin) or 'flux' not in current or origin['flux'] is not None:
            raise ValueError('Require complete original transporter fields and literal cold flux None')
        for key in origin.keys() - {'flux'}:
            if not qualified.equal_tree(current[key], origin[key]):
                raise ValueError('Changed source-generated transporter equations or targeting metadata')
        flux = current['flux']
        if flux is not None:
            a = np.asarray(flux)
            if a.shape != (len(ctx.cells.mem_i),) or a.dtype != np.float64 or not np.isfinite(a).all():
                raise ValueError('Require a complete finite signed transporter flux cache')

def transporter_before(ctx, material_declaration):
    sim,cells,p,net = ctx.sim,ctx.cells,ctx.p,ctx.net
    return dict(
        mode='transporters', conditioned_before_model_transporters=True,
        definition=dict(transporters=clone(p.network_config.get('transporters')),
                        biomolecules=clone(p.network_config['biomolecules'])),
        material_declaration=clone(material_declaration),
        ion_ids=list(ctx.ion_ids), valence=clone(sim.zs),
        values_before=material_values(sim),
        concentrations_before={zone:{name:clone(mapping[name]) for name in mapping}
            for zone,mapping in ((a,getattr(net,a)) for a in ('cell_concs','mem_concs','env_concs'))},
        fluxes_before={name:clone(obj.flux) for name,obj in net.transporters.items()},
        metadata={name:qualified.public(obj) for name,obj in net.transporters.items()},
        geometry=dict(owner=clone(cells.mem_to_cells),membrane_area_m2=clone(cells.mem_sa),
                      cell_volume_m3=clone(cells.cell_vol),membrane_volume_m3=clone(cells.mem_vol)),
        rho_pump=clone(np.broadcast_to(sim.rho_pump,(sim.mdl,))),
        runtime_temperature_K=sim.T,F=p.F,R=p.R,dt_s=p.dt,
        extra_current_before_A_m2=clone(net.extra_J_mem),
        cache_before=cache_general(ctx),
        source_completed=False, independently_carried_trajectory=False,
    )

def attach_transporters(ctx):
    net=ctx.net
    def observe(stage,name,term,delta,actual):
        ctx.trace.setdefault('transporter_frames',[]).append(dict(
            stage=stage,name=name,term=term,delta=clone(delta),
            concentrations={zone:{s:clone(values[s]) for s in values}
                for zone,values in ((a,getattr(net,a)) for a in ('cell_concs','mem_concs','env_concs'))},
            fluxes={n:clone(o.flux) for n,o in net.transporters.items()},
            extra_current_A_m2=clone(net.extra_J_mem),
            values=material_values(actual), cache=cache_general(ctx),
        ))
    net._observe_transporter=observe
"""

DISPATCHED = """
def dispatched(stage, actual, phase):
    ctx.trace['dispatch_stages'].append(stage)
    if stage == 'clear_run_loop' and ctx.sim.molecules.transporters:
        ctx.trace['before_transporters']=transporter_before(ctx,material_declaration)
        if transporter_observer is not None:
            transporter_observer(clone(ctx.trace['before_transporters']))
    ready = stage == 'run_loop_transporters' or (
        stage == 'clear_run_loop' and not ctx.sim.molecules.transporters
    )
    if ready:
        ctx.trace['before_channels']=before_general(ctx,material_declaration)
        ctx.trace['before_channels'].update(mode='channels',catalog=clone(ctx.catalog))
        if channel_observer is not None:
            channel_observer(clone(ctx.trace['before_channels']))
    if stage == 'run_loop_channels' or (ready and not ctx.sim.molecules.channels):
        ctx.trace['before']=before_general(ctx,material_declaration)
        if observer is not None:
            observer(clone(ctx.trace['before']))
"""

BIND = """
def bind(inputs):
    raw=ions.data(inputs)
    if not isinstance(raw,dict) or raw.get('kind') != INPUT_KIND or 'transport' not in raw:
        raise ValueError('Require the separate complete ECM general-transporter declaration')
    lower=qualified.clone(raw)
    transport=lower.pop('transport')
    lower['kind']=prior.INPUT_KIND
    if raw['configuration']['general network'] is None:
        raise NativeConfigurationObstructed('Absent general network leaves molecules_enabled unwritten')
    general=raw['handlers']['molecules']['network']['configuration']
    lower['handlers']['molecules']['network']['configuration'].pop('transporters',None)
    lower['configuration']['general network'].pop('transporters',None)
    base=prior.bind(lower)
    expected=dict(general,channels=raw['handlers']['molecules']['catalog']['populations'],
                  **{'implement network':raw['configuration']['general network']['implement network']})
    if not qualified.equal_tree(raw['configuration']['general network'],expected):
        raise ValueError('Native general configuration and configured transporter owner differ')
    if not isinstance(transport,dict) or set(transport) != {'membrane_volume_m3','raw_setup_fault'}:
        raise ValueError('Require explicit native membrane wedge volumes and raw-fault declaration')
    external=base.component.inputs['definition']['environment_geometry_definition']
    cg=external['current_definition']['geometry']
    area=np.asarray(cg['membrane_area_m2'],np.float64)
    owner=np.asarray(cg['owner'],np.int64)
    mids=np.asarray(external['geometry']['membrane_midpoints_m'],np.float64)
    centres=np.asarray(external['geometry']['cell_centres_m'],np.float64)
    rads=mids-centres[owner]
    radius=np.sqrt(rads[:,0]**2+rads[:,1]**2)
    volume=np.asarray(transport['membrane_volume_m3'],np.float64)
    if (volume.shape != area.shape or not np.isfinite(volume).all() or np.any(volume <= 0)
        or not np.array_equal(volume,0.5*radius*area)):
        raise ValueError('Require source mem_vol=0.5*R_rads*mem_sa on the actual supplied geometry')
    rows=general.get('transporters')
    if rows is not None and (not isinstance(rows,list) or len(rows)>3):
        raise ValueError('Require at most three ordered native general-owner transporters')
    fault=transport['raw_setup_fault']
    if fault not in (None,'missing_max_rate_0','missing_max_rate_1'):
        raise ValueError('Unknown separately declared raw transporter setup fault')
    admitted=qualified.clone(rows or [])
    if fault is not None:
        index=int(fault[-1])
        if (not raw['configuration']['general network']['implement network']
            or index>=len(admitted) or 'max rate' in admitted[index]):
            raise ValueError('Raw setup fault must be the literal absent max rate in an enabled owner')
        # Validation-only structural witness; the runtime/native configuration stays missing.
        admitted[index]['max rate']=1e-9
    for row in admitted:
        if row.get('apply to') != 'all' or row.get('ignore ECM') is not False:
            raise ValueError('First ECM transporter seam requires all targets and the declared stored ignore flag False')
        if row.get('standard free energy') != 'None' and not (
            type(row.get('standard free energy')) in (int,float)
            and np.isfinite(row['standard free energy'])
        ):
            raise ValueError("Native standard energy must be finite or literal 'None'")
    if admitted:
        ids=tuple(external['current_definition']['ions']['ids'])
        products=general['biomolecules']
        species=ids+tuple(row['name'] for row in products)
        zs=tuple(external['current_definition']['ions']['valence'])+tuple(row['z'] for row in products)
        transport_component.bind(
            admitted,species,transporter_source.integer_valences(zs),
            [0]*len(admitted),[1]*len(admitted),[True,True],
            area_m2=[1.0]*len(admitted),
            temperature_K=external['parameters']['configured_temperature_K'],
        )
    value=Binding(base.component,ions.freeze(raw),'')
    return replace(value,identity=ions.digest(binding_record(value)))
"""

RUNTIME_ADDITIONS = """
def validate_transport_cache(binding,parent):
    if parent.owners['shared'].get('rho_pump') != 1:
        raise ValueError('Ordinary source rho_pump remains the identity scalar')
    saved=parent.owners['handlers']['molecules']
    if saved is None:
        return
    view=SimpleNamespace(
        definition=ions.data(binding.inputs['handlers']['molecules']['network']),
        cells=SimpleNamespace(mem_i=np.arange(len(parent.material.values.voltage_V))),
    )
    source.validate_cached_transporters(view,saved['cache'])
    for fields in saved['cache']['wire']['transporter_fields'].values():
        if (fields['flux'] is not None) is not (parent.cursor>0):
            raise ValueError('Transporter flux presence differs from the actual cold/warm epoch')
"""


def main():
    assert hashlib.sha256((PARENT.parent / "MANIFEST.json").read_bytes()).hexdigest() == (
        "e51f7eead8d6bfe3a0e4f669005386e6f4271632f0531084754320025b1ed922"
    )
    source = ast.parse((PARENT / PROCESS / (OLD + "_source.py")).read_text())
    source.body[1:1] = ast.parse("""
import numpy as np
from types import SimpleNamespace
""").body
    source.body += ast.parse("""
tex_val=str
BetseSimConfException=ValueError
stb=SimpleNamespace(div_env=qualified.base.div_env)
""").body
    source.body = [
        n
        for n in source.body
        if not (
            isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Name)
            and n.targets[0].id in {"MasterOfNetworks", "wire"}
        )
    ]
    old_transport = ast.parse(
        (TRANSPORTER / PROCESS / "betse_normal_transporter_source.py").read_text()
    )
    cls = copy.deepcopy(
        next(
            n for n in old_transport.body if isinstance(n, ast.ClassDef) and n.name == "Transporter"
        )
    )
    net = next(
        n for n in old_transport.body if isinstance(n, ast.ClassDef) and n.name == "_Network"
    )
    methods = [
        copy.deepcopy(n)
        for n in net.body
        if isinstance(n, ast.FunctionDef)
        and n.name in {"read_transporters", "write_transporters", "run_loop_transporters"}
    ]
    newnet = ast.ClassDef(
        name="MasterOfNetworks",
        bases=[ast.parse("qualified.MasterOfNetworks", mode="eval").body],
        keywords=[],
        body=methods,
        decorator_list=[],
    )
    source.body.extend([cls, newnet])
    # The late class definition replaces only this new module's alias.
    science = function(source, "science_general")
    science.body = ast.parse(
        "return dict(qualified.science(),MasterOfGenes=MasterOfMolecules,MasterOfNetworks=MasterOfNetworks,Transporter=Transporter)"
    ).body
    cached = function(source, "cache_general")
    cached.body[0].value.keywords.append(
        ast.keyword(
            arg="initial_transporter_fields",
            value=ast.parse("clone(ctx.initial_transporter_fields)", mode="eval").body,
        )
    )
    restored = function(source, "restore_general")
    # Extend the exact local cache schema; no temporary deletion/reset of actual buffers.
    for n in ast.walk(restored):
        if isinstance(n, ast.Set) and {x.value for x in n.elts if isinstance(x, ast.Constant)} == {
            "owner_fields",
            "core_fields",
            "molecule_fields",
            "reaction_fields",
            "modulator_fields",
            "ion_boundary_state",
            "simulator_fields",
            "channel_fields",
        }:
            n.elts.append(ast.Constant("transporter_fields"))
    pos = next(
        i
        for i, n in enumerate(restored.body)
        if isinstance(n, ast.Expr)
        and isinstance(n.value, ast.Call)
        and ast.unparse(n.value.func) == "validate_cached_channels"
    )
    restored.body[pos:pos] = ast.parse("""
validate_cached_transporters(ctx,incoming)
ctx.initial_transporter_fields=clone(incoming['initial_transporter_fields'])
""").body
    pos = next(i for i, n in enumerate(restored.body) if isinstance(n, ast.Return))
    restored.body[pos:pos] = ast.parse("""
net.transporters=OrderedDict()
for name,fields in raw['transporter_fields'].items():
    obj=object.__new__(api['Transporter'])
    vars(obj).update(clone(fields))
    net.transporters[name]=obj
""").body
    attach = function(source, "attach_general")
    attach.args.args.append(ast.arg(arg="transporter_observer"))
    attach.args.defaults.append(ast.Constant(None))
    attach.body.insert(1, ast.parse("attach_transporters(ctx)").body[0])
    for i, n in enumerate(attach.body):
        if isinstance(n, ast.FunctionDef) and n.name == "dispatched":
            attach.body[i] = ast.parse(DISPATCHED).body[0]
    source.body += ast.parse(SOURCE_ADDITIONS).body
    write(NEW + "_source.py", source)

    tree = ast.parse((PARENT / PROCESS / (OLD + ".py")).read_text().replace(OLD, NEW))
    tree.body[1:1] = ast.parse("""
from cells.processes import betse_normal_ecm_molecule_dispatch as prior
from cells.processes import betse_network_transport as transport_component
from cells.processes import betse_normal_transporter_source as transporter_source
""").body
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
            if n.targets[0].id == "LAW_ID":
                n.value = ast.Constant(
                    "betse_supplied_FULL_ECM_general_transport_then_GRN_v1_5_0@1"
                )
            if n.targets[0].id == "INPUT_KIND":
                n.value = ast.Constant("cells.normal_ecm_general_molecule_transport_inputs@1")
    tree.body = [
        ast.parse(BIND).body[0] if isinstance(n, ast.FunctionDef) and n.name == "bind" else n
        for n in tree.body
    ]
    function(tree, "verify").body.extend(
        ast.parse("runtime.validate_transport_cache(binding,parent)").body
    )
    write(NEW + ".py", tree)

    rt = ast.parse((PARENT / PROCESS / (OLD + "_runtime.py")).read_text().replace(OLD, NEW))
    for n in rt.body:
        if (
            isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Name)
            and n.targets[0].id == "SHARED"
        ):
            n.value.elts.append(ast.Constant("rho_pump"))
    make = function(rt, "make_context")
    pos = next(i for i, n in enumerate(make.body) if isinstance(n, ast.Return))
    make.body[pos:pos] = ast.parse("""
ctx.cells.mem_vol=np.asarray(raw['transport']['membrane_volume_m3'],np.float64).copy()
for view in ctx.views.values():
    view.initial_transporter_fields={}
""").body
    initialize = function(rt, "initialize")
    hook = next(n for n in initialize.body if isinstance(n, ast.FunctionDef) and n.name == "hook")
    branch = next(n for n in hook.body if isinstance(n, ast.If))
    branch.orelse[2:2] = ast.parse("""
if role == 'molecules':
    view.initial_transporter_fields=source.transporter_fields(view.net)
""").body
    dispatch = function(rt, "dispatch")
    hook = next(n for n in dispatch.body if isinstance(n, ast.FunctionDef) and n.name == "hook")
    # Add independent pre-transporter notification alongside the existing channel/network notifications.
    branch = next(n for n in hook.body if isinstance(n, ast.If))
    branch.body.insert(
        2,
        ast.parse("""
def before_transporters(value):
    if observer is not None:
        observer(role,'transporters',ions.freeze(value))
""").body[0],
    )
    for n in ast.walk(hook):
        if isinstance(n, ast.Call) and ast.unparse(n.func) == "source.attach_general":
            n.args.append(ast.Name(id="before_transporters", ctx=ast.Load()))
    rt.body += ast.parse(RUNTIME_ADDITIONS).body
    write(NEW + "_runtime.py", rt)


if __name__ == "__main__":
    main()
