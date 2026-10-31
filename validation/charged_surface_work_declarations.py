"""Literal supplied-patch cases, constructed only in a future authorized run.

These are numerical component controls, not inferred BETSE tissue populations.
Every refinement arm declares its complete horizon and clock at initial binding.
"""

from copy import deepcopy

LAW_ID = "held_charged_surface_prescribed_field_work@1"


def _declaration(owners, layout, initial, potential, *, steps=32, horizon_s=4.0):
    return dict(
        kind="charged_surface_work_declaration@1",
        law=LAW_ID,
        scope="supplied_fixed_surface_prescribed_field_component@1",
        policies=dict(
            chemical="ideal_dilute_surface_mixture@1",
            field="prescribed_time_constant_potential@1",
            thermal="maintained_isothermal_temperature@1",
            charge="constant_effective_cargo_no_ionic_field_feedback@1",
        ),
        owners=owners,
        layout=layout,
        initial_amount_fmol=initial,
        reference_density_fmol_um2=[1.0 for _ in owners["populations"]],
        prescribed_potential_V=potential,
        time_labels_s=[horizon_s * step / steps for step in range(steps + 1)],
        provenance=dict(
            caller="held charged-surface independent component declaration",
            units=dict(
                amount="fmol",
                area="um2",
                length="um",
                diffusivity="um2/s",
                potential="V",
                temperature="K",
                energy="pJ",
                time="s",
            ),
        ),
    )


def two_patch(*, charge=1.0, steps=32, potential=(0.01, -0.01), initial=(0.0001, 0.0002)):
    return _declaration(
        dict(
            cells=["cell-a"],
            patches=["a-left", "a-right"],
            populations=["charged-cargo"],
            edges=["a-edge"],
        ),
        dict(
            temperature_K=298.15,
            effective_charge_e=[charge],
            cell_active=[True],
            patch_active=[True, True],
            patch_cell=[0, 0],
            patch_area_um2=[2.0, 5.0],
            edge_active=[True],
            edge_sender=[0],
            edge_receiver=[1],
            edge_diffusivity_um2_s=[[0.2]],
            edge_width_um=[1.5],
            edge_distance_um=[0.8],
        ),
        [list(initial)],
        list(potential),
        steps=steps,
    )


def multi_owner():
    return _declaration(
        dict(
            cells=["cell-a", "cell-b", "padding-cell"],
            patches=["a-left", "a-right", "b-left", "b-right", "padding-patch"],
            populations=["neutral", "positive", "negative", "absent"],
            edges=["a-edge", "b-edge", "padding-edge"],
        ),
        dict(
            temperature_K=300.0,
            effective_charge_e=[0.0, 1.0, -1.0, 2.0],
            cell_active=[True, True, False],
            patch_active=[True, True, True, True, False],
            patch_cell=[0, 0, 1, 1, 2],
            patch_area_um2=[2.0, 3.0, 4.0, 5.0, 0.0],
            edge_active=[True, True, False],
            edge_sender=[0, 2, 0],
            edge_receiver=[1, 3, 0],
            edge_diffusivity_um2_s=[
                [0.2, 0.3, 0.0],
                [0.1, 0.2, 0.0],
                [0.15, 0.25, 0.0],
                [0.1, 0.2, 0.0],
            ],
            edge_width_um=[1.5, 2.0, 0.0],
            edge_distance_um=[0.8, 1.2, 0.0],
        ),
        [
            [0.0001, 0.0002, 0.0003, 0.0004, 0.0],
            [0.0002, 0.0001, 0.0004, 0.0003, 0.0],
            [0.0001, 0.0003, 0.0002, 0.0004, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0],
        ],
        [0.015, -0.005, -0.01, 0.02, 0.0],
    )


def no_edges():
    raw = two_patch()
    raw["owners"]["edges"] = []
    for key in ("edge_active", "edge_sender", "edge_receiver", "edge_width_um", "edge_distance_um"):
        raw["layout"][key] = []
    raw["layout"]["edge_diffusivity_um2_s"] = [[]]
    return raw


def transformed(raw, kind):
    result = deepcopy(raw)
    if kind == "potential_gauge":
        result["prescribed_potential_V"] = [
            phi + 0.125 if active else 0.0
            for phi, active in zip(
                raw["prescribed_potential_V"], raw["layout"]["patch_active"], strict=True
            )
        ]
    elif kind == "reference_density_gauge":
        result["reference_density_fmol_um2"] = [
            8.0 * value for value in raw["reference_density_fmol_um2"]
        ]
    elif kind == "charge_and_field_reversal":
        result["layout"]["effective_charge_e"] = [
            -value for value in raw["layout"]["effective_charge_e"]
        ]
        result["prescribed_potential_V"] = [-value for value in raw["prescribed_potential_V"]]
    elif kind == "edge_orientation":
        p = result["layout"]
        p["edge_sender"], p["edge_receiver"] = p["edge_receiver"], p["edge_sender"]
    else:
        raise ValueError("Unknown predeclared physical invariance")
    return result
