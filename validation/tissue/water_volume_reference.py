"""Independent closed-compartment osmotic water reference; no Cells/JAX imports.

Volumes are pL, amounts fmol, pressures Pa, energies pJ and time seconds.
Every listed solute contributes one ideal osmotic particle. Water carries no
solute. Areas, topology and the declared linear elastic law remain fixed.
"""

import math
from decimal import Decimal, localcontext

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

R = 6.02214076e23 * 1.380649e-23


def bind(case):
    """Validate an unpadded graph independently of production schemas."""
    c = dict(case)
    c["temperature_K"] = float(c["temperature_K"])
    c["gas_constant_J_per_mol_K"] = float(c.get("gas_constant_J_per_mol_K", R))
    if not all(
        math.isfinite(c[k]) and c[k] > 0 for k in ("temperature_K", "gas_constant_J_per_mol_K")
    ):
        raise ValueError("Temperature and gas constant must be positive and finite")
    for key in (
        "initial_volume_pL",
        "reference_volume_pL",
        "impermeant_amount_fmol",
        "bulk_modulus_Pa",
        "pressure_offset_Pa",
    ):
        c[key] = np.array(c[key], dtype=float, copy=True)
    n = c["initial_volume_pL"].size
    if n == 0:
        raise ValueError("Require at least one finite compartment")
    for key in (
        "initial_volume_pL",
        "reference_volume_pL",
        "impermeant_amount_fmol",
        "bulk_modulus_Pa",
        "pressure_offset_Pa",
    ):
        value = c[key]
        if value.shape != (n,) or not np.isfinite(value).all():
            raise ValueError("Invalid node vector: " + key)
        if key.endswith("volume_pL") and np.any(value <= 0):
            raise ValueError("Volumes must be strictly positive")
        if key in ("impermeant_amount_fmol", "bulk_modulus_Pa") and np.any(value < 0):
            raise ValueError("Osmolyte amounts and moduli must be nonnegative")
    amount = np.array(c["amount_fmol"], dtype=float, copy=True)
    if amount.size == 0:
        amount = np.empty((0, n))
    if (
        amount.ndim != 2
        or amount.shape[1] != n
        or not np.isfinite(amount).all()
        or np.any(amount < 0)
    ):
        raise ValueError("Amounts must be nonnegative species-by-node arrays")
    c["amount_fmol"] = amount
    c["edges"] = [dict(edge) for edge in c["edges"]]
    for edge in c["edges"]:
        if (
            type(edge["sender"]) is not int
            or type(edge["receiver"]) is not int
            or not 0 <= edge["sender"] < n
            or not 0 <= edge["receiver"] < n
            or edge["sender"] == edge["receiver"]
        ):
            raise ValueError("Require distinct valid edge owners")
        for key in ("area_m2", "hydraulic_permeability_m_per_Pa_s"):
            edge[key] = float(edge[key])
            if not math.isfinite(edge[key]) or edge[key] < 0:
                raise ValueError("Invalid water conductance")
        if edge["area_m2"] == 0:
            raise ValueError("A declared interface must have positive area")
    return c


def _volumes(c, volume):
    result = np.array(c["initial_volume_pL"] if volume is None else volume, dtype=float)
    if (
        result.shape != c["initial_volume_pL"].shape
        or not np.isfinite(result).all()
        or np.any(result <= 0)
    ):
        raise ValueError("Water reference requires positive finite volumes")
    return result


def evaluate(case, volume_pL=None, amount_fmol=None, *, precision=80):
    """Scalar Decimal pressure/flow/free-energy oracle on the positive-volume domain."""
    c = bind(case if amount_fmol is None else dict(case, amount_fmol=amount_fmol))
    volume = _volumes(c, volume_pL)
    if type(precision) is not int or precision < 30:
        raise ValueError("Reference precision must be an integer of at least 30 digits")
    d = lambda value: Decimal(str(float(value)))  # noqa: E731
    with localcontext() as context:
        context.prec = precision
        rt = d(c["gas_constant_J_per_mol_K"]) * d(c["temperature_K"])
        osmotic, pressure, chemical, elastic = [], [], [], []
        for i, vi in enumerate(volume):
            v, v0 = d(vi), d(c["reference_volume_pL"][i])
            amounts = [d(a[i]) for a in c["amount_fmol"]]
            amounts.append(d(c["impermeant_amount_fmol"][i]))
            osmotic.append(rt * sum(amounts) / v)
            k, p0 = d(c["bulk_modulus_Pa"][i]), d(c["pressure_offset_Pa"][i])
            pressure.append(k * (v / v0 - 1) + p0)
            chemical.append(
                Decimal("0.001") * rt * sum(a * ((a / v).ln() - 1) for a in amounts if a)
            )
            elastic.append(Decimal("0.001") * (k * (v - v0) ** 2 / (2 * v0) + p0 * (v - v0)))
        potential = [p - pi for p, pi in zip(pressure, osmotic, strict=True)]
        rate = [Decimal(0)] * len(volume)
        flux, heat, forces = [], [], []
        for edge in c["edges"]:
            a, b = edge["sender"], edge["receiver"]
            force = potential[a] - potential[b]
            flow = (
                Decimal("1e15")
                * d(edge["area_m2"])
                * d(edge["hydraulic_permeability_m_per_Pa_s"])
                * force
            )
            rate[a] -= flow
            rate[b] += flow
            flux.append(flow)
            forces.append(force)
            heat.append(Decimal("0.001") * flow * force)
        derivative = Decimal("0.001") * sum(p * v for p, v in zip(potential, rate, strict=True))
        return dict(
            volume_pL=volume,
            concentration_mM=c["amount_fmol"] / volume[None, :],
            impermeant_concentration_mM=c["impermeant_amount_fmol"] / volume,
            osmotic_pressure_Pa=np.asarray(osmotic, dtype=float),
            hydrostatic_pressure_Pa=np.asarray(pressure, dtype=float),
            water_potential_Pa=np.asarray(potential, dtype=float),
            edge_force_Pa=np.asarray(forces, dtype=float),
            edge_flow_pL_s=np.asarray(flux, dtype=float),
            volume_rate_pL_s=np.asarray(rate, dtype=float),
            mixing_energy_pJ=float(sum(chemical)),
            elastic_energy_pJ=float(sum(elastic)),
            free_energy_pJ=float(sum(chemical) + sum(elastic)),
            edge_dissipation_pJ_s=np.asarray(heat, dtype=float),
            free_energy_rate_pJ_s=float(derivative),
            energy_balance_pJ_s=float(derivative + sum(heat)),
            volume_balance_pL_s=float(sum(rate)),
        )


def integrate(case, times, *, refinement=1):
    """Independent DOP853 water-only history with fixed particle amounts."""
    c = bind(case)
    times = np.asarray(times, dtype=float)
    if (
        times.ndim != 1
        or times.size < 2
        or times[0] != 0
        or not np.isfinite(times).all()
        or np.any(np.diff(times) <= 0)
        or type(refinement) is not int
        or refinement < 1
    ):
        raise ValueError("Require increasing finite times from zero and positive refinement")
    n, e = len(c["initial_volume_pL"]), len(c["edges"])
    osmoles = np.asarray(
        [math.fsum([*c["amount_fmol"][:, i], c["impermeant_amount_fmol"][i]]) for i in range(n)]
    )
    rt = c["gas_constant_J_per_mol_K"] * c["temperature_K"]

    def rhs(_, y):
        v = _volumes(c, y[:n])
        potential = (
            c["bulk_modulus_Pa"] * (v / c["reference_volume_pL"] - 1)
            + c["pressure_offset_Pa"]
            - rt * osmoles / v
        )
        result = np.zeros(n + 2 * e)
        for j, edge in enumerate(c["edges"]):
            a, b = edge["sender"], edge["receiver"]
            force = potential[a] - potential[b]
            flow = 1e15 * edge["area_m2"] * edge["hydraulic_permeability_m_per_Pa_s"] * force
            result[a] -= flow
            result[b] += flow
            result[n + j] = flow
            result[n + e + j] = 1e-3 * flow * force
        return result

    initial = np.r_[c["initial_volume_pL"], np.zeros(2 * e)]
    solution = solve_ivp(
        rhs,
        (0.0, times[-1]),
        initial,
        method="DOP853",
        t_eval=times,
        rtol=1e-12 / refinement,
        atol=1e-13 / refinement,
        max_step=times[-1] / (32 * refinement),
    )
    if not solution.success:
        raise RuntimeError(solution.message)
    volumes = solution.y[:n].T
    energy = np.asarray([evaluate(c, v)["free_energy_pJ"] for v in volumes])
    return dict(
        times_s=times,
        volume_pL=volumes,
        concentration_mM=c["amount_fmol"][None, :, :] / volumes[:, None, :],
        edge_transferred_pL=solution.y[n : n + e].T,
        edge_dissipated_energy_pJ=solution.y[n + e :].T,
        free_energy_pJ=energy,
        evaluations=solution.nfev,
        refinement=refinement,
        method="independent scalar DOP853; Decimal free-energy readout",
    )


def two_compartment_equilibrium(case):
    """Unique zero-flow volume for one connected positive-osmole pair."""
    c = bind(case)
    if len(c["initial_volume_pL"]) != 2 or not any(
        edge["hydraulic_permeability_m_per_Pa_s"] > 0 for edge in c["edges"]
    ):
        raise ValueError("Require two connected compartments")
    osmoles = c["amount_fmol"].sum(axis=0) + c["impermeant_amount_fmol"]
    if np.any(osmoles <= 0):
        raise ValueError("This equilibrium bracket requires osmolytes on both sides")
    total = math.fsum(c["initial_volume_pL"])

    def difference(v):
        potential = evaluate(c, [v, total - v])["water_potential_Pa"]
        return potential[0] - potential[1]

    # Expand only the root-search bracket. No state or concentration is clipped.
    left, right = total / 4, 3 * total / 4
    while difference(left) > 0:
        previous, left = left, left / 2
        if left == 0 or previous == left:
            raise ValueError("Equilibrium is not resolved by positive float64 volumes")
    while difference(right) < 0:
        previous, right = right, (right + total) / 2
        if right == total or previous == right:
            raise ValueError("Equilibrium is not resolved by positive float64 volumes")
    v = brentq(difference, left, right, xtol=5e-15, rtol=1e-14)
    return np.asarray([v, total - v])


def exact_mechanical_pair(case, times):
    """Closed-form pure-water elastic relaxation, independent of ODE integration."""
    c = bind(case)
    if (
        len(c["initial_volume_pL"]) != 2
        or np.any(c["amount_fmol"])
        or np.any(c["impermeant_amount_fmol"])
    ):
        raise ValueError("Exact mechanical pair requires two solute-free compartments")
    total = math.fsum(c["initial_volume_pL"])
    k, v0, p0 = c["bulk_modulus_Pa"], c["reference_volume_pL"], c["pressure_offset_Pa"]
    slope = math.fsum(k / v0)
    if slope <= 0:
        raise ValueError("Require positive restoring stiffness")
    equilibrium = (k[0] - k[1] + k[1] * total / v0[1] - p0[0] + p0[1]) / slope
    if not 0 < equilibrium < total:
        raise ValueError("Declared pressures have no interior mechanical equilibrium")
    conductance = math.fsum(
        1e15 * e["area_m2"] * e["hydraulic_permeability_m_per_Pa_s"] for e in c["edges"]
    )
    first = equilibrium + (c["initial_volume_pL"][0] - equilibrium) * np.exp(
        -conductance * slope * np.asarray(times)
    )
    return np.stack([first, total - first], axis=-1)
