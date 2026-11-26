"""Complex I on the cycle kind (the mitochondria appendix's §1.1, Eqs. 2-5): one NADH oxidized and
four protons pumped. The appendix's single redox_driven_proton_cycle@1 is three laws here, one per
complex (the lead's ruling 1, 20 November 2026), since a cycle law has one fixed set of rows.

    NADH(N) + Q(N) + 5 H+(N) -> NAD(N) + QH2(N) + 4 H+(P),   q = +4

Its declared S is Eq. 3's forward term, a monomial (mitochondria_source's conventions):
S = X e^(-x°) [NADH] [Q] [QH2]^-1 h_N^5 h_P^-4 e^(-4u).
- x° = Delta G°/RT at 1 M, from Table 2's -69.37 kJ/mol at pH 7 with one scalar proton consumed.
- The population's capacity carries X_C1."""

from cells.laws.cycles.forms import CitedConstant, CycleForm, MonomialForm, MonomialRate, Reference
from cells.laws.cycles.mitochondria_source import citation
from cells.modules import CycleLaw, qualified

LAW_ID = "cells.cycle.nadh_ubiquinone_proton_cycle@1"
DECLARED_ID = qualified(LAW_ID)  # As definitions write it; a module-level name, for the manifest.
CYCLE = CycleForm(
    kinetics="monomial",
    roles=(("NADH", -2), ("Q", 0), ("NAD", -1), ("QH2", 0), ("H", 1)),
    rows=(("NADH", "N"), ("Q", "N"), ("NAD", "N"), ("QH2", "N"), ("H", "N"), ("H", "P")),
    modes=(("oxidation", (-1, -1, 1, 1, -5, 4)),),
    monomial=MonomialForm(
        (
            MonomialRate(
                log_k=CitedConstant(-69.37, protons=-1),  # Table 2, at pH 7: x° = -44.1016.
                orders=(
                    (Reference("NADH", "N"), 1.0),
                    (Reference("Q", "N"), 1.0),
                    (Reference("QH2", "N"), -1.0),
                    (Reference("H", "N"), 5.0),
                    (Reference("H", "P"), -4.0),
                ),
                zeta=4.0,  # e^(-4u)
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
        "the appendix's §1.1 (Eqs. 2 and 3; Table 2's Delta G°_C1)",
        ("three laws for the appendix's one redox_driven_proton_cycle@1 (the lead's ruling 1)",),
    ),
)
