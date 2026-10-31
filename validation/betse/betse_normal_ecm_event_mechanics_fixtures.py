"""Deferred shared supplied-state specimens; no physical seed or fixture execution here."""

from copy import deepcopy

from cells.processes import betse_ecm_transport as material
from validation.betse import betse_normal_ecm_event_join_fixtures as events
from validation.betse import betse_normal_ecm_mechanics_join_fixtures as mechanical

CASES = (
    "combined",
    "salt_order",
    "temperature",
    "GJ_override",
    "NaK_shape",
    "membrane_four",
    "ecmJ",
    "periodic",
    "sweep",
    "voltage_same_edge",
    "profile_duplicate",
    "static_K_reset",
    "noise_zero_level",
    "noise_disabled",
    "no_events",
    "no_channel",
    "no_CaATP",
    "rectangular",
    "fast_duplicate",
    "moving_P_noise",
    "pressure_only",
    "mechanics_disabled",
    "osmotic_without_deformation",
    "no_aquaporin",
    "sparse_sampling",
)
COMPONENT_CONTROLS = (
    "static_K_reset",
    "noise_zero_level",
    "noise_disabled",
    "no_events",
    "no_channel",
    "no_CaATP",
    "pressure_only",
    "mechanics_disabled",
    "osmotic_without_deformation",
    "no_aquaporin",
)
RAW_CASES = (
    "zero_global_pulse_width",
    "radial_pressure_shape",
    "negative_Dm_source_return",
    "protein_noise_large_limit",
    "GRN_refuses_before_noise",
    "late_negative_temperature",
    "mechanics_overflow_before_commit",
)
DEPENDENCIES = (
    "foreign_cell_owners",
    "foreign_membrane_owners",
    "changed_cell_measure",
    "changed_membrane_measure",
    "changed_centres",
    "changed_environment_map",
    "wrong_phase_dt",
    "enabled_flow",
    "dynamic_deformation",
    "FAST",
    "display_regime",
    "physical_initialization",
    "cut_requested",
    "missing_owner",
    "wrong_RNG_version",
    "competing_control_override",
    "nonzero_disabled_flow",
    "foreign_mechanics_parent",
    "changed_prior_field",
    "wrong_clock",
    "changed_event_store",
    "changed_noise_cache",
    "sampled_display",
    "unsampled_display",
    "changed_binding",
    "changed_sample_state",
)
CORRUPTIONS = ("wrong_PP", "wrong_displacement_axis", "end_field_epoch", "pre_noise_primary_epoch")


def shared(event_inputs, case):
    # This new coupled declaration uses held-zero fluid stores; old component
    # fixtures remain byte-for-byte unchanged and contribute no carried credit.
    for step in event_inputs["field"]["steps"]:
        for key in ("velocity_x_m_s", "velocity_y_m_s"):
            step["material"][key] = [[0.0 for _ in row] for row in step["material"][key]]
    baseline = mechanical.fixture("coupled-osmotic")
    definition = deepcopy(baseline["mechanics_definition"])
    initial = deepcopy(baseline["mechanics_initial"])
    field = event_inputs["field"]
    external = field["definition"]["environment_geometry_definition"]
    cg = external["current_definition"]["geometry"]
    fg = external["geometry"]
    n, m = len(cg["cell_ids"]), len(cg["membrane_ids"])
    if (n, m) != (3, 9):
        raise ValueError("Require the declared shared3/9 DEC owner layout")
    bound = material.bind(field["definition"])
    geometry = definition["geometry"]
    layout = geometry["layout"]
    layout.update(
        centers_m=deepcopy(fg["cell_centres_m"]),
        cell_volume_m3=deepcopy(fg["cell_volume_m3"]),
        membrane_ids=list(cg["membrane_ids"]),
        membrane_area_m2=deepcopy(cg["membrane_area_m2"]),
        cell_area_m2=deepcopy(cg["cell_area_m2"]),
        cell_height_m=external["parameters"]["cell_height_m"],
    )
    geometry["cell_ids"] = list(cg["cell_ids"])
    geometry["environment_ids"] = [
        "native-grid/" + str(k) for k in range(len(bound.geometry_binding.geometry.grid_points_m))
    ]
    geometry["cell_to_environment"] = bound.geometry_binding.geometry.cell_to_grid.tolist()
    geometry["membrane_to_environment"] = bound.geometry_binding.geometry.membrane_to_grid.tolist()
    e = len(geometry["environment_ids"])
    geometry["environment_average"] = [
        [float(j == geometry["cell_to_environment"][i]) for j in range(e)] for i in range(n)
    ]
    for key in ("u_env_x", "u_env_y"):
        drive = "velocity_x_m_s" if key == "u_env_x" else "velocity_y_m_s"
        initial[key] = deepcopy(field["steps"][0]["material"][drive])
    initial["osmo_P_env"] = [0.0] * e
    initial["display_centres_m"] = deepcopy(layout["centers_m"])
    definition["parameters"].update(
        dt_s=event_inputs["calendar"]["dt_s"],
        gas_constant_J_mol_K=field["definition"]["parameters"]["R_J_mol_K"],
        membrane_thickness_m=field["definition"]["parameters"]["membrane_thickness_m"],
        cell_radius_m=external["parameters"]["cell_radius_m"],
    )
    if case == "pressure_only":
        definition["policy"]["deform_osmo"] = False
        definition["parameters"]["galvanotropism_m2_V"] = 0.0
    elif case == "mechanics_disabled":
        definition["policy"].update(deformation=False, deform_osmo=False)
    elif case == "osmotic_without_deformation":
        definition["policy"]["deformation"] = False
    elif case == "no_aquaporin":
        definition["parameters"]["aquaporin_fraction"] = 0.0
    return dict(
        kind="cells.normal_ecm_event_mechanics_inputs@1",
        case_id=case,
        event_inputs=event_inputs,
        mechanics_definition=definition,
        mechanics_initial=initial,
        sample_policy="calendar_eligibility_only_explicit_display_refusal",
    )


def fixture(case="combined"):
    if case not in CASES:
        raise ValueError("Choose a declared shared event/mechanics case")
    event_inputs = events.fixture(case if case in events.CASES else "combined")
    if case == "sparse_sampling":
        event_inputs["calendar"]["sample_stride"] = 2.0
    return shared(event_inputs, case)


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Choose a declared coupled raw source limit")
    if case in events.RAW_CASES:
        return shared(events.raw_fixture(case), case)
    event_inputs = events.fixture("no_events")
    entry = event_inputs["entry_event_state"]
    entry["P_base"] = [1.0, -1.0, 0.5]
    entry["P_mod"] = [0.0, 0.0, 0.0]
    entry["P_cells"] = list(entry["P_base"])
    result = shared(event_inputs, case)
    result["mechanics_definition"]["parameters"]["young_modulus_Pa"] = 1e-320
    return result
