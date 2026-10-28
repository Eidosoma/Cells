"""Independent scalar eighty-digit native Mito timing, flux and amount oracle.

No production Cells, NumPy or JAX imports. Explicit modern-constant overrides
remain inputs; default constants preserve the pinned parameters.py values.
"""

from copy import deepcopy
from decimal import Decimal, localcontext
from numbers import Real

NONCE = Decimal("1e-25")


def number(value, *, nonnegative=False, positive=False):
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        raise ValueError("Require real mitochondrial inputs")
    result = Decimal(str(value))
    if not result.is_finite() or (nonnegative and result < 0) or (positive and result <= 0):
        raise ValueError("Invalid mitochondrial input domain")
    return result


def geometry(raw):
    """Native init uses half geometry and the full supplied cytosolic volume."""
    with localcontext() as context:
        context.prec = 80
        volume = [number(v, positive=True) for v in raw["cell_volume_m3"]]
        area = [number(v, positive=True) for v in raw["cell_area_m2"]]
        cm = number(raw["specific_capacitance_F_m2"], positive=True)
        return dict(
            cytosol_volume_m3=[float(v) for v in volume],
            mitochondria_volume_m3=[float(v / 2) for v in volume],
            mitochondria_area_m2=[float(a / 2) for a in area],
            capacitance_F=[float(a * cm / 2) for a in area],
        )


def charge(concentrations, z, volume, extra, faraday):
    return [
        faraday
        * v
        * sum(
            (row[j] * number(valence) for row, valence in zip(concentrations, z, strict=True)),
            Decimal(0),
        )
        + extra[j] * v
        for j, v in enumerate(volume)
    ]


def evaluate(raw):
    with localcontext() as context:
        context.prec = 80
        cy = [[number(v, nonnegative=True) for v in row] for row in raw["cytosol_mM"]]
        mi = [[number(v, nonnegative=True) for v in row] for row in raw["mitochondria_mM"]]
        z, moving = raw["species_valence"], raw["moving_species"]
        count = len(raw["cell_volume_m3"])
        mito_volume = [number(v, positive=True) / 2 for v in raw["cell_volume_m3"]]
        cy_volume = [
            number(v, positive=True)
            for v in raw.get("live_cytosol_volume_m3", raw["cell_volume_m3"])
        ]
        area = [number(v, positive=True) / 2 for v in raw["cell_area_m2"]]
        cap = [a * number(raw["specific_capacitance_F_m2"], positive=True) for a in area]
        extra = [number(v) for v in raw["extra_charge_density_C_m3"]]
        f, r, temp = (
            number(raw[key], positive=True)
            for key in ("faraday_C_mol", "gas_constant_J_mol_K", "temperature_K")
        )
        dt, thickness = (
            number(raw["dt_s"], nonnegative=True),
            number(raw["membrane_thickness_m"], positive=True),
        )
        cached = [number(v) for v in raw["charge_C"]]
        voltage = [number(v) for v in raw["voltage_V"]]
        before = charge(mi, z, mito_volume, extra, f)
        if raw.get("refresh_before"):
            cached = before.copy()
            voltage = [q / c for q, c in zip(cached, cap, strict=True)]
        fluxes = [[Decimal(0)] * count for _ in z]
        transferred = deepcopy(fluxes)
        used = []
        for species in moving:
            voltage = [v + NONCE for v in voltage]
            used.append([float(v) for v in voltage])
            for j in range(count):
                alpha = (number(z[species]) + NONCE) * voltage[j] * f / (r * temp)
                if not alpha:
                    raise ValueError("Native nonce-shifted alpha=0 singularity")
                exponential = (-alpha).exp()
                d = number(
                    raw.get("diffusivity_m2_s", [[1e-19] * count for _ in z])[species][j],
                    nonnegative=True,
                )
                flux = -(d * alpha / thickness) * (
                    (mi[species][j] - cy[species][j] * exponential) / (1 - exponential)
                )
                fluxes[species][j] = flux
                transferred[species][j] = flux * area[j] * dt / Decimal("1e-15")
                cy[species][j] -= flux * area[j] / cy_volume[j] * dt
                mi[species][j] += flux * area[j] / mito_volume[j] * dt
        after = charge(mi, z, mito_volume, extra, f)
        final_voltage = [q / c for q, c in zip(after, cap, strict=True)]
        return dict(
            cytosol_mM=[[float(v) for v in row] for row in cy],
            mitochondria_mM=[[float(v) for v in row] for row in mi],
            charge_C=[float(v) for v in after],
            voltage_V=[float(v) for v in final_voltage],
            flux_density_mol_m2_s=[[float(v) for v in row] for row in fluxes],
            transferred_fmol=[[float(v) for v in row] for row in transferred],
            voltage_used_V=used,
            physical_charge_before_C=[float(v) for v in before],
            cache_charge_adjustment_C=[float(a - b) for a, b in zip(before, cached, strict=True)],
        )


def neutral_profile(raw, times):
    """Exact finite-volume neutral diffusion, at the native physical rate."""
    with localcontext() as context:
        context.prec = 80
        vc = number(raw["cell_volume_m3"][0], positive=True)
        vm = vc / 2
        area = number(raw["cell_area_m2"][0], positive=True) / 2
        d = Decimal("1e-19")
        conductance = d * area / number(raw["membrane_thickness_m"], positive=True)
        rate = conductance * (1 / vc + 1 / vm)
        ci, cm = number(raw["cytosol_mM"][0][0]), number(raw["mitochondria_mM"][0][0])
        equilibrium = (vc * ci + vm * cm) / (vc + vm)
        values = []
        for time in times:
            decay = (-rate * number(time, nonnegative=True)).exp()
            difference = (ci - cm) * decay
            values.append(
                [
                    float(equilibrium + vm / (vc + vm) * difference),
                    float(equilibrium - vc / (vc + vm) * difference),
                ]
            )
        return dict(
            tau_s=float(1 / rate),
            horizon_s=float(12 / rate),
            equilibrium_mM=float(equilibrium),
            concentration_mM=values,
        )
