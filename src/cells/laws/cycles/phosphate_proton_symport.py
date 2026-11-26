"""The phosphate carrier on the cycle kind (the mitochondria appendix's §4, Eqs. 15 and 16),
balanced in frame B (D236): one phosphate into N with its protons, in base forms one HPO4 2- and
two H+.

    HPO4 2-(P) + 2 H+(P) -> HPO4 2-(N) + 2 H+(N),   q = 0

J = A_16 (1 - e^x), keeping Eq. 16's forward term: S = X h_N / (1 + k_PiHt/[H2PO4-]_P).
- [H2PO4-] is a registry form of phosphate at P.
- k_PiHt, printed in mM, is a parameter, since Table 1's two columns differ in it."""

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

LAW_ID = "cells.cycle.phosphate_proton_symport@1"
DECLARED_ID = qualified(LAW_ID)  # As definitions write it; a module-level name, for the manifest.
CYCLE = CycleForm(
    kinetics="monomial",
    roles=(("Pi", -2), ("H", 1)),
    rows=(("Pi", "P"), ("Pi", "N"), ("H", "P"), ("H", "N")),
    modes=(("import", (-1, 1, -2, 2)),),
    parameters=(Parameter("k_PiHt", "mM", positive=True),),  # Table 1: 0.45082 or 0.72911.
    monomial=MonomialForm(
        (
            MonomialRate(
                orders=((Reference("H", "N"), 1.0),),
                factors=(
                    MonomialFactor(
                        1.0,
                        (
                            MonomialTerm(
                                Scaled("k_PiHt", 1e-3), ((Reference("Pi", "P", "H2PO4"), -1.0),)
                            ),
                        ),
                    ),
                ),
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
        "the appendix's §4 (Eqs. 15 and 16; Table 1's k_PiHt)",
        (
            "Eq. 16 balanced in frame B (D236): its forward term is kept, and its backward term "
            "is the balanced one",
        ),
    ),
)
