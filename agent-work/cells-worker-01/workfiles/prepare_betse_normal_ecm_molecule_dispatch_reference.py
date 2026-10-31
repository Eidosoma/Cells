"""Generate unchanged independent primary-prefix and deferred-commit equations."""
# ruff: noqa: E501 -- embedded source templates.

import ast
import builtins
import copy
import symtable
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-02/source")
PREFIX = "betse_normal_ecm_molecule_dispatch"


def main():
    parent = PARENT / "validation/betse/betse_normal_ecm_catalog_join_reference.py"
    original = next(
        n
        for n in ast.parse(parent.read_text()).body
        if isinstance(n, ast.FunctionDef) and n.name == "material_model"
    )
    prefix = copy.deepcopy(original)
    prefix.name = "prefix_model"
    finish = next(n for n in prefix.body if isinstance(n, ast.FunctionDef) and n.name == "finish")
    assert ast.unparse(finish.body[-1]) == "return serial(result)"
    finish.body[-1].value = ast.Name(id="result", ctx=ast.Load())
    outer = next(n for n in prefix.body if isinstance(n, ast.With))
    loop = next(n for n in outer.body if isinstance(n, ast.For))
    channel = next(
        i
        for i, n in enumerate(loop.body)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "channel_result"
    )
    commit_loop = copy.deepcopy(loop.body[channel + 1])
    assert isinstance(commit_loop, ast.For) and ast.unparse(commit_loop.target) == "i"
    ledger = copy.deepcopy(loop.body[channel + 2 : -1])
    assert ast.unparse(ledger[-1].targets[0]) == "ledgers"
    loop.body = (
        loop.body[:channel]
        + ast.parse("""
return finish(dict(geometry=g,frames=frames,environment_records=environment_records,
                   candidate=deepcopy(v),prefix_books=dict(
                       boundary_clamp_change_mol=clamp,collocated_transport_change_mol=collocated,
                       smoothing_change_mol=smoothing),precision=context.prec))
""").body
    )
    # A single actual material call is the reference's conditional input.
    outer.body = outer.body[: outer.body.index(loop) + 1]
    commit = ast.parse(
        "def commit_model(inputs,*,refinement=1,retain_decimal=None):\n    pass"
    ).body[0]
    with_body = ast.parse("""
context.prec=100 if refinement==1 else 160
raw=inputs['definition']
external,junction,ions,p=(raw[key] for key in ('environment_geometry_definition','junction_geometry','ions','parameters'))
cg=external['current_definition']['geometry']
names=external['current_definition']['ions']['ids']
g=geometry(external,precision=context.prec)
ny,nx=g['shape']
s,m,n,e=len(names),len(cg['membrane_ids']),len(cg['cell_ids']),ny*nx
owner,mapping=cg['owner'],g['membrane_to_grid']
area,volume=numbers(cg['membrane_area_m2']),numbers(external['geometry']['cell_volume_m3'])
site_volume=d(external['parameters']['cell_height_m'])*g['delta_m']**2
moving=[names.index(name) for name in ions['moving_ids']]
zero=Decimal(0)
v=numbers(inputs['values_before'])
old=numbers(inputs['initial'])
dt=d(inputs['steps'][0]['dt_s'])
frames=[]
conservative_exchange=[]
clip,exchange=([zero]*s for _ in range(2))
requested_gap_outward_increment=[[zero]*n for _ in range(s)]
prefix=prefix_model(inputs['material_inputs'],refinement=refinement)
clamp,collocated,smoothing=(prefix['prefix_books'][key] for key in ('boundary_clamp_change_mol','collocated_transport_change_mol','smoothing_change_mol'))
""").body
    observe = copy.deepcopy(
        next(n for n in loop.body if isinstance(n, ast.FunctionDef) and n.name == "observe")
    )
    with_body += [observe, commit_loop, *ledger]
    with_body += ast.parse("""
result=dict(frames=frames,candidate=deepcopy(v),ledgers=ledgers,
            conservative_exchange=conservative_exchange,precision=context.prec,
            fixed_budget_reference=True,physical_material_or_energy_parity=False)
if retain_decimal is not None:retain_decimal(deepcopy(result))
return result
""").body
    commit.body = ast.parse("""
if refinement not in (1,2):raise ValueError('Require predeclared independent precision')
with localcontext() as context:
    pass
""").body
    commit.body[-1].body = with_body
    nodes = [prefix, commit]
    symbols = set()
    known = set(dir(builtins)) | {"prefix_model", "commit_model"}
    for node in nodes:
        table = symtable.symtable(
            ast.unparse(ast.fix_missing_locations(node)), "<reference source>", "exec"
        )

        def walk(scope):
            symbols.update(
                s.get_name()
                for s in scope.get_symbols()
                if s.is_global() and s.is_referenced() and s.get_name() not in known
            )
            for child in scope.get_children():
                walk(child)

        walk(table)
    header = '''# ruff: noqa: E501, F841
"""Fresh Decimal primary/CaATP prefix and unchanged deferred material commit.

The two network handlers are checked independently from actual conditional
inputs. These equations do not claim an independently carried trajectory.
"""

from validation.betse import betse_normal_ecm_catalog_join_reference as qualified

'''
    header += "\n".join(name + "=qualified." + name for name in sorted(symbols)) + "\n\n"
    output = ROOT / "validation/betse" / f"{PREFIX}_reference_models.py"
    with output.open("x") as stream:
        stream.write(
            header + "\n\n".join(ast.unparse(ast.fix_missing_locations(n)) for n in nodes) + "\n"
        )
    compile(output.read_text(), str(output), "exec")
    print(str(output))


if __name__ == "__main__":
    main()
