"""cells.cycle.electroneutral_symport_reversible_tanh@1: the symport of one cation and one anion in an
electroneutral ratio, in a manufactured rate form (the cycle kind's monomial form).

    n_cation C(P) + n_anion A(P) -> n_cation C(N) + n_anion A(N)

Per forward cycle n_cation of its cation and n_anion of its anion go from the population's P end to
its N end, each count a declared integer, 1 or 2. The law declares itself electroneutral, since its
rate has no voltage term: the kind refuses by name a population whose species and counts move
charge. Its free energy is the kind's, with no standard part and no voltage term:

    x = dG_cyc / RT = n_cation ln(C_N / C_P) + n_anion ln(A_N / A_P).

Its rate (fmol cycles/s), with k the capacity and v the availability, is

    J = k v tanh(-x/2) = k v S (1 - e^x),   S = 1 / (1 + e^x),

which the form holds exactly: one factor of power 1 with one term, whose K is 1 and whose orders
are the rows' own counts, plus at N and minus at P. The standard state cancels, since the orders
sum to zero.

**Manufactured.** The rate form has no outside source, and no number is the law's: the two counts
are a population's parameters, and the capacity and the availability are the kind's. J depends on
the concentrations through x alone and never exceeds k v in size. It claims no transporter protein,
no regulation and no water carried with the salt. It is not a second law of the potassium-chloride
symport, whose own is cells.operator.k_anion_symport_mass_action@1, an operator beside water. A salt of three or
more ions is a law of its own.

Its domain is the kind's for this form, x <= 80, one-sided. Its moves are base rows, so a closure
may hold them: the kind reads them free.

Its step term is the kind's material rate (material_term), the sum over its four rows, on each of
them, which bounds their relaxation at every stage. It moves no net charge, so it has no charge
slope, and refusal 4 (version 1.3, docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.4) refuses its moves of
charged rows at a compartment's node, fail-closed.
"""

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
from cells.modules import Citation, CycleLaw, qualified

LAW_ID = "cells.cycle.electroneutral_symport_reversible_tanh@1"
DECLARED_ID = qualified(LAW_ID)  # As definitions write it; a module-level name, for the manifest.
COUNT_RANGE = (1, 2)  # n_cation and n_anion: integers.
# e^x = (C_N/C_P)^n_cation (A_N/A_P)^n_anion: each row's own count as its order, plus at N and
# minus at P.
E_X = MonomialTerm(
    1.0,
    (
        (Reference("cation", "N"), Affine("n_cation", 1.0)),
        (Reference("cation", "P"), Affine("n_cation", -1.0)),
        (Reference("anion", "N"), Affine("n_anion", 1.0)),
        (Reference("anion", "P"), Affine("n_anion", -1.0)),
    ),
)
CYCLE = CycleForm(
    kinetics="monomial",
    roles=(("cation", None), ("anion", None)),
    rows=(("cation", "N"), ("cation", "P"), ("anion", "N"), ("anion", "P")),
    modes=(("import", ("n_cation", "-n_cation", "n_anion", "-n_anion")),),
    parameters=tuple(
        Parameter(name, "1", low=COUNT_RANGE[0], high=COUNT_RANGE[1], integer=True, positive=True)
        for name in ("n_cation", "n_anion")
    ),
    monomial=MonomialForm((MonomialRate(factors=(MonomialFactor(1.0, (E_X,)),)),)),
)
LAW = CycleLaw(
    DECLARED_ID,
    reads=(
        "cells.binding.rapid_binding@1",
    ),  # Its rows at a closure node are read free (§5.2's admission).
    forms="base",  # Two ions moved together: each move is a base row.
    material_term="material_term",  # The kind's: its rate over all the rows it moves.
    electroneutral=True,
    cycle=CYCLE,
    host="cells.kind.transporter@1",
    provenance="parity",
    source=Citation(
        "manufactured: the rate form has no outside source. It moved from an older model family's "
        "law of the same equation",
        "the older family's kernel: J = C a tanh(A / 2RT), A the affinity of the moved ions",
        "no number taken: the law is a form, its capacity and counts a definition's values",
        (
            "manufactured: a saturating function of the affinity alone, with no binding constants",
            "two species at counts 1 or 2, where the older kernel took any number of species",
            "no regulation, and no water with the salt",
        ),
    ),
    test="tests/unit/test_cycle_kind.py"
    "::test_the_pump_and_the_symports_meet_their_equations_and_each_plant_misses_its_criteria",
)
