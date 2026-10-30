"""Stdlib-only source audit and literal adapter generation; no numerical runs."""

import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0")
INSTALLED = Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
FAMILIES = {
    "Na": ("vg_na.py", "VgNaABC"),
    "K": ("vg_k.py", "VgKABC"),
    "Ca": ("vg_ca.py", "VgCaABC"),
    "Cl": ("vg_cl.py", "VgClABC"),
    "Fun": ("vg_funny.py", "VgFunABC"),
    "Cat": ("cation.py", "CationABC"),
    "ML": ("vg_morrislecar.py", "VgKABC"),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return dict(expression=ast.unparse(node))


def assignments(node):
    result = {}
    for n in ast.walk(node):
        if isinstance(n, ast.Assign):
            for target in n.targets:
                if isinstance(target, ast.Attribute) and ast.unparse(target.value) == "self":
                    result[target.attr] = literal(n.value)
    return result


def roles(family, name):
    if family in ("Na", "K", "Ca", "Cl"):
        return [(family, 1.0)]
    if family == "Fun":
        return [("Na", 0.33 if name == "HCNLeak" else 0.2), ("K", 1.0), ("Ca", 0.05)]
    if family == "Cat":
        return [("Na", 1.0), ("K", 1.0), ("Ca", 0.0 if name == "CatLeak" else 1.0)]
    if name in ("HCN2_ML", "HCN4_ML"):
        return [("K", 1.0), ("Na", 0.2)]
    if name == "Nav_ML":
        return [("Na", 1.0)]
    return [("Ca" if name.startswith("Cav_") else "K", 1.0)]


def oracle(family, name):
    if family == "Na":
        return "validation/channels/sodium_catalog_reference.py"
    if family == "K":
        return (
            "validation/tissue/kv1_reference.py"
            if name.startswith("Kv1p")
            else "validation/channels/potassium_catalog_reference.py"
        )
    if family == "Ca":
        return (
            "validation/channels/calcium_catalog_extra_reference.py"
            if name in ("Ca_L2", "Ca_L3", "Cav_G", "CaLeak")
            else "validation/tissue/cav_reference.py"
        )
    if family == "Fun":
        return (
            "validation/channels/hcn_extra_reference.py"
            if name in ("HCNLeak", "HCN2_cAMP", "HCN4_cAMP")
            else "validation/tissue/hcn_reference.py"
        )
    if family in ("Cl", "Cat"):
        return "validation/channels/leak_channels_reference.py"
    return "validation/channels/morris_lecar_channels_reference.py"


class Clean(ast.NodeTransformer):
    """Remove logs/docstrings/abstract stubs; numerical statements are literal."""

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        if isinstance(node.value, ast.Call) and ast.unparse(node.value.func).startswith("logs."):
            return None
        return self.generic_visit(node)


def prepare():
    owned = ROOT / "src/cells/processes/betse_channel_catalog_source.py"
    inventory_path = ROOT / "validation/betse/betse_normal_catalog_join_inventory.json"
    if owned.exists() or inventory_path.exists():
        raise FileExistsError("Static catalog adapter already prepared")
    pins, entries, emitted, audits = {}, {}, [], {}
    abc_path = "betse/science/channels/channelsabc.py"
    paths = [abc_path] + ["betse/science/channels/" + path for path, _ in FAMILIES.values()]
    for path in paths:
        assert (NATIVE / path).read_bytes() == (INSTALLED / path).read_bytes(), path
        pins[path] = sha(NATIVE / path)
    clock = next(
        n for n in ast.parse((NATIVE / abc_path).read_text()).body if isinstance(n, ast.ClassDef)
    )
    methods = [
        Clean().visit(copy.deepcopy(n))
        for n in clock.body
        if isinstance(n, ast.FunctionDef) and n.name in ("update_mh", "update_ml")
    ]
    clock_port = ast.ClassDef(name="_Clock", bases=[], keywords=[], body=methods, decorator_list=[])
    emitted.append(clock_port)
    for family, (filename, base_name) in FAMILIES.items():
        relative = "betse/science/channels/" + filename
        classes = [
            n
            for n in ast.parse((NATIVE / relative).read_text()).body
            if isinstance(n, ast.ClassDef)
        ]
        base = next(n for n in classes if n.name == base_name)
        base_methods = [
            Clean().visit(copy.deepcopy(n))
            for n in base.body
            if isinstance(n, ast.FunctionDef) and n.name not in ("_init_state", "_calculate_state")
        ]
        emitted.append(
            ast.ClassDef(
                name="_" + family + "Base",
                bases=[ast.Name(id="_Clock", ctx=ast.Load())],
                keywords=[],
                body=base_methods,
                decorator_list=[],
            )
        )
        for node in classes:
            if node.name == base_name:
                continue
            name = node.name
            functions = [n for n in node.body if isinstance(n, ast.FunctionDef)]
            out = [Clean().visit(copy.deepcopy(n)) for n in functions]
            emitted.append(
                ast.ClassDef(
                    name="_" + name,
                    bases=[ast.Name(id="_" + family + "Base", ctx=ast.Load())],
                    keywords=[],
                    body=out,
                    decorator_list=[],
                )
            )
            fields = assignments(node)
            transport = roles(family, name)
            entries[name] = dict(
                family=family,
                source=relative,
                original_base=base_name,
                source_lines=[node.lineno, node.end_lineno],
                source_class_AST_sha256=hashlib.sha256(
                    ast.dump(node, include_attributes=False).encode()
                ).hexdigest(),
                source_assignments=fields,
                routes=transport,
                requires_live_calcium=any(ion == "Ca" for ion, _ in transport),
                modern_gate_reads_calcium=False,
                modern_gate_temperature_scaling=False,
                clock="ML rational update with Phi"
                if family == "ML" and fields.get("kinetic_gate")
                else "algebraic, no consumed clock"
                if family == "ML"
                else "HH backward Euler including unused m/h",
                native_state_fields=sorted(fields),
                catalog_reference=oracle(family, name),
                catalog_reference_sha256=sha(ROOT / oracle(family, name)),
                scope="prepared_not_qualified",
                was_in_B28=name in ("Nav1p6", "Kv1p5", "Kv3p2", "ClLeak"),
            )
            audits[name] = {
                fn.name: hashlib.sha256(
                    ast.dump(Clean().visit(copy.deepcopy(fn)), include_attributes=False).encode()
                ).hexdigest()
                for fn in functions
            }
    assert len(entries) == 55
    assert sum(e["requires_live_calcium"] for e in entries.values()) == 23
    header = '''"""Literal native catalog class adapters; STATIC PREPARATION, NOT QUALIFIED.

Numerical method bodies adapted from BETSE1.5.0, revision5269a714aa2593ed2a6708c4516289977d8ae1a2.
Original equations by Alexis Pietak and Cecil Curry. Source metadata and exact
AST adaptation audit: validation/betse/betse_normal_catalog_join_inventory.json.
Only docstrings/logging/abstract stubs and class names/inheritance are removed.
No regularization, gate clipping, thermal scaling or implicit calcium inputs.
"""

import numpy as np
from types import SimpleNamespace

'''
    body = ast.unparse(ast.fix_missing_locations(ast.Module(body=emitted, type_ignores=[])))
    registry = (
        "\n\nCLASSES = {\n" + "".join(repr(name) + ": _" + name + ",\n" for name in entries) + "}\n"
    )
    routes = (
        "ROUTES = "
        + repr({name: tuple(tuple(v) for v in e["routes"]) for name, e in entries.items()})
        + "\n"
    )
    tail = """
def initialize(class_name, voltage, targets):
    core = CLASSES[class_name]()
    # The native network constructor does not force an integer dtype for an
    # empty profile list; retain its initialization refusal.
    core.init(voltage, SimpleNamespace(mem_i=np.arange(len(voltage))),
              SimpleNamespace(), targets=np.asarray(targets))
    core.chan_flux = np.zeros(len(voltage))
    core.DChan = None
    return dict(vars(core))


def update(class_name, incoming, voltage, dt_s, modulator):
    core = object.__new__(CLASSES[class_name])
    vars(core).update({key: value.copy() if isinstance(value, np.ndarray) else value
                      for key, value in incoming.items()})
    core.modulator = modulator
    core.run(voltage, SimpleNamespace(dt=dt_s))
    return dict(vars(core))
"""
    owned.write_text(header + body + registry + routes + tail)
    inventory = dict(
        kind="cells.native_channel_catalog_static_inventory@1",
        status="prepared_not_executed_not_qualified",
        revision="5269a714aa2593ed2a6708c4516289977d8ae1a2",
        checkout=str(NATIVE),
        installed=str(INSTALLED),
        source_sha256=pins,
        classes=entries,
        class_count=55,
        no_calcium_route_classes=32,
        calcium_route_classes=23,
        new_classes_beyond_B28=51,
        literal_numeric_method_AST_sha256=audits,
        generated_module=str(owned.relative_to(ROOT)),
        generated_sha256=sha(owned),
        legacy=dict(
            name="cagPotassium",
            kind="legacy standalone function, not Channel class",
            runtime_callsite_found=False,
            source="betse/science/tissue/channels_o.py",
            source_sha256=sha(NATIVE / "betse/science/tissue/channels_o.py"),
            requirements=[
                "current free cytosolic Ca gathered by membrane owner",
                "live T",
                "original whole-row Dm_cag assignment/shape quirks",
                "explicit separate chronology; no modern network insertion",
            ],
        ),
        required_calcium_policy=dict(
            supported_static=dict(alpha_Ca=0.0, Ca_dyn=0),
            live_rows=["bulk free Ca", "at-membrane Ca", "scalar external Ca"],
            never_hold_Ca_constant=True,
            deferred=[
                "alpha_Ca>0 CaATP pump and rate/cache/maintained pools",
                "Ca_dyn1 ER update and ER/buffer state",
            ],
        ),
        numerical_runs=0,
        numerical_imports=0,
        automatic_launch=False,
    )
    inventory_path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            dict(classes=55, live_calcium=23, no_calcium=32, generated=str(owned), numerical_runs=0)
        )
    )


if __name__ == "__main__":
    prepare()
