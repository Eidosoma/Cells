# ruff: noqa: E501
"""Audit reachability, then emit isolated new-prefix source/native files as text."""

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PIN = Path("/mnt/workspaces/Cells/betse-v1.5.0")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
OLD = "betse_ecm_grn"
NEW = "betse_ecm_charged_grn"


def functions(text):
    return {
        n.name: ast.get_source_segment(text, n)
        for n in ast.parse(text).body
        if isinstance(n, ast.FunctionDef)
    }


def change(text, before, after):
    assert before in text, before
    return text.replace(before, after, 1)


def emit(relative, text):
    with (ROOT / relative).open("x") as stream:
        stream.write(text)


# The reachability check precedes any scientific-file emission. It parses only.
anchors = {}
for relative in (
    "betse/science/sim.py",
    "betse/science/parameters.py",
    "betse/science/chemistry/gene.py",
    "betse/science/chemistry/networks.py",
):
    path = PIN / relative
    raw = path.read_bytes()
    installed = Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages") / relative
    assert raw == installed.read_bytes()
    anchors[relative] = dict(sha256=hashlib.sha256(raw).hexdigest())
network_tree = ast.parse((PIN / "betse/science/chemistry/networks.py").read_text())
core = next(
    n for n in network_tree.body if isinstance(n, ast.ClassDef) and n.name == "MasterOfNetworks"
)
methods = {n.name: n for n in core.body if isinstance(n, ast.FunctionDef)}
tissue = methods["tissue_init"]
balance_guard = next(
    n
    for n in ast.walk(tissue)
    if isinstance(n, ast.If)
    and ast.unparse(n.test)
    == "p.substances_affect_charge and self.charge_has_been_balanced is False"
)
calls = [
    ast.unparse(n)
    for n in balance_guard.body
    if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
]
assert calls == ["self.bal_charge(Qcells, sim, 'cell', p)", "self.bal_charge(Qenv, sim, 'env', p)"]
assert isinstance(balance_guard.body[-1], ast.Assign)
assert ast.unparse(balance_guard.body[-1]) == "self.charge_has_been_balanced = True"
gene_tree = ast.parse((PIN / "betse/science/chemistry/gene.py").read_text())
reader = next(
    n
    for n in ast.walk(gene_tree)
    if isinstance(n, ast.FunctionDef) and n.name == "read_gene_config"
)
reader_calls = [
    ast.unparse(n.value)
    for n in reader.body
    if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
]
assert reader_calls[:2] == [
    "self.core.read_substances(sim, cells, substances_config, p)",
    "self.core.tissue_init(phase, substances_config)",
]
sim_tree = ast.parse((PIN / "betse/science/sim.py").read_text())
guards = [n for n in ast.walk(sim_tree) if isinstance(n, ast.If) and n.lineno in (884, 1306)]
assert len(guards) == 2 and all(ast.unparse(n.test) == "p.grn_enabled" for n in guards)
receipt = dict(
    kind="cells.ecm_charged_grn_reachability@1",
    reachable=True,
    static_only=True,
    native_source=anchors,
    original_cold_guard=[884, 900],
    original_dispatch_guard=[1306, 1319],
    charge_guard=ast.unparse(balance_guard.test),
    charge_guard_lines=[balance_guard.lineno, balance_guard.end_lineno],
    region_order=calls,
    balanced_flag_after_both_regions=True,
    no_mitochondrial_enable_override=True,
    no_scientific_execution=True,
)
emit(
    "agent-work/cells-worker-01/workfiles/betse_ecm_charged_grn_reachability_01.json",
    json.dumps(receipt, indent=2, sort_keys=True) + "\n",
)

charged = (ROOT / "src/cells/processes/betse_normal_charged_grn_source.py").read_text()
charged_functions = functions(charged)
source = (ROOT / f"src/cells/processes/{OLD}_source.py").read_text().replace(OLD, NEW)
source = change(
    source,
    "from collections.abc import MutableMapping",
    "from collections.abc import Mapping, MutableMapping",
)
source = source.replace("cells.ecm_grn_owner_cache@1", "cells.ecm_charged_grn_owner_cache@1")
source = change(
    source,
    "BetseSimConfException = ValueError",
    "BetseSimException = molecule_source.BetseSimException\n\n\n"
    "class BetseSimConfException(BetseSimException):\n    pass",
)
source = change(
    source,
    "    def bal_charge(self, Q, sim, tag, p):\n",
    "    def bal_charge(self, Q, sim, tag, p):\n"
    '        observe_balance(self, "before", Q, sim, tag, p)\n',
)
start = source.index("    def bal_charge(")
end = source.index("\n\nclass MasterOfGenes", start)
# The compensation method is the last method of this literal core class.
source = source[:end] + '\n        observe_balance(self, "after", Q, sim, tag, p)\n' + source[end:]
source = change(
    source,
    "clone, public, wire = qualified.clone, qualified.public, qualified.wire",
    "clone, public = qualified.clone, qualified.public\n"
    "ALIASES, OBJECTS = qualified.ALIASES, qualified.OBJECTS\n\n\n"
    + charged_functions["wire"]
    + "\n\n\n"
    + charged_functions["ionic_state"]
    + "\n\n\n"
    + charged_functions["observe_balance"],
)
source = change(
    source,
    'sim.iNa, sim.iK = sim.get_ion("Na"), sim.get_ion("K")',
    'sim.iNa, sim.iK, sim.iM = (sim.get_ion(name) for name in ("Na", "K", "M"))',
)
source = change(
    source,
    '        "simulator_fields",\n    }:',
    '        "simulator_fields",\n        "ionic_state",\n        "balance_events",\n    }:',
)
source = change(
    source,
    '    raw = incoming["wire"]\n',
    '    raw = incoming["wire"]\n'
    '    if "ionic_state" not in raw:\n'
    '        raise ValueError("Require complete ECM charged ionic snapshot")\n'
    '    if "balance_events" not in raw:\n'
    '        raise ValueError("Require ECM charged compensation observations")\n',
)
source = change(
    source,
    "    # The current packet's ionic boundary vector remains authoritative.",
    "    validate_ionic_cache(ctx, raw)\n"
    '    net._balance_events = clone(raw["balance_events"])\n'
    "    # The current packet's ionic boundary vector remains authoritative.",
)
source = change(
    source,
    'if not {"Na", "K"} <= set(ids):\n        raise ValueError("Require actual Na/K rows for the ECM network context")',
    'if not {"Na", "K", "M"} <= set(ids):\n'
    '        raise ValueError("Require actual Na/K/M rows for ECM charged compensation")',
)
source = change(
    source,
    '    if fault not in (None, "X", "Y"):',
    '    if fault not in (None, "cell_positive_excess", "cell_negative_excess",\n'
    '                      "env_positive_excess", "env_negative_excess"):',
)
source = change(
    source,
    'needed - set(row) != ({"Dm"} if fault == row["name"] else set())',
    "needed - set(row) != set()",
)
source = change(
    source,
    '    if definition["cold_publish"] and any(row["z"] != 0 for row in rows):\n'
    '        raise ValueError("Charged ECM cold compensation is separately scoped")\n',
    "",
)
source = change(
    source,
    "    g = binding.geometry_binding.geometry\n    cb = binding.geometry_binding.current_binding",
    "    g = binding.geometry_binding.geometry\n"
    "    cb = binding.geometry_binding.current_binding\n"
    '    for name, charge in (("Na", 1), ("K", 1), ("M", -1)):\n'
    "        if name not in cb.ion_ids or cb.kernel.valence[cb.ion_ids.index(name)] != charge:\n"
    '            raise ValueError("Require actual Na(+1), K(+1), M(-1) counterion rows")\n'
    '    if cb.ion_ids.index("M") in binding.kernel.moving:\n'
    '        raise ValueError("Declare the compensation M row stationary")',
)
source += """\n\ndef validate_ionic_cache(ctx, raw):
    if not isinstance(raw.get("ionic_state"), Mapping) or set(raw["ionic_state"]) != {"cc_cells", "cc_at_mem", "cc_env"}:
        raise ValueError("Require complete ECM charged ionic snapshot")
    for key, value in raw["ionic_state"].items():
        array = np.asarray(value)
        if array.shape != getattr(ctx.sim, key).shape or array.dtype.kind not in "fiu" or not np.isfinite(array).all():
            raise ValueError("Require original E-grid and M-membrane ionic cache shapes")
    if not isinstance(raw.get("balance_events"), (list, tuple)):
        raise ValueError("Require ECM charged compensation observations")
"""
emit(f"src/cells/processes/{NEW}_source.py", source)

join = (ROOT / f"src/cells/processes/{OLD}_join.py").read_text().replace(OLD, NEW)
join = join.replace(
    "betse_normal_ecm_grn_network_v1_5_0@1", "betse_normal_ecm_charged_grn_network_v1_5_0@1"
)
join = change(
    join,
    '    return _state(binding, parent, cached, definition["initial_controls"])',
    "    compensated = material.state(binding.material_binding, source.material_values(ctx.sim),\n"
    "                                 step_index=parent.step_index)\n"
    '    return _state(binding, compensated, cached, definition["initial_controls"])',
)
join = change(
    join,
    'stage="cold", cache=source.cache(ctx), material=parent',
    'stage="cold", cache=source.cache(ctx), material=parent,\n'
    "                                    partial_material=source.material_values(ctx.sim)",
)
emit(f"src/cells/processes/{NEW}_join.py", join)

native_network = (ROOT / f"validation/betse/{OLD}_native_network.py").read_text().replace(OLD, NEW)
native_network = change(
    native_network,
    "from collections import OrderedDict",
    "from collections import OrderedDict\nfrom collections.abc import Mapping",
)
native_network = change(
    native_network,
    "clone, public, wire = previous.clone, previous.public, previous.wire",
    "clone, public = previous.clone, previous.public\n"
    "ALIASES, OBJECTS = previous.ALIASES, previous.OBJECTS\n\n\n"
    + charged_functions["wire"]
    + "\n\n\n"
    + charged_functions["ionic_state"]
    + "\n\n\n"
    + charged_functions["observe_balance"],
)
native_network = change(
    native_network,
    "    nodes = previous.literal_nodes(root)\n",
    "    nodes = previous.literal_nodes(root)\n"
    '    core = next(n for n in nodes if isinstance(n, ast.ClassDef) and n.name == "MasterOfNetworks")\n'
    '    balance = next(n for n in core.body if isinstance(n, ast.FunctionDef) and n.name == "bal_charge")\n'
    "    balance.body.insert(0, ast.parse(\"observe_balance(self, 'before', Q, sim, tag, p)\").body[0])\n"
    "    balance.body.append(ast.parse(\"observe_balance(self, 'after', Q, sim, tag, p)\").body[0])\n"
    '    exceptions = ast.parse((root / "exceptions.py").read_text())\n'
    '    nodes.append(copy.deepcopy(next(n for n in exceptions.body if isinstance(n, ast.ClassDef) and n.name == "BetseSimConfException")))\n',
)
native_network = change(
    native_network,
    "        ns = previous.authenticated()\n",
    '        ns = previous.authenticated()\n        ns["observe_balance"] = observe_balance\n',
)
# All non-scientific adapters are the same reviewed source bridge. Scientific
# namespace and actual original AST construction stay native-owned above.
source_functions = functions(source)
native_functions = functions(native_network)
for name in (
    "augment",
    "cache",
    "cold",
    "restore",
    "validate_definition",
    "validate",
    "validate_ionic_cache",
    "owner_evidence",
    "before",
    "attach",
    "run_dispatch",
    "new_trace",
):
    if name in native_functions:
        native_network = change(native_network, native_functions[name], source_functions[name])
    else:
        native_network += "\n\n" + source_functions[name] + "\n"
emit(f"validation/betse/{NEW}_native_network.py", native_network)
native = (ROOT / f"validation/betse/{OLD}_native.py").read_text().replace(OLD, NEW)
native = change(
    native,
    "            cold_failure=network.cache(ctx),",
    "            cold_failure=network.cache(ctx),\n            cold_partial_material=values(),",
)
native = change(
    native,
    "        cold_cache=cold_cache,",
    "        cold_cache=cold_cache,\n"
    '        compensated_parent={key: value for key, value in cold_cache["wire"]["ionic_state"].items()},',
)
emit(f"validation/betse/{NEW}_native.py", native)
print(
    json.dumps(
        {"reachability": True, "new_scientific_files_emitted": 4, "scientific_evaluation": False}
    )
)
