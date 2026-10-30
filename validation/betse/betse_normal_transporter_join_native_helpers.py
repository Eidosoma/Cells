"""Original 55-class factory, dynamic aliases and late-route observations.

Static preparation only. Numerical captures require a subsequently requested
bounded run; no constructor or channel equations execute on module import.
"""

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
from validation.betse import betse_normal_transporter_join_native_network as network_native

INVENTORY = Path(__file__).with_name("betse_normal_catalog_join_inventory.json")
PROTOCOL = Path(__file__).with_name("betse_normal_transporter_join_protocol.json")


class NativeChannelInitializationRefused(ValueError):
    def __init__(self, reason, partial):
        super().__init__(str(reason))
        self.partial = partial


class Executable(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        node.decorator_list = [d for d in node.decorator_list if ast.unparse(d) != "type_check"]
        node.returns = None
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            arg.annotation = None
        return self.generic_visit(node)


def authenticated():
    inventory = json.loads(INVENTORY.read_text())
    pins = json.loads(PROTOCOL.read_text())["native_source"]
    trees, sites = {}, {}
    for name, expected in pins["source_sha256"].items():
        data = (Path(pins["checkout"]) / name).read_bytes()
        if (
            hashlib.sha256(data).hexdigest() != expected
            or (Path(pins["installed_package"]).parent / name).read_bytes() != data
        ):
            raise ValueError("Pinned catalog source changed: " + name)
        trees[name] = ast.parse(data)
    namespace = dict(
        np=np,
        ABCMeta=ABCMeta,
        abstractmethod=abstractmethod,
        MappingMutableType=MutableMapping,
        logs=SimpleNamespace(log_info=lambda *_: None),
        SimPhaseKind=SimpleNamespace(INIT=object(), SIM=object()),
        BetseMethodUnimplementedException=NotImplementedError,
        __name__="pinned_catalog_common",
    )

    def execute(nodes, scope):
        for node in nodes:
            sites[scope["__name__"] + ":" + str(node.lineno) + ":" + node.name] = dict(
                first_line=node.lineno,
                last_line=node.end_lineno,
                AST_sha256=hashlib.sha256(
                    ast.dump(node, include_attributes=False).encode()
                ).hexdigest(),
            )
        exec(
            compile(
                ast.fix_missing_locations(
                    ast.Module(
                        body=[Executable().visit(copy.deepcopy(n)) for n in nodes], type_ignores=[]
                    )
                ),
                "<authenticated native catalog>",
                "exec",
            ),
            scope,
        )

    clock = next(
        n
        for n in trees["betse/science/channels/channelsabc.py"].body
        if isinstance(n, ast.ClassDef) and n.name == "ChannelsABC"
    )
    execute([clock], namespace)
    for family in ("Na", "K", "Ca", "Cl", "Fun", "Cat", "ML"):
        members = {
            name: row for name, row in inventory["classes"].items() if row["family"] == family
        }
        first = next(iter(members.values()))
        base = first["original_base"]
        selected = [
            n
            for n in trees[first["source"]].body
            if isinstance(n, ast.ClassDef) and (n.name == base or n.name in members)
        ]
        local = dict(namespace, __name__="pinned_catalog_" + family)
        execute(selected, local)
        module = SimpleNamespace(**{name: local[name] for name in members})
        namespace[
            {
                "Na": "vgna",
                "K": "vgk",
                "Ca": "vgca",
                "Cl": "vgcl",
                "Fun": "vgfun",
                "Cat": "vgcat",
                "ML": "vgml",
            }[family]
        ] = module
        for name in members:
            namespace[name] = local[name]
    aliases = [
        n
        for n in trees["betse/util/type/iterable/mapping/mapcls.py"].body
        if isinstance(n, ast.ClassDef) and n.name in ("DynamicValue", "DynamicValueDict")
    ]
    execute(aliases, namespace)
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
    factory = next(n for n in networks.body if isinstance(n, ast.ClassDef) and n.name == "Channel")
    methods += [
        copy.deepcopy(n)
        for n in factory.body
        if isinstance(n, ast.FunctionDef) and n.name == "init_channel"
    ]
    simulator = next(
        n
        for n in trees["betse/science/sim.py"].body
        if isinstance(n, ast.ClassDef) and n.name == "Simulator"
    )
    methods += [
        copy.deepcopy(n)
        for n in simulator.body
        if isinstance(n, ast.FunctionDef) and n.name == "ca_handler"
    ]
    for node in methods:
        sites["original:" + node.name] = dict(
            first_line=node.lineno,
            last_line=node.end_lineno,
            AST_sha256=hashlib.sha256(
                ast.dump(node, include_attributes=False).encode()
            ).hexdigest(),
        )

    class Observe(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            if node.name != "run_loop_channels":
                return node
            self.generic_visit(node)
            pop = next(n for n in node.body if isinstance(n, ast.For))
            pop.body[1:1] = ast.parse("_population_before(name,chan,sim,p,phase)").body
            pop.body += ast.parse("_population_after(name,chan,sim,p,phase)").body
            return node

        def visit_Expr(self, node):
            if ast.unparse(node) == "chan.channel_core.run(sim.vm, p)":
                return [node, *ast.parse("_population_gate_updated(sim)").body]
            return node

        def visit_Assign(self, node):
            target = ast.unparse(node.targets[0])
            result = [node]
            if target == "ioni":
                result += ast.parse("_route_before(ion,rel_perm,chan,sim)").body
            fields = dict(
                ccell="sampled_bulk_mM",
                cmem="sampled_membrane_mM",
                cenv="sampled_bath_mM",
                DChan="diffusion_m2_s",
                f_ED="flux_mol_m2_s",
            )
            if target in fields:
                result += ast.parse("_route_local('" + fields[target] + "'," + target + ")").body
            if target == "chan.channel_core.DChan":
                result += ast.parse("_route_after(ion,rel_perm,chan,sim)").body
            return result if len(result) > 1 else node

    methods = [Observe().visit(n) for n in methods]
    execute(methods, namespace)
    return namespace, sites, pins


def setup(
    sim,
    cells,
    p,
    definition,
    live,
    caches,
    calls,
    source,
    observe,
    *,
    calcium_live,
    incoming_network_controls,
    incoming_network_cache,
):
    ns, sites, pins = authenticated()
    inv = json.loads(INVENTORY.read_text())
    ns["stb"] = source["stb"]
    p.substances_affect_charge = live["substances_affect_charge"]
    p.ions_dict = {name: 1 for name in definition["ion_ids"]}
    policy = definition["calcium_handler"]
    if policy is None:
        if calcium_live["alpha_Ca"] != 0:
            raise ValueError("No CaATP without live Ca row")
        p.alpha_Ca, p.Ca_dyn = 0.0, 0
    else:
        if policy["Ca_dyn"] != 0:
            raise ValueError("Active CaATP requires explicit Ca_dyn0; ER/buffers separate")
        p.alpha_Ca = calcium_live["alpha_Ca"]
        p.Ca_dyn = 0
        sim.iCa = definition["ion_ids"].index("Ca")
        sim.CaATP_block = np.asarray(calcium_live["block"], np.float64)
        for key, value in (policy["maintained"] | policy["kinetics"]).items():
            if key in ("cATP", "cADP", "cPi", "deltaGATP") and getattr(p, key) != value:
                raise ValueError("Actual source maintained pools/deltaG must be shared")
            setattr(p, key, value)
    calcium_observations = {}
    ns["_calcium_local"] = lambda name, value: calcium_observations.__setitem__(
        name, np.array(value, copy=True)
    )
    ns["_calcium_alias"] = lambda actual, flux: calcium_observations.__setitem__(
        "rate_aliases_helper_flux", actual.rate_CaATP is flux
    )
    toolbox = ast.parse((Path(pins["checkout"]) / "betse/science/sim_toolbox.py").read_text())
    pump = copy.deepcopy(
        next(n for n in toolbox.body if isinstance(n, ast.FunctionDef) and n.name == "pumpCaATP")
    )
    labels = dict(
        Qnumo="quotient_numerator",
        Qdenomo="quotient_denominator_raw",
        Q="quotient",
        Keq="equilibrium",
        numo_E="forward_numerator",
        denomo_E="forward_denominator",
        frwd="forward",
        numo_Eb="backward_numerator_unused",
        denomo_Eb="backward_denominator_unused",
        bkwrd="backward_unused",
        f_Ca="raw_flux_mol_m2_s",
    )

    class CalciumObserve(ast.NodeTransformer):
        def visit_Assign(self, node):
            target = ast.unparse(node.targets[0])
            out = [node]
            if target in labels:
                out += ast.parse("_calcium_local('" + labels[target] + "'," + target + ")").body
            if target == "inds_Z":
                out += ast.parse("_calcium_local('zero_denominator_indices',inds_Z[0])").body
            if target == "Qdenomo[inds_Z]":
                out += ast.parse("_calcium_local('quotient_denominator_used',Qdenomo)").body
            if target == "self.rate_CaATP":
                out += ast.parse("_calcium_alias(self,f_CaATP)").body
            return out if len(out) > 1 else node

        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "no_negs":
                value = ast.unparse(node.value.args[0])
                label = "membrane" if value == "cCai" else "bath"
                return (
                    ast.parse("_calcium_local('before_no_negs_" + label + "'," + value + ")").body
                    + [node]
                    + ast.parse("_calcium_local('after_no_negs_" + label + "'," + value + ")").body
                )
            return node

    pump = CalciumObserve().visit(pump)
    simtree = ast.parse((Path(pins["checkout"]) / "betse/science/sim.py").read_text())
    handler = copy.deepcopy(
        next(
            n
            for n in ast.walk(simtree)
            if isinstance(n, ast.FunctionDef) and n.name == "ca_handler"
        )
    )
    handler = CalciumObserve().visit(handler)
    ns["no_negs"] = source["no_negs"]
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[pump, handler], type_ignores=[])),
            "<pinned actual CaATP/handler observations>",
            "exec",
        ),
        ns,
    )
    source["stb"].pumpCaATP = ns["pumpCaATP"]
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
    for attr, physical in (
        ("cell_concs", "cc_cells"),
        ("mem_concs", "cc_at_mem"),
        ("env_concs", "cc_env"),
    ):
        mapping = {
            name: ns["DynamicValue"](
                lambda i=i, a=physical: getattr(sim, a)[i],
                lambda value, i=i, a=physical: getattr(sim, a).__setitem__(i, value),
            )
            for i, name in enumerate(definition["ion_ids"])
        }
        setattr(net, attr, ns["DynamicValueDict"](mapping))
    net.zmol = {name: sim.zs[i] for i, name in enumerate(definition["ion_ids"])}
    net.energy_charge = MethodType(ns["energy_charge"], net)
    feedback = network_native.attach(
        net,
        sim,
        cells,
        p,
        definition["network"],
        incoming_network_controls,
        incoming_network_cache,
        source["stb"],
        ion_ids=definition["ion_ids"],
        dynamic_value=ns["DynamicValue"],
        dynamic_dict=ns["DynamicValueDict"],
    )
    phase = SimpleNamespace(
        sim=sim, cells=cells, p=p, kind=getattr(ns["SimPhaseKind"], live["phase_kind"])
    )
    sim.dyna = SimpleNamespace(tissue_target_inds={})
    initializations, events = [], []
    counts = [0] * len(definition["channels"]) if calls is None else list(calls)
    for slot, row in enumerate(definition["channels"]):
        if caches is None:
            sim.dyna.tissue_target_inds["explicit"] = np.asarray(row["targets"], np.int64)
            chan = SimpleNamespace(channel_profiles_list=["explicit"])
            try:
                ns["init_channel"](
                    chan,
                    inv["classes"][row["class_name"]]["family"],
                    row["class_name"],
                    row["maxDm_m2_s"],
                    phase,
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
                    ),
                ) from error
            initializations.append(copy.deepcopy(vars(chan.channel_core)))
        else:
            chan = SimpleNamespace(
                channel_core=object.__new__(ns[row["class_name"]]), maxDm=row["maxDm_m2_s"]
            )
            vars(chan.channel_core).update(copy.deepcopy(caches[slot]))
        chan.init_active = row["init_active"]
        chan.alpha_eval_string = "_modulators['" + row["id"] + "']"
        net.channels[row["id"]] = chan
    ns["_modulators"] = {
        name: np.asarray(value, np.float64) for name, value in live["modulators"].items()
    }
    pending, route = {}, {}

    def population_before(name, chan, actual, params, actual_phase):
        pending.clear()
        slot = list(net.channels).index(name)
        row = definition["channels"][slot]
        skip = actual_phase.kind is ns["SimPhaseKind"].INIT and not chan.init_active
        pending.update(
            channel_id=name,
            class_name=row["class_name"],
            skipped=skip,
            cache_before=copy.deepcopy(vars(chan.channel_core)),
            voltage_before_V=actual.vm.copy(),
            values_before=material_native.values(actual),
            routes=[],
            dt_s=params.dt,
            native_dt=params.dt * chan.channel_core.time_unit
            if not skip and getattr(chan.channel_core, "kinetic_gate", True)
            else 0.0,
        )

    def route_before(ion, relative, chan, actual):
        i = definition["ion_ids"].index(ion)
        route.clear()
        route.update(
            ion_id=ion,
            relative_permeability=float(relative),
            sampled_bulk_mM=actual.cc_cells[i].copy(),
            sampled_membrane_mM=actual.cc_cells[i][cells.mem_to_cells].copy(),
            sampled_bath_mM=np.asarray(actual.cc_env[i]).copy(),
            values_before=material_native.values(actual),
            network_current_before_A_m2=net.extra_J_mem.copy(),
        )

    def route_after(ion, relative, chan, actual):
        route.update(
            values_after=material_native.values(actual),
            cache_after=copy.deepcopy(vars(chan.channel_core)),
            network_current_after_A_m2=net.extra_J_mem.copy(),
        )
        pending["routes"].append(copy.deepcopy(route))
        observe("channel_direct", definition["ion_ids"].index(ion), actual)

    def population_after(name, chan, actual, params, actual_phase):
        slot = list(net.channels).index(name)
        if not pending["skipped"]:
            counts[slot] += 1
        else:
            observe("channel_skipped", None, actual)
        pending.update(
            cache_after=copy.deepcopy(vars(chan.channel_core)),
            call_index=counts[slot],
            voltage_after_V=actual.vm.copy(),
            values_after=material_native.values(actual),
        )
        events.append(copy.deepcopy(pending))

    ns.update(
        _population_before=population_before,
        _population_after=population_after,
        _population_gate_updated=lambda actual: observe("channel_update", None, actual),
        _route_before=route_before,
        _route_after=route_after,
        _route_local=lambda name, value: route.__setitem__(name, np.array(value, copy=True)),
    )
    publication = {}

    def late(actual, geometry, params, t):
        if policy is None:
            publication.update(
                calcium_phase=dict(
                    enabled=False,
                    source_completed=True,
                    rate_before=None,
                    rate_after=None,
                    arithmetic={},
                )
            )
        else:
            calcium_observations.clear()
            old = actual.rate_CaATP.copy()
            before_values = material_native.values(actual)
            try:
                ns["ca_handler"](actual, geometry, params)
            except Exception as error:
                publication.update(
                    calcium_phase=dict(
                        source_completed=False,
                        source_exception=type(error).__name__,
                        values_before=before_values,
                        values_after=material_native.values(actual),
                        rate_before=old,
                        rate_after=actual.rate_CaATP.copy(),
                        arithmetic=copy.deepcopy(calcium_observations),
                    )
                )
                observe("calcium_handler_failure", actual.iCa, actual)
                raise
            publication.update(
                calcium_phase=dict(
                    source_completed=True,
                    values_before=before_values,
                    values_after=material_native.values(actual),
                    rate_before=old,
                    rate_after=actual.rate_CaATP.copy(),
                    arithmetic=copy.deepcopy(calcium_observations),
                    alpha_Ca=params.alpha_Ca,
                    rho_pump=actual.rho_pump.copy(),
                    block_unused=actual.CaATP_block.copy(),
                    Ca_dyn=0,
                    cc_env_rank=actual.cc_env.ndim,
                    bath_row_shape=list(actual.cc_env[actual.iCa].shape),
                )
            )
            observe("calcium_handler", actual.iCa, actual)
        ns["clear_run_loop"](net, actual)
        observe("network_clear", None, actual)
        execution = network_native.execution_inputs(
            net,
            actual,
            geometry,
            params,
            definition["network"],
            definition["ion_ids"],
            material_native.values(actual),
        )
        feedback["transporter_execution"] = execution
        try:
            net.run_loop_transporters(t, actual, geometry, params)
            execution["source_completed"] = True
            observe("network_transporters", None, actual)
        finally:
            execution.update(
                values_after=material_native.values(actual),
                concentrations_after=network_native.concentrations(net),
                fluxes_after=network_native.fluxes(net),
                extra_current_after_A_m2=net.extra_J_mem.copy(),
                frames=copy.deepcopy(feedback["transporter_frames"]),
            )
            feedback.update(
                cache_after=network_native.cache(net),
                controls_after=dict(
                    gj_block=actual.gj_block.copy(), NaKATP_block=actual.NaKATP_block.copy()
                ),
            )
        ns["run_loop_channels"](net, phase)

        feedback.update(
            values_before=material_native.values(actual),
            molecule_states_before=network_native.snapshot(net.molecules),
            controls_before=dict(
                gj_block=np.array(actual.gj_block, copy=True),
                NaKATP_block=np.array(actual.NaKATP_block, copy=True),
            ),
            incoming_channel_current_A_m2=net.extra_J_mem.copy(),
        )
        try:
            net.run_loop_modulators(actual, geometry, params)
            observe("network_modulators", None, actual)
            net.run_loop(phase, t)
            observe("network_molecule_chemistry", None, actual)
            feedback.update(source_completed=True, configured_chemistry_run_loop_completed=True)
        finally:
            feedback.update(
                cache_after=network_native.cache(net),
                chemical_rhs_evaluated=any(
                    row["stage"] == "rhs_ready" for row in feedback["molecule_frames"]
                ),
                chemical_commit_completed=feedback["source_completed"],
                executed_chemistry=any(
                    row["stage"] == "rhs_ready" for row in feedback["molecule_frames"]
                )
                and (
                    bool(definition["network"]["reactions"])
                    or any(row["growth"]["enabled"] for row in definition["network"]["molecules"])
                ),
                molecular_transports_completed=sum(
                    row["stage"] == "transport_after" for row in feedback["molecule_frames"]
                ),
                molecule_states_after=network_native.snapshot(net.molecules),
                values_after=material_native.values(actual),
                controls_after=dict(
                    gj_block=np.array(actual.gj_block, copy=True),
                    NaKATP_block=np.array(actual.NaKATP_block, copy=True),
                ),
            )
        publication.update(
            extra_current_A_m2=net.extra_J_mem.copy(),
            extra_charge_C_m3=net.extra_rho_cells.copy(),
            energy_charge=net.chi.copy(),
            current_publication="replace" if params.substances_affect_charge else "retain incoming",
            aliases_follow_live_rows=all(
                np.shares_memory(net.cell_concs[name], actual.cc_cells[i])
                for i, name in enumerate(definition["ion_ids"])
            ),
        )
        observe("network_publish", None, actual)

    return late, dict(
        network_feedback=feedback,
        initializations=initializations,
        events=events,
        calls=counts,
        network=publication,
        caches=lambda: [copy.deepcopy(vars(chan.channel_core)) for chan in net.channels.values()],
        source_sites=sites,
        native_source=pins,
    )
