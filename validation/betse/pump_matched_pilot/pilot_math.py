"""Explicit comparison coordinates and ledgers; no model imports."""

import math

import pilot_context as ctx

c = ctx.c


def flat(value):
    if isinstance(value, list):
        for x in value:
            yield from flat(x)
    else:
        yield value


def canonical(state, n=7):
    return (
        [float(state["amount_increment"][s][i]) for i in range(n) for s in range(3)]
        + [float(state["extracellular_amount_increment"][s][0]) for s in range(3)]
        + [float(state["leak_transferred"][s][i]) for i in range(n) for s in range(3)]
        + list(map(float, state["pump_cycles"][:n]))
        + list(map(float, state["dissipated_energy_pJ"][:n]))
    )


class Ledger:
    def __init__(self):
        self.comparisons = 0
        self.maxima = {}

    def compare(self, name, actual, expected, atol, rtol=0.0):
        a, b = list(flat(actual)), list(flat(expected))
        c.require(len(a) == len(b), "Wrong comparison extent: " + name)
        for x, y in zip(a, b, strict=True):
            c.require(math.isfinite(x) and math.isfinite(y), "Nonfinite comparison")
            error = abs(x - y)
            c.require(error <= atol + rtol * abs(y), "Pilot mismatch: " + name)
            self.maxima[name] = max(self.maxima.get(name, 0.0), error)
            self.comparisons += 1


def native_rates(row, variant, raw):
    """Integrate applied face densities; the third pump return is not ATP."""
    g = row["geometry"]
    n, m = g["cell_count"], g["membrane_count"]
    leak = [[0.0] * n for _ in range(3)]
    cycles = [0.0] * n
    for call in raw["calls"]:
        for face in range(m):
            if not variant["cluster_open"] and face in g["boundary_faces"]:
                continue
            i = g["membrane_owners"][face]
            factor = g["membrane_areas_m2"][face] * 1e15
            if call["function"] == "pumpNaKATP":
                cycles[i] += -call["returned"][0][face] / 3 * factor * variant["rho_pump"]
            elif call["species_index"] < 3:
                leak[call["species_index"]][i] += call["returned"][face] * factor
    p = raw["before"]["physical"]
    params = row["settings"]["pump_parameters"]
    rt = ctx.R * row["settings"]["temperature_K"]
    drive = params["deltaGATP"] + rt * math.log(
        params["cADP"] * params["cPi"] / (1000 * params["cATP"])
    )
    v = ctx.owners(p["voltage_V"], g)
    diss = []
    for i in range(n):
        mu = [
            rt * math.log(p["inside_mM"][s][i] / p["outside_mM"][s][0])
            + (1, 1, -1)[s] * ctx.F * v[i]
            for s in range(3)
        ]
        affinity = drive - 3 * mu[0] + 2 * mu[1]
        diss.append(
            -0.001 * (math.fsum(leak[s][i] * mu[s] for s in range(3)) + cycles[i] * affinity)
        )
    amounts = [[leak[s][i] + (-3, 2, 0)[s] * cycles[i] for s in range(3)] for i in range(n)]
    return (
        [x for row_ in amounts for x in row_]
        + [-math.fsum(row_[s] for row_ in amounts) for s in range(3)]
        + [leak[s][i] for i in range(n) for s in range(3)]
        + cycles
        + diss
    )


def native_state(row, index, accumulated):
    g = row["geometry"]
    initial = row["trace"]["initial"]["physical"]
    p = initial if index == 0 else row["trace"]["steps"][index - 1]["after_voltage"]["physical"]
    n = g["cell_count"]
    q = [
        (p["inside_mM"][s][i] - initial["inside_mM"][s][i]) * g["cell_volumes_m3"][i] * 1e15
        for i in range(n)
        for s in range(3)
    ]
    q += [
        (ctx.uniform(p["outside_mM"][s]) - initial["outside_mM"][s][0])
        * g["effective_bath_volume_m3"]
        * 1e15
        for s in range(3)
    ]
    return q + accumulated[3 * n + 3 :], ctx.owners(p["voltage_V"], g)


def contraction(errors, floor, ratio):
    c.require(
        len(errors) == 3 and all(math.isfinite(v) and v >= 0 for v in errors),
        "Refinement error vector",
    )
    for coarse, fine in zip(errors[:-1], errors[1:], strict=True):
        c.require(coarse <= floor or fine <= ratio * coarse, "Refinement did not contract")
    return dict(
        errors=errors, floor=floor, roundoff_or_reference_limited=all(v <= floor for v in errors)
    )
