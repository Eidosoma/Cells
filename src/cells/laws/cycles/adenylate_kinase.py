"""Adenylate kinase on the cycle kind (the mitochondria appendix's §7, Eqs. 17 and 18): in the
intermembrane space, two ADP make one ATP and one AMP (D236). Every row is at P (chemistry at P,
K3).

    2 ADP3-(P) -> ATP4-(P) + AMP2-(P),   q = 0

Declared in base forms with the source's rate (D236), J = S (1 - e^x):
- S = X (1 + [Mg2+]_P/K_MgATP) K_base [ADP3-]^2, with affinity share 1. The population's
  capacity carries X_AK.
- [ADP3-] is the Mg-free base form at P, and [Mg2+] the free Mg2+ there, a read role.
- x is the registry's, -ln K_base + ln([ATP4-][AMP2-]/[ADP3-]^2), from cells.potential_set.beard2005@2, whose AMP2-
  potential this constant fixes.
- K_base is §7's match at full precision: Table 1's K_AK = 0.4331 on totals, converted at the
  state-3 buffer's free Mg2+, m = 3.808553529 mM. Its display, 0.388964538, is not the constant,
  and would move x by 1.5e-10. It is the law's CitedConstant, an equilibrium constant cited
  dimensionless: log k = ln K_base, and its seam-E entry carries -ln K_base unrounded (the forms'
  addition (b)).
- The prefactor (1 + [Mg2+]_P/K_MgATP) is the ratio of total to Mg-free ATP, so the rate stays
  the source's, on totals. Without it the rate is too small by that factor, 159.69 at the matched
  m (the appendix's planted control).
- K_MgATP is a population parameter in M (Table 1: 24.0e-6), never the law's (D144).

At binding equilibrium the law is the source's form on totals, X (K_tot [ADP]^2 - [AMP][ATP]),
with K_tot = K_base (1 + m/K_MgATP)/(1 + m/K_MgADP)^2 at the IMS's free Mg2+ m. At the matched m,
K_tot is K_AK, which is Eq. 18 exactly.

Its population sits on the inner membrane with every row at P. The patch's flux record reads its
conversion as its forms crossing in opposite directions, with no net charge (the convention for
chemistry at P)."""

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
    Scaled,
)
from cells.laws.cycles.mitochondria_source import citation
from cells.modules import CycleLaw, qualified

LAW_ID = "cells.cycle.adenylate_kinase@1"
DECLARED_ID = qualified(LAW_ID)  # As definitions write it; a module-level name, for the manifest.
K_BASE = 0.38896453805908730400  # §7's K_base at full precision (its match; D236).
MG_P = Reference("Mg", "P")  # The free Mg2+ at P, read and never moved.
CYCLE = CycleForm(
    kinetics="monomial",
    roles=(("ADP", -3), ("ATP", -4), ("AMP", -2)),
    rows=(("ADP", "P"), ("ATP", "P"), ("AMP", "P")),
    modes=(("phosphotransfer", (-2, 1, 1)),),
    parameters=(Parameter("K_MgATP", "M", positive=True),),  # Table 1: 24.0e-6.
    monomial=MonomialForm(
        (
            MonomialRate(
                log_k=CitedConstant(0.0, rt_term=-math.log(K_BASE)),  # k = K_base, x° = -ln K_base
                orders=((Reference("ADP", "P"), 2.0),),
                factors=(  # The prefactor (1 + [Mg2+]_P/K_MgATP): total over Mg-free ATP.
                    MonomialFactor(
                        -1.0, (MonomialTerm(Scaled("K_MgATP", power=-1), ((MG_P, 1.0),)),)
                    ),
                ),
            ),
        ),
        read_roles=(("Mg", 2),),
    ),
)
LAW = CycleLaw(
    DECLARED_ID,
    reads=(
        "cells.binding.rapid_binding@1",
    ),  # Its rows at a closure node are read free (§5.2's admission).
    forms="base",  # Frame B: every move in base forms (D236).
    cycle=CYCLE,
    host="cells.kind.transporter@1",
    provenance="cited",
    source=citation(
        "the appendix's §7 (Eqs. 17 and 18; Table 1's K_AK, X_AK and K_MgATP)",
        (
            "Eq. 18 declared in base forms with the source's rate (D236): the prefactor "
            "(1 + [Mg2+]_P/K_MgATP) keeps its rate on totals",
            "K_base matched at the source's state-3 buffer (D236), declared: the source states "
            "no free Mg2+ in the intermembrane space",
        ),
    ),
)
