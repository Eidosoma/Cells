"""The adenine nucleotide exchange on the cycle kind (the mitochondria appendix's §3, Eq. 14): one
ATP4- out of N for one ADP3- in, both the Mg-free forms, which are the base rows.

    ATP4-(N) + ADP3-(P) -> ATP4-(P) + ADP3-(N),   q = -1

Eq. 14 is used as printed, J = S (1 - e^x), with
S = X ([ATP]_N/[ADP]_N) e^(theta_N u) / ((1 + ([ATP]_P/[ADP]_P) e^(-theta_P u))
    (1 + ([ATP]_N/[ADP]_N) e^(theta_N u)) (1 + k_mADP/[ADP]_P)).
The voltage shares are one parameter, theta_P, and theta_N = 1 - theta_P is written into the
exponents. So a pair that does not sum to one, the condition under which Eq. 14 passes, cannot be
declared. k_mADP is a population parameter in M (Table 1: 3.5e-6), never the law's (D144)."""

from cells.laws.cycles.forms import (
    Affine,
    CycleForm,
    MonomialFactor,
    MonomialForm,
    MonomialRate,
    MonomialTerm,
    Parameter,
    Reference,
)
from cells.laws.cycles.mitochondria_source import citation
from cells.modules import CycleLaw, qualified

LAW_ID = "electrogenic_nucleotide_exchange@1"
DECLARED_ID = qualified(LAW_ID)  # As definitions write it; a module-level name, for the manifest.
THETA_P = Affine("theta_P")  # e^(-theta_P u) = e^(theta_P psi)
MINUS_THETA_N = Affine("theta_P", 1.0, -1.0)  # -theta_N = theta_P - 1: e^(theta_N u)
RATIO_P = ((Reference("ATP", "P"), 1.0), (Reference("ADP", "P"), -1.0))
RATIO_N = ((Reference("ATP", "N"), 1.0), (Reference("ADP", "N"), -1.0))
CYCLE = CycleForm(
    kinetics="monomial",
    roles=(("ATP", -4), ("ADP", -3)),
    rows=(("ATP", "N"), ("ATP", "P"), ("ADP", "P"), ("ADP", "N")),
    modes=(("exchange", (-1, 1, -1, 1)),),
    parameters=(
        Parameter("theta_P", "1", low=0.0, high=1.0),  # Eq. 14: 0.35.
        Parameter("k_mADP", "M", positive=True),  # Table 1: 3.5e-6.
    ),
    monomial=MonomialForm(
        (
            MonomialRate(
                orders=RATIO_N,
                zeta=MINUS_THETA_N,
                factors=(
                    MonomialFactor(1.0, (MonomialTerm(1.0, RATIO_P, THETA_P),)),
                    MonomialFactor(1.0, (MonomialTerm(1.0, RATIO_N, MINUS_THETA_N),)),
                    MonomialFactor(
                        1.0, (MonomialTerm("k_mADP", ((Reference("ADP", "P"), -1.0),)),)
                    ),
                ),
            ),
        )
    ),
)
LAW = CycleLaw(
    DECLARED_ID,
    reads=("rapid_binding@1",),  # Its rows at a closure node are read free (§5.2's admission).
    forms="base",  # Frame B: every move in base forms (D236).
    material_term="material_term",  # The kind's: its rate over all the rows it moves.
    cycle=CYCLE,
    host="cells.transporter@1",
    provenance="cited",
    source=citation(
        "the appendix's §3 (Eq. 14; Table 1's k_mADP)",
        ("the voltage shares as one parameter, theta_N = 1 - theta_P",),
    ),
)
