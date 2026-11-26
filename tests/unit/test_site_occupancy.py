"""Stage A of FR-3's milestone 1: cells.operator.site_occupancy@1's contract fit, in NumPy (no compile).

docs/SITE_OCCUPANCY_DESIGN.md §1, §2, §4.3, §6.2; criteria A1 to A5 in
/mnt/workspaces/Cells/site-occupancy-m1-20261115-01/HANDOFF.md, fixed before any code:
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

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.operators import OPERATORS, species_common
from cells.operators import site_occupancy as so
from cells.operators.contract import check_declarations
from cells.registry.models import get_model
from validation.tissue import bath_schedule_fixtures as bfx
from validation.tissue import compartment_fixtures as cfx
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import site_occupancy_fixtures as sfx
from validation.tissue import species_reactions_fixtures as rfx


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
    # FR-23 (D244): the bath at the trace, halved at 10 ms, a step the bath schedule's own rule
    # admits (neutral, down, ratio 2): only the sites' trace rule refuses it.
    "a scheduled dose below the trace": (
        lambda: bfx.with_bath_schedule(
            world(), ["bath"], bfx.CARGO, [(bfx.on_grid(0.01, 1e-3), ["bath"], {"cargo": -5e-13})]
        ),
        "scheduled bath bath from 0.01 s, below its declared trace",
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
    "internalisation on a contact": (
        lambda: two_cells([sfx.population("k0", contact="j0", side="first", k_int=0.1)]),
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
        "on the clock's grid",
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


# FR-26 (D244, W): cells.operator.site_occupant_replacement@1 on replaced_sites' world (cell_1 replaced at 5 ms
# from template T), with an outward population o1 on contact_1 and an inward i1 on wall_cell_1,
# both on cell_1, and o0 on cell_0's contact_0.
W_POPULATIONS = (
    ("o1", dict(patch="contact_1", theta0=0.5)),
    ("i1", dict(patch="wall_cell_1", face="inside", theta0=0.3)),
    ("o0", dict(patch="contact_0", theta0=0.4)),
)
W_TEMPLATE = {"o1": (0.1, 2.0, None), "i1": (0.9, 0.5, None)}


def w_world(occupants=W_TEMPLATE, *, populations=W_POPULATIONS, **kwargs):
    pops = [sfx.population(pid, **dict(attrs)) for pid, attrs in populations]
    return sfx.replaced_sites(pops, occupants, **kwargs)


def _w_edit(edit):
    def make():
        raw = w_world()
        edit(raw)
        return raw

    return make


def _w_block(raw):
    return next(b for b in raw["model"]["operators"] if b["law"] == so.OCCUPANT_LAW)


def _late_founder_change(raw):
    for c in raw["experiment"]["site_controls"]:
        if c["population"] == "o1":
            c["schedule"].append(dict(time=0.007, multiplier=0.5))


def _donor_copy(raw):
    raw["experiment"]["replacement_events"][0].update(
        newcomer="donor_copy", template=None, donor="cell_0"
    )


def _w_first(raw):
    ops = raw["model"]["operators"]
    w = ops.pop()
    ops.insert(1, w)  # After replacement@1, before the site operator.


REFUSALS.update(
    {
        "W: a template that is not a replacement template": (
            _w_edit(lambda r: _w_block(r)["templates"][0].update(template_id="U")),
            "declares U, not a replacement template",
        ),
        "W: a population not on a slot its newcomers fill": (
            lambda: w_world({**W_TEMPLATE, "o0": (0.2, 1.0, None)}),
            "names o0, not a population on a slot its newcomers fill",
        ),
        "W: a newcomer without an arrival occupancy": (
            lambda: w_world({"o1": (0.1, 2.0, None)}),
            "declares no arrival occupancy for i1",
        ),
        "W: a donor copy onto a slot with populations": (
            _w_edit(_donor_copy),
            "a donor copy onto cell_1, which holds site populations, is version 1.1",
        ),
        "W: an internalisation multiplier without the route": (
            lambda: w_world({**W_TEMPLATE, "o1": (0.1, 2.0, 1.0)}),
            "an internalisation multiplier exactly when it internalises",
        ),
        "W: before the site operator": (
            _w_edit(_w_first),
            "requires cells.operator.site_occupancy@1 before it",
        ),
        "W: without replacement@1": (
            lambda: sfx.with_occupant(
                sfx.face_free_sites([sfx.population("r0")]), {"T": {"r0": (0.1, 1.0, None)}}
            ),
            "requires cells.operator.scheduled_cell_replacement@1 before it",
        ),
        "W: an empty newcomer": (
            lambda: w_world({**W_TEMPLATE, "o1": (0.0, 2.0, None)}),
            "occupancy of o1 lies in \\(0, 1\\) in version 1",
        ),
        "W: a full newcomer": (
            lambda: w_world({**W_TEMPLATE, "i1": (1.0, 0.5, None)}),
            "occupancy of i1 lies in \\(0, 1\\) in version 1",
        ),
        "W: a newcomer within the capacity's rounding of empty": (
            lambda: w_world({**W_TEMPLATE, "o1": (1e-17, 2.0, None)}),
            "occupancy 1e-17 of o1 leaves its bound sites within 4 ulps of its capacity",
        ),
        "W: a newcomer within the capacity's rounding of full": (
            lambda: w_world({**W_TEMPLATE, "i1": (1 - 2**-53, 0.5, None)}),
            "of i1 leaves its free sites within 4 ulps of its capacity",
        ),
        "W: a founder's change after its death": (
            _w_edit(_late_founder_change),
            "changes at 0.007 s, after its founder's death at 0.005 s",
        ),
    }
)


@pytest.mark.parametrize("name", sorted(REFUSALS))
def test_definition_refusals(name):
    build, message = REFUSALS[name]
    with pytest.raises(ConfigError, match=message):
        parse_spec(build())


def test_populations_on_a_replaced_slot_are_refused_and_elsewhere_admitted():
    """FR-26 (D244, W): a patch population on a replaced slot is admitted with
    cells.operator.site_occupant_replacement@1 and refused without it, naming it; a contact population incident
    to a replaced slot stays refused."""
    inward = sfx.population("w1", patch="wall_cell_1", face="inside")
    with pytest.raises(ConfigError, match="its occupants need cells.operator.site_occupant_replacement@1"):
        parse_spec(two_cells([inward], replaced=True))
    parse_spec(sfx.with_occupant(two_cells([inward], replaced=True), {"T": {"w1": (0.2, 1, None)}}))
    on_contact = sfx.population("k0", contact="j0", side="first")
    with pytest.raises(ConfigError, match="a contact population there is refused in version 1"):
        parse_spec(two_cells([on_contact], replaced=True))
    parse_spec(two_cells([sfx.population("w0", patch="wall_cell_0", face="inside")], replaced=True))
    parse_spec(two_cells([on_contact]))  # A contact population, no replacement.


def _w_event(raw, time=0.005):
    """(spec, model, the bound state, p, the control at `time`, the state after the event maps)."""
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [time])))
    after = state
    for op in model.events:
        after, ok = op.event(after, control, p, xp=np)
        assert ok is None or bool(ok)
    return spec, model, state, p, control, after


def _w_energy(spec, model, row, p):
    tol = np.asarray(spec.execution.material_balance_atol_fmol)
    rtol = model.ENERGY_RTOL[spec.execution.solver]
    _, limits = model.ledger_limits(row, p, tol, rtol, steps=1, magnitudes=model.magnitudes(row, p))
    return float(model.inner_balances(row, p)["energy"]), float(limits[6])


def test_w_resets_a_replaced_slots_populations_from_the_newcomers_template():
    """FR-26's event rows (D244, W; NumPy, no world compiled, about 1 s). At t_e the newcomer's
    populations hold B = theta' S and R = S - B, to the anchored increments' ulp; the other
    cell's population and the facing node keep their bits; W's departed is the bound amount
    before and its arrived theta' S; its jump is the owner's own site free energy's change; the
    owner's ledgers close with W's external terms (dropped, the bound ledger misses by arrived -
    departed) and @3's energy ledger with its term, at the event's own step, for a nearly empty
    and a nearly full newcomer of 60 fmol capacity too (theta' of exactly 0 or 1 is refused).
    The multipliers switch from the founder's schedule to the template's at t_e. A count the
    state has not reached refuses the step; nothing more is due at the same control."""
    spec, model, state, p, control, after = _w_event(w_world())
    sites = next(o for o in model.operators if o.LAW_ID == so.LAW_ID)
    w = next(o for o in model.operators if o.LAW_ID == so.OCCUPANT_LAW)
    s = np.asarray(p.site_capacity_fmol)
    before = np.asarray(p.site_bound_anchor_fmol) + np.asarray(state.site_bound_increment_fmol)
    bound = np.asarray(p.site_bound_anchor_fmol) + np.asarray(after.site_bound_increment_fmol)
    free = np.asarray(p.site_free_anchor_fmol) + np.asarray(after.site_free_increment_fmol)
    theta = np.asarray([0.1, 0.9])  # The anchored increments hold them to an ulp or two.
    assert bound[:2] == pytest.approx(theta * s[:2], rel=4 * np.finfo(float).eps, abs=0)
    assert free[:2] == pytest.approx(s[:2] - theta * s[:2], rel=4 * np.finfo(float).eps, abs=0)
    for name, axes in so.STATE_AXES.items():  # o0, on cell_0, keeps its bits.
        if axes == ["site_population"]:
            assert np.asarray(getattr(after, name))[2] == np.asarray(getattr(state, name))[2]
    ecs = [c.id for c in spec.model.extracellular].index("ecs_0")
    assert (
        np.asarray(after.extracellular_amount_increment)[:, ecs].tobytes()
        == np.asarray(state.extracellular_amount_increment)[:, ecs].tobytes()
    )
    assert np.asarray(after.site_departed_fmol)[:2].tobytes() == before[:2].tobytes()
    assert np.asarray(after.site_arrived_fmol)[:2].tobytes() == (theta * s[:2]).tobytes()
    g0, _ = so.site_energy(state, p, xp=np)
    g1, _ = so.site_energy(after, p, xp=np)
    jump = float(np.sum(after.site_replacement_free_energy_pJ))
    assert jump == pytest.approx(g1 - g0, rel=1e-12, abs=1e-18)
    ledgers = model._own_ledgers(sites, after, p, xp=np)
    assert not np.any(ledgers["site_bound_entity"]) and not np.any(ledgers["site_moiety_entity"])
    planted = sites.own_ledgers(after, p, xp=np)["site_bound_entity"]  # W's term dropped.
    expected = np.asarray(after.site_arrived_fmol) - np.asarray(after.site_departed_fmol)
    assert planted.tobytes() == expected.tobytes() and np.any(planted)
    residual, bound_e = _w_energy(spec, model, after, p)
    assert abs(residual) <= 1e-3 * bound_e
    assert abs(residual + jump) > 1e3 * bound_e  # Without W's term the ledger fails.
    assert np.asarray(control.site_binding_multiplier).tolist() == [2.0, 0.5, 1.0]
    early = cs.control_values(spec, [0.004])
    names = list(model.CONTROL_TYPE._fields)
    assert early[names.index("site_binding_multiplier")][0].tolist() == [1.0, 1.0, 1.0]
    again, ok = w.event(after, control, p, xp=np)
    assert ok and all(
        np.asarray(x).tobytes() == np.asarray(y).tobytes()
        for x, y in zip(again, after, strict=True)
    )
    stale = control._replace(site_replacement_count=control.site_replacement_count + 1)
    assert not bool(w.event(state, stale, p, xp=np)[1])
    theta = np.asarray(control.site_arrival_occupancy).copy()
    theta[0] = (
        1e-17  # Below o1's anchor rounding: the definition refuses it; the event fails closed.
    )
    assert not bool(w.event(state, control._replace(site_arrival_occupancy=theta), p, xp=np)[1])
    big = (("o1", dict(patch="contact_1", theta0=0.5, copies=60 * so.SITES_PER_FMOL, alpha=1.0)),)
    for theta_new in (1e-9, 1.0 - 1e-9):
        raw = w_world({"o1": (theta_new, 1.0, None)}, populations=big)
        spec2, model2, _, p2, _, after2 = _w_event(raw)
        residual, bound_e = _w_energy(spec2, model2, after2, p2)
        assert np.isfinite(residual) and abs(residual) <= bound_e, (theta_new, residual, bound_e)


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


def test_identities_must_agree_with_d152_in_either_order():
    """D152's reaction network declares S with a catalogue reference; the sites declare S without
    one (refused), or with the same one (admitted), with either operator first."""
    tag = dict(catalogue=dict(catalogue="uniprot", entry="P00001"), evidence="model")
    raw = rfx.enzyme_network()
    network = next(op for op in raw["model"]["operators"] if op["law"] == rfx.REACTIONS)
    next(s for s in network["species"] if s["id"] == sfx.LIGAND).update(tag)
    sited = sfx.with_site_occupancy(raw, [sfx.population("out")])
    agreeing = copy.deepcopy(sited)
    block(agreeing)["species"] = [sfx.ligand(**tag)]
    for first in (False, True):
        refused, admitted = copy.deepcopy(sited), copy.deepcopy(agreeing)
        if first:
            for spec in (refused, admitted):
                spec["model"]["operators"].reverse()
        with pytest.raises(ConfigError, match="another identity than cells.operator.local_species_reactions@1"):
            parse_spec(refused)
        parse_spec(admitted)


def test_the_stationary_analysis_does_not_admit_the_composite():
    from cells.analysis import stationary

    with pytest.raises(ConfigError, match="not cells.model.resolved_pump_composite@1"):
        stationary.problem(parse_spec(world()))


def test_the_species_cap_is_checked(monkeypatch):
    """Its call to the cap (1,024 since FR-43 / D315), set to 16 here so the world stays small."""
    monkeypatch.setattr(species_common, "MAX_SPECIES", 16)
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


STATE, WATER = "cells.operator.membrane_entity_state@1", "cells.operator.ideal_osmosis_linear_compliance_water@1"
VIEW_REFUSED = {
    "water": (WATER,),
    "insertion@1": (STATE, "cells.operator.scheduled_membrane_insertion@1"),
    "insertion@2": (STATE, "cells.operator.scheduled_membrane_insertion@2"),
    "the partition": (STATE, "cells.operator.isopotential_partition@1"),
    "lumen@1": (STATE, "cells.operator.scheduled_membrane_insertion@1", "cells.operator.restricted_cleft_lumen@1"),
    "lumen@2": (STATE, "cells.operator.scheduled_membrane_insertion@2", "cells.operator.restricted_cleft_lumen@2"),
}


@pytest.mark.parametrize("name", sorted(VIEW_REFUSED))
def test_the_structure_check_refuses_providers_and_closers_of_what_it_reads(name):
    laws = VIEW_REFUSED[name]
    for order in ((*laws, so.LAW_ID), (so.LAW_ID, *laws)):
        errors = pump_composite.structure_errors(adapter, tuple(OPERATORS[k] for k in order))
        # The refusal names the provider or closer itself, not only a law it requires.
        assert any(e.startswith(so.LAW_ID + " reads") and laws[-1] in e for e in errors), (
            order,
            errors,
        )


def test_the_structure_check_admits_its_neighbours():
    for laws in (
        ("cells.operator.scheduled_species_exchange@1",),
        ("cells.operator.scheduled_species_turnover@1",),
        ("cells.operator.local_species_reactions@1",),
        ("cells.operator.species_regulated_availability@1",),
        ("cells.operator.electrode_current_injection@1",),
        ("cells.operator.scheduled_cell_replacement@1",),
        ("cells.operator.scheduled_bath_composition@1",),  # FR-23 (D244): both declare their slots (door S).
        (STATE,),
    ):
        for order in ((*laws, so.LAW_ID), (so.LAW_ID, *laws)):
            errors = pump_composite.structure_errors(adapter, tuple(OPERATORS[k] for k in order))
            assert errors == [], (order, errors)


def test_a_bath_dose_beside_occupied_sites_books_the_dose_and_leaves_the_sites():
    """FR-23's acceptance at the event boundary (D244), in NumPy with no compile, about a second.
    The bath schedule's dosed world: the held bath joined by face_0 to the finite node ecs_0, which
    an occupied outward population on cell_0's contact_0 faces, and a x10 dose of the ligand at the
    bath at t_e (a measured step). Admitted with the sites' reads scoped to ecs_0; the event maps at
    t_e book the dose as the held content's change and leave every site field bitwise."""
    t_e, offset = bfx.on_grid(0.02, 1e-3), 9e-3
    raw = bfx.dosed_world(c0=1e-3, trace_mM=sfx.TRACE_mM, end=0.05)
    raw = sfx.with_site_occupancy(raw, [sfx.population("r0", theta0=0.5)])
    spec = parse_spec(
        bfx.with_bath_schedule(raw, ["bath"], bfx.CARGO, [(t_e, ["bath"], {"cargo": offset})])
    )
    sites = next(op for op in OPERATORS.values() if op.LAW_ID == so.LAW_ID)
    outside = [c.id for c in spec.model.extracellular]
    declaration = next(d for op, d, _ in cs.entries(spec) if op.LAW_ID == so.LAW_ID)
    assert sites.read_slots(spec, declaration) == dict.fromkeys(
        so.SiteOccupancy.SCOPED_READS, (outside.index("ecs_0"),)
    )
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [t_e])))
    after = state
    for op in model.events:
        after, ok = op.event(after, control, p, xp=np)
        assert ok is None or bool(ok)
    for name in so.STATE_AXES:  # Occupied sites keep their bound material across the event.
        assert (
            np.asarray(getattr(after, name)).tobytes() == np.asarray(getattr(state, name)).tobytes()
        )
    s, bath = list(spec.model.species_ids).index(fx.SPECIES), outside.index("bath")
    change = (
        np.asarray(after.bath_held_amount_fmol)[s, bath]
        - np.asarray(state.bath_held_amount_fmol)[s, bath]
    )
    dose = np.asarray(after.bath_dose_fmol)[s, bath]
    assert dose == change  # The bath records the dose: its held content's change, bit for bit.
    assert dose == pytest.approx(
        spec.model.extracellular[bath].volume_pL * offset, rel=1e-15, abs=0
    )


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
    # R3's readable quantities (FR-24) at the bound state, and theta at saturation: exactly 1 though
    # B exceeds S by rounding there (B + R is S to the moiety's rounding).
    op = OPERATORS[so.LAW_ID]
    state, _ = get_model(spec.model).initial_values(spec)
    q = op.quantities(state, p, xp=np)
    b = np.asarray(p.site_bound_anchor_fmol)
    assert list(q["site_occupied_fraction"]) == list(b / (b + np.asarray(p.site_free_anchor_fmol)))
    assert q["site_occupied_fmol"].tobytes() == b.tobytes() and q["site_capacity_fmol"] is s
    full = state._replace(
        site_free_increment_fmol=-np.asarray(p.site_free_anchor_fmol),
        site_bound_increment_fmol=np.asarray(p.site_free_anchor_fmol) * (1 + 1e-15),
    )
    assert list(op.quantities(full, p, xp=np)["site_occupied_fraction"]) == [1.0, 1.0]


def test_a_contact_population_faces_the_cell_on_its_side():
    """A contact's first side faces the junction's sender, its second the receiver (§1.1); two
    populations on one contact face different cells, so they are two components."""
    pops = [
        sfx.population("k0", contact="j0", side="first"),
        sfx.population("k1", contact="j0", side="second"),
    ]
    spec, p = layout(two_cells(pops))
    cells = [c.id for c in spec.model.cells]
    assert list(np.asarray(p.site_facing_kind)) == [so.CELL, so.CELL]
    assert list(np.asarray(p.site_facing_node)) == [cells.index("cell_0"), cells.index("cell_1")]
    assert list(np.asarray(p.site_internalises)) == [False, False]
    assert list(np.asarray(p.site_component)) == [0, 1]


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


# ------------------------------------------------------------------ FR-28: a node's own sites


def _node_sites_refusals():
    """FR-28's refusals (D268, option A; docs/NODE_SURFACE_SITES_DESIGN.md §7), each a world."""
    from validation.tissue import wash_schedule_fixtures as wfx

    def edited(edit):
        raw = wfx.well(wall="node")
        sites = next(o for o in raw["model"]["operators"] if o["law"] == so.LAW_ID)
        edit(next(q for q in sites["populations"] if q["id"] == "wall_sites"))
        return raw

    def internalising(q):
        q["internalisation"] = dict(rate_per_s=0.01, destination="cell")

    return {
        "a held bath": (lambda: edited(lambda q: q.update(owner=dict(node="bath"))), "held bath"),
        "an unknown node": (
            lambda: edited(lambda q: q.update(owner=dict(node="pond"))),
            "is unknown",
        ),
        "a cell as a node": (
            lambda: edited(lambda q: q.update(owner=dict(node="specimen"))),
            "is a cell, whose sites sit on its patches",
        ),
        "a face beside the node": (
            lambda: edited(lambda q: q.update(owner=dict(node="well", face="outside"))),
            "no face or side beside it",
        ),
        "an internalisation route": (
            lambda: edited(internalising),
            "only an outward-facing patch population may",
        ),
    }


def test_a_nodes_own_sites_are_the_stand_ins_layout_and_round_trip():
    """FR-28 (D268, option A; host only, about 1 s): the review's well with its wall owned by the
    node, against the same well with the review's stand-in cell. Every site layout array is
    bitwise the same, since the layout reads the facing pool, never the owner; the declaration
    round-trips; the summary records the owner kind node; the population belongs to no cell. Each
    refusal of the note's §7 fires, @2's included."""
    from validation.tissue import wash_schedule_fixtures as wfx

    node, stand_in = (parse_spec(wfx.well(wall=w)) for w in ("node", "stand-in"))
    for spec in (node, stand_in):
        assert parse_spec(cs.to_dict(spec)) == spec
    p_node = get_model(node.model).initial_values(node)[1]
    p_stand = get_model(stand_in.model).initial_values(stand_in)[1]
    fields = [f for f in type(p_node)._fields if f.startswith("site_")]
    assert len(fields) > 10
    for f in fields:
        a, b = np.asarray(getattr(p_node, f)), np.asarray(getattr(p_stand, f))
        assert a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes(), f
    sites = next(d for o, d, _ in cs.entries(node) if o.LAW_ID == so.LAW_ID)
    wall = next(q for q in sites.populations if q.id == "wall_sites")
    assert (wall.owner_kind, wall.owner_id, wall.facing) == ("node", "well", so.SURFACE)
    assert so.population_cell(node.model, wall) is None
    owner = next(e for e in so.identity_block(sites)["site_populations"] if e["id"] == "wall_sites")
    assert owner["owner"] == dict(kind="node", id="well", facing=so.SURFACE)
    for build, message in _node_sites_refusals().values():
        with pytest.raises(ConfigError, match=message):
            parse_spec(build())
    from validation.tissue import regulated_availability_fixtures as rf

    raw = wfx.well(wall="node")
    raw = add_turnover_target(raw)
    entry = dict(
        id="c_wall",
        target=dict(operator=fx.TURNOVER, control="turnover_rate", ids=["make_x"],
                    evaluation="target_half_steps", operating_range=[0.0, 1.0]),
        source={"site_population": "wall_sites", "quantity": "occupied_fraction"},
        law="site_fraction", basal=0.1,
    )  # fmt: skip
    raw = rf.with_coupling(raw, species=[], couplings=[entry])
    next(b for b in raw["model"]["operators"] if b["law"] == rf.LAW)["law"] = (
        "cells.operator.species_regulated_availability@2"
    )
    rank = {so.LAW_ID: 0, "cells.operator.species_regulated_availability@2": 1, fx.TURNOVER: 2}
    raw["model"]["operators"].sort(key=lambda b: rank.get(b["law"], -1))
    with pytest.raises(ConfigError, match="a node's own sites, which belong to no cell"):
        parse_spec(raw)


def add_turnover_target(raw):
    """The specimen cell's production of S (route make_x), a target for @2's row above."""
    return fx.with_turnover(raw, [("make_x", "specimen", "production")],
                            [("make_x", "specimen", [(0.0, 1e-9)])])  # fmt: skip


def test_a_nodes_own_sites_are_left_by_a_replacement_at_cell_0(monkeypatch):
    """FR-28's aliasing row (docs/NODE_SURFACE_SITES_DESIGN.md §8; host only, about 1 s). cell_0,
    index 0 (W's padding index), is replaced beside a node-owned wall at ecs_0, the node its
    population o0 faces. After the event maps at t_e:
    - o0 is reset to its template, within W's 4 ulps;
    - the wall's R and B are bitwise unchanged, and its departed, arrived and jump entries are 0;
    - the summed departed is o0's B before the event, so it excludes the wall;
    - the owner's bound ledger closes with W's terms.
    Planted, the wall read as cell_0's (site_replaced true at its padding index 0): the event resets
    it and books its B as departed."""
    pops = [sfx.population("o0", patch="contact_0", theta0=0.4),
            sfx.population("wall", node="ecs_0", theta0=0.5)]  # fmt: skip
    raw = sfx.replaced_sites(pops, {"o0": (0.9, 1.0, None)}, slot="cell_0")
    spec, model, state, p, control, after = _w_event(raw)
    w_index, o_index = 1, 0
    bound0 = np.asarray(p.site_bound_anchor_fmol) + np.asarray(state.site_bound_increment_fmol)
    bound1 = np.asarray(p.site_bound_anchor_fmol) + np.asarray(after.site_bound_increment_fmol)
    capacity = np.asarray(p.site_capacity_fmol)
    assert bound1[o_index] == pytest.approx(0.9 * capacity[o_index], rel=4 * np.finfo(float).eps)
    for name in ("site_bound_increment_fmol", "site_free_increment_fmol"):
        assert (
            np.asarray(getattr(after, name))[w_index] == np.asarray(getattr(state, name))[w_index]
        )
    for name in ("site_departed_fmol", "site_arrived_fmol", "site_replacement_free_energy_pJ"):
        assert np.asarray(getattr(after, name))[w_index] == 0.0
    assert float(np.sum(np.asarray(after.site_departed_fmol))) == bound0[o_index]
    sites = next(o for o in model.operators if o.LAW_ID == so.LAW_ID)
    ledgers = model._own_ledgers(sites, after, p, xp=np)
    assert not np.any(ledgers["site_bound_entity"]) and not np.any(ledgers["site_moiety_entity"])
    planted = p._replace(site_replaced=np.asarray(p.site_replaced).copy())
    planted.site_replaced[w_index] = True
    again = state
    for op in model.events:
        again, _ = op.event(again, control, planted, xp=np)
    assert np.asarray(again.site_departed_fmol)[w_index] == bound0[w_index] != 0.0
