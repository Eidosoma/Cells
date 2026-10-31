"""Prepare authenticated phase-aware native conditionals without importing science."""
# ruff: noqa: E501 -- Literal independent namespace/capture plumbing.

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PARENT = Path(
    "/mnt/workspaces/Cells/betse-normal-ecm-molecule-transport-prepared-20261031-01/source"
)
PREFIX = "betse_normal_ecm_molecule_lifecycle"
OLD = "betse_normal_ecm_molecule_transport"


def fn(tree, name):
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def write(name, tree):
    path = ROOT / "validation/betse" / name
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


def main():
    network = ast.parse((PARENT / "validation/betse" / (OLD + "_native_network.py")).read_text())
    literal = fn(network, "literal_nodes")
    position = next(i for i, n in enumerate(literal.body) if isinstance(n, ast.Return))
    literal.body[position:position] = ast.parse("""
network.body.append(Clean().visit(copy.deepcopy(next(
    n for n in original.body if isinstance(n,ast.FunctionDef) and n.name=='clear_cache'))))
""").body
    write(PREFIX + "_native_network.py", network)

    product = ast.parse((ROOT / "src/cells/processes" / (PREFIX + "_source.py")).read_text())
    skip = {
        "MasterOfNetworks",
        "Transporter",
        "init_profiles",
        "initDenv",
        "_finalize_events_global",
        "_finalize_events_tissue",
        "f_sweep",
        "static_and_blocks",
        "screening_conductivity",
    }
    bodies = [
        copy.deepcopy(n)
        for n in product.body
        if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name not in skip
    ]
    source = ast.parse('''
"""Literal independent native general/GRN owner boundaries on actual phase buffers."""
import posixpath as pathnames
from collections import OrderedDict
from types import SimpleNamespace
import numpy as np
from validation.betse import betse_normal_ecm_catalog_join_native_network as qualified
from validation.betse import betse_normal_ecm_molecule_lifecycle_native_network as transport_native
MasterOfNetworks=None
MasterOfGenes=None
Transporter=None
set_net_opts=None
logs=SimpleNamespace(log_info=lambda *args:None,log_warning=lambda *args:None)
clone=qualified.clone
PARAMETERS=qualified.PARAMETERS
validate_cached_channels=qualified.validate_cached_channels
channel_fields=qualified.channel_fields
material_values=qualified.material_values

def prepare_native_namespace():
    global MasterOfNetworks,MasterOfGenes,Transporter,set_net_opts
    api=transport_native.science()
    MasterOfNetworks=api['MasterOfNetworks']
    MasterOfGenes=api['MasterOfGenes']
    Transporter=api['Transporter']
    set_net_opts=api['set_net_opts']
''')
    source.body.extend(bodies)
    write(PREFIX + "_native_source.py", source)

    outer = ast.parse(
        (PARENT / "validation/betse" / (OLD + "_native.py"))
        .read_text()
        .replace(OLD + "_native_source", PREFIX + "_native_source")
    )
    evaluate = fn(outer, "evaluate")
    try_node = next(n for n in evaluate.body if isinstance(n, ast.Try))
    guard = try_node.body[0]
    assert isinstance(guard, ast.If)
    # This new native input explicitly chooses its actual phase and operation.
    guard.test = ast.parse(
        "inputs['kind']!='cells.actual_ECM_general_GRN_conditional_inputs@1' or inputs['mode'] not in ('initialize','dispatch','reinitialize','entry') or inputs['source_phase'] not in ('INIT','SIM') or inputs['legacy_run_sim'] is not (inputs['source_phase']=='SIM')",
        mode="eval",
    ).body
    for node in ast.walk(evaluate):
        if isinstance(node, ast.Assign):
            target = ast.unparse(node.targets[0])
            if target == "p._run_sim":
                node.value = ast.parse("inputs['source_phase']=='SIM'", mode="eval").body
            if target == "ctx.phase.kind":
                node.value = ast.parse(
                    "'INIT' if inputs['source_phase']=='INIT' else 'SIM'", mode="eval"
                ).body
        if isinstance(node, ast.If) and ast.unparse(node.test) == "inputs['mode'] == 'dispatch'":
            node.test = ast.parse(
                "inputs['mode'] in ('dispatch','reinitialize','entry')", mode="eval"
            ).body
    # Warm reinitialize restores under the old declaration before changing configs.
    role_loop = next(
        n for n in try_node.body if isinstance(n, ast.For) and ast.unparse(n.target) == "role"
    )
    role_loop.body.insert(
        0,
        ast.parse("owner_raw=inputs['old_raw'] if inputs['mode']=='reinitialize' else raw").body[0],
    )

    class OldDefinition(ast.NodeTransformer):
        def visit_Subscript(self, node):
            if ast.unparse(node) == "raw['handlers']":
                return ast.parse("owner_raw['handlers']", mode="eval").body
            return self.generic_visit(node)

    OldDefinition().visit(role_loop)
    restore = next(
        n
        for n in try_node.body
        if isinstance(n, ast.If)
        and ast.unparse(n.test) == "inputs['mode'] in ('dispatch', 'reinitialize', 'entry')"
    )
    where = try_node.body.index(restore) + 1
    try_node.body[where:where] = ast.parse("""
if inputs['mode']=='reinitialize':
    for role in ROLES:
        view=views[role]
        view.definition=network.clone(raw['handlers'][role]['network'])
        network.configure(view,network.clone(raw['handlers'][role]['catalog']))
    p.grn=SimpleNamespace(conf=network.clone(views['grn'].definition['configuration']))
""").body
    operation = next(
        n
        for n in reversed(try_node.body)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "inputs['mode'] == 'initialize'"
    )
    operation.test = ast.parse("inputs['mode'] in ('initialize','reinitialize')", mode="eval").body
    operation.orelse = ast.parse("""
if inputs['mode']=='dispatch':
    source.dispatch_both(sim,inputs['source_time_s'],ctx.phase,cells,p,hook=hook)
""").body
    snapshot = fn(outer, "snapshot")
    returned = next(n for n in snapshot.body if isinstance(n, ast.Return))
    for keyword in returned.value.keywords:
        if keyword.arg == "shared":
            keyword.value = ast.parse(
                "{key:network.clone(getattr(ctx.sim,key)) for key in SHARED if hasattr(ctx.sim,key)}",
                mode="eval",
            ).body
    returned.value.keywords.extend(
        [
            ast.keyword(
                arg="shared_absent",
                value=ast.parse(
                    "[key for key in SHARED if not hasattr(ctx.sim,key)]", mode="eval"
                ).body,
            ),
            ast.keyword(arg="source_phase", value=ast.parse("ctx.phase.kind", mode="eval").body),
            ast.keyword(arg="legacy_run_sim", value=ast.parse("ctx.p._run_sim", mode="eval").body),
        ]
    )
    returned.value.keywords.insert(
        -2,
        ast.keyword(
            arg="partial_wires",
            value=ast.parse(
                "{role:source.wire(getattr(ctx.sim,role,None),ctx.sim) for role in ROLES}",
                mode="eval",
            ).body,
        ),
    )
    final = next(n for n in evaluate.body if isinstance(n, ast.Return))
    evaluate.body[evaluate.body.index(final) : evaluate.body.index(final)] = ast.parse("""
partial_buffers={}
if ctx is not None:
    for name,reader in (
        ('material',lambda:network.material_values(ctx.sim)),
        ('shared',lambda:{key:network.clone(getattr(ctx.sim,key)) for key in SHARED if hasattr(ctx.sim,key)}),
        ('partial_wires',lambda:{role:source.wire(getattr(ctx.sim,role,None),ctx.sim) for role in ROLES})):
        try:
            partial_buffers[name]=reader()
        except Exception as error:
            capture_errors.append(dict(section=name,type=type(error).__name__,message=str(error)))
""").body
    final.value.keywords.insert(
        1, ast.keyword(arg="partial_buffers", value=ast.Name(id="partial_buffers", ctx=ast.Load()))
    )
    write(PREFIX + "_native.py", outer)


if __name__ == "__main__":
    main()
