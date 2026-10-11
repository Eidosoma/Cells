"""Independent saved-state algebra; stdlib and the already audited D094 math only.

No D095 oracle, comparator, integrator, Cells, BETSE, NumPy or JAX is imported.
"""

import hashlib
import json
import math
import struct
from decimal import Decimal, localcontext

import loop_independent as ind
import readiness_independent as ready

require = ind.require


def flat(value):
    if isinstance(value, list):
        for item in value:
            yield from flat(item)
    else:
        yield ind.finite(value)


def component(value, indices):
    for index in indices:
        require(isinstance(value, list), "Unexpected scalar axis")
        value = value[int(index)]
    return ind.finite(value)


def initial(p):
    n, active = len(p["volume_pL"]), sum(p["channel_enabled"])
    return [0.0] * n + [0.2] * active + [0.6] * active + [0.0] * n


def unpack(p, state):
    n = len(p["volume_pL"])
    active = [i for i, enabled in enumerate(p["channel_enabled"]) if enabled]
    require(len(state) == 2 * (n + len(active)), "Reference coordinate extent")
    require(all(math.isfinite(v) for v in flat(state)), "Nonfinite reference state")
    m, h = [0.0] * n, [0.0] * n
    for j, i in enumerate(active):
        m[i], h[i] = state[n + j], state[n + len(active) + j]
    return state[:n], m, h, state[n + 2 * len(active) :]


def readout(p, state):
    q, m, h, energy = unpack(p, state)
    rates = ready.vector_field(p, q, m, h)
    return {
        "gate": [m, h],
        "voltage_V": rates["voltage_V"],
        "cell_K_fmol": [n + dq for n, dq in zip(p["initial_K_fmol"], q, strict=True)],
        "bath_K_fmol": p["outside_K_fmol"] - math.fsum(q),
        "transfer_fmol": q,
        "flux_fmol_per_s": rates["inward_K_fmol_per_s"],
        "permeability_m_per_s": rates["permeability_m_per_s"],
        "inward_current_A": rates["inward_current_A"],
        "energy_pJ": energy,
    }


def dissipated(p, transfers):
    """Independent log-ratio free-energy change and expanded capacitor work."""
    with localcontext() as context:
        context.prec = 80
        d = ind.decimal
        q = [d(v) for v in transfers]
        chemical, electrical = Decimal(0), Decimal(0)
        initial_amounts = [*p["initial_K_fmol"], p["outside_K_fmol"]]
        volumes = [*p["volume_pL"], p["outside_volume_pL"]]
        for a, volume, change in zip(initial_amounts, volumes, [*q, -sum(q)], strict=True):
            a, volume = d(a), d(volume)
            require(min(a, a + change, volume) > 0, "Thermodynamic amount domain")
            chemical += (a + change) * ((a + change) / a).ln() + change * (a / volume).ln()
        for change, area, v0 in zip(q, p["area_m2"], p["initial_voltage_V"], strict=True):
            charge = change * d(p["F"]) * Decimal("1e-15")
            electrical += charge * d(v0) + charge**2 / (2 * d(area) * d(p["cm_F_per_m2"]))
        return float(
            -chemical * d(p["R"]) * d(p["temperature_K"]) * Decimal(".001")
            - electrical * Decimal("1e12")
        )


def dense(interval, time_s):
    """Direct polynomial-basis sum, independently of D095's nested DOP853 replay."""
    left, right = interval["left_s"], interval["right_s"]
    require(left <= time_s <= right and left < right, "Dense time domain")
    x, start, coefficients = (
        (time_s - left) / (right - left),
        interval["y_left"],
        interval["coefficients"],
    )
    if interval["method"] == "DOP853":
        require(
            len(coefficients) == 7 and all(len(row) == len(start) for row in coefficients),
            "DOP853 polynomial axes",
        )
        basis = [x ** (k // 2 + 1) * (1 - x) ** ((k + 1) // 2) for k in range(7)]
        return [
            v + math.fsum(coefficients[k][i] * basis[k] for k in range(7))
            for i, v in enumerate(start)
        ]
    require(
        interval["method"] == "Radau" and len(coefficients) == len(start), "Radau polynomial axes"
    )
    require(all(len(row) == 3 for row in coefficients), "Radau coefficient extent")
    return [
        v + x * (row[0] + x * (row[1] + x * row[2]))
        for v, row in zip(start, coefficients, strict=True)
    ]


def analytic_gate(voltage, time_s):
    targets, taus = ind.kinetics(voltage)
    with localcontext() as context:
        context.prec = 80
        return [
            float(target + (ind.decimal(start) - target) * (-ind.decimal(time_s) / tau).exp())
            for target, tau, start in zip(targets, taus, (0.2, 0.6), strict=True)
        ]


def interval_transfer(points, index):
    require(index > 0, "No interval before the initial observation")
    return [
        a - b
        for a, b in zip(
            points[index]["transfer_fmol"], points[index - 1]["transfer_fmol"], strict=True
        )
    ]


class Crosscheck:
    """Streaming identities and all mismatches; no multi-million-row RAM ledger."""

    def __init__(self, path=None):
        self.path = path
        self.count = self.failed = self.numerical_rejections = 0
        self.maximum = 0.0
        self.digest = hashlib.sha256()
        self.failures = []

    def add(
        self,
        name,
        actual,
        expected,
        independent_actual,
        independent_expected,
        unit,
        absolute,
        relative,
    ):
        values = tuple(
            map(ind.finite, (actual, expected, independent_actual, independent_expected))
        )
        self.digest.update(
            name.encode() + b"\0" + unit.encode() + b"\0" + struct.pack("<4d", *values)
        )
        self.count += 1
        independent_rejected = (
            ind.scaled(independent_actual, independent_expected, absolute, relative) > 1
        )
        original_rejected = ind.scaled(actual, expected, absolute, relative) > 1
        self.numerical_rejections += independent_rejected
        error = max(
            ind.scaled(actual, independent_actual, absolute, relative),
            ind.scaled(expected, independent_expected, absolute, relative),
        )
        self.maximum = max(self.maximum, error)
        if error > 1 or independent_rejected != original_rejected:
            self.failed += 1
            row = {
                "id": name,
                "actual": actual,
                "expected": expected,
                "independent_actual": independent_actual,
                "independent_expected": independent_expected,
                "unit": unit,
                "scaled_column_error": error,
                "classification_changed": independent_rejected != original_rejected,
            }
            if self.path is None:
                self.failures.append(row)
            else:
                with self.path.open("a") as stream:
                    stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")

    def summary(self):
        return {
            "identities": self.count,
            "column_mismatches": self.failed,
            "independent_numerical_rejections": self.numerical_rejections,
            "maximum_column_scaled_error": self.maximum,
            "identity_stream_sha256": self.digest.hexdigest(),
        }
