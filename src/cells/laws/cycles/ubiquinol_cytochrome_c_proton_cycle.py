"""Complex III on the cycle kind (the mitochondria appendix's §1.2): one QH2 oxidized, two
cytochrome c reduced on the P side (chemistry at P, K3), and four protons pumped.

    QH2(N) + 2 c3+(P) + 2 H+(N) -> Q(N) + 2 c2+(P) + 4 H+(P),   q = +2

Eq. 24 is restored as phi_Pi x Eq. 7 (D236), so J = phi_Pi A_7 (1 - e^(x/2)).
- S = phi_Pi A_7 / (1 + e^(x/2)), with affinity share 2.
- A_7 = X e^(-x°/2) h_N h_P^-2 e^(-u) [QH2]^(1/2) [Q]^(-1/2) [c3+], with x° from Table 2's
  -32.53 kJ/mol at pH 7 and two scalar protons released.
- phi_Pi = (1 + [Pi]_N/k_Pi3)/(1 + [Pi]_N/k_Pi4), on the total matrix phosphate, a read role.
- Eq. 7 is the same law with k_Pi3 = k_Pi4, where phi_Pi = 1 exactly (the lead's ruling 2).

It is one of three laws for the appendix's single redox_driven_proton_cycle@1 (the lead's ruling
1), named apart since a cycle law has one fixed set of rows."""

from cells.laws.cycles.forms import (
    CitedConstant,
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

LAW_ID = "ubiquinol_cytochrome_c_proton_cycle@1"
DECLARED_ID = qualified(LAW_ID)  # As definitions write it; a module-level name, for the manifest.
PI_TOTAL = Reference("Pi", "N", "total")  # The total matrix phosphate, read and never moved.
CYCLE = CycleForm(
    kinetics="monomial",
    roles=(("QH2", 0), ("Q", 0), ("c_ox", 3), ("c_red", 2), ("H", 1)),
    rows=(("QH2", "N"), ("Q", "N"), ("c_ox", "P"), ("c_red", "P"), ("H", "N"), ("H", "P")),
    modes=(("oxidation", (-1, 1, -2, 2, -2, 4)),),
    parameters=(
        Parameter("k_Pi3", "mM", positive=True),  # Table 1: 0.19172 (with Pi control).
        Parameter("k_Pi4", "mM", positive=True),  # Table 1: 25.310; k_Pi3 = k_Pi4 gives Eq. 7.
    ),
    monomial=MonomialForm(
        (
            MonomialRate(
                log_k=CitedConstant(-32.53, protons=2, scale=0.5),  # e^(-x°/2), x° = 19.1137.
                orders=(
                    (Reference("QH2", "N"), 0.5),
                    (Reference("Q", "N"), -0.5),
                    (Reference("c_ox", "P"), 1.0),
                    (Reference("H", "N"), 1.0),
                    (Reference("H", "P"), -2.0),
                ),
                zeta=1.0,  # e^(-u)
                factors=(  # phi_Pi: (1 + [Pi]/k_Pi3) up, (1 + [Pi]/k_Pi4) down; k in mM.
                    MonomialFactor(
                        -1.0, (MonomialTerm(Scaled("k_Pi3", 1000.0, -1), ((PI_TOTAL, 1.0),)),)
                    ),
                    MonomialFactor(
                        1.0, (MonomialTerm(Scaled("k_Pi4", 1000.0, -1), ((PI_TOTAL, 1.0),)),)
                    ),
                ),
                share=2,  # J = phi_Pi A_7 (1 - e^(x/2))
            ),
        ),
        read_roles=(("Pi", -2),),
    ),
)
LAW = CycleLaw(
    DECLARED_ID,
    reads=("rapid_binding@1",),  # Its rows at a closure node are read free (§5.2's admission).
    forms="base",  # Frame B: every move in base forms, every proton counted (D236).
    material_term="material_term",  # The kind's: its rate over all the rows it moves.
    cycle=CYCLE,
    host="cells.transporter@1",
    provenance="cited",
    source=citation(
        "the appendix's §1.2 (Eqs. 6, 7 and 24; Table 2's Delta G°_C3; Table 1's k_Pi3, k_Pi4)",
        (
            "Eq. 24 restored as phi_Pi x Eq. 7 (D236): its forward term is Eq. 24's times "
            "1e-7 M / h_N",
            "three laws for the appendix's one redox_driven_proton_cycle@1 (the lead's ruling 1)",
        ),
    ),
)
