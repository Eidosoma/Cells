"""Compact worlds for isopotential_partition@1 (docs/CELL_DIVISION_S5_DESIGN.md §8.1).

Nominal values around one heredity cell (validation/tissue/surface_pump_v3_fixtures), built from
neither J1 input (the J2 bright line, §10.1). The parent is the heredity cell with its pump
removed: pumps on a dividing cell are later work. It keeps its Kir2.1 and NaV1.2 populations, so
the partition maps populations too. Daughter slots are written by core/partition_spec.add_division
(the anchor rule), and membrane_entity_state@1 declares every population.

Variants (§8.1): a neighbour cell (a second heredity cell, its own bath) with a gated contact to
the parent, so the partition maps a contact; and a bridge between the daughters
(cytoplasmic_bridge_closure@1, add_bridge) with sigma_cyt at its declared default.
"""

from cells.core import partition_spec as ps
from cells.core import pump_composite_spec as cs
from cells.models.operators.contract import Operator
from tests import membrane_insertion_fixtures as ifx
from validation.tissue import pump_water_fixtures as wfx
from validation.tissue import surface_pump_v3_fixtures as v3f

PARTITION = "isopotential_partition@1"
BRIDGE = "cytoplasmic_bridge_closure@1"
INSERTION2 = "scheduled_membrane_insertion@2"
LUMEN2 = "restricted_cleft_lumen@2"
INJECTION = "electrode_current_injection@1"
DT = 1e-3
EVENT = 0.002
# The furrow world (cleft_divided): tests/membrane_insertion_fixtures.cleft_cell's furrow and
# cleft, S2's furrow rate, and an onset one step before the division.
ONSET = 0.001
FURROW_RATE = 1e-11  # m^2/s
FURROW_AREA_M2 = 1e-11  # cleft_cell's furrow area (A_on).
CLEFT_PL = 0.01  # cleft_cell's cleft volume (V_on).
# An electrode's carriers: K and M, the heredity cell's (composite_crossrev's injection world).
INJECTION_CARRIERS = {"K": 0.4912, "M": 0.5088}
# The bridge (S5 design §4.2): the declared cytoplasmic conductivity's default, standard
# free-solution diffusivities (M as a chloride-like anion, P impermeant), and an aperture whose
# conductance 2 a_0 sigma_cyt keeps dt x 2 G_b / C_daughter below 1 at 1 ms for this small cell.
SIGMA_CYT = 0.5  # S/m
FREE_D = {"Na": 1.33e-9, "K": 1.96e-9, "M": 2.03e-9, "P": 0.0}
APERTURE_M = 2e-9
# The neighbour's contact: nominal, with a voltage gate declared away from its steady state.
CONTACT = dict(
    area_m2=1e-10,
    permeability_m_per_s={"Na": 1e-8, "K": 1e-8, "M": 1e-8, "P": 0.0},
    gate=dict(threshold_voltage_V=0.015, minimum_open_fraction=0.1, initial_gate=0.8),
)


def parent(*, end=0.004, neighbour=False):
    """The heredity cell facing its held bath, without its pump (@3, raw); with neighbour, a
    second heredity cell (cell_1, in the depolarised state D, so the contact carries current
    and its gate moves) in contact with it."""
    if neighbour:
        kinds = [v3f.HEREDITY_STATES[k][:4] for k in ("H", "D")]
        base = v3f.heredity_cells(kinds, dt=DT, end_time=end)
    else:
        base = wfx.heredity_cell("H", dt=DT, end_time=end)
    base["experiment"]["observation_times"] = [0.0, end]
    for patch in base["model"]["membranes"]:
        patch["pump"] = None
    base["experiment"]["pump_controls"] = []
    if neighbour:
        gate = dict(law="junction_voltage_relaxation@1", **CONTACT["gate"])
        base["model"]["junctions"] = [
            dict(
                id="contact",
                sender="cell_0",
                receiver="cell_1",
                area_m2=CONTACT["area_m2"],
                permeability_m_per_s=dict(CONTACT["permeability_m_per_s"]),
                law="constant_field@1",
                gate=gate,
            )
        ]
        base["experiment"]["junction_controls"] = [
            dict(junction_id="contact", schedule=[dict(time=0.0, availability=1.0)])
        ]
        base["execution"]["edge_capacity"] = 1
    return base


def divided(
    *,
    f=0.5,
    area_fraction=None,
    carriers=None,
    at=EVENT,
    end=0.004,
    events=True,
    second=None,
    bridge=None,
    neighbour=False,
    injection=None,
    injection_start=None,
):
    """The parent, its two daughters (d1, d2) and the partition, as a composition (raw).

    second: a time for both daughters' own divisions (d1 -> g1, g2; d2 -> g3, g4), or None.
    bridge: (closure law, closure time s[, aperture m]) for a bridge between d1 and d2 that starts
    closing at the first division, or None.
    neighbour: a neighbour cell (cell_1) with a gated contact to the parent, which the first
    division maps to d1 and d2 (a_e = 1/2).
    injection: a current (A) into d1 from injection_start (default the first division) on, until
    its own division with second, or None.
    """
    raw = cs.frozen_definition(parent(end=end, neighbour=neighbour))
    blocks = [
        ps.add_division(
            raw,
            division_id="first",
            parent="cell_0",
            daughters=("d1", "d2"),
            volume_fraction=f,
            area_fractions=None if area_fraction is None else {"membrane_0": area_fraction},
            mismatch_carriers=carriers,
        )
    ]
    bridges = []
    if bridge is not None:
        closure, tau, *rest = bridge
        block = ps.add_bridge(
            raw,
            junction_id="bridge_1",
            daughters=("d1", "d2"),
            aperture_m=rest[0] if rest else APERTURE_M,
            diffusivity=diffusivity(raw),
        )
        bridges.append(dict(block, closure=closure, closure_time_s=tau))
    if second is not None:
        for d, kids in (("d1", ("g1", "g2")), ("d2", ("g3", "g4"))):
            blocks.append(
                ps.add_division(
                    raw,
                    division_id=f"second_{d}",
                    parent=d,
                    daughters=kids,
                    bridges=("bridge_1",) if bridges else (),
                )
            )
    raw["model"]["operators"] = [ifx.membrane_state(raw), dict(law=PARTITION, divisions=blocks)]
    if bridges:
        raw["model"]["operators"].append(dict(law=BRIDGE, bridges=bridges))
        raw["experiment"]["bridge_controls"] = (
            [dict(junction_id="bridge_1", start_time=at)] if events else []
        )
    schedule = []
    if events:
        schedule.append(dict(division="first", time=at, carriers=["c1", "c2"]))
        if second is not None:
            schedule += [
                dict(division="second_d1", time=second, carriers=["c11", "c12"]),
                dict(division="second_d2", time=second, carriers=["c21", "c22"]),
            ]
    raw["experiment"]["partition_events"] = schedule
    if injection is not None:
        inject(
            raw, "d1", injection, at if injection_start is None else injection_start, stop=second
        )
    return raw


def inject(raw, cell, current_A, start, *, stop=None):
    """Append electrode_current_injection@1 into cell from start (until stop) (in place)."""
    raw["model"]["operators"].append(
        dict(law=INJECTION, electrodes=[dict(cell_id=cell, carriers=dict(INJECTION_CARRIERS))])
    )
    schedule = [dict(time=0.0, current_A=0.0), dict(time=start, current_A=current_A)]
    if stop is not None:
        schedule.append(dict(time=stop, current_A=0.0))
    raw["experiment"]["injection_controls"] = [dict(cell_id=cell, schedule=schedule)]


def cleft_divided(
    *,
    f=0.5,
    area_fraction=None,
    carriers=None,
    at=EVENT,
    end=0.004,
    onset=ONSET,
    rate=FURROW_RATE,
    lumen=True,
    events=True,
    bridge=None,
    injection=None,
    injection_start=None,
):
    """The compact division world with a furrow (§8.1), as a composition (raw).

    The parent (the heredity cell without its pump) has its old patch on the bath and a furrow
    patch into a cleft. The cleft is a finite node, open from the furrow's onset at bath
    composition with a zero charge anchor, joined to the bath by a narrow access face
    (tests/membrane_insertion_fixtures.cleft_cell). Its operators:
    * scheduled_membrane_insertion@2: the furrow, from its onset until the division, then the
      daughters' furrows at their shares of the rate;
    * restricted_cleft_lumen@2 (with lumen): the cleft, faced by the furrow and its daughters;
    * isopotential_partition@1: cell_0 into d1 and d2 at `at`, each patch split at
      area_fraction (default f);
    * optionally a bridge (as divided()) and an injection into d1 from injection_start (default
      the division) on.
    """
    base = ifx.cleft_cell(end=end, cleft_pL=CLEFT_PL)
    base["experiment"]["observation_times"] = [0.0, end]
    for patch in base["model"]["membranes"]:
        patch["pump"] = None
    base["experiment"]["pump_controls"] = []
    raw = cs.frozen_definition(base)
    a = f if area_fraction is None else area_fraction
    block = ps.add_division(
        raw,
        division_id="first",
        parent="cell_0",
        daughters=("d1", "d2"),
        volume_fraction=f,
        area_fractions={"membrane_0": a, "furrow": a},
        mismatch_carriers=carriers,
    )
    bridges = []
    if bridge is not None:
        closure, tau, *rest = bridge
        made = ps.add_bridge(
            raw,
            junction_id="bridge_1",
            daughters=("d1", "d2"),
            aperture_m=rest[0] if rest else APERTURE_M,
            diffusivity=diffusivity(raw),
        )
        bridges.append(dict(made, closure=closure, closure_time_s=tau))
    furrows = ("furrow", "furrow_d1", "furrow_d2")
    operators = [
        ifx.membrane_state(raw),
        dict(
            law=INSERTION2,
            patches=[
                dict(
                    membrane_id=k,
                    specific_capacitance_F_per_m2=ifx.SPECIFIC_CAPACITANCE,
                    population_densities_per_m2={},
                )
                for k in furrows
            ],
        ),
    ]
    if lumen:
        width = 2e-15 * CLEFT_PL / FURROW_AREA_M2  # V_on = w A_on / 2.
        operators.append(
            dict(law=LUMEN2, lumens=[dict(node_id="cleft", source_id="bath_0", gap_width_m=width)])
        )
    operators.append(dict(law=PARTITION, divisions=[block]))
    if bridges:
        operators.append(dict(law=BRIDGE, bridges=bridges))
        raw["experiment"]["bridge_controls"] = (
            [dict(junction_id="bridge_1", start_time=at)] if events else []
        )
    raw["model"]["operators"] = operators
    split = [dict(time=at, rate_m2_per_s=a * rate)] if events else []
    rest = [dict(time=at, rate_m2_per_s=(1 - a) * rate)] if events else []
    stop = [dict(time=at, rate_m2_per_s=0.0)] if events else []
    raw["experiment"]["insertion_controls"] = [
        dict(
            membrane_id="furrow",
            onset_time=onset,
            schedule=[dict(time=0.0, rate_m2_per_s=0.0), dict(time=onset, rate_m2_per_s=rate)]
            + stop,
        ),
        dict(
            membrane_id="furrow_d1",
            onset_time=None,
            schedule=[dict(time=0.0, rate_m2_per_s=0.0)] + split,
        ),
        dict(
            membrane_id="furrow_d2",
            onset_time=None,
            schedule=[dict(time=0.0, rate_m2_per_s=0.0)] + rest,
        ),
    ]
    raw["experiment"]["partition_events"] = (
        [dict(division="first", time=at, carriers=["c1", "c2"])] if events else []
    )
    if injection is not None:
        inject(raw, "d1", injection, at if injection_start is None else injection_start)
    return raw


SECOND_ONSET = 0.003
SECOND = 0.005


def cleft_quartered(
    *,
    at=EVENT,
    second_onset=SECOND_ONSET,
    second=SECOND,
    end=0.006,
    rate=FURROW_RATE,
    bridge=("linear", 0.001),
    injection=None,
):
    """The furrow world through 1 -> 2 -> 4 with second onsets (§4.3, §8.1), as raw.

    The first cleavage is cleft_divided's: the furrow opens at ONSET, cell_0 divides at `at`,
    and the daughters' furrows keep inserting. A bridge closes over 1 ms (linear: d1 and d2
    divide again). Then each daughter d opens a second furrow (furrow2_d) at second_onset, onto
    its own new cleft (cleft2_d) with its own access face to the bath. At `second` each daughter
    divides, and its three patches (old, first furrow, second furrow) split in half. Its
    furrows' rates pass to its daughters' halves. Every cleft is a lumen. Optionally 1 pA goes
    into d1 from its birth until its division. All fractions are 1/2.
    """
    base = ifx.cleft_cell(end=end, cleft_pL=CLEFT_PL)
    base["experiment"]["observation_times"] = [0.0, end]
    for patch in base["model"]["membranes"]:
        patch["pump"] = None
    base["experiment"]["pump_controls"] = []
    raw = cs.frozen_definition(base)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    blocks = [ps.add_division(raw, division_id="first", parent="cell_0", daughters=("d1", "d2"))]
    bridges = []
    if bridge is not None:
        closure, tau, *rest = bridge
        made = ps.add_bridge(
            raw,
            junction_id="bridge_1",
            daughters=("d1", "d2"),
            aperture_m=rest[0] if rest else APERTURE_M,
            diffusivity=diffusivity(raw),
        )
        bridges.append(dict(made, closure=closure, closure_time_s=tau))
    cleft = next(c for c in m["extracellular"] if c["id"] == "cleft")
    furrow = next(p for p in m["membranes"] if p["id"] == "furrow")
    access = next(f for f in m["faces"] if f["id"] == "access")
    control = next(c for c in e["membrane_controls"] if c["membrane_id"] == "furrow")
    for d in ("d1", "d2"):
        node = dict(cleft, id=f"cleft2_{d}", initial_amount_fmol=dict(cleft["initial_amount_fmol"]))
        m["extracellular"].append(node)
        m["membranes"].append(
            dict(
                furrow,
                id=f"furrow2_{d}",
                inside=d,
                outside=f"cleft2_{d}",
                permeability_m_per_s=dict(furrow["permeability_m_per_s"]),
            )
        )
        m["faces"].append(
            dict(
                access,
                id=f"access2_{d}",
                sender=f"cleft2_{d}",
                diffusivity_m2_per_s=dict(access["diffusivity_m2_per_s"]),
            )
        )
        e["membrane_controls"].append(dict(control, membrane_id=f"furrow2_{d}"))
    x["extracellular_capacity"] = len(m["extracellular"])
    x["membrane_capacity"] = len(m["membranes"])
    x["face_capacity"] = len(m["faces"])
    links = ("bridge_1",) if bridges else ()
    for d, kids in (("d1", ("g1", "g2")), ("d2", ("g3", "g4"))):
        blocks.append(
            ps.add_division(raw, division_id=f"second_{d}", parent=d, daughters=kids, bridges=links)
        )
    halves = {"d1": ("g1", "g2"), "d2": ("g3", "g4")}
    schedules = {"furrow": (ONSET, [(0.0, 0.0), (ONSET, rate), (at, 0.0)])}
    for d, kids in halves.items():
        schedules[f"furrow_{d}"] = (None, [(0.0, 0.0), (at, 0.5 * rate), (second, 0.0)])
        schedules[f"furrow2_{d}"] = (
            second_onset,
            [(0.0, 0.0), (second_onset, rate), (second, 0.0)],
        )
        for g in kids:
            schedules[f"furrow_{d}_{g}"] = (None, [(0.0, 0.0), (second, 0.25 * rate)])
            schedules[f"furrow2_{d}_{g}"] = (None, [(0.0, 0.0), (second, 0.5 * rate)])
    width = 2e-15 * CLEFT_PL / FURROW_AREA_M2  # V_on = w A_on / 2 for every cleft.
    operators = [
        ifx.membrane_state(raw),
        dict(
            law=INSERTION2,
            patches=[
                dict(
                    membrane_id=k,
                    specific_capacitance_F_per_m2=ifx.SPECIFIC_CAPACITANCE,
                    population_densities_per_m2={},
                )
                for k in schedules
            ],
        ),
        dict(
            law=LUMEN2,
            lumens=[
                dict(node_id=k, source_id="bath_0", gap_width_m=width)
                for k in ("cleft", "cleft2_d1", "cleft2_d2")
            ],
        ),
        dict(law=PARTITION, divisions=blocks),
    ]
    if bridges:
        operators.append(dict(law=BRIDGE, bridges=bridges))
        e["bridge_controls"] = [dict(junction_id="bridge_1", start_time=at)]
    m["operators"] = operators
    e["insertion_controls"] = [
        dict(
            membrane_id=k,
            onset_time=onset,
            schedule=[dict(time=t, rate_m2_per_s=r) for t, r in changes],
        )
        for k, (onset, changes) in schedules.items()
    ]
    e["partition_events"] = [
        dict(division="first", time=at, carriers=["c1", "c2"]),
        dict(division="second_d1", time=second, carriers=["c11", "c12"]),
        dict(division="second_d2", time=second, carriers=["c21", "c22"]),
    ]
    if injection is not None:
        inject(raw, "d1", injection, at, stop=second)
    return raw


def without_divisions(*, end=0.004):
    """The parent alone with an idle partition (no divisions) and membrane state."""
    raw = cs.frozen_definition(parent(end=end))
    raw["model"]["operators"] = [ifx.membrane_state(raw), dict(law=PARTITION, divisions=[])]
    raw["experiment"]["partition_events"] = []
    return raw


def without_partition(*, end=0.004):
    """The parent with membrane state only (the idle partition's comparison)."""
    raw = cs.frozen_definition(parent(end=end))
    raw["model"]["operators"] = [ifx.membrane_state(raw)]
    return raw


def diffusivity(raw):
    """The cytoplasmic diffusivities of the parent's cytosol at SIGMA_CYT (one obstruction
    factor)."""
    cell = next(c for c in raw["model"]["cells"] if c["id"] == "cell_0")
    cytosol = {s: a / cell["volume_pL"] for s, a in cell["initial_amount_fmol"].items()}
    valence = {s["id"]: s["valence"] for s in raw["model"]["species"]}
    return ps.cytoplasmic_diffusivities(
        SIGMA_CYT, cytosol, FREE_D, valence, raw["model"]["temperature_K"]
    )


class FollowsSplit(Operator):
    """A stub split part whose view follows its split (VIEW_FOLLOWS_SPLIT, as water's does),
    which changes nothing: it provides the declared pump capacity and its half-steps return
    their start state. No registered operator with such a view can run beside a closer in
    version 1 (water provides volume, which the partition refuses), so the composite's step-end
    domain at the view with closers is exercised through this stub."""

    LAW_ID = "stub_follows_split@1"
    SPLIT = True
    RK4 = "split"
    VIEW_FOLLOWS_SPLIT = True
    VIEW_FIELDS = ("pump_capacity",)

    def view(self, state, p, q, *, xp):
        return {"pump_capacity": q.pump_capacity}

    def half_step(self, state, h, control, p, *, xp):
        return state, None


def with_follower(spec):
    """spec's composition with FollowsSplit appended (built directly; the spec does not name
    it, and it owns no state, layout or schedule)."""
    from cells.models import pump_composite, pump_composite_adapter
    from cells.models.operators import OPERATORS

    operators = tuple(OPERATORS[d.law] for d in spec.model.operators)
    return pump_composite.Composition(pump_composite_adapter, (*operators, FollowsSplit()))
