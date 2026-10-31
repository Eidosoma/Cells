# ruff: noqa: E501
"""Native reinitialization order on retained, explicitly supplied INIT owners.

Profile picker outputs and the mechanical DEC view are conditional supplied
seams. They are not native seed/load or physical geometry attestations. Both
process RNG streams are supplied explicitly; pickle does not own those streams.
"""

import hashlib
import json
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_ecm_transport as material
from cells.processes import betse_mechanics_join as mechanics
from cells.processes import betse_normal_ecm_calcium_join as calcium
from cells.processes import betse_normal_ecm_catalog_join_source as catalog
from cells.processes import betse_normal_ecm_event_join_source as events
from cells.processes import betse_normal_ecm_init_phase_setup as init_setup
from cells.processes import betse_normal_ecm_molecule_lifecycle_owners as owners
from cells.processes import betse_normal_ecm_molecule_lifecycle_source as source
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_perturbations as perturbations

ROLES = ("Na", "K", "Cl", "Ca", "M", "P")


class SetupRejected(RuntimeError):
    def __init__(self, error, partial):
        super().__init__(str(error))
        self.partial = ions.freeze(partial)


def numpy_restore(saved):
    perturbations.native_stream_from_manifest(saved)
    rng = np.random.RandomState(0)
    state = saved["state"]
    rng.set_state((state[0], np.asarray(state[1], np.uint32), state[2], state[3], state[4]))
    return rng


def numpy_manifest(rng):
    state = rng.get_state()
    payload = dict(
        rng_id=perturbations.NATIVE_RNG_ID,
        numpy_version=np.__version__,
        state=[state[0], state[1].tolist(), int(state[2]), int(state[3]), float(state[4])],
    )
    identity = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return dict(payload, identity=identity)


class FixedPickerOutputs:
    def __init__(self, cells, membranes):
        self.cells = np.asarray(cells, dtype=np.int64)
        self.membranes = np.asarray(membranes, dtype=np.int64)

    def pick_cells_and_mems(self, *, cells, p):
        return (self.cells.copy(), self.membranes.copy())


def profile_owner(rows):
    return SimpleNamespace(
        tissue_name_to_profile={
            row["name"]: SimpleNamespace(
                picker=FixedPickerOutputs(row["cell_indices"], row["membrane_indices"]),
                **row["diffusion_m2_s"],
            )
            for row in rows
        }
    )


def mechanical_entry(init_parent, definition):
    values = ions.data(init_parent.mechanics.cache)
    values = {key: np.array(value, copy=True) for key, value in values.items()}
    n = len(definition["geometry"]["cell_ids"])
    values["div_u_osmo"] = np.zeros(n)
    if definition["policy"]["deformation"]:
        values["d_cells_x"] = np.zeros(n)
        values["d_cells_y"] = np.zeros(n)
    return values


def finalized_owner(template, actual, p):
    owner = ions.data(template)
    owner.update(
        {
            key: material.plain(getattr(actual, key))
            for key in ("cell_target_inds", "tissue_target_inds", "env_target_inds")
        }
    )
    excluded = {
        "tissue_name_to_profile",
        "cell_target_inds",
        "tissue_target_inds",
        "env_target_inds",
    }
    owner["handler_fields"] = {
        key: material.plain(value)
        for key, value in vars(actual).items()
        if key not in excluded
        and (not key.startswith(("dyna_", "scalar_")))
        and (not callable(value))
    }
    callbacks = {}
    for key, suffix in (
        ("Na_mem", "Namem"),
        ("K_mem", "Kmem"),
        ("Cl_mem", "Clmem"),
        ("Ca_mem", "Camem"),
        ("pressure", "P"),
    ):
        row = owner["scheduled_options"][key]
        if row == 0:
            continue
        function = row[5]
        if function not in ("None", "f_sweep"):
            raise ValueError(
                "Transition source setup admits only constant or real SIM f_sweep callbacks"
            )
        dynamic = (
            dict(kind="constant")
            if function == "None"
            else dict(
                kind="sweep",
                start=p.f_scan_properties["f start"],
                slope=p.f_scan_properties["f slope"],
                provenance="Actual SIM f_sweep finalizer result",
            )
        )
        callbacks[suffix] = dict(
            source_function=function,
            source_scalar=material.plain(getattr(actual, "scalar_" + suffix)),
            dynamic=dynamic,
            provenance="Actual retained-owner SIM finalizer callback output, not evaluated at setup",
        )
    owner["callbacks"] = callbacks
    return owner


def prepare(init_binding, init_parent, raw, observer=None):
    """Execute real reinitialize/setup bodies; never call a fresh cold initializer."""
    raw = legacy_setup_inputs(raw)
    cfg = ions.data(raw["source_setup"])
    template = ions.data(raw["sim_composition_template"])
    packet = template["event_inputs"]
    field = packet["field"]
    field["initial"] = material.plain(init_parent.network.material.values._asdict())
    ctx = None
    reached = {}
    stage = "supplied_SIM_configuration"

    def observe(name, value):
        reached[name] = ions.freeze(value)
        if observer is not None:
            observer(name, ions.freeze(value))

    try:
        temporary = calcium.bind(
            dict(
                kind="cells.normal_ecm_calcium_join_inputs@1",
                case_id=raw["case_id"],
                case_role="transition setup context only",
                field=field,
                calcium=packet["calcium"],
            )
        )
        ctx = owners.make_context(
            temporary,
            ions.data(init_binding.inputs_raw["owners"]),
            [np.array(v, copy=True) for v in init_parent.network.material.values],
            phase_kind="INIT",
        )
        owners.restore(ctx, ions.data(init_parent.network.network_cache))
        for key, value in init_parent.stores.items():
            setattr(ctx.sim, key, catalog.clone(value))
        for attr, cache in (
            ("rate_CaATP", init_parent.rate_cache),
            ("rate_NaKATP", init_parent.nak_rate),
        ):
            if cache.present:
                setattr(ctx.sim, attr, cache.value.copy())
        calcium.native_policy(ctx, temporary)
        ctx.sim.T = float(init_parent.stores["T"])
        ctx.sim.P_cells = np.array(init_parent.stores["P_cells"], copy=True)
        ctx.phase.kind = "SIM"
        p, sim, cells = (ctx.p, ctx.sim, ctx.cells)
        p._run_sim = True
        p.dt = raw["time_profile"]["sim_dt_s"]
        p.sim_time_total = raw["time_profile"]["sim_total_s"]
        p.global_options = ions.data(packet["event_owner"]["global_options"])
        p.scheduled_options = ions.data(packet["event_owner"]["scheduled_options"])
        p.f_scan_properties = ions.data(cfg["frequency_sweep"])
        p.channel_noise_level = cfg["static_noise_level"]
        ep = field["definition"]["environment_geometry_definition"]["parameters"]
        p.NAv, p.er, p.eo = (
            ep["NAv_per_mol"],
            ep["relative_permittivity"],
            ep["vacuum_permittivity_F_m"],
        )
        p.cm = field["field_parameters"]["capacitance_F_m2"]
        p.Ca_dyn = False
        p.molecules_enabled = ctx.enabled["molecules"]
        p.grn_enabled = ctx.enabled["grn"]
        p.substances_affect_charge = field["network"]["cold_publish"]
        p.deformation = template["mechanics_definition"]["policy"]["deformation"]
        p.deform_osmo = template["mechanics_definition"]["policy"]["deform_osmo"]
        sim.D_free = np.asarray(init_parent.stores["D_free"]).copy()
        denv = cfg["environment_diffusion"]
        p.D_adh, p.D_tj = (denv["adherens_multiplier"], denv["tight_junction_multiplier"])
        cells.envInds_inClust = np.asarray(denv["environment_in_cluster_indices"], np.int64)
        sim.Dtj_rel = np.asarray(denv["tight_junction_relative"], np.float64)
        stage = "source_initDenv"
        source.initDenv(sim, cells, p)
        if cfg["cbnd"] is not None:
            for i, name in enumerate(ctx.ion_ids):
                sim.c_env_bound[i] = cfg["cbnd"][name]
        owner = profile_owner(cfg["tissue_profiles"])
        sim.dyna = ctx.phase.dyna = owner
        stage = "supplied_profile_outputs_and_literal_assignments"
        source.init_profiles(owner, ctx.phase)
        sim.D_env_base = sim.D_env.copy()
        observe(
            "pre_static",
            dict(
                available=available(ctx),
                numpy_rng=cfg["numpy_rng"],
                python_rng=cfg["python_rng"],
                profile_picker_outputs=cfg["tissue_profiles"],
                profile_picking_executed=False,
            ),
        )
        rng = numpy_restore(cfg["numpy_rng"])
        python_rng = init_setup.python_restore(cfg["python_rng"])
        stage = "SIM_static_setup"
        source.static_and_blocks(sim, cells, p, rng)
        observe(
            "post_static",
            dict(
                available=available(ctx),
                numpy_rng_after=numpy_manifest(rng),
                channel_noise_factor=sim.channel_noise_factor.copy(),
                rate_CaATP=init_parent.rate_cache,
                rate_NaKATP=init_parent.nak_rate,
            ),
        )
        stage = "retained_general_then_GRN_reinitialize"
        identity = reinitialize_owners(
            ctx, init_binding, init_parent, raw["_phase_input"]["owners"], observe
        )
        stage = "SIM_mechanics_entry"
        initial_mechanics = mechanical_entry(init_parent, template["mechanics_definition"])
        mechanical_binding = mechanics.bind(template["mechanics_definition"])
        mechanical_state = mechanics.state(mechanical_binding, initial_mechanics)
        sim.rho_pump = 1
        sim.rho_channel = 1
        stage = "SIM_event_finalization"
        source._finalize_events_global(owner, ctx.phase, shuffle=python_rng.shuffle)
        source._finalize_events_tissue(owner, ctx.phase)
        event_owner = finalized_owner(packet["event_owner"], owner, p)
        observe(
            "event_finalized",
            dict(
                owner=event_owner,
                python_rng_after=init_setup.python_manifest(python_rng),
                frequency_sweep_after=p.f_scan_properties,
                source_phase="SIM",
                legacy_run_sim=True,
                event_fire_calls=0,
            ),
        )
        stage = "source_screening_conductivity"
        source.screening_conductivity(sim, cells, p)
        observe(
            "screening_conductivity",
            dict(
                ko_env=sim.ko_env,
                ko_cell=sim.ko_cell,
                sigma=sim.sigma,
                sigma_cell=sim.sigma_cell.copy(),
                sigma_env=sim.sigma_env.copy(),
            ),
        )
        stage = "source_clear_storage"
        cells.ecm_verts_unique = np.asarray(
            template["mechanics_definition"]["geometry"]["layout"]["vertices_m"]
        ).copy()
        owners.reset_storage(ctx)
        observe(
            "storage_cleared",
            dict(
                available=available(ctx),
                native_storage_write_calls=0,
                retained_rate_CaATP_present=hasattr(sim, "rate_CaATP"),
                retained_rate_NaKATP_present=hasattr(sim, "rate_NaKATP"),
            ),
        )
        stage = "post_setup_component_declaration"
        field["initial"] = material.plain(catalog.material_values(sim))
        field["definition"]["ions"]["membrane_diffusion_m2_s"] = sim.Dm_cells.tolist()
        field["definition"]["ions"]["environment_diffusion_m2_s"] = sim.D_env.tolist()
        field["definition"]["ions"]["tight_junction_modulator"] = sim.TJ_modulator.tolist()
        field["definition"]["environment_geometry_definition"]["cache_initial_state"].update(
            cell_mol_m3=sim.cc_cells.tolist(),
            environment_mol_m3=sim.cc_env.tolist(),
            free_diffusion_m2_s=sim.D_free.tolist(),
        )
        field["network"]["initial_controls"] = {
            key: np.broadcast_to(getattr(sim, key), (sim.mdl,)).tolist()
            for key in ("gj_block", "NaKATP_block")
        }
        field["network"]["initial_ion_boundary"] = sim.c_env_bound.tolist()
        for row in field["steps"]:
            row["boundary_V"] = material.plain(sim.bound_V)
            row["material"].update(
                runtime_temperature_K=float(sim.T),
                boundary_mol_m3=sim.c_env_bound.tolist(),
                junction_block=np.broadcast_to(sim.gj_block, (sim.mdl,)).tolist(),
                channel_multiplier=np.broadcast_to(sim.rho_channel, (sim.mdl,)).tolist(),
            )
        field["bootstrap"]["boundary_V"] = material.plain(sim.bound_V)
        packet["entry_event_state"] = material.plain(events.event_snapshot(sim))
        event_owner["geometry_declaration_sha256"] = hashlib.sha256(
            json.dumps(
                field["definition"]["environment_geometry_definition"],
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()
        packet["event_owner"] = event_owner
        packet["prepared_rng"] = dict(
            kind="cells.supplied_post_event_finalization_numpy_state@1",
            manifest=numpy_manifest(rng),
            provenance="Actual supplied-process stream after native SIM static setup",
        )
        packet["noise_cache"] = dict(
            present=False,
            value=None,
            provenance="Actual INIT source never executes the SIM protein-noise producer",
        )
        template["mechanics_initial"] = material.plain(initial_mechanics)
        template["_phase_input"] = phase_input_after_setup(ctx, template, raw, initial_mechanics)
        observe(
            "entry_declaration",
            dict(
                template=template,
                available=available(ctx),
                mechanical_entry=mechanical_state,
                owner_identity=identity,
                native_SIM_inputs=conditional_sim_input(ctx, template, raw),
            ),
        )
        return (ctx, template, mechanical_state, ions.freeze(reached))
    except Exception as error:
        raise SetupRejected(
            error,
            dict(
                stage=stage,
                reached=reached,
                available=available(ctx),
                source_init_parent=init_parent,
                root_cause=dict(type=type(error).__name__, message=str(error)),
            ),
        ) from error


def legacy_setup_inputs(raw):
    result = ions.data(raw)
    current = ions.data(raw["sim_phase"])
    setup = current["setup"]
    event_owner = dict(
        global_options=setup["global_options"],
        scheduled_options=setup["scheduled_options"],
        handler_fields={},
        callbacks={},
        tissue_target_inds=setup["maps"]["tissue_target_inds"],
        cell_target_inds=setup["maps"]["cell_target_inds"],
        env_target_inds=setup["maps"]["env_target_inds"],
    )
    result["flags"] = current["flags"]
    result["time_profile"] = current["time_profile"]
    result["sim_composition_template"] = dict(
        event_inputs=dict(
            field=current["field"],
            calcium=current["calcium"],
            catalog=current["catalog"],
            event_owner=event_owner,
        ),
        mechanics_definition=current["mechanics_definition"],
        mechanics_initial=current["mechanics_initial"],
    )
    result["_phase_input"] = current
    return result


def available(ctx):
    return owners.available(ctx)


def encoded(value):
    if isinstance(value, (np.ndarray, np.generic)):
        a = np.asarray(value)
        return dict(__native_buffer__=a.tolist(), dtype=a.dtype.str, shape=list(a.shape))
    if isinstance(value, dict) or hasattr(value, "items"):
        return {k: encoded(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [encoded(v) for v in value]
    return value


def reinitialize_owners(ctx, init_binding, init_parent, new_raw, observe):
    actual = {}
    old_raw = ions.data(init_binding.inputs_raw["owners"])
    old_cache = ions.data(init_parent.network.network_cache)
    for role in owners.ROLES:
        obj = getattr(ctx.sim, role, None)
        actual[role] = (
            None
            if obj is None
            else dict(
                owner=obj,
                core=obj.core,
                molecules=dict(obj.core.molecules),
                channels=dict(obj.core.channels),
                transporters=dict(obj.core.transporters),
            )
        )
    dyna = ctx.phase.dyna
    for role in owners.ROLES:
        view = ctx.views[role]
        view.definition = ions.data(new_raw["handlers"][role]["network"])
        catalog.configure(view, ions.data(new_raw["handlers"][role]["catalog"]))
    ctx.phase.dyna = ctx.sim.dyna = dyna
    ctx.raw = ions.data(new_raw)
    ctx.p.network_config = ions.data(new_raw["configuration"]["general network"])
    ctx.p.grn = SimpleNamespace(conf=catalog.clone(ctx.views["grn"].definition["configuration"]))
    ctx.p.molecules_enabled = ctx.enabled["molecules"]
    ctx.p.grn_enabled = ctx.enabled["grn"]
    owners.phase(ctx, "SIM")

    def hook(role, stage, value):
        if role == "all":
            inputs = owners.conditional_input(ctx, "reinitialize")
            inputs["incoming_owners"] = encoded(old_cache)
            inputs["old_raw"] = old_raw
            inputs["mode"] = "reinitialize"
            inputs["source_cold_recapture"] = False
            observe("before_dual_reinitialize", inputs)
        else:
            observe("owner_" + role + "_" + stage, value)

    owners.initialize(ctx, hook)
    identity = {}
    for role in owners.ROLES:
        old = actual[role]
        obj = getattr(ctx.sim, role, None)
        if not ctx.enabled[role]:
            if old is not None or obj is not None:
                raise ValueError(
                    "Disabled latent owner is preserved by native source but outside this first lifecycle representation"
                )
            identity[role] = dict(enabled=False, owner_absent=True)
            continue
        identity[role] = dict(
            enabled=True,
            owner_retained=obj is old["owner"],
            core_retained=obj.core is old["core"],
            molecule_objects_retained={
                k: obj.core.molecules.get(k) is v for k, v in old["molecules"].items()
            },
            channel_objects_rebuilt={
                k: v is not old["channels"].get(k) for k, v in obj.core.channels.items()
            },
            transporter_objects_rebuilt={
                k: v is not old["transporters"].get(k) for k, v in obj.core.transporters.items()
            },
            transporter_fluxes_after={
                k: catalog.clone(v.flux) for k, v in obj.core.transporters.items()
            },
            read_substances_called=False,
            fresh_cold_owner_created=False,
        )
        cfg = ctx.views[role].definition["configuration"]
        for key in ("transporters", "channels", "modulators", "reactions"):
            configuration = (
                ctx.views[role].catalog["populations"] if key == "channels" else cfg.get(key)
            )
            if configuration is None and getattr(obj.core, key):
                raise ValueError(
                    "Native null configuration retains latent "
                    + role
                    + "/"
                    + key
                    + "; complete actual buffers are retained, not normalized"
                )
    observe(
        "dual_owners_reinitialized",
        dict(
            available=available(ctx),
            owner_identity=identity,
            carried_gate_voltage_V=ctx.sim.vm.copy(),
            source_cold_recapture=False,
        ),
    )
    return identity


def conditional_sim_input(ctx, template, raw):
    return dict(
        kind="cells.actual_dual_owner_SIM_phase_entry@1",
        owners=owners.conditional_input(ctx, "entry"),
        phase_input=ions.data(template["_phase_input"]),
        setup_fields=ions.data(template),
        source_phase="SIM",
        legacy_run_sim=True,
        source_cold_recapture=False,
        native_load_or_pickle=False,
    )


def phase_input_after_setup(ctx, template, raw, mechanical_initial):
    result = ions.data(raw["_phase_input"])
    field = ions.data(template["event_inputs"]["field"])
    result["field"] = field
    result["catalog"] = ions.data(template["event_inputs"]["catalog"])
    result["mechanics_initial"] = ions.data(mechanical_initial)
    result["owners"]["field"] = ions.data(field)
    result["owners"]["calcium"] = ions.data(result["calcium"])
    for role in owners.ROLES:
        definition = result["owners"]["handlers"][role]["network"]
        definition["initial_controls"] = ions.data(field["network"]["initial_controls"])
        definition["initial_ion_boundary"] = ions.data(field["network"]["initial_ion_boundary"])
    result["owners"]["handlers"]["grn"]["network"] = ions.data(field["network"])
    ctx.raw = ions.data(result["owners"])
    for role in owners.ROLES:
        ctx.views[role].definition = ions.data(ctx.raw["handlers"][role]["network"])
    return result
