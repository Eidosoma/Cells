"""Alternate saved-reference algebra and explicit gate histories, never integration.

D099 checks references with D096's D094 field/direct basis/log-ratio work.
Here use the separately audited D093 field, nested basis and endpoint free energy.
Those formulations also underlie the saved reference generator: this is a
cross-check between existing formulations, not a third independent ODE solver.
"""

import math
from decimal import localcontext

import feedback_audit_math as base
import pilot_reference as field
from feedback_reference_check import dense_value, thermodynamic_dissipation

require, ind, ready = base.require, base.ind, base.ready
flat, component, unpack = base.flat, base.component, base.unpack
interval_transfer, Crosscheck = base.interval_transfer, base.Crosscheck
dense, dissipated = dense_value, thermodynamic_dissipation


def initial(p, gates):
    require(len(gates) == 2 and all(0 <= ind.finite(v) <= 1 for v in gates), "Gate fixture domain")
    n, active = len(p["volume_pL"]), sum(p["channel_enabled"])
    return [0.0] * n + [gates[0]] * active + [gates[1]] * active + [0.0] * n


def readout(p, state):
    q, m, h, energy = unpack(p, state)
    rates = field.rates(p, q, m, h)
    return {
        "gate": [m, h],
        "voltage_V": rates["voltage_V"],
        "cell_K_fmol": [a + b for a, b in zip(p["initial_K_fmol"], q, strict=True)],
        "bath_K_fmol": p["outside_K_fmol"] - math.fsum(q),
        "transfer_fmol": q,
        "flux_fmol_per_s": rates["inward_K_fmol_per_s"],
        "permeability_m_per_s": rates["permeability_m_per_s"],
        "inward_current_A": rates["inward_current_A"],
        "energy_pJ": energy,
    }


def analytic_gate(voltage, time_s, gates):
    require(ind.finite(time_s) >= 0, "Negative analytic clock")
    targets, taus = ind.kinetics(voltage)
    with localcontext() as context:
        context.prec = 80
        return [
            float(target + (ind.decimal(start) - target) * (-ind.decimal(time_s) / tau).exp())
            for target, tau, start in zip(targets, taus, gates, strict=True)
        ]


def subtract(left, right):
    if isinstance(left, list):
        require(isinstance(right, list) and len(left) == len(right), "Independent contrast axes")
        return [subtract(a, b) for a, b in zip(left, right, strict=True)]
    ind.finite(left)
    ind.finite(right)
    with localcontext() as context:
        context.prec = 80
        return float(ind.decimal(left) - ind.decimal(right))


def contrast(first, second):
    require(len(first) == len(second), "Independent contrast length")
    result = []
    for a, b in zip(first, second, strict=True):
        require(set(a) == set(b), "Independent contrast fields")
        result.append({field: subtract(a[field], b[field]) for field in a})
    return result
