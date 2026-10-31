"""Common mechanics validation and actual post-network input, before commit.

Only the event-wrapper nesting is removed. Constitutive arithmetic stays in the
existing ordinary steady/osmotic mechanics component and its unchanged budgets.
"""

import numpy as np

from cells.processes import betse_mechanics_join as mechanics


def bind(raw, eb):
    policy = raw["mechanics_definition"]["policy"]
    if policy["display_regime"] != "none":
        raise ValueError("Keep native display held on the existing field domain")
    mb = mechanics.bind(raw["mechanics_definition"])
    if not policy["is_ecm"] or policy["molecules_enabled"] or (not policy["grn_enabled"]):
        raise ValueError("Require actual ECM GRN owner and no separate molecule handler")
    fb = eb
    definition = mb.definition
    cg = fb.material_binding.geometry_binding.definition["current_definition"]["geometry"]
    geometry = fb.material_binding.geometry_binding.definition["geometry"]
    mg = definition["geometry"]
    layout = mg["layout"]
    n, m = (len(cg["cell_ids"]), len(cg["membrane_ids"]))
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
    if (
        p["gas_constant_J_mol_K"] != fb.material_binding.kernel.R_J_mol_K
        or p["membrane_thickness_m"] != fb.material_binding.kernel.membrane_thickness_m
    ):
        raise ValueError("Use the actual shared pressure constants and membrane thickness")
    for packet in eb.inputs["steps"]:
        if packet["material"]["dt_s"] != p["dt_s"] or p["dt_s"] != eb.calendar.dt_s:
            raise ValueError("Require the same native phase dt for events, material and mechanics")
        for drive, cached in (("velocity_x_m_s", "u_env_x"), ("velocity_y_m_s", "u_env_y")):
            values = np.asarray(packet["material"][drive])
            if np.any(values != 0) or not np.array_equal(
                values, np.asarray(raw["mechanics_initial"][cached])
            ):
                raise ValueError("Disabled fluid needs shared held-zero velocity stores")
    mechanics.state(mb, raw["mechanics_initial"])
    return mb


def mechanics_input(binding, parent, ctx, index):
    geometry = binding.mechanics.definition["geometry"]
    previous = parent.field
    molecules = ctx.sim.grn.core.molecules
    names = list(molecules)
    return dict(
        receipt=dict(
            stage=mechanics.FIELD_STAGE,
            geometry_epoch=binding.mechanics.definition["provenance"]["geometry_epoch"],
            cell_ids=geometry["cell_ids"],
            environment_ids=geometry["environment_ids"],
            source_step=index,
            deferred_material_voltage_commit_done=False,
        ),
        clock_s=float(parent.clock.source_times_s[index]),
        dt_s=binding.calendar.dt_s,
        temperature_K=float(ctx.sim.T),
        pressure_Pa=np.array(ctx.sim.P_cells, copy=True),
        electric_field_V_m=np.asarray(previous.voltage.values.cell_field_xy_V_m).T,
        current_density_A_m2=np.asarray(previous.current.values.cell_current_xy_A_m2).T,
        charge_density_C_m3=previous.current.values.charge_density_C_m3,
        conductivity_S_m=binding.material_binding.geometry_binding.cache.sigma_S_m,
        primary_ids=list(binding.material_binding.geometry_binding.current_binding.ion_ids),
        primary_cell_mM=np.array(ctx.sim.cc_cells, copy=True),
        primary_env_mM=np.array(ctx.sim.cc_env, copy=True),
        molecule_ids=[],
        molecule_cell_mM=[],
        molecule_env_mM=[],
        grn_ids=names,
        grn_cell_mM=[np.array(molecules[name].c_cells, copy=True) for name in names],
        grn_env_mM=[np.array(molecules[name].c_env, copy=True) for name in names],
        sample=False,
    )
