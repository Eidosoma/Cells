"""The NADH supply on the cycle kind (the mitochondria appendix's §6, Eq. 1): a held neutral
reductant pair reduces NAD in the matrix (D236). It has no membrane leg.

    S_red(N) + NAD(N) -> S_ox(N) + NADH(N) + H+(N),   q = 0

Eq. 1 is declared balanced on the held pair (D236), J = A_1 (1 - e^x), keeping its printed
forward term:
- S = A_1 = X phi_DH r [NAD], with affinity share 1. The population's capacity carries X_DH.
- r, the source's NADH/NAD ratio, is a population parameter (Table 1: 4.5807 with Pi control,
  4.2530 without), never the law's (D144). It multiplies S as the rate's constant.
- phi_DH = (1 + [Pi]_N/k_Pi1)/(1 + [Pi]_N/k_Pi2), on the total matrix phosphate, a read role.
  k_Pi1 and k_Pi2 are population parameters in mM.
- x is the registry's: x° = +16.1181 at 1 M, from the named set's declared anchor (Delta G°_S = 0
  at pH 7, one scalar proton released), plus ln([S_ox][NADH] h_N / ([S_red][NAD])). The forward
  term carries no standard free energy, so the law has no cited constant and emits no seam-E
  entry.
- S_red and S_ox are its fuel, held together (cells.fuel_kind.maintained_held_rows@1 only): read at every stage,
  never moved. Their upkeep is the kind's held-row work, -J (mu_S_ox - mu_S_red). It equals the
  supply's heat, -J Delta G, plus the work delivered to the NAD pool, J (mu_NADH + mu_H - mu_NAD).

A world states r twice, and the law does not tie the two: as the population's parameter, which
sets the rate, and in the held pair's ratio S_red/S_ox = 10^-0.10 r, which sets the drive. With
both, the equilibrium is the source's [NADH]/[NAD] = r at the reference matrix pH 7.10. A pair
held at r, without 10^-0.10, puts it at pH_N 7.00 instead, its x smaller by 0.10 ln 10 at every
state (the appendix's planted control)."""

from cells.laws.cycles.forms import (
    CycleForm,
    MonomialFactor,
    MonomialForm,
    MonomialRate,
    MonomialTerm,
    Parameter,
    Reference,
    Scaled,
)
from cells.laws.cycles.mitochondria_source import citation
from cells.modules import CycleLaw, qualified

LAW_ID = "cells.cycle.held_reductant_supply@1"
DECLARED_ID = qualified(LAW_ID)  # As definitions write it; a module-level name, for the manifest.
PI_TOTAL = Reference("Pi", "N", "total")  # The total matrix phosphate, read and never moved.
CYCLE = CycleForm(
    kinetics="monomial",
    roles=(("S_red", 0), ("NAD", -1), ("S_ox", 0), ("NADH", -2), ("H", 1)),
    rows=(("S_red", "N"), ("NAD", "N"), ("S_ox", "N"), ("NADH", "N"), ("H", "N")),
    modes=(("reduction", (-1, -1, 1, 1, 1)),),
    parameters=(
        Parameter("r", "1", positive=True),  # Table 1: 4.5807 (with Pi control).
        Parameter("k_Pi1", "mM", positive=True),  # Table 1: 0.13413.
        Parameter("k_Pi2", "mM", positive=True),  # Table 1: 0.67668.
    ),
    fuel_roles=("S_red", "S_ox"),  # The held pair: held together, never moved.
    monomial=MonomialForm(
        (
            MonomialRate(
                constants=("r",),  # S = X phi_DH r [NAD]: no standard free energy in it.
                orders=((Reference("NAD", "N"), 1.0),),
                factors=(  # phi_DH: (1 + [Pi]/k_Pi1) up, (1 + [Pi]/k_Pi2) down; k in mM.
                    MonomialFactor(
                        -1.0, (MonomialTerm(Scaled("k_Pi1", 1000.0, -1), ((PI_TOTAL, 1.0),)),)
                    ),
                    MonomialFactor(
                        1.0, (MonomialTerm(Scaled("k_Pi2", 1000.0, -1), ((PI_TOTAL, 1.0),)),)
                    ),
                ),
            ),
        ),
        read_roles=(("Pi", -2),),
    ),
)
LAW = CycleLaw(
    DECLARED_ID,
    fuel_kinds=(
        "cells.fuel_kind.maintained_held_rows@1",
    ),  # A world that moves the pair is refused.
    reads=(
        "cells.binding.rapid_binding@1",
    ),  # Its rows at a closure node are read free (§5.2's admission).
    forms="base",  # Frame B: every move in base forms, every proton counted (D236).
    cycle=CYCLE,
    host="cells.kind.transporter@1",
    provenance="cited",
    source=citation(
        "the appendix's §6 (Eq. 1; Table 1's X_DH, r, k_Pi1 and k_Pi2)",
        (
            "Eq. 1 balanced on the held pair (D236): its forward term is kept, and its backward "
            "term is the balanced one",
            "declared, not cited (D236): Delta G°_S = 0 at pH 7, the named set's anchor, and the "
            "held pair's ratio, 10^-0.10 r, the world's",
        ),
    ),
)
