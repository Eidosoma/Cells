"""atp_driven_transporter_mass_action_positive@2: ATP-driven transport of one species of any
valence, on held fuel, in the cycle kind's factored form.

Per forward cycle it hydrolyses one ATP to ADP + Pi at the population's N end and moves n of its
role from N to P, n a declared integer from 1 to 4 and z the bound species' valence:

    n role(N) + ATP(N) -> n role(P) + ADP(N) + Pi(N),   n z charges from N to P.

A population whose N is its cell (orientation {"N": "a"}) pumps its role out of the cell. Its free
energy is the cycle kind's, from the species registry's potentials at its c0:

    x = dG_cyc / RT = [mu(ADP) + mu(Pi) - mu(ATP)]/RT + ln(c_ADP c_Pi / (c_ATP c0))
        + n ln(c_P / c_N) - n z psi,   psi = F (phi_N - phi_P) / RT,

and its rate (fmol cycles/s), with k the capacity and v the availability, is

    J = k v S (1 - e^x),   S = [1 + (K/c_N)^n]^-1 [1 + K_ATP/c_ATP]^-1.

The form is the engine's own mass-action completion (laws/pumps/nak_atp_mass_action_positive.py),
and no number is the law's: n, K and K_ATP are a population's parameters, and the fuel's potentials
are the registry's. It claims no mechanism of any pump protein, no counter-transport and no kinetic
constant.

**Held fuel only** (maintained_held_rows@1). ATP, ADP and Pi are neutral rows at N that the kind
reads and never moves, and it records the maintenance's supply and work. Finite fuel waits for a
consumer. It has no pH band: a proton's pump on transformed potentials is
proton_atp_mass_action_positive@1.

At z = 0 its rate is version 1's on held fuel (atp_driven_transporter_mass_action_positive@1). At
z = 2 and n = 1 it is the rate of @3's own calcium pump (ca_atp_mass_action_positive@1). It
supersedes both for a new definition on held fuel, and neither retires before its worlds move
(docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md §6.3). The kind refuses one of them beside it on one
patch, for one species.

Its domain is the kind's for this form, |x| <= 80. Its moves are base rows, so a closure may hold
its role: the kind reads it free.

Its step terms are the kind's: a charged role's charge slope (stage_term) at both its ends, and its
material rate (material_term), the sum over its role's two rows, on each of them, so a scarce role's
relaxation is bounded at every stage, charged or neutral. By them refusal 4 (version 1.3,
docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.4) admits its moves at a compartment's node. A role that
version 1's proton buffer holds is refused by name: its read has no derivative for the term.
"""

from cells.laws.cycles.forms import CycleForm, Parameter, Saturation
from cells.modules import Citation, CycleLaw, qualified

LAW_ID = "atp_driven_transporter_mass_action_positive@2"
DECLARED_ID = qualified(LAW_ID)  # As definitions write it; a module-level name, for the manifest.
STOICHIOMETRY_RANGE = (1, 4)  # n: the role's ions or molecules per ATP, an integer.
# Its rows, in the form's order: the role at N and at P, then the fuel at N, where it is hydrolysed.
CYCLE = CycleForm(
    kinetics="factored",
    roles=(("role", None), ("ATP", 0), ("ADP", 0), ("Pi", 0)),
    rows=(("role", "N"), ("role", "P"), ("ATP", "N"), ("ADP", "N"), ("Pi", "N")),
    modes=(("cycle", ("-stoichiometry", "stoichiometry", -1, 1, 1)),),
    parameters=(
        Parameter(
            "stoichiometry",
            "1",
            low=STOICHIOMETRY_RANGE[0],
            high=STOICHIOMETRY_RANGE[1],
            integer=True,
            positive=True,
        ),
        Parameter("km_role_mM", "mM", positive=True),
        Parameter("km_atp_mM", "mM", positive=True),
    ),
    fuel_roles=("ATP", "ADP", "Pi"),
    saturation=(
        (
            Saturation(("role", "N"), "km_role_mM", "stoichiometry"),
            Saturation(("ATP", "N"), "km_atp_mM", 1),
        ),
    ),
)

# Its declaration on the law template (registry/laws.py): form-carried, registered by the law
# registry's loader as one of the model table's law homes, hosted by the transporter kind's general
# layout.
LAW = CycleLaw(
    DECLARED_ID,
    fuel_kinds=("maintained_held_rows@1",),
    reads=("rapid_binding@1",),  # Its rows at a closure node are read free (§5.2's admission).
    stage_term="stage_term",  # The kind's: its charge slope at both ends.
    material_term="material_term",  # The kind's: its rate over all the rows it moves.
    forms="base",  # One species moved: each move is a base row.
    cycle=CYCLE,
    host="cells.transporter@1",
    provenance="parity",
    source=Citation(
        "an ATP-driven transporter of one species, in the Na/K law's mass-action form "
        "(laws/pumps/nak_atp_mass_action_positive.py; docs/KINETIC_PUMP_PROCESS.md): the engine's "
        "own completion of that form",
        "docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md §6.3",
        "no numbers taken: the law is a form, its parameters a definition's values",
        (
            "one species of any valence, where version 1 moves a neutral one",
            "held fuel only, where version 1 also runs on finite fuel",
            "its ions per ATP are a declared parameter, with no measured value",
        ),
    ),
    test="tests/unit/test_cycle_kind.py"
    "::test_the_pump_and_the_symports_meet_their_equations_and_each_plant_misses_its_criteria",
)
