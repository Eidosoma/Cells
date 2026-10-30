"""Static creation of the new seam adapters; never imports numerical modules."""

import ast
import copy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def append_material_seams():
    source = ROOT / "src/cells/processes/betse_normal_pump_join.py"
    selected = [
        n
        for n in ast.parse(source.read_text()).body
        if isinstance(n, ast.FunctionDef)
        and n.name in ("material_step", "_active_material_step", "_pumped_material_step")
    ]
    names = {
        "Binding",
        "State",
        "binding_record",
        "bind",
        "packet",
        "_state",
        "_arithmetic",
        "Phase",
        "MaterialTrial",
        "PumpJoinRejected",
        "Packet",
    }

    class Qualify(ast.NodeTransformer):
        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Load) and node.id in names:
                return ast.Attribute(
                    value=ast.Name(id="pump", ctx=ast.Load()), attr=node.id, ctx=node.ctx
                )
            return node

        def visit_Call(self, node):
            node = self.generic_visit(node)
            if isinstance(node.func, ast.Name) and node.func.id in (
                "_active_material_step",
                "_pumped_material_step",
            ):
                node.args.append(ast.Name(id="late_callback", ctx=ast.Load()))
            return node

    out = []
    for original in selected:
        node = Qualify().visit(copy.deepcopy(original))
        node.args.args.append(ast.arg(arg="late_callback"))
        if node.name == "material_step":
            node.name = "_pump_material_step"
        if node.name == "_pumped_material_step":
            # Exactly one late hook between the actual two moving-ion loops.
            loops = [
                n
                for n in ast.walk(node)
                if isinstance(n, ast.For) and ast.unparse(n.iter) == "k.moving"
            ]
            assert len(loops) == 2
            owner = next(
                n
                for n in ast.walk(node)
                if isinstance(n, ast.With) and loops[0] in n.body and loops[1] in n.body
            )
            at = owner.body.index(loops[1])
            owner.body[at:at] = ast.parse(
                "late_callback((cell, membrane, bath, vm, fm, fg, vgj, egj, exy, opening), observe)"
            ).body
        out.append(ast.unparse(ast.fix_missing_locations(node)))
    target = ROOT / "src/cells/processes/betse_normal_channel_join.py"
    data = target.read_text()
    assert "def _pump_material_step(" not in data
    target.write_text(data + "\n\n" + "\n\n\n".join(out) + "\n")


if __name__ == "__main__":
    append_material_seams()
