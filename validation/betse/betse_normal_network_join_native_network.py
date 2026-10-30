# ruff: noqa: B007, B905, E501
"""Native network builders and control writes from authenticated original AST."""

import ast
import copy
import hashlib
import json
from collections import OrderedDict
from pathlib import Path
from types import MethodType, SimpleNamespace

import numpy as np

PROTOCOL = Path(__file__).with_name("betse_normal_network_join_protocol.json")
METHODS = (
    "read_reactions",
    "default_zones",
    "get_influencers",
    "write_reactions",
    "write_growth_and_decay",
    "create_reaction_matrix",
    "read_modulators",
    "clear_run_loop",
    "run_loop_modulators",
    "run_loop",
    "energy_charge",
)


def literal_nodes(path):
    tree = ast.parse(path.read_text())
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}

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

    result = []
    for name, selected in [
        ("MasterOfNetworks", METHODS),
        ("Reaction", ("__init__",)),
        ("Modulator", ("__init__", "init_modulator")),
    ]:
        nodes = [
            Clean().visit(copy.deepcopy(n))
            for n in classes[name].body
            if isinstance(n, ast.FunctionDef) and n.name in selected
        ]
        assert {n.name for n in nodes} == set(selected)
        result.append(
            ast.ClassDef(
                name="_LiteralNetwork" if name == "MasterOfNetworks" else name,
                bases=[],
                keywords=[],
                body=nodes,
                decorator_list=[],
            )
        )
    return result


def authenticated(stb):
    pins = json.loads(PROTOCOL.read_text())["native_source"]
    name = "betse/science/chemistry/networks.py"
    path = Path(pins["checkout"]) / name
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == pins["source_sha256"][name]
    assert data == (Path(pins["installed_package"]).parent / name).read_bytes()
    nodes = literal_nodes(path)
    cls = next(n for n in nodes if n.name == "_LiteralNetwork")
    method = next(n for n in cls.body if n.name == "run_loop_modulators")
    loop = next(n for n in method.body if isinstance(n, ast.For))
    loop.body.append(ast.parse("self._observe_control(name,modulator,sim)").body[0])
    ns = dict(
        np=np,
        OrderedDict=OrderedDict,
        SimpleNamespace=SimpleNamespace,
        stb=stb,
        logs=SimpleNamespace(log_info=lambda *_: None, log_warning=lambda *_: None),
        tex_val=str,
        BetseSimConfException=ValueError,
    )
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(path), "exec"
        ),
        ns,
    )
    return ns["_LiteralNetwork"]


def cache(net):
    fields = ("reaction_rates", "delta_conc", "delta_conc_env", "chi")
    return dict(
        present_fields=tuple(name for name in fields if hasattr(net, name)),
        reaction_rates=copy.deepcopy(getattr(net, "reaction_rates", None)),
        delta_conc=copy.deepcopy(getattr(net, "delta_conc", None)),
        delta_conc_env=copy.deepcopy(getattr(net, "delta_conc_env", None)),
        chi=copy.deepcopy(getattr(net, "chi", None)),
        reaction_matrix=net.reaction_matrix.copy(),
        reaction_expressions={
            name: row.reaction_eval_string for name, row in net.reactions.items()
        },
        modulator_expressions={name: row.alpha_eval_string for name, row in net.modulators.items()},
        extra_rho_env=net.extra_rho_env.copy(),
        extra_rho_mit=net.extra_rho_mit.copy(),
        extra_Jenv_x=net.extra_Jenv_x.copy(),
        extra_Jenv_y=net.extra_Jenv_y.copy(),
        extra_rho_cells=net.extra_rho_cells.copy(),
        extra_J_mem=net.extra_J_mem.copy(),
    )


def attach(net, sim, cells, p, definition, incoming_controls, incoming_cache, stb):
    cls = authenticated(stb)
    for name in METHODS:
        setattr(net, name, MethodType(getattr(cls, name), net))
    sim.gj_block = np.asarray(incoming_controls["gj_block"], np.float64).copy()
    sim.NaKATP_block = np.asarray(incoming_controls["NaKATP_block"], np.float64).copy()
    cells.map_mem2ecm = np.asarray(definition["membrane_to_environment"], np.int64)
    net.reaction_rates = None
    if incoming_cache is not None:
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
        source_completed=False,
        executed_chemistry=False,
    )

    def observe(name, value, actual):
        trace["control_writes"].append(
            dict(
                rule_id=name,
                target=net.modulators[name].target_label,
                value=np.array(value, copy=True),
                gj_block=np.array(actual.gj_block, copy=True),
                NaKATP_block=np.array(actual.NaKATP_block, copy=True),
            )
        )

    net._observe_control = observe
    return trace
