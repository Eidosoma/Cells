"""Explicit post-flux snapshots; these are not evolved native trajectories."""

from validation.betse.betse_fast_solver_fixtures import fixture as geometry_fixture

CASES = (
    "standard",
    "multivalent",
    "neutral",
    "cancellation",
    "area_mismatch",
    "sharpness_large",
    "permuted",
    "inward_sign",
)


def fixture(case="standard"):
    if case not in CASES:
        raise ValueError("Require a declared normal-current snapshot case")
    base = geometry_fixture("no_ecm")["definition"]["geometry"]
    g = {
        key: base[key]
        for key in (
            "cell_ids",
            "membrane_ids",
            "owner",
            "membrane_area_m2",
            "cell_area_m2",
            "normal_xy",
        )
    }
    g["cell_area_m2"] = [
        sum(g["membrane_area_m2"][j] for j, a in enumerate(g["owner"]) if a == i) for i in range(3)
    ]
    if case == "area_mismatch":
        g["cell_area_m2"] = [
            value * factor for value, factor in zip(g["cell_area_m2"], (1.1, 0.8, 1.3), strict=True)
        ]
    ids, z = (
        (["Ca", "Cl", "neutral"], [2.0, -1.0, 0.0])
        if case == "multivalent"
        else (["Na", "K", "Cl", "P"], [1.0, 1.0, -1.0, -1.0])
    )
    if case == "neutral":
        ids, z = ["neutral"], [0.0]
    raw = dict(
        kind="cells.betse_normal_current_inputs@1",
        provenance=(
            "Explicit post-commit bulk and full face-flux snapshots with native source signs"
        ),
        geometry=g,
        ions=dict(ids=ids, valence=z),
        parameters=dict(F_C_mol=96485.0, sharpness_cell=8.0 if case == "sharpness_large" else 0.5),
    )
    snapshots = []
    for tick in range(3):
        cell = [[13.0 + 17 * i + 2 * j + 0.2 * tick for j in range(3)] for i in range(len(ids))]
        membrane = [
            [(i + 1) * (j - 3) * 1e-7 * (1 + 0.05 * tick) for j in range(9)]
            for i in range(len(ids))
        ]
        gap = [
            [(i + 2) * (4 - j) * 1e-7 * (1 + 0.04 * tick) for j in range(9)]
            for i in range(len(ids))
        ]
        extra_rho = [(j - 1) * 0.002 for j in range(3)]
        extra_current = [(j - 4) * 0.0002 for j in range(9)]
        if case == "cancellation":
            cell = [[1e5 + 13 * i + 2 * j + 0.2 * tick for j in range(3)] for i in range(len(ids))]
            extra_rho = [
                -sum(zz * 96485.0 * cell[i][j] for i, zz in enumerate(z)) + 1e-10 for j in range(3)
            ]
            extra_current = [
                sum(zz * 96485.0 * (membrane[i][j] - gap[i][j]) for i, zz in enumerate(z)) + 1e-20
                for j in range(9)
            ]
        if case == "inward_sign":
            membrane = [[1e-7 if i == 0 else 0.0 for _ in range(9)] for i in range(len(ids))]
            gap = [[0.0] * 9 for _ in ids]
            extra_rho = [0.0] * 3
            extra_current = [0.0] * 9
        snapshots.append(
            dict(
                cell_mol_m3=cell,
                membrane_flux_mol_m2_s=membrane,
                junction_flux_mol_m2_s=gap,
                extra_charge_C_m3=extra_rho,
                extra_current_A_m2=extra_current,
            )
        )
    if case == "permuted":
        order = list(reversed(range(9)))
        for key in ("membrane_ids", "owner", "membrane_area_m2", "normal_xy"):
            g[key] = [g[key][j] for j in order]
        for frame in snapshots:
            for key in ("membrane_flux_mol_m2_s", "junction_flux_mol_m2_s"):
                frame[key] = [[row[j] for j in order] for row in frame[key]]
            frame["extra_current_A_m2"] = [frame["extra_current_A_m2"][j] for j in order]
    return dict(definition=raw, snapshots=snapshots)
