"""Ordinary disabled-flow ownership seam; no new enabled flow trajectory."""

import traceback
from dataclasses import dataclass

import numpy as np

from cells.processes import betse_normal_ecm_mechanics_join as ordinary
from cells.processes import betse_normal_ion_join as ions

LAW_ID = "betse_ordinary_ecm_disabled_flow_ownership_v1_5_0@1"
INPUT_KIND = "cells.betse_normal_ecm_flow_join_inputs@1"
FLOW_STORES = ("u_cells_x", "u_cells_y", "u_env_x", "u_env_y")


@dataclass(frozen=True)
class Binding:
    ordinary: ordinary.Binding
    inputs: object
    identity: str


@dataclass(frozen=True)
class FlowPoint:
    binding_identity: str
    parent_identity: str
    source_step: int
    values: object
    identity: str


class FlowJoinRejected(RuntimeError):
    def __init__(self, reason, *, stage, partial):
        super().__init__(str(reason))
        self.stage, self.partial = stage, ions.freeze(ions.data(partial))


def bind(inputs):
    raw = ions.data(inputs)
    if set(raw) != {"kind", "case_id", "ordinary_inputs"} or raw["kind"] != INPUT_KIND:
        raise ValueError("Declare only the ordinary disabled-flow ownership composition")
    inherited = raw["ordinary_inputs"]
    if raw["case_id"] != inherited["case_id"]:
        raise ValueError("Keep the complete original ordinary caller identity")
    if (
        inherited["mechanics_definition"]["policy"]["fluid_flow"] is not False
        or inherited["field_inputs"]["definition"]["parameters"]["fluid_flow"] is not False
    ):
        raise ValueError("Pinned ordinary loader disables flow; standalone GRN is a separate phase")
    shared = ordinary.bind(inherited)
    frozen = ions.freeze(raw)
    return Binding(shared, frozen, ions.digest((LAW_ID, shared.identity, frozen)))


def _verify(binding):
    if type(binding) is not Binding or binding.identity != ions.digest(
        (LAW_ID, binding.ordinary.identity, binding.inputs)
    ):
        raise ValueError("Require the complete unchanged disabled-flow binding")


def initialize(binding, *, observer=None):
    _verify(binding)
    return ordinary.initialize(binding.ordinary, observer=observer)


def _same_arrays(first, second, names):
    for name in names:
        a, b = np.asarray(first[name]), np.asarray(second[name])
        if a.dtype != b.dtype or a.shape != b.shape or a.tobytes() != b.tobytes():
            raise ValueError("Disabled flow changed a typed source cache: " + name)


def _point(binding, parent, incoming, network_after, mechanical):
    shared = binding.ordinary
    geometry = shared.field.material_binding.geometry_binding.geometry
    declaration = shared.mechanics.definition["geometry"]
    frames = mechanical["frames"]
    positions = [i for i, row in enumerate(frames) if row["stage"] == "disabled_flow_gate"]
    if len(positions) != 1 or positions[0] == 0 or mechanical["auxiliaries"]["flow"] is not None:
        raise ValueError("Require the actual single disabled source gate and its None result")
    index = positions[0]
    before, after = frames[index - 1]["cache"], frames[index]["cache"]
    if set(before) != set(after):
        raise ValueError("Keep the complete gate cache, including pressure and displacement")
    _same_arrays(before, after, before)
    _same_arrays(parent.mechanics.cache, mechanical["candidate"]["cache"], FLOW_STORES)
    previous = parent.field.field
    step = incoming["receipt"]["source_step"]
    supplied = shared.field.inputs["steps"][step]["material"]
    values = dict(
        source_step=step,
        source_stage="after_optional_osmotic_before_deformation_and_deferred_material_voltage",
        observation="Recovered from unchanged mechanics frames before deferred material commit",
        policy=dict(
            ordinary_fluid_flow=False,
            material_fluid_flow=False,
            source_getFlow_executed=False,
            existing_component_gate_result=None,
        ),
        ownership=dict(
            cell_ids=declaration["cell_ids"],
            membrane_ids=declaration["layout"]["membrane_ids"],
            environment_ids=declaration["environment_ids"],
            shape=geometry.shape,
            delta_m=geometry.delta_m,
            cell_to_grid=geometry.cell_to_grid,
            membrane_to_grid=geometry.membrane_to_grid,
        ),
        mechanics_input=incoming,
        previous_field=dict(
            current=previous.current.values._asdict(),
            environment=previous.environment.values._asdict(),
            voltage=previous.voltage.values._asdict(),
        ),
        post_GRN_cache=network_after["cache"],
        post_GRN_material=network_after["material"],
        complete_cache_before_flow=before,
        complete_cache_after_flow=after,
        source_mechanics_stage_order=[row["stage"] for row in frames],
        transport_input=dict(
            velocity_x_m_s=supplied["velocity_x_m_s"],
            velocity_y_m_s=supplied["velocity_y_m_s"],
            preceding_transport_consumes_zero_flow=True,
            new_flow_output_fed_into_transport=False,
        ),
    )
    frozen = ions.freeze(ions.data(values))
    identity = ions.digest((LAW_ID, binding.identity, parent.identity, step, frozen))
    return FlowPoint(binding.identity, parent.identity, step, frozen, identity)


def verify_point(binding, parent, point):
    _verify(binding)
    if type(point) is not FlowPoint or (
        point.binding_identity != binding.identity
        or point.parent_identity != parent.identity
        or point.source_step != parent.field.network.material.step_index
        or point.identity
        != ions.digest((LAW_ID, binding.identity, parent.identity, point.source_step, point.values))
    ):
        raise ValueError("Require the unchanged flow seam and its actual prior full parent")


def advance(binding, parent, *, observer=None):
    _verify(binding)
    records, captured = {}, {}
    step = parent.field.network.material.step_index
    stem = "step-" + str(step) + "-"

    def observe(name, value):
        records[name] = ions.freeze(ions.data(value))
        if name == stem + "mechanics-output-before-material":
            point = _point(
                binding,
                parent,
                records[stem + "mechanics-input"]["steps"][0],
                records[stem + "network-output-before-mechanics"],
                records[name],
            )
            captured["point"] = point
            records[stem + "flow-point"] = ions.freeze(ions.data(point))
            if observer is not None:
                observer(stem + "flow-point", point)
        if observer is not None:
            observer(name, value)

    try:
        candidate, context = ordinary.advance(binding.ordinary, parent, observer=observe)
        point = captured["point"]
        verify_point(binding, parent, point)
        _same_arrays(parent.mechanics.cache, candidate.mechanics.cache, FLOW_STORES)
        return candidate, dict(
            context,
            disabled_flow_point=point,
            ordinary_getFlow_executed=False,
            standalone_diagnostic_executed=False,
        )
    except Exception as error:
        partial = dict(
            parent=parent,
            binding_identity=binding.identity,
            source_step=step,
            completed_records=records,
            completed_flow_point=captured.get("point"),
            original_type=type(error).__name__,
            original_reason=str(error),
            original_stage=getattr(error, "stage", None),
            original_partial=getattr(error, "partial", None),
            traceback=traceback.format_exc(),
            accepted_candidate=False,
            ordinary_getFlow_executed=False,
        )
        raise FlowJoinRejected(
            error, stage="ordinary_disabled_flow_composition", partial=partial
        ) from error


def standalone_diagnostic_input(binding, parent, point):
    """Export source-format inputs; evaluates no flow and enables no ordinary branch."""
    verify_point(binding, parent, point)
    raw = ions.data(point.values)
    declaration = ions.data(binding.ordinary.inputs)
    field = declaration["field_inputs"]["definition"]
    geometry = declaration["mechanics_definition"]["geometry"]
    environment = field["environment_geometry_definition"]
    previous = raw["previous_field"]
    shape = tuple(raw["ownership"]["shape"])
    world = environment["world"]
    result = dict(
        name="conditional-only-source-step-" + str(point.source_step),
        layout=geometry["layout"],
        cell_ids=geometry["cell_ids"],
        environment_ids=geometry["environment_ids"],
        shape=list(shape),
        delta_m=raw["ownership"]["delta_m"],
        bounds_m=[world[k + "_m"] for k in ("xmin", "xmax", "ymin", "ymax")],
        is_ecm=True,
        viscosity_Pa_s=0.01,
        gj_fraction=field["parameters"]["gap_surface_fraction"],
        epsilon_F_m=environment["parameters"]["vacuum_permittivity_F_m"],
        relative_permittivity=environment["parameters"]["relative_permittivity"],
        cell_E_V_m=np.asarray(previous["voltage"]["cell_field_xy_V_m"]).T,
        cell_rho_C_m3=previous["current"]["charge_density_C_m3"],
        environment_E_V_m=np.stack(
            [
                previous["environment"]["electric_x_source"],
                previous["environment"]["electric_y_source"],
            ]
        ),
        environment_potential_V=np.asarray(
            previous["environment"]["environment_voltage_V"]
        ).reshape(shape),
        diffusion_weight=raw["post_GRN_cache"]["coefficient_fields"]["D_env_weight"],
        pressure_Pa=raw["mechanics_input"]["pressure_Pa"],
        osmotic_PP_native=raw["complete_cache_before_flow"]["PP"],
    )
    return dict(
        kind="standalone_flow_conditional_input_export_only@1",
        raw=ions.freeze(result),
        source_point_identity=point.identity,
        numerical_flow_evaluations=0,
        ordinary_activation=False,
        ordinary_feedback=False,
        new_owner_qualification_inherited=False,
        transport_unit_conversion_performed=False,
    )
