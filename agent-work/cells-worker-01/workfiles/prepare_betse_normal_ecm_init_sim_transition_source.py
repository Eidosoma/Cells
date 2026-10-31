"""Generate private transition source bodies, never execute scientific AST."""

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")
INIT = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-01/source")
PREFIX = "betse_normal_ecm_init_sim_transition"


def fn(path, name, owner=None):
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
    nodes = []
    for relative, name, owner in (
        ("science/chemistry/gene.py", "reinitialize", "MasterOfGenes"),
        ("science/chemistry/networks.py", "clear_cache", "MasterOfNetworks"),
        ("science/tissue/tishandler.py", "init_profiles", "TissueHandler"),
        ("science/sim.py", "initDenv", "Simulator"),
        ("science/sim.py", "clear_storage", "Simulator"),
        ("science/tissue/tishandler.py", "_finalize_events_global", "TissueHandler"),
        ("science/tissue/tishandler.py", "_finalize_events_tissue", "TissueHandler"),
        ("science/math/modulate.py", "f_sweep", None),
    ):
        node = clean(fn(NATIVE / relative, name, owner))
        if name == "_finalize_events_global":
            node.args.kwonlyargs.append(ast.arg(arg="shuffle"))
            node.args.kw_defaults.append(None)
        if name == "clear_storage":
            # Preserve the complete body; lower this method binding only. The
            # existing retained owner executes the literal clear_cache body.
            class Lower(ast.NodeTransformer):
                def visit_Call(self, node):
                    if ast.unparse(node.func) == "self.grn.core.clear_cache":
                        assert not node.args and not node.keywords
                        return ast.Call(
                            func=ast.Name(id="clear_cache", ctx=ast.Load()),
                            args=[ast.parse("self.grn.core", mode="eval").body],
                            keywords=[],
                        )
                    return self.generic_visit(node)

            node = Lower().visit(node)
        nodes.append(node)
    nodes.append(
        fn(
            INIT / "validation/betse/betse_normal_ecm_init_phase_native_setup.py",
            "static_and_blocks",
        )
    )
    init = fn(NATIVE / "science/sim.py", "init_dynamics", "Simulator")
    begin = next(
        i
        for i, n in enumerate(init.body)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "self.ko_env"
    )
    cache = ast.parse("def screening_conductivity(self,cells,p):\n    pass").body[0]
    end = (
        next(
            i
            for i, n in enumerate(init.body)
            if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "self.rho_factor"
        )
        + 1
    )
    cache.body = copy.deepcopy(init.body[begin:end])
    assert ast.unparse(cache.body[-1].targets[0]) == "self.rho_factor"
    cache.body.append(
        copy.deepcopy(
            next(
                n
                for n in init.body
                if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "self.cgj"
            )
        )
    )
    nodes.append(cache)
    header = '''# ruff: noqa: E731, F841, B905
"""Pinned native SIM reinitialization bodies on explicitly supplied owners.

No cold constructor, seed loader, pickle, profile selector or full solver runs.
The retained GRN executes its real reinitialize body; channels are reconstructed
by that body, never inferred from a fresh cold snapshot.
"""

from types import SimpleNamespace

import numpy as np

from cells.processes import betse_environment_field as environment

gaussian_filter=environment.gaussian_filter
logs=SimpleNamespace(log_info=lambda *args:None,log_debug=lambda *args:None)
EndoRetic=None  # unreachable under the explicit ordinary Ca_dyn=False flag

'''
    output = ROOT / "src/cells/processes" / f"{PREFIX}_source.py"
    with output.open("x") as stream:
        stream.write(
            header
            + "\n\n".join(ast.unparse(ast.fix_missing_locations(n)) for n in nodes)
            + "\n\nmod=SimpleNamespace(f_sweep=f_sweep)\n"
        )
    compile(output.read_text(), str(output), "exec")
    print(str(output))


if __name__ == "__main__":
    main()
