"""Production-free reconstruction of the disabled seam from native phase evidence."""

from copy import deepcopy

from validation.betse.betse_normal_ecm_mechanics_join_boundaries import assert_identical

FLOW_STORES = ("u_cells_x", "u_cells_y", "u_env_x", "u_env_y")


def native_points(inputs, proof):
    ordinary = inputs["ordinary_inputs"]
    fields, mechanics = proof["ionic_field"], proof["mechanics"]
    if mechanics is None:
        return []
    geometry = ordinary["mechanics_definition"]["geometry"]
    grid = fields["geometry"]
    previous = fields["bootstrap"]
    result = []
    for index, (mechanical, incoming) in enumerate(
        zip(mechanics["history"], proof["mechanics_inputs"]["steps"], strict=True)
    ):
        frames = mechanical["frames"]
        positions = [i for i, row in enumerate(frames) if row["stage"] == "disabled_flow_gate"]
        if len(positions) != 1:
            break
        position = positions[0]
        row = fields["history"][index]
        packet = ordinary["field_inputs"]["steps"][index]["material"]
        result.append(
            dict(
                source_step=index,
                source_stage=(
                    "after_optional_osmotic_before_deformation_and_deferred_material_voltage"
                ),
                observation=(
                    "Recovered from unchanged mechanics frames before deferred material commit"
                ),
                policy=dict(
                    ordinary_fluid_flow=False,
                    material_fluid_flow=False,
                    source_getFlow_executed=False,
                    existing_component_gate_result=None,
                ),
                ownership=dict(
                    cell_ids=geometry["cell_ids"],
                    membrane_ids=geometry["layout"]["membrane_ids"],
                    environment_ids=geometry["environment_ids"],
                    **{
                        key: grid[key]
                        for key in ("shape", "delta_m", "cell_to_grid", "membrane_to_grid")
                    },
                ),
                mechanics_input=incoming,
                previous_field={
                    key: previous[key]["values"] for key in ("current", "environment", "voltage")
                },
                post_GRN_cache=row["network"]["cache_after"],
                post_GRN_material=row["network"]["values_after"],
                complete_cache_before_flow=frames[position - 1]["cache"],
                complete_cache_after_flow=frames[position]["cache"],
                source_mechanics_stage_order=[frame["stage"] for frame in frames],
                transport_input=dict(
                    velocity_x_m_s=packet["velocity_x_m_s"],
                    velocity_y_m_s=packet["velocity_y_m_s"],
                    preceding_transport_consumes_zero_flow=True,
                    new_flow_output_fed_into_transport=False,
                ),
            )
        )
        previous = row.get("field")
    return deepcopy(result)


def disabled_reference(point):
    """Exact independent conditional output: the source false branch writes nothing."""
    policy = point["policy"]
    if policy != dict(
        ordinary_fluid_flow=False,
        material_fluid_flow=False,
        source_getFlow_executed=False,
        existing_component_gate_result=None,
    ):
        raise ValueError("Only the pinned ordinary disabled branch is reachable")
    before, after = point["complete_cache_before_flow"], point["complete_cache_after_flow"]
    if set(before) != set(after) or any(name not in before for name in FLOW_STORES):
        raise ValueError("Require all flow, pressure and mechanics cache owners")
    assert_identical(after, before)
    order = point["source_mechanics_stage_order"]
    if order.count("disabled_flow_gate") != 1 or order[0] != "initial":
        raise ValueError("Missing actual disabled-flow source frame")
    position = order.index("disabled_flow_gate")
    if "osmotic_pressure" in order and order.index("osmotic_pressure") >= position:
        raise ValueError("Osmotic pressure must precede the disabled flow gate")
    if "steady_deformation" in order and order.index("steady_deformation") <= position:
        raise ValueError("Steady deformation must follow the disabled flow gate")
    return dict(
        flow_store_names=list(FLOW_STORES),
        expected_cache=deepcopy(before),
        source_getFlow_executed=False,
        physical_flow_claim=False,
        enabled_conditional_equations_reevaluated=False,
    )
