"""Ordinary ECM material/CaATP with distinct native general and GRN owners.

Supplied physical/setup fields are explicit. General and GRN source flags are
independent. Native publication overwrites, role caches, boundary/control carry
and full current/field feedback remain owned. This feature is held and unrun.
"""

from dataclasses import dataclass, replace

import numpy as np

from cells.processes import betse_ecm_grn_join as network
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_normal_ecm_calcium_join as calcium
from cells.processes import betse_normal_ecm_catalog_join_source as qualified
from cells.processes import betse_normal_ecm_field_join as full
from cells.processes import betse_normal_ecm_molecule_dispatch_runtime as runtime
from cells.processes import betse_normal_ion_join as ions

LAW_ID = "betse_supplied_FULL_ECM_general_then_GRN_v1_5_0@1"
INPUT_KIND = "cells.normal_ecm_general_molecule_dispatch_inputs@1"
FLAGS = dict(
    solver="FULL",
    is_ecm=True,
    Ca_dyn=False,
    fluid_flow=False,
    td_deform=False,
    sim_eosmosis=False,
    dynamic_noise=0,
    deform_osmo=False,
    deformation=False,
)


@dataclass(frozen=True)
class Binding:
    component: object
    inputs: object
    identity: str


@dataclass(frozen=True)
class State:
    binding_identity: str
    material: object
    field: object
    owners: object
    controls: object
    rate_cache: object
    clock: object
    identity: str

    @property
    def cursor(self):
        return self.material.step_index


class NativeConfigurationObstructed(ValueError):
    pass


class DispatchRejected(RuntimeError):
    def __init__(self, error, partial):
        super().__init__(str(error))
        self.partial = ions.freeze(partial)


def binding_record(value):
    return LAW_ID, value.component.identity, value.inputs


def bind(inputs):
    raw = ions.data(inputs)
    if (
        set(raw)
        != {
            "kind",
            "case_id",
            "provenance",
            "flags",
            "configuration",
            "field",
            "calcium",
            "handlers",
            "shared_initial",
        }
        or raw["kind"] != INPUT_KIND
    ):
        raise ValueError("Require the complete separately supplied dual-owner composition")
    for key in ("case_id", "provenance"):
        if not isinstance(raw[key], str) or not raw[key].strip():
            raise ValueError("Require explicit composition provenance")
    if set(raw["flags"]) != set(FLAGS) or any(
        type(raw["flags"][k]) is not type(v) or raw["flags"][k] != v for k, v in FLAGS.items()
    ):
        raise ValueError("Unsupported source branch: no forced ER, flow, noise, mechanics or FAST")
    conf = raw["configuration"]
    if set(conf) != {"general network", "gene regulatory network settings"}:
        raise ValueError("Require both native configuration sections")
    general = conf["general network"]
    if general is None:
        raise NativeConfigurationObstructed(
            "Parameters.load 777-798 leaves molecules_enabled unwritten when general "
            "network is absent; no false default inferred"
        )
    if type(general.get("implement network")) is not bool:
        raise ValueError("Native implement network must explicitly select general-handler dispatch")
    if (
        set(conf["gene regulatory network settings"]) != {"gene regulatory network simulated"}
        or type(conf["gene regulatory network settings"]["gene regulatory network simulated"])
        is not bool
    ):
        raise ValueError("Require explicit independent native GRN enabled flag")
    component = calcium.bind(
        dict(
            kind="cells.normal_ecm_calcium_join_inputs@1",
            case_id=raw["case_id"],
            case_role=raw["provenance"],
            field=raw["field"],
            calcium=raw["calcium"],
        )
    )
    if set(raw["handlers"]) != set(runtime.ROLES):
        raise ValueError("Require separate general and GRN cache/configuration owners")
    names = component.material_binding.geometry_binding.current_binding.ion_ids
    cg = component.material_binding.geometry_binding.current_binding
    e = len(component.inputs["initial"]["environment_mol_m3"][0])
    for role in runtime.ROLES:
        item = raw["handlers"][role]
        if set(item) != {"network", "catalog"}:
            raise ValueError("Complete handler network/catalog declaration required")
        if item["network"]["owner"] != role:
            raise ValueError("Handler declaration belongs to the other owner namespace")
        # Reuse the qualified core predicates while preserving actual owner
        # labels in runtime data and cache identities.
        qualified.base.validate(dict(item["network"], owner="grn"), component.material_binding)
        qualified.validate_catalog(item["catalog"], list(names), len(cg.membrane_ids))
        if item["network"]["configuration"].get("transporters") is not None:
            raise ValueError(
                "Additional transporter owners require a separate complete native binding"
            )
        for key in (
            "grid_index_groups",
            "initial_controls",
            "initial_ion_boundary",
            "cold_publish",
        ):
            if not qualified.equal_tree(item["network"][key], raw["field"]["network"][key]):
                raise ValueError(
                    "Both handlers must share actual geometry, controls, boundaries "
                    "and publication flag"
                )
    if not qualified.equal_tree(raw["handlers"]["grn"]["network"], raw["field"]["network"]):
        raise ValueError(
            "The common field-format carrier must match the declared GRN definition; "
            "no GRN constructor is inferred"
        )
    a, b = (raw["handlers"][role]["catalog"]["tissue_profiles"] for role in runtime.ROLES)
    if not qualified.equal_tree(a, b):
        raise ValueError("Both handlers share the single native tissue/event target owner")
    expected = dict(raw["handlers"]["molecules"]["network"]["configuration"])
    expected["channels"] = raw["handlers"]["molecules"]["catalog"]["populations"]
    expected["implement network"] = general["implement network"]
    if not qualified.equal_tree(general, expected):
        raise ValueError(
            "Actual native general network configuration differs from declared numeric owner"
        )
    if set(raw["shared_initial"]) != set(runtime.PUBLICATIONS):
        raise ValueError(
            "Supply every original shared charge/current array, including disabled-handler carry"
        )
    dimensions = dict(
        extra_rho_cells=len(cg.cell_ids),
        extra_rho_env=e,
        extra_J_mem=len(cg.membrane_ids),
        extra_Jenv_x=e,
        extra_Jenv_y=e,
    )
    for key, size in dimensions.items():
        value = np.asarray(raw["shared_initial"][key])
        if value.shape != (size,) or value.dtype.kind not in "iuf" or not np.isfinite(value).all():
            raise ValueError("Invalid complete shared publication " + key)
    for row in component.inputs["steps"]:
        if row["scheduled_controls"] is not None:
            raise ValueError("Scheduled events require their own owned source handler")
    value = Binding(component, ions.freeze(raw), "")
    return replace(value, identity=ions.digest(binding_record(value)))


def state_record(value):
    return (
        value.binding_identity,
        value.material,
        value.field,
        value.owners,
        value.controls,
        value.rate_cache,
        value.clock,
    )


def state(binding, parent, field, owners, controls, rate, clock):
    value = State(
        binding.identity, parent, field, ions.freeze(owners), ions.freeze(controls), rate, clock, ""
    )
    return replace(value, identity=ions.digest(state_record(value)))


def verify(binding, parent):
    if type(binding) is not Binding or binding.identity != ions.digest(binding_record(binding)):
        raise ValueError("Changed dual-owner composition declaration")
    if (
        type(parent) is not State
        or parent.binding_identity != binding.identity
        or parent.identity != ions.digest(state_record(parent))
    ):
        raise ValueError("Changed complete primary/field/dual-owner state")
    checked = material.state(
        binding.component.material_binding,
        parent.material.values._asdict(),
        step_index=parent.cursor,
    )
    if (
        checked.identity != parent.material.identity
        or parent.clock.call_index != parent.cursor
        or not 0 <= parent.cursor <= 3
    ):
        raise ValueError("Original bounded source material and clock epochs differ")
    dt = binding.component.inputs["bootstrap"]["dt_s"]
    if (
        type(parent.clock) is not calcium.Clock
        or not isinstance(parent.clock.source_times_s, np.ndarray)
        or parent.clock.source_times_s.dtype != np.float64
        or parent.clock.source_times_s.flags.writeable
        or not np.array_equal(parent.clock.source_times_s, np.linspace(0, 3 * dt, 3))
        or parent.clock.material_dt_sum_s != parent.cursor * dt
    ):
        raise ValueError("Changed original source labels or accumulated material time")
    if (
        type(parent.field) is not full.FieldStage
        or parent.field.binding_identity != binding.component.identity
        or parent.field.identity != ions.digest(full.field_record(parent.field))
    ):
        raise ValueError("Require the actual complete preceding field state")
    expected = bool(binding.component.calcium["alpha_Ca"] > 0 and parent.cursor > 0)
    rate = parent.rate_cache
    if (
        type(rate) is not calcium.RateCache
        or rate.present is not expected
        or (
            rate.value is not None
            if not expected
            else not isinstance(rate.value, np.ndarray)
            or rate.value.shape
            != (
                len(
                    binding.component.material_binding.geometry_binding.current_binding.membrane_ids
                ),
            )
            or rate.value.dtype != np.float64
            or rate.value.flags.writeable
            or not np.isfinite(rate.value).all()
        )
    ):
        raise ValueError("CaATP cache must match its actual source writer epoch")
    flags = dict(
        molecules=binding.inputs["configuration"]["general network"]["implement network"],
        grn=binding.inputs["configuration"]["gene regulatory network settings"][
            "gene regulatory network simulated"
        ],
    )
    if not qualified.equal_tree(parent.owners["enabled"], flags):
        raise ValueError("Changed active source flags")
    for role in runtime.ROLES:
        saved = parent.owners["handlers"][role]
        if (saved is not None) is not flags[role]:
            raise ValueError("Enabled owner must be complete; disabled owner must be absent")
        if saved is not None and saved["role"] != role:
            raise ValueError("General and GRN owners cannot be interchanged")
    for key in runtime.PUBLICATIONS:
        if not qualified.equal_tree(
            parent.owners["wire"]["simulator_fields"][key], parent.owners["shared"][key]
        ):
            raise ValueError("Field projection and actual shared publication epoch differ")
    pubs = parent.owners["wire"]["simulator_fields"]
    for actual, wanted in (
        (parent.field.before["current"]["extra_charge_C_m3"], pubs["extra_rho_cells"]),
        (parent.field.before["current"]["extra_current_A_m2"], pubs["extra_J_mem"]),
        (
            parent.field.before["environment"]["extra_environment_charge_C_m3"],
            pubs["extra_rho_env"],
        ),
        (
            parent.field.before["environment"]["extra_environment_current_xy"],
            np.column_stack((pubs["extra_Jenv_x"], pubs["extra_Jenv_y"])),
        ),
    ):
        if not qualified.equal_tree(actual, wanted):
            raise ValueError("Shared network publications differ from their actual field epoch")


def initialize(binding, *, observer=None, before_field=None):
    ctx = None
    stage = "entry"
    try:
        if type(binding) is not Binding or binding.identity != ions.digest(binding_record(binding)):
            raise ValueError("Changed supplied dual-owner binding")
        component = binding.component
        original = material.state(
            component.material_binding, ions.data(component.inputs["initial"])
        )
        working = material.Values(*(np.array(v, copy=True) for v in original.values))
        ctx = runtime.make_context(component, ions.data(binding.inputs), working)
        stage = "native_handler_setup"
        owners = runtime.initialize(ctx, observer)
        initial = material.state(component.material_binding, qualified.material_values(ctx.sim))
        controls = {
            key: qualified.clone(getattr(ctx.sim, key)) for key in ("gj_block", "NaKATP_block")
        }
        net = network._state(component, initial, owners, controls)
        stage = "bootstrap"
        dt = component.inputs["bootstrap"]["dt_s"]
        prepared, field = full.reconstruct(
            component,
            net,
            dt,
            ions.data(component.inputs["bootstrap"]["boundary_V"]),
            "bootstrap",
            before_field,
        )
        result = state(
            binding,
            prepared.material,
            field,
            owners,
            controls,
            calcium.RateCache(False, None),
            calcium.Clock(ions.freeze(np.linspace(0, 3 * dt, 3)), 0, 0.0),
        )
        verify(binding, result)
        return result
    except Exception as error:
        raise DispatchRejected(
            error,
            dict(
                stage=stage,
                available=runtime.available(ctx),
                inner_partial=getattr(error, "partial", None),
                root_cause=dict(type=type(error).__name__, message=str(error)),
                automatic_retry=False,
            ),
        ) from error


def advance(
    binding,
    parent,
    *,
    before_material=None,
    before_calcium=None,
    handler_observer=None,
    before_commit=None,
    before_field=None,
):
    verify(binding, parent)
    ctx = None
    holder = {}
    stage = "material_input"
    component = binding.component
    index = parent.cursor
    if index >= 3:
        raise ValueError("Original three-call material domain exhausted")
    row = ions.data(component.inputs["steps"][index])
    packet = dict(
        row["material"],
        junction_block=ions.data(parent.controls["gj_block"]),
        electric_x_source=parent.field.environment.values.electric_x_source,
        electric_y_source=parent.field.environment.values.electric_y_source,
    )
    forcing = material.drive(component.material_binding, packet)
    incoming = dict(
        mode="material",
        definition=ions.data(component.inputs["definition"]),
        initial=ions.data(parent.material.values._asdict()),
        steps=[qualified.clone(packet)],
        calcium=ions.data(component.calcium),
        rate_cache_before=parent.rate_cache,
        clock=parent.clock,
        dual_owner_cache=parent.owners,
    )
    try:
        if before_material is not None:
            before_material(ions.freeze(incoming))

        def on_calcium(arrays):
            holder["rate"], holder["calcium"] = calcium.calcium(
                component, arrays, forcing, parent.rate_cache, parent.clock, before_calcium
            )

        def on_network(arrays):
            nonlocal ctx, stage
            stage = "general_then_GRN"
            ctx = runtime.make_context(component, ions.data(binding.inputs), arrays, forcing)
            runtime.restore(ctx, ions.data(parent.owners))
            # Actual material/forcing arrays own this source epoch; restoring
            # network caches must not restore old material or forcing fields.
            ctx.sim.gj_block = qualified.clone(parent.controls["gj_block"])
            ctx.sim.NaKATP_block = qualified.clone(parent.controls["NaKATP_block"])
            ctx.sim.rho_channel = np.array(forcing.channel_multiplier, copy=True)
            ctx.sim.c_env_bound = np.array(forcing.boundary_mol_m3, copy=True)
            if holder["rate"].present:
                ctx.sim.rate_CaATP = holder["rate"].value.copy()
            holder["dispatch"] = runtime.dispatch(
                ctx,
                ions.data(component.inputs["definition"]),
                row["publication"],
                float(parent.clock.source_times_s[index]),
                handler_observer,
            )
            holder["before_commit"] = ions.freeze(
                dict(
                    mode="commit",
                    definition=ions.data(component.inputs["definition"]),
                    values_before=qualified.material_values(ctx.sim),
                    initial=ions.data(parent.material.values._asdict()),
                    steps=[qualified.clone(packet)],
                    material_inputs=incoming,
                )
            )
            if before_commit is not None:
                before_commit(holder["before_commit"])

        def failed(local):
            holder["material_partial"] = dict(
                frames=tuple(local.get("frames", ())),
                environment_records=tuple(local.get("environment_records", ())),
            )

        trial = calcium._material_step(
            component.material_binding,
            parent.material,
            forcing,
            on_network=on_network,
            on_failure=failed,
            on_calcium=on_calcium,
        )
        holder["trial"] = trial
        owners = runtime.cache(ctx)
        controls = {
            key: qualified.clone(getattr(ctx.sim, key)) for key in ("gj_block", "NaKATP_block")
        }
        net = network._state(component, trial.candidate, owners, controls)
        stage = "field"
        prepared, field = full.reconstruct(
            component, net, forcing.dt_s, row["boundary_V"], "field", before_field
        )
        result = state(
            binding,
            prepared.material,
            field,
            owners,
            controls,
            holder["rate"],
            calcium.Clock(
                parent.clock.source_times_s,
                index + 1,
                parent.clock.material_dt_sum_s + forcing.dt_s,
            ),
        )
        verify(binding, result)
        return result, ions.freeze(holder)
    except Exception as error:
        raise DispatchRejected(
            error,
            dict(
                stage=stage,
                parent=parent,
                available=runtime.available(ctx),
                holder=holder,
                inner_partial=getattr(error, "partial", None),
                root_cause=dict(type=type(error).__name__, message=str(error)),
                automatic_retry=False,
            ),
        ) from error
