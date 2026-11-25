"""na_k_2anion_symport_reversible_tanh@1: the electroneutral symport of one Na+, one K+ and two
monovalent anions, in a manufactured rate form (the cycle kind's monomial form).

    Na+(P) + K+(P) + 2 A-(P) -> Na+(N) + K+(N) + 2 A-(N)

Per forward cycle one Na+, one K+ and two anions go from the population's P end to its N end, so no
charge moves. A population whose N is its cell (orientation {"N": "a"}) takes the salt in. It runs
on no fuel and converts nothing, so its free energy, the cycle kind's, has no standard part and no
voltage term:

    x = dG_cyc / RT = ln(Na_N / Na_P) + ln(K_N / K_P) + 2 ln(A_N / A_P).

Its rate (fmol cycles/s), with k the capacity and v the availability, is

    J = k v tanh(-x/2) = k v S (1 - e^x),   S = 1 / (1 + e^x),

which the form holds exactly: one factor of power 1 with one term, whose K is 1 and whose orders
are the rows' own counts, plus at N and minus at P. The standard state cancels, since the orders
sum to zero.

**Manufactured.** The rate form has no outside source, and no number is the law's: the capacity and
the availability are the kind's. The 1:1:2 coupling is the form's, and nothing about it is measured
here. J depends on the concentrations through x alone and never exceeds k v in size. It claims no
transporter protein, no isoform, no regulation by volume, chloride or phosphorylation, and no water
carried with the salt. The kind reads no volume.

Its domain is the kind's for this form, x <= 80, one-sided. Its moves are base rows, so a closure
may hold them: the kind reads them free.

A known limit: it declares no step term and moves charged rows with no net charge, so refusal 4
(version 1.3, docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.4) refuses its moves at a compartment's node,
fail-closed. It has no charge slope, and the kind's material term counts no charged row that
crosses, so no per-stage rule bounds its rows' relaxation.
"""

from cells.laws.cycles.forms import (
    CycleForm,
    MonomialFactor,
    MonomialForm,
    MonomialRate,
    MonomialTerm,
    Reference,
)
from cells.modules import Citation, CycleLaw, qualified

LAW_ID = "na_k_2anion_symport_reversible_tanh@1"
DECLARED_ID = qualified(LAW_ID)  # As definitions write it; a module-level name, for the manifest.
COUNTS = (("Na", 1), ("K", 1), ("anion", 2))  # Per forward cycle, from P to N.
ROWS = tuple((role, end) for role, _ in COUNTS for end in ("N", "P"))
# e^x = prod (c_N / c_P)^count: each row's own count as its order, plus at N and minus at P.
E_X = MonomialTerm(
    1.0,
    tuple(
        (Reference(role, end), float(n if end == "N" else -n))
        for role, n in COUNTS
        for end in ("N", "P")
    ),
)
CYCLE = CycleForm(
    kinetics="monomial",
    roles=(("Na", 1), ("K", 1), ("anion", -1)),
    rows=ROWS,
    modes=(("import", tuple(n if end == "N" else -n for _, n in COUNTS for end in ("N", "P"))),),
    monomial=MonomialForm((MonomialRate(factors=(MonomialFactor(1.0, (E_X,)),)),)),
)
LAW = CycleLaw(
    DECLARED_ID,
    reads=("rapid_binding@1",),  # Its rows at a closure node are read free (§5.2's admission).
    forms="base",  # Three ions moved together: each move is a base row.
    electroneutral=True,
    cycle=CYCLE,
    host="cells.transporter@1",
    provenance="parity",
    source=Citation(
        "manufactured: the rate form has no outside source. It moved from an older model family's "
        "law of the same equation",
        "the older family's kernel: J = C a tanh(A / 2RT), A the affinity of one Na+, one K+ and "
        "two anions",
        "no number taken: the law is a form, its capacity a definition's value",
        (
            "manufactured: a saturating function of the affinity alone, with no binding constants",
            "no regulation by volume, chloride or phosphorylation, and no water with the salt",
        ),
    ),
    test="tests/unit/test_cycle_kind.py"
    "::test_the_pump_and_the_symports_meet_their_equations_and_each_plant_misses_its_criteria",
)
