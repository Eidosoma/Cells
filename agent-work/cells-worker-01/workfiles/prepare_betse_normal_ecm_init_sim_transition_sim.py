# ruff: noqa: E501
"""Prepare private SIM rate-entry/NaK adapters and the existing lifecycle body.

All common arithmetic/control bodies are copied from immutable INIT01's common
parent. Only the declared entry-cache guard, real NaK producer seam, phase-entry
receipt labels and private module binding change. No scientific AST is executed.
"""

import ast
import builtins
import copy
import symtable
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-01/source")
PREFIX = "betse_normal_ecm_init_sim_transition"


def fn(path, name):
    tree = ast.parse(path.read_text())
    return copy.deepcopy(
        next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    )


def aliases(node, excluded):
    table = symtable.symtable(
        ast.unparse(ast.fix_missing_locations(node)), "<private SIM adapter>", "exec"
    )
    known = set(dir(builtins)) | excluded | {"__name__", "__file__"}

    def walk(scope):
        out = {
            s.get_name()
            for s in scope.get_symbols()
            if s.is_global() and s.is_referenced() and s.get_name() not in known
        }
        for child in scope.get_children():
            out |= walk(child)
        return out

    return walk(table)


def main():
    path = PARENT / "src/cells/processes/betse_normal_ecm_event_mechanics.py"
    advance = fn(path, "_advance_events")
    for name, default in (
        ("entry_ca_rate_present", None),
        ("nak_rate_before", None),
        ("alpha_NaK", None),
        ("before_nak", ast.Constant(None)),
    ):
        advance.args.kwonlyargs.append(ast.arg(arg=name))
        advance.args.kw_defaults.append(default)

    class Guard(ast.NodeTransformer):
        def visit_Compare(self, node):
            if ast.unparse(node).startswith(
                "rate.present is not (binding.calcium['alpha_Ca'] > 0 and index > 0)"
            ):
                return ast.parse(
                    'rate.present is not (entry_ca_rate_present or (binding.calcium["alpha_Ca"] > 0 and index > 0))',
                    mode="eval",
                ).body
            return self.generic_visit(node)

    advance = Guard().visit(advance)
    block = next(n for n in advance.body if isinstance(n, ast.Try))
    i = next(
        i
        for i, n in enumerate(block.body)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "packet"
    )
    block.body[i:i] = ast.parse("""
pump_binding = SimpleNamespace(material_binding=runtime, inputs=dict(binding.inputs,definition=definition),
                               inputs_raw={"flags":{"alpha_NaK":alpha_NaK}})
pump_stores = dict(stores, rho_pump=1)
nak_phase, nak_flux, nak_proxy = pump.produce(pump_binding, lowered, pump_stores, nak_rate_before, before_nak)
holder["nak"] = nak_phase
holder["nak_rate_after"] = calcium_component.RateCache(True, nak_proxy)
if not pump.finite(nak_phase):
    raise ValueError("Nonfinite complete transitioned SIM NaK output")
""").body
    packet = next(
        n for n in block.body if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "packet"
    )
    packet.value.keywords.append(
        ast.keyword(
            arg="supplied_pump_membrane_flux_mol_m2_s",
            value=ast.Name(id="nak_flux", ctx=ast.Load()),
        )
    )
    inputs = next(
        n
        for n in block.body
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "material_input"
    )
    inputs.value.keywords.extend(
        [
            ast.keyword(
                arg="nak_before",
                value=ast.Subscript(
                    value=ast.Name(id="nak_phase", ctx=ast.Load()),
                    slice=ast.Constant("before"),
                    ctx=ast.Load(),
                ),
            )
        ]
    )
    on_network = next(
        n for n in block.body if isinstance(n, ast.FunctionDef) and n.name == "on_network"
    )
    j = next(
        i
        for i, n in enumerate(on_network.body)
        if isinstance(n, ast.Expr) and ast.unparse(n.value.func) == "source.run_dispatch"
    )
    on_network.body[j:j] = ast.parse("current.sim.rate_NaKATP = nak_proxy.copy()").body
    returned = next(n for n in block.body if isinstance(n, ast.Return))
    context = returned.value.elts[-1].args[0]
    context.keywords.extend(
        [
            ast.keyword(arg="nak", value=ast.Name(id="nak_phase", ctx=ast.Load())),
            ast.keyword(
                arg="nak_rate_after",
                value=ast.Subscript(
                    value=ast.Name(id="holder", ctx=ast.Load()),
                    slice=ast.Constant("nak_rate_after"),
                    ctx=ast.Load(),
                ),
            ),
        ]
    )
    outer = fn(path, "advance")
    # The common composition body passes the new explicit cache knobs through
    # its existing **callbacks seam; mechanics and acceptance are unchanged.
    header = f'''"""Private existing SIM composition with native retained-rate entry and NaK.

No shared body is patched. The phase handoff supplies actual incoming rate
caches explicitly; no fresh cold initialization is performed here.
"""

from types import SimpleNamespace

from cells.processes import betse_normal_ecm_event_mechanics as base
from cells.processes import {PREFIX}_pump as pump

Binding=base.Binding
State=base.State
bind=base.bind
verify_binding=base.verify_binding
verify=base.verify
event=base.event
full=base.full
source=base.source
sample=base.sample
'''
    seen = {"Binding", "State", "bind", "verify_binding", "verify", "event", "full", "source"}
    for node in (advance, outer):
        for name in sorted(
            aliases(node, {"_advance_events", "advance", "pump", "SimpleNamespace"})
        ):
            if name not in seen:
                header += name + " = base." + name + "\n"
                seen.add(name)
    with (ROOT / "src/cells/processes" / f"{PREFIX}_sim.py").open("x") as stream:
        stream.write(
            header
            + "\n\n"
            + "\n\n".join(ast.unparse(ast.fix_missing_locations(n)) for n in (advance, outer))
            + "\n"
        )
    # The already prepared NaK producer remains exact except phase metadata.
    old = (PARENT / "src/cells/processes/betse_normal_ecm_init_phase_pump.py").read_text()
    old = old.replace('source_phase="INIT"', 'source_phase="SIM"').replace(
        "legacy_run_sim=False", "legacy_run_sim=True"
    )
    old = old.replace(
        "Ordinary ECM NaK producer before movers", "Transitioned SIM NaK producer before movers"
    )
    with (ROOT / "src/cells/processes" / f"{PREFIX}_pump.py").open("x") as stream:
        stream.write(old)
    # Reuse the full existing lifecycle coordinator, with a private composition
    # module and accurate reinitialized entry labels instead of cold labels.
    lifecycle = (PARENT / "src/cells/processes/betse_normal_ecm_run_lifecycle.py").read_text()
    lifecycle = lifecycle.replace(
        "betse_normal_ecm_event_mechanics as composition", PREFIX + "_sim as composition"
    )
    lifecycle = lifecycle.replace(
        "betse_normal_ecm_headless_supplied_SIM_run_v1_5_0@1",
        "betse_normal_ecm_reinitialized_SIM_run_v1_5_0@1",
    )
    lifecycle = lifecycle.replace(
        "cells.normal_ecm_headless_run_inputs@1", "cells.normal_ecm_transitioned_run_inputs@1"
    )
    lifecycle = lifecycle.replace(
        "supplied_component_cold_bootstrap_subset", "supplied_reinitialized_INIT_to_SIM_subset"
    )
    lifecycle = lifecycle.replace(
        "Headless in-memory SIM/N3 lifecycle on explicitly supplied component entry.",
        "Headless SIM/N3 lifecycle on explicitly reinitialized INIT owners.",
    )
    with (ROOT / "src/cells/processes" / f"{PREFIX}_lifecycle.py").open("x") as stream:
        stream.write(lifecycle)
    for path in (ROOT / "src/cells/processes").glob(PREFIX + "*.py"):
        compile(path.read_text(), str(path), "exec")
    print("Prepared private SIM producer, rate guard and lifecycle coordinator")


if __name__ == "__main__":
    main()
