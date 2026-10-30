"""Independent SI ideal-protein endpoint functionals; no Cells/JAX imports.

640-digit direct absolute endpoint energies use the supplied m3 volumes and
mol/m3 stocks, with exact-float Decimal products/sums at4096digits. Neither
production pivot formulas nor production material normalization is consumed.
"""

from decimal import Context, Decimal, localcontext
from functools import lru_cache

import numpy as np


def _d(value):
    return Decimal.from_float(float(value))


@lru_cache(maxsize=512)
def _log_ratio(c, c0):
    with localcontext(Context(prec=640)):
        return (_d(c) / _d(c0)).ln()


def change(
    reference_protein,
    current_protein,
    cell_volume_m3,
    environment_volume_m3,
    *,
    temperature_K,
    standard_concentration_mol_m3,
    gas_constant_J_mol_K,
):
    frame = (temperature_K, standard_concentration_mol_m3, gas_constant_J_mol_K)
    if any(not np.isfinite(value) or value <= 0 for value in frame):
        raise ValueError("Independent explicit positive finite SI chemical frame required")
    answer, all_energy, deltas = {}, [], []
    with localcontext(Context(prec=4096)):
        rt = _d(temperature_K) * _d(gas_constant_J_mol_K)
        for domain, field, volumes in (
            ("cell", "cell_mol_m3", cell_volume_m3),
            ("environment", "environment_mol_m3", environment_volume_m3),
        ):
            before, after, volume = (
                np.asarray(a) for a in (reference_protein[field], current_protein[field], volumes)
            )
            if (
                before.ndim != 1
                or before.shape != after.shape
                or before.shape != volume.shape
                or not all(np.isfinite(a).all() for a in (before, after, volume))
                or np.any(before < 0)
                or np.any(after < 0)
                or np.any(volume <= 0)
            ):
                raise ValueError("Independent complete physical owner mismatch/domain")
            energies, potentials_before, potentials_after = [], [], []
            for b, e, v in zip(before, after, volume, strict=True):
                values = []
                potentials = []
                for c in (b, e):
                    n = _d(c) * _d(v)
                    log = (
                        Decimal(0)
                        if c == 0
                        else _log_ratio(float(c), float(standard_concentration_mol_m3))
                    )
                    values.append(Decimal(0) if c == 0 else Decimal("1e12") * rt * n * (log - 1))
                    potentials.append(Decimal("-Infinity") if c == 0 else rt * log)
                energies.append(values[1] - values[0])
                potentials_before.append(float(potentials[0]))
                potentials_after.append(float(potentials[1]))
                deltas.append((_d(e) - _d(b)) * _d(v))
            answer[domain + "_free_energy_change_pJ"] = [float(value) for value in energies]
            answer[domain + "_free_energy_change_pJ_exact"] = [str(value) for value in energies]
            answer[domain + "_before_chemical_potential_J_mol"] = potentials_before
            answer[domain + "_after_chemical_potential_J_mol"] = potentials_after
            all_energy.extend(energies)
        total, net = sum(all_energy, Decimal(0)), sum(deltas, Decimal(0))
        gross = sum((abs(value) for value in deltas), Decimal(0))
        tolerance = _d(3e-13) * gross
        answer.update(
            total_free_energy_change_pJ=float(total),
            total_free_energy_change_pJ_exact=str(total),
            net_mol=float(net),
            net_mol_exact=str(net),
            gross_mol=float(gross),
            gross_mol_exact=str(gross),
            tolerance_mol=float(tolerance),
            tolerance_mol_exact=str(tolerance),
            strict_conservation_valid=bool(abs(net) <= tolerance),
            energy_display_representable=all(
                np.isfinite(float(v)) and (v == 0 or float(v) != 0) for v in (*all_energy, total)
            ),
            optional_Cells_ideal_functional=True,
            heat_inferred=False,
            driving_law_inferred=False,
        )
    return answer


def precision(actual, expected):
    actual, expected = np.asarray(actual), np.asarray(expected)
    finite = np.isfinite(expected)
    budget = np.zeros_like(expected)
    budget[finite] = 3e-14 * abs(expected[finite]) + 4 * abs(np.spacing(expected[finite]))
    error = np.zeros_like(expected)
    error[finite] = abs(actual[finite] - expected[finite])
    ratio = np.divide(error, budget, out=np.zeros_like(error), where=budget > 0)
    ratio = np.where(finite & (budget == 0) & (error != 0), np.inf, ratio)
    return budget, ratio
