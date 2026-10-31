"""Ordinary ECM/field plus steady mechanics at the reached pre-commit seam.

The previous reconstructed field and current post-GRN concentrations are
different source epochs. Mechanics runs between dispatch and deferred commit.
Hydrostatic pressure and the complete matching DEC layout are declared inputs.
No physical geometry, enabled flow, dynamic deformation or sampling is added.
"""

from dataclasses import dataclass

import numpy as np

from cells.processes import betse_ecm_grn_source as source
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_mechanics_join as mechanics
from cells.processes import betse_normal_ecm_field_join as field
from cells.processes import betse_normal_ion_join as ions

LAW_ID = "betse_normal_ecm_field_steady_mechanics_v1_5_0@1"
INPUT_KIND = "cells.normal_ecm_mechanics_join_inputs@1"


@dataclass(frozen=True)
class Binding:
    field: field.Binding
    mechanics: mechanics.Binding
    inputs: object
    identity: str


@dataclass(frozen=True)
class State:
    binding_identity: str
    field: field.State
    mechanics: mechanics.State
    identity: str


class CompositionRejected(RuntimeError):
    def __init__(self, reason, partial):
        super().__init__(str(reason))
        self.partial = ions.freeze(partial)


def state(binding, fields, mechanical):
    return State(
        binding.identity, fields, mechanical, ions.digest((binding.identity, fields, mechanical))
    )


def bind(inputs):
    raw = ions.data(inputs)
    if (
        set(raw)
        != {
            "kind",
            "case_id",
            "field_inputs",
            "mechanics_definition",
            "mechanics_initial",
            "pressure_policy",
            "pressure_drives",
            "clocks_s",
        }
        or raw["kind"] != INPUT_KIND
    ):
        raise ValueError("Require the complete shared field/mechanics declaration")
    fb = field.bind(raw["field_inputs"])
    mb = mechanics.bind(raw["mechanics_definition"])
    definition = mb.definition
    policy = definition["policy"]
    if policy["display_regime"] != "none":
        raise ValueError("Display needs>=25 cells; the frozen native field domain permits<=16")
    if not policy["is_ecm"] or policy["molecules_enabled"] or not policy["grn_enabled"]:
        raise ValueError("Preserve actual ECM GRN ownership; separate molecule handler is absent")
    cg = fb.material_binding.geometry_binding.definition["current_definition"]["geometry"]
    geometry = fb.material_binding.geometry_binding.definition["geometry"]
    mg = definition["geometry"]
    layout = mg["layout"]
    n, m = len(cg["cell_ids"]), len(cg["membrane_ids"])
    if not 1 <= n <= 16 or not 1 <= m <= 128:
        raise ValueError("Keep the frozen native ECM domain without widening")
    if mg["cell_ids"] != cg["cell_ids"] or layout["membrane_ids"] != cg["membrane_ids"]:
        raise ValueError("Mechanics must use the actual shared cell/membrane owner order")
    expected = dict(
        centers_m=geometry["cell_centres_m"],
        cell_volume_m3=geometry["cell_volume_m3"],
        membrane_area_m2=cg["membrane_area_m2"],
        cell_area_m2=cg["cell_area_m2"],
    )
    for key, value in expected.items():
        np.testing.assert_array_equal(np.asarray(layout[key]), np.asarray(value), err_msg=key)
    owner = np.asarray(cg["owner"], dtype=int)
    sm = np.eye(n)[owner].T
    np.testing.assert_array_equal(layout["sum_membranes"], sm)
    np.testing.assert_array_equal(np.asarray(layout["neighbors"])[:, 0], owner)
    g = fb.material_binding.geometry_binding.geometry
    if mg["environment_ids"] != ["native-grid/" + str(k) for k in range(len(g.grid_points_m))]:
        raise ValueError("Declare the native C-order environment owner axis")
    np.testing.assert_array_equal(mg["cell_to_environment"], g.cell_to_grid)
    np.testing.assert_array_equal(mg["membrane_to_environment"], g.membrane_to_grid)
    p = definition["parameters"]
    if p["gas_constant_J_mol_K"] != fb.material_binding.kernel.R_J_mol_K or (
        p["membrane_thickness_m"] != fb.material_binding.kernel.membrane_thickness_m
    ):
        raise ValueError("Use the actual shared pressure constants and membrane thickness")
    if len(raw["pressure_drives"]) != 3 or len(raw["clocks_s"]) != 3:
        raise ValueError("Declare all three source-clock/pressure prerequisites")
    if raw["pressure_policy"] not in (
        "native_zero_baseline_no_pressure_events",
        "supplied_post_event_pressure",
    ):
        raise ValueError("No pressure scheduler or inferred pressure field is implemented")
    for index, packet in enumerate(ions.data(fb.inputs["steps"])):
        if packet["material"]["dt_s"] != p["dt_s"]:
            raise ValueError("Bind one phase dt for material and osmotic mechanics")
        for drive_name, cache_name in (
            ("velocity_x_m_s", "u_env_x"),
            ("velocity_y_m_s", "u_env_y"),
        ):
            value = np.asarray(packet["material"][drive_name])
            if np.any(value != 0) or not np.array_equal(
                value, np.asarray(raw["mechanics_initial"][cache_name])
            ):
                raise ValueError(
                    "Ordinary disabled-flow composition requires shared held-zero velocity stores"
                )
        drive = raw["pressure_drives"][index]
        if set(drive) != {"stage", "source_step", "P_base_Pa", "P_mod_Pa"} or (
            drive["stage"] != "after_fire_events_before_pumps" or drive["source_step"] != index
        ):
            raise ValueError("Pressure must be declared at its reached source event boundary")
        for key in ("P_base_Pa", "P_mod_Pa"):
            value = np.asarray(drive[key], dtype=float)
            if value.shape != (n,) or not np.isfinite(value).all():
                raise ValueError("Require complete finite hydrostatic pressure owners")
            if raw["pressure_policy"] == "native_zero_baseline_no_pressure_events" and np.any(
                value != 0
            ):
                raise ValueError(
                    "The native zero-pressure baseline cannot acquire invented pressure"
                )
    mechanics.state(mb, raw["mechanics_initial"])
    return Binding(fb, mb, ions.freeze(raw), ions.digest((LAW_ID, fb.identity, mb.identity, raw)))


def initialize(binding, *, observer=None):
    if observer is not None:
        inputs = ions.data(binding.field.inputs)
        observer(
            "cold-input",
            dict(
                mode="cold_initialization",
                network=inputs["network"],
                material_declaration=inputs["definition"],
                ion_ids=inputs["definition"]["environment_geometry_definition"][
                    "current_definition"
                ]["ions"]["ids"],
                cells=len(inputs["initial"]["cell_mol_m3"][0]),
                membranes=len(inputs["initial"]["voltage_V"]),
                environment_sites=len(inputs["initial"]["environment_mol_m3"][0]),
            ),
        )

    def before_field(incoming):
        if observer is not None:
            observer("bootstrap-input", incoming)

    def after_cold(parent):
        if observer is not None:
            observer("cold-output", parent)

    fields = field.initialize(binding.field, before_field=before_field, after_cold=after_cold)
    if observer is not None:
        observer("bootstrap-output", fields)
    mechanical = mechanics.state(binding.mechanics, ions.data(binding.inputs["mechanics_initial"]))
    result = state(binding, fields, mechanical)
    if observer is not None:
        observer("initial-parent", result)
    return result


def mechanics_input(binding, parent, ctx, pressure, index):
    """Old field outputs; current ionic and actual post-dispatch gene rows."""
    geometry = binding.mechanics.definition["geometry"]
    previous = parent.field.field
    molecular = ctx.sim.grn.core.molecules
    names = list(molecular)
    return dict(
        receipt=dict(
            stage=mechanics.FIELD_STAGE,
            geometry_epoch=binding.mechanics.definition["provenance"]["geometry_epoch"],
            cell_ids=geometry["cell_ids"],
            environment_ids=geometry["environment_ids"],
            source_step=index,
            deferred_material_voltage_commit_done=False,
        ),
        clock_s=ions.data(binding.inputs["clocks_s"])[index],
        dt_s=binding.mechanics.definition["parameters"]["dt_s"],
        temperature_K=float(ctx.sim.T),
        pressure_Pa=pressure,
        electric_field_V_m=np.asarray(previous.voltage.values.cell_field_xy_V_m).T,
        current_density_A_m2=np.asarray(previous.current.values.cell_current_xy_A_m2).T,
        charge_density_C_m3=previous.current.values.charge_density_C_m3,
        conductivity_S_m=binding.field.material_binding.geometry_binding.cache.sigma_S_m,
        primary_ids=list(binding.field.material_binding.geometry_binding.current_binding.ion_ids),
        primary_cell_mM=np.array(ctx.sim.cc_cells, copy=True),
        primary_env_mM=np.array(ctx.sim.cc_env, copy=True),
        molecule_ids=[],
        molecule_cell_mM=[],
        molecule_env_mM=[],
        grn_ids=names,
        grn_cell_mM=[np.array(molecular[name].c_cells, copy=True) for name in names],
        grn_env_mM=[np.array(molecular[name].c_env, copy=True) for name in names],
        sample=False,
    )


def advance(binding, parent, *, observer=None):
    if (
        type(parent) is not State
        or parent.binding_identity != binding.identity
        or (parent.identity != ions.digest((binding.identity, parent.field, parent.mechanics)))
    ):
        raise ValueError("Require the full unchanged coupled parent")
    fb = binding.field
    old = parent.field
    if old.binding_identity != fb.identity or old.identity != ions.digest(
        (fb.identity, old.network, old.field)
    ):
        raise ValueError("Require the actual prior full ECM field parent")
    if (
        type(old.field) is not field.FieldStage
        or old.field.binding_identity != fb.identity
        or old.field.identity != ions.digest(field.field_record(old.field))
    ):
        raise ValueError("Changed prior field before mechanics")
    mechanics._verify(binding.mechanics, parent.mechanics)
    index = old.network.material.step_index
    if index != parent.mechanics.step_index or not 0 <= index < 3:
        raise ValueError("Material and mechanics source counters must name the same call")
    row = ions.data(fb.inputs["steps"][index])
    controls = (
        ions.data(old.network.controls)
        if row["scheduled_controls"] is None
        else row["scheduled_controls"]
    )
    packet = dict(
        row["material"],
        junction_block=controls["gj_block"],
        electric_x_source=old.field.environment.values.electric_x_source,
        electric_y_source=old.field.environment.values.electric_y_source,
    )
    forcing = material.drive(fb.material_binding, packet)
    drive = ions.data(binding.inputs["pressure_drives"])[index]
    pressure = np.asarray(drive["P_mod_Pa"]) + np.asarray(drive["P_base_Pa"])
    holder = {}

    def emit(name, value):
        if observer is not None:
            observer("step-" + str(index) + "-" + name, value)

    emit("parent", parent)
    emit(
        "pressure-prerequisite",
        dict(policy=binding.inputs["pressure_policy"], drive=drive, P_cells_Pa=pressure),
    )
    emit(
        "material-input",
        dict(
            mode="material",
            definition=ions.data(fb.inputs["definition"]),
            initial=ions.data(old.network.material.values._asdict()),
            steps=[source.clone(packet)],
        ),
    )

    def on_network(arrays):
        ctx = field.make_context(fb, arrays, ions.data(fb.inputs["network"]), forcing)
        holder["ctx"] = ctx
        source.restore(ctx, old.network.network_cache)
        ctx.sim.gj_block = np.asarray(controls["gj_block"], dtype=float).copy()
        ctx.sim.NaKATP_block = np.asarray(controls["NaKATP_block"], dtype=float).copy()
        source.run_dispatch(
            ctx,
            ions.data(fb.inputs["definition"]),
            row["publication"],
            lambda incoming: emit("network-input", incoming),
        )
        emit(
            "network-output-before-mechanics",
            dict(
                trace=ctx.trace, cache=source.cache(ctx), material=source.material_values(ctx.sim)
            ),
        )
        incoming = mechanics_input(binding, parent, ctx, pressure, index)
        holder["mechanics_input"] = incoming
        emit(
            "mechanics-input",
            dict(
                definition=binding.mechanics.definition,
                initial=parent.mechanics.cache,
                steps=[incoming],
                full_prior_field=old.field,
            ),
        )
        try:
            trial = mechanics.step(binding.mechanics, parent.mechanics, incoming)
        except Exception as error:
            holder["mechanics_failure"] = getattr(error, "trial", None)
            raise
        holder["mechanics_trial"] = trial
        emit("mechanics-output-before-material", trial)

    def on_failure(local):
        holder["material_failure"] = dict(
            frames=tuple(local.get("frames", ())),
            environment_records=tuple(local.get("environment_records", ())),
            trial=local.get("trial"),
            diagnostics=local.get("diagnostics"),
            failure=local.get("failure"),
            available_arrays={
                key: value.copy() for key, value in local.items() if isinstance(value, np.ndarray)
            },
        )

    try:
        trial = field.material_step(
            fb.material_binding,
            old.network.material,
            forcing,
            on_network=on_network,
            on_failure=on_failure,
        )
        holder["material_trial"] = trial
        ctx = holder["ctx"]
        material_parent = field._state(
            fb, trial.candidate, source.cache(ctx), ctx.trace["controls_after"]
        )
        emit(
            "material-output-before-field",
            dict(candidate=material_parent, trial=trial, network=ctx.trace),
        )
        prepared, fields = field.reconstruct(
            fb,
            material_parent,
            packet["dt_s"],
            row["boundary_V"],
            "field",
            lambda incoming: emit("field-input", incoming),
        )
        result = state(
            binding, field.state(fb, prepared, fields), holder["mechanics_trial"].candidate
        )
        emit("complete-output", result)
        return result, dict(
            material_trial=trial,
            network_trace=ions.freeze(ctx.trace),
            material_parent=material_parent,
            mechanics_trial=holder["mechanics_trial"],
            mechanics_input=ions.freeze(holder["mechanics_input"]),
            initial_field=old.field,
            final_field=fields,
        )
    except Exception as error:
        partial = dict(
            parent=parent,
            stage="field" if "material_trial" in holder else "mechanics_or_material",
            pressure_prerequisite=drive,
            **{key: value for key, value in holder.items() if key != "ctx"},
            source_failure=field._failure_snapshot(holder.get("ctx"), old.network.network_cache),
            field_failure=getattr(error, "partial", None),
            reason=str(error),
        )
        emit("raw-failure", partial)
        raise CompositionRejected(error, partial) from error
