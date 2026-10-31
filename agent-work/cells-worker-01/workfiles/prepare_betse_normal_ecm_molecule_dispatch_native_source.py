"""Prepare native-backed dual-owner class/plumbing without importing science."""

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PREFIX = "betse_normal_ecm_molecule_dispatch"
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-02/source")


def main():
    product = ROOT / "src/cells/processes" / f"{PREFIX}_source.py"
    tree = ast.parse(product.read_text())
    functions = [
        copy.deepcopy(n) for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))
    ]
    header = '''# ruff: noqa: E501, F841
"""Native-backed literal two-owner boundaries; independent scientific namespace.

Classes and dispatch slices have native AST provenance. Metadata hydration
keeps actual conditional inputs; no production package may be imported.
"""

import posixpath as pathnames
from collections import OrderedDict
from types import SimpleNamespace

from validation.betse import betse_normal_ecm_catalog_join_native_network as qualified

MasterOfNetworks=None
MasterOfGenes=None
set_net_opts=None
logs=SimpleNamespace(log_info=lambda *args:None,log_warning=lambda *args:None)
clone=qualified.clone
wire=qualified.wire
PARAMETERS=qualified.PARAMETERS
validate_cached_channels=qualified.validate_cached_channels
channel_fields=qualified.channel_fields
material_values=qualified.material_values


def prepare_native_namespace():
    global MasterOfNetworks,MasterOfGenes,set_net_opts
    api=qualified.science()
    MasterOfNetworks=api['MasterOfNetworks']
    MasterOfGenes=api['MasterOfGenes']
    set_net_opts=api['set_net_opts']

'''
    output = ROOT / "validation/betse" / f"{PREFIX}_native_source.py"
    with output.open("x") as stream:
        stream.write(
            header
            + "\n\n".join(ast.unparse(ast.fix_missing_locations(n)) for n in functions)
            + "\n"
        )
    compile(output.read_text(), str(output), "exec")
    print(str(output))


if __name__ == "__main__":
    main()
