# ruff: noqa: E501
"""Statically reuse every existing complete per-call scientific comparison."""

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PREFIX = "betse_normal_ecm_run_lifecycle"
source = Path(
    "/mnt/workspaces/Cells/betse-normal-ecm-event-mechanics-prepared-20261031-02/source/tests/unit/test_betse_normal_ecm_event_mechanics.py"
)
tree = ast.parse(source.read_text())
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_history")
loop = next(
    n for n in fn.body if isinstance(n, ast.For) and ast.unparse(n.target) == "(index, native_call)"
)
start = next(
    i
    for i, n in enumerate(loop.body)
    if isinstance(n, ast.Assign)
    and isinstance(n.targets[0], ast.Tuple)
    and ast.unparse(n.targets[0]) == "(inner, trial, feedback, calcium, noise, event_context)"
)
stop = next(
    i
    for i, n in enumerate(loop.body)
    if isinstance(n, ast.Expr) and ast.unparse(n) == "states.append(candidate)"
)
wrapper = ast.parse(
    "def compare_call(binding,parent,candidate,context,native_call,captured,incoming,index,observed,answers,tmp_path,case,point,check):\n pass"
).body[0]
wrapper.body = copy.deepcopy(loop.body[start:stop])
header = '''"""Byte-for-byte AST scientific assertions reused from reviewed component successor."""

from tests.unit import test_betse_normal_ecm_event_mechanics as component

base,catalog,exact,established=component.base,component.catalog,component.exact,component.established
ions,np,joined=component.ions,component.np,component.joined
mechanical_rows=component.mechanical_rows
'''
path = ROOT / "validation/betse" / (PREFIX + "_compare.py")
with path.open("x") as stream:
    stream.write(header + "\n" + ast.unparse(ast.fix_missing_locations(wrapper)) + "\n")
print(path)
