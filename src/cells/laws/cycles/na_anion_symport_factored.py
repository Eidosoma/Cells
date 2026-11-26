"""cells.cycle.na_anion_symport_factored@1: a fuel-free, electrogenic cotransporter of n Na+ and one monovalent
anion, in the cycle kind's factored form (seam A's general form, docs/CORE_SEAMS_DESIGN.md §3;
D228 item 1; an SLC5-type monocarboxylate carrier's coupling).

Per forward cycle it moves n Na+ and one anion B- from the population's P end to its N end, so a
population whose N is its cell (orientation {"N": "a"}) imports, carrying n - 1 charges inward. It
runs on no fuel and converts nothing, so no standard part survives in its free energy, which is
the cycle kind's, from the species registry:

    dG_cyc / RT = n ln(c_Na,N / c_Na,P) + ln(c_B,N / c_B,P) + (n - 1) F (phi_N - phi_P) / RT,

and its net rate is the kind's factored law, J = k a S (1 - exp(dG_cyc / RT)), with J+ = k a S and
J- = J+ exp(dG_cyc / RT) from the contract and the saturation at the source end P,

    S = [1 + (K_Na / c_Na,P)^h_Na]^-1 [1 + (K_B / c_B,P)^h_B]^-1.

Its consequences: J vanishes where dG_cyc = 0, at the stall voltage
V_stall = -(RT / ((n - 1) F)) [n ln(c_Na,N / c_Na,P) + ln(c_B,N / c_B,P)] for n > 1, which is
also the reversal voltage, and the population's capacity k scales J at every state without moving
it. Its voltage dependence is thermodynamic only (through dG_cyc); a kinetic one needs a diagram
form, version 2, its own law.

The law carries no constants. n_Na (an integer from 1 to 4), K_Na_mM and K_B_mM (positive), and
hill_Na and hill_B (positive integers: the factored form's Hill numbers) are the population's
declared parameters, and its capacity and availability are the kind's. The cited
work establishes the 2:1 coupling for lactate and propionate; n_Na stays a parameter because the
coupling for another anion is its declaration's claim, never the law's.

A known limit: it declares no step term, so refusal 4 (version 1.3,
docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.4) refuses its moves at a compartment's node, fail-closed.
A compartment consumer needs declared step terms first; no current consumer puts it there.
"""

from cells.laws.cycles.forms import CycleForm, Parameter, Saturation
from cells.modules import Citation, CitedWork, CycleLaw, qualified

LAW_ID = "cells.cycle.na_anion_symport_factored@1"
STOICHIOMETRY_RANGE = (1, 4)  # n_Na: Na+ per cycle, an integer.

# Its rows, in the form's order: Na+ at N and at P, then the anion at N and at P. Its one mode moves
# n_Na Na+ and one anion from P to N per forward cycle (N's rows gain, P's lose).
CYCLE = CycleForm(
    kinetics="factored",
    roles=(("Na", 1), ("B", -1)),
    rows=(("Na", "N"), ("Na", "P"), ("B", "N"), ("B", "P")),
    modes=(("import", ("n_Na", "-n_Na", 1, -1)),),
    parameters=(
        Parameter(
            "n_Na",
            "1",
            low=STOICHIOMETRY_RANGE[0],
            high=STOICHIOMETRY_RANGE[1],
            integer=True,
            positive=True,
        ),
        Parameter("K_Na_mM", "mM", positive=True),
        Parameter("K_B_mM", "mM", positive=True),
        Parameter("hill_Na", "1", integer=True, positive=True),
        Parameter("hill_B", "1", integer=True, positive=True),
    ),
    saturation=(
        (
            Saturation(("Na", "P"), "K_Na_mM", "hill_Na"),
            Saturation(("B", "P"), "K_B_mM", "hill_B"),
        ),
    ),
)

# Its declaration on the law template (registry/laws.py): form-carried, so no version-1 moves or
# kernels; registered by the law registry's loader as one of the model table's law homes, hosted
# by the transporter kind's general layout.
DECLARED_ID = qualified(LAW_ID)  # As definitions write it; a module-level name, for the manifest.
LAW = CycleLaw(
    DECLARED_ID,
    cycle=CYCLE,
    host="cells.kind.transporter@1",
    provenance="cited",
    source=Citation(
        "the Na+/monocarboxylate cotransporter SMCT1 (human SLC5A8) expressed in Xenopus oocytes",
        "the abstract: an invariant 2:1 Na+/substrate cotransport stoichiometry, for lactate and "
        "for propionate",
        "the abstract only (the article is not open access): no number taken beyond the 2:1 "
        "coupling, which is the range's declared default's evidence",
        (
            "n_Na is a declared parameter from 1 to 4, not the abstract's 2, which it reports for "
            "lactate and propionate only",
            "the anionic leak current the abstract reports through the protein is not modelled",
            "the saturation is the kind's factored Hill form with declared constants, not a "
            "measured kinetic scheme, and no kinetic voltage dependence",
        ),
        (
            CitedWork(
                ("Coady MJ", "Wallendorff B", "Bourgeois F", "Charron F", "Lapointe JY"),
                2007,
                "Establishing a definitive stoichiometry for the Na+/monocarboxylate "
                "cotransporter SMCT1",
                doi="10.1529/biophysj.107.108555",
            ),
        ),
    ),
)
