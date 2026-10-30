# ruff: noqa: B007, B905, E501
"""Authenticated molecule/core/mover bodies with observation hooks only.

This consumes a complete configured starting state, not a native lifecycle.
It never imports the production implementation.
"""

import ast
import copy
import hashlib
import json
from abc import ABCMeta
from collections import OrderedDict
from pathlib import Path
from types import MethodType, SimpleNamespace

import numpy as np

from validation.betse import betse_normal_network_join_native_network as previous

PROTOCOL = Path(__file__).with_name("betse_normal_molecule_join_protocol.json")
DYNAMIC = ("c_cells", "cc_at_mem", "c_env", "flux_intra", "f_mem", "f_gj", "fenvx", "fenvy")


def _outside_scope(*args, **kwargs):
    raise ValueError("Separate ECM, shell-field, motor, event and pumping state is required")


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


def literal_nodes(root):
    path = root / "science/chemistry/networks.py"
    nodes = previous.literal_nodes(path)
    network = next(node for node in nodes if node.name == "_LiteralNetwork")
    loop = next(node for node in network.body if node.name == "run_loop")

    class Observe(ast.NodeTransformer):
        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call):
                name = ast.unparse(node.value.func)
                if name == "obj.update_intra":
                    return [node, statement("self._observe_chem('molecule_intra',mol,sim)")]
                if name == "obj.transport":
                    return [
                        statement("self._observe_chem('transport_before',name,sim)"),
                        node,
                        statement("self._observe_chem('transport_after',name,sim)"),
                    ]
            return self.generic_visit(node)

        def visit_Assign(self, node):
            result = self.generic_visit(node)
            name = ast.unparse(node.targets[0])
            if name == "self.delta_conc":
                return [
                    result,
                    statement("self._observe_rhs(gad_rates,self.reaction_rates,all_rates)"),
                    statement("self._observe_chem('rhs_ready',None,sim)"),
                ]
            if name == "self.cell_concs[name]":
                return [result, statement("self._observe_chem('chemical_commit',name,sim)")]
            return result

    index = network.body.index(loop)
    network.body[index] = Observe().visit(loop)
    modulators = next(node for node in network.body if node.name == "run_loop_modulators")
    next(node for node in modulators.body if isinstance(node, ast.For)).body.append(
        statement("self._observe_control(name,modulator,sim)")
    )
    parsed = ast.parse(path.read_text())
    molecule = copy.deepcopy(
        next(
            node
            for node in parsed.body
            if isinstance(node, ast.ClassDef) and node.name == "Molecule"
        )
    )
    molecule = Clean().visit(molecule)
    molecule.body = [
        node
        for node in molecule.body
        if isinstance(node, ast.FunctionDef)
        and node.name in ("__init__", "transport", "update_intra", "init_growth")
    ]
    molecule.bases = []
    nodes.append(molecule)
    toolbox = ast.parse((root / "science/sim_toolbox.py").read_text())
    helpers = [
        Clean().visit(copy.deepcopy(node))
        for node in toolbox.body
        if isinstance(node, ast.FunctionDef)
        and node.name in ("electroflux", "update_Co", "molecule_mover", "no_negs")
    ]
    assert len(helpers) == 4 and len(molecule.body) == 4
    mover = next(node for node in helpers if node.name == "molecule_mover")
    observed = []
    for node in mover.body:
        if isinstance(node, ast.Return):
            observed.append(statement("p._mover_observe('return',name,locals(),sim)"))
        observed.append(node)
        stage = None
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and ast.unparse(node.value.func) == "update_Co"
        ):
            stage = "membrane_commit"
        if isinstance(node, ast.If) and ast.unparse(node.test) == "ignoreGJ is False":
            stage = "junction_commit"
        if (
            isinstance(node, ast.If)
            and ast.unparse(node.test) == "p.is_ecm is True"
            and any(
                isinstance(child, ast.Assign) and ast.unparse(child.targets[0]) == "cX_env_temp"
                for child in node.orelse
            )
        ):
            stage = "environment_mix"
        if stage:
            observed.append(statement("p._mover_observe(" + repr(stage) + ",name,locals(),sim)"))
    mover.body = observed
    exceptions = ast.parse((root / "exceptions.py").read_text())
    exception_nodes = [
        Clean().visit(copy.deepcopy(node))
        for node in exceptions.body
        if isinstance(node, ast.ClassDef)
        and node.name in ("BetseException", "BetseSimException", "BetseSimUnstableException")
    ]
    assert len(exception_nodes) == 3
    return exception_nodes + helpers + nodes


def authenticated():
    pins = json.loads(PROTOCOL.read_text())["native_source"]
    for name in (
        "betse/science/chemistry/networks.py",
        "betse/science/sim_toolbox.py",
        "betse/exceptions.py",
    ):
        path = Path(pins["checkout"]) / name
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == pins["source_sha256"][name]
        assert data == (Path(pins["installed_package"]).parent / name).read_bytes()
    nodes = literal_nodes(Path(pins["checkout"]) / "betse")
    ns = dict(
        np=np,
        copy=copy,
        ABCMeta=ABCMeta,
        OrderedDict=OrderedDict,
        SimpleNamespace=SimpleNamespace,
        logs=SimpleNamespace(log_info=lambda *_: None, log_warning=lambda *_: None),
        tex_val=str,
        BetseSimConfException=ValueError,
        fd=SimpleNamespace(
            gradient=_outside_scope, divergence=_outside_scope, integrator=_outside_scope
        ),
        div_env=_outside_scope,
        nernst_planck_flux=_outside_scope,
    )
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
            "<pinned molecule/core/mover with observations>",
            "exec",
        ),
        ns,
    )
    ns["stb"] = SimpleNamespace(
        molecule_mover=ns["molecule_mover"], no_negs=ns["no_negs"], map_to_cells=_outside_scope
    )
    return ns


def initial_cache(definition):
    molecules = {}
    for row in definition["molecules"]:
        values = {
            name: np.asarray(row["initial"][name], np.float64).copy()
            if name in row["initial"]
            else None
            for name in DYNAMIC
        }
        values["present_fields"] = tuple(name for name in DYNAMIC if values[name] is not None)
        molecules[row["name"]] = values
    return dict(present_fields=(), molecule_states=molecules)


def snapshot(molecules):
    return {
        name: dict(
            {key: copy.deepcopy(getattr(obj, key, None)) for key in DYNAMIC},
            present_fields=tuple(key for key in DYNAMIC if hasattr(obj, key)),
        )
        for name, obj in molecules.items()
    }


def cache(net):
    values = previous.cache(net)
    values.update(
        molecule_states=snapshot(net.molecules),
        growth_expressions={name: obj.gad_eval_string for name, obj in net.molecules.items()},
    )
    return values


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
    ns = authenticated()
    cls = ns["_LiteralNetwork"]
    for name in previous.METHODS:
        setattr(net, name, MethodType(getattr(cls, name), net))
    sim.gj_block = np.asarray(incoming_controls["gj_block"], np.float64).copy()
    sim.NaKATP_block = np.asarray(incoming_controls["NaKATP_block"], np.float64).copy()
    if not np.array_equal(sim.rho_channel, np.asarray(definition["rho_channel"], np.float64)):
        raise ValueError("Supplied molecule rho must equal the actual native channel context")
    cells.map_mem2ecm = np.asarray(definition["membrane_to_environment"], np.int64)
    cells.R_rads = np.asarray(definition["radius_m"], np.float64)
    if incoming_cache is None or "molecule_states" not in incoming_cache:
        raise ValueError("Require the complete supplied molecular starting state")
    net.molecules = OrderedDict()
    for row in definition["molecules"]:
        mol = ns["Molecule"](sim, cells, p)
        mol.name = row["name"]
        for name, value in row["parameters"].items():
            setattr(mol, name, copy.deepcopy(value))
        growth = row["growth"]
        mol.simple_growth = growth["enabled"]
        mol.r_production, mol.r_decay, mol.decay_max = (
            growth[name] for name in ("production_rate_mM_s", "decay_rate_per_s", "decay_max_per_s")
        )
        mol.gad_scale_factor = growth["scale_factor"]
        mol.growth_profiles_list = "all" if mol.simple_growth else None
        mol.growth_mod_function_cells = np.ones(sim.cdl)
        for prefix in ("growth", "decay"):
            for sign in ("activators", "inhibitors"):
                for suffix in ("list", "Km", "n", "zone"):
                    setattr(mol, prefix + "_" + sign + "_" + suffix, None)
        mol.init_growth(SimpleNamespace(sim=sim, cells=cells, p=p))
        dynamic = incoming_cache["molecule_states"][mol.name]
        for name in dynamic["present_fields"]:
            value = dynamic[name]
            setattr(
                mol,
                name,
                np.asarray(value, np.float64).copy()
                if name not in ("fenvx", "fenvy")
                else copy.deepcopy(value),
            )
        net.molecules[mol.name] = mol
    for attr, ionic, molecular in (
        ("cell_concs", "cc_cells", "c_cells"),
        ("mem_concs", "cc_at_mem", "cc_at_mem"),
        ("env_concs", "cc_env", "c_env"),
    ):
        mapping = OrderedDict()
        for i, name in enumerate(ion_ids):
            mapping[name] = dynamic_value(
                lambda i=i, a=ionic: getattr(sim, a)[i],
                lambda value, i=i, a=ionic: getattr(sim, a).__setitem__(i, value),
            )
        for name, mol in net.molecules.items():
            mapping[name] = dynamic_value(
                lambda mol=mol, a=molecular: getattr(mol, a),
                lambda value, mol=mol, a=molecular: setattr(mol, a, value),
            )
        setattr(net, attr, dynamic_dict(mapping))
    net.zmol.update({name: mol.z for name, mol in net.molecules.items()})
    net.reaction_rates = None
    for name in incoming_cache["present_fields"]:
        setattr(net, name, copy.deepcopy(incoming_cache[name]))
    net.read_reactions(definition["reactions"], sim, cells, p)
    net.write_reactions()
    net.write_growth_and_decay()
    net.create_reaction_matrix()
    net.read_modulators(definition["modulators"], sim, cells, p)
    trace = dict(
        cache_before=copy.deepcopy(incoming_cache),
        control_writes=[],
        molecule_frames=[],
        mover_frames=[],
        rhs={},
        source_completed=False,
        executed_chemistry=False,
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
                fields={key: copy.deepcopy(local.get(key)) for key in fields},
                vm=actual.vm.copy(),
                vgj=actual.vgj.copy(),
            )
        )

    net._observe_control, net._observe_chem, p._mover_observe = control, chemistry, mover
    net._observe_rhs = lambda growth, reaction, combined: trace["rhs"].update(
        growth_rates=np.array(growth, copy=True),
        reaction_rates=np.array(reaction, copy=True),
        all_rates=np.array(combined, copy=True),
    )
    return trace
