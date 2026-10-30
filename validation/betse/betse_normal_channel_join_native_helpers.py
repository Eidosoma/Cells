"""Authenticate native class, alias and network call bodies for the late join."""

import ast
import copy
import hashlib
import json
from abc import ABCMeta, abstractmethod
from collections.abc import MutableMapping
from pathlib import Path
from types import MethodType, SimpleNamespace

import numpy as np

from validation.betse import betse_normal_ion_join_native as material_native

PROTOCOL = Path(__file__).with_name("betse_normal_channel_join_protocol.json")


class NativeChannelInitializationRefused(ValueError):
    def __init__(self, reason, partial):
        super().__init__(str(reason))
        self.partial = partial


def authenticated():
    pins = json.loads(PROTOCOL.read_text())["native_source"]
    trees, sites = {}, {}
    for name, expected in pins["source_sha256"].items():
        data = (Path(pins["checkout"]) / name).read_bytes()
        installed = Path(pins["installed_package"]).parent / name
        if hashlib.sha256(data).hexdigest() != expected or installed.read_bytes() != data:
            raise ValueError("Native channel/alias/network source changed: " + name)
        trees[name] = ast.parse(data)

    def selected(path, names):
        result = []
        for node in trees[path].body:
            if isinstance(node, ast.ClassDef) and node.name in names:
                sites[path + ":" + node.name] = dict(
                    first_line=node.lineno,
                    last_line=node.end_lineno,
                    AST_sha256=hashlib.sha256(
                        ast.dump(node, include_attributes=False).encode()
                    ).hexdigest(),
                )
                result.append(copy.deepcopy(node))
        if {n.name for n in result} != set(names):
            raise ValueError("Native class selector changed")
        return result

    nodes = selected("betse/science/channels/channelsabc.py", ["ChannelsABC"])
    nodes += selected("betse/science/channels/vg_na.py", ["VgNaABC", "Nav1p6"])
    nodes += selected("betse/science/channels/vg_k.py", ["VgKABC", "Kv1p5", "Kv3p2"])
    nodes += selected("betse/science/channels/vg_cl.py", ["VgClABC", "ClLeak"])
    nodes += selected(
        "betse/util/type/iterable/mapping/mapcls.py", ["DynamicValue", "DynamicValueDict"]
    )
    networks = trees["betse/science/chemistry/networks.py"]
    master = next(
        n for n in networks.body if isinstance(n, ast.ClassDef) and n.name == "MasterOfNetworks"
    )
    methods = [
        copy.deepcopy(n)
        for n in master.body
        if isinstance(n, ast.FunctionDef)
        and n.name in ("clear_run_loop", "run_loop_channels", "run_loop", "energy_charge")
    ]
    channel = next(n for n in networks.body if isinstance(n, ast.ClassDef) and n.name == "Channel")
    methods += [
        copy.deepcopy(n)
        for n in channel.body
        if isinstance(n, ast.FunctionDef) and n.name == "init_channel"
    ]
    for node in methods:
        sites["betse/science/chemistry/networks.py:" + node.name] = dict(
            first_line=node.lineno,
            last_line=node.end_lineno,
            AST_sha256=hashlib.sha256(
                ast.dump(node, include_attributes=False).encode()
            ).hexdigest(),
        )
    nodes += methods

    class StripAnnotations(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            node.decorator_list = [d for d in node.decorator_list if ast.unparse(d) != "type_check"]
            node.returns = None
            for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                arg.annotation = None
            return self.generic_visit(node)

    class Observe(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            if node.name != "run_loop_channels":
                return node
            self.generic_visit(node)
            loop = next(n for n in node.body if isinstance(n, ast.For))
            loop.body[1:1] = ast.parse("_channel_before(name,chan,sim,p,phase)").body
            loop.body += ast.parse("_channel_after(name,chan,sim,p,phase)").body
            return node

        def visit_Assign(self, node):
            target = ast.unparse(node.targets[0])
            field = {
                "ccell": "sampled_bulk_mM",
                "cmem": "sampled_membrane_mM",
                "cenv": "sampled_bath_mM",
                "DChan": "diffusion_m2_s",
                "f_ED": "flux_mol_m2_s",
            }.get(target)
            if field:
                return [node, *ast.parse("_channel_local('" + field + "'," + target + ")").body]
            return node

    enum = SimpleNamespace(INIT=object(), SIM=object())
    namespace = dict(
        np=np,
        ABCMeta=ABCMeta,
        abstractmethod=abstractmethod,
        MappingMutableType=MutableMapping,
        logs=SimpleNamespace(log_info=lambda *_: None),
        SimPhaseKind=enum,
        __name__="pinned_late_channel_join",
        BetseMethodUnimplementedException=NotImplementedError,
    )
    exec(
        compile(
            ast.fix_missing_locations(
                ast.Module(
                    body=[StripAnnotations().visit(Observe().visit(n)) for n in nodes],
                    type_ignores=[],
                )
            ),
            "<authenticated BETSE channel classes/aliases/network>",
            "exec",
        ),
        namespace,
    )
    for short, classes in (
        ("vgna", ("Nav1p6",)),
        ("vgk", ("Kv1p5", "Kv3p2")),
        ("vgcl", ("ClLeak",)),
    ):
        namespace[short] = SimpleNamespace(**{name: namespace[name] for name in classes})
    return namespace, sites, pins


def setup(sim, cells, parameters, definition, live, caches, calls, source, observe):
    namespace, sites, pins = authenticated()
    namespace["stb"] = source["stb"]
    parameters.substances_affect_charge = live["substances_affect_charge"]
    parameters.ions_dict = {name: 1 for name in definition["ion_ids"]}
    sim.cdl, sim.edl = len(cells.cell_i), sim.mdl
    sim.get_ion = lambda name: definition["ion_ids"].index(name)
    net = SimpleNamespace(
        channels={},
        molecules={},
        reactions={},
        reactions_env={},
        reactions_mit={},
        reaction_matrix=np.zeros((len(definition["ion_ids"]), 0)),
        mit_enabled=False,
    )
    for attr, sim_attr in (
        ("cell_concs", "cc_cells"),
        ("mem_concs", "cc_at_mem"),
        ("env_concs", "cc_env"),
    ):
        mapping = {
            name: namespace["DynamicValue"](
                lambda i=i, a=sim_attr: getattr(sim, a)[i],
                lambda value, i=i, a=sim_attr: getattr(sim, a).__setitem__(i, value),
            )
            for i, name in enumerate(definition["ion_ids"])
        }
        setattr(net, attr, namespace["DynamicValueDict"](mapping))
    net.zmol = {name: sim.zs[i] for i, name in enumerate(definition["ion_ids"])}
    net.energy_charge = MethodType(namespace["energy_charge"], net)
    phase = SimpleNamespace(
        sim=sim,
        cells=cells,
        p=parameters,
        kind=getattr(namespace["SimPhaseKind"], live["phase_kind"]),
    )
    initializations, events = [], []
    call_counts = [0] * len(definition["channels"]) if calls is None else list(calls)
    roles = dict(Nav1p6="Na", Kv1p5="K", Kv3p2="K", ClLeak="Cl")
    sim.dyna = SimpleNamespace(tissue_target_inds={})
    for slot, row in enumerate(definition["channels"]):
        if caches is None:
            sim.dyna.tissue_target_inds["explicit"] = np.asarray(row["targets"], np.int64)
            chan = SimpleNamespace(channel_profiles_list=["explicit"])
            try:
                namespace["init_channel"](
                    chan, roles[row["class_name"]], row["class_name"], row["maxDm_m2_s"], phase
                )
            except Exception as error:
                raise NativeChannelInitializationRefused(
                    error,
                    dict(
                        channel_id=row["id"],
                        prior_caches=copy.deepcopy(initializations),
                        failed_core_cache=copy.deepcopy(vars(chan.channel_core)),
                        source_exception=type(error).__name__,
                        no_repair_applied=True,
                        native_source=pins,
                        source_sites=sites,
                        raw_simulator_state={
                            key: copy.deepcopy(value)
                            for key, value in vars(sim).items()
                            if not callable(value) and key not in {"gj_funk", "dyna"}
                        },
                        source_geometry=vars(cells),
                        source_parameters=vars(parameters),
                    ),
                ) from error
            initializations.append(copy.deepcopy(vars(chan.channel_core)))
        else:
            chan = SimpleNamespace(
                channel_core=object.__new__(namespace[row["class_name"]]), maxDm=row["maxDm_m2_s"]
            )
            vars(chan.channel_core).update(copy.deepcopy(caches[slot]))
        chan.init_active = row["init_active"]
        chan.alpha_eval_string = "_modulators['" + row["id"] + "']"
        net.channels[row["id"]] = chan
    namespace["_modulators"] = {
        name: np.asarray(value, np.float64) for name, value in live["modulators"].items()
    }
    pending = {}

    def before(name, chan, actual, p, actual_phase):
        row = definition["channels"][list(net.channels).index(name)]
        i = sim.get_ion(roles[row["class_name"]])
        skip = actual_phase.kind is namespace["SimPhaseKind"].INIT and not chan.init_active
        pending.clear()
        pending.update(
            channel_id=name,
            class_name=row["class_name"],
            ion_id=roles[row["class_name"]],
            skipped=skip,
            cache_before=copy.deepcopy(vars(chan.channel_core)),
            voltage_before_V=actual.vm.copy(),
            values_before=material_native.values(actual),
            sampled_bulk_mM=actual.cc_cells[i].copy(),
            sampled_membrane_mM=actual.cc_cells[i][cells.mem_to_cells].copy(),
            sampled_bath_mM=np.asarray(actual.cc_env[i]).copy(),
            diffusion_m2_s=None,
            flux_mol_m2_s=None,
            network_current_before_A_m2=net.extra_J_mem.copy(),
            dt_s=p.dt,
            native_dt=0.0 if skip else p.dt * chan.channel_core.time_unit,
        )

    def after(name, chan, actual, p, actual_phase):
        slot = list(net.channels).index(name)
        if not pending["skipped"]:
            call_counts[slot] += 1
        pending.update(
            cache_after=copy.deepcopy(vars(chan.channel_core)),
            call_index=call_counts[slot],
            voltage_after_V=actual.vm.copy(),
            values_after=material_native.values(actual),
            network_current_after_A_m2=net.extra_J_mem.copy(),
        )
        events.append(copy.deepcopy(pending))
        observe(
            "channel_skipped" if pending["skipped"] else "channel_direct",
            sim.get_ion(pending["ion_id"]),
            actual,
        )

    namespace["_channel_before"], namespace["_channel_after"] = before, after
    namespace["_channel_local"] = lambda name, value: pending.__setitem__(
        name, np.array(value, copy=True)
    )
    publication = {}

    def late(actual, geometry, p, t):
        namespace["clear_run_loop"](net, actual)
        observe("network_clear", None, actual)
        namespace["run_loop_channels"](net, phase)
        namespace["run_loop"](net, phase, t)
        publication.update(
            extra_current_A_m2=net.extra_J_mem.copy(),
            extra_charge_C_m3=net.extra_rho_cells.copy(),
            current_publication="replace" if p.substances_affect_charge else "retain incoming",
            energy_charge=net.chi.copy(),
            aliases_follow_live_rows=all(
                np.shares_memory(net.cell_concs[name], actual.cc_cells[i])
                for i, name in enumerate(definition["ion_ids"])
            ),
            current_alias_published=actual.extra_J_mem is net.extra_J_mem
            if p.substances_affect_charge
            else False,
        )
        observe("network_publish", None, actual)

    return late, dict(
        initializations=initializations,
        events=events,
        calls=call_counts,
        network=publication,
        caches=lambda: [copy.deepcopy(vars(chan.channel_core)) for chan in net.channels.values()],
        source_sites=sites,
        native_source=pins,
    )
