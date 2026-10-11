"""Independent continuous coupled vector field, not a trajectory solver.

Only Decimal/math; neither engine, old comparator nor configuration compiler.
q_i is cumulative inward K transfer in fmol. The shared bath has ONE opposite
sum; each cell's capacitor voltage is derived from its own q_i, never clamped.
"""

import math
from decimal import Decimal, localcontext


def number(value):
    if type(value) not in (int, float, Decimal) or not math.isfinite(value):
        raise ValueError("Finite typed number required")
    return Decimal(str(value))


def rates(parameters, transfer, m_gate, h_gate):
    with localcontext() as context:
        context.prec = 80
        return _rates(parameters, transfer, m_gate, h_gate)


def _rates(p, transfer, m_gate, h_gate):
    n = len(p["volume_pL"])
    if n < 1 or any(
        len(v) != n
        for v in (
            transfer,
            m_gate,
            h_gate,
            p["area_m2"],
            p["initial_K_fmol"],
            p["initial_voltage_V"],
            p["channel_enabled"],
            p["Pmax_m_per_s"],
        )
    ):
        raise ValueError("Mismatched coupled axes")
    f, r, temperature = (number(p[k]) for k in ("F", "R", "temperature_K"))
    vo, outside0, cm = (
        number(p[k]) for k in ("outside_volume_pL", "outside_K_fmol", "cm_F_per_m2")
    )
    if min(f, r, temperature, vo, outside0, cm) <= 0 or temperature != Decimal("298.15"):
        raise ValueError("Invalid constants/temperature/bath/capacitance")
    q = list(map(number, transfer))
    outside = outside0 - sum(q, Decimal(0))
    if outside <= 0:
        raise ValueError("Nonpositive shared bath")
    co = outside / vo
    voltage, ci, flux, permeability, gate_rate, dissipation = [], [], [], [], [[], []], []
    for i in range(n):
        volume, area = number(p["volume_pL"][i]), number(p["area_m2"][i])
        amount, maximum = number(p["initial_K_fmol"][i]) + q[i], number(p["Pmax_m_per_s"][i])
        if (
            min(volume, area, amount) <= 0
            or maximum < 0
            or type(p["channel_enabled"][i]) is not bool
        ):
            raise ValueError("Invalid cell/channel parameters")
        m, h = number(m_gate[i]), number(h_gate[i])
        if not 0 <= m <= 1 or not 0 <= h <= 1:
            raise ValueError("Invalid gate state")
        v = number(p["initial_voltage_V"][i]) + q[i] * f * Decimal("1e-15") / (area * cm)
        if not Decimal("-0.12") <= v <= Decimal("0.06"):
            raise ValueError("Voltage outside declared kinetics domain")
        inside = amount / volume
        enabled = p["channel_enabled"][i]
        if not enabled and (m != 0 or h != 0 or maximum != 0):
            raise ValueError("Inactive channel carries state/permeability")
        mi = 1 / (1 + (-(v + Decimal("0.006")) / Decimal("0.0064")).exp())
        hi = 1 / (1 + ((v + Decimal("0.0253")) / Decimal("0.0035")).exp())
        tm, th = Decimal("0.008330") - Decimal("0.1163") * v, Decimal("1.620") - Decimal("15.5") * v
        effective = maximum * m * h
        x = f * v / (r * temperature)
        # This direct exponential form is evaluated with 80 digits, including
        # near-zero initial native charge residuals. No epsilon voltage mutation.
        density = (
            effective * (co - inside)
            if x == 0
            else effective * x * (co - inside * x.exp()) / (x.exp() - 1)
        )
        flow = area * Decimal("1e15") * density
        mu = r * temperature * (inside / co).ln() + f * v
        voltage.append(float(v))
        ci.append(float(inside))
        flux.append(float(flow))
        permeability.append(float(effective))
        gate_rate[0].append(float((mi - m) / tm) if enabled else 0.0)
        gate_rate[1].append(float((hi - h) / th) if enabled else 0.0)
        dissipation.append(float(-Decimal("0.001") * flow * mu))
    return {
        "voltage_V": voltage,
        "inside_K_mM": ci,
        "outside_K_mM": float(co),
        "gate_rate_per_s": gate_rate,
        "inward_K_fmol_per_s": flux,
        "outside_K_fmol_per_s": -math.fsum(flux),
        "permeability_m_per_s": permeability,
        "inward_current_A": [float(f * Decimal("1e-15") * number(v)) for v in flux],
        "dissipation_pJ_per_s": dissipation,
    }
