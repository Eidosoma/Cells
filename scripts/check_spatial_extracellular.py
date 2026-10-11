"""SPEC-009 Decimal oracle versus NumPy arithmetic; prints evidence, never writes it.

The Decimal path assembles outside-node Kirchhoff equations directly, uses its
own elimination and GHK exponentials, and never calls the reference's flux,
incidence or potential routines. This is not an ODE or a spatial convergence test.
"""

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests import reference_spatial_extracellular as ref  # noqa: E402

PANEL = ROOT / "configs/reference/spatial_extracellular_v1.json"
SOURCES = (
    "docs/SPATIAL_EXTRACELLULAR_SPEC.md",
    "configs/reference/spatial_extracellular_v1.json",
    "tests/reference_spatial_extracellular.py",
    "tests/reference_multispecies.py",
    "tests/unit/test_spatial_extracellular_reference.py",
    "scripts/check_spatial_extracellular.py",
)
F = Decimal("6.02214076e23") * Decimal("1.602176634e-19")
R = Decimal("6.02214076e23") * Decimal("1.380649e-23")
A = Decimal("1e-15")
ZERO = Decimal(0)


def d(value):
    return Decimal(value) if type(value) is int else Decimal.from_float(float(value))


def elimination(matrix, vector):
    """Small high-precision row elimination; no NumPy/SciPy linear solver."""
    size = len(vector)
    rows = [list(row) + [value] for row, value in zip(matrix, vector, strict=True)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda i: abs(rows[i][column]))
        rows[column], rows[pivot] = rows[pivot], rows[column]
        assert rows[column][column] != 0, "Singular Decimal field constraint"
        divisor = rows[column][column]
        rows[column] = [v / divisor for v in rows[column]]
        for i in range(size):
            if i != column:
                multiplier = rows[i][column]
                rows[i] = [a - multiplier * b for a, b in zip(rows[i], rows[column], strict=True)]
    return [row[-1] for row in rows]


def decimal_evaluate(raw, delta, availability):
    owners, z = raw["compartments"], [d(v) for v in raw["valence"]]
    indices = {c["id"]: i for i, c in enumerate(owners)}
    outside = [i for i, c in enumerate(owners) if c["kind"] == "extracellular"]
    outside_index = {i: j for j, i in enumerate(outside)}
    rt = R * d(raw["temperature_K"])
    c = [
        [
            (d(n) + d(shift)) / d(owner["volume_pL"])
            for n, shift in zip(owner["initial_amount_fmol"], row, strict=True)
        ]
        for owner, row in zip(owners, delta, strict=True)
    ]
    matrix = [[ZERO for _ in outside] for _ in outside]
    rhs = [ZERO for _ in outside]
    faces = []
    for f in raw["faces"]:
        u, v = indices[f["left"]], indices[f["right"]]
        weights, logs = [], []
        for a, b, ds in zip(c[u], c[v], f["diffusivity_m2_per_s"], strict=True):
            log_ratio = a.ln() - b.ln()
            mean = a if a == b else (a - b) / log_ratio
            weights.append(d(ds) * d(f["area_m2"]) / d(f["length_m"]) * mean)
            logs.append(log_ratio)
        current = F * sum((s * w * log for s, w, log in zip(z, weights, logs, strict=True)), ZERO)
        conductance = F * F / rt * sum((s * s * w for s, w in zip(z, weights, strict=True)), ZERO)
        left, right = outside_index[u], outside_index[v]
        matrix[left][left] += conductance
        matrix[right][right] += conductance
        matrix[left][right] -= conductance
        matrix[right][left] -= conductance
        rhs[left] -= current
        rhs[right] += current
        faces.append((u, v, weights, logs))
    solution = [ZERO] + elimination([row[1:] for row in matrix[1:]], rhs[1:])
    phi = [ZERO for _ in owners]
    for i, value in zip(outside, solution, strict=True):
        phi[i] = value
    for m in raw["membranes"]:
        u, v = indices[m["inside"]], indices[m["outside"]]
        charge_shift = A * F * sum((s * d(n) for s, n in zip(z, delta[u], strict=True)), ZERO)
        phi[u] = phi[v] + d(m["initial_voltage_V"]) + charge_shift / d(m["capacitance_F"])
    shift = phi[-1]  # Same common gauge as the NumPy default.
    phi = [p - shift for p in phi]
    rates = [[ZERO for _ in z] for _ in owners]
    bulk_flux, membrane_flux, currents, dissipation, voltages = [], [], [], ZERO, []

    def scatter(u, v, flux, mu):
        for s, value in enumerate(flux):
            rates[u][s] -= value
            rates[v][s] += value
        return A * sum((j * m for j, m in zip(flux, mu, strict=True)), ZERO)

    for u, v, weights, logs in faces:
        mu = [rt * log + s * F * (phi[u] - phi[v]) for s, log in zip(z, logs, strict=True)]
        flux = [w / A * m / rt for w, m in zip(weights, mu, strict=True)]
        dissipation += scatter(u, v, flux, mu)
        bulk_flux.append(flux)
        currents.append(A * F * sum((s * j for s, j in zip(z, flux, strict=True)), ZERO))
    for m in raw["membranes"]:
        u, v = indices[m["inside"]], indices[m["outside"]]
        voltage = phi[u] - phi[v]
        voltages.append(voltage)
        mu, flux = [], []
        for s, ci, co, p in zip(z, c[u], c[v], m["permeability_m_per_s"], strict=True):
            x = s * F * voltage / rt
            numerator = ci - co if x == 0 else x * (ci * x.exp() - co) / (x.exp() - 1)
            flux.append(d(m["area_m2"]) * d(p) * d(availability) / A * numerator)
            mu.append(rt * (ci.ln() - co.ln()) + s * F * voltage)
        dissipation += scatter(u, v, flux, mu)
        membrane_flux.append(flux)
    charge_rate = [A * F * sum((s * j for s, j in zip(z, row, strict=True)), ZERO) for row in rates]
    chemical = (
        A
        * rt
        * sum(
            (
                n.ln() * j
                for row, change in zip(c, rates, strict=True)
                for n, j in zip(row, change, strict=True)
            ),
            ZERO,
        )
    )
    capacitor = sum(
        (
            voltage * charge_rate[indices[m["inside"]]]
            for m, voltage in zip(raw["membranes"], voltages, strict=True)
        ),
        ZERO,
    )

    def array(rows, columns=None):
        result = np.asarray(rows, dtype=float)
        return result if columns is None else result.reshape(-1, columns)

    return {
        "potential_V": array(phi),
        "membrane_voltage_V": array(voltages),
        "amount_rate_fmol_per_s": array(rates),
        "charge_rate_A": array(charge_rate),
        "membrane_flux_fmol_per_s": array(membrane_flux, len(z)),
        "face_flux_fmol_per_s": array(bulk_flux, len(z)),
        "face_current_A": array(currents),
        "stored_energy_rate_W": float(chemical + capacitor),
        "dissipation_W": float(dissipation),
    }


def probes(g):
    initial = np.zeros_like(g.initial)
    shifted = initial.copy()
    if g.membrane_pairs:
        u, v = g.membrane_pairs[0]
        shifted[u, 0] += 1e-6
        shifted[v, 0] -= 1e-6
    if g.face_pairs:
        u, v = g.face_pairs[0]
        positive = next(i for i, z in enumerate(g.z) if z > 0)
        negative = next(i for i, z in enumerate(g.z) if z < 0)
        for s, multiplier in ((positive, abs(g.z[negative])), (negative, abs(g.z[positive]))):
            shifted[u, s] -= 1e-3 * multiplier
            shifted[v, s] += 1e-3 * multiplier
    return (("initial", initial), ("owned_shift", shifted))


def run():
    panel = json.loads(PANEL.read_text())
    limits = panel["tolerances"]
    records, values_checked, max_error = [], 0, 0.0
    with localcontext() as ctx:
        ctx.prec = 70
        for raw in panel["cases"]:
            g = ref.resolve(raw)
            for state_id, delta in probes(g):
                for availability in (0.0, 0.35, 1.0) if g.membrane_pairs else (1.0,):
                    actual = ref.evaluate(g, delta, membrane_availability=availability)
                    oracle = decimal_evaluate(raw, delta, availability)
                    errors = {}
                    for key, wanted in oracle.items():
                        units = (
                            "voltage_V"
                            if key.endswith("_V")
                            else "current_A"
                            if key.endswith("_A")
                            else "power_W"
                            if key.endswith("_W")
                            else "flux_fmol_per_s"
                        )
                        scale = limits[units] + limits["rtol"] * np.abs(wanted)
                        error = np.abs(actual[key] - wanted) / scale
                        worst = float(np.max(error, initial=0))
                        assert worst <= 1, (raw["id"], state_id, availability, key, worst)
                        errors[key] = worst
                        max_error = max(max_error, worst)
                        values_checked += int(np.size(wanted))
                    assert actual["dissipation_W"] >= -limits["power_W"]
                    assert abs(actual["stored_energy_rate_W"] + actual["dissipation_W"]) <= (
                        limits["power_W"] + limits["rtol"] * abs(actual["dissipation_W"])
                    )
                    records.append(
                        {
                            "case": raw["id"],
                            "state": state_id,
                            "membrane_availability": availability,
                            "increment_fmol": delta.tolist(),
                            "maximum_normalized_errors": errors,
                            "reference": {
                                key: value.tolist() if isinstance(value, np.ndarray) else value
                                for key, value in actual.items()
                            },
                        }
                    )
    return {
        "schema": "cells.spatial_extracellular_design_check@1",
        "status": "pass",
        "scope": (
            "Instantaneous arithmetic only; not trajectory, mesh, biology or production acceptance"
        ),
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "decimal_digits": 70,
        },
        "case_count": len(panel["cases"]),
        "evaluations": len(records),
        "scalar_oracle_comparisons": values_checked,
        "maximum_normalized_error": max_error,
        "files_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES},
        "records": records,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify", type=Path, help="Read-only exact recomputation of saved evidence"
    )
    args = parser.parse_args()
    report = run()
    if args.verify:
        saved = json.loads(args.verify.read_text())
        for entry in (saved, report):
            entry.pop("captured_utc")
        assert saved == report, "Saved arithmetic evidence differs (excluding capture time)"
        print(
            json.dumps(
                {
                    "status": "pass",
                    "exact_replay": True,
                    "evaluations": report["evaluations"],
                    "scalar_oracle_comparisons": report["scalar_oracle_comparisons"],
                }
            )
        )
    else:
        print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
