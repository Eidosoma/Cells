"""cells.cycle.sodium_calcium_exchange_symmetric_barrier@1: the exchange of three Na+ for one Ca2+, a fuel-free
electrogenic cycle in the cycle kind's monomial form. Its rate form is synthetic.

    3 Na+(P) + Ca2+(N) -> 3 Na+(N) + Ca2+(P)

Per forward cycle three Na+ come into the population's N end and one Ca2+ leaves it, so one
elementary charge moves from P to N: a population whose N is its cell (orientation {"N": "a"})
takes calcium out and carries one charge inward. Its free energy is the cycle kind's. It converts
nothing, so no standard part survives in it:

    x = dG_cyc / RT = 3 ln(Na_N / Na_P) + ln(Ca_P / Ca_N) + psi,   psi = F (phi_N - phi_P) / RT.

Its rate (fmol cycles/s), with a = Na_N/K_Na, b = Na_P/K_Na, c = Ca_N/K_Ca, d = Ca_P/K_Ca (each in
mM), k the capacity and v the availability, is

    J = k v [b^3 c e^(-psi/2) - a^3 d e^(psi/2)] / [(1 + a^3 + b^3) (1 + c + d)],

the kind's J = J+ (1 - e^x) with J+ = k v S, S = b^3 c e^(-psi/2) / [(1 + a^3 + b^3) (1 + c + d)],
which the form holds exactly: orders Na@P 3 and Ca@N 1, zeta -1/2, two factors of power 1 and the
constants K_Na^-3 and K_Ca^-1, with activities against 1 mM, so that each K is its number in mM.

Its consequences: J vanishes at phi_N - phi_P = 3 E_Na - 2 E_Ca (the Nernst potentials at the
stage's concentrations), its sign is that of -x on either side, and neither the capacity nor a
half-saturation moves that potential.

**What it claims.** Only the 3:1 coupling, so the reversal, which rests on measurements that do not
all agree (the Citation). The denominator, the equal split of the one charge over the two directions
and every number are synthetic: no source gives them. The capacity and both half-saturations are a
population's declared parameters, and no value of theirs is a measured one. The sodium and calcium
factors multiply, so the form has no competition between the two ions at a face, and each one-way
flux changes by a factor 2 in (2 ln 2) RT/F (35.6 mV at 298.15 K) at every concentration. It has no
inactivation, no regulation, no leak mode and no temperature dependence beyond RT.

Its domain is the kind's for this form, x <= 80, one-sided, with no voltage bound of its own. Its
moves are its base rows, so a closure may hold them: the kind reads them free.

Its step terms are the kind's: its charge slope (stage_term) at both its ends, and its material rate
(material_term), the sum over its four rows, on each of them, so a scarce calcium row's relaxation
is bounded at every stage. By them refusal 4 (version 1.3, docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.4)
admits its moves at a compartment's node.
"""

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
from cells.modules import Citation, CitedWork, CycleLaw, qualified

LAW_ID = "cells.cycle.sodium_calcium_exchange_symmetric_barrier@1"
DECLARED_ID = qualified(LAW_ID)  # As definitions write it; a module-level name, for the manifest.
NA_N, NA_P = Reference("Na", "N"), Reference("Na", "P")
CA_N, CA_P = Reference("Ca", "N"), Reference("Ca", "P")
PER_K_NA_CUBED = Scaled("km_na_mM", 1.0, -3)  # (Na/K_Na)^3 is K_Na^-3 Na^3.
PER_K_CA = Scaled("km_ca_mM", 1.0, -1)
CYCLE = CycleForm(
    kinetics="monomial",
    roles=(("Na", 1), ("Ca", 2)),
    rows=(("Na", "N"), ("Na", "P"), ("Ca", "N"), ("Ca", "P")),
    modes=(("exchange", (3, -3, -1, 1)),),
    parameters=(
        Parameter("km_na_mM", "mM", positive=True),
        Parameter("km_ca_mM", "mM", positive=True),
    ),
    monomial=MonomialForm(
        (
            MonomialRate(
                orders=((NA_P, 3.0), (CA_N, 1.0)),  # b^3 c.
                zeta=-0.5,  # e^(-psi/2): half of the one charge on each direction.
                factors=(
                    MonomialFactor(
                        1.0,  # 1 + a^3 + b^3.
                        (
                            MonomialTerm(PER_K_NA_CUBED, ((NA_N, 3.0),)),
                            MonomialTerm(PER_K_NA_CUBED, ((NA_P, 3.0),)),
                        ),
                    ),
                    MonomialFactor(
                        1.0,  # 1 + c + d.
                        (
                            MonomialTerm(PER_K_CA, ((CA_N, 1.0),)),
                            MonomialTerm(PER_K_CA, ((CA_P, 1.0),)),
                        ),
                    ),
                ),
                constants=(PER_K_NA_CUBED, PER_K_CA),
            ),
        ),
        standard_state_mM=1.0,
    ),
)

# Its declaration on the law template (registry/laws.py): form-carried, registered by the law
# registry's loader as one of the model table's law homes, hosted by the transporter kind's general
# layout. A four-state cycle of the same mechanism is planned (docs/HUMAN_CARDIAC_LAWS_DESIGN.md);
# which of the two forms stays is decided when it lands (D210, D211).
LAW = CycleLaw(
    DECLARED_ID,
    reads=(
        "cells.binding.rapid_binding@1",
    ),  # Its rows at a closure node are read free (§5.2's admission).
    stage_term="stage_term",  # The kind's: its charge slope at both ends.
    material_term="material_term",  # The kind's: its rate over all the rows it moves.
    forms="base",  # Two ions exchanged: each move is a base row.
    cycle=CYCLE,
    host="cells.kind.transporter@1",
    provenance="parity",
    source=Citation(
        "only the 3:1 coupling, so the reversal, is supported, by measured reversals of the "
        "sodium-calcium exchange current of guinea-pig ventricular cells, in giant patches (1992) "
        "and in whole cells (2002); the reversal itself is contested (the third departure). The "
        "denominator, the equal voltage split and every number are synthetic: no source gives them",
        "the abstracts of the works below (1992, item e; 2002, the conclusion); none was read in "
        "full",
        "no number taken: the capacity and the two half-saturations are a definition's values, "
        "none of them measured for this form",
        (
            "the denominator, a sodium factor times a calcium factor, is synthetic: it has no "
            "competition between the two ions, which the 1992 abstract reports at the inner face",
            "the equal voltage split is synthetic: each one-way flux changes by a factor 2 in 36 "
            "mV (298 K), where the 1992 abstract reports currents that change by a factor 2 in "
            "about 100 mV, and voltage dependences that move with the concentrations",
            "one mode at 3:1: a 2000 abstract concludes 4:1 or a variable coupling in patches of "
            "the same cells, and a 2004 abstract says that the reversals of the exchange current "
            "had indicated a ratio closer to 4:1, and reports flux ratios near 3.2, two minor "
            "modes and a net current and a calcium flux that can reverse at different potentials",
            "no inactivation, no regulation by either ion, no leak mode and no temperature "
            "dependence beyond RT",
        ),
        (
            CitedWork(
                ("Matsuoka S", "Hilgemann DW"),
                1992,
                "Steady-state and dynamic properties of cardiac sodium-calcium exchange. Ion and "
                "voltage dependencies of the transport cycle",
                doi="10.1085/jgp.100.6.963",
            ),
            CitedWork(
                (
                    "Hinata M",
                    "Yamamura H",
                    "Li L",
                    "Watanabe Y",
                    "Watano T",
                    "Imaizumi Y",
                    "Kimura J",
                ),
                2002,
                "Stoichiometry of Na+-Ca2+ exchange is 3:1 in guinea-pig ventricular myocytes",
                doi="10.1113/jphysiol.2002.025866",
            ),
            CitedWork(
                ("Fujioka Y", "Komeda M", "Matsuoka S"),
                2000,
                "Stoichiometry of Na+-Ca2+ exchange in inside-out patches excised from guinea-pig "
                "ventricular myocytes",
                doi="10.1111/j.1469-7793.2000.t01-2-00339.x",
            ),
            CitedWork(
                ("Kang TM", "Hilgemann DW"),
                2004,
                "Multiple transport modes of the cardiac Na+/Ca2+ exchanger",
                doi="10.1038/nature02271",
            ),
        ),
    ),
    test="tests/unit/test_cycle_kind.py"
    "::test_the_exchange_meets_its_rate_equation_and_each_plant_misses_its_criteria",
)
