"""Independent ideal-protein reference using source pL/fmol owner arithmetic.

No Cells/JAX imports. Direct activity ratios and 640-digit absolute endpoint
free energies provide the reference difference. The optional Cells functional
is a fixed-volume chemical-potential primitive, not native BETSE energetics.
"""

from decimal import Context, Decimal, localcontext

from validation.tissue import physiology_protein_projection_reference as owners


def _d(value):
    return Decimal.from_float(float(value))


def _state(
    raw, binding, protein, temperature_K, standard_concentration_mol_m3, gas_constant_J_mol_K
):
    domains = owners._owners(raw, binding, protein)
    rt = _d(gas_constant_J_mol_K) * _d(temperature_K)
    c0 = _d(standard_concentration_mol_m3)
    result, energies, amounts = {}, {}, {}
    for domain, rows in domains.items():
        result[domain], energies[domain], amounts[domain] = {}, {}, {}
        for owner, (concentration, volume_pL) in rows.items():
            c = _d(concentration)
            # C [mol/m3] equals its numerical value in mM; C*V[pL] is fmol.
            n_fmol = c * _d(volume_pL)
            g = Decimal(0) if c == 0 else Decimal("1e-3") * rt * n_fmol * ((c / c0).ln() - 1)
            mu = Decimal("-Infinity") if c == 0 else rt * (c / c0).ln()
            result[domain][owner] = dict(
                free_energy_pJ=float(g), chemical_potential_J_mol=float(mu), zero_stock=c == 0
            )
            energies[domain][owner] = g
            amounts[domain][owner] = n_fmol * Decimal("1e-15")
    total = sum((value for domain in energies.values() for value in domain.values()), Decimal(0))
    result["total_free_energy_pJ"] = float(total)
    return result, energies, amounts


def evaluate(
    raw, binding, protein, *, temperature_K, standard_concentration_mol_m3, gas_constant_J_mol_K
):
    with localcontext(Context(prec=640)):
        return _state(
            raw,
            binding,
            protein,
            temperature_K,
            standard_concentration_mol_m3,
            gas_constant_J_mol_K,
        )[0]


def change(
    raw,
    binding,
    before,
    after,
    *,
    temperature_K,
    standard_concentration_mol_m3,
    gas_constant_J_mol_K,
):
    with localcontext(Context(prec=640)):
        _, g0, n0 = _state(
            raw, binding, before, temperature_K, standard_concentration_mol_m3, gas_constant_J_mol_K
        )
        _, g1, n1 = _state(
            raw, binding, after, temperature_K, standard_concentration_mol_m3, gas_constant_J_mol_K
        )
        result = {}
        net, gross, total = Decimal(0), Decimal(0), Decimal(0)
        for domain, rows in g0.items():
            result[domain] = {}
            for owner, old in rows.items():
                delta_g = g1[domain][owner] - old
                amount = n1[domain][owner] - n0[domain][owner]
                result[domain][owner] = dict(free_energy_change_pJ=float(delta_g))
                total += delta_g
                net += amount
                gross += abs(amount)
        result.update(
            total_free_energy_change_pJ=float(total),
            amount_balance_residual_mol=float(net),
            gross_amount_change_mol=float(gross),
        )
        return result


def endpoint_work(chemical_free_energy_change_pJ, *, capacitor_energy_change_pJ, clamp_work_pJ):
    """Conditional algebra of explicit inputs; no inferred heat/holding work."""
    with localcontext(Context(prec=2048)):
        result = (
            _d(chemical_free_energy_change_pJ) + _d(capacitor_energy_change_pJ) - _d(clamp_work_pJ)
        )
        return float(result)
