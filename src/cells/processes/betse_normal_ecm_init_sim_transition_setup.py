"""Native reinitialization order on retained, explicitly supplied INIT owners.

Profile picker outputs and the mechanical DEC view are conditional supplied
seams. They are not native seed/load or physical geometry attestations. Both
process RNG streams are supplied explicitly; pickle does not own those streams.
"""

import hashlib
import json
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_ecm_grn_join as network
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_mechanics_join as mechanics
from cells.processes import betse_normal_ecm_calcium_join as calcium
from cells.processes import betse_normal_ecm_catalog_join_source as catalog
from cells.processes import betse_normal_ecm_event_join_source as events
from cells.processes import betse_normal_ecm_init_phase_setup as init_setup
from cells.processes import betse_normal_ecm_init_sim_transition_source as source
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
        return self.cells.copy(), self.membranes.copy()


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


def available(ctx):
    if ctx is None:
        return None
    result = dict(
        phase=ctx.phase.kind, legacy_run_sim=getattr(ctx.p, "_run_sim", None), capture_errors=[]
    )
    for name, producer in (
        ("material", lambda: catalog.material_values(ctx.sim)),
        ("catalog_cache", lambda: catalog.cache(ctx)),
    ):
        try:
            result[name] = producer()
        except Exception as error:
            result["capture_errors"].append(
                dict(section=name, type=type(error).__name__, message=str(error))
            )
    result["simulator_fields"] = {
        name: catalog.clone(value)
        for name, value in vars(ctx.sim).items()
        if isinstance(value, (np.ndarray, np.generic, float, int, bool, str)) or value is None
    }
    result["trace"] = catalog.clone(ctx.trace)
    return result


def conditional_reinitialize_input(ctx, old_catalog, old_cache):
    """Actual incoming owner/cache/parameter buffers, before reinitialize writes."""
    simple = (np.ndarray, np.generic, float, int, bool, str, list, tuple, dict)

    def encoded(value):
        if isinstance(value, (np.ndarray, np.generic)):
            value = np.asarray(value)
            return dict(
                __transition_ndarray__=value.tolist(),
                dtype=value.dtype.str,
                shape=list(value.shape),
            )
        if isinstance(value, dict) or hasattr(value, "items"):
            return {key: encoded(v) for key, v in value.items()}
        if isinstance(value, (tuple, list)):
            return [encoded(v) for v in value]
        return value

    parameters = {
        key: encoded(value)
        for key, value in vars(ctx.p).items()
        if isinstance(value, simple) or value is None
    }
    cells = {
        key: encoded(value)
        for key, value in vars(ctx.cells).items()
        if isinstance(value, simple) or value is None
    }
    sim = {
        key: encoded(value)
        for key, value in vars(ctx.sim).items()
        if isinstance(value, simple) or value is None
    }
    cache = catalog.cache(ctx)
    # New catalog configuration resets instrumentation before the source reader
    # runs; the incoming old owner still has the actual INIT gate metadata.
    cache["initial_channel_fields"] = catalog.clone(old_cache["initial_channel_fields"])
    cache["channel_calls"] = catalog.clone(old_cache["channel_calls"])
    return dict(
        kind="cells.actual_SIM_reinitialize_conditional_inputs@1",
        mode="reinitialize",
        simulator_fields=sim,
        cells_fields=cells,
        parameter_fields=parameters,
        definition=catalog.clone(ctx.definition),
        catalog=catalog.clone(ctx.catalog),
        old_catalog=catalog.clone(old_catalog),
        incoming_cache=encoded(cache),
        ion_ids=list(ctx.ion_ids),
        maps={
            key: encoded(getattr(ctx.phase.dyna, key))
            for key in ("tissue_target_inds", "cell_target_inds", "env_target_inds")
        },
        source_phase=ctx.phase.kind,
        legacy_run_sim=ctx.p._run_sim,
        numpy_random_state_consumed=False,
        source_cold_recapture=False,
    )


def conditional_sim_input(ctx, template, raw):
    """Archive the actual post-clear, pre-bootstrap entry, without cold recapture."""

    def encoded(value):
        if isinstance(value, (np.ndarray, np.generic)):
            array = np.asarray(value)
            return dict(
                __transition_ndarray__=array.tolist(),
                dtype=array.dtype.str,
                shape=list(array.shape),
            )
        if isinstance(value, dict) or hasattr(value, "items"):
            return {key: encoded(v) for key, v in value.items()}
        if isinstance(value, (tuple, list)):
            return [encoded(v) for v in value]
        return value

    simple = (np.ndarray, np.generic, float, int, bool, str, list, tuple, dict)
    return dict(
        kind="cells.actual_reinitialized_SIM_conditional_entry@1",
        composition=ions.data(template),
        simulator_fields={
            key: encoded(value)
            for key, value in vars(ctx.sim).items()
            if isinstance(value, simple) or value is None
        },
        entry_cache=encoded(catalog.cache(ctx)),
        alpha_NaK=raw["flags"]["alpha_NaK"],
        sim_total_s=raw["time_profile"]["sim_total_s"],
        independent_INIT_trajectory=False,
        source_cold_recapture=False,
        native_pickle_or_load_attested=False,
    )


def mechanical_entry(init_parent, definition):
    values = ions.data(init_parent.mechanics.cache)
    values = {key: np.array(value, copy=True) for key, value in values.items()}
    n = len(definition["geometry"]["cell_ids"])
    values["div_u_osmo"] = np.zeros(n)
    if definition["policy"]["deformation"]:
        values["d_cells_x"] = np.zeros(n)
        values["d_cells_y"] = np.zeros(n)
    # The source does not reset osmotic output/pressure gradients or disabled
    # flow caches here. Preserve them until their actual source writer runs.
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
        if key not in excluded and not key.startswith(("dyna_", "scalar_")) and not callable(value)
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
            provenance=(
                "Actual retained-owner SIM finalizer callback output, not evaluated at setup"
            ),
        )
    owner["callbacks"] = callbacks
    return owner


def prepare(init_binding, init_parent, raw, observer=None):
    """Execute real reinitialize/setup bodies; never call a fresh cold initializer."""
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
        ctx = network.make_context(
            temporary,
            [np.array(v, copy=True) for v in init_parent.network.material.values],
            ions.data(temporary.inputs["network"]),
        )
        # Restore under the actual old catalog before installing new channels.
        catalog.configure(ctx, ions.data(init_binding.catalog))
        catalog.restore(ctx, init_parent.network.network_cache)
        retained_owner, retained_core = ctx.sim.grn, ctx.sim.grn.core
        old_molecules = dict(retained_core.molecules)
        old_channels = dict(retained_core.channels)
        for key, value in init_parent.stores.items():
            setattr(ctx.sim, key, catalog.clone(value))
        for attr, cache in (
            ("rate_CaATP", init_parent.rate_cache),
            ("rate_NaKATP", init_parent.nak_rate),
        ):
            if cache.present:
                setattr(ctx.sim, attr, cache.value.copy())
        catalog.configure(ctx, packet["catalog"])
        calcium.native_policy(ctx, temporary)
        # The native phase does not reset these retained attributes when it
        # changes the clock and legacy flag.
        ctx.sim.T = float(init_parent.stores["T"])
        ctx.sim.P_cells = np.array(init_parent.stores["P_cells"], copy=True)
        ctx.phase.kind = "SIM"
        p, sim, cells = ctx.p, ctx.sim, ctx.cells
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
        p.molecules_enabled = False
        p.grn_enabled = True
        p.substances_affect_charge = field["network"]["cold_publish"]
        p.deformation = template["mechanics_definition"]["policy"]["deformation"]
        p.deform_osmo = template["mechanics_definition"]["policy"]["deform_osmo"]
        sim.D_free = np.asarray(init_parent.stores["D_free"]).copy()
        denv = cfg["environment_diffusion"]
        p.D_adh, p.D_tj = denv["adherens_multiplier"], denv["tight_junction_multiplier"]
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
        stage = "retained_GRN_reinitialize"
        observe(
            "before_GRN_reinitialize",
            conditional_reinitialize_input(
                ctx, init_binding.catalog, init_parent.network.network_cache
            ),
        )
        source.reinitialize(sim.grn, ctx.phase)
        ctx.initial_channel_fields = catalog.channel_fields(sim.grn.core)
        ctx.channel_calls = {name: 0 for name in sim.grn.core.channels}
        after_cache = catalog.cache(ctx)
        identity = dict(
            owner_retained=sim.grn is retained_owner,
            core_retained=sim.grn.core is retained_core,
            molecule_objects_retained={
                name: sim.grn.core.molecules.get(name) is obj for name, obj in old_molecules.items()
            },
            channel_objects_reconstructed={
                name: obj is not old_channels.get(name)
                for name, obj in sim.grn.core.channels.items()
            },
            read_substances_called=False,
            fresh_cold_owner_created=False,
        )
        observe(
            "GRN_reinitialized",
            dict(
                available=available(ctx),
                owner_identity=identity,
                carried_gate_voltage_V=sim.vm.copy(),
            ),
        )
        if packet["catalog"]["populations"] is None and sim.grn.core.channels:
            raise ValueError(
                "Native None-channel transition retained latent gates; "
                "this owner shape remains unqualified"
            )
        catalog.validate_cached_channels(ctx, after_cache)
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
        source.clear_storage(sim, cells, p)
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
        # The component binder still declares vector control axes; the real
        # scalar/vector source stores are carried separately in entry state.
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
        return ctx, template, mechanical_state, ions.freeze(reached)
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
