"""Validation-only positive-domain array law, not a Cells production mechanism.

Thermodynamic formulation of the pinned BETSE Na/K equation. Public contract and
source attribution: docs/BETSE_PUMP_CONTACT.md. No simulator lifecycle code.
"""

from pump_reference import FIELDS


def densities(values, constants, xp):
    """Float64 [case, field] -> [case, Na-in/K-in/outward-Na] mol/m²/s.

    The host validates positive-domain input before JIT entry. This kernel does
    not hide invalid input with floors/clipping, or own inventories and ATP pools.
    """
    v = {name: values[:, index] for index, name in enumerate(FIELDS)}
    log_q = (
        xp.log(v["adp_mM"] / 1000)
        + xp.log(v["pi_mM"] / 1000)
        - xp.log(v["atp_mM"] / 1000)
        + 3 * (xp.log(v["na_out_mM"]) - xp.log(v["na_in_mM"]))
        + 2 * (xp.log(v["k_in_mM"]) - xp.log(v["k_out_mM"]))
    )
    drive = log_q + (v["delta_g0_J_mol"] - constants["F"] * v["voltage_V"]) / (
        constants["R"] * v["temperature_K"]
    )
    saturation = (
        1
        / (1 + (v["km_na_mM"] / v["na_in_mM"]) ** 3)
        / (1 + (v["km_k_mM"] / v["k_out_mM"]) ** 2)
        / (1 + v["km_atp_mM"] / v["atp_mM"])
    )
    cycles = -v["alpha_mol_m2_s"] * v["availability"] * saturation * xp.expm1(drive)
    return xp.stack((-3 * cycles, 2 * cycles, 3 * cycles), axis=-1)
