"""Stage A of FR-3's milestone 1: site_occupancy@1's contract fit, in NumPy (no compile).

docs/SITE_OCCUPANCY_DESIGN.md §1, §2, §4.3, §6.2; criteria A1 to A5 in
/mnt/workspaces/Cells/site-occupancy-m1-20261115-01/HANDOFF.md, fixed before any code. The operator
is registered for these tests only (monkeypatch), since it is registered in OPERATORS only with its
half-step (stage B):
* A1, every refusal of §6.2 fires with its reason;
* A2, the declaration round-trips;
* A3, the binding layout: S = alpha nu N / N_f, B0 = theta0 S, R0 = S - B0, ln(K_d / 1 mM), the
  facing and receiving indices, and the component map against hand-built cases;
* A4, identities are metadata: a catalogue reference or a functional unit changes no binding;
* A5, the contract: check_declarations admits it, the field map has one owner per row and the
  ACCEPTS_WRITES wiring with no writer, and no view, mask or capacitance is provided, so an
  occupancy-only composition has no field inputs (ARCHITECTURE.md: ownership is separate from
  solver invalidation).
"""

import copy
import math

import numpy as np
import pytest

from cells.core import pump_composite_spec as cs
from cells.core.specs import ConfigError, parse_spec
from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.models.operators import OPERATORS
from cells.models.operators import site_occupancy as so
from cells.models.operators.contract import check_declarations
from cells.models.registry import get_model
from validation.tissue import compartment_fixtures as cfx
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import site_occupancy_fixtures as sfx


@pytest.fixture(autouse=True)
def registered(monkeypatch):
    monkeypatch.setitem(OPERATORS, so.LAW_ID, so.SiteOccupancy())


def world(populations=None, **kwargs):
    return sfx.face_free_sites(populations, **kwargs)


def block(raw):
    return next(op for op in raw["model"]["operators"] if op["law"] == so.LAW_ID)


def changed(raw, edit):
    out = copy.deepcopy(raw)
    edit(out)
    return out


def two_cells(populations, *, replaced=False):
    """Two cells on the bath joined by a gated junction j0; cell_1 replaced at 5 ms if asked."""
    raw = fx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=(("ecs_0", 1.0),),
        contacts=(("contact_0", "cell_0", "ecs_0"),),
        faces=(),
        junctions=(("j0", "cell_0", "cell_1"),),
        end=0.01,
        trace_mM=sfx.TRACE_mM,
        concentrations_mM=dict(cell_0=1e-3, cell_1=1e-3, ecs_0=1e-3),
    )
    if replaced:
        template = fx.template(raw, "cell_1", "T", s_mM=1e-3)
        raw = fx.with_replacement(raw, [template], [(0.005, "cell_1", "T", "c1_new")])
    return sfx.with_site_occupancy(raw, populations)


# ------------------------------------------------------------------ A1, the refusals


def _pop(**changes):
    return [sfx.population(**changes)]


def _unlisted(raw):
    block(raw)["populations"][0]["ligand"] = "Na"


def _extra_key(raw):
    block(raw)["populations"][0]["colour"] = "red"


def _permeant(raw):
    next(p for p in raw["model"]["membranes"] if p["id"] == "wall_cell_0")["permeability_m_per_s"][
        sfx.LIGAND
    ] = 1e-12


def _schedule(edit):
    def apply(raw):
        edit(raw["experiment"]["site_controls"])

    return apply


REFUSALS = {
    "a charged ligand": (lambda: world(ligands=[sfx.ligand(species="K")]), "neutral species only"),
    "an undeclared ligand": (lambda: world(ligands=[sfx.ligand(species="X")]), "does not declare"),
    "a permeant ligand": (lambda: changed(world(), _permeant), "zero membrane, junction"),
    "a node below the trace": (
        lambda: world(ligands=[sfx.ligand(trace_mM=2e-3)]),
        "below its declared trace",
    ),
    "a trace above 1e-6 K_d": (
        lambda: world(_pop(k_on=1e7, k_off=1.0)),
        "exceeds 1e-06 K_d",
    ),
    "an unknown patch": (lambda: world(_pop(patch="nope")), "unknown patch"),
    "an unknown contact": (lambda: world(_pop(contact="j9", side="first")), "unknown contact"),
    "a face not outside or inside": (lambda: world(_pop(face="up")), "faces one of"),
    "an outward population facing the held bath": (
        lambda: world(_pop(patch="wall_cell_0", face="outside")),
        "faces the held bath",
    ),
    "copies <= 0": (lambda: world(_pop(copies=0.0)), "copies must be >"),
    "sites per copy not an int": (lambda: world(_pop(sites_per_copy=1.5)), "positive integer"),
    "sites per copy 0": (lambda: world(_pop(sites_per_copy=0)), "positive integer"),
    "alpha 0": (lambda: world(_pop(alpha=0.0)), "lies in \\(0, 1\\]"),
    "alpha above 1": (lambda: world(_pop(alpha=1.5)), "lies in \\(0, 1\\]"),
    "an unlisted ligand": (lambda: changed(world(), _unlisted), "unlisted ligand"),
    "initial occupancy below 0": (lambda: world(_pop(theta0=-0.1)), "lies in \\[0, 1\\]"),
    "initial occupancy above 1": (lambda: world(_pop(theta0=1.1)), "lies in \\[0, 1\\]"),
    "k_on <= 0": (lambda: world(_pop(k_on=0.0)), "k_on must be >"),
    "k_off <= 0": (lambda: world(_pop(k_off=0.0)), "k_off must be >"),
    "k_int < 0": (lambda: world(_pop(k_int=-1.0)), "internalisation rate must be >="),
    "internalisation on an inward patch": (
        lambda: world(_pop(patch="wall_cell_0", face="inside", k_int=0.1)),
        "only an outward-facing patch",
    ),
    "a destination other than cell": (
        lambda: world(_pop(k_int=0.1, destination="lysosome")),
        "destination is one of",
    ),
    "RK4": (lambda: world(solver="rk4", dt=1e-4, end=1e-3), "refuses RK4"),
    "an unknown key": (lambda: changed(world(), _extra_key), "unknown"),
    "a population twice": (lambda: world([sfx.population(), sfx.population()]), "twice"),
    "a missing route schedule": (
        lambda: changed(world(_pop(k_int=0.1)), _schedule(lambda c: c.pop())),
        "missing",
    ),
    "a schedule not from 0": (
        lambda: changed(world(), _schedule(lambda c: c[0]["schedule"][0].update(time=0.002))),
        "starts at time 0",
    ),
    "a change off the grid": (
        lambda: changed(
            world(),
            _schedule(lambda c: c[0]["schedule"].append(dict(time=0.0015, multiplier=1.0))),
        ),
        "exact multiple of dt",
    ),
    "a change beyond the horizon": (
        lambda: changed(
            world(), _schedule(lambda c: c[0]["schedule"].append(dict(time=1.0, multiplier=1.0)))
        ),
        "outside the horizon",
    ),
    "a negative multiplier": (
        lambda: changed(world(), _schedule(lambda c: c[0]["schedule"][0].update(multiplier=-1.0))),
        "must be >= 0",
    ),
    "a schedule for an undeclared route": (
        lambda: changed(
            world(),
            _schedule(
                lambda c: c.append(
                    dict(
                        population="r0",
                        route="internalisation",
                        schedule=[dict(time=0.0, multiplier=1.0)],
                    )
                )
            ),
        ),
        "names no declared route",
    ),
}


@pytest.mark.parametrize("name", sorted(REFUSALS))
def test_definition_refusals(name):
    build, message = REFUSALS[name]
    with pytest.raises(ConfigError, match=message):
        parse_spec(build())


def test_populations_on_a_replaced_slot_are_refused_and_elsewhere_admitted():
    inward = sfx.population("w1", patch="wall_cell_1", face="inside")
    with pytest.raises(ConfigError, match="replaces; version 1 has no occupant rule"):
        parse_spec(two_cells([inward], replaced=True))
    on_contact = sfx.population("k0", contact="j0", side="first")
    with pytest.raises(ConfigError, match="replaces; version 1 has no occupant rule"):
        parse_spec(two_cells([on_contact], replaced=True))
    parse_spec(two_cells([sfx.population("w0", patch="wall_cell_0", face="inside")], replaced=True))
    parse_spec(two_cells([on_contact]))  # A contact population, no replacement.


def test_internalisation_from_a_compartment_is_refused():
    raw = world(_pop(k_int=0.1))
    raw = cfx.with_compartments(raw, [cfx.compartment()])
    with pytest.raises(ConfigError, match="internalises from compartment"):
        parse_spec(raw)


def test_identities_must_agree_with_d150_in_either_order():
    raw = world()
    catalogue = dict(catalogue="uniprot", entry="P00001")
    other = fx.identity(catalogue=catalogue, evidence="model")
    exchanged = fx.with_exchange(
        raw,
        [("sec", "contact_0", "export", "first_order")],
        [("sec", "cell_0", [(0.0, 0.1)])],
        species=other,
    )
    with pytest.raises(ConfigError, match="another identity"):
        parse_spec(exchanged)
    first = copy.deepcopy(exchanged)
    ops = first["model"]["operators"]
    first["model"]["operators"] = [ops[1], ops[0]]
    with pytest.raises(ConfigError, match="another identity"):
        parse_spec(first)
    agreeing = copy.deepcopy(exchanged)
    block(agreeing)["species"] = [sfx.ligand(catalogue=catalogue, evidence="model")]
    parse_spec(agreeing)


def test_the_species_cap_is_checked():
    raw = world()
    for k in range(13):  # 4 + 13 = 17 species.
        name = f"N{k}"
        raw["model"]["species"].append(dict(id=name, valence=0))
        for node in (*raw["model"]["cells"], *raw["model"]["extracellular"]):
            node["initial_amount_fmol"][name] = 1e-3 * node["volume_pL"]
        for patch in raw["model"]["membranes"]:
            patch["permeability_m_per_s"][name] = 0.0
        raw["execution"]["material_balance_atol_fmol"][name] = 1e-10
    with pytest.raises(ConfigError, match="at most 16 species"):
        parse_spec(raw)


STATE, WATER = "membrane_entity_state@1", "ideal_osmosis_linear_compliance_water@1"
VIEW_REFUSED = {
    "water": (WATER,),
    "insertion@1": (STATE, "scheduled_membrane_insertion@1"),
    "insertion@2": (STATE, "scheduled_membrane_insertion@2"),
    "the partition": (STATE, "isopotential_partition@1"),
    "lumen@1": (STATE, "scheduled_membrane_insertion@1", "restricted_cleft_lumen@1"),
}


@pytest.mark.parametrize("name", sorted(VIEW_REFUSED))
def test_the_structure_check_refuses_providers_and_closers_of_what_it_reads(name):
    laws = VIEW_REFUSED[name]
    for order in ((*laws, so.LAW_ID), (so.LAW_ID, *laws)):
        errors = pump_composite.structure_errors(adapter, tuple(OPERATORS[k] for k in order))
        assert any(e.startswith(so.LAW_ID + " reads") for e in errors), (order, errors)


def test_the_structure_check_admits_its_neighbours():
    for laws in (
        ("scheduled_species_exchange@1",),
        ("scheduled_species_turnover@1",),
        ("local_species_reactions@1",),
        ("species_regulated_availability@1",),
        ("electrode_current_injection@1",),
        ("scheduled_cell_replacement@1",),
        (STATE,),
    ):
        for order in ((*laws, so.LAW_ID), (so.LAW_ID, *laws)):
            errors = pump_composite.structure_errors(adapter, tuple(OPERATORS[k] for k in order))
            assert errors == [], (order, errors)


# ------------------------------------------------------------------ A2 to A4


def test_the_declaration_round_trips():
    spec = parse_spec(world([sfx.population(k_int=0.1, theta0=0.2), sfx.population("r1")]))
    assert parse_spec(cs.to_dict(spec)) == spec


def layout(raw):
    spec = parse_spec(raw)
    _, p = get_model(spec.model).initial_values(spec)
    return spec, p


def test_the_binding_layout():
    pops = [
        sfx.population("o", copies=2e5, sites_per_copy=3, alpha=0.25, theta0=0.4, k_int=0.2),
        sfx.population("i", patch="wall_cell_0", face="inside", k_on=2e3, k_off=0.5),
    ]
    spec, p = layout(world(pops))
    s = np.asarray(p.site_capacity_fmol)
    assert s[0] == 0.25 * 3 * 2e5 / so.SITES_PER_FMOL
    assert s[1] == 0.5 * 1 * 1e5 / so.SITES_PER_FMOL
    assert np.asarray(p.site_bound_anchor_fmol)[0] == 0.4 * s[0]
    assert np.asarray(p.site_free_anchor_fmol)[0] == s[0] - 0.4 * s[0]
    assert np.asarray(p.site_standard_RT)[1] == math.log(0.5 / 2e3)
    assert list(np.asarray(p.site_facing_kind)) == [so.OUTSIDE, so.CELL]
    outside = [c.id for c in spec.model.extracellular]
    assert list(np.asarray(p.site_facing_node)) == [outside.index("ecs_0"), 0]
    assert list(np.asarray(p.site_internalises)) == [True, False]
    assert list(np.asarray(p.site_internalisation_rate)) == [0.2, 0.0]


def test_the_component_map():
    # Two populations sharing a node are one component.
    _, p = layout(world([sfx.population("a"), sfx.population("b")]))
    assert list(np.asarray(p.site_component)) == [0, 0]
    # An outward and an inward population with no internalisation: two components.
    _, p = layout(
        world([sfx.population("a"), sfx.population("b", patch="wall_cell_0", face="inside")])
    )
    assert list(np.asarray(p.site_component)) == [0, 1]
    # Internalisation into the cell joins them.
    pops = [sfx.population("a", k_int=0.1), sfx.population("b", patch="wall_cell_0", face="inside")]
    _, p = layout(world(pops))
    assert list(np.asarray(p.site_component)) == [0, 0]


def test_identities_are_metadata():
    plain = cfx.bindings(world())
    for edit in (
        dict(catalogue=dict(catalogue="uniprot", entry="P00002")),
        dict(unit="site_unit_z"),
    ):
        other = cfx.bindings(world([sfx.population(**edit)]))
        assert cfx.same_bindings(plain, other) == []


# ------------------------------------------------------------------ A5, the contract


def test_the_contract_fit():
    assert check_declarations(so.SiteOccupancy) is so.SiteOccupancy
    spec = parse_spec(world([sfx.population(k_int=0.1)]))
    model = get_model(spec.model)
    state = model.FIELD_MAP["state"]
    for name in so.STATE_AXES:
        assert state[name]["owner"] == so.LAW_ID and state[name]["writers"] == [], name
    assert so.LAW_ID in state["amount_increment"]["writers"]
    assert so.LAW_ID in state["extracellular_amount_increment"]["writers"]
    assert set(so.SiteOccupancy.ACCEPTS_WRITES) == {
        "site_free_increment_fmol",
        "site_bound_increment_fmol",
    }
    assert not so.SiteOccupancy.VIEW_FIELDS and not so.SiteOccupancy.CLOSES
    assert not model.field_inputs  # Occupancy only: no field refresh (D174).


def test_no_population_is_statically_idle():
    spec = parse_spec(world([]))
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    op = next(o for o in model.operators if o.LAW_ID == so.LAW_ID)
    assert op.statically_idle(p)
