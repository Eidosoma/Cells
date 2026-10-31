# ruff: noqa: E501
"""Exclusive copy of the qualified pure-stdlib chemistry prefix, never evaluation."""

import ast
import copy
from pathlib import Path

root = Path("/home/robert/Cells")
old = ast.parse((root / "validation/betse/betse_ecm_grn_reference.py").read_text())
fn = copy.deepcopy(next(n for n in old.body if isinstance(n, ast.FunctionDef) and n.name == "warm"))
fn.name = "chemistry_prefix"
block = next(n for n in fn.body if isinstance(n, ast.With))
stop = next(
    i for i, n in enumerate(block.body) if isinstance(n, ast.FunctionDef) and n.name == "ghk"
)
block.body = block.body[:stop]
extra = ast.parse("""chemical = {name:[old_cell[name][j]+delta[name][j]*dt for j in range(n)] for name in names}
chemical_gross={name:[abs(old_cell[name][j])+rate_gross[name][j]*dt for j in range(n)] for name in names}
return plain(dict(mode="network_chemistry_prefix",rhs=dict(growth_rates=[growth[name] for name in names],reaction_rates=[reaction] if reaction else [],all_rates=[growth[name] for name in names]+([reaction] if reaction else [])),delta_conc=delta_rows,delta_gross=gross_rows,chemical_commit=chemical,chemical_gross=chemical_gross,decimal_precision=ctx.prec,carried_reference_forms=0,fresh_conditional_reference=True,complete_network_return_predicted=False,transport_evaluations=0,physical_global_conservation_credit=False))""").body
block.body += extra
header = '''"""Independent actual pre-GRN chemistry prefix; transport is outside this raw check.

Existing qualified scalar RHS/delta equations and fixed budgets are unchanged.
The historical no_negs exception is a NaN refusal after X transport, not a
refusal of finite negative concentration (the source clips finite negatives).
"""
import argparse
import json
from decimal import Decimal,localcontext
from pathlib import Path
from validation.betse import betse_ecm_grn_reference as grn

d=grn.d
_alpha=grn._alpha
hill=grn.hill
plain=grn.plain
derive_geometry=grn.derive_geometry

'''
with (root / "validation/betse/betse_normal_ecm_calcium_domain04_reference.py").open("x") as stream:
    stream.write(header + ast.unparse(ast.fix_missing_locations(fn)) + "\n")
