# ruff: noqa: E501
"""Write new-prefix source copies and prove the declared AST-only substitutions.

This generator uses stdlib source parsing only. It never imports science modules.
"""

import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-run-lifecycle-prepared-20261031-02/source")
NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")
OUTPUT = ROOT / "src/cells/processes/betse_normal_ecm_init_phase_source.py"


def function(path, name, owner=None):
    tree = ast.parse(path.read_text())
    if owner:
        tree = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner)
    return copy.deepcopy(
        next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    )


def dump(node):
    return ast.dump(node, include_attributes=False)


def main():
    source = PARENT / "src/cells/processes/betse_normal_ecm_catalog_join_source.py"
    dispatcher = function(source, "run_dispatch")
    changed = copy.deepcopy(dispatcher)
    changed.body[1].value.value = "INIT"
    changed.body.insert(2, ast.parse("ctx.p._run_sim = False").body[0])
    inverse = copy.deepcopy(changed)
    inverse.body.pop(2)
    inverse.body[1].value.value = "SIM"
    assert dump(inverse) == dump(dispatcher)
    nodes = [changed]
    proofs = {"run_dispatch": "phase literal SIM->INIT and explicit legacy flag only"}
    for name in ("_finalize_events_global", "_finalize_events_tissue"):
        node = function(NATIVE / "science/tissue/tishandler.py", name, "TissueHandler")
        node.decorator_list = []
        node.returns = None
        for arg in node.args.args:
            arg.annotation = None
        if name == "_finalize_events_global":
            node.args.kwonlyargs.append(ast.arg(arg="shuffle"))
            node.args.kw_defaults.append(None)
        nodes.append(node)
        proofs[name] = (
            "whole function body unchanged; annotations/decorator removed; global shuffle injected"
        )
    node = function(NATIVE / "science/math/modulate.py", "f_sweep")
    node.returns = None
    nodes.append(node)
    header = '''"""INIT dispatch and literal event-setup bodies; no event firing/noise execution.

Common catalog kernels remain unchanged. Local RNG injection preserves the
source shuffle of an unused copy and the original unshuffled target choice.
"""

from types import SimpleNamespace

import numpy as np

from cells.processes import betse_normal_ecm_catalog_join_source as common

attach = common.attach
cache = common.cache
clone = common.clone
material_values = common.material_values
owner_evidence = common.owner_evidence
science = common.science

'''
    body = "\n\n".join(ast.unparse(ast.fix_missing_locations(n)) for n in nodes)
    tail = """


mod = SimpleNamespace(f_sweep=f_sweep)


def cold(ctx):
    ctx.p._run_sim = False
    return common.cold(ctx)


def validate_init_cache(ctx, incoming, call_index):
    common.validate_cached_channels(ctx, incoming)
    for row in ctx.catalog["populations"] or []:
        name = row["name"]
        active = row.get("init active", True)
        expected = call_index if active else 0
        if incoming["channel_calls"][name] != expected:
            raise ValueError("INIT channel count differs from its active flag and source epoch")
        if not active and not common.equal_tree(
            incoming["wire"]["channel_fields"][name], incoming["initial_channel_fields"][name]
        ):
            raise ValueError("INIT-inactive population must retain its complete cold private state")


def restore(ctx, incoming, call_index):
    validate_init_cache(ctx, incoming, call_index)
    return common.restore(ctx, incoming)
"""
    with OUTPUT.open("x") as stream:
        stream.write(header + body + tail)
    receipt = dict(
        kind="cells.init_source_generation@1",
        scientific_execution=False,
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        proofs=proofs,
    )
    path = (
        ROOT
        / "agent-work/cells-worker-01/workfiles/betse_normal_ecm_init_phase_source_generation_01.json"
    )
    with path.open("x") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
