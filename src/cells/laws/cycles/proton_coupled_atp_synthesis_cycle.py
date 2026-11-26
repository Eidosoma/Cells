"""ATP synthesis on the cycle kind (the mitochondria appendix's §2, Eqs. 10 and 11), balanced in
frame B (D236): one ATP made in the matrix, with n_A = 3 protons entering from P.

    ADP3-(N) + HPO4 2-(N) + 3 H+(P) -> ATP4-(N) + 2 H+(N) (+ H2O),   q = -3

J = A_11 (1 - e^x), keeping Eq. 11's forward term:
S = X e^(-Delta G°_ATP/RT) (K_MgADP/K_MgATP) [MgADP-] [Pi] h_P^3 h_N^-3 e^(3u).
- [MgADP-] is a registry form of ADP and [Pi] the total phosphate, both at N.
- Table 2's Delta G°_ATP, +36.03 kJ/mol at pH 7 on total phosphate, is a RateConstant (the lead's
  ruling 3, 20 November 2026). It scales S only, emits no seam-E entry and never enters x.
- x is the registry's base-form free energy, §2's derived Delta G°_F of -5.032 kJ/mol at 1 M.
- K_MgADP and K_MgATP are population parameters in M (Table 1: 347.0e-6 and 24.0e-6), never the
  law's (D144): their ratio multiplies S as the rate's constants.

A declared limit of this head: n_A = 3 is fixed in the counts (Table 1). A count written from a
parameter needs affine counts, which do not exist yet (the held item); a rotor's c protons per
three ATP is another law until then."""

from cells.laws.cycles.forms import (
    CycleForm,
    MonomialForm,
    MonomialRate,
    Parameter,
    RateConstant,
    Reference,
    Scaled,
)
from cells.laws.cycles.mitochondria_source import citation
from cells.modules import CycleLaw, qualified

LAW_ID = "cells.cycle.proton_coupled_atp_synthesis_cycle@1"
DECLARED_ID = qualified(LAW_ID)  # As definitions write it; a module-level name, for the manifest.
CYCLE = CycleForm(
    kinetics="monomial",
    roles=(("ADP", -3), ("Pi", -2), ("ATP", -4), ("H", 1)),
    rows=(("ADP", "N"), ("Pi", "N"), ("ATP", "N"), ("H", "N"), ("H", "P")),
    modes=(("synthesis", (-1, -1, 1, 2, -3)),),
    parameters=(
        Parameter("K_MgADP", "M", positive=True),  # Table 1: 347.0e-6.
        Parameter("K_MgATP", "M", positive=True),  # Table 1: 24.0e-6.
    ),
    monomial=MonomialForm(
        (
            MonomialRate(
                log_k=RateConstant(36.03),  # e^(-Delta G°_ATP/RT): rate only, never x's.
                constants=("K_MgADP", Scaled("K_MgATP", power=-1)),  # K_MgADP / K_MgATP
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
    reads=(
        "cells.binding.rapid_binding@1",
    ),  # Its rows at a closure node are read free (§5.2's admission).
    forms="base",  # Frame B: every move in base forms, every proton counted (D236).
    material_term="material_term",  # The kind's: its rate over all the rows it moves.
    cycle=CYCLE,
    host="cells.kind.transporter@1",
    provenance="cited",
    source=citation(
        "the appendix's §2 (Eqs. 10 and 11; Table 2's Delta G°_ATP; Table 1's K_MgATP, K_MgADP)",
        (
            "Eq. 11 balanced in frame B (D236): its forward term is kept, and its backward term is "
            "the balanced one",
            "n_A = 3 fixed in the counts (Table 1), a declared limit until affine counts exist",
        ),
    ),
)
