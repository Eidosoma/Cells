# ruff: noqa: E501, E402
"""Fresh authenticated native namespace; complete cache/capture plumbing."""

import ast
import copy
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
augment, validate_definition = base.augment, base.validate_definition
PROTOCOL = Path(__file__).with_name("betse_normal_ecm_catalog_join_protocol.json")
_SCIENCE = None
FAMILIES = {
    "CaLeak": "Ca",
    "Ca_L2": "Ca",
    "Ca_L3": "Ca",
    "CatLeak": "Cat",
    "CatLeak2": "Cat",
    "Cav1p2": "Ca",
    "Cav1p3": "Ca",
    "Cav2p1": "Ca",
    "Cav2p2": "Ca",
    "Cav2p3": "Ca",
    "Cav3p1": "Ca",
    "Cav3p3": "Ca",
    "Cav_G": "Ca",
    "Cav_L_ML": "ML",
    "Cav_L_ML2": "ML",
    "Cav_N_ML": "ML",
    "Cav_T_ML": "ML",
    "ClLeak": "Cl",
    "HCN1": "Fun",
    "HCN2": "Fun",
    "HCN2_ML": "ML",
    "HCN2_cAMP": "Fun",
    "HCN4": "Fun",
    "HCN4_ML": "ML",
    "HCN4_cAMP": "Fun",
    "HCNLeak": "Fun",
    "KLeak": "K",
    "K_Fast": "K",
    "Kir2p1": "K",
    "Kir_ML": "ML",
    "Kv1p1": "K",
    "Kv1p2": "K",
    "Kv1p3": "K",
    "Kv1p3_ML": "ML",
    "Kv1p4": "K",
    "Kv1p5": "K",
    "Kv1p5S_ML": "ML",
    "Kv1p5_ML": "ML",
    "Kv1p6": "K",
    "Kv2p1": "K",
    "Kv2p1_ML": "ML",
    "Kv2p2": "K",
    "Kv3p1": "K",
    "Kv3p2": "K",
    "Kv3p3": "K",
    "Kv3p4": "K",
    "Kv_ML1": "ML",
    "NaLeak": "Na",
    "Nav1p2": "Na",
    "Nav1p3": "Na",
    "Nav1p6": "Na",
    "NavRat1": "Na",
    "NavRat2": "Na",
    "NavRat3": "Na",
    "Nav_ML": "ML",
}
ROUTES = {
    "CaLeak": [["Ca", 1.0]],
    "Ca_L2": [["Ca", 1.0]],
    "Ca_L3": [["Ca", 1.0]],
    "CatLeak": [["Na", 1.0], ["K", 1.0], ["Ca", 0.0]],
    "CatLeak2": [["Na", 1.0], ["K", 1.0], ["Ca", 1.0]],
    "Cav1p2": [["Ca", 1.0]],
    "Cav1p3": [["Ca", 1.0]],
    "Cav2p1": [["Ca", 1.0]],
    "Cav2p2": [["Ca", 1.0]],
    "Cav2p3": [["Ca", 1.0]],
    "Cav3p1": [["Ca", 1.0]],
    "Cav3p3": [["Ca", 1.0]],
    "Cav_G": [["Ca", 1.0]],
    "Cav_L_ML": [["Ca", 1.0]],
    "Cav_L_ML2": [["Ca", 1.0]],
    "Cav_N_ML": [["Ca", 1.0]],
    "Cav_T_ML": [["Ca", 1.0]],
    "ClLeak": [["Cl", 1.0]],
    "HCN1": [["Na", 0.2], ["K", 1.0], ["Ca", 0.05]],
    "HCN2": [["Na", 0.2], ["K", 1.0], ["Ca", 0.05]],
    "HCN2_ML": [["K", 1.0], ["Na", 0.2]],
    "HCN2_cAMP": [["Na", 0.2], ["K", 1.0], ["Ca", 0.05]],
    "HCN4": [["Na", 0.2], ["K", 1.0], ["Ca", 0.05]],
    "HCN4_ML": [["K", 1.0], ["Na", 0.2]],
    "HCN4_cAMP": [["Na", 0.2], ["K", 1.0], ["Ca", 0.05]],
    "HCNLeak": [["Na", 0.33], ["K", 1.0], ["Ca", 0.05]],
    "KLeak": [["K", 1.0]],
    "K_Fast": [["K", 1.0]],
    "Kir2p1": [["K", 1.0]],
    "Kir_ML": [["K", 1.0]],
    "Kv1p1": [["K", 1.0]],
    "Kv1p2": [["K", 1.0]],
    "Kv1p3": [["K", 1.0]],
    "Kv1p3_ML": [["K", 1.0]],
    "Kv1p4": [["K", 1.0]],
    "Kv1p5": [["K", 1.0]],
    "Kv1p5S_ML": [["K", 1.0]],
    "Kv1p5_ML": [["K", 1.0]],
    "Kv1p6": [["K", 1.0]],
    "Kv2p1": [["K", 1.0]],
    "Kv2p1_ML": [["K", 1.0]],
    "Kv2p2": [["K", 1.0]],
    "Kv3p1": [["K", 1.0]],
    "Kv3p2": [["K", 1.0]],
    "Kv3p3": [["K", 1.0]],
    "Kv3p4": [["K", 1.0]],
    "Kv_ML1": [["K", 1.0]],
    "NaLeak": [["Na", 1.0]],
    "Nav1p2": [["Na", 1.0]],
    "Nav1p3": [["Na", 1.0]],
    "Nav1p6": [["Na", 1.0]],
    "NavRat1": [["Na", 1.0]],
    "NavRat2": [["Na", 1.0]],
    "NavRat3": [["Na", 1.0]],
    "Nav_ML": [["Na", 1.0]],
}


def parsed(path):
    return ast.parse(path.read_text())


def node(tree, name):
    return copy.deepcopy(next((n for n in tree.body if getattr(n, "name", None) == name)))


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
    return (methods, channel)


def literal_nodes(root):
    nodes = base.literal_nodes(root)
    methods, channel = literal_additions(root)
    master = next(n for n in nodes if getattr(n, "name", None) == "MasterOfNetworks")
    master.body.extend(methods)
    return nodes + [channel]


def science():
    global _SCIENCE
    if _SCIENCE is None:
        # Copy the namespace and recompile every selected body, so no shared class is mutated.
        ns = dict(base.science())
        channels, sites, pins = catalog_native.authenticated()
        for module in ("vgna", "vgk", "vgcl", "vgca", "vgfun", "vgcat", "vgml"):
            ns[module] = channels[module]
        ns["SimPhaseKind"] = SimpleNamespace(INIT="INIT", SIM="SIM")
        root = Path(pins["checkout"]) / "betse"
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=literal_nodes(root), type_ignores=[])),
                "<authenticated ECM modern factory and channel dispatch>",
                "exec",
            ),
            ns,
        )
        ns["fd"] = SimpleNamespace(
            **{key: ns[key] for key in ("gradient", "divergence", "integrator")}
        )
        ns["stb"] = SimpleNamespace(
            molecule_mover=ns["molecule_mover"],
            no_negs=ns["no_negs"],
            electroflux=ns["electroflux"],
            update_Co=ns["update_Co"],
        )
        ns["class_for"] = lambda name: channels[name]
        _SCIENCE = ns
    return _SCIENCE


def validate_catalog(declaration, ids, m):
    if (
        set(declaration) != {"kind", "populations", "tissue_profiles", "phase", "provenance"}
        or declaration["kind"] != "cells.native_ECM_modern_channel_configuration@1"
        or declaration["phase"] != "SIM"
    ):
        raise ValueError("Require separately declared normal SIM channel configuration")
    if not isinstance(declaration["provenance"], str) or not declaration["provenance"].strip():
        raise ValueError("Require channel configuration provenance")
    profiles = declaration["tissue_profiles"]
    if not isinstance(profiles, dict) or any(
        not isinstance(k, str)
        or not k
        or not isinstance(v, list)
        or any(type(i) is not int or not 0 <= i < m for i in v)
        for k, v in profiles.items()
    ):
        raise ValueError("Require explicit prepared tissue membrane index maps")
    rows = declaration["populations"]
    if rows is None:
        return
    if not isinstance(rows, list) or len(rows) > 16:
        raise ValueError("Require bounded ordered native channel populations")
    names = []
    for row in rows:
        required = {"name", "channel class", "channel type", "apply to"}
        allowed = (
            required
            | {"max Dm", "max conductivity", "init active"}
            | {
                k
                for role in ("activator", "inhibitor")
                for k in ("channel " + role + "s", role + " Km", role + " n", role + " zone")
            }
        )
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
                if (
                    not isinstance(values, list)
                    or len(values) != len(species)
                    or any(
                        type(v) not in (float, int) or not math.isfinite(v) or v <= 0
                        for v in values
                    )
                ):
                    raise ValueError("Require complete native channel modifier lists")
            zones = row.get(role + " zone")
            if zones is not None and (
                not isinstance(zones, list)
                or len(zones) != len(species)
                or any(z not in ("cell", "env") for z in zones)
            ):
                raise ValueError("Require explicit membrane/environment channel modifier zones")
            if any(value not in set(ids) | {"X", "Y"} for value in species):
                raise ValueError(
                    "Channel expression labels require separately qualified regulation"
                )


def configure(ctx, declaration):
    validate_catalog(declaration, ctx.ion_ids, len(ctx.cells.mem_i))
    ctx.catalog = clone(declaration)
    ctx.definition = clone(ctx.definition)
    ctx.definition["configuration"]["channels"] = clone(declaration["populations"])
    ctx.p.grn = SimpleNamespace(conf=clone(ctx.definition["configuration"]))
    prepared = {
        key: np.asarray(value, np.int64).copy()
        for key, value in declaration["tissue_profiles"].items()
    }
    ctx.sim.dyna = SimpleNamespace(tissue_target_inds=prepared)
    ctx.phase.dyna = ctx.sim.dyna
    ctx.initial_channel_fields = {}
    ctx.channel_calls = {row["name"]: 0 for row in declaration["populations"] or []}
    ctx.trace.update(channel_events=[], channel_initializations=[])
    install_channel_observer(ctx)
    return ctx


def channel_fields(net):
    return {
        name: dict(
            fields={k: clone(v) for k, v in vars(obj).items() if k != "channel_core"},
            core_class=getattr(obj, "channel_type", None),
            core_fields=None if not hasattr(obj, "channel_core") else clone(vars(obj.channel_core)),
        )
        for name, obj in getattr(net, "channels", {}).items()
    }


def wire(owner, sim):
    result = base.wire(owner, sim)
    net = getattr(owner, "core", None) if owner is not None else None
    result["channel_fields"] = {} if net is None else channel_fields(net)
    return result


def cache(ctx):
    return dict(
        kind="cells.ecm_catalog_grn_owner_cache@1",
        wire=wire(getattr(ctx.sim, "grn", None), ctx.sim),
        coefficient_fields={
            name: clone(getattr(ctx.sim, name))
            for name in ("D_env_weight", "D_env_weight_base", "TJ_targets")
            if hasattr(ctx.sim, name)
        },
        initial_channel_fields=clone(ctx.initial_channel_fields),
        channel_calls=clone(ctx.channel_calls),
    )


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
            stage=stage,
            name=name,
            values=material_values(ctx.sim),
            cache=cache(ctx),
            fields={
                key: clone(local[key])
                for key in (
                    "ion",
                    "rel_perm",
                    "zzz",
                    "ioni",
                    "DChan",
                    "cenv",
                    "ccell",
                    "cmem",
                    "f_ED",
                    "moddy",
                )
                if key in local
            },
            population=None
            if obj is None
            else dict(
                fields={k: clone(v) for k, v in vars(obj).items() if k != "channel_core"},
                core_fields=None
                if not hasattr(obj, "channel_core")
                else clone(vars(obj.channel_core)),
            ),
            incoming_current=clone(ctx.sim.grn.core.extra_J_mem),
        )
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
        if (
            set(current) != {"fields", "core_class", "core_fields"}
            or set(origin) != set(current)
            or current["core_class"] != cls
            or origin["core_class"] != cls
            or current["core_fields"] is None
            or origin["core_fields"] is None
            or type(calls[name]) is not int
            or not 0 <= calls[name] <= 3
            or set(current["fields"]) != set(origin["fields"])
        ):
            raise ValueError(
                "Require every configured channel and complete constructor/cache metadata"
            )
        a, b = current["core_fields"], origin["core_fields"]
        warm = (
            set()
            if calls[name] == 0
            else (
                {"P", "_mInf", "_mTau"}
                if FAMILIES[cls] == "ML"
                else {"P", "_mInf", "_mTau", "_hInf", "_hTau"}
            )
        )
        if set(a) != set(b) | warm:
            raise ValueError("Require all source-private initialized and hot gate fields")
        if not equal_tree(current["fields"], origin["fields"]):
            raise ValueError("Changed native channel routing or constructor metadata")
        dynamic = {
            "m",
            "h",
            "P",
            "modulator",
            "chan_flux",
            "DChan",
            "_mInf",
            "_mTau",
            "_hInf",
            "_hTau",
        }
        for key in set(b) - dynamic:
            if not equal_tree(a.get(key), b[key]):
                raise ValueError("Changed native channel routing or constructor metadata")
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
        for state in (a, b):
            if not finite_tree(state):
                raise ValueError(
                    "Port requires finite complete channel caches; native return retained"
                )
    actual_flag = ctx.catalog["populations"] is not None
    if incoming["wire"]["owner_fields"].get("channels") is not actual_flag:
        raise ValueError("Require the actual cold-configured channel owner flag")


def equal_tree(a, b):
    if isinstance(a, Mapping) or isinstance(b, Mapping):
        return (
            isinstance(a, Mapping)
            and isinstance(b, Mapping)
            and list(a) == list(b)
            and all(equal_tree(a[k], b[k]) for k in a)
        )
    if isinstance(a, (list, tuple)) or isinstance(b, (list, tuple)):
        return (
            isinstance(a, (list, tuple))
            and isinstance(b, (list, tuple))
            and len(a) == len(b)
            and all(equal_tree(x, y) for x, y in zip(a, b, strict=True))
        )
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        return (
            isinstance(a, np.ndarray)
            and isinstance(b, np.ndarray)
            and a.dtype == b.dtype
            and np.array_equal(a, b)
        )
    return a == b


def finite_tree(value):
    if isinstance(value, Mapping):
        return all(finite_tree(v) for v in value.values())
    if isinstance(value, (tuple, list)):
        return all(finite_tree(v) for v in value)
    if isinstance(value, (np.ndarray, np.generic, float)):
        return bool(np.isfinite(value).all())
    return True


def restore(ctx, incoming):
    if incoming is None or incoming.get("kind") != "cells.ecm_catalog_grn_owner_cache@1":
        raise ValueError("Require complete ECM catalog GRN owner cache")
    raw = incoming["wire"]
    if set(raw) != {
        "owner_fields",
        "core_fields",
        "molecule_fields",
        "reaction_fields",
        "modulator_fields",
        "ion_boundary_state",
        "simulator_fields",
        "channel_fields",
    }:
        raise ValueError("Require every ECM owner/cache field")
    if set(raw["molecule_fields"]) != {"X", "Y"}:
        raise ValueError("Require both configured ECM gene products")
    for values in raw["molecule_fields"].values():
        if (
            not set(PARAMETERS) | {"c_cells", "cc_at_mem", "c_env", "flux_intra", "gad_eval_string"}
            <= values.keys()
        ):
            raise ValueError("Missing source-initialized ECM gene fields")
        if values["ignore_ECM_pump"] is not True:
            raise ValueError("Preserve actual source ignore_ECM_pump default")
    validate_cached_channels(ctx, incoming)
    ctx.initial_channel_fields = clone(incoming["initial_channel_fields"])
    ctx.channel_calls = clone(incoming["channel_calls"])
    api = science()
    owner = object.__new__(api["MasterOfGenes"])
    vars(owner).update(clone(raw["owner_fields"]))
    net = object.__new__(api["MasterOfNetworks"])
    vars(net).update(clone(raw["core_fields"]))
    owner.core, ctx.sim.grn = (net, owner)
    for attr, key, cls in (
        ("molecules", "molecule_fields", "Molecule"),
        ("reactions", "reaction_fields", "Reaction"),
        ("modulators", "modulator_fields", "Modulator"),
    ):
        objects = OrderedDict()
        for name, fields in raw[key].items():
            obj = object.__new__(api[cls])
            vars(obj).update(clone(fields))
            objects[name] = obj
        setattr(net, attr, objects)
    net.reactions_env, net.reactions_mit, net.channels, net.mit = (
        OrderedDict(),
        OrderedDict(),
        OrderedDict(),
        None,
    )
    for name, saved in raw["channel_fields"].items():
        obj = object.__new__(api["Channel"])
        vars(obj).update(clone(saved["fields"]))
        core = object.__new__(api["class_for"](saved["core_class"]))
        vars(core).update(clone(saved["core_fields"]))
        obj.channel_core = core
        net.channels[name] = obj
    for key, value in raw["simulator_fields"].items():
        setattr(ctx.sim, key, clone(value))
    if set(incoming["coefficient_fields"]) != {"D_env_weight", "D_env_weight_base", "TJ_targets"}:
        raise ValueError("Require owned ECM molecular grid coefficients")
    for key, value in incoming["coefficient_fields"].items():
        setattr(ctx.sim, key, clone(value))
    for attr, ionic, molecular in (
        ("cell_concs", "cc_cells", "c_cells"),
        ("mem_concs", "cc_at_mem", "cc_at_mem"),
        ("env_concs", "cc_env", "c_env"),
        ("bound_concs", "c_env_bound", "c_bound"),
    ):
        mapping = OrderedDict()
        for name, enabled in ctx.p.ions_dict.items():
            if enabled != 1:
                continue
            i = ctx.sim.get_ion(name)
            mapping[name] = api["DynamicValue"](
                lambda i=i, a=ionic: getattr(ctx.sim, a)[i],
                lambda value, i=i, a=ionic: getattr(ctx.sim, a).__setitem__(i, value),
            )
        for name in net.molecules:
            mapping[name] = api["DynamicValue"](
                lambda name=name, a=molecular: getattr(net.molecules[name], a),
                lambda value, name=name, a=molecular: setattr(net.molecules[name], a, value),
            )
        setattr(net, attr, api["DynamicValueDict"](mapping))
    net.mit_concs = None
    return net


def before(ctx, material_declaration):
    sim, p, cells, net = (ctx.sim, ctx.p, ctx.cells, ctx.net)
    configured = []
    for name, obj in net.molecules.items():
        g = dict(
            enabled=obj.simple_growth,
            production_rate_mM_s=0.0 if obj.r_production is None else obj.r_production,
            decay_rate_per_s=0.0 if obj.r_decay is None else obj.r_decay,
            decay_max_per_s=0.0 if not obj.simple_growth else obj.decay_max,
            scale_factor=obj.gad_scale_factor,
        )
        configured.append(
            dict(
                name=name,
                parameters={key: clone(getattr(obj, key)) for key in PARAMETERS},
                growth=g,
            )
        )
    return dict(
        conditioned_before_model_network=True,
        ecm_normal_grn=True,
        material_declaration=clone(material_declaration),
        definition=dict(
            molecules=configured,
            grn_configuration=clone(p.grn.conf),
            reactions=clone(p.grn.conf["reactions"]),
            modulators=clone(p.grn.conf.get("modulators") or []),
        ),
        values_before=material_values(sim),
        molecule_states_before={
            name: {
                key: clone(getattr(obj, key))
                for key in ("c_cells", "cc_at_mem", "c_env", "flux_intra")
            }
            for name, obj in net.molecules.items()
        },
        cache_before=cache(ctx),
        controls_before=dict(gj_block=clone(sim.gj_block), NaKATP_block=clone(sim.NaKATP_block)),
        molecular_geometry=dict(
            owner=clone(cells.mem_to_cells),
            partner=clone(cells.nn_i),
            boundary=clone(cells.bflags_mems),
            membrane_area_m2=clone(cells.mem_sa),
            cell_volume_m3=clone(cells.cell_vol),
            gap_length_m=clone(cells.gj_len),
        ),
        dt_s=p.dt,
        F=p.F,
        R=p.R,
        q_C=p.q,
        kb_J_K=p.kb,
        membrane_thickness_m=p.tm,
        runtime_temperature_K=sim.T,
        configured_temperature_K=p.T,
        gap_open=clone(sim.gjopen),
        rho_channel=clone(sim.rho_channel),
        ion_ids=list(ctx.ion_ids),
        valence=clone(sim.zs),
        electric_x_source=clone(sim.E_env_x),
        electric_y_source=clone(sim.E_env_y),
        D_env=clone(sim.D_env),
        grid_index_groups=clone(ctx.definition["grid_index_groups"]),
        substances_affect_charge=p.substances_affect_charge,
        sharpness=p.sharpness,
        cluster_open=p.cluster_open,
        incoming_channel_current_A_m2=clone(net.extra_J_mem),
        simulator_fields_before=wire(sim.grn, sim)["simulator_fields"],
        owner=owner_evidence(ctx),
    )


def attach(ctx, material_declaration, observer=None, channel_observer=None):
    sim, p, net = (ctx.sim, ctx.p, ctx.net)

    def chemistry(stage, species, actual):
        ctx.trace["molecule_frames"].append(
            dict(stage=stage, species=species, values=material_values(sim), cache=cache(ctx))
        )

    def mover(stage, name, local, actual):
        fields = (
            "cX_env_o",
            "cX_cells",
            "cX_mems",
            "f_X_ED",
            "fgj_X",
            "fenvx",
            "fenvy",
            "cenv",
            "gcx",
            "gcy",
            "fx",
            "fy",
            "div_fa",
            "denv_multiplier",
        )
        ctx.trace["mover_frames"].append(
            dict(
                stage=stage,
                species=name,
                fields={key: clone(local.get(key)) for key in fields},
                vm=clone(actual.vm),
                vgj=clone(actual.vgj),
            )
        )

    def rhs(growth, reaction, all_rates):
        ctx.trace["rhs"] = dict(
            growth_rates=clone(growth), reaction_rates=clone(reaction), all_rates=clone(all_rates)
        )

    def control(name, value, actual):
        ctx.trace["control_writes"].append(
            dict(
                rule_id=name,
                target=net.modulators[name].target_label,
                value=clone(value),
                gj_block=clone(actual.gj_block),
                NaKATP_block=clone(actual.NaKATP_block),
            )
        )

    def dispatched(stage, actual, phase):
        ctx.trace["dispatch_stages"].append(stage)
        if stage == "clear_run_loop":
            ctx.trace["before_channels"] = before(ctx, material_declaration)
            ctx.trace["before_channels"].update(mode="channels", catalog=clone(ctx.catalog))
            if channel_observer is not None:
                channel_observer(clone(ctx.trace["before_channels"]))
        if stage == "run_loop_channels" or (stage == "clear_run_loop" and not ctx.sim.grn.channels):
            ctx.trace["before"] = before(ctx, material_declaration)
            if observer is not None:
                observer(clone(ctx.trace["before"]))

    (
        net._observe_chem,
        net._observe_rhs,
        net._observe_control,
        net._observe_dispatch,
        p._mover_observe,
    ) = (chemistry, rhs, control, dispatched, mover)


def run_dispatch(
    ctx, material_declaration, publication, source_time_s, observer=None, channel_observer=None
):
    ctx.p.substances_affect_charge = publication
    ctx.phase.kind = "SIM"
    ctx.net = ctx.sim.grn.core
    attach(ctx, material_declaration, observer, channel_observer)
    try:
        science()["dispatch"](ctx.sim, source_time_s, ctx.phase, ctx.cells, ctx.p)
        ctx.trace["source_completed"] = True
    finally:
        ctx.trace.update(
            cache_after=cache(ctx),
            values_after=material_values(ctx.sim),
            controls_after=dict(
                gj_block=clone(ctx.sim.gj_block), NaKATP_block=clone(ctx.sim.NaKATP_block)
            ),
            owner_after=owner_evidence(ctx),
            completed_transports=sum(
                (row["stage"] == "transport_after" for row in ctx.trace["molecule_frames"])
            ),
        )
    return ctx.trace
