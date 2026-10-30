# ruff: noqa: B007, B905, E501
"""Independent original-AST GRN lifecycle, owner and dispatch capture."""

import ast
import copy
import hashlib
import json
from abc import ABCMeta
from collections import OrderedDict
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.betse import betse_normal_molecule_join_native_network as previous

PROTOCOL = Path(__file__).with_name("betse_normal_grn_join_protocol.json")
_LITERAL = None


def _outside_scope(*args, **kwargs):
    raise ValueError("Separate mitochondria, asymmetry, optimizer or profile state required")


def statement(text):
    return ast.parse(text).body[0]


class Clean(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        node.decorator_list = []
        node.returns = None
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            arg.annotation = None
        return self.generic_visit(node)


def original_nodes(root):
    network = ast.parse((root / "science/chemistry/networks.py").read_text())
    core = next(
        (
            node
            for node in network.body
            if isinstance(node, ast.ClassDef) and node.name == "MasterOfNetworks"
        )
    )
    core = Clean().visit(copy.deepcopy(core))
    core.body = [
        node
        for node in core.body
        if isinstance(node, ast.FunctionDef)
        and node.name
        in {
            "__init__",
            "read_substances",
            "tissue_init",
            "write_reactions_env",
            "create_reaction_matrix_env",
            "bal_charge",
        }
    ]
    core.bases = [ast.parse("molecule_source._Network", mode="eval").body]
    gene = ast.parse((root / "science/chemistry/gene.py").read_text())
    owner = Clean().visit(
        copy.deepcopy(
            next(
                (
                    node
                    for node in gene.body
                    if isinstance(node, ast.ClassDef) and node.name == "MasterOfGenes"
                )
            )
        )
    )
    owner.body = [
        node
        for node in owner.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"__init__", "read_gene_config", "reinitialize"}
    ]
    mapping = ast.parse((root / "util/type/iterable/mapping/mapcls.py").read_text())
    mappings = [
        Clean().visit(copy.deepcopy(node))
        for node in mapping.body
        if isinstance(node, ast.ClassDef) and node.name in {"DynamicValue", "DynamicValueDict"}
    ]
    plot = Clean().visit(
        copy.deepcopy(
            next(
                (
                    node
                    for node in ast.parse((root / "science/chemistry/netplot.py").read_text()).body
                    if isinstance(node, ast.FunctionDef) and node.name == "set_net_opts"
                )
            )
        )
    )
    sim = ast.parse((root / "science/sim.py").read_text())
    init = copy.deepcopy(
        next((node for node in ast.walk(sim) if isinstance(node, ast.If) and node.lineno == 884))
    )
    dispatch = copy.deepcopy(
        next((node for node in ast.walk(sim) if isinstance(node, ast.If) and node.lineno == 1306))
    )

    class Observe(ast.NodeTransformer):
        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call):
                name = ast.unparse(node.value.func)
                if name.startswith("self.grn.core."):
                    stage = name.rsplit(".", 1)[-1]
                    return [
                        node,
                        statement(
                            "self.grn.core._observe_dispatch(" + repr(stage) + ",self,phase)"
                        ),
                    ]
            return node

    dispatch = Observe().visit(dispatch)
    wrappers = []
    for name, body in (("initialize_owner", init), ("dispatch", dispatch)):
        function = ast.parse("def " + name + "(self,t,phase,cells,p):\n    pass\n").body[0]
        function.body = [body]
        wrappers.append(function)
    return mappings + [plot, core, owner] + wrappers


def literal_nodes(root):
    base = previous.literal_nodes(root)
    net = next(node for node in base if getattr(node, "name", None) == "_LiteralNetwork")
    net.name = "MasterOfNetworks"
    original = original_nodes(root)
    added = next(node for node in original if getattr(node, "name", None) == "MasterOfNetworks")
    net.body.extend(added.body)
    return (
        [
            node
            for node in original
            if getattr(node, "name", None)
            not in {"MasterOfNetworks", "MasterOfGenes", "initialize_owner", "dispatch"}
        ]
        + base
        + [
            node
            for node in original
            if getattr(node, "name", None) in {"MasterOfGenes", "initialize_owner", "dispatch"}
        ]
    )


def authenticated():
    pins = json.loads(PROTOCOL.read_text())["native_source"]
    for name, digest in pins["source_sha256"].items():
        data = (Path(pins["checkout"]) / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest
        assert data == (Path(pins["installed_package"]).parent / name).read_bytes()
    ns = dict(
        np=np,
        copy=copy,
        ABCMeta=ABCMeta,
        OrderedDict=OrderedDict,
        SimpleNamespace=SimpleNamespace,
        MappingMutableType=MutableMapping,
        types=SimpleNamespace(trim=repr),
        BetseMethodUnimplementedException=NotImplementedError,
        BetseSimConfException=ValueError,
        logs=SimpleNamespace(log_info=lambda *_: None, log_warning=lambda *_: None),
        tex_val=str,
        Mito=_outside_scope,
        mods=SimpleNamespace(),
        fd=SimpleNamespace(
            gradient=_outside_scope, divergence=_outside_scope, integrator=_outside_scope
        ),
        div_env=_outside_scope,
        nernst_planck_flux=_outside_scope,
    )
    nodes = literal_nodes(Path(pins["checkout"]) / "betse")
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
            "<original GRN owner lifecycle and normal dispatch>",
            "exec",
        ),
        ns,
    )
    ns["stb"] = SimpleNamespace(
        molecule_mover=ns["molecule_mover"], no_negs=ns["no_negs"], map_to_cells=_outside_scope
    )
    return ns


def literals():
    global _LITERAL
    if _LITERAL is None:
        _LITERAL = authenticated()
    return _LITERAL


def initial_cache(definition):
    return None


def dispatch_owner(sim, t, phase, cells, p):
    return literals()["dispatch"](sim, t, phase, cells, p)


"""Pure state-adapter template emitted into two independent capture modules.

This file is not imported as a scientific implementation. The emitting tool
reads its text; lifecycle/math bodies are separately original-AST authenticated.
"""

ALIASES = {"cell_concs", "mem_concs", "env_concs", "bound_concs", "mit_concs"}
OBJECTS = {
    "molecules",
    "reactions",
    "reactions_env",
    "reactions_mit",
    "modulators",
    "channels",
    "mit",
    "molecule_frames",
    "mover_frames",
    "rhs",
}
DYNAMIC = ("c_cells", "cc_at_mem", "c_env", "flux_intra", "f_mem", "f_gj", "fenvx", "fenvy")
REQUIRED_MOLECULE = {
    "Dgj",
    "Dm",
    "Do",
    "Mu_mem",
    "TJ_factor",
    "c_bound",
    "c_cells",
    "c_env",
    "cc_at_mem",
    "ignoreGJ",
    "ignoreTJ",
    "ignore_ECM_pump",
    "modify_time_factor",
    "name",
    "transmem",
    "u_mt",
    "update_intra_conc",
    "z",
    "active_pumping",
    "ion_channel_gating",
    "change_bounds",
    "cell_clamp",
    "simple_growth",
    "gad_eval_string",
    "scale_factor",
}


class GRNInitializationRefused(ValueError):
    def __init__(self, reason, partial):
        super().__init__(str(reason))
        self.partial = partial


def clone(value):
    if isinstance(value, np.ndarray):
        return value.copy()
    if isinstance(value, Mapping):
        return {key: clone(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [clone(item) for item in value]
    return copy.deepcopy(value)


def public(obj, excluded=()):
    return {
        key: clone(value)
        for key, value in vars(obj).items()
        if not key.startswith("_") and key not in excluded and not callable(value)
    }


def wire(owner, sim):
    core = getattr(owner, "core", None) if owner is not None else None
    return dict(
        owner_fields={} if owner is None else public(owner, {"core"}),
        core_fields={} if core is None else public(core, ALIASES | OBJECTS),
        molecule_fields={}
        if core is None
        else {name: public(obj) for name, obj in core.molecules.items()},
        reaction_fields={}
        if core is None
        else {name: public(obj) for name, obj in core.reactions.items()},
        modulator_fields={}
        if core is None
        else {name: public(obj) for name, obj in core.modulators.items()},
        ion_boundary_state=clone(sim.c_env_bound),
        simulator_fields={
            key: clone(getattr(sim, key))
            for key in (
                "extra_rho_cells",
                "extra_rho_env",
                "extra_J_mem",
                "extra_Jenv_x",
                "extra_Jenv_y",
            )
            if hasattr(sim, key)
        },
    )


def snapshot(molecules):
    return {
        name: dict(
            {key: clone(getattr(obj, key, None)) for key in DYNAMIC},
            present_fields=tuple(key for key in DYNAMIC if hasattr(obj, key)),
        )
        for name, obj in molecules.items()
    }


def cache(net):
    raw = wire(net._sim.grn, net._sim)
    dynamic = ("reaction_rates", "delta_conc", "delta_conc_env", "chi")
    result = dict(
        kind="cells.genuine_grn_owner_cache@1",
        wire=raw,
        present_fields=tuple(key for key in dynamic if hasattr(net, key)),
        molecule_states=snapshot(net.molecules),
        growth_expressions={name: obj.gad_eval_string for name, obj in net.molecules.items()},
    )
    for key in (
        *dynamic,
        "reaction_matrix",
        "extra_rho_env",
        "extra_rho_mit",
        "extra_Jenv_x",
        "extra_Jenv_y",
        "extra_rho_cells",
        "extra_J_mem",
    ):
        result[key] = clone(getattr(net, key, None))
    result["reaction_expressions"] = {
        name: obj.reaction_eval_string for name, obj in net.reactions.items()
    }
    result["modulator_expressions"] = {
        name: obj.alpha_eval_string for name, obj in net.modulators.items()
    }
    return result


def owner_evidence(sim, expected_core):
    owner = sim.grn
    return dict(
        owner_class=type(owner).__name__,
        core_class=type(owner.core).__name__,
        grn_enabled=sim._grn_parameters.grn_enabled,
        molecules_enabled=sim._grn_parameters.molecules_enabled,
        actual_core_identity=owner.core is expected_core,
        flags=public(owner, {"core"}),
        charge_has_been_balanced=owner.core.charge_has_been_balanced,
        time_dilation=owner.core.time_dila,
    )


def configure_owner_context(sim, cells, p, definition):
    p.grn = SimpleNamespace(conf=clone(definition["grn_configuration"]))
    sim._grn_parameters = p
    p.grn_enabled, p.molecules_enabled, p.plot_network = True, False, False
    sim.c_env_bound = np.asarray(definition["ion_boundary_mM"], np.float64).copy()
    cells.R_rads = np.asarray(definition["radius_m"], np.float64).copy()


def cold_owner(sim, cells, p, definition):
    configure_owner_context(sim, cells, p, definition)
    sim.grn = None
    old_publication = p.substances_affect_charge
    p.substances_affect_charge = definition["grn_initialization_publish"]
    phase = SimpleNamespace(sim=sim, cells=cells, p=p, kind="INIT", dyna=SimpleNamespace())
    try:
        literals()["initialize_owner"](sim, 0.0, phase, cells, p)
    except Exception as error:
        partial = dict(
            source_exception=type(error).__name__,
            source_message=str(error),
            stage="grn_initialization",
            owner_snapshot=wire(sim.grn, sim),
            actual_grn_enabled=p.grn_enabled,
            actual_molecules_enabled=p.molecules_enabled,
            initialization_publication=p.substances_affect_charge,
        )
        raise GRNInitializationRefused(error, partial) from error
    finally:
        p.substances_affect_charge = old_publication
    sim.grn.core._sim = sim
    return sim.grn.core


def restore_owner(sim, cells, p, definition, incoming):
    configure_owner_context(sim, cells, p, definition)
    if incoming is None or incoming.get("kind") != "cells.genuine_grn_owner_cache@1":
        raise ValueError("Require a complete genuine GRN owner cache")
    raw = incoming["wire"]
    if not isinstance(raw, Mapping) or set(raw) != {
        "owner_fields",
        "core_fields",
        "molecule_fields",
        "reaction_fields",
        "modulator_fields",
        "ion_boundary_state",
        "simulator_fields",
    }:
        raise ValueError("Require all GRN owner/cache fields")
    expected_flags = dict(
        reset_MT=False,
        recalc_fluid=False,
        reactions=True,
        transporters=False,
        channels=False,
        modulators=definition["grn_configuration"].get("modulators") is not None,
    )
    if dict(raw["owner_fields"]) != expected_flags or set(raw["molecule_fields"]) != {"X", "Y"}:
        raise ValueError("Changed GRN owner or configured dispatch flags")
    for values in raw["molecule_fields"].values():
        if not REQUIRED_MOLECULE <= values.keys() or values["ignore_ECM_pump"] is not True:
            raise ValueError("Missing source-initialized GRN molecule fields")
    ns = literals()
    owner = object.__new__(ns["MasterOfGenes"])
    vars(owner).update(clone(raw["owner_fields"]))
    net = object.__new__(ns["MasterOfNetworks"])
    vars(net).update(clone(raw["core_fields"]))
    owner.core, sim.grn, net._sim = net, owner, sim
    for attr, key, cls in (
        ("molecules", "molecule_fields", "Molecule"),
        ("reactions", "reaction_fields", "Reaction"),
        ("modulators", "modulator_fields", "Modulator"),
    ):
        objects = OrderedDict()
        for name, values in raw[key].items():
            obj = object.__new__(ns[cls])
            vars(obj).update(clone(values))
            objects[name] = obj
        setattr(net, attr, objects)
    net.reactions_env, net.reactions_mit, net.channels, net.mit = (
        OrderedDict(),
        OrderedDict(),
        OrderedDict(),
        None,
    )
    sim.c_env_bound = np.asarray(raw["ion_boundary_state"], np.float64).copy()
    for key, value in raw["simulator_fields"].items():
        if key not in {"extra_rho_cells", "extra_J_mem"}:
            setattr(sim, key, clone(value))
    for attr, ionic, molecular in (
        ("cell_concs", "cc_cells", "c_cells"),
        ("mem_concs", "cc_at_mem", "cc_at_mem"),
        ("env_concs", "cc_env", "c_env"),
        ("bound_concs", "c_env_bound", "c_bound"),
    ):
        mapping = OrderedDict()
        for name in p.ions_dict:
            i = sim.get_ion(name)
            mapping[name] = ns["DynamicValue"](
                lambda i=i, a=ionic: getattr(sim, a)[i],
                lambda value, i=i, a=ionic: getattr(sim, a).__setitem__(i, value),
            )
        for name in net.molecules:
            mapping[name] = ns["DynamicValue"](
                lambda name=name, a=molecular: getattr(net.molecules[name], a),
                lambda value, name=name, a=molecular: setattr(net.molecules[name], a, value),
            )
        setattr(net, attr, ns["DynamicValueDict"](mapping))
    net.mit_concs = None
    return net


def attach_observers(net, sim, p, incoming):
    trace = dict(
        cache_before=clone(incoming),
        control_writes=[],
        molecule_frames=[],
        mover_frames=[],
        rhs={},
        source_completed=False,
        executed_chemistry=False,
    )
    net.molecule_frames, net.mover_frames, net.rhs = (
        trace["molecule_frames"],
        trace["mover_frames"],
        trace["rhs"],
    )

    def chemistry(stage, species, actual):
        trace["molecule_frames"].append(
            dict(
                stage=stage,
                species=species,
                molecule_states=snapshot(net.molecules),
                cell_concs=actual.cc_cells.copy(),
                mem_concs=actual.cc_at_mem.copy(),
                vm=actual.vm.copy(),
                vgj=actual.vgj.copy(),
                cache=cache(net),
            )
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
            "delta_cco",
            "Dm_vect",
        )
        trace["mover_frames"].append(
            dict(
                stage=stage,
                species=name,
                fields={key: clone(local.get(key)) for key in fields},
                vm=actual.vm.copy(),
                vgj=actual.vgj.copy(),
            )
        )

    def control(name, value, actual):
        trace["control_writes"].append(
            dict(
                rule_id=name,
                target=net.modulators[name].target_label,
                value=np.array(value, copy=True),
                gj_block=np.array(actual.gj_block, copy=True),
                NaKATP_block=np.array(actual.NaKATP_block, copy=True),
            )
        )

    net._observe_control, net._observe_chem, p._mover_observe = control, chemistry, mover
    net._observe_rhs = lambda growth, reaction, combined: trace["rhs"].update(
        growth_rates=np.array(growth, copy=True),
        reaction_rates=np.array(reaction, copy=True),
        all_rates=np.array(combined, copy=True),
    )
    return trace


def attach(
    net,
    sim,
    cells,
    p,
    definition,
    incoming_controls,
    incoming_cache,
    stb,
    *,
    ion_ids,
    dynamic_value,
    dynamic_dict,
):
    configure_owner_context(sim, cells, p, definition)
    sim.gj_block = np.asarray(incoming_controls["gj_block"], np.float64).copy()
    sim.NaKATP_block = np.asarray(incoming_controls["NaKATP_block"], np.float64).copy()
    if incoming_cache is None:
        # Cold lifecycle precedes the explicitly supplied ordinary forcing.
        # Preserve its actual simulator writes in the cold cache, then apply
        # the incoming readout packet as in the production material boundary.
        supplied_charge = sim.extra_rho_cells.copy()
        supplied_current = sim.extra_J_mem.copy()
        sim.extra_rho_cells = np.zeros(sim.cdl)
        sim.extra_J_mem = np.zeros(sim.mdl)
        net = cold_owner(sim, cells, p, definition)
        incoming_cache = cache(net)
        sim.extra_rho_cells = supplied_charge
        sim.extra_J_mem = supplied_current
        cold = True
    else:
        net = restore_owner(sim, cells, p, definition, incoming_cache)
        cold = False
    trace = attach_observers(net, sim, p, incoming_cache)
    trace["cold_initialization"] = cold
    return net, sim.grn, trace
