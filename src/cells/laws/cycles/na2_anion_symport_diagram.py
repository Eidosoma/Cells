"""na2_anion_symport_diagram@1: the cotransporter of two Na+ and one monovalent anion as an
eight-state mass-action diagram, with a kinetic voltage dependence (D228 item 1, version 2; seam A's
diagram form, docs/CORE_SEAMS_DESIGN.md §3 and §16). Its rates are named, so each population
declares its own (forms.resolved).

Its cycle runs from the population's P end to its N end (N is the cell under orientation
{"N": "a"}):

    E_P -> Na_P -> Na2_P -> Na2B_P -> Na2B_N -> Na2_N -> Na_N -> E_N -> E_P

Na binds twice at P and then the anion B; the loaded carrier crosses; B leaves at N, then Na twice;
the empty carrier crosses back. Its one mode, `import`, moves 2 Na+ and one B- from P to N per
forward cycle: counts (2, -2, 1, -1) on the rows (Na, N), (Na, P), (B, N), (B, P), so one charge
moves inward. n = 2 is the structure's, since a diagram's counts are integers: the 2:1 coupling
version 1 cites (laws/cycles/na_anion_symport_factored.py).

Each edge's rate is alpha = k0 prod a^order exp(zeta psi), with a = c/c° (c° = 1000 mM) and psi =
F (phi_N - phi_P)/RT. A binding at P has the bound row's order at P forward; a release at N has the
released row's order at N backward (its binding from N); a crossing has none.

**Its parameters are every population's own, and none is sourced:**
- 16 rate constants, k_<edge>_f and k_<edge>_b (1/s, positive), for the edges na1_P, na2_P, b_P,
  loaded, b_N, na2_N, na1_N and empty, in the cycle's order;
- 8 zeta (1), forward and backward, on the four edges that can carry charge: the two Na bindings at
  P (an ion well) and both crossings. Every other zeta is 0.

**The law fixes no carrier charge: the charge each crossing carries is the declaration's zeta
split.** A carrier whose empty form has a charge z_E != 0 declares zeta on both crossings; z_E = 0
is the declaration whose empty crossing's zeta is zero, so only the loaded crossing (and any Na well
at P) carries charge. Detailed balance fixes only their sum.

**At parse, Wegscheider's condition for the declared values** (the kind's cycle_checks on the
resolved form): the cycle converts nothing, so it is prod k0+ = prod k0- (R0 = 0 within B_W =
32 eps (T + N)) and sum (zeta+ - zeta-) = -1 (B_psi = 0 within u sum |zeta|: one charge inward per
cycle). A population whose rates break either is refused, naming its law, mode and cycle.

Its thermodynamics are version 1's at n = 2: the same dG_cyc / RT = 2 ln(c_Na,N / c_Na,P) +
ln(c_B,N / c_B,P) + F (phi_N - phi_P) / RT, and the same stall voltage. Its kinetics are its own: S
depends on the voltage through the declared zeta, which version 1's factored form cannot.
"""

from cells.laws.cycles.forms import CycleForm, Diagram, Edge, Parameter, Rate
from cells.modules import Citation, CitedWork, CycleLaw, qualified

LAW_ID = "na2_anion_symport_diagram@1"
STATES = ("E_P", "Na_P", "Na2_P", "Na2B_P", "Na2B_N", "Na2_N", "Na_N", "E_N")
EDGES = ("na1_P", "na2_P", "b_P", "loaded", "b_N", "na2_N", "na1_N", "empty")  # The cycle's order.
CHARGED = ("na1_P", "na2_P", "loaded", "empty")  # The edges whose zeta the population declares.
RATE_SCALE_PER_S = 1.0  # omega: S = j+ / omega, the capacity k = N_carriers omega.


def _rate(edge, direction, orders=()):
    """One direction's Rate: its named k0, its orders, and its named zeta on a charged edge."""
    zeta = f"z_{edge}_{direction}" if edge in CHARGED else 0.0
    return Rate(f"k_{edge}_{direction}", orders, zeta)


def _edge(k, edge, forward=(), backward=()):
    """The cycle's edge k, from state k to the next."""
    target = (k + 1) % len(STATES)
    return Edge(edge, k, target, _rate(edge, "f", forward), _rate(edge, "b", backward))


# Its rows, in version 1's order: Na+ at N and at P, then the anion at N and at P.
CYCLE = CycleForm(
    kinetics="diagram",
    roles=(("Na", 1), ("B", -1)),
    rows=(("Na", "N"), ("Na", "P"), ("B", "N"), ("B", "P")),
    modes=(("import", (2, -2, 1, -1)),),
    parameters=(
        *(Parameter(f"k_{e}_{d}", "1/s", positive=True) for e in EDGES for d in ("f", "b")),
        *(Parameter(f"z_{e}_{d}", "1") for e in CHARGED for d in ("f", "b")),
    ),
    diagram=Diagram(
        states=STATES,
        edges=(
            _edge(0, "na1_P", forward=(("Na", "P", 1),)),
            _edge(1, "na2_P", forward=(("Na", "P", 1),)),
            _edge(2, "b_P", forward=(("B", "P", 1),)),
            _edge(3, "loaded"),
            _edge(4, "b_N", backward=(("B", "N", 1),)),
            _edge(5, "na2_N", backward=(("Na", "N", 1),)),
            _edge(6, "na1_N", backward=(("Na", "N", 1),)),
            _edge(7, "empty"),
        ),
        cycles=(("import", tuple((edge, 1) for edge in EDGES)),),
        rate_scale_per_s=RATE_SCALE_PER_S,
    ),
)

# Its declaration on the law template (registry/laws.py): form-carried, registered by the law
# registry's loader as one of the model table's law homes, hosted by the transporter kind's general
# layout. Its scheme was named from memory and not read (CORE_SEAMS §15).
DECLARED_ID = qualified(LAW_ID)  # As definitions write it; a module-level name, for the manifest.
LAW = CycleLaw(
    DECLARED_ID,
    cycle=CYCLE,
    host="cells.transporter@1",
    provenance="cited",
    source=Citation(
        "an ordered Na+-coupled cotransport cycle of the SLC5 family: the cations bind before "
        "the substrate at the outer face and leave after it at the inner face, with the empty "
        "carrier's return and the cation well as the voltage-dependent steps (the SGLT1 schemes "
        "of E. M. Wright's group, named from memory and not read); its 2:1 coupling from Coady "
        "et al.'s abstract, as version 1 cites it",
        "the abstract of the work below, for the 2:1 coupling only",
        "no numbers taken: the law is a form, its 16 rate constants and 8 zeta a definition's "
        "values, unsourced today",
        (
            "two Na+ per cycle, fixed by the diagram, where version 1 declares n_Na",
            "the anionic leak current through the protein is not modelled",
            "no state of its own: the kind's directional diagrams give its steady state",
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
