"""FR-42's kinds hook (D303 item 6; docs/NEUTRAL_LABELS_DESIGN.md §11): labels carried by declared
kinds' one-way moves, the passive routes' kernels' two terms and the transporter's one-way cycle
rates, through @3's labelled step.

One compiled world, run labelled and as its unlabelled twin (two compiles, about 80 s on a light
CPU; the hook's engine row, so a regression in the owner's admission, @3's call or a kind's report
shows here). Its cell and finite node cross a contact patch: S at equal concentrations (zero net
flux) by a neutral passive route, labelled a in the cell and b in the node; and Y, labelled,
pumped from the cell into the node by a neutral transporter on held fuel and leaking to the held
bath by the wall patch's own route (@3's), so the cell's Y closure holds both movers' reports.
Every history field, observation and diagnostic of the labelled run is the unlabelled run's bit
for bit; the closure diagnostic reads rounding; S's labels exchange at the route's one-way rate as
the closed form says, at rounding; Y's label reaches the node through the pump.

Host rows (NumPy steps and evaluations, no compile):
- each kernel's one-way terms: forward - backward is its net flux at rounding, both >= 0, and each
  is the law's own term (P A c B(-+x), J+ = k a S and J- = J+ e^x), for the neutral, leak and
  charged routes, version 1's two laws and the population axis's factored, diagram and monomial
  forms; an unlabelled rectifier route and a net-flow population beside report finite zeros;
- the gap between a step's booked net and the trapezoid of its one-way fluxes falls as dt^3;
- zero-net exchange through @3's step follows the one-way rate, and a planted halving of the
  route's one-way terms fails it (the closure cannot see it);
- a kind carrying Q beside S moved by a face: labelled S is admitted, and its face transfers are
  the kind-free twin's bit for bit (before the hook, any declared kind turned the inner step's
  reports off);
- admitted (parses): a transporter's crossing rows in both layouts, and K beside every FR-4 and
  FR-5 kind; the hook's refusals are rows of test_neutral_arrival_labels.py's REFUSED;
- the population axis through the labelled step (factored with N at either end, a diagram's two
  crossing rows, and a net-flow population beside an untouched row), the Euler IMEX's weighted
  start fluxes, and @3's label_errors reading each kind's reasons from the model;
- the unlabelled step's jaxpr is unchanged by each mover's hook.
"""

import contextlib
import copy
import dataclasses

import jax
import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.kinds import passive_routes, transporter
from cells.laws.cycles.forms import CycleForm, Saturation
from cells.laws.electrochemistry import F, R, bernoulli
from cells.models import surface_pump_v3
from cells.numerics import label_shares
from cells.registry import kind_registry
from cells.registry import laws as law_registry
from cells.registry.inventory_species import add_inventory_species
from cells.registry.models import get_model
from tests.unit import test_cycle_kind as ck
from tests.unit import test_transporter_kind as tk
from validation.compartment_ph_engine import definitions as fr
from validation.tissue import secreted_species_fixtures as fx

LAW = "cells.operator.neutral_arrival_labels@1"
EPS = np.finfo(float).eps
CELL, NODE, BATH = "cell_0", "ecs_0", "bath"
RATE = 10.0  # 1/s: 1e15 P A (1/V_cell + 1/V_node), each 1 pL, S's exchange relaxation rate.
P_S = RATE / (1e15 * fx.CONTACT_AREA_M2 * 2.0)
P_WALL = 1e-5  # m/s: Y's leak to the bath, about 1/s through the wall patch.
S_mM = 1.0  # S in the cell, and in the node by default: it crosses at zero net flux.
DRIVE0_J_MOL = tk.DRIVE0_J_MOL


def bits(value):
    return np.asarray(value).tobytes()


def kinds_world(*, dt=1e-3, steps=100, labelled=True, node_mM=S_mM):
    """The compiled world (module docstring): the contact patch joins cell_0 and its node ecs_0 (1
    pL each), the wall patch joins the cell to the held bath. S starts labelled a in the cell and
    b in the node; node_mM, S's concentration there (S_mM: zero net flux)."""
    end = dt * steps
    raw = fx.world(
        faces=(),
        concentrations_mM={CELL: S_mM, NODE: node_mM},
        dt=dt,
        end=end,
        observation_times=fx.grid_times(end, dt, end / 4),
    )
    fuel = {"Y": {CELL: 1.0, NODE: 1.0, BATH: 1.0}, "ATP": {CELL: 3.0}, "ADP": {CELL: 0.3}}
    for name, at in (*fuel.items(), ("Pi", {CELL: 3.0})):
        raw = add_inventory_species(
            raw, name, trace_mM=1e-6, diffusivity_m2_per_s=fx.D_S, floor_fmol=1e-12,
            concentrations_mM=at,
        )  # fmt: skip
    m = raw["model"]
    m["standard_concentration_mM"] = 1000.0  # The fuel's potentials (tk.held_world's).
    mu = dict(ATP=0.0, ADP=DRIVE0_J_MOL / (R * m["temperature_K"]), Pi=0.0)
    for entry in m["species"]:
        if entry["id"] in mu:
            entry["standard_mu_RT"] = mu[entry["id"]]
    (wall,) = (p for p in m["membranes"] if p["id"] == f"wall_{CELL}")
    wall["permeability_m_per_s"]["Y"] = P_WALL
    m[passive_routes.MODEL_KEY] = [
        dict(id="route_S", patch="contact_0", law=passive_routes.LAW_ID, species="S",
             permeability_m_per_s=P_S)
    ]  # fmt: skip
    m[transporter.MODEL_KEY] = [tk.population(id="pump_Y", patch="contact_0", capacity_fmol_s=1.0)]
    if labelled:
        m["operators"].append(
            dict(
                law=LAW,
                species=[
                    dict(id="S", labels=["a", "b"], initial=[dict(node=NODE, shares={"b": 1.0})]),
                    dict(id="Y", labels=["base", "x"], initial=[dict(node=CELL, shares={"x": 1})]),
                ],
            )
        )
        raw["experiment"]["label_arrivals"] = []
    return raw


@pytest.fixture(scope="module")
def runs():
    from cells.execution.runner import run

    spec = parse_spec(kinds_world())
    return spec, run(spec), run(parse_spec(kinds_world(labelled=False)))


def test_kinds_carry_the_labels_and_change_nothing_physical(runs):
    """Labelled against unlabelled: every history field, observation and diagnostic bit for bit,
    with the passive route's and the transporter's transfers non-zero; the closure diagnostic at
    rounding (every mover of S and Y reported, the pump beside @3's own route at the cell). At zero
    net flux S's amounts never change, and its labels exchange at the route's one-way rate P A c:
    the cell's label a is (1 + e^(-k t)) / 2, k = 1e15 P A (1/V_cell + 1/V_node), at rounding (the
    update's predictor-corrector gives the two nodes' difference e^(-2u) per step exactly). Y's
    label x reached the node through the pump alone."""
    from tests.unit.test_neutral_arrival_labels import same_physics

    spec, labelled, plain = runs
    same_physics(labelled, plain)
    final, ids = labelled.final.state, list(spec.model.species_ids)
    assert float(np.max(final.label_closure_relative)) <= 64 * EPS
    obs, times = labelled.observations, np.asarray(spec.experiment.observation_times)
    s, y = ids.index("S"), ids.index("Y")
    cell = np.asarray(obs.amount)[:, :, 0]  # [time, species] at cell_0.
    node = np.asarray(obs.extracellular_amount)[:, :, 1]  # ecs_0, after the held bath.
    assert np.all(cell[:, s] == cell[0, s]) and np.all(node[:, s] == node[0, s])  # Zero net.
    closed = 0.5 * (1.0 + np.exp(-RATE * times))
    inside = np.asarray(obs.label_share)[:, 0, 0, 0]  # S's label a in the cell and the node.
    outside = np.asarray(obs.label_outside_share)[:, 0, 0, 1]
    np.testing.assert_allclose(inside, closed, rtol=0, atol=16 * EPS)
    np.testing.assert_allclose(outside, 1.0 - closed, rtol=0, atol=16 * EPS)
    pumped = float(final.transporter_cycles[1])  # The contact patch, after the wall.
    assert pumped > 0.01 and float(node[-1, y] - node[0, y]) == pytest.approx(pumped, rel=1e-12)
    # Y's label x at ecs_0: what the pump carried from the cell, whose x share fell from 1 to about
    # e^(-0.1) as the wall's one-way inflow (1/s) brought the bath's base in.
    x_node = float(np.asarray(obs.label_outside_share)[-1, 1, 1, 1] * node[-1, y])
    assert 0.9 * pumped < x_node < pumped


# ------------------------------------------------------------------ host rows (NumPy)


def host(raw, kinds=None):
    """(spec, impl, state, p, control) of a world's inner @3 definition on the host, its label
    owner and other operators dropped; kinds: a test registry to build it in."""
    raw = copy.deepcopy(raw)
    m = raw["model"]
    if "inner_model" in m:
        m["id"] = m.pop("inner_model")
    m.pop("operators", None)
    raw["experiment"].pop("label_arrivals", None)
    spec = parse_spec(raw)
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    return spec, impl, state, p, control


def potentials_at(p, cell, outside=0.0):
    out = np.full(p.active.size + p.outside_active.size, outside)
    out[: p.active.size] = cell
    return out


RECTIFIER_NA = dict(
    id="rectifier_Na", patch=f"wall_{CELL}", law=passive_routes.RECTIFIER_LAW_ID, species="Na",
    g_ref_S_per_m2=1.0, k_ref_mM=5.0, v_half_V=0.01, slope_V=0.01,
)  # fmt: skip
# A test-only law whose one mode takes two of a species at N for one at P (its role bound to the
# exchange world's W, whose potential the registry declares): no crossing, refused beside labels.
UNEQUAL_LAW = law_registry.CycleLaw(
    "seamtest.cycle.unequal_crossing@1",
    (),
    (),
    None,
    None,
    cycle=CycleForm(
        kinetics="factored",
        roles=(("Z", 0),),
        rows=(("Z", "N"), ("Z", "P")),
        modes=(("cyc", (-2, 1)),),
        saturation=((Saturation(("Z", "N"), 1.0, 1),),),
    ),
    host=transporter.KIND_ID,
    provenance="calibrated",
    source="a test-only law with unequal counts at its two ends, never shipped",
)
UNEQUAL = dict(
    id="p_unequal", host="membrane_0", law=UNEQUAL_LAW.law_id, orientation={"N": "a"},
    capacity_fmol_s=0.05, roles={"Z": "W"}, parameters={}, held_rows=[],
)  # fmt: skip


@contextlib.contextmanager
def cycle_scope():
    """The cycle kind's test registries (tests/unit/test_cycle_kind.py) with UNEQUAL_LAW too."""
    laws = law_registry.BUILTIN.extended(*ck.TEST_LAWS, UNEQUAL_LAW)
    with ck.scoped(), law_registry.scope(laws):
        yield


def routes_world():
    """The compiled world's host side with S at half the cell's concentration in the node, a
    charged route for K on the contact patch and an unlabelled inward rectifier for Na on the
    wall beside them."""
    raw = kinds_world(labelled=False, node_mM=0.5 * S_mM)
    m = raw["model"]
    m[passive_routes.MODEL_KEY] += [
        dict(id="route_K", patch="contact_0", law=passive_routes.CHARGED_LAW_ID, species="K",
             permeability_m_per_s=1e-8),
        RECTIFIER_NA,
    ]  # fmt: skip
    for node in m["cells"]:
        node["initial_amount_fmol"]["K"] *= 2.0  # An uphill K gradient, against the voltage.
        node["fixed_charge_equivalent_fmol"] -= node["initial_amount_fmol"]["K"] / 2.0
    return raw


def route_terms(view, p, row):
    """[route] P A m c B(-+x) / MOL at each end, written from the constant-field law: the inward
    term from the outside end, the outward from the inside end (the neutral law at x = 0)."""
    from cells.laws.electrochemistry import MOL_PER_FMOL

    c_in, c_out = passive_routes._ends(view.read, p, np)
    opening = passive_routes._opening(view.read, view.control, p, np)
    voltage = view.potentials[p.passive_inside] - view.potentials[p.passive_outside]
    z = np.where(p.passive_leak | getattr(p, "passive_charged", False), p.valence[row], 0.0)
    x = np.reshape(z, (-1,)) * F * voltage / (R * p.temperature)
    scale = p.passive_area * p.passive_permeability[row] * opening / MOL_PER_FMOL
    return scale * c_out[row] * bernoulli(x, xp=np), scale * c_in[row] * bernoulli(-x, xp=np)


ROUTES = {  # Each law's world, its labelled row and its route.
    "neutral": (routes_world, "S", "route_S"),
    "charged": (routes_world, "K", "route_K"),
    "proton leak": (lambda: fr.development_world(fr.fr4_world()), "H", "proton_leak_0"),
}


@pytest.mark.parametrize("law", list(ROUTES))
def test_a_routes_one_way_terms_are_its_kernels_two_terms(law):
    """Forward - backward is the kernel's own flux at rounding, both >= 0, each the constant-field
    law's term at its source end (so a halved, swapped or misplaced term shows), at a membrane
    voltage of -50 mV; a route that does not carry the row (the rectifier's included) reports 0."""
    build, row_id, route_id = ROUTES[law]
    spec, impl, state, p, control = host(build())
    row = list(spec.model.species_ids).index(row_id)
    view = surface_pump_v3.LabelView(state, state, potentials_at(p, -0.05), control)
    if law == "proton leak":  # The leak reads free h through B4's stage read.
        structure = surface_pump_v3.structure(spec.model)
        read = surface_pump_v3._stage_read(state, p, surface_pump_v3._kinds(structure), xp=np)[0]
        view = view._replace(read=read)
    inward, outward = passive_routes.one_way_fluxes(view, p, np.asarray([row]), xp=np)
    net = passive_routes._flux(view.read, view.potentials, view.control, p, xp=np).flux[row]
    k = [r.id for r in dict(spec.model.kinds)[passive_routes.KIND_ID]].index(route_id)
    assert inward[0, k] > 0 and outward[0, k] > 0 and net[k] != 0
    assert inward[0, k] - outward[0, k] == pytest.approx(net[k], rel=1e-14, abs=0)
    terms = route_terms(view, p, row)
    assert inward[0, k] == pytest.approx(terms[0][k], rel=1e-14, abs=0)
    assert outward[0, k] == pytest.approx(terms[1][k], rel=1e-14, abs=0)
    others = np.arange(inward.shape[1]) != k
    carried = p.passive_permeability[row] > 0
    assert np.all(np.isfinite(inward)) and np.all(np.isfinite(outward))
    assert np.all(inward[0, others & ~carried] == 0) and np.all(outward[0, others & ~carried] == 0)


def _probe_population(raw, kinds, scope, volts):
    with scope(*kinds):
        spec, impl, state, p, control = host(raw)
        view = surface_pump_v3.LabelView(state, state, potentials_at(p, volts), control)
        plus, minus = transporter._population_one_way(view, p, xp=np)
        e = transporter._evaluate(state, view.potentials, control, p, xp=np)
    return plus, minus, e.j, e.x, p


CYCLES = {  # Each kinetic form's world, its kinds and the registry scope it needs.
    "version 1, neutral": (lambda: tk.held_world(), (), tk.scoped),
    "version 1, proton": (tk.charged_world, tk.CHARGED_KINDS, tk.scoped),
    "factored": (lambda: tk.held_world(ck.general(tk.population())), (), ck.scoped),
    "diagram": (lambda: ck.exchange_world(ck.exchanger()), (), ck.scoped),
    "monomial": (ck.mono_world, (), ck.mono_scoped),
}


@pytest.mark.parametrize("form", list(CYCLES))
def test_a_cycles_one_way_rates_are_j_plus_and_j_plus_e_to_the_x(form):
    """J+ - J- is the law's own signed cycle rate at rounding, both >= 0, and J- / J+ = e^x with x
    its own dG_cyc / RT (so a halved or swapped rate shows), at a membrane voltage of -30 mV, in
    version 1's two laws and the population axis's factored, diagram and monomial forms."""
    build, kinds, scope = CYCLES[form]
    raw, volts = build(), -0.03
    if form.startswith("version 1"):
        with scope(*kinds):
            spec, impl, state, p, control = host(raw)
            view = surface_pump_v3.LabelView(state, state, potentials_at(p, volts), control)
            if kinds:  # The proton law reads free h through B4's stage read.
                bound = surface_pump_v3._kinds(surface_pump_v3.structure(spec.model))
                view = view._replace(read=surface_pump_v3._stage_read(state, p, bound, xp=np)[0])
            plus, minus = transporter._version_1_one_way(view, p, xp=np)
            a = control.transporter_availability
            j, energy, _, _ = transporter.kinetics(view.read, view.potentials, a, p, xp=np)
        x, on = energy / (R * p.temperature), p.transporter_present
    else:
        plus, minus, j, x, p = _probe_population(raw, kinds, scope, volts)
        on = p.cycle_mode_present & p.cycle_present[None, :]
    assert np.all(plus[on] > 0) and np.all(minus[on] > 0) and np.all(j[on] != 0)
    np.testing.assert_allclose((plus - minus)[on], j[on], rtol=4e-14, atol=0)
    np.testing.assert_allclose((minus / np.where(on, plus, 1.0))[on], np.exp(x[on]), rtol=1e-13)


def test_a_net_flow_population_beside_reports_finite_zeros():
    """A net-flow mode has no one-way form: its J+ and J- (NaN in the evaluation) are selected to
    0 before any arithmetic, so a labelled row beside it reads finite amounts."""
    raw = ck.exchange_world(ck.exchanger(law="seamtest.cycle.net_exchange@1"))
    plus, minus, j, _, p = _probe_population(raw, (), ck.scoped, -0.03)
    assert np.all(plus == 0) and np.all(minus == 0) and np.any(j != 0)


def _gaps(raw, row_id, one_way, booked, *, steps=(4e-3, 2e-3, 1e-3)):
    """The booked net less the trapezoid of the kind's one-way fluxes (forward - backward) over one
    host step from the world's start, at each dt: what the hook adds on the gap's side."""
    spec, impl, state, p, control = host(raw)
    rows = np.asarray([list(spec.model.species_ids).index(row_id)])
    structure = surface_pump_v3.structure(spec.model)
    kinds = surface_pump_v3._kinds(structure)
    out = []
    for dt in steps:
        end, valid = impl.imex_step(state, dt, control, p, xp=np)
        assert bool(valid)
        views = [
            surface_pump_v3.crossing_view(s, control, p, xp=np, kinds=kinds, structure=structure)[0]
            for s in (state, end)
        ]
        net = [np.subtract(*one_way(v, p, rows)) for v in views]
        trapezoid = 0.5 * dt * (net[0] + net[1])
        out.append(float(np.max(np.abs(booked(end, rows) - booked(state, rows) - trapezoid))))
    return out


def test_the_gap_to_the_booked_net_falls_as_dt_cubed():
    """The gap the hook adds on one side is the booked net less the trapezoid of the one-way
    fluxes at the step's two ends: O(dt^3), falling 8 times per halving of dt under ARS(2,2,2)
    (8.000 and 8.005 to 8.009 measured), for a neutral route (S at a tenth of the cell's in the
    node) and the transporter (Y)."""
    raw = kinds_world(labelled=False, node_mM=0.1 * S_mM)
    route = _gaps(
        raw, "S",
        lambda v, p, rows: passive_routes.one_way_fluxes(v, p, rows, xp=np),
        lambda s, rows: np.asarray(s.passive_transferred)[rows],
    )  # fmt: skip
    pump = _gaps(
        raw, "Y",
        lambda v, p, rows: transporter._version_1_one_way(v, p, xp=np),
        lambda s, rows: np.asarray(s.transporter_cycles),
    )  # fmt: skip
    for gaps in (route, pump):
        ratios = [gaps[i] / gaps[i + 1] for i in range(len(gaps) - 1)]
        assert gaps[-1] > 0 and all(7.5 < r < 8.5 for r in ratios), gaps


def exchange_shares(raw, steps, *, planted=None):
    """S's label a in the cell after each of `steps` host steps of @3's labelled step, its shares
    advanced from the step's transfers as the label owner does (label_shares.advance_transfers),
    with the passive routes' hook, or `planted` in its place."""
    kinds = None
    if planted is not None:
        kinds = kind_registry.KindRegistry()
        for kind in (passive_routes.PASSIVE_ROUTES, transporter.TRANSPORTER):
            kinds.register(
                dataclasses.replace(kind, label_transfers=planted)
                if kind is passive_routes.PASSIVE_ROUTES
                else kind
            )
    scope = kind_registry.scope(kinds) if kinds is not None else contextlib.nullcontext()
    with scope:
        spec, impl, state, p, control = host(raw)
        rows = np.asarray([list(spec.model.species_ids).index("S")])
        dt = spec.execution.dt
        n = p.active.size
        shares = np.zeros((1, 2, n + p.outside_active.size))
        shares[:, 1, :] = 1.0  # Label b everywhere but the cell.
        shares[:, :, 0] = (1.0, 0.0)  # The cell's S starts as label a.
        present, held = np.ones((1, 2), dtype=bool), np.concatenate((np.zeros(n), p.reservoir))
        out = []
        for _ in range(steps):
            end, valid, transfers = impl.imex_step(state, dt, control, p, xp=np, labels=rows)
            assert bool(valid)
            amounts = [
                np.concatenate(
                    (p.amount_reference + s.amount_increment,
                     p.extracellular_amount_reference + s.extracellular_amount_increment),
                    axis=1,
                )[rows]
                for s in (state, end)
            ]  # fmt: skip
            shares = label_shares.advance_transfers(
                shares, *amounts, transfers, present, held.astype(bool), xp=np
            )
            out.append(float(shares[0, 0, 0]))
            state = end
    return np.asarray(out)


def halved(start, end, p, dt, rows, *, weight=None, xp):
    """A planted hook: the routes' one-way amounts halved (forward - backward still the booked net
    at zero net flux, so the closure cannot see it)."""
    out = passive_routes.label_transfers(start, end, p, dt, rows, weight=weight, xp=xp)
    return tuple((0.5 * amount, source, destination) for amount, source, destination in out)


def test_zero_net_exchange_follows_the_one_way_rate_and_a_halved_split_fails():
    """S at equal concentrations in the cell and its node crosses at zero net flux, so the
    closure cannot see how its one-way amounts are split. Through @3's step and the owner's
    update, the cell's label a relaxes as (1 + e^(-k t)) / 2, k = 1e15 P A (1/V_cell + 1/V_node),
    from the route's one-way rate P A c alone, at rounding (2.2e-16 measured: the update's
    predictor-corrector gives the nodes' difference e^(-2u) per step exactly). Halving the hook's
    one-way amounts leaves the closure exact and misses the closed form by 0.074."""
    raw = kinds_world(labelled=False, steps=40)
    times = 1e-3 * np.arange(1, 41)
    closed = 0.5 * (1.0 + np.exp(-RATE * times))
    honest = exchange_shares(raw, 40)
    assert np.max(np.abs(honest - closed)) <= 16 * EPS
    planted = exchange_shares(raw, 40, planted=halved)
    assert np.max(np.abs(planted - closed)) > 0.05


def face_world(*, kind=True):
    """S moved by the face between the node and the held bath, labelled; Q crossing the contact
    patch by a passive route where `kind` (unlabelled), else impermeant (the kind-free twin)."""
    raw = fx.world(concentrations_mM={NODE: 1e-3, CELL: 1e-3}, end=0.004, dt=1e-3)
    raw = add_inventory_species(
        raw, "Q", trace_mM=fx.TRACE_mM, diffusivity_m2_per_s=fx.D_S, floor_fmol=fx.FLOOR_FMOL,
        concentrations_mM={CELL: 1.0, NODE: 0.5},
    )  # fmt: skip
    for face in raw["model"]["faces"]:  # Q does not cross the face: only the route moves it.
        face["diffusivity_m2_per_s"]["Q"] = 0.0
    if kind:
        raw["model"][passive_routes.MODEL_KEY] = [
            dict(id="route_Q", patch="contact_0", law=passive_routes.LAW_ID, species="Q",
                 permeability_m_per_s=1e-6)
        ]  # fmt: skip
    raw["model"]["operators"].append(
        dict(law=LAW, species=[dict(id="S", labels=["base", "x"], initial=[])])
    )
    raw["experiment"]["label_arrivals"] = []
    return raw


def test_a_kind_carrying_q_leaves_labelled_face_transport_admitted_and_unchanged():
    """A passive route carrying Q, unlabelled, beside S moved by a face: the definition with S
    labelled is admitted and its inner step reports (before the hook, any declared kind turned
    the reports off and refused every labelled in-step mover), and S's face transfers over a step
    are the kind-free twin's bit for bit; the kind's own transfers follow the core's."""
    composite = get_model(parse_spec(face_world()).model)
    assert composite.inner_reports_labels
    steps = []
    for kind in (True, False):
        spec, impl, state, p, control = host(face_world(kind=kind))
        rows = np.asarray([list(spec.model.species_ids).index("S")])
        steps.append(impl.imex_step(state, 1e-3, control, p, xp=np, labels=rows)[2])
    with_kind, twin = steps
    assert len(with_kind) == len(twin) + 2  # The route's inward and outward transfers.
    for i in (0, 1):  # The face's two directions, the core's first.
        assert float(np.max(np.asarray(twin[i][0]))) > 0
        for a, b in zip(with_kind[i], twin[i], strict=True):
            assert bits(a) == bits(b)


def admitted(case):
    """(a labelled definition beside kinds that report, the registry scope it parses in)."""
    from tests.unit import test_fr5_source_kinds as fr5
    from tests.unit.test_neutral_arrival_labels import mover, with_labels

    if case == "version 1's pump role":
        raw = cs.frozen_definition(tk.held_world())
        return with_labels(raw, [("Y", ["base"], {})]), contextlib.nullcontext()
    if case == "a population's role beside its finite fuel":
        return mover("role"), contextlib.nullcontext()
    if case == "a diagram's two crossing roles":
        raw = cs.frozen_definition(ck.exchange_world(ck.exchanger()))
        return with_labels(raw, [("W", ["base"], {}), ("X", ["base"], {})]), ck.scoped()
    raw = fr.development_world(fr.fr4_world())  # FR-4's kinds and FR-5's source kinds.
    raw = cs.frozen_definition(raw)  # A composite without FR-1's compartment operator.
    raw["model"]["patch_damage"] = [copy.deepcopy(fr5.DAMAGE)]
    raw["model"]["ph_conditions"] = [copy.deepcopy(fr5.CONDITION)]
    return with_labels(raw, [("K", ["base"], {})]), contextlib.nullcontext()


ADMITTED = (
    "version 1's pump role",
    "a population's role beside its finite fuel",
    "a diagram's two crossing roles",
    "FR-4's and FR-5's kinds beside @3's K route",
)


@pytest.mark.parametrize("case", ADMITTED)
def test_labels_beside_kinds_are_admitted_where_the_kinds_report(case):
    """Parses only: a crossing row a transporter moves (version 1's and the population axis's,
    beside finite fuel; a diagram's two roles), and K labelled beside every FR-4 and FR-5 kind
    (the stage read, the pump, the leak, patch damage, whose label_refusals give none since it
    moves no row, and the pH condition), are admitted, the inner step reporting."""
    raw, scope = admitted(case)
    with scope:
        assert get_model(parse_spec(raw).model).inner_reports_labels


def _jaxpr(raw, registry):
    with kind_registry.scope(registry):
        spec, impl, state, p, control = host(raw)
        traced = jax.make_jaxpr(lambda s, c, q: impl.imex_step(s, 1e-3, c, q))(state, control, p)
    return str(traced)


def _registry(kinds, *, strip):
    registry = kind_registry.KindRegistry()
    for kind in kinds:
        if strip:
            kind = dataclasses.replace(kind, label_refusals=None, label_transfers=None)
        registry.register(kind)
    return registry


MOVERS = {  # Each mover's world, its kinds and the law registry it needs.
    "a passive route and version 1's transporter": (
        lambda: kinds_world(labelled=False),
        (passive_routes.PASSIVE_ROUTES, transporter.TRANSPORTER),
        None,
    ),
    "the population axis": (
        lambda: ck.exchange_world(ck.exchanger()),
        (transporter.TRANSPORTER,),
        ck.TEST_LAWS,
    ),
}


@pytest.mark.parametrize("mover", list(MOVERS))
def test_the_unlabelled_step_is_unchanged_by_each_movers_hook(mover):
    """The hook is a static switch (D148 case 2): the unlabelled step's jaxpr with the kinds as
    registered is the one with their two label hooks removed."""
    build, kinds, laws = MOVERS[mover]
    raw = build()
    scope = contextlib.nullcontext()
    if laws:
        scope = law_registry.scope(law_registry.BUILTIN.extended(*laws))
    with scope:
        text = [_jaxpr(raw, _registry(kinds, strip=strip)) for strip in (False, True)]
    assert text[0] == text[1] and len(text[0]) > 10_000


def axis_world(case):
    """(the world, its labelled species, its scope) of each population-axis case."""
    if case == "factored, N at the cell":
        return tk.held_world(ck.general(tk.population())), ["Y"], ck.scoped()
    if case == "factored, N at the bath":
        return tk.held_world(ck.general(tk.population(), n_end="b")), ["Y"], ck.scoped()
    if case == "diagram, two crossing rows":
        return ck.exchange_world(ck.exchanger()), ["W", "X"], ck.scoped()
    raw = ck.exchange_world(ck.exchanger(law="seamtest.cycle.net_exchange@1"))
    raw["execution"]["dt"] = 1e-4  # A step every form admits (test_cycle_kind's four_steps).
    return raw, ["Y"], ck.scoped()  # Y: moved by nothing, beside a net-flow population.


@pytest.mark.parametrize(
    "case",
    [
        "factored, N at the cell",
        "factored, N at the bath",
        "diagram, two crossing rows",
        "net flow beside an untouched row",
    ],
)
def test_the_population_axis_reports_its_crossings_through_the_labelled_step(case):
    """@3's labelled host step with the population axis: the state and validity are the
    unlabelled step's bit for bit; the pump's two transfers run N to P and P to N, every amount
    finite and >= 0; and N to P less P to N is each row's move out of N, the cell's change with
    its sign, at rounding (the bath is held). A net-flow population beside reports finite zeros
    (its NaN one-way rates are selected out)."""
    raw, labelled, scope = axis_world(case)
    with scope:
        spec, impl, state, p, control = host(raw)
        rows = np.asarray([list(spec.model.species_ids).index(s) for s in labelled])
        dt = spec.execution.dt
        plain = impl.imex_step(state, dt, control, p, xp=np)
        end, valid, transfers = impl.imex_step(state, dt, control, p, xp=np, labels=rows)
    assert bool(plain[1]) and bool(valid)
    assert all(bits(a) == bits(b) for a, b in zip(plain[0], end, strict=True))
    (to_p, n_node, p_node), (to_n, back_p, back_n) = transfers[-2:]
    assert bits(n_node) == bits(back_n) and bits(p_node) == bits(back_p)
    for amount in (to_p, to_n):
        assert np.all(np.isfinite(amount)) and np.all(amount >= 0)
    net = (to_p - to_n)[:, 0]
    if case.startswith("net flow"):
        assert np.all(to_p == 0) and np.all(to_n == 0)
        return
    cell = int(n_node[0]) < p.active.size  # Whether N is the cell (else the held bath).
    change = (end.amount_increment - state.amount_increment)[rows, 0]
    np.testing.assert_allclose(net, -change if cell else change, rtol=4 * EPS, atol=0)
    assert np.all(net != 0) and np.all(to_n > 0)  # Both directions run.


def test_the_euler_imex_weights_each_kinds_start_fluxes():
    """Under the Euler IMEX each kind's hook takes weight = dt a[last, 0] times its one-way
    fluxes at the start (its end view the state alone): the state is the unlabelled step's bit for
    bit, and the passive route's and the pump's forward less backward are their booked nets at
    rounding, every amount >= 0."""
    raw = kinds_world(labelled=False, node_mM=0.1 * S_mM)
    raw["execution"]["solver"] = "cells.solver.imex_euler_face_electromigration@1"
    spec, impl, state, p, control = host(raw)
    ids = list(spec.model.species_ids)
    rows = np.asarray([ids.index("S"), ids.index("Y")])
    dt = spec.execution.dt
    plain = impl.imex_step(state, dt, control, p, xp=np)
    end, valid, transfers = impl.imex_step(state, dt, control, p, xp=np, labels=rows)
    assert bool(valid) and all(bits(a) == bits(b) for a, b in zip(plain[0], end, strict=True))
    inward, outward, pumped, back = (t[0] for t in transfers[-4:])
    assert all(np.all(t[0] >= 0) for t in transfers)
    booked = (end.passive_transferred - state.passive_transferred)[rows]
    np.testing.assert_allclose(inward - outward, booked, rtol=4 * EPS, atol=0)
    cycles = end.transporter_cycles - state.transporter_cycles  # Y's stoichiometry is 1.
    np.testing.assert_allclose((pumped - back)[1], cycles, rtol=4 * EPS, atol=0)
    assert float(np.max(np.abs(booked))) > 0 and float(np.max(cycles)) > 0


def test_label_errors_take_each_kinds_reasons_from_the_model():
    """@3's host-side label_errors: given the parsed model, the declared kinds' own reasons (here a
    rectifier carrying the labelled Na, none for S); without the model, kinds stay refused."""
    spec, impl, state, p, control = host(routes_world())
    structure = surface_pump_v3.structure(spec.model)
    ids = list(spec.model.species_ids)
    for species, refused in (("S", False), ("Na", True)):
        rows = (ids.index(species),)
        errors = surface_pump_v3.label_errors(p, rows, structure=structure, model=spec.model)
        assert any("rectifier_Na runs" in e for e in errors) == refused, (species, errors)
    blanket = surface_pump_v3.label_errors(p, (ids.index("S"),), structure=structure)
    assert any("need the parsed model" in e for e in blanket)


@pytest.mark.parametrize("own", [False, True])
@pytest.mark.parametrize("solver", [None, "cells.solver.imex_euler_face_electromigration@1"])
def test_labels_beside_one_way_records_share_the_steps_ends_and_change_nothing(solver, own):
    """FR-50 (D327) beside FR-42: the world's route and pump keep one-way records too, and with
    `own` (phase 2) @3's wall patch keeps its own Y record (its one_way_records). Over three host
    steps, under ARS(2,2,2) and the Euler IMEX, the labelled transfers are the labelled-only twin's
    bit for bit, the records the recorded-only twin's, and every shared field all three twins'.
    Records and labels read one end view of each step."""
    raw = kinds_world(labelled=False)
    if solver:
        raw["execution"]["solver"] = solver
    recorded = copy.deepcopy(raw)
    recorded["model"][passive_routes.MODEL_KEY][0]["one_way"] = True
    recorded["model"][transporter.MODEL_KEY][0]["one_way"] = True
    if own:
        recorded["model"]["one_way_records"] = [
            dict(entity="membrane", id=f"wall_{CELL}", species=["Y"])
        ]
    twins = {}
    for name, world, labelled in (("labels", raw, True), ("records", recorded, False),
                                  ("both", recorded, True)):  # fmt: skip
        spec, impl, state, p, control = host(world)
        rows = np.asarray([list(spec.model.species_ids).index(s) for s in ("S", "Y")])
        transfers = []
        for _ in range(3):
            asks = dict(labels=rows) if labelled else {}
            out = impl.imex_step(state, 1e-3, control, p, xp=np, **asks)
            state, valid = out[0], out[1]
            assert bool(valid)
            transfers.append(out[2] if labelled else None)
        twins[name] = (state, transfers)
    (labels, label_transfers), (records, _), (both, both_transfers) = twins.values()
    for a, b in zip(label_transfers, both_transfers, strict=True):
        assert bits(np.concatenate([np.ravel(x) for t in a for x in t])) == bits(
            np.concatenate([np.ravel(x) for t in b for x in t])
        )
    for name in type(both)._fields:
        assert bits(getattr(both, name)) == bits(getattr(records, name)), name
        if name in type(labels)._fields:
            assert bits(getattr(both, name)) == bits(getattr(labels, name)), name
    assert np.all(both.passive_inward_fmol > 0) and np.all(both.transporter_forward_fmol[1] > 0)
    if own:
        assert np.all(both.one_way_forward_fmol > 0) and np.all(both.one_way_backward_fmol > 0)
