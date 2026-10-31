"""Generate phase-aware private owner plumbing from explicit frozen source."""
# ruff: noqa: E501 -- Literal source fragments and phase-contract diagnostics.

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
BASE = Path("/mnt/workspaces/Cells")
TRANSPORT = BASE / "betse-normal-ecm-molecule-transport-prepared-20261031-01/source"
TRANSITION = BASE / "betse-normal-ecm-init-sim-transition-prepared-20261031-02/source"
PREFIX = "betse_normal_ecm_molecule_lifecycle"
OLD = "betse_normal_ecm_molecule_transport"


def fn(tree, name):
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def write(name, tree):
    path = ROOT / "src/cells/processes" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        "# ruff: noqa: E501, E731, F841, B007, B905\n"
        + ast.unparse(ast.fix_missing_locations(tree))
        + "\n"
    )
    compile(text, str(path), "exec")
    with path.open("x") as stream:
        stream.write(text)
    print(str(path))


VALIDATE = """
def validate_phase_cache(ctx,saved,call_index,*,pre_late=False):
    if saved['source_phase']!=ctx.phase.kind or saved['legacy_run_sim'] is not (ctx.phase.kind=='SIM'):
        raise ValueError('Owner phase and legacy flags differ from their actual cache epoch')
    expected_absent={'rho_pump','rho_channel'} if pre_late else set()
    if set(saved['shared_absent'])!=expected_absent or set(saved['shared'])!=set(SHARED)-expected_absent:
        raise ValueError('Shared attribute presence differs from the actual phase setup stage')
    if not pre_late and saved['shared'].get('rho_pump')!=1:
        raise ValueError('Native ordinary pump weight remains the scalar identity')
    for role in ROLES:
        record=saved['handlers'][role]
        if not ctx.enabled[role]:
            if record is not None:
                raise ValueError('Latent disabled owner requires an explicit qualified phase boundary')
            continue
        if record is None or record['role']!=role or record['configuration_identity']!=owner_identity(ctx.views[role],role):
            raise ValueError('Require each unchanged actual phase owner and declaration')
        view=ctx.views[role]
        incoming=record['cache']
        qualified.validate_cached_channels(view,incoming)
        for row in view.catalog['populations'] or []:
            name=row['name']
            active=ctx.phase.kind=='SIM' or row.get('init active',True)
            expected=call_index if active else 0
            if incoming['channel_calls'][name]!=expected:
                raise ValueError('Gate call count differs from its actual phase and init-active flag')
            if not active and not qualified.equal_tree(incoming['wire']['channel_fields'][name],incoming['initial_channel_fields'][name]):
                raise ValueError('INIT-inactive gate must retain its complete original cold state')
        if role=='molecules':
            source.validate_cached_transporters(view,incoming)
            for fields in incoming['wire']['transporter_fields'].values():
                if (fields['flux'] is not None) is not (call_index>0):
                    raise ValueError('Rebuilt transporter flux epoch differs from the actual phase cursor')

def phase(ctx,kind):
    if kind not in ('INIT','SIM'):
        raise ValueError('Only explicit native INIT/SIM owner phases are supported')
    ctx.phase.kind='INIT' if kind=='INIT' else 'SIM'
    ctx.p._run_sim=kind=='SIM'
    return ctx

def reset_storage(ctx):
    # Literal native clear_storage and clear_cache bodies; no display or persistence call.
    source.clear_storage(ctx.sim,ctx.cells,ctx.p)
    for role in ROLES:
        if not ctx.enabled[role]:
            continue
        view=ctx.views[role]
        view.net=getattr(ctx.sim,role).core
        view.initial_channel_fields=qualified.channel_fields(view.net)
        view.channel_calls={name:0 for name in view.net.channels}
        if role=='molecules':
            view.initial_transporter_fields=source.transporter_fields(view.net)
    return cache(ctx)
"""


def main():
    product = ast.parse((TRANSPORT / "src/cells/processes" / (OLD + "_source.py")).read_text())
    transition = ast.parse(
        (
            TRANSITION / "src/cells/processes/betse_normal_ecm_init_sim_transition_source.py"
        ).read_text()
    )
    network = next(
        n for n in product.body if isinstance(n, ast.ClassDef) and n.name == "MasterOfNetworks"
    )
    network.body.append(copy.deepcopy(fn(transition, "clear_cache")))
    product.body.append(copy.deepcopy(fn(transition, "clear_cache")))
    product.body.append(copy.deepcopy(fn(transition, "clear_storage")))
    product.body[1:1] = ast.parse(
        "from cells.processes import betse_environment_field as environment"
    ).body
    product.body += ast.parse("gaussian_filter=environment.gaussian_filter\nEndoRetic=None").body
    for name in (
        "init_profiles",
        "initDenv",
        "_finalize_events_global",
        "_finalize_events_tissue",
        "f_sweep",
        "static_and_blocks",
        "screening_conductivity",
    ):
        product.body.append(copy.deepcopy(fn(transition, name)))
    product.body += ast.parse("mod=SimpleNamespace(f_sweep=f_sweep)").body
    write(PREFIX + "_source.py", product)

    runtime = ast.parse(
        (TRANSPORT / "src/cells/processes" / (OLD + "_runtime.py"))
        .read_text()
        .replace(OLD + "_source", PREFIX + "_source")
    )
    runtime.body = [
        n
        for n in runtime.body
        if not (isinstance(n, ast.FunctionDef) and n.name == "validate_transport_cache")
    ]
    make = fn(runtime, "make_context")
    make.args.kwonlyargs.append(ast.arg(arg="phase_kind"))
    make.args.kw_defaults.append(None)
    for n in ast.walk(make):
        if not isinstance(n, ast.Assign):
            continue
        if ast.unparse(n.targets[0]) == "ctx.phase.kind":
            n.value = ast.parse("'INIT' if phase_kind=='INIT' else 'SIM'", mode="eval").body
        if ast.unparse(n.targets[0]) == "ctx.p._run_sim":
            n.value = ast.parse("phase_kind=='SIM'", mode="eval").body
    make.body.insert(
        0,
        ast.parse(
            "if phase_kind not in ('INIT','SIM'):\n    raise ValueError('Require an explicit source phase before owner construction')"
        ).body[0],
    )
    cached = fn(runtime, "cache")
    cached.body[0].value = ast.parse(
        "{key:qualified.clone(getattr(ctx.sim,key)) for key in SHARED if hasattr(ctx.sim,key)}",
        mode="eval",
    ).body
    cached.body[1].value.keywords.extend(
        [
            ast.keyword(arg="source_phase", value=ast.parse("ctx.phase.kind", mode="eval").body),
            ast.keyword(arg="legacy_run_sim", value=ast.parse("ctx.p._run_sim", mode="eval").body),
        ]
    )
    cached.body[1].value.keywords.insert(
        4,
        ast.keyword(
            arg="shared_absent",
            value=ast.parse(
                "[key for key in SHARED if not hasattr(ctx.sim,key)]", mode="eval"
            ).body,
        ),
    )
    restore = fn(runtime, "restore")
    restore.body[0:0] = ast.parse("""
if saved['source_phase']!=ctx.phase.kind or saved['legacy_run_sim'] is not ctx.p._run_sim:
    raise ValueError('Restore requires the actual original owner phase, not an inferred rebase')
""").body
    dispatch = fn(runtime, "dispatch")
    dispatch.body = [
        n
        for n in dispatch.body
        if not (isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "ctx.phase.kind")
    ]
    dispatch.body[0:0] = ast.parse("""
if ctx.phase.kind not in ('INIT','SIM') or ctx.p._run_sim is not (ctx.phase.kind=='SIM'):
    raise ValueError('Dispatch requires native phase/legacy consistency')
""").body
    for n in ast.walk(dispatch):
        if isinstance(n, ast.Call) and ast.unparse(n.func) == "observer" and len(n.args) == 3:
            if ast.unparse(n.args[2]) == "ions.freeze(value)":
                n.args[2] = ast.parse(
                    "ions.freeze(dict(value,source_phase=ctx.phase.kind,legacy_run_sim=ctx.p._run_sim))",
                    mode="eval",
                ).body
    condition = fn(runtime, "conditional_input")
    return_node = next(n for n in condition.body if isinstance(n, ast.Return))
    return_node.value.keywords.extend(
        [
            ast.keyword(arg="source_phase", value=ast.parse("ctx.phase.kind", mode="eval").body),
            ast.keyword(arg="legacy_run_sim", value=ast.parse("ctx.p._run_sim", mode="eval").body),
        ]
    )
    runtime.body += ast.parse(VALIDATE).body
    available = fn(runtime, "available")
    readers = next(n for n in available.body if isinstance(n, ast.For))
    readers.iter.elts.append(
        ast.parse(
            "('partial_wires',lambda:{role:source.wire(getattr(ctx.sim,role,None),ctx.sim) for role in ROLES})",
            mode="eval",
        ).body
    )
    write(PREFIX + "_owners.py", runtime)


if __name__ == "__main__":
    main()
