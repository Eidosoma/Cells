"""scheduled_compartment_wash@1 (FR-27, D246) in NumPy and a compiled kernel, no world compiled.

docs/COMPARTMENT_WASH_DESIGN.md. Rows, each a claim: every refusal fires with its reason; the event
map on the review's well (60 fmol free, 30 on the specimen's sites and 10 on the wall's, half
washed with buffer at the trace) books the sample, the supply and the free-energy split, keeps
every site field and every ion amount bit for bit, and closes @3's ledgers at the event; the
whole wash is FR-20's booking; the mixing heat stands against a 50-digit reference, at the trace
too, and each plant breaks it; the host's domain check reads every event's heat; two washes of one
node keep their own fractions and buffers. FR-44 (D327): the label owner beside the wash parses in
either order; with labels= the event reports its own sample and supply, in NumPy and compiled;
a whole wash after an earlier one leaves no label behind, where the cumulative gain (plant 5)
would; a labelled gene unit's export and a labelled exchange route at the washed node are refused,
each parsing beside a wash of another node; and FR-49's C1 world, labels beside a compartment with
a wash at another node, is refused by the compartments' admitted list until FR-49's wash
narrowing. About 10 s together.
"""

import copy
import math
from decimal import Decimal, localcontext

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.errors import NumericalError
from cells.laws.electrochemistry import R
from cells.models import surface_pump as first
from cells.numerics import ideal_mixing
from cells.numerics import label_shares as ls
from cells.operators import OPERATORS
from cells.operators import site_occupancy as so
from cells.operators import wash_schedule as ws
from cells.registry.models import get_model
from validation.gene_regulation import kernel as gene_kernel
from validation.gene_regulation import worlds as gene_worlds
from validation.tissue import bath_schedule_fixtures as bfx
from validation.tissue import compartment_fixtures as cfx
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import wash_schedule_fixtures as wfx

S = wfx.TRACER
T_E = 1.0  # s: the wash, on the well's 10 ms grid.
EPS = np.finfo(float).eps


def washed(raw=None, events=((T_E, "well", 0.5, {S: wfx.TRACE_mM}),), nodes=("well",), **kw):
    return wfx.with_wash(wfx.well() if raw is None else raw, nodes, events, **kw)


def changed(raw, edit):
    out = copy.deepcopy(raw)
    edit(out)
    return out


def _permeant(raw):
    patch = next(p for p in raw["model"]["membranes"] if p["id"] == "specimen_face")
    patch["permeability_m_per_s"][S] = 1e-9


def _route(raw):
    """The review's crossing by a registered route (D263 finding 2): species exchange imports S
    from the well into the specimen through its patch, at first order."""
    return fx.with_exchange(
        raw,
        [("uptake", "specimen_face", "import", "first_order")],
        [("uptake", "specimen", [(0.0, 0.5)])],
    )


def _kind_route(raw):
    raw["model"]["passive_routes"] = [
        dict(id="s_route", patch="specimen_face", law="passive_neutral_permeation@1", species=S,
             permeability_m_per_s=1e-12)
    ]  # fmt: skip


def _internalising(raw):
    sites = next(o for o in raw["model"]["operators"] if o["law"] == "site_occupancy@1")
    population = next(q for q in sites["populations"] if q["id"] == "specimen_sites")
    population["internalisation"] = dict(rate_per_s=0.01, destination="cell")
    raw["experiment"]["site_controls"].append(
        dict(population="specimen_sites", route="internalisation",
             schedule=[dict(time=0.0, multiplier=1.0)])
    )  # fmt: skip


def _event(time=T_E, fraction=0.5, buffer=None, node="well"):
    return (time, node, fraction, {S: wfx.TRACE_mM} if buffer is None else buffer)


def _gene_unit(*, outside=True, other_node=False):
    """The gene unit's export world (validation/gene_regulation/worlds.with_export on R1 at
    p = 0.75, truncated to 600 s): R exported from cell_0 into the finite node space_0, with its
    outside degradation there unless outside is False. other_node adds space_1, a copy of space_0
    and of its patch that nothing exports into (D327's passing control)."""
    raw = gene_worlds.with_export(
        gene_kernel.truncated(gene_worlds.r1(0.75), 600.0), k_E=1e-3, outside=outside
    )
    if other_node:
        m, e, x = raw["model"], raw["experiment"], raw["execution"]
        node = copy.deepcopy(next(n for n in m["extracellular"] if n["id"] == gene_worlds.SPACE))
        node["id"] = "space_1"
        m["extracellular"].append(node)
        x["extracellular_capacity"] = len(m["extracellular"])
        patch = copy.deepcopy(next(p for p in m["membranes"] if p["outside"] == gene_worlds.SPACE))
        patch.update(id="patch_cell_0_space_1", outside="space_1")
        m["membranes"].append(patch)
        x["membrane_capacity"] = len(m["membranes"])
        control = next(c for c in e["membrane_controls"] if c["membrane_id"] != "patch_0")
        e["membrane_controls"].append(dict(copy.deepcopy(control), membrane_id=patch["id"]))
    return raw


def _labelled(raw, species):
    """raw with the label owner labelling `species` (base and cohort, every node at the base)."""
    out = copy.deepcopy(raw)
    out["model"]["operators"].append(dict(law="neutral_arrival_labels@1", species=[
        dict(id=s, labels=["base", "cohort"], initial=[]) for s in species
    ]))  # fmt: skip
    out["experiment"]["label_arrivals"] = []
    return out


def _second_well(raw):
    """raw with well_2, a copy of the well, joined to the specimen by a copy of its patch."""
    out = copy.deepcopy(raw)
    m, e, x = out["model"], out["experiment"], out["execution"]
    node = copy.deepcopy(next(n for n in m["extracellular"] if n["id"] == "well"))
    node["id"] = "well_2"
    m["extracellular"].append(node)
    x["extracellular_capacity"] = len(m["extracellular"])
    patch = copy.deepcopy(next(p for p in m["membranes"] if p["id"] == "specimen_face"))
    patch.update(id="specimen_face_2", outside="well_2")
    m["membranes"].append(patch)
    x["membrane_capacity"] = len(m["membranes"])
    for c in [c for c in e["membrane_controls"] if c["membrane_id"] == "specimen_face"]:
        e["membrane_controls"].append(dict(copy.deepcopy(c), membrane_id="specimen_face_2"))
    return out


def _c1_world():
    """FR-49's C1 shape (validation/fr49/REGISTRATION.md §5; D327), which is also the inherited
    three-way composition (cell_owned_compartments@1, neutral_arrival_labels@1, and the wash at an
    external node). It is World L, a compartment with labelled S (validation/fr49/worlds.py), plus
    a well joined to cell_0 by a copy of the bounding patch, which carries no S route. The well's S
    is labelled x 0.6 and base 0.4, and the well is washed by half at 900 s for a buffer with S at
    1e-9 mM."""
    from validation.fr49 import worlds as fr49

    raw = fr49.world_l()
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    node = copy.deepcopy(next(n for n in m["extracellular"] if n["id"] == fr49.NODE))
    node["id"] = "well"
    m["extracellular"].append(node)
    x["extracellular_capacity"] = len(m["extracellular"])
    patch = copy.deepcopy(next(p for p in m["membranes"] if p["id"] == fr49.PATCH))
    patch.update(id="patch_cell_0_well", outside="well")
    m["membranes"].append(patch)
    x["membrane_capacity"] = len(m["membranes"])
    control = next(c for c in e["membrane_controls"] if c["membrane_id"] == fr49.PATCH)
    e["membrane_controls"].append(dict(copy.deepcopy(control), membrane_id=patch["id"]))
    owner = next(o for o in m["operators"] if o["law"] == fr49.LABELS)
    owner["species"][0]["initial"].append(dict(node="well", shares={"x": 0.6, "base": 0.4}))
    neutral = [s["id"] for s in m["species"] if s["valence"] == 0]
    buffer = {s: node["initial_amount_fmol"][s] / node["volume_pL"] for s in neutral}
    return wfx.with_wash(raw, ["well"], [(900.0, "well", 0.5, buffer | {fr49.S: 1e-9})])


def _washed_at(raw, node):
    """raw with half of `node` washed at 300 s, its buffer every neutral species at the node's
    own declared concentration."""
    m = raw["model"]
    entry = next(n for n in m["extracellular"] if n["id"] == node)
    neutral = [s["id"] for s in m["species"] if s["valence"] == 0]
    buffer = {s: entry["initial_amount_fmol"][s] / entry["volume_pL"] for s in neutral}
    return wfx.with_wash(raw, [node], [(300.0, node, 0.5, buffer)])


REFUSALS = {
    "a held bath": (lambda: washed(nodes=("bath",), events=[]), "is a held bath"),
    "an undeclared node": (lambda: washed(nodes=("pond",), events=[]), "undeclared outside node"),
    "a node twice": (lambda: washed(nodes=("well", "well"), events=[]), "lists a node twice"),
    "ions not the node's own": (lambda: washed(ions="formula_units"), "declares its ions"),
    "a buffer without a species": (lambda: washed(events=[_event(buffer={})]), "missing \\['S'\\]"),
    "a buffer with an ion": (
        lambda: washed(events=[_event(buffer={S: 1e-9, "K": 5.0})]),
        "other \\['K'\\]",
    ),
    "an exact zero": (lambda: washed(events=[_event(buffer={S: 0.0})]), "an exact zero"),
    "a fraction of 0": (lambda: washed(events=[_event(fraction=0.0)]), "fraction lies in"),
    "a fraction above 1": (lambda: washed(events=[_event(fraction=1.5)]), "fraction lies in"),
    "a time off the grid": (lambda: washed(events=[_event(time=1.005)]), "on the clock's grid"),
    "a time at 0": (lambda: washed(events=[_event(time=0.0)]), "after time 0"),
    "a time at the end": (lambda: washed(events=[_event(time=2.0)]), "before the end time"),
    "times not increasing": (
        lambda: washed(events=[_event(time=1.0), _event(time=0.5)]),
        "increase strictly",
    ),
    "an event at a node not declared": (
        lambda: washed(events=[_event(node="bath")]),
        "does not declare",
    ),
    "a face at the node": (
        lambda: wfx.with_wash(fx.world(), ["ecs_0"], [(0.002, "ecs_0", 0.5, {S: 1e-9})]),
        "face face_0 touches node ecs_0",
    ),
    "a neutral species across a facing patch": (
        lambda: washed(changed(wfx.well(sites=False), _permeant)),
        "S crosses patch specimen_face",
    ),
    # D263 finding 2 (a second review): the same crossing by a registered route was admitted.
    "a neutral species across the surface by an exchange route": (
        lambda: washed(_route(wfx.well(sites=False))),
        "S may cross node well's surface by scheduled_species_exchange@1's route uptake",
    ),
    "a neutral species across the surface by a kind's route": (
        lambda: washed(changed(wfx.well(sites=False), _kind_route)),
        "by cells.passive_routes@1 \\(passive_neutral_permeation@1\\)",
    ),
    "a ligand internalised across the surface": (
        lambda: washed(changed(wfx.well(), _internalising)),
        "by site_occupancy@1's internalisation specimen_sites",
    ),
    # D327, the fail-open fix: amendment T's export and outside degradation, each by name.
    "a gene unit's export into the node": (
        lambda: _washed_at(_gene_unit(outside=False), "space_0"),
        "R may cross node space_0's surface by templated_polymerisation@1's export export_R",
    ),
    "a gene unit's outside degradation at the node": (
        lambda: _washed_at(_gene_unit(), "space_0"),
        "by templated_polymerisation@1's outside degradation deg_R_space_0",
    ),
    "a buffer below a site ligand's trace": (
        lambda: washed(events=[_event(buffer={S: 1e-13})]),
        "below its declared trace",
    ),
    # Off the compartments' admitted list, which fails closed (compartments.check_definition).
    "beside the compartments": (
        lambda: wfx.with_wash(
            cfx.loaded_compartment(), ["ecs_0"], [(0.01, "ecs_0", 0.5, {S: 1e-6})]
        ),
        "scheduled_compartment_wash@1 is not on its admitted list",
    ),
    # FR-44 (D327): the paths that FR-44's labels would follow unmeasured stay refused by name.
    "a labelled gene unit's export into the node": (
        lambda: _washed_at(_labelled(_gene_unit(outside=False), ["R", "R_s"]), "space_0"),
        "R may cross node space_0's surface by templated_polymerisation@1's export export_R",
    ),
    "a labelled exchange route through a patch facing the node": (
        lambda: washed(_labelled(_route(wfx.well(sites=False)), [S])),
        "S may cross node well's surface by scheduled_species_exchange@1's route uptake",
    ),
    # D327, FR-44 landing second (FR-49's parts H and L first): FR-49's C1 world, also the
    # inherited three-way composition, is refused by name until FR-49's wash narrowing and its C1
    # judgement.
    "FR-49's C1 world: labels beside a compartment and a wash at another node": (
        _c1_world,
        "scheduled_compartment_wash@1 is not on its admitted list",
    ),
}


@pytest.mark.parametrize("name", sorted(REFUSALS))
def test_each_refusal_fires_with_its_reason(name):
    build, message = REFUSALS[name]
    with pytest.raises(ConfigError, match=message):
        parse_spec(build())


def test_every_path_across_a_washed_surface_is_classified(monkeypatch):
    """D263 finding 2, fail closed (host only, parse): every registered operator law is read for its
    routes (exchange, sites, the gene unit's exports and outside degradations), shown local or
    refused with its reason, so a new law is refused beside the wash until it is classified here.
    Planted: turnover unclassified, a world with it is refused. The review's well with its sites,
    a route-free wash, and the gene unit's export world washed at a node it neither exports into
    nor degrades at (D327's passing control) stay admitted."""
    from cells.operators import OPERATORS
    from cells.operators import wash_schedule as wash

    read = set(wash.READ)
    lists = [read, set(wash.SHOWN_LOCAL), set(wash.REFUSED)]
    assert sorted(set(OPERATORS) - set().union(*lists)) == [], "classify the new law here"
    assert sum(len(x) for x in lists) == len(set().union(*lists))
    parse_spec(washed())
    parse_spec(washed(wfx.well(sites=False)))
    parse_spec(_washed_at(_gene_unit(other_node=True), "space_1"))
    raw = fx.with_turnover(
        wfx.well(sites=False),
        [("make", "specimen", "production")],
        [("make", "specimen", [(0.0, 1e-6)])],
    )
    parse_spec(washed(raw))
    shown = {k: v for k, v in wash.SHOWN_LOCAL.items() if k != "scheduled_species_turnover@1"}
    monkeypatch.setattr(wash, "SHOWN_LOCAL", shown)
    with pytest.raises(ConfigError, match="scheduled_species_turnover@1, which is not classified"):
        parse_spec(washed(raw))


def test_admitted_beside_a_dose_at_a_held_bath_and_the_declaration_round_trips():
    """Door S: the wash reads the well alone, so the bath schedule's dose at the held bath (a
    measured KCl-for-NaCl step, on its 1 ms grid) is admitted beside it and the sites."""
    raw = washed(wfx.well(dt=1e-3, end=1.5))
    raw = bfx.with_bath_schedule(
        raw, ["bath"], bfx.SALTS, [(0.5, ["bath"], {"KCl": 2.5, "NaCl": -2.5})]
    )
    spec = parse_spec(raw)
    assert parse_spec(cs.to_dict(spec)) == spec
    ((op, declaration, _),) = [e for e in cs.entries(spec) if e[0].LAW_ID == ws.LAW_ID]
    well = [c.id for c in spec.model.extracellular].index("well")
    assert op.read_slots(spec, declaration) == dict.fromkeys(
        ws.ScheduledCompartmentWash.SCOPED_READS, (well,)
    )


@pytest.mark.parametrize("owner_first", [False, True])
def test_admitted_beside_the_label_owner_in_either_order(owner_first):
    """FR-44 (D327; parses only): the label owner beside the wash parses with either one declared
    first. The owner is shown local to the wash, and it admits the wash's exchanging event. Its
    record of what left is then sized [labelled species, label, outside node]."""
    raw = washed(wfx.well(sites=False))
    block = dict(law="neutral_arrival_labels@1", species=[dict(
        id=S, labels=["base", "cohort"], initial=[dict(node="well", shares={"cohort": 1.0})]
    )])  # fmt: skip
    operators = raw["model"]["operators"]
    operators.insert(len(operators) - 1 if owner_first else len(operators), block)
    raw["experiment"]["label_arrivals"] = []
    spec = parse_spec(raw)
    laws = [op.LAW_ID for op, _, _ in cs.entries(spec)]
    assert (laws.index("neutral_arrival_labels@1") < laws.index(ws.LAW_ID)) == owner_first
    state, _ = get_model(spec.model).initial_values(spec)
    shape = (1, 2, spec.execution.extracellular_capacity)
    assert np.shape(state.label_outside_removed_fmol) == shape


LABELLED_ELSEWHERE = {  # FR-44 (D327): each refused path above, labelled, beside a wash elsewhere.
    "the gene unit, its export node unwashed": lambda: _washed_at(
        _labelled(_gene_unit(other_node=True), ["R", "R_s"]), "space_1"
    ),
    "an exchange route facing another node": lambda: washed(
        _labelled(_route(_second_well(wfx.well(sites=False))), [S]),
        events=((T_E, "well_2", 0.5, {S: wfx.TRACE_mM}),),
        nodes=("well_2",),
    ),
}


@pytest.mark.parametrize("case", sorted(LABELLED_ELSEWHERE))
def test_a_labelled_path_beside_a_wash_of_another_node_is_admitted(case):
    """FR-44 (D327; parses only): the passing controls of the two labelled refusals above. The gene
    unit with labelled R and R_s, and an exchange route with labelled S, each parse beside a wash
    of a node their paths do not cross. These are the newly admitted triples of the labels, the
    wash and each of the two laws."""
    parse_spec(LABELLED_ELSEWHERE[case]())


# ------------------------------------------------------------------ the event map, in NumPy


def at_event(raw, time=T_E, count=None):
    """(spec, model, the bound state, p, the control at `time`, the state after the event maps,
    their validity)."""
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [time])))
    if count is not None:
        control = control._replace(wash_count=np.full_like(control.wash_count, count))
    after, valid = state, True
    for op in model.events:
        after, ok = op.event(after, control, p, xp=np)
        valid &= ok is None or bool(ok)
    return spec, model, state, p, control, after, valid


def energy(spec, model, row, p, steps=1):
    """(@3's energy residual with the operators' terms, its bound at `steps`, and the wash's own
    term) at `row`."""
    tol = np.asarray(spec.execution.material_balance_atol_fmol)
    rtol = first.ENERGY_RTOL[spec.execution.solver]
    magnitudes = model.magnitudes(row, p)
    _, limits = model.ledger_limits(row, p, tol, rtol, steps=steps, magnitudes=magnitudes)
    own = row.wash_mixing_heat_pJ - row.wash_buffer_free_energy_pJ + row.wash_sample_free_energy_pJ
    return float(model.inner_balances(row, p)["energy"]), float(limits[6]), float(np.sum(own))


def in_turn(raw, times):
    """(spec, model, p, the states after the event maps at each of `times` in turn, no step
    between; the bound state first)."""
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    states = [state]
    for time in times:
        control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [time])))
        for op in model.events:
            state, ok = op.event(state, control, p, xp=np)
            assert ok is None or bool(ok)
        states.append(state)
    return spec, model, p, states


def reference(n, volume, fraction, buffer, temperature):
    """(H_mix, F_sample, F_buffer) of one species' wash, 50 digits."""
    with localcontext() as ctx:
        ctx.prec = 50
        n, v, f, cb = (Decimal(float(x)) for x in (n, volume, fraction, buffer))
        rt = Decimal("1e-3") * Decimal(R) * Decimal(temperature)
        c = n / v
        c1 = (1 - f) * c + f * cb

        def phi(x):
            return x * x.ln() - x + 1 if x > 0 else Decimal(1)

        heat = rt * v * c1 * ((1 - f) * phi(c / c1) + f * phi(cb / c1))
        return heat, rt * f * n * (c.ln() - 1), rt * f * v * cb * (cb.ln() - 1)


def close(value, expected, ulps, rel=0.0):
    """Within `ulps` of the value's spacing, plus `rel` of the reference."""
    bound = ulps * Decimal(np.spacing(abs(value))) + Decimal(rel) * abs(expected)
    return math.isfinite(value) and abs(Decimal(value) - expected) <= bound


def test_the_wash_books_the_sample_the_buffer_and_its_free_energy_and_keeps_the_rest():
    """The review's well at t_e: 60 fmol free become 30 plus the buffer's trace, the sample is 30,
    the sites and the ions keep their bits, and @3's ledgers close at the event with the wash's
    terms (the energy residual about 1e-13 pJ, its bound 2e-8 pJ), while the wash's energy term
    alone is about 4e10 times that bound."""
    spec, model, state, p, control, after, valid = at_event(washed())
    assert valid
    ids = list(spec.model.species_ids)
    s, w = ids.index(S), [c.id for c in spec.model.extracellular].index("well")
    n = np.asarray(p.extracellular_amount_reference) + np.asarray(
        state.extracellular_amount_increment
    )
    collected, supplied = (
        np.asarray(after.wash_collected_fmol),
        np.asarray(after.wash_supplied_fmol),
    )
    assert collected[s, w] == 0.5 * n[s, w] == 30.0
    assert supplied[s, w] == 0.5 * wfx.V_WELL * wfx.TRACE_mM
    moved = np.asarray(after.extracellular_amount_increment) - np.asarray(
        state.extracellular_amount_increment
    )
    assert moved[s, w] == supplied[s, w] - collected[s, w]
    for i, z in enumerate(spec.model.valence):  # Ions: f n out and the same in, the amount kept.
        if z:
            assert (
                collected[i, w].tobytes() == supplied[i, w].tobytes() == (0.5 * n[i, w]).tobytes()
            )
            assert moved[i, w] == 0.0
    assert np.count_nonzero(moved) == 1  # Only the tracer at the well moved.
    for name in so.STATE_AXES:  # Bound material is not liquid: every site field keeps its bits.
        assert (
            np.asarray(getattr(after, name)).tobytes() == np.asarray(getattr(state, name)).tobytes()
        )
    heat, f_sample, f_buffer = reference(
        n[s, w], wfx.V_WELL, 0.5, wfx.TRACE_mM, spec.model.temperature_K
    )
    assert close(float(after.wash_mixing_heat_pJ[w]), heat, 64)
    assert after.wash_last_mixing_heat_pJ[w] == after.wash_mixing_heat_pJ[w] > 0
    assert close(float(after.wash_sample_free_energy_pJ[w]), f_sample, 8)
    assert close(float(after.wash_buffer_free_energy_pJ[w]), f_buffer, 8)
    assert after.wash_applied[w] == 1 and np.count_nonzero(after.wash_applied) == 1
    op = next(op for op in model.events if op.LAW_ID == ws.LAW_ID)
    assert not np.any(op.own_ledgers(after, p, xp=np)["wash_ions"])
    # @3's ledgers at the event, with the wash's terms: the chemical jump against the split.
    b = model.inner_balances(after, p)
    tol = np.asarray(spec.execution.material_balance_atol_fmol)
    rtol = first.ENERGY_RTOL[spec.execution.solver]
    _, limits = model.ledger_limits(
        after, p, tol, rtol, steps=1, magnitudes=model.magnitudes(after, p)
    )
    assert np.all(np.abs(b["outside"]) <= limits[1]) and np.all(np.abs(b["total"]) <= limits[2])
    assert abs(b["energy"]) <= 1e-3 * limits[6]
    split = float(
        np.sum(
            after.wash_mixing_heat_pJ
            - after.wash_buffer_free_energy_pJ
            + after.wash_sample_free_energy_pJ
        )
    )
    assert abs(b["energy"] - split) > 1e9 * limits[6]  # Without its term the ledger fails.
    # Nothing more is due at the same control: the state, bit for bit.
    again, ok = op.event(after, control, p, xp=np)
    assert ok and all(
        np.asarray(x).tobytes() == np.asarray(y).tobytes()
        for x, y in zip(again, after, strict=True)
    )
    # A count the state has not reached refuses the step.
    _, _, _, _, _, _, valid = at_event(washed(), count=2)
    assert not valid


def test_the_whole_wash_is_fr20s_booking_and_the_trace_limit_of_its_amounts():
    """f = 1: the sink takes F(old pool), the source F(fresh pool), with no mixing heat, and @3's
    energy ledger closes at the event's own step (steps = 1), for 1 uL and 10 mL wells to traces
    down to 1e-14 mM (the new amount, anchor plus increment, is rounded at eps times the stored
    amounts: its magnitude term). The node at 1 mM: at 2^-60 mM the buffer's amount lies below one
    ulp of the node's anchor and the event refuses the step; at f = 0.5 it is admitted, its heat
    finite."""
    one = wfx.well(sites=False, free=wfx.V_WELL)  # 1 mM.
    spec, model, state, p, _, after, valid = at_event(
        washed(one, [_event(fraction=1.0, buffer={S: 1e-9})])
    )
    assert valid
    residual, bound, _ = energy(spec, model, after, p)
    assert abs(residual) <= bound
    for volume, buffer in ((1e10, 1e-12), (1e10, 1e-14)):  # Ratios 1.3 and 4.8 without the term.
        big = wfx.well(sites=False, volume=volume, free=volume)
        spec_b, model_b, _, p_b, _, after_b, valid_b = at_event(
            washed(big, [_event(fraction=1.0, buffer={S: buffer})])
        )
        residual, bound, _ = energy(spec_b, model_b, after_b, p_b)
        assert valid_b and abs(residual) <= 0.2 * bound
    s, w = (
        list(spec.model.species_ids).index(S),
        [c.id for c in spec.model.extracellular].index("well"),
    )
    n = float(
        np.asarray(p.extracellular_amount_reference)[s, w]
        + np.asarray(state.extracellular_amount_increment)[s, w]
    )
    assert after.wash_mixing_heat_pJ[w] == 0.0 and after.wash_collected_fmol[s, w] == n
    _, f_old, f_fresh = reference(n, wfx.V_WELL, 1.0, 1e-9, spec.model.temperature_K)
    assert close(float(after.wash_sample_free_energy_pJ[w]), f_old, 8)
    assert close(float(after.wash_buffer_free_energy_pJ[w]), f_fresh, 8)
    left = float(
        np.asarray(p.extracellular_amount_reference)[s, w]
        + np.asarray(after.extracellular_amount_increment)[s, w]
    )
    assert left == pytest.approx(wfx.V_WELL * 1e-9, rel=1e-6)  # eps x the anchor, absolute.
    trace = 2.0**-60
    assert not at_event(washed(one, [_event(fraction=1.0, buffer={S: trace})]))[-1]
    spec, _, state, p, _, after, valid = at_event(
        washed(one, [_event(fraction=0.5, buffer={S: trace})])
    )
    heat, _, _ = reference(n, wfx.V_WELL, 0.5, trace, spec.model.temperature_K)
    assert valid and close(float(after.wash_mixing_heat_pJ[w]), heat, 8)


def test_the_domain_check_reads_every_events_heat():
    """The host's row check (the composite's check_values): the row after the wash passes; with a
    negative heat at the latest event it fails the domain, though the cumulative record stays
    positive (the host check of H_mix >= 0 at every event, D246)."""
    spec, model, _, _, _, after, _ = at_event(washed())
    w = [c.id for c in spec.model.extracellular].index("well")
    model.check_values(after, spec)
    last = np.array(after.wash_last_mixing_heat_pJ)
    last[w] = -1e-9
    assert after.wash_mixing_heat_pJ[w] > 0
    with pytest.raises(NumericalError, match="Invalid"):
        model.check_values(after._replace(wash_last_mixing_heat_pJ=last), spec)


def test_two_washes_of_one_node_keep_their_own_fractions_and_buffers():
    """Half the well with the trace at 1 s, then a quarter with 2e-5 mM at 1.5 s: two applied, the
    second's sample a quarter of what the first left, its buffer its own, the records summed, the
    latest heat the second's, and @3's energy ledger closed after both."""
    events = [_event(), _event(time=1.5, fraction=0.25, buffer={S: 2e-5})]
    spec, model, p, (_, first_wash, second) = in_turn(washed(events=events), [T_E, 1.5])
    s, w = (
        list(spec.model.species_ids).index(S),
        [c.id for c in spec.model.extracellular].index("well"),
    )
    left = float(
        np.asarray(p.extracellular_amount_reference)[s, w]
        + np.asarray(first_wash.extracellular_amount_increment)[s, w]
    )
    assert second.wash_applied[w] == 2
    assert second.wash_collected_fmol[s, w] == first_wash.wash_collected_fmol[s, w] + 0.25 * left
    supply = 0.25 * wfx.V_WELL * 2e-5
    assert second.wash_supplied_fmol[s, w] == first_wash.wash_supplied_fmol[s, w] + supply
    heat, _, _ = reference(left, wfx.V_WELL, 0.25, 2e-5, spec.model.temperature_K)
    assert close(float(second.wash_last_mixing_heat_pJ[w]), heat, 64)
    total = first_wash.wash_mixing_heat_pJ[w] + second.wash_last_mixing_heat_pJ[w]
    assert second.wash_mixing_heat_pJ[w] == total
    residual, bound, _ = energy(spec, model, second, p)
    assert abs(residual) <= 1e-3 * bound


def test_with_labels_the_event_reports_its_own_sample_and_supply():
    """FR-44 (D327), the wash alone on the review's well at t_e, in NumPy and compiled (the event
    map alone; about 1 s). With labels= (S's and Cl's rows):
    - the state and validity are the unlabelled call's, bit for bit;
    - the LiquidExchange report is the two per-event level records at those rows where the wash is
      due: S's 30 fmol sample and its buffer, and Cl's sample twice, since an ion's supply is its
      sample. It is zero at the held bath.
    Called again at the same control, nothing is due: the report is zero, though the records
    persist."""
    spec, model, state, p, control, _, _ = at_event(washed())
    op = next(op for op in model.events if op.LAW_ID == ws.LAW_ID)
    ids = list(spec.model.species_ids)
    rows = np.array([ids.index(S), ids.index("Cl")])
    w = [c.id for c in spec.model.extracellular].index("well")
    calls = {
        "NumPy": (
            lambda s: op.event(s, control, p, xp=np, labels=rows),
            lambda s: op.event(s, control, p, xp=np),
        ),
        "compiled": (
            jax.jit(lambda s: op.event(s, control, p, xp=jnp, labels=rows)),
            jax.jit(lambda s: op.event(s, control, p, xp=jnp)),
        ),
    }
    for name, (labelled, plain) in calls.items():
        new, ok, report = labelled(state)
        base, ok_plain = plain(state)
        assert all(
            np.asarray(a).tobytes() == np.asarray(b).tobytes()
            for a, b in zip(new, base, strict=True)
        ), name
        assert bool(ok) and bool(ok_plain), name
        removed, supplied = np.asarray(report.removed), np.asarray(report.supplied)
        sample = np.asarray(new.wash_last_sample_fmol)[rows]
        supply = np.asarray(new.wash_last_supply_fmol)[rows]
        assert removed[:, w].tobytes() == sample[:, w].tobytes(), name
        assert supplied[:, w].tobytes() == supply[:, w].tobytes(), name
        assert removed[0, w] == 30.0 and supplied[0, w] == 0.5 * wfx.V_WELL * wfx.TRACE_mM, name
        assert removed[1, w].tobytes() == supplied[1, w].tobytes(), name  # Cl: its own sample.
        others = np.arange(removed.shape[1]) != w
        assert not np.any(removed[:, others]) and not np.any(supplied[:, others]), name
        again, ok_again, nothing = labelled(new)
        assert bool(ok_again), name
        assert not np.any(np.asarray(nothing.removed)), name
        assert not np.any(np.asarray(nothing.supplied)), name
        assert np.asarray(again.wash_last_sample_fmol)[rows[0], w] == 30.0, name  # It persists.


@pytest.mark.parametrize("free, buffer, sign", [(60.0, 3e-5, -1.0), (70.0, 1e-5, 1.0)])
def test_a_whole_wash_after_an_earlier_one_leaves_no_label_behind(free, buffer, sign):
    """FR-44's regression (D327), the wash alone in NumPy: 3/7 of the well at 1 s, then all of it
    at 1.5 s.
    - The second report removes that event's own sample, fl(1.0 n) = n, so the kept part is
      exactly 0. The label map then leaves the cohort's share exactly 0 and the base's exactly 1.
    - Plant 5 takes the cumulative record's gain as the removed amount instead. On these numbers it
      leaves a kept part of about 7e-15 fmol: negative on the first row, a negative share that the
      owner's domain refuses, and positive on the second, a cohort share that should be 0."""
    events = [_event(fraction=3 / 7, buffer={S: buffer}),
              _event(time=1.5, fraction=1.0, buffer={S: buffer})]  # fmt: skip
    spec = parse_spec(washed(wfx.well(free=free), events=events))
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    op = next(op for op in model.events if op.LAW_ID == ws.LAW_ID)
    rows = np.array([list(spec.model.species_ids).index(S)])
    w = [c.id for c in spec.model.extracellular].index("well")
    states, reports = [state], []
    for time in (T_E, 1.5):
        control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [time])))
        state, ok, report = op.event(state, control, p, xp=np, labels=rows)
        assert ok
        states.append(state)
        reports.append(report)
    n0 = (p.extracellular_amount_reference + states[1].extracellular_amount_increment)[rows]
    removed, supplied = reports[1]
    assert removed[0, w] == n0[0, w] and n0[0, w] - removed[0, w] == 0.0
    shares = np.zeros((1, 2, n0.shape[1]))
    shares[0, 0] = 1.0
    shares[0, :, w] = (2 / 3, 1 / 3)
    present = np.ones((1, 2), dtype=bool)
    new = ls.exchange(shares, n0, removed, supplied, present, xp=np)
    assert new[0, 1, w] == 0.0 and new[0, 0, w] == 1.0
    gain = (states[2].wash_collected_fmol - states[1].wash_collected_fmol)[rows]  # Plant 5.
    kept = n0[0, w] - gain[0, w]
    assert np.sign(kept) == sign and abs(kept) < 1e-13
    planted = ls.exchange(shares, n0, gain, supplied, present, xp=np)
    assert planted[0, 1, w] != 0.0 and (planted[0, 1, w] < 0) == (sign < 0)
    assert bool(ls.domain_valid(planted, present, xp=np)) == (sign > 0)


# ------------------------------------------------------------------ the mixing heat, a kernel table


def kernel(n, volume, fraction, buffer, compiled):
    """(H_mix, F_sample, F_buffer) per column of one neutral species, from wash_terms."""
    args = (
        np.asarray(n, float)[None, :],
        np.asarray(volume, float)[None, :],
        np.asarray(fraction, float)[None, :],
        np.asarray(buffer, float)[None, :],
    )
    ion = np.zeros((1, 1), dtype=bool)
    if compiled:
        out = jax.jit(lambda *a: ws.wash_terms(*a, ion, 310.0, xp=jnp))(*args)
    else:
        with np.errstate(all="ignore"):
            out = ws.wash_terms(*args, ion, 310.0, xp=np)
    return np.asarray(out[5])[0], np.asarray(out[3])[0], np.asarray(out[4])[0]


def columns(row):
    """(n, volume, fraction, buffer) for a row of the table."""
    if row in ("trace_buffer", "trace_node"):
        c, cb = (1.0, 2.0**-60) if row == "trace_buffer" else (2.0**-60, 1.0)
        f = np.array([0.5, 0.1, 0.9])
        return np.full(3, c * 1e6), np.full(3, 1e6), f, np.full(3, cb)
    if row == "threshold_edge":  # c_b / c' from about 2^-59 to 2^-41, below RATIO_BELOW.
        cb = 2.0 ** -np.linspace(42, 60, 12)
        return np.full(12, 1e3), np.full(12, 1e3), np.full(12, 0.5), cb
    # Ordinary: buffer-to-node ratios from 1e-6 to 1e6; within 2e-3 of 1, where the e-form takes
    # over from the series; within 1e-5 of 1, the series; and fractions to 1.
    rng = np.random.default_rng(27)
    sign = rng.choice([-1.0, 1.0], 16)
    ratio = np.concatenate(
        [
            10 ** rng.uniform(-6, 6, 32),
            1 + sign * rng.uniform(2e-4, 2e-3, 16),
            1 + rng.uniform(-1e-5, 1e-5, 16),
        ]
    )
    c = 10 ** rng.uniform(-6, 2, 64)
    f = np.concatenate([rng.uniform(0.01, 1.0, 60), [1.0, 1.0, 0.5, 1e-3]])
    volume = 2.0 ** rng.integers(0, 20, 64)  # So c = n / V is exact, as the reference's is.
    return c * volume, volume, f, c * ratio


def heat_failures(row):
    out = []
    n, volume, f, cb = columns(row)
    expected = [reference(*x, 310.0)[0] for x in zip(n, volume, f, cb, strict=True)]
    # The form's own accuracy: a few ulps from the ratio and the series; the e-form keeps about
    # eps |ln r| of phi far from 1 and about 2 eps / |e| just above the series' 1e-4.
    rel = 1e-11 if row == "ordinary" else 0.0
    for compiled in (False, True):
        heat = kernel(n, volume, f, cb, compiled)[0]
        bad = [
            j
            for j, (h, x) in enumerate(zip(heat, expected, strict=True))
            if not (h >= 0 and close(float(h), x, 16, rel))
        ]
        if bad:
            out.append(f"heat off the reference at {bad} ({compiled=})")
    return out


def e_alone(e, ratio, *, xp):  # Planted: the e-form as the cleft first had it, the ratio unread.
    small = xp.abs(e) < ideal_mixing.SERIES_BELOW
    safe = xp.where(small, 1.0, e)
    return xp.where(
        small,
        e * e * (0.5 - e * (1.0 / 6.0 - e * (1.0 / 12.0 - e / 20.0))),
        (1.0 + safe) * xp.log1p(safe) - safe,
    )


HEATS = (  # Each plant: the e-form alone, or the ratio form everywhere.
    pytest.param("trace_buffer", ("phi", e_alone), id="trace_buffer"),
    pytest.param("trace_node", ("phi", e_alone), id="trace_node"),
    pytest.param("threshold_edge", ("phi", e_alone), id="threshold_edge"),
    pytest.param("ordinary", ("RATIO_BELOW", np.inf), id="ordinary"),
)


@pytest.mark.parametrize("row, plant", HEATS)
def test_the_mixing_heat_against_a_50_digit_reference_and_each_plant_breaks_it(
    row, plant, monkeypatch
):
    assert heat_failures(row) == []
    monkeypatch.setattr(ideal_mixing, *plant)
    assert heat_failures(row) != []


def test_it_registers_with_its_run_view():
    op = OPERATORS[ws.LAW_ID]
    assert op.IDENTITY_ROLE == "user" and [layer["representation"] for layer in op.VIEW_LAYERS] == [
        "prescribed"
    ]
    spec = parse_spec(washed(events=[_event(time=0.5), _event(time=1.5, fraction=1.0)]))
    ((_, declaration, schedule),) = [e for e in cs.entries(spec) if e[0].LAW_ID == ws.LAW_ID]
    events = op.view_events(spec, declaration, schedule)
    assert [(e["time"], e["at"], e["layer"]) for e in events] == [
        (0.5, {"outside": "well"}, "wash"),
        (1.5, {"outside": "well"}, "wash"),
    ]


def test_a_draw_from_chosen_regions_of_an_uneven_liquid():
    """FR-37 (D274), its synthetic test with existing operators (validation/sampling/uneven_draw.py;
    host only, the composite's own event maps on the bound state, about 1 s): two 100 pL regions,
    each a finite node, 8 and 2 fmol of S above the buffer's background; 100 pL collected by
    per-region wash events, refilled with buffer at the background.
    - unmixed, all 100 pL from A: sample 8, left 0 and 2;
    - mixed (declared, 5 and 5), 50 pL from each: sample 5, left 2.5 and 2.5;
    - the port's, 75 pL from A and 25 from B: sample 6.5, left 2 and 1.5.
    Each reports the drawn volumes, the sample and its concentration, the remainders and the refill
    separately, and accounts for the 10 fmol within rounding."""
    from validation.sampling import uneven_draw as draw

    expected = {"unmixed": (8.0, (0.0, 2.0)), "mixed": (5.0, (2.5, 2.5)), "port": (6.5, (2.0, 1.5))}
    for case, (sample, left) in expected.items():
        out = draw.report(case)
        assert sum(out["drawn_pL"].values()) == 100.0
        assert out["sample_above_background_fmol"] == pytest.approx(sample, abs=1e-12), case
        assert out["sample_mM"] == pytest.approx(out["sample_fmol"] / 100.0, rel=1e-15)
        for region, amount in zip(draw.REGIONS, left, strict=True):
            got = out["remainder_above_background_fmol"][region]
            assert got == pytest.approx(amount, abs=1e-12), (case, region)
        assert out["refill_supplied_fmol"] == pytest.approx(draw.BACKGROUND_mM * 100.0, rel=1e-12)
        assert abs(out["account_residual_fmol"]) <= 1e-15, case
