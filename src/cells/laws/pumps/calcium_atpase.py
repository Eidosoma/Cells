"""Positive-domain plasma-membrane Ca-ATPase: one Ca out per formal cycle.

Neutral identity for the equations of an older family's calcium pump, evaluated
by that family's kernel (``plasma_calcium.pump_rates``); its module cites the
source law. Positive cycles move one divalent Ca from the cytosol to the outside
and hydrolyse one ATP from maintained ATP/ADP/Pi pools. Saturation is in
cytosolic Ca and ATP; the thermodynamic factor is (1 - exp(affinity)) with

    affinity RT = drive - mu_Ca,   mu_Ca = RT ln(ci/co) + 2 F V   (V inside - outside).

The standard hydrolysis energy is declared, like cells.cycle.nak_atp_mass_action_positive@1,
against a 1 M standard state; the kernel's numeric-mM quotient receives it as
delta_g0 - RT ln(1000), so both ATPases of one model use the same convention.
Species roles, geometry, inventories and ledgers belong to the composing model.
Supply neutral padding BEFORE this law and reject invalid trials with
domain_valid; there is no concentration floor, clipping or state repair.

The law's own module is laws/pumps/ca_atp_mass_action_positive.py (docs/CORE_SEAMS_DESIGN.md
§8.2), which declares it; this module re-imports its names for their importers.
"""

from cells.laws.pumps.ca_atp_mass_action_positive import (  # noqa: F401
    CALCIUM_PER_CYCLE,
    LAW_ID,
    MAX_ABS_AFFINITY_OVER_RT,
    MAX_ABS_VOLTAGE_V,
    VALENCE,
    Parameters,
    Rates,
    chemical_drive,
    domain_valid,
    kernel_parameters,
    kinetics,
)
