"""Write authenticated native transporter namespaces without executing them."""
# ruff: noqa: E501 -- Literal generated namespace source.

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
BASE = Path("/mnt/workspaces/Cells")
PARENT = BASE / "betse-normal-ecm-molecule-dispatch-prepared-20261031-01/source"
TRANSPORTER = BASE / "betse-normal-transporter-prepared-20261030-03/source"
PREFIX = "betse_normal_ecm_molecule_transport"


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
    old = ast.parse(
        (
            TRANSPORTER / "validation/betse/betse_normal_transporter_join_native_network.py"
        ).read_text()
    )
    clean = copy.deepcopy(
        next(n for n in old.body if isinstance(n, ast.ClassDef) and n.name == "Clean")
    )
    literal = copy.deepcopy(
        next(n for n in old.body if isinstance(n, ast.FunctionDef) and n.name == "literal_nodes")
    )
    literal.body = [n for n in literal.body if not isinstance(n, ast.ImportFrom)]

    class Adapt(ast.NodeTransformer):
        def visit_Attribute(self, node):
            if ast.unparse(node) == "molecule_native.literal_nodes":
                return ast.parse("qualified.literal_nodes", mode="eval").body
            return self.generic_visit(node)

        def visit_Constant(self, node):
            if node.value == "_LiteralNetwork":
                node.value = "MasterOfNetworks"
            return node

    literal = Adapt().visit(literal)
    helper = ast.parse('''
"""Fresh pinned ECM channel/molecule/transporter native namespace; never production."""
import ast
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from validation.betse import betse_normal_ecm_catalog_join_native_network as qualified
_SCIENCE=None

def statement(text):
    return ast.parse(text).body[0]

def science():
    global _SCIENCE
    if _SCIENCE is None:
        # Recompile every selected native body in a new private namespace.
        pins=json.loads(qualified.PROTOCOL.read_text())['native_source']
        root=Path(pins['checkout'])/'betse'
        for name in ('betse/science/chemistry/networks.py','betse/science/sim_toolbox.py'):
            file=Path(pins['checkout'])/name
            if hashlib.sha256(file.read_bytes()).hexdigest()!=pins['source_sha256'][name]:
                raise ValueError('Changed authenticated transporter source '+name)
            if file.read_bytes()!=(Path(pins['installed_package']).parent/name).read_bytes():
                raise ValueError('Installed/native transporter source mismatch '+name)
        ns=dict(qualified.science())
        ns['tex_val']=str
        exec(compile(ast.fix_missing_locations(ast.Module(body=literal_nodes(root),type_ignores=[])),
                     '<authenticated ECM general-owner configured transport>','exec'),ns)
        ns['fd']=SimpleNamespace(**{key:ns[key] for key in ('gradient','divergence','integrator')})
        ns['stb']=SimpleNamespace(
            molecule_mover=ns['molecule_mover'],no_negs=ns['no_negs'],
            electroflux=ns['electroflux'],update_Co=ns['update_Co'],div_env=ns['div_env'],
        )
        _SCIENCE=ns
    return _SCIENCE
''')
    helper.body[8:8] = [clean, literal]
    write(PREFIX + "_native_network.py", helper)

    product = ast.parse((ROOT / "src/cells/processes" / (PREFIX + "_source.py")).read_text())
    functions = [
        copy.deepcopy(n)
        for n in product.body
        if isinstance(n, (ast.ClassDef, ast.FunctionDef))
        and n.name not in {"MasterOfNetworks", "Transporter"}
    ]
    native = ast.parse('''
"""Literal native general-owner setup and observation-only transporter cache plumbing."""
import posixpath as pathnames
from collections import OrderedDict
from types import SimpleNamespace
import numpy as np
from validation.betse import betse_normal_ecm_catalog_join_native_network as qualified
from validation.betse import betse_normal_ecm_molecule_transport_native_network as transport_native
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
    # The independent source class/helpers resolve globals only from the authenticated API.
    native.body.extend(functions)
    write(PREFIX + "_native_source.py", native)

    outer = ast.parse(
        (PARENT / "validation/betse/betse_normal_ecm_molecule_dispatch_native.py")
        .read_text()
        .replace("betse_normal_ecm_molecule_dispatch_native_source", PREFIX + "_native_source")
    )
    for n in outer.body:
        if (
            isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Name)
            and n.targets[0].id == "SHARED"
        ):
            n.value.elts.append(ast.Constant("rho_pump"))
    evaluate = next(
        n for n in outer.body if isinstance(n, ast.FunctionDef) and n.name == "evaluate"
    )

    class AddInitial(ast.NodeTransformer):
        def visit_Assign(self, node):
            node = self.generic_visit(node)
            text = ast.unparse(node.targets[0])
            if text == "view.trace":
                return [node, *ast.parse("view.initial_transporter_fields={}").body]
            if text == "view.initial_channel_fields":
                return [
                    node,
                    *ast.parse(
                        "if role=='molecules':\n    view.initial_transporter_fields=source.transporter_fields(view.net)"
                    ).body,
                ]
            return node

    AddInitial().visit(evaluate)
    write(PREFIX + "_native.py", outer)


if __name__ == "__main__":
    main()
