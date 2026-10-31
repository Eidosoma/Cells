"""Two distinct native network owners sharing the actual ordinary ECM buffers."""

from types import SimpleNamespace

import numpy as np

from cells.processes import betse_ecm_grn_join as network
from cells.processes import betse_normal_ecm_calcium_join as calcium
from cells.processes import betse_normal_ecm_catalog_join_source as qualified
from cells.processes import betse_normal_ecm_molecule_dispatch_source as source
from cells.processes import betse_normal_ion_join as ions

ROLES = ("molecules", "grn")
PUBLICATIONS = ("extra_rho_cells", "extra_rho_env", "extra_J_mem", "extra_Jenv_x", "extra_Jenv_y")
SHARED = (
    *PUBLICATIONS,
    "c_env_bound",
    "gj_block",
    "NaKATP_block",
    "rho_channel",
    "D_env_weight",
    "D_env_weight_base",
    "TJ_targets",
)


def owner_identity(view, role):
    return ions.digest((role, view.definition, view.catalog))


def owner_cache(ctx, role):
    view = ctx.views[role]
    owner = getattr(ctx.sim, role, None)
    if owner is None or not hasattr(owner, "core"):
        return None
    cached = source.cache_general(view) if role == "molecules" else qualified.cache(view)
    return dict(role=role, configuration_identity=owner_identity(view, role), cache=cached)


def cache(ctx):
    shared = {key: qualified.clone(getattr(ctx.sim, key)) for key in SHARED}
    return dict(
        kind="cells.normal_ECM_two_native_network_owners@1",
        enabled=qualified.clone(ctx.enabled),
        handlers={role: owner_cache(ctx, role) for role in ROLES},
        shared=shared,
        wire=dict(simulator_fields={key: qualified.clone(shared[key]) for key in PUBLICATIONS}),
        publication_owner=ctx.publication_owner,
    )


def available(ctx):
    if ctx is None:
        return None
    result = dict(capture_errors=[], source_order=qualified.clone(ctx.order))
    for name, reader in (
        ("material", lambda: qualified.material_values(ctx.sim)),
        ("owners", lambda: cache(ctx)),
        ("traces", lambda: {role: qualified.clone(view.trace) for role, view in ctx.views.items()}),
    ):
        try:
            result[name] = reader()
        except Exception as error:
            result["capture_errors"].append(
                dict(section=name, type=type(error).__name__, message=str(error))
            )
    result["simulator_arrays"] = {
        key: np.array(value, copy=True)
        for key, value in vars(ctx.sim).items()
        if isinstance(value, (np.ndarray, np.generic))
    }
    return result


def make_context(component, raw, values, forcing=None):
    ctx = network.make_context(component, values, ions.data(component.inputs["network"]), forcing)
    ctx.enabled = dict(
        molecules=raw["configuration"]["general network"]["implement network"],
        grn=raw["configuration"]["gene regulatory network settings"][
            "gene regulatory network simulated"
        ],
    )
    ctx.order = []
    ctx.views = {}
    ctx.raw = raw
    ctx.publication_owner = "supplied_initial"
    # The old geometry constructor prepares no handler. Actual source flags and
    # owner slots are selected before any native handler constructor or dispatch.
    ctx.sim.molecules = ctx.sim.grn = None
    for role in ROLES:
        definition = ions.data(raw["handlers"][role]["network"])
        view = SimpleNamespace(**vars(ctx))
        view.definition = definition
        view.trace = qualified.new_trace()
        qualified.configure(view, ions.data(raw["handlers"][role]["catalog"]))
        ctx.views[role] = view
    ctx.p.network_config = ions.data(raw["configuration"]["general network"])
    ctx.p.grn = SimpleNamespace(conf=qualified.clone(ctx.views["grn"].definition["configuration"]))
    ctx.p.grn_enabled = ctx.enabled["grn"]
    ctx.p.molecules_enabled = ctx.enabled["molecules"]
    ctx.p._run_sim = True
    ctx.phase.kind = "SIM"
    ctx.p.init_pickle_dirname = "supplied_native_persistence_disabled"
    ctx.p.dt = component.inputs["bootstrap"]["dt_s"]
    calcium.native_policy(ctx, component)
    ctx.p.dynamic_noise = 0
    ctx.p.deform_osmo = ctx.p.deformation = ctx.p.fluid_flow = ctx.p.sim_eosmosis = False
    for key, value in raw["shared_initial"].items():
        setattr(ctx.sim, key, np.asarray(value, np.float64).copy())
    return ctx


def restore(ctx, saved):
    if saved["kind"] != "cells.normal_ECM_two_native_network_owners@1" or not qualified.equal_tree(
        saved["enabled"], ctx.enabled
    ):
        raise ValueError("Changed two-handler source flags or complete cache kind")
    for role in ROLES:
        record = saved["handlers"][role]
        if not ctx.enabled[role]:
            if record is not None:
                raise ValueError("Latent disabled owners require a separate entry contract")
            continue
        if (
            record is None
            or record["role"] != role
            or record["configuration_identity"] != owner_identity(ctx.views[role], role)
        ):
            raise ValueError("Foreign general/GRN role or configuration cache")
        if role == "molecules":
            source.restore_general(ctx.views[role], record["cache"])
        else:
            qualified.restore(ctx.views[role], record["cache"])
    # Per-owner snapshots repeat shared fields. The independently retained
    # shared epoch is authoritative after both dynamic owner maps are restored.
    for key, value in saved["shared"].items():
        setattr(ctx.sim, key, qualified.clone(value))
    ctx.publication_owner = saved["publication_owner"]
    return ctx


def initialize(ctx, observer=None):
    ctx.p.substances_affect_charge = ctx.views["grn"].definition["cold_publish"]
    if observer is not None:
        observer("all", "before_initialize", ions.freeze(conditional_input(ctx, "initialize")))

    def hook(role, stage, sim, phase):
        view = ctx.views[role]
        ctx.order.append(dict(role=role, stage=stage))
        if stage == "before_setup":
            if role == "molecules":
                source.install_channel_observer_general(view)
            else:
                qualified.install_channel_observer(view)
        else:
            view.net = getattr(sim, role).core
            view.initial_channel_fields = qualified.channel_fields(view.net)
            if ctx.p.substances_affect_charge:
                ctx.publication_owner = role + "/cold_balance"
        if observer is not None:
            observer(role, stage, ions.freeze(available(ctx)))

    source.initialize_both(ctx.sim, 0.0, ctx.phase, ctx.cells, ctx.p, hook=hook)
    return cache(ctx)


def dispatch(ctx, definition, publication, label, observer=None):
    ctx.p.substances_affect_charge = publication
    ctx.phase.kind = "SIM"
    if observer is not None:
        observer(
            "all",
            "before_dispatch",
            ions.freeze(conditional_input(ctx, "dispatch", definition, label)),
        )

    def hook(role, stage, sim, phase):
        view = ctx.views[role]
        ctx.order.append(dict(role=role, stage=stage))
        if stage == "before_dispatch":
            view.net = getattr(sim, role).core
            view.trace = qualified.new_trace()
            view.trace.update(channel_events=[], channel_initializations=[])

            def before_network(value):
                if observer is not None:
                    observer(role, "network", ions.freeze(value))

            def before_channels(value):
                if observer is not None:
                    observer(role, "channels", ions.freeze(value))

            if role == "molecules":
                source.install_channel_observer_general(view)
                source.attach_general(view, definition, before_network, before_channels)
            else:
                qualified.install_channel_observer(view)
                qualified.attach(view, definition, before_network, before_channels)
        else:
            view.net._observe_dispatch(stage, sim, phase)
            if stage == "run_loop":
                if publication:
                    ctx.publication_owner = role
                view.trace.update(
                    source_completed=True,
                    cache_after=owner_cache(ctx, role)["cache"],
                    values_after=qualified.material_values(sim),
                    controls_after={
                        key: qualified.clone(getattr(sim, key))
                        for key in ("gj_block", "NaKATP_block")
                    },
                    owner_after=source.owner_evidence_general(view)
                    if role == "molecules"
                    else qualified.owner_evidence(view),
                    completed_transports=sum(
                        row["stage"] == "transport_after" for row in view.trace["molecule_frames"]
                    ),
                )
                if observer is not None:
                    observer(role, "returned", ions.freeze(view.trace))

    source.dispatch_both(ctx.sim, label, ctx.phase, ctx.cells, ctx.p, hook=hook)
    return dict(
        order=qualified.clone(ctx.order),
        handlers={
            role: qualified.clone(ctx.views[role].trace) if ctx.enabled[role] else None
            for role in ROLES
        },
        shared_after={key: qualified.clone(getattr(ctx.sim, key)) for key in SHARED},
        publication_owner=ctx.publication_owner,
    )


def conditional_input(ctx, mode, definition=None, label=0.0):
    """Complete actual incoming owner/field buffers, never outgoing predictions."""

    def encoded(value):
        if isinstance(value, (np.ndarray, np.generic)):
            array = np.asarray(value)
            return dict(
                __native_buffer__=array.tolist(), dtype=array.dtype.str, shape=list(array.shape)
            )
        if isinstance(value, dict) or hasattr(value, "items"):
            return {key: encoded(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [encoded(item) for item in value]
        return value

    def fields(obj):
        simple = (np.ndarray, np.generic, float, int, bool, str, list, tuple, dict)
        return {
            key: encoded(value)
            for key, value in vars(obj).items()
            if isinstance(value, simple) or value is None
        }

    return dict(
        kind="cells.actual_ECM_general_GRN_conditional_inputs@1",
        mode=mode,
        raw=ions.data(ctx.raw),
        ion_ids=list(ctx.ion_ids),
        simulator_fields=fields(ctx.sim),
        cell_fields=fields(ctx.cells),
        parameter_fields=fields(ctx.p),
        incoming_owners=None if mode == "initialize" else encoded(cache(ctx)),
        publication=ctx.p.substances_affect_charge,
        source_time_s=label,
        material_definition=qualified.clone(definition),
        independently_carried_trajectory=False,
        native_whole_initializer=False,
    )
