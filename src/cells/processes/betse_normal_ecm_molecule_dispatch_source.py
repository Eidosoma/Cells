# ruff: noqa: E501, F841
"""Private native general owner and explicit FULL general-then-GRN source slices.

No shared scientific module is patched. Qualified molecule/ECM kernels are
reused; helper role lowering changes owner access and evidence wiring only.
"""

import posixpath as pathnames
from collections import OrderedDict

from cells.processes import betse_normal_ecm_catalog_join_source as qualified

MasterOfNetworks = qualified.MasterOfNetworks
MasterOfGenes = qualified.MasterOfGenes
set_net_opts = qualified.base.set_net_opts
logs = qualified.logs
clone = qualified.clone
wire = qualified.wire
PARAMETERS = qualified.PARAMETERS
validate_cached_channels = qualified.validate_cached_channels
channel_fields = qualified.channel_fields
material_values = qualified.material_values


def science_general():
    return dict(qualified.science(), MasterOfGenes=MasterOfMolecules)


class MasterOfMolecules:
    def __init__(self, p):
        self.savedMoM = pathnames.join(p.init_pickle_dirname, "GeneralNetwork.betse")

    def read_mol_config(self, phase):
        cells = phase.cells
        p = phase.p
        sim = phase.sim
        config_dic = p.network_config
        substances_config = config_dic["biomolecules"]
        reactions_config = config_dic.get("reactions", None)
        transporters_config = config_dic.get("transporters", None)
        channels_config = config_dic.get("channels", None)
        modulators_config = config_dic.get("modulators", None)
        self.core = MasterOfNetworks(sim, cells, substances_config, p)
        self.core.time_dila = float(config_dic.get("time dilation factor", 1.0))
        self.core.read_substances(sim, cells, substances_config, p)
        self.core.tissue_init(phase, substances_config)
        if reactions_config is not None:
            self.core.read_reactions(reactions_config, sim, cells, p)
            self.core.write_reactions()
            self.core.create_reaction_matrix()
            self.core.write_reactions_env()
            self.core.create_reaction_matrix_env()
            self.reactions = True
        else:
            self.core.create_reaction_matrix()
            self.core.create_reaction_matrix_env()
            self.reactions = False
        if transporters_config is not None:
            self.core.read_transporters(transporters_config, phase)
            self.core.write_transporters(sim, cells, p)
            self.transporters = True
        else:
            self.transporters = False
        if channels_config is not None:
            self.core.read_channels(channels_config, phase)
            self.channels = True
        else:
            self.channels = False
        if modulators_config is not None:
            self.core.read_modulators(modulators_config, sim, cells, p)
            self.modulators = True
        else:
            self.modulators = False
        self.core.net_plot_opts = config_dic.get("network plotting", None)
        set_net_opts(self.core, self.core.net_plot_opts, p)
        optim_exists = config_dic.get("optimization", None)
        if optim_exists is not None:
            opti = config_dic["optimization"]["optimize network"]
            self.core.opti_N = config_dic["optimization"]["optimization steps"]
            self.core.opti_method = config_dic["optimization"]["optimization method"]
            self.core.target_vmem = float(config_dic["optimization"]["target Vmem"])
            self.core.opti_T = float(config_dic["optimization"]["optimization T"])
            self.core.opti_step = float(config_dic["optimization"]["optimization step"])
            if opti:
                logs.log_info("Analyzing the general network for optimal rates...")
                self.core.optimizer(sim, cells, p)
                self.reinitialize(phase)

    def reinitialize(self, phase):
        cells = phase.cells
        p = phase.p
        sim = phase.sim
        config_dic = p.network_config
        self.core.time_dila = float(config_dic.get("time dilation factor", 1.0))
        substances_config = config_dic["biomolecules"]
        reactions_config = config_dic.get("reactions", None)
        transporters_config = config_dic.get("transporters", None)
        channels_config = config_dic.get("channels", None)
        modulators_config = config_dic.get("modulators", None)
        self.core.tissue_init(phase, substances_config)
        if reactions_config is not None:
            self.core.read_reactions(reactions_config, sim, cells, p)
            self.core.write_reactions()
            self.core.create_reaction_matrix()
            self.core.write_reactions_env()
            self.core.create_reaction_matrix_env()
            self.reactions = True
        else:
            self.core.create_reaction_matrix()
            self.core.create_reaction_matrix_env()
            self.reactions = False
        if transporters_config is not None:
            self.core.read_transporters(transporters_config, phase)
            self.core.write_transporters(sim, cells, p)
            self.transporters = True
        else:
            self.transporters = False
        if channels_config is not None:
            self.core.read_channels(channels_config, phase)
            self.channels = True
        else:
            self.channels = False
        if modulators_config is not None:
            self.core.read_modulators(modulators_config, sim, cells, p)
            self.modulators = True
        else:
            self.modulators = False


def initialize_both(self, t, phase, cells, p, *, hook):
    if p.molecules_enabled:
        hook("molecules", "before_setup", self, phase)
        if self.molecules is None:
            logs.log_info("Initializing general network...")
            self.molecules = MasterOfMolecules(p)
            self.molecules.read_mol_config(phase)
        else:
            logs.log_info("Reinitializing the general regulatory network for simulation...")
            self.molecules.reinitialize(phase)
        hook("molecules", "after_setup", self, phase)
    if p.grn_enabled:
        hook("grn", "before_setup", self, phase)
        if self.grn is None:
            logs.log_info("Initializing gene regulatory network...")
            self.grn = MasterOfGenes(p)
            self.grn.read_gene_config(phase)
        else:
            logs.log_info("Reinitializing the gene regulatory network for simulation...")
            self.grn.reinitialize(phase)
        hook("grn", "after_setup", self, phase)


def dispatch_both(self, t, phase, cells, p, *, hook):
    if p.molecules_enabled:
        hook("molecules", "before_dispatch", self, phase)
        self.molecules.core.clear_run_loop(self)
        hook("molecules", "clear_run_loop", self, phase)
        if self.molecules.transporters:
            self.molecules.core.run_loop_transporters(t, self, cells, p)
            hook("molecules", "run_loop_transporters", self, phase)
        if self.molecules.channels:
            self.molecules.core.run_loop_channels(phase)
            hook("molecules", "run_loop_channels", self, phase)
        if self.molecules.modulators:
            self.molecules.core.run_loop_modulators(self, cells, p)
            hook("molecules", "run_loop_modulators", self, phase)
        self.molecules.core.run_loop(phase=phase, t=t)
        hook("molecules", "run_loop", self, phase)
    if p.grn_enabled:
        hook("grn", "before_dispatch", self, phase)
        self.grn.core.clear_run_loop(self)
        hook("grn", "clear_run_loop", self, phase)
        if self.grn.transporters:
            self.grn.core.run_loop_transporters(t, self, cells, p)
            hook("grn", "run_loop_transporters", self, phase)
        if self.grn.channels:
            self.grn.core.run_loop_channels(phase)
            hook("grn", "run_loop_channels", self, phase)
        if self.grn.modulators:
            self.grn.core.run_loop_modulators(self, cells, p)
            hook("grn", "run_loop_modulators", self, phase)
        self.grn.core.run_loop(phase=phase, t=t)
        hook("grn", "run_loop", self, phase)


def cache_general(ctx):
    return dict(
        kind="cells.ecm_catalog_grn_owner_cache@1",
        wire=wire(getattr(ctx.sim, "molecules", None), ctx.sim),
        coefficient_fields={
            name: clone(getattr(ctx.sim, name))
            for name in ("D_env_weight", "D_env_weight_base", "TJ_targets")
            if hasattr(ctx.sim, name)
        },
        initial_channel_fields=clone(ctx.initial_channel_fields),
        channel_calls=clone(ctx.channel_calls),
    )


def restore_general(ctx, incoming):
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
    api = science_general()
    owner = object.__new__(api["MasterOfGenes"])
    vars(owner).update(clone(raw["owner_fields"]))
    net = object.__new__(api["MasterOfNetworks"])
    vars(net).update(clone(raw["core_fields"]))
    owner.core, ctx.sim.molecules = (net, owner)
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


def before_general(ctx, material_declaration):
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
            grn_configuration=clone(p.network_config),
            reactions=clone(p.network_config["reactions"]),
            modulators=clone(p.network_config.get("modulators") or []),
        ),
        values_before=material_values(sim),
        molecule_states_before={
            name: {
                key: clone(getattr(obj, key))
                for key in ("c_cells", "cc_at_mem", "c_env", "flux_intra")
            }
            for name, obj in net.molecules.items()
        },
        cache_before=cache_general(ctx),
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
        simulator_fields_before=wire(sim.molecules, sim)["simulator_fields"],
        owner=owner_evidence_general(ctx),
    )


def attach_general(ctx, material_declaration, observer=None, channel_observer=None):
    sim, p, net = (ctx.sim, ctx.p, ctx.net)

    def chemistry(stage, species, actual):
        ctx.trace["molecule_frames"].append(
            dict(
                stage=stage, species=species, values=material_values(sim), cache=cache_general(ctx)
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
            ctx.trace["before_channels"] = before_general(ctx, material_declaration)
            ctx.trace["before_channels"].update(mode="channels", catalog=clone(ctx.catalog))
            if channel_observer is not None:
                channel_observer(clone(ctx.trace["before_channels"]))
        if stage == "run_loop_channels" or (
            stage == "clear_run_loop" and (not ctx.sim.molecules.channels)
        ):
            ctx.trace["before"] = before_general(ctx, material_declaration)
            if observer is not None:
                observer(clone(ctx.trace["before"]))

    (
        net._observe_chem,
        net._observe_rhs,
        net._observe_control,
        net._observe_dispatch,
        p._mover_observe,
    ) = (chemistry, rhs, control, dispatched, mover)


def install_channel_observer_general(ctx):

    def observe(stage, name, local):
        obj = local.get("chan", local.get("obj"))
        values = dict(
            stage=stage,
            name=name,
            values=material_values(ctx.sim),
            cache=cache_general(ctx),
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
            incoming_current=clone(ctx.sim.molecules.core.extra_J_mem),
        )
        if stage.startswith("initialize") or stage == "configuration_after":
            ctx.trace["channel_initializations"].append(values)
        else:
            if stage == "population_after":
                ctx.channel_calls[name] += 1
                values["cache"] = cache_general(ctx)
            ctx.trace["channel_events"].append(values)

    ctx.p._catalog_observe = observe


def owner_evidence_general(ctx):
    return dict(
        owner_class=type(ctx.sim.molecules).__name__,
        core_class=type(ctx.sim.molecules.core).__name__,
        actual_core_identity=ctx.sim.molecules.core is ctx.net,
        grn_enabled=ctx.p.grn_enabled,
        molecules_enabled=ctx.p.molecules_enabled,
        standalone_sim_grn=False,
    )
