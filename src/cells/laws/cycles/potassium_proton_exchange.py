"""The K+/H+ exchange on the cycle kind (the mitochondria appendix's §5, Eq. 21): one K+ into N
for one H+ out.

    K+(P) + H+(N) -> K+(N) + H+(P),   q = 0

Eq. 21 is used as printed, J = S (1 - e^x), with S = X [K+]_P h_N."""

from cells.laws.cycles.forms import CycleForm, MonomialForm, MonomialRate, Reference
from cells.laws.cycles.mitochondria_source import citation
from cells.modules import CycleLaw, qualified

LAW_ID = "cells.cycle.potassium_proton_exchange@1"
DECLARED_ID = qualified(LAW_ID)  # As definitions write it; a module-level name, for the manifest.
CYCLE = CycleForm(
    kinetics="monomial",
    roles=(("K", 1), ("H", 1)),
    rows=(("K", "P"), ("K", "N"), ("H", "N"), ("H", "P")),
    modes=(("exchange", (-1, 1, -1, 1)),),
    monomial=MonomialForm(
        (MonomialRate(orders=((Reference("K", "P"), 1.0), (Reference("H", "N"), 1.0))),)
    ),
)
LAW = CycleLaw(
    DECLARED_ID,
    reads=("cells.binding.rapid_binding@1",),  # Its rows at a closure node are read free (§5.2's admission).
    forms="base",  # Frame B: every proton counted (D236).
    material_term="material_term",  # The kind's: its rate over all the rows it moves.
    cycle=CYCLE,
    host="cells.kind.transporter@1",
    provenance="cited",
    source=citation("the appendix's §5 (Eq. 21)"),
)
