"""Independent scalar/80-digit Decimal cotransport; no Cells/NumPy/JAX imports."""

from decimal import Decimal, localcontext
from numbers import Real

GAS_CONSTANT = Decimal("8.31446261815324")
FARADAY = Decimal("96485.3321233100184")


def _d(value, name, *, positive=False, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        raise ValueError(name + " requires a real number")
    result = Decimal(str(value))
    if not result.is_finite() or (positive and result <= 0) or (nonnegative and result < 0):
        raise ValueError("Invalid " + name)
    return result


def _substrates(inside, outside, coefficients):
    if not inside or len(inside) != len(outside) or len(inside) != len(coefficients):
        raise ValueError("Explicit matching species lists required")
    if any(type(n) is not int or n < 0 or n > 2 for n in coefficients) or not any(coefficients):
        raise ValueError("Invalid symport stoichiometry")
    return (
        [_d(v, "inside concentration", positive=True) for v in inside],
        [_d(v, "outside concentration", positive=True) for v in outside],
    )


def cycle(inside, outside, coefficients, capacity, availability, temperature):
    """Independent concentration products and exponential quotient, not tanh."""
    with localcontext() as context:
        context.prec = 80
        ci, co = _substrates(inside, outside, coefficients)
        cap = _d(capacity, "capacity", nonnegative=True)
        opening = _d(availability, "availability", nonnegative=True)
        temp = _d(temperature, "temperature", positive=True)
        if opening > 1 or not 200 <= temp <= 400:
            raise ValueError("Availability or temperature outside declared domain")
        product_in, product_out = Decimal(1), Decimal(1)
        for inside_value, outside_value, n in zip(ci, co, coefficients, strict=True):
            product_in *= inside_value**n
            product_out *= outside_value**n
        ratio = product_out / product_in
        reduced = ratio.ln()
        affinity = GAS_CONSTANT * temp * reduced
        cycles = cap * opening * (ratio - 1) / (ratio + 1)
        heat = cycles * affinity / 1000
        return dict(
            cycle_fmol_s=float(cycles),
            affinity_J_mol=float(affinity),
            reaction_free_energy_J_mol=float(-affinity),
            transported_fmol_s=[float(n * cycles) for n in coefficients],
            dissipated_power_pJ_s=float(heat),
            chemical_power_pJ_s=float(-heat),
            direct_charge_C_s=0.0,
        )


def exchange(cycles, inside, outside, coefficients, compartment_count):
    """Explicit route/species loops and Decimal accumulation."""
    if len(cycles) != len(inside) or len(cycles) != len(outside):
        raise ValueError("Route ownership mismatch")
    if type(compartment_count) is not int or compartment_count < 1:
        raise ValueError("Invalid compartment count")
    with localcontext() as context:
        context.prec = 80
        result = [[Decimal(0)] * compartment_count for _ in coefficients]
        for route, value in enumerate(cycles):
            i, o = inside[route], outside[route]
            if any(type(v) is not int or not 0 <= v < compartment_count for v in (i, o)):
                raise ValueError("Invalid owner")
            v = _d(value, "signed cycles")
            for species, nu in enumerate(coefficients):
                n = _d(nu[route], "coefficient", nonnegative=True)
                result[species][i] += n * v
                result[species][o] -= n * v
        return [[float(v) for v in row] for row in result]


def chemical_free_energy_change(initial, current, volumes, temperature):
    """Ideal fixed-volume ionic free energy, in pJ, evaluated before subtraction."""
    with localcontext() as context:
        context.prec = 80
        rt = GAS_CONSTANT * _d(temperature, "temperature", positive=True)
        v = [_d(x, "volume", positive=True) for x in volumes]
        totals = []
        for amounts in (initial, current):
            total = Decimal(0)
            for row in amounts:
                if len(row) != len(v):
                    raise ValueError("Amount/volume ownership mismatch")
                for value, volume in zip(row, v, strict=True):
                    n = _d(value, "amount", positive=True)
                    total += rt * n * ((n / (1000 * volume)).ln() - 1) / 1000
            totals.append(total)
        return float(totals[1] - totals[0])


def betse_generic_density(
    inside,
    outside,
    coefficients,
    km_reactants,
    max_flux_mol_m2_s,
    availability=1.0,
    rho=1.0,
    temperature=298.15,
    standard_free_energy=0.0,
):
    """Separate generic-source oracle; positive is configured inward transfer.

    This is not the manufactured tanh kernel. It covers a configured neutral
    symport with no influencers and zero electrical transfer energy. None is
    the source's irreversible branch. Product-side Km does not enter its
    generated executable expression. Geometry/integration are not emulated.
    """
    with localcontext() as context:
        context.prec = 80
        ci, co = _substrates(inside, outside, coefficients)
        if len(km_reactants) != len(ci):
            raise ValueError("Km/species mismatch")
        forward, quotient = Decimal(1), Decimal(1)
        for inside_value, outside_value, n, km in zip(
            ci, co, coefficients, km_reactants, strict=True
        ):
            k = _d(km, "reactant Km", positive=True)
            loading = (outside_value / k) ** n
            forward *= loading / (1 + loading)
            quotient *= (inside_value / outside_value) ** n
        reverse_factor = Decimal(1)
        if standard_free_energy is not None:
            rt = GAS_CONSTANT * _d(temperature, "temperature", positive=True)
            keq = (-_d(standard_free_energy, "standard energy") / rt).exp()
            reverse_factor -= quotient / keq
        return float(
            _d(max_flux_mol_m2_s, "maximum flux", nonnegative=True)
            * _d(availability, "availability", nonnegative=True)
            * _d(rho, "rho", nonnegative=True)
            * forward
            * reverse_factor
        )
