"""Exact held-owner/source-order checks; no new numerical allowance."""

from validation.betse.betse_normal_ecm_mechanics_join_boundaries import assert_identical

HELD_SIMULATOR_FIELDS = (
    "P_cells",
    "PP",
    "E_cell_x",
    "E_cell_y",
    "E_env_x",
    "E_env_y",
    "J_cell_x",
    "J_cell_y",
    "rho_cells",
    "u_cells_x",
    "u_cells_y",
    "J_env_x",
    "J_env_y",
    "cc_cells",
    "cc_at_mem",
    "cc_env",
    "zs",
)


def held_source_owners(cold, history):
    for row in history:
        snapshot, trace = row["snapshot"], row["trace"]
        for name in HELD_SIMULATOR_FIELDS:
            assert_identical(snapshot["simulator"][name], cold["simulator"][name])
        assert_identical(snapshot["grid_fields"], cold["grid_fields"])
        decisions = trace["flow_activations"]
        if len(decisions) != 1:
            raise ValueError("Exactly one source flow decision must precede each invocation loop")
        activation = decisions[0]
        before, after = activation["before"], activation["after"]
        assert activation["computed_after_reinitialize_and_clear_cache"] is True
        assert activation["ordinary_getFlow_called"] is False
        for name in HELD_SIMULATOR_FIELDS:
            assert_identical(before["simulator"][name], after["simulator"][name])
        if activation["recalculate_fluid"]:
            assert after["parameters"]["fluid_flow"] is True
            assert len(trace["stream_plot_calls"]) == 3
            assert [call["operation"] for call in trace["stream_plot_calls"]] == [
                "figure",
                "subplot",
                "plotStreamField",
            ]
            assert all(call["rendered"] is False for call in trace["stream_plot_calls"])
        else:
            assert trace["stream_plot_calls"] == []
            assert_identical(after["parameters"]["fluid_flow"], before["parameters"]["fluid_flow"])
            for name in ("u_env_x", "u_env_y"):
                assert_identical(after["simulator"][name], before["simulator"][name])
        for step in trace["steps"]:
            for axis in ("x", "y"):
                held = after["simulator"]["u_env_" + axis]
                assert_identical(step["before"]["velocity_" + axis + "_m_s"], held)
                assert_identical(step["after"]["simulator"]["u_env_" + axis], held)
        for frame in trace["mover_frames"]:
            if frame["stage"] not in ("ecm_flux", "ecm_euler"):
                continue
            supplied = frame["flow_inputs"]
            for axis in ("x", "y"):
                actual = supplied["u" + axis]
                if supplied["fluid_flow"] is True:
                    assert_identical(actual, after["simulator"]["u_env_" + axis])
                else:
                    assert actual == 0.0
    return dict(
        invocations=len(history),
        complete_held_owners=True,
        pressure_electric_or_ionic_recomputation=False,
        geometry_moved=False,
        flow_computed_once_per_invocation=True,
    )
