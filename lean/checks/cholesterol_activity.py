"""Compare the bulk mixing curves with Shaw et al., Fig. 2A / Table S1."""

import json
from pathlib import Path

import numpy as np

from validation.assembly_lineages_v2.probes import rate_table

TABLE = Path(__file__).with_name("data") / "shaw2023_dopc.json"
SATURATION = TABLE.with_name("parker2004_dopc_saturation.json")


def fit(rows, regular, weighted):
    x, dx, activity, da = rows.T
    # ln(A/x) = ln(s) + χ (1-x)². The crystal reference leaves s free.
    columns = [np.ones_like(x)]
    if regular:
        columns.append((1 - x) ** 2)
    design = np.column_stack(columns)
    y = np.log(activity / x)
    params = np.linalg.lstsq(design, y, rcond=None)[0]
    if weighted:
        # Sensitivity only. First-order propagation at the unweighted parameters
        # uses both printed half-widths and assumes zero unreported covariance.
        chi = params[1] if regular else 0.0
        width = np.hypot(da / activity, (1 / x - 2 * chi * (1 - x)) * dx)
        params = np.linalg.lstsq(design / width[:, None], y / width, rcond=None)[0]
    return float(params[0]), float(params[1]) if regular else 0.0


def compare(ideal_spec, regular_spec, names):
    """Use the actual multinomial ledger at N=1000 as a finite-count cross-check."""
    data = json.loads(TABLE.read_text())
    rows = np.array(data["rows"], dtype=float)
    rows[:, :2] /= 100  # Both composition columns are percentages in the supplement.
    x, _, observed, _ = rows.T
    levels = np.unique(x)
    external = json.loads(SATURATION.read_text())
    onset = external["chol_mole_fraction_at_crystal_onset"]
    spread = external["reported_plus_minus_mole_fraction"]
    onset_points = np.array([onset - spread, onset, onset + spread])
    total = 1000  # Every tabulated composition is exactly representable in this probe.
    a = np.rint(x * total).astype(int)
    np.testing.assert_allclose(a / total, x, rtol=0, atol=1e-15)
    states = np.zeros((len(rows), 2, len(names)), dtype=int)
    states[:, :, names.index("A@membrane")] = a[:, None] + [0, 1]
    states[:, :, names.index("B@membrane")] = (total - a)[:, None]
    energies = []
    for spec in (ideal_spec, regular_spec):
        _, _, free = rate_table(spec, names, states.reshape(-1, len(names)))
        energies.append(np.diff(free.reshape(-1, 2), axis=1).ravel())
    finite_activity = np.exp(energies[0])
    finite_excess = energies[1] - energies[0]  # χ_AB = 1 in ol1_wa.
    np.testing.assert_allclose(finite_activity, (a + 1) / (total + 1), rtol=0, atol=1e-10)
    np.testing.assert_allclose(
        finite_excess, (total - a) ** 2 / (total * (total + 1)), rtol=0, atol=1e-10
    )

    report = {
        "dataset": data["dataset_id"],
        "rows": len(x),
        "distinct_compositions": len(levels),
        "external_dataset": external["dataset_id"],
        "external_onset_mole_fractions": onset_points.tolist(),
    }
    for model in ("ideal", "regular"):
        regular = model == "regular"
        model_result = {}
        for weighted in (False, True):
            bulk, finite = np.empty_like(x), np.empty_like(x)
            for level in levels:
                held = x == level  # Group rows with the same printed, extracted composition.
                offset, chi = fit(rows[~held], regular, weighted)
                bulk[held] = x[held] * np.exp(offset + chi * (1 - x[held]) ** 2)
                finite[held] = finite_activity[held] * np.exp(offset + chi * finite_excess[held])
            offset, chi = fit(rows, regular, weighted)
            worst = int(np.argmax(np.abs(bulk - observed)))
            result = {
                "all_rows_scale": float(np.exp(offset)),
                "all_rows_chi_kT": chi,
                "activity_at_external_onset_low_center_high": (
                    onset_points * np.exp(offset + chi * (1 - onset_points) ** 2)
                ).tolist(),
                "held_composition_rmse_activity": float(np.sqrt(np.mean((bulk - observed) ** 2))),
                "max_abs_finite_N1000_minus_bulk_activity": float(np.max(np.abs(finite - bulk))),
                "largest_error": {
                    "mol_percent": data["rows"][worst][0],
                    "observed": float(observed[worst]),
                    "predicted": float(bulk[worst]),
                },
            }
            model_result["two_axis_sensitivity" if weighted else "unweighted"] = result
        report[model] = model_result
    return report
