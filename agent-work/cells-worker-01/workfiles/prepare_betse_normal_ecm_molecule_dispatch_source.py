"""Generate distinct general owner bodies and literal two-handler source dispatch."""

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-02/source")
PREFIX = "betse_normal_ecm_molecule_dispatch"


def function(path, name, owner=None):
    tree = ast.parse(path.read_text())
    if owner:
        tree = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner)
    return copy.deepcopy(
        next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    )


def clean(node):
    node.decorator_list = []
    node.returns = None
    for arg in node.args.args:
        arg.annotation = None
    return node


def main():
    methods = [
        clean(function(NATIVE / "science/chemistry/molecules.py", name, "MasterOfMolecules"))
        for name in ("__init__", "read_mol_config", "reinitialize")
    ]
    cls = ast.ClassDef(
        name="MasterOfMolecules", bases=[], keywords=[], body=methods, decorator_list=[]
    )
    nodes = [cls]
    setup = function(NATIVE / "science/sim.py", "init_dynamics", "Simulator")
    loop = next(
        n
        for n in function(NATIVE / "science/sim.py", "_run_sim_core_loop", "Simulator").body
        if isinstance(n, ast.For)
    )
    for name, body in (("initialize_both", setup.body), ("dispatch_both", loop.body)):
        guards = copy.deepcopy(
            [
                n
                for n in body
                if isinstance(n, ast.If)
                and ast.unparse(n.test) in ("p.molecules_enabled", "p.grn_enabled")
            ]
        )
        assert [ast.unparse(n.test) for n in guards] == ["p.molecules_enabled", "p.grn_enabled"]
        for guard, role in zip(guards, ("molecules", "grn"), strict=True):
            first = "before_setup" if name == "initialize_both" else "before_dispatch"
            guard.body[:0] = ast.parse(f"hook({role!r},{first!r},self,phase)").body
            if name == "initialize_both":
                guard.body.extend(ast.parse(f'hook({role!r},"after_setup",self,phase)').body)
            else:

                def instrument(statements, role=role):
                    result = []
                    for node in statements:
                        if isinstance(node, ast.If):
                            node.body = instrument(node.body)
                        result.append(node)
                        if (
                            isinstance(node, ast.Expr)
                            and isinstance(node.value, ast.Call)
                            and isinstance(node.value.func, ast.Attribute)
                        ):
                            stage = node.value.func.attr
                            if stage in {
                                "clear_run_loop",
                                "run_loop_transporters",
                                "run_loop_channels",
                                "run_loop_modulators",
                                "run_loop",
                            }:
                                result.extend(
                                    ast.parse(f"hook({role!r},{stage!r},self,phase)").body
                                )
                    return result

                guard.body = instrument(guard.body)
        wrapper = ast.parse(f"def {name}(self,t,phase,cells,p,*,hook):\n    pass").body[0]
        wrapper.body = guards
        nodes.append(wrapper)
    q = PARENT / "src/cells/processes/betse_normal_ecm_catalog_join_source.py"
    names = ("cache", "restore", "before", "attach", "install_channel_observer")
    rename = {name: name + "_general" for name in (*names, "owner_evidence")}

    class General(ast.NodeTransformer):
        def visit_Call(self, node):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and ast.unparse(node.args[0]) == "ctx.sim"
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "grn"
            ):
                node.args[1] = ast.Constant("molecules")
            return self.generic_visit(node)

        def visit_Attribute(self, node):
            if ast.unparse(node) == "p.grn.conf":
                return ast.parse("p.network_config", mode="eval").body
            if node.attr == "grn":
                node.attr = "molecules"
            return self.generic_visit(node)

        def visit_Name(self, node):
            if node.id in rename:
                node.id = rename[node.id]
            elif node.id == "science":
                node.id = "science_general"
            return node

    for name in names:
        node = function(q, name)
        node.name = rename[name]
        nodes.append(General().visit(node))
    node = function(PARENT / "src/cells/processes/betse_ecm_grn_source.py", "owner_evidence")
    node.name = rename["owner_evidence"]
    nodes.append(General().visit(node))
    header = '''# ruff: noqa: E501, F841
"""Private native general owner and explicit FULL general-then-GRN source slices.

No shared scientific module is patched. Qualified molecule/ECM kernels are
reused; helper role lowering changes owner access and evidence wiring only.
"""

import posixpath as pathnames
from collections import OrderedDict


from cells.processes import betse_normal_ecm_catalog_join_source as qualified

MasterOfNetworks=qualified.MasterOfNetworks
MasterOfGenes=qualified.MasterOfGenes
set_net_opts=qualified.base.set_net_opts
logs=qualified.logs
clone=qualified.clone
wire=qualified.wire
PARAMETERS=qualified.PARAMETERS
validate_cached_channels=qualified.validate_cached_channels
channel_fields=qualified.channel_fields
material_values=qualified.material_values


def science_general():
    return dict(qualified.science(),MasterOfGenes=MasterOfMolecules)

'''
    output = ROOT / "src/cells/processes" / f"{PREFIX}_source.py"
    with output.open("x") as stream:
        stream.write(
            header + "\n\n".join(ast.unparse(ast.fix_missing_locations(n)) for n in nodes) + "\n"
        )
    compile(output.read_text(), str(output), "exec")
    print(str(output))


if __name__ == "__main__":
    main()
