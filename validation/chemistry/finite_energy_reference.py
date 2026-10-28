"""Independent 80-digit finite-energy equations; no Cells, NumPy or JAX imports."""

from decimal import Decimal, localcontext
from numbers import Real

GAS_CONSTANT = Decimal("8.31446261815324")
STANDARD_STATE_mM = Decimal(1000)


def _d(value, name, *, positive=False, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        raise ValueError(name + " must be a finite number")
    result = Decimal(str(value))
    if not result.is_finite() or (positive and result <= 0) or (nonnegative and result < 0):
        raise ValueError("Invalid " + name)
    return result


def _thermodynamics(amount, volume, temperature, delta_g0, gas_constant):
    if len(amount) != 3:
        raise ValueError("Require ATP, ADP and Pi in declared order")
    n = [_d(v, "amount", positive=True) for v in amount]
    v = _d(volume, "volume", positive=True)
    t = _d(temperature, "temperature", positive=True)
    d = _d(delta_g0, "standard hydrolysis energy")
    r = _d(gas_constant, "gas constant", positive=True)
    if not 200 <= t <= 400:
        raise ValueError("Temperature outside component domain")
    rt = r * t
    concentrations = [a / v for a in n]
    standard = [-d, Decimal(0), Decimal(0)]
    mu = [
        s + rt * (c / STANDARD_STATE_mM).ln() for s, c in zip(standard, concentrations, strict=True)
    ]
    g = (
        d
        + rt
        * (concentrations[1] * concentrations[2] / (STANDARD_STATE_mM * concentrations[0])).ln()
    )
    free = sum(a * (u - rt) for a, u in zip(n, mu, strict=True)) / 1000
    return dict(
        concentration_mM=concentrations,
        chemical_potential_J_mol=mu,
        hydrolysis_free_energy_J_mol=g,
        free_energy_pJ=free,
        osmolyte_amount_fmol=sum(n),
        volume_derivative_pJ_per_pL=-rt * sum(n) / (1000 * v),
    )


def thermodynamics(amount, volume, temperature, delta_g0, gas_constant=GAS_CONSTANT):
    with localcontext() as context:
        context.prec = 80
        result = _thermodynamics(amount, volume, temperature, delta_g0, gas_constant)
        return {
            k: [float(v) for v in value] if isinstance(value, list) else float(value)
            for k, value in result.items()
        }


def free_energy_change(
    initial, final, initial_volume, final_volume, temperature, delta_g0, gas_constant=GAS_CONSTANT
):
    with localcontext() as context:
        context.prec = 80
        before = _thermodynamics(initial, initial_volume, temperature, delta_g0, gas_constant)
        after = _thermodynamics(final, final_volume, temperature, delta_g0, gas_constant)
        return float(after["free_energy_pJ"] - before["free_energy_pJ"])


def regeneration(
    amount,
    volume,
    temperature,
    delta_g0,
    capacity,
    supplied_energy,
    availability,
    gas_constant=GAS_CONSTANT,
):
    with localcontext() as context:
        context.prec = 80
        values = _thermodynamics(amount, volume, temperature, delta_g0, gas_constant)
        cap = _d(capacity, "capacity", nonnegative=True)
        work = _d(supplied_energy, "supplied energy", nonnegative=True)
        opening = _d(availability, "availability", nonnegative=True)
        if opening > 1:
            raise ValueError("Availability outside [0,1]")
        g = values["hydrolysis_free_energy_J_mol"]
        rt = _d(gas_constant, "gas constant", positive=True) * _d(temperature, "temperature")
        drive = g + work
        if abs(drive / rt) > 80:
            raise ValueError("Regeneration affinity outside numeric domain")
        exponent = (drive / rt).exp()
        cycles = cap * opening * (exponent - 1) / (exponent + 1)
        return dict(
            synthesis_fmol_s=float(cycles),
            reaction_free_energy_J_mol=float(-drive),
            supplied_power_pJ_s=float(cycles * work / 1000),
            dissipated_power_pJ_s=float(cycles * drive / 1000),
            pool_chemical_power_pJ_s=float(-cycles * g / 1000),
        )


def exchange(pump_cycles, pump_owners, synthesis_cycles, synthesis_owners, owner_count):
    """Scalar route-by-route material accounting, independent of array scatter."""
    with localcontext() as context:
        context.prec = 80
        demand = [Decimal(0)] * owner_count
        supply = [Decimal(0)] * owner_count
        hydrolysis = [Decimal(0)] * owner_count
        synthesis = [Decimal(0)] * owner_count
        for rates, owners, sign, totals in (
            (pump_cycles, pump_owners, 1, demand),
            (synthesis_cycles, synthesis_owners, -1, supply),
        ):
            for value, owner in zip(rates, owners, strict=True):
                if type(owner) is not int or not 0 <= owner < owner_count:
                    raise ValueError("Invalid energy route owner")
                value = _d(value, "signed cycles")
                totals[owner] += value
                hydrolysis[owner] += max(sign * value, 0)
                synthesis[owner] += max(-sign * value, 0)
        net = [d - s for d, s in zip(demand, supply, strict=True)]
        return dict(
            amount_fmol_s=[[float(sign * value) for value in net] for sign in (-1, 1, 1)],
            pump_hydrolysis_fmol_s=[float(v) for v in demand],
            regeneration_synthesis_fmol_s=[float(v) for v in supply],
            gross_hydrolysis_fmol_s=[float(v) for v in hydrolysis],
            gross_synthesis_fmol_s=[float(v) for v in synthesis],
        )
