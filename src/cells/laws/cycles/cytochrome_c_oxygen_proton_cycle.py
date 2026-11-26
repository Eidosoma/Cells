"""Complex IV on the cycle kind (the mitochondria appendix's §1.3), per O2: four cytochrome c
oxidized on the P side (chemistry at P, K3), four protons pumped, and four matrix protons consumed.

    O2(N) + 4 c2+(P) + 8 H+(N) -> 4 c3+(P) + 4 H+(P) (+ 2 H2O),   q = +8

Eq. 9 is written per 1/2 O2, so J = J_C4/2 = (A_9/2) (1 - e^(x/4)).
- S = (A_9/2) / (1 + e^(x/4) + e^(x/2) + e^(3x/4)), with affinity share 4.
- A_9 = X [O2]/([O2] + k_O2) [c2+]/c_tot e^(-x°/4) h_N^2 h_P^-1 e^(-u) [O2]^(1/4) [c2+].
- x° is per O2, from Table 2's 2 x -122.94 kJ/mol at pH 7 with four scalar protons consumed.
- The per-O2 factor 1/2 sits in its own rate constant, the CitedConstant's offset ln 1/2, not in the
  population's capacity.
- k_O2 is a population parameter in M (Table 1: 1.20e-4 in both columns), never the law's (D144).
- Its x reaches about -119 RT at the grid's corner, within the monomial form's one-sided domain.

It is one of three laws for the appendix's single redox_driven_proton_cycle@1 (the lead's ruling
1)."""

import math

from cells.laws.cycles.forms import (
    CitedConstant,
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

LAW_ID = "cells.cycle.cytochrome_c_oxygen_proton_cycle@1"
DECLARED_ID = qualified(LAW_ID)  # As definitions write it; a module-level name, for the manifest.
CYCLE = CycleForm(
    kinetics="monomial",
    roles=(("O2", 0), ("c_red", 2), ("c_ox", 3), ("H", 1)),
    rows=(("O2", "N"), ("c_red", "P"), ("c_ox", "P"), ("H", "N"), ("H", "P")),
    modes=(("reduction", (-1, -4, 4, -8, 4)),),
    parameters=(Parameter("k_O2", "M", positive=True),),  # Table 1: 1.20e-4.
    monomial=MonomialForm(
        (
            MonomialRate(
                # e^(-x°/4) / 2, x° = -163.6593 per O2: half of Eq. 9's flux per 1/2 O2.
                log_k=CitedConstant(2 * -122.94, protons=-4, scale=0.25, offset=math.log(0.5)),
                orders=(
                    (Reference("c_red", "P"), 1.0),
                    (Reference("O2", "N"), 0.25),
                    (Reference("H", "N"), 2.0),
                    (Reference("H", "P"), -1.0),
                ),
                zeta=1.0,  # e^(-u)
                factors=(
                    # [O2]/([O2] + k_O2) = 1/(1 + k_O2/[O2]).
                    MonomialFactor(1.0, (MonomialTerm("k_O2", ((Reference("O2", "N"), -1.0),)),)),
                    # [c2+]/c_tot = 1/(1 + [c3+]/[c2+]).
                    MonomialFactor(
                        1.0,
                        (
                            MonomialTerm(
                                1.0,
                                ((Reference("c_ox", "P"), 1.0), (Reference("c_red", "P"), -1.0)),
                            ),
                        ),
                    ),
                ),
                share=4,  # J = (A_9/2) (1 - e^(x/4))
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
        "the appendix's §1.3 (Eqs. 8 and 9; Table 2's Delta G°_C4; Table 1's k_O2)",
        (
            "per O2, twice Eq. 9's turnover per 1/2 O2, for integer counts",
            "three laws for the appendix's one redox_driven_proton_cycle@1 (the lead's ruling 1)",
        ),
    ),
)
