"""Independent 80-digit scalar native-transporter algebra and owner loops.

No production Cells, NumPy or JAX imports. The literal generated Q applies its
1e-3 once per list item, outside the concentration power. Driving energy is a
source diagnostic, not a physical heat/free-energy ledger.
"""

from decimal import Decimal, localcontext
from numbers import Real

F = Decimal("96485.3321233100184")
R = Decimal("8.31446261815324")


def number(value, *, positive=False, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        raise ValueError("Require real native transporter inputs")
    result = Decimal(str(value))
    if not result.is_finite() or (positive and result <= 0) or (nonnegative and result < 0):
        raise ValueError("Invalid native transporter input domain")
    return result


def evaluate(
    config,
    inside_mM,
    outside_mM,
    valence,
    *,
    voltage_V=-0.07,
    temperature_K=298.15,
    area_m2=1e-12,
    availability=1.0,
    rho=1.0,
):
    """Evaluate one native cell-zone configuration, positive configured forward."""
    with localcontext() as context:
        context.prec = 80
        inside = {s: number(v, nonnegative=True) for s, v in inside_mM.items()}
        outside = {s: number(v, nonnegative=True) for s, v in outside_mM.items()}
        z = {s: number(v) for s, v in valence.items()}
        voltage = number(voltage_V)
        rt = R * number(temperature_K, positive=True)
        area, opening, density = (number(v, nonnegative=True) for v in (area_m2, availability, rho))
        if opening > 1 or config["reaction zone"] != "cell":
            raise ValueError("Unsupported zone or availability")
        net_z, electrical, forward, quotient = Decimal(0), Decimal(0), Decimal(1), Decimal(1)
        reactants, products = [], []
        for product, role, multipliers, km_key, transfer in (
            (False, "reactants", "reactant multipliers", "Km reactants", "transfered into cell"),
            (True, "products", "product multipliers", "Km products", "transfered out of cell"),
        ):
            moved = config[transfer]
            moved = [] if moved in (None, "None") else moved
            for s, coefficient, km in zip(
                config[role], config[multipliers], config[km_key], strict=True
            ):
                n, k = number(coefficient, positive=True), number(km, positive=True)
                owner = outside if s in moved else inside
                concentration = owner[s]
                if concentration <= 0:
                    raise ValueError(
                        "Participating substrate must be strictly positive even when blocked"
                    )
                literal_term = Decimal("0.001") * concentration**n
                quotient = quotient * literal_term if product else quotient / literal_term
                if not product:
                    loading = (concentration / k) ** n
                    forward *= loading / (1 + loading)
                if s in moved:
                    transferred_z = (1 if product else -1) * n * z[s]
                    net_z += transferred_z
                    electrical -= transferred_z * F * voltage
                (products if product else reactants).append((s, s in moved, n))

        regular, independent, inhibitors, direct = Decimal(1), Decimal(0), Decimal(1), []
        for activating, label, km_key, exponent_key in (
            (True, "transporter activators", "activator Km", "activator n"),
            (False, "transporter inhibitors", "inhibitor Km", "inhibitor n"),
        ):
            configured = config.get(label)
            if configured in (None, "None") or configured == []:
                continue
            for s, km, exponent in zip(
                configured, config[km_key], config[exponent_key], strict=True
            ):
                s = s[:-1] if s.endswith("*") else s
                special = s[-1:] if s.endswith(("!", "&")) else ""
                s = s[:-1] if special else s
                value, k, n = inside[s], number(km, positive=True), number(exponent, positive=True)
                if special == "&":
                    direct.append(value if activating else -value)
                else:
                    loading = (value / k) ** n
                    if activating:
                        hill = loading / (1 + loading)
                        if special == "!":
                            independent += hill
                        else:
                            regular *= hill
                    else:
                        inhibitors /= 1 + loading
        regulation = (regular + independent) * inhibitors
        if direct:
            regulation *= sum(direct, Decimal(0))
        standard = config["standard free energy"]
        reversible = standard not in (None, "None")
        energy = number(standard) + electrical + rt * quotient.ln() if reversible else Decimal(0)
        factor = 1 - (energy / rt).exp() if reversible else Decimal(1)
        flux = (
            number(config["max rate"], nonnegative=True)
            * opening
            * density
            * regulation
            * forward
            * factor
        )
        extent = flux * area / Decimal("1e-15")
        owners = {s: [Decimal(0), Decimal(0)] for s in inside}
        for sign, terms in ((-1, reactants), (1, products)):
            for s, external, n in terms:
                owners[s][int(external)] += sign * n * extent
        return dict(
            flux_density_mol_m2_s=float(flux),
            extent_fmol_s=float(extent),
            native_net_z=float(net_z),
            outward_current_density_A_m2=float(net_z * F * flux),
            outward_current_C_s=float(net_z * F * Decimal("1e-15") * extent),
            forward_saturation=float(forward),
            regulation=float(regulation),
            log_source_quotient=float(quotient.ln()),
            source_electrical_energy_J_mol=float(electrical),
            source_reaction_energy_J_mol=float(energy),
            amount_fmol_s={s: [float(v) for v in values] for s, values in owners.items()},
        )
