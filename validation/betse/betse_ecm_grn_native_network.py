# ruff: noqa: E501, E402
"""Independent authenticated original-AST ECM GRN scientific namespace."""

import ast
import copy
import hashlib
import json
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.betse import betse_normal_grn_join_native_network as previous

clone, public, wire = previous.clone, previous.public, previous.wire
PROTOCOL = Path(__file__).with_name("betse_ecm_grn_protocol.json")
_SCIENCE = None


class ObserveEnvironment(ast.NodeTransformer):
    def visit_Assign(self, node):
        target = ast.unparse(node.targets[0])
        label = {
            "cenv[-1, :]": "ecm_clamp",
            "(gcx, gcy)": "ecm_gradient",
            "(fx, fy)": "ecm_flux",
        }.get(target)
        if target == "cenv" and "div_fa" in ast.unparse(node.value):
            label = "ecm_euler"
        return (
            [node, *ast.parse("p._mover_observe(" + repr(label) + ",name,locals(),sim)").body]
            if label
            else node
        )


def extra_nodes(root):
    tb = ast.parse((root / "science/sim_toolbox.py").read_text())
    fd = ast.parse((root / "science/math/finitediff.py").read_text())
    return [
        copy.deepcopy(n)
        for tree, names in (
            (tb, {"nernst_planck_flux", "div_env"}),
            (fd, {"gradient", "diff", "divergence", "integrator"}),
        )
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name in names
    ]


def derive_radial(self):
    self.rads = self.mem_mids_flat - self.cell_centres[self.mem_to_cells]
    self.R_rads = np.sqrt(self.rads[:, 0] ** 2 + self.rads[:, 1] ** 2)


def derive_context(self, cells):
    D_env_weight = self.D_env[self.iNa] / self.D_env[self.iNa].max()
    self.D_env_weight = D_env_weight.reshape(cells.X.shape)
    self.D_env_weight_base = np.copy(self.D_env_weight)
    self.TJ_targets = np.hstack(
        (cells.all_bound_mem_inds, cells.interior_bound_mem_inds, cells.ecm_inds_bound_cell)
    )
    derive_radial(cells)


def literal_nodes(root):
    nodes = previous.literal_nodes(root)
    for node in nodes:
        if isinstance(node, ast.FunctionDef) and node.name == "molecule_mover":
            ObserveEnvironment().visit(node)
    helper_tree = ast.parse(Path(__file__).read_text())
    derived = [
        copy.deepcopy(n)
        for n in helper_tree.body
        if isinstance(n, ast.FunctionDef) and n.name in {"derive_radial", "derive_context"}
    ]
    return nodes + extra_nodes(root) + derived


def science():
    global _SCIENCE
    if _SCIENCE is None:
        pins = json.loads(PROTOCOL.read_text())["native_source"]
        for name, digest in pins["source_sha256"].items():
            data = (Path(pins["checkout"]) / name).read_bytes()
            assert hashlib.sha256(data).hexdigest() == digest
            assert data == (Path(pins["installed_package"]).parent / name).read_bytes()
        ns = previous.authenticated()
        exec(
            compile(
                ast.fix_missing_locations(
                    ast.Module(
                        body=literal_nodes(Path(pins["checkout"]) / "betse"), type_ignores=[]
                    )
                ),
                "<original ECM GRN scientific bodies>",
                "exec",
            ),
            ns,
        )
        ns["fd"] = SimpleNamespace(
            **{name: ns[name] for name in ("gradient", "divergence", "integrator")}
        )
        ns["stb"] = SimpleNamespace(molecule_mover=ns["molecule_mover"], no_negs=ns["no_negs"])
        _SCIENCE = ns
    return _SCIENCE


MATERIAL_PAIRS = (
    ("cell_mol_m3", "cc_cells"),
    ("membrane_mol_m3", "cc_at_mem"),
    ("environment_mol_m3", "cc_env"),
    ("voltage_V", "vm"),
    ("membrane_flux_mol_m2_s", "fluxes_mem"),
    ("junction_flux_mol_m2_s", "fluxes_gj"),
    ("environment_flux_x_mol_m2_s", "fluxes_env_x"),
    ("environment_flux_y_mol_m2_s", "fluxes_env_y"),
    ("junction_voltage_V", "vgj"),
    ("junction_field_source", "Egj"),
    ("gap_open", "gjopen"),
)
PARAMETERS = (
    "z",
    "Dm",
    "Do",
    "Dgj",
    "c_bound",
    "TJ_factor",
    "ignoreTJ",
    "ignoreGJ",
    "ignore_ECM_pump",
    "update_intra_conc",
    "transmem",
    "modify_time_factor",
    "Mu_mem",
    "u_mt",
    "scale_factor",
    "active_pumping",
    "ion_channel_gating",
    "change_bounds",
    "cell_clamp",
)


def material_values(sim):
    return {key: clone(getattr(sim, attr)) for key, attr in MATERIAL_PAIRS} | dict(
        junction_field_xy_source=np.column_stack((sim.E_gj_x, sim.E_gj_y))
    )


def augment(sim, cells, p, definition, ion_ids):
    p.ions_dict = {name: 1 for name in ion_ids}
    p.ions_dict.setdefault("Ca", 0)
    p.grn = SimpleNamespace(conf=clone(definition["configuration"]))
    p.grn_enabled, p.molecules_enabled, p.plot_network = True, False, False
    sim.get_ion = lambda name: ion_ids.index(name)
    sim.iNa, sim.iK = sim.get_ion("Na"), sim.get_ion("K")
    sim.cdl = len(cells.cell_i)
    p.fluid_flow = False
    for key in ("all_bound_mem_inds", "interior_bound_mem_inds", "ecm_inds_bound_cell"):
        setattr(cells, key, np.asarray(definition["grid_index_groups"][key], np.int64).copy())
    science()["derive_context"](sim, cells)
    return SimpleNamespace(
        sim=sim,
        cells=cells,
        p=p,
        definition=definition,
        ion_ids=ion_ids,
        phase=SimpleNamespace(sim=sim, cells=cells, p=p, kind="SIM", dyna=SimpleNamespace()),
        trace=new_trace(),
    )


def cache(ctx):
    return dict(
        kind="cells.ecm_grn_owner_cache@1",
        wire=wire(ctx.sim.grn, ctx.sim),
        coefficient_fields={
            name: clone(getattr(ctx.sim, name))
            for name in ("D_env_weight", "D_env_weight_base", "TJ_targets")
        },
    )


def cold(ctx):
    ctx.sim.grn = None
    ctx.phase.kind = "INIT"
    ctx.p.substances_affect_charge = ctx.definition["cold_publish"]
    science()["initialize_owner"](ctx.sim, 0.0, ctx.phase, ctx.cells, ctx.p)
    return cache(ctx)


def restore(ctx, incoming):
    if incoming is None or incoming.get("kind") != "cells.ecm_grn_owner_cache@1":
        raise ValueError("Require complete ECM GRN owner cache")
    raw = incoming["wire"]
    if set(raw) != {
        "owner_fields",
        "core_fields",
        "molecule_fields",
        "reaction_fields",
        "modulator_fields",
        "ion_boundary_state",
        "simulator_fields",
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
    api = science()
    owner = object.__new__(api["MasterOfGenes"])
    vars(owner).update(clone(raw["owner_fields"]))
    net = object.__new__(api["MasterOfNetworks"])
    vars(net).update(clone(raw["core_fields"]))
    owner.core, ctx.sim.grn = net, owner
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
    # The current packet's ionic boundary vector remains authoritative. Gene
    # boundary scalars already travel with their complete molecule fields.
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


def owner_evidence(ctx):
    return dict(
        owner_class=type(ctx.sim.grn).__name__,
        core_class=type(ctx.sim.grn.core).__name__,
        actual_core_identity=ctx.sim.grn.core is ctx.net,
        grn_enabled=ctx.p.grn_enabled,
        molecules_enabled=ctx.p.molecules_enabled,
        standalone_sim_grn=False,
    )


def before(ctx, material_declaration):
    sim, p, cells, net = ctx.sim, ctx.p, ctx.cells, ctx.net
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


def attach(ctx, material_declaration, observer=None):
    sim, p, net = ctx.sim, ctx.p, ctx.net

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
            ctx.trace["before"] = before(ctx, material_declaration)
            if observer is not None:
                observer(clone(ctx.trace["before"]))

    (
        net._observe_chem,
        net._observe_rhs,
        net._observe_control,
        net._observe_dispatch,
        p._mover_observe,
    ) = chemistry, rhs, control, dispatched, mover


def run_dispatch(ctx, material_declaration, publication, observer=None):
    ctx.p.substances_affect_charge = publication
    ctx.phase.kind = "SIM"
    ctx.net = ctx.sim.grn.core
    attach(ctx, material_declaration, observer)
    try:
        science()["dispatch"](ctx.sim, 0.0, ctx.phase, ctx.cells, ctx.p)
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
                row["stage"] == "transport_after" for row in ctx.trace["molecule_frames"]
            ),
        )
    return ctx.trace


def _number(value, positive=False):
    return (
        type(value) in (int, float)
        and np.isfinite(value)
        and (value > 0 if positive else value >= 0)
    )


def validate_definition(definition, ids, n, m, e):
    required = {
        "owner",
        "configuration",
        "cold_publish",
        "grid_index_groups",
        "initial_controls",
        "initial_ion_boundary",
        "raw_initialization_fault",
        "scope",
    }
    if set(definition) != required or definition["owner"] != "grn":
        raise ValueError("Require a complete genuine ECM GRN declaration")
    if definition["scope"] != {
        "mitochondria": False,
        "fluid": False,
        "cuts": False,
        "standalone": False,
    }:
        raise ValueError("ECM GRN mitochondria/fluid/cuts/standalone require separate state")
    if not {"Na", "K"} <= set(ids):
        raise ValueError("Require actual Na/K rows for the ECM network context")
    cfg = definition["configuration"]
    if set(cfg) - {"biomolecules", "reactions", "modulators", "time dilation factor"}:
        raise ValueError("Other ECM GRN lifecycle branches require separate state")
    if not _number(cfg.get("time dilation factor", 1.0), True):
        raise ValueError("Require positive source time dilation")
    if type(definition["cold_publish"]) is not bool:
        raise ValueError("Require an explicit ECM cold publication flag")
    rows = cfg["biomolecules"]
    if len(rows) != 2 or [row["name"] for row in rows] != ["X", "Y"]:
        raise ValueError("Require actual configured X/Y gene products")
    fault = definition["raw_initialization_fault"]
    if fault not in (None, "X", "Y"):
        raise ValueError("Undeclared ECM cold source failure")
    for row in rows:
        needed = {
            "name",
            "cell conc",
            "env conc",
            "Dm",
            "Do",
            "z",
            "update intracellular",
            "TJ permeable",
            "GJ impermeable",
            "TJ factor",
            "growth and decay",
            "plotting",
        }
        if needed - set(row) != ({"Dm"} if fault == row["name"] else set()) or set(row) - needed - {
            "Dgj",
            "scale factor",
            "use time dilation",
        }:
            raise ValueError("Require complete bounded ECM gene configuration")
        if row["z"] not in (-1.0, 0.0, 1.0) or row["update intracellular"] is not False:
            raise ValueError("Require bounded monovalent instant-mixing ECM products")
        if (
            any(type(row[key]) is not bool for key in ("TJ permeable", "GJ impermeable"))
            or type(row.get("use time dilation", False)) is not bool
        ):
            raise ValueError("Require explicit source transport flags")
        if not all(
            _number(row.get(key, default))
            for key, default in (
                ("cell conc", 0.0),
                ("env conc", 0.0),
                ("Dm", 0.0),
                ("Do", 0.0),
                ("Dgj", 1e-16),
                ("TJ factor", 1.0),
            )
        ) or not _number(row.get("scale factor", 1.0), True):
            raise ValueError("Require finite source concentrations and coefficients")
        if row["plotting"] != {
            "plot 2D": False,
            "animate": False,
            "autoscale colorbar": True,
            "max val": 1.0,
            "min val": 0.0,
        }:
            raise ValueError("ECM network plotting is outside this boundary")
        gad = row["growth and decay"]
        if gad is not None:
            allowed = {
                "production rate",
                "decay rate",
                "decay max",
                "scale factor",
                "apply to",
                "activators",
                "Km activators",
                "n activators",
                "inhibitors",
                "Km inhibitors",
                "n inhibitors",
                "decay activators",
                "Km decay activators",
                "n decay activators",
                "decay inhibitors",
                "Km decay inhibitors",
                "n decay inhibitors",
            }
            if (
                set(gad) - allowed
                or gad["apply to"] != "all"
                or not _number(gad["production rate"])
                or not _number(gad["decay rate"])
                or not _number(gad.get("decay max", 0.0))
                or not _number(gad.get("scale factor", 1.0), True)
            ):
                raise ValueError("Require ordinary all-cell ECM gene regulation")
            for prefix in ("", "decay "):
                for sign in ("activators", "inhibitors"):
                    names = gad.get(prefix + sign)
                    if names is None:
                        continue
                    for name, km, exponent in zip(
                        names, gad["Km " + prefix + sign], gad["n " + prefix + sign], strict=True
                    ):
                        if (
                            name not in (*ids, "X", "Y")
                            or not _number(km, True)
                            or not _number(exponent, True)
                        ):
                            raise ValueError("Invalid ECM gene Hill regulator")
    if definition["cold_publish"] and any(row["z"] != 0 for row in rows):
        raise ValueError("Charged ECM cold compensation is separately scoped")
    if rows[0]["z"] != rows[1]["z"] or rows[0].get("scale factor", 1.0) != rows[1].get(
        "scale factor", 1.0
    ):
        raise ValueError("Preserve X-to-Y formal charge weighting")
    reactions = cfg["reactions"]
    if len(reactions) != 1:
        raise ValueError("Require one configured source X-to-Y reaction")
    reaction = reactions[0]
    if (
        reaction["name"] != "X_to_Y"
        or reaction["reaction zone"] != "cell"
        or reaction["reactants"] != ["X"]
        or reaction["products"] != ["Y"]
        or reaction["reactant multipliers"] != [1.0]
        or reaction["product multipliers"] != [1.0]
        or reaction["standard free energy"] != "None"
    ):
        raise ValueError("Require the irreversible cell-zone conversion")
    for key in ("Km reactants", "Km products"):
        if len(reaction[key]) != 1 or not _number(reaction[key][0], True):
            raise ValueError("Require positive source reaction constants")
    if not _number(reaction["max rate"]):
        raise ValueError("Require a finite source reaction rate")
    for mod in cfg.get("modulators") or []:
        allowed = {
            "name",
            "target",
            "max effect",
            "activators",
            "activator Km",
            "activator n",
            "activator zone",
            "inhibitors",
            "inhibitor Km",
            "inhibitor n",
            "inhibitor zone",
        }
        if (
            set(mod) - allowed
            or mod["target"] not in ("GJ", "Na/K-ATPase")
            or not _number(mod["max effect"])
        ):
            raise ValueError("Require bounded ion-driven ECM modulators")
        for sign in ("activator", "inhibitor"):
            names = mod.get(sign + "s")
            if names is None:
                continue
            zone = mod.get(sign + " zone", ["cell"] * len(names))
            for name, km, exponent, where in zip(
                names, mod[sign + " Km"], mod[sign + " n"], zone, strict=True
            ):
                if (
                    name not in ids
                    or not _number(km, True)
                    or not _number(exponent, True)
                    or where not in ("cell", "env")
                ):
                    raise ValueError("Invalid ECM modulator input")
    if set(definition["grid_index_groups"]) != {
        "all_bound_mem_inds",
        "interior_bound_mem_inds",
        "ecm_inds_bound_cell",
    }:
        raise ValueError("Require the three original TJ index groups")
    for group in definition["grid_index_groups"].values():
        if any(type(index) is not int or not 0 <= index < e for index in group):
            raise ValueError("Require owned in-grid TJ indices")
    if set(definition["initial_controls"]) != {"gj_block", "NaKATP_block"} or any(
        len(row) != m or not all(_number(value) for value in row)
        for row in definition["initial_controls"].values()
    ):
        raise ValueError("Require complete ECM network controls")
    if len(definition["initial_ion_boundary"]) != len(ids) or not all(
        _number(v) for v in definition["initial_ion_boundary"]
    ):
        raise ValueError("Require every original ionic boundary scalar")


def new_trace():
    return dict(
        molecule_frames=[],
        mover_frames=[],
        rhs={},
        control_writes=[],
        dispatch_stages=[],
        source_completed=False,
    )
