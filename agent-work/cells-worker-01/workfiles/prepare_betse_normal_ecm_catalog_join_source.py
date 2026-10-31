# ruff: noqa: E501
"""Emit owned adapters from text/AST only; never import scientific modules."""

import ast
import copy
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")
PREFIX = "betse_normal_ecm_catalog_join"
WORK = ROOT / "agent-work/cells-worker-01/workfiles"


def parsed(path):
    return ast.parse(path.read_text())


def node(tree, name):
    return copy.deepcopy(next(n for n in tree.body if getattr(n, "name", None) == name))


class Clean(ast.NodeTransformer):
    def visit_Expr(self, value):
        if isinstance(value.value, ast.Constant) and isinstance(value.value.value, str):
            return None
        return self.generic_visit(value)

    def visit_FunctionDef(self, value):
        value.decorator_list = []
        value.returns = None
        for arg in (*value.args.posonlyargs, *value.args.args, *value.args.kwonlyargs):
            arg.annotation = None
        return self.generic_visit(value)


def hook(stage):
    return ast.parse("p._catalog_observe(" + repr(stage) + ", name, locals())").body


class Observe(ast.NodeTransformer):
    def visit_Assign(self, value):
        target = ast.unparse(value.targets[0])
        stage = {
            "chan": "population_before",
            "moddy": "modulator",
            "ioni": "route_before",
            "f_ED": "flux_after",
            "chan.channel_core.DChan": "route_after",
            "obj.alpha_eval_string": "configuration_after",
        }.get(target)
        return [value, *hook(stage)] if stage else value

    def visit_Expr(self, value):
        if not isinstance(value.value, ast.Call):
            return value
        called = ast.unparse(value.value.func)
        if called == "obj.init_channel":
            return [*hook("initialize_before"), value, *hook("initialize_after")]
        if called == "chan.channel_core.run":
            return [value, *hook("gate_after")]
        return value

    def visit_For(self, value):
        value = self.generic_visit(value)
        if ast.unparse(value.iter).startswith("zip(chan.channel_core.ions,"):
            return [value, *hook("population_after")]
        return value


def literal_additions(root):
    tree = parsed(root / "science/chemistry/networks.py")
    master = node(tree, "MasterOfNetworks")
    methods = [
        Observe().visit(Clean().visit(copy.deepcopy(n)))
        for n in master.body
        if isinstance(n, ast.FunctionDef) and n.name in {"read_channels", "run_loop_channels"}
    ]
    channel = Clean().visit(node(tree, "Channel"))
    channel.body = [
        n
        for n in channel.body
        if isinstance(n, ast.FunctionDef) and n.name in {"__init__", "init_channel"}
    ]
    return methods, channel


HEADER = '''# ruff: noqa: E501, E402
"""Owned literal modern-channel reader, factory, dispatch and complete caches.

Normal ECM SIM only. Numeric class methods and lower ECM math stay unchanged.
Gate-private fields are retained, and cold initializer failures remain raw.
"""
import copy
import math
from collections import OrderedDict
from collections.abc import Mapping
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_ecm_grn_source as base
from cells.processes import betse_channel_catalog_source as catalog

clone, public = base.clone, base.public
MATERIAL_PAIRS, PARAMETERS = base.MATERIAL_PAIRS, base.PARAMETERS
logs, set_net_opts = base.logs, base.set_net_opts
BetseSimConfException = ValueError
SimPhaseKind = SimpleNamespace(INIT="INIT", SIM="SIM")
stb = SimpleNamespace(molecule_mover=base.molecule_mover,
    no_negs=base.molecule_source.no_negs, electroflux=base.electroflux, update_Co=base.update_Co)
material_values, owner_evidence = base.material_values, base.owner_evidence
new_trace = base.new_trace
'''

PLUMBING = """
def validate_catalog(declaration, ids, m):
    if (set(declaration) != {"kind", "populations", "tissue_profiles", "phase", "provenance"}
        or declaration["kind"] != "cells.native_ECM_modern_channel_configuration@1"
        or declaration["phase"] != "SIM"):
        raise ValueError("Require separately declared normal SIM channel configuration")
    if not isinstance(declaration["provenance"], str) or not declaration["provenance"].strip():
        raise ValueError("Require channel configuration provenance")
    profiles = declaration["tissue_profiles"]
    if not isinstance(profiles, dict) or any(
        not isinstance(k, str) or not k or not isinstance(v, list)
        or any(type(i) is not int or not 0 <= i < m for i in v)
        for k, v in profiles.items()):
        raise ValueError("Require explicit prepared tissue membrane index maps")
    rows = declaration["populations"]
    if rows is None:
        return
    if not isinstance(rows, list) or len(rows) > 16:
        raise ValueError("Require bounded ordered native channel populations")
    names = []
    for row in rows:
        required = {"name", "channel class", "channel type", "apply to"}
        allowed = required | {"max Dm", "max conductivity", "init active"} | {
            k for role in ("activator", "inhibitor")
            for k in ("channel " + role + "s", role + " Km", role + " n", role + " zone")}
        if not isinstance(row, dict) or not required <= row.keys() or set(row) - allowed:
            raise ValueError("Unsupported modern channel configuration branch")
        name, cls, family = row["name"], row["channel type"], row["channel class"]
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("Require unique native channel names")
        names.append(name)
        if cls not in FAMILIES or FAMILIES[cls] != family:
            raise ValueError("Require a reachable modern catalog factory class")
        if any(ion not in ids for ion, _ in ROUTES[cls]):
            raise ValueError("Require every original channel route ion role")
        conductance = row.get("max conductivity", None)
        maximum = conductance if conductance is not None else row.get("max Dm", None)
        if type(maximum) not in (float, int) or not math.isfinite(maximum) or maximum < 0:
            raise ValueError("Require finite nonnegative native channel maximum")
        if type(row.get("init active", True)) is not bool:
            raise ValueError("Require the original Boolean init active flag")
        targets = row["apply to"]
        if targets == "express":
            raise ValueError("Expression profiles require separately owned expression/tissue state")
        if targets not in (None, "all"):
            if not isinstance(targets, list) or any(k not in profiles for k in targets):
                raise ValueError("Require explicit prepared tissue membrane index maps")
        for role in ("activator", "inhibitor"):
            species = row.get("channel " + role + "s")
            if species is None:
                if any(row.get(role + " " + key) is not None for key in ("Km", "n", "zone")):
                    raise ValueError("Require complete native channel modifier lists")
                continue
            if not isinstance(species, list) or not 1 <= len(species) <= 4:
                raise ValueError("Require complete native channel modifier lists")
            for key in ("Km", "n"):
                values = row.get(role + " " + key)
                if (not isinstance(values, list) or len(values) != len(species)
                    or any(type(v) not in (float,int) or not math.isfinite(v) or v <= 0
                           for v in values)):
                    raise ValueError("Require complete native channel modifier lists")
            zones = row.get(role + " zone")
            if zones is not None and (not isinstance(zones, list) or len(zones) != len(species)
                                     or any(z not in ("mem", "env") for z in zones)):
                raise ValueError("Require explicit membrane/environment channel modifier zones")
            if any(value not in set(ids) | {"X", "Y"} for value in species):
                raise ValueError("Channel expression labels require separately qualified regulation")


def configure(ctx, declaration):
    validate_catalog(declaration, ctx.ion_ids, len(ctx.cells.mem_i))
    ctx.catalog = clone(declaration)
    ctx.definition = clone(ctx.definition)
    ctx.definition["configuration"]["channels"] = clone(declaration["populations"])
    ctx.p.grn = SimpleNamespace(conf=clone(ctx.definition["configuration"]))
    prepared = {key: np.asarray(value, np.int64).copy()
                for key, value in declaration["tissue_profiles"].items()}
    ctx.sim.dyna = SimpleNamespace(tissue_target_inds=prepared)
    ctx.phase.dyna = ctx.sim.dyna
    ctx.initial_channel_fields = {}
    ctx.channel_calls = {row["name"]: 0 for row in declaration["populations"] or []}
    ctx.trace.update(channel_events=[], channel_initializations=[])
    install_channel_observer(ctx)
    return ctx


def channel_fields(net):
    return {name: dict(
        fields={k: clone(v) for k,v in vars(obj).items() if k != "channel_core"},
        core_class=getattr(obj, "channel_type", None),
        core_fields=None if not hasattr(obj, "channel_core") else clone(vars(obj.channel_core)))
        for name, obj in getattr(net, "channels", {}).items()}


def wire(owner, sim):
    result = base.wire(owner, sim)
    net = getattr(owner, "core", None) if owner is not None else None
    result["channel_fields"] = {} if net is None else channel_fields(net)
    return result


def cache(ctx):
    return dict(
        kind="cells.ecm_catalog_grn_owner_cache@1",
        wire=wire(getattr(ctx.sim, "grn", None), ctx.sim),
        coefficient_fields={name: clone(getattr(ctx.sim, name))
            for name in ("D_env_weight", "D_env_weight_base", "TJ_targets")
            if hasattr(ctx.sim, name)},
        initial_channel_fields=clone(ctx.initial_channel_fields),
        channel_calls=clone(ctx.channel_calls))


def cold(ctx):
    ctx.sim.grn = None
    ctx.phase.kind = "INIT"
    ctx.p.substances_affect_charge = ctx.definition["cold_publish"]
    science()["initialize_owner"](ctx.sim, 0.0, ctx.phase, ctx.cells, ctx.p)
    ctx.initial_channel_fields = channel_fields(ctx.sim.grn.core)
    return cache(ctx)


def install_channel_observer(ctx):
    def observe(stage, name, local):
        obj = local.get("chan", local.get("obj"))
        # Constructor hooks have obj; warm hooks have chan. Preserve raw absent fields.
        values = dict(
            stage=stage, name=name, values=material_values(ctx.sim),
            cache=cache(ctx),
            fields={key: clone(local[key]) for key in
                    ("ion", "rel_perm", "zzz", "ioni", "DChan", "cenv", "ccell", "cmem", "f_ED", "moddy")
                    if key in local},
            population=None if obj is None else dict(
                fields={k: clone(v) for k,v in vars(obj).items() if k != "channel_core"},
                core_fields=None if not hasattr(obj, "channel_core") else clone(vars(obj.channel_core))),
            incoming_current=clone(ctx.sim.grn.core.extra_J_mem))
        if stage.startswith("initialize") or stage == "configuration_after":
            ctx.trace["channel_initializations"].append(values)
        else:
            if stage == "population_after":
                ctx.channel_calls[name] += 1
                values["cache"] = cache(ctx)
            ctx.trace["channel_events"].append(values)
    ctx.p._catalog_observe = observe


def validate_cached_channels(ctx, incoming):
    rows = ctx.catalog["populations"] or []
    fields = incoming["wire"]["channel_fields"]
    initial = incoming["initial_channel_fields"]
    calls = incoming["channel_calls"]
    expected = [row["name"] for row in rows]
    if list(fields) != expected or list(initial) != expected or list(calls) != expected:
        raise ValueError("Require every configured channel and complete constructor/cache metadata")
    for row in rows:
        name, cls = row["name"], row["channel type"]
        current, origin = fields[name], initial[name]
        if (set(current) != {"fields", "core_class", "core_fields"}
            or set(origin) != set(current) or current["core_class"] != cls
            or origin["core_class"] != cls or current["core_fields"] is None
            or origin["core_fields"] is None
            or type(calls[name]) is not int or not 0 <= calls[name] <= 3
            or set(current["fields"]) != set(origin["fields"])):
            raise ValueError("Require every configured channel and complete constructor/cache metadata")
        a, b = current["core_fields"], origin["core_fields"]
        warm = set() if calls[name] == 0 else (
            {"P", "_mInf", "_mTau"} if FAMILIES[cls] == "ML"
            else {"P", "_mInf", "_mTau", "_hInf", "_hTau"})
        if set(a) != set(b) | warm:
            raise ValueError("Require all source-private initialized and hot gate fields")
        for key in ("targets", "data_length", "mdl", "ions", "rel_perm", "time_unit"):
            if key in b and not np.array_equal(a.get(key), b[key]):
                raise ValueError("Changed native channel routing or constructor metadata")
        targets = []
        if row["apply to"] in (None, "all"):
            targets = list(ctx.cells.mem_i)
        else:
            for key in row["apply to"]:
                targets.extend(ctx.catalog["tissue_profiles"][key])
        if not np.array_equal(b.get("targets"), targets):
            raise ValueError("Changed native channel routing or constructor metadata")
        if current["fields"]["name"] != name or current["fields"]["channel_type"] != cls:
            raise ValueError("Changed native channel routing or constructor metadata")
        for state in (a,b):
            if not finite_tree(state):
                raise ValueError("Port requires finite complete channel caches; native return retained")
    actual_flag = ctx.catalog["populations"] is not None
    if incoming["wire"]["owner_fields"].get("channels") is not actual_flag:
        raise ValueError("Require the actual cold-configured channel owner flag")


def finite_tree(value):
    if isinstance(value, Mapping):
        return all(finite_tree(v) for v in value.values())
    if isinstance(value, (tuple,list)):
        return all(finite_tree(v) for v in value)
    if isinstance(value, (np.ndarray,np.generic,float)):
        return bool(np.isfinite(value).all())
    return True
"""


def prepare():
    base_tree = parsed(ROOT / "src/cells/processes/betse_ecm_grn_source.py")
    methods, channel = literal_additions(NATIVE)
    master = ast.parse("class MasterOfNetworks(base.MasterOfNetworks):\n    pass").body[0]
    master.body = methods
    definitions = [
        master,
        channel,
        node(base_tree, "MasterOfGenes"),
        node(base_tree, "initialize_owner"),
        node(base_tree, "dispatch"),
    ]
    inventory = json.loads(
        (ROOT / "validation/betse/betse_normal_catalog_join_inventory.json").read_text()
    )
    families = {name: row["family"] for name, row in inventory["classes"].items()}
    routing = {name: row["routes"] for name, row in inventory["classes"].items()}
    assignments = "FAMILIES = " + repr(families) + "\nROUTES = " + repr(routing) + "\n"
    for family, module in {
        "Na": "vgna",
        "K": "vgk",
        "Cl": "vgcl",
        "Ca": "vgca",
        "Fun": "vgfun",
        "Cat": "vgcat",
        "ML": "vgml",
    }.items():
        assignments += (
            module
            + " = SimpleNamespace(**{name: catalog.CLASSES[name] for name, family in FAMILIES.items() if family == "
            + repr(family)
            + "})\n"
        )
    api = """\ndef science():
    return base.science() | dict(MasterOfGenes=MasterOfGenes, MasterOfNetworks=MasterOfNetworks,
        Channel=Channel, initialize_owner=initialize_owner, dispatch=dispatch, class_for=class_for)

def class_for(name):
    return catalog.CLASSES[name]
"""
    restore = ast.unparse(node(base_tree, "restore"))
    restore = restore.replace("cells.ecm_grn_owner_cache@1", "cells.ecm_catalog_grn_owner_cache@1")
    restore = restore.replace(
        "Require complete ECM GRN owner cache", "Require complete ECM catalog GRN owner cache"
    )
    restore = restore.replace("'simulator_fields'}", "'simulator_fields', 'channel_fields'}")
    restore = restore.replace(
        "    api = science()",
        "    validate_cached_channels(ctx, incoming)\n    ctx.initial_channel_fields = clone(incoming['initial_channel_fields'])\n    ctx.channel_calls = clone(incoming['channel_calls'])\n    api = science()",
    )
    restore = restore.replace("    # The current", "    # The current")
    # Place complete channel objects after the inherited empty object initialization.
    mark = "    for key, value in raw['simulator_fields'].items():"
    added = """    for name, saved in raw["channel_fields"].items():
        obj = object.__new__(api["Channel"])
        vars(obj).update(clone(saved["fields"]))
        core = object.__new__(api["class_for"](saved["core_class"]))
        vars(core).update(clone(saved["core_fields"]))
        obj.channel_core = core
        net.channels[name] = obj
"""
    assert mark in restore
    restore = restore.replace(mark, added + mark)
    before = ast.unparse(node(base_tree, "before"))
    attach = ast.unparse(node(base_tree, "attach"))
    old = "        if stage == 'clear_run_loop':\n            ctx.trace['before'] = before(ctx, material_declaration)\n            if observer is not None:\n                observer(clone(ctx.trace['before']))"
    new = """        if stage == 'clear_run_loop':
            ctx.trace['before_channels'] = before(ctx, material_declaration)
            ctx.trace['before_channels'].update(mode='channels', catalog=clone(ctx.catalog))
            if channel_observer is not None:
                channel_observer(clone(ctx.trace['before_channels']))
        if stage == 'run_loop_channels' or (stage == 'clear_run_loop' and not ctx.sim.grn.channels):
            ctx.trace['before'] = before(ctx, material_declaration)
            if observer is not None:
                observer(clone(ctx.trace['before']))"""
    assert old in attach
    attach = attach.replace(
        "def attach(ctx, material_declaration, observer=None):",
        "def attach(ctx, material_declaration, observer=None, channel_observer=None):",
    )
    attach = attach.replace(old, new)
    dispatch = ast.unparse(node(base_tree, "run_dispatch"))
    dispatch = dispatch.replace(
        "publication, observer=None",
        "publication, source_time_s, observer=None, channel_observer=None",
    )
    dispatch = dispatch.replace(
        "attach(ctx, material_declaration, observer)",
        "attach(ctx, material_declaration, observer, channel_observer)",
    )
    dispatch = dispatch.replace(
        "(ctx.sim, 0.0, ctx.phase, ctx.cells, ctx.p)",
        "(ctx.sim, source_time_s, ctx.phase, ctx.cells, ctx.p)",
    )
    body = (
        HEADER
        + assignments
        + "\n"
        + ast.unparse(ast.Module(body=definitions, type_ignores=[]))
        + api
        + PLUMBING
        + "\n"
        + restore
        + "\n\n"
        + before
        + "\n\n"
        + attach
        + "\n\n"
        + dispatch
        + "\n"
    )
    destination = ROOT / "src/cells/processes" / f"{PREFIX}_source.py"
    destination.write_text(body)
    # Native scientific bodies are constructed directly from authenticated original AST.
    native_header = '''# ruff: noqa: E501, E402
"""Fresh authenticated native namespace; complete cache/capture plumbing."""
import ast
import copy
import json
import math
from collections import OrderedDict
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from validation.betse import betse_ecm_grn_native_network as base
from validation.betse import betse_normal_catalog_join_native_helpers as catalog_native

clone, public = base.clone, base.public
MATERIAL_PAIRS, PARAMETERS = base.MATERIAL_PAIRS, base.PARAMETERS
material_values, owner_evidence = base.material_values, base.owner_evidence
new_trace = base.new_trace
PROTOCOL = Path(__file__).with_name("betse_normal_ecm_catalog_join_protocol.json")
_SCIENCE = None
'''
    # Copy ONLY stdlib AST construction code, never the emitted production classes.
    construction = "\n\n".join(
        ast.unparse(node(parsed(Path(__file__)), name))
        for name in ("parsed", "node", "Clean", "hook", "Observe", "literal_additions")
    )
    native_science = """
def literal_nodes(root):
    nodes = base.literal_nodes(root)
    methods, channel = literal_additions(root)
    master = next(n for n in nodes if getattr(n,"name",None) == "MasterOfNetworks")
    master.body.extend(methods)
    return nodes + [channel]

def science():
    global _SCIENCE
    if _SCIENCE is None:
        # Copy the namespace and recompile every selected body, so no shared class is mutated.
        ns = dict(base.science())
        channels, sites, pins = catalog_native.authenticated()
        for module in ("vgna","vgk","vgcl","vgca","vgfun","vgcat","vgml"):
            ns[module] = channels[module]
        ns["SimPhaseKind"] = SimpleNamespace(INIT="INIT",SIM="SIM")
        root=Path(pins["checkout"])/"betse"
        exec(compile(ast.fix_missing_locations(ast.Module(body=literal_nodes(root),type_ignores=[])),
            "<authenticated ECM modern factory and channel dispatch>","exec"),ns)
        ns["fd"] = SimpleNamespace(**{key:ns[key] for key in ("gradient","divergence","integrator")})
        ns["stb"] = SimpleNamespace(molecule_mover=ns["molecule_mover"],no_negs=ns["no_negs"],
            electroflux=ns["electroflux"],update_Co=ns["update_Co"])
        ns["class_for"] = lambda name: channels[name]
        _SCIENCE = ns
    return _SCIENCE
"""
    (ROOT / "validation/betse" / f"{PREFIX}_native_network.py").write_text(
        native_header
        + "FAMILIES = "
        + repr(families)
        + "\nROUTES = "
        + repr(routing)
        + "\n"
        + construction
        + native_science
        + PLUMBING
        + "\n"
        + restore
        + "\n\n"
        + before
        + "\n\n"
        + attach
        + "\n\n"
        + dispatch
        + "\n"
    )
    print("Emitted two owned source/native adapters from text/AST; science not imported/executed")


if __name__ == "__main__":
    prepare()
