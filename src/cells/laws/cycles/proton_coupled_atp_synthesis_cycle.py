"""ATP synthesis on the cycle kind (the mitochondria appendix's §2, Eqs. 10 and 11), balanced in
frame B (D236): one ATP made in the matrix, with n_A = 3 protons entering from P.

    ADP3-(N) + HPO4 2-(N) + 3 H+(P) -> ATP4-(N) + 2 H+(N) (+ H2O),   q = -3

J = A_11 (1 - e^x), keeping Eq. 11's forward term:
S = X e^(-Delta G°_ATP/RT) (K_MgADP/K_MgATP) [MgADP-] [Pi] h_P^3 h_N^-3 e^(3u).
- [MgADP-] is a registry form of ADP and [Pi] the total phosphate, both at N.
- Table 2's Delta G°_ATP, +36.03 kJ/mol at pH 7 on total phosphate, is a RateConstant (the lead's
  ruling 3, 20 November 2026). It scales S only, emits no seam-E entry and never enters x.
- x is the registry's base-form free energy, §2's derived Delta G°_F of -5.032 kJ/mol at 1 M."""

import math

from cells.laws.cycles.forms import CycleForm, MonomialForm, MonomialRate, RateConstant, Reference
from cells.laws.cycles.mitochondria_source import citation
from cells.modules import CycleLaw

LAW_ID = "proton_coupled_atp_synthesis_cycle@1"
DECLARED_ID = f"cells.{LAW_ID}"  # As definitions write it; a module-level name, for the manifest.
K_MGATP, K_MGADP = 24.0e-6, 347.0e-6  # M, Table 1 (2006): the registry's forms' own constants.
CYCLE = CycleForm(
    kinetics="monomial",
    roles=(("ADP", -3), ("Pi", -2), ("ATP", -4), ("H", 1)),
    rows=(("ADP", "N"), ("Pi", "N"), ("ATP", "N"), ("H", "N"), ("H", "P")),
    modes=(("synthesis", (-1, -1, 1, 2, -3)),),
    monomial=MonomialForm(
        (
            MonomialRate(
                # e^(-Delta G°_ATP/RT) K_MgADP/K_MgATP: a rate-only constant, never x's.
                log_k=RateConstant(36.03, offset=math.log(K_MGADP / K_MGATP)),
                orders=(
                    (Reference("ADP", "N", "MgADP"), 1.0),
                    (Reference("Pi", "N", "total"), 1.0),
                    (Reference("H", "P"), 3.0),
                    (Reference("H", "N"), -3.0),
                ),
                zeta=-3.0,  # e^(3u)
            ),
        )
    ),
)
LAW = CycleLaw(
    DECLARED_ID,
    reads=("rapid_binding@1",),  # Its rows at a closure node are read free (§5.2's admission).
    forms="base",  # Frame B: every move in base forms, every proton counted (D236).
    cycle=CYCLE,
    host="cells.transporter@1",
    provenance="cited",
    source=citation(
        "the appendix's §2 (Eqs. 10 and 11; Table 2's Delta G°_ATP; Table 1's K_MgATP, K_MgADP)",
        (
            "Eq. 11 balanced in frame B (D236): its forward term is kept, and its backward term is "
            "the balanced one",
            "n_A = 3 fixed (Table 1); a rotor's c protons per three ATP is another law",
        ),
    ),
)
