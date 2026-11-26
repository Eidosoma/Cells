"""The charged constant-field law on junction hosts (FR-15 F2, D310; cells.kind.passive_routes@1).

docs/CHARGED_TRACE_SPECIES_DESIGN.md §3 (option A) and §8, ruled in D310. The junction pair: two
1 pL cells of fx.world, each with its wall patch on the held bath, joined by one junction whose
gate is pinned open, on which cells.route.passive_constant_field_permeation@1 carries the anion X (z = -1).
- On each host kind (the junction, a patch on a finite node, a patch on the held bath), the
  route's rate, material term and stage term are the constant-field law written out: the two
  ends' slopes summed where both relax, 2G at each of a junction's cells. Planted on the law's
  kernel, the valence's sign, the voltage's orientation and the ends' concentrations each fail.
- Each junction term refuses the step it bounds, and planted at half admits it.
- A charged row drifts across a junction to its closed forms: at a trace, the held voltage's
  exponential to the Nernst ratio; with its own charge, the equilibrium in which the capacitor
  closure moves the voltage (an independent bisection), far from the closure-blind references.
- A reacting charged trace row beside cells.operator.local_species_reactions@1 reaches its linear steady state
  (the microRNA's shape).
- The charged law refuses a neutral row on a junction, and a junction that crosses a floating
  capacitor component in a composite beside cells.operator.local_species_reactions@1. The plain @3 crossing row is
  the kind file's (test_passive_routes_kind.py), where the blanket junction refusal's row was
  (D310's sanctioned change).
The kind file keeps its tier-2 cost (D224); these rows hold their own: two compiles, 61 s on the
timed lane (CPU 4 under its lock, at b82856ad), the kind file 70 s.
"""

import copy
import dataclasses
import re

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.runner import run
from cells.kinds import passive_routes
from cells.laws.electrochemistry import CHARGE_PER_FMOL, F, R, bernoulli
from cells.laws.junctions import junction_gate
from cells.models import surface_pump_v3
from cells.registry import kind_registry
from cells.registry.inventory_species import add_inventory_species
from cells.registry.models import get_model
from tests.unit.test_passive_routes_kind import charged_pair
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import species_reactions_fixtures as rfx

CHARGED = passive_routes.CHARGED_LAW_ID


P_X = 5e-3  # m/s: A P (1/V_a + 1/V_b) = 100/s between the junction's two 1 pL cells at V = 0.
VOLT = 0.025 * fx.WALL_C_F / (F * 1e-15)  # fmol of charge that holds 25 mV on a wall patch.


def junction_pair(
    *, a_mM=1e-9, b_mM=5e-10, voltage_fmol=0.0, end=0.04, dt=2.5e-5, crossing=False,
    composite=False,
):  # fmt: skip
    """Two 1 pL cells of fx.world, each with its wall patch on the held bath, joined by one
    junction j_ab whose gate is pinned open (minimum open fraction 1), on which the charged law
    carries the anion X (z = -1) at P_X; every ion and S impermeant, so the cells' anchors
    (+voltage_fmol at cell_a, -voltage_fmol at cell_b) hold a junction voltage that no ion moves.
    crossing: cell_b's only patch faces a finite node ecs_b, joined to the bath by a face, so its
    capacitor component floats and j_ab crosses it. composite: the frozen composite form, for an
    operator beside the route."""
    kw = dict(nodes=(), contacts=(), faces=())
    if crossing:
        kw = dict(
            nodes=(("ecs_b", 1.0),),
            contacts=(("contact_b", "cell_b", "ecs_b"),),
            faces=(("face_b", "ecs_b", "bath", 1e-10, 1e-5),),
        )
    raw = fx.world(
        cells=(("cell_a", 1.0), ("cell_b", 1.0)),
        junctions=(("j_ab", "cell_a", "cell_b"),),
        dt=dt,
        end=end,
        **kw,
    )
    m = raw["model"]
    if not composite:
        m["id"] = "cells.model.resolved_pump_tissue@3"
        m.pop("inner_model")
        m.pop("operators")
    if crossing:  # cell_b keeps only its contact patch: its component holds no reservoir.
        m["membranes"] = [patch for patch in m["membranes"] if patch["id"] != "wall_cell_b"]
        controls = raw["experiment"]["membrane_controls"]
        raw["experiment"]["membrane_controls"] = [
            c for c in controls if c["membrane_id"] != "wall_cell_b"
        ]
        raw["execution"]["membrane_capacity"] = len(m["membranes"])
    raw = add_inventory_species(
        raw, "X", trace_mM=fx.TRACE_mM, diffusivity_m2_per_s=fx.D_S, floor_fmol=fx.FLOOR_FMOL,
        concentrations_mM=dict(cell_a=a_mM, cell_b=b_mM),
    )  # fmt: skip
    m = raw["model"]
    next(s for s in m["species"] if s["id"] == "X")["valence"] = -1
    for node in (*m["cells"], *m["extracellular"]):  # Each node stays neutral (z = -1).
        node["fixed_charge_equivalent_fmol"] += node["initial_amount_fmol"]["X"]
    for cell, sign in ((m["cells"][0], 1.0), (m["cells"][1], -1.0)):  # cell_a, cell_b.
        cell["fixed_charge_equivalent_fmol"] += sign * voltage_fmol
        cell["initial_charge_C"] += sign * voltage_fmol * CHARGE_PER_FMOL
    m["junctions"][0]["gate"] = dict(
        law=junction_gate.LAW_ID, threshold_voltage_V=fx.JUNCTION_THRESHOLD_V,
        minimum_open_fraction=1.0, initial_gate=1.0,
    )  # fmt: skip
    m[passive_routes.MODEL_KEY] = [
        dict(id="drift_X", junction="j_ab", law=CHARGED, species="X", permeability_m_per_s=P_X)
    ]
    return raw


def start_of(raw):
    """(spec, model, state, layout, control, node potentials) at a world's start, host side."""
    spec = parse_spec(copy.deepcopy(raw))
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    control = model.Control(*(v[0] for v in control_values(spec, [0.0])))
    structure = surface_pump_v3.structure(spec.model)
    values = surface_pump_v3.readouts(state, control, p, xp=np, structure=structure)
    return spec, model, state, p, control, np.asarray(values.field.potential_V)


def closed_slopes(spec, p, potentials, k=0):
    """Route k's carried row s, its ends (i inside, o outside), x = z F (phi_i - phi_o)/RT and its
    inward rate constants k_in = A P B(-x)/V_i and k_out = A P B(x)/V_o (1/s), written from the
    constant-field law at an opening of 1: dn_i/dt = k_out n_o - k_in n_i."""
    s = int(np.flatnonzero(p.passive_permeability[:, k])[0])
    z = float(np.asarray(p.valence).reshape(-1)[s])
    i, o = int(p.passive_inside[k]), int(p.passive_outside[k])
    volume, _ = passive_routes._volumes(p, np)
    x = z * F * (potentials[i] - potentials[o]) / (R * spec.model.temperature_K)
    rate = float(p.passive_area[k] * p.passive_permeability[s, k]) * 1e15  # pL/s.
    k_in = rate * float(bernoulli(-x, xp=np)) / volume[i]
    return s, i, o, z, x, k_in, rate * float(bernoulli(x, xp=np)) / volume[o]


def host_worlds():
    """The charged law on each host kind: the junction pair at +-25 mV, and the closed pair's
    contact patch (on its finite node ecs_0) and its wall patch (on the held bath) at the pair's
    held voltage, X at 2e-9 mM in cell_0 against the trace elsewhere."""
    wall = charged_pair(voltage_fmol=-5.18e-5, pool_mM=2e-9)
    wall["model"][passive_routes.MODEL_KEY][0]["patch"] = "wall_cell_0"
    return {
        "junction": junction_pair(voltage_fmol=VOLT),
        "finite patch": charged_pair(voltage_fmol=-5.18e-5, pool_mM=2e-9),
        "held patch": wall,
    }


@pytest.mark.parametrize("host", ("junction", "finite patch", "held patch"))
def test_the_charged_laws_rate_and_step_terms_on_each_host_are_their_closed_forms(
    host, monkeypatch
):
    """D310, host side at the start (no step), each value against the constant-field law written
    out (closed_slopes): the route's rate at its inside end is k_out n_out - k_in n_in; its
    material term is the two ends' sum k_in + k_out at each end where both relax (the junction's
    two cells, the contact patch's cell and finite node) and the cell's own k_in facing the held
    bath; its stage term is G = F^2/RT z^2 P A max(c) at a patch's two ends and 2G at each of a
    junction's cells. On the junction, each convention planted on the law's kernel fails the
    rate: the valence's sign, the voltage's orientation and the two ends' concentrations swapped.
    Parses only: under 1 s each on the timed lane."""
    raw = host_worlds()[host]
    spec, _, state, p, control, phi = start_of(raw)
    s, i, o, z, x, k_in, k_out = closed_slopes(spec, p, phi)
    amounts = passive_routes._amounts(state, p, np)
    expected = k_out * amounts[s, o] - k_in * amounts[s, i]

    def inside_rate():
        rates = passive_routes.rates(state, phi, control, p, xp=np)
        return float(np.concatenate((rates.cell, rates.outside), axis=1)[s, i])

    assert inside_rate() == pytest.approx(expected, rel=1e-12) and expected != 0
    material = np.asarray(passive_routes.material_term(state, phi, control, p, xp=np))
    if host == "held patch":  # The bath's row is held: the cell's own slope (P2's term).
        assert material[i] == pytest.approx(k_in, rel=1e-12)
    else:
        assert material[i] == pytest.approx(k_in + k_out, rel=1e-12)
        assert material[o] == pytest.approx(k_in + k_out, rel=1e-12)
    volume, _ = passive_routes._volumes(p, np)
    c = amounts[s] / volume
    conductance = (
        F * F / (R * spec.model.temperature_K) * z * z * float(p.passive_permeability[s, 0])
        * float(p.passive_area[0]) * max(c[i], c[o])
    )  # fmt: skip
    stage = np.asarray(passive_routes.stage_term(state, phi, control, p, xp=np))
    hosted = 2.0 if host == "junction" else 1.0  # D310: @3's own junction form.
    assert stage[i] == pytest.approx(hosted * conductance, rel=1e-12)
    assert stage[o] == pytest.approx(hosted * conductance, rel=1e-12)
    if host != "junction":
        return
    assert abs(x) > 1.8  # The held 50 mV gives the sign plants their power.
    kernel = passive_routes.charged_law.flux_fmol_s
    plants = {
        "valence": lambda ci, co, v, zz, *a, **k: kernel(ci, co, v, -zz, *a, **k),
        "orientation": lambda ci, co, v, zz, *a, **k: kernel(ci, co, -v, zz, *a, **k),
        "ends": lambda ci, co, v, zz, *a, **k: kernel(co, ci, v, zz, *a, **k),
    }
    for name, planted in plants.items():
        monkeypatch.setattr(passive_routes.charged_law, "flux_fmol_s", planted)
        assert inside_rate() != pytest.approx(expected, rel=1e-3), name
    monkeypatch.undo()
    assert inside_rate() == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize("term", ("charge", "material"))
def test_a_junction_route_refuses_the_step_its_term_bounds_and_a_planted_half_admits_it(term):
    """D310's two junction terms, one host step each (NumPy, no compile). At dt = 1.5 / the
    honest rate the step is refused: membrane_rate's charge rule over the 2G term, with X at 2 and
    1 uM (its charge mode is the fastest), and material_rate's rule over the two-end sum, at
    V = 0. With the term planted at half (G at each cell; each end's own slope, half the sum
    between equal cells at V = 0) the same step is admitted. 0.1 s each on the timed lane."""
    if term == "charge":
        raw = junction_pair(a_mM=2e-3, b_mM=1e-3, voltage_fmol=VOLT)
    else:
        raw = junction_pair()
    spec, model, state, p, control, phi = start_of(raw)
    structure = surface_pump_v3.structure(spec.model)
    if term == "charge":
        rate = surface_pump_v3.membrane_rate(
            state, control, p, xp=np, structure=structure, potentials=phi
        )
        other = surface_pump_v3.material_rate(
            state, control, p, xp=np, structure=structure, potentials=phi
        )
    else:
        rate = surface_pump_v3.material_rate(
            state, control, p, xp=np, structure=structure, potentials=phi
        )
        other = surface_pump_v3.membrane_rate(
            state, control, p, xp=np, structure=structure, potentials=phi
        )
    dt = 1.5 / float(rate)
    assert dt * float(other) < 0.75  # Only the term under test binds.
    assert not bool(model.imex_step(state, dt, control, p, xp=np)[1])
    hook = "stage_term" if term == "charge" else "material_term"
    honest = getattr(passive_routes.PASSIVE_ROUTES, hook)
    half = dataclasses.replace(
        passive_routes.PASSIVE_ROUTES, **{hook: lambda *a, **k: 0.5 * honest(*a, **k)}
    )
    kinds = kind_registry.KindRegistry()
    kinds.register(half)
    with kind_registry.scope(kinds):
        spec, model, state, p, control, _ = start_of(raw)
        assert bool(model.imex_step(state, dt, control, p, xp=np)[1])


def own_charge_root(n_a, n_b, phi_a, phi_b, capacitance, temperature):
    """The amount d (fmol) of the anion X (z = -1) moved from cell_a to cell_b at equilibrium,
    when each cell's potential moves with its own charge, phi_a = phi_a0 - z F d / C and
    phi_b = phi_b0 + z F d / C: the root of ln((n_a - d)/(n_b + d)) = -z F (phi_a - phi_b)/RT, by
    bisection (the residual falls monotonically in d)."""
    z, q = -1.0, F * 1e-15  # C per fmol.

    def residual(d):
        drop = (phi_a - z * q * d / capacitance) - (phi_b + z * q * d / capacitance)
        return np.log((n_a - d) / (n_b + d)) + z * F * drop / (R * temperature)

    low, high = -n_b * (1 - 1e-15), n_a * (1 - 1e-15)
    for _ in range(200):
        middle = 0.5 * (low + high)
        low, high = (middle, high) if residual(middle) > 0 else (low, middle)
    return 0.5 * (low + high)


@pytest.mark.parametrize("row", ("trace", "own charge"))
def test_a_charged_row_drifts_across_a_junction_to_its_closed_form(row):
    """D310's checks 1 and 2, the junction pair held at +-25 mV (x = z F (phi_a - phi_b)/RT, about
    -1.87):
    - trace (X at 1e-9 and 5e-10 mM): its charge moves the voltages by under 10 uV, so
      dn_a/dt = k_b n_b - k_a n_a at the held voltage, an exponential to the Nernst ratio
      c_a/c_b = e^-x; the end state is within 5e-4 of that closed form;
    - own charge (X at 2 and 1 uM): X's transfer builds the junction voltage, so the end state is
      the root of own_charge_root, an independent bisection, within 1e-6. The closure-blind
      references, equal concentrations and the held voltage's Nernst ratio, lie far outside it.
    Material is conserved, the heat is > 0 and every ledger passes: with no ion moving, the energy
    check reads this route alone (the species-only guard). Both ends start resolved: from a trace
    end the tableau's heat samples the log-singular start and books at first order (measured at
    2 uM against 1e-9 mM: 2.0% of the route's heat at this dt and 0.86% at half of it, refused),
    as the reactions operator's known limit (its §3.3 (a)); from 1 uM, 7.2e-5 and 1.8e-5, second
    order. Both rows share one compile (only data differ); dt = 25 us keeps dt x rate at most
    about 0.02 (FR-18's step advice). On the timed lane, 23 s with the compile and then 3 s."""
    if row == "trace":
        raw = junction_pair(voltage_fmol=VOLT)
    else:
        raw = junction_pair(a_mM=2e-3, b_mM=1e-3, voltage_fmol=VOLT)
    spec, _, _, p, _, phi = start_of(raw)
    s, i, o, _, x, k_a, k_b = closed_slopes(spec, p, phi)
    result = run(parse_spec(copy.deepcopy(raw)))
    final = result.final.state
    n_a0, n_b0 = float(p.amount_reference[s, 0]), float(p.amount_reference[s, 1])
    n_a = n_a0 + float(final.amount_increment[s, 0])
    n_b = n_b0 + float(final.amount_increment[s, 1])
    assert n_a + n_b == pytest.approx(n_a0 + n_b0, rel=1e-12, abs=0)
    assert float(final.passive_dissipated_energy_pJ[0]) > 0
    end = spec.experiment.end_time
    walls = np.asarray(result.observations.membrane_voltage_V)
    if row == "trace":
        assert np.max(np.ptp(walls, axis=0)) < 1e-5
        lam = k_a + k_b
        expected = n_a0 * np.exp(-lam * end) + k_b * (n_a0 + n_b0) / lam * -np.expm1(-lam * end)
        assert n_a == pytest.approx(expected, rel=5e-4)
        return
    moved = own_charge_root(n_a0, n_b0, phi[i], phi[o], fx.WALL_C_F, spec.model.temperature_K)
    assert n_a == pytest.approx(n_a0 - moved, rel=1e-6)
    nernst = (n_a0 + n_b0) / (1.0 + np.exp(x))  # c_a/c_b = e^-x at the held voltage.
    for blind in (0.5 * (n_a0 + n_b0), nernst):
        assert abs(n_a / blind - 1) > 1e-2


def test_a_reacting_charged_trace_row_on_a_junction_reaches_its_linear_steady_state():
    """D310's check 3, the microRNA's shape: a composite with cells.operator.local_species_reactions@1 on the
    junction pair, a source 0 -> X + K in cell_a (zeroth order, K the declared counter-ion), a
    first-order conversion X -> D in both cells (D an impermeant charged product sharing X's
    moiety N), the charged law carrying X on j_ab and K on @3's own junction route. K shorts the
    junction voltage, so this is a check of the composition, not of drift (checks 1 and 2 are):
    at V = 0 the steady state is n_a = k0 V (k + g)/(k (k + 2g)), n_b = g n_a/(k + g), with
    g = A P/V, and every ledger passes (its flows sit under the energy check's 2e-8 pJ floor, so
    the energy guard is the own-charge row's, not this one's). Measured at this dt, 2.4e-4 and
    2.8e-4 from it: the operator's Strang split moves the scheme's fixed point by O(dt^2) (7.8e-5
    and 9.4e-5 at half the dt), beside the 2 uV junction voltage that K's counter-current needs;
    5e-4 holds. One composite compile: 31 s on the timed lane."""
    k0, k_dec, end, dt = 1e-6, 10.0, 1.5, 1e-3
    raw = junction_pair(a_mM=1e-9, b_mM=1e-9, end=end, dt=dt, composite=True)
    raw = add_inventory_species(
        raw, "D", trace_mM=fx.TRACE_mM, diffusivity_m2_per_s=fx.D_S, floor_fmol=fx.FLOOR_FMOL
    )
    m = raw["model"]
    next(s for s in m["species"] if s["id"] == "D")["valence"] = -1
    for node in (*m["cells"], *m["extracellular"]):
        node["fixed_charge_equivalent_fmol"] += node["initial_amount_fmol"]["D"]
    m["junctions"][0]["permeability_m_per_s"]["K"] = 1.4e-7  # @3's 2G/C near 50/s at 5 mM.
    raw["execution"]["max_steps"] = int(round(end / dt)) + 8
    species = [
        rfx.species("X", moieties={"N": 1}),
        rfx.species("D", moieties={"N": 1}),
        dict(rfx.species("K"), counter_ion=True),
    ]
    reactions = [
        rfx.mass_action("make", {"cells": ["cell_a"]}, {}, {"X": 1, "K": 1}, k0),
        rfx.mass_action("decay", {"cells": "all"}, {"X": 1}, {"D": 1}, k_dec),
    ]
    controls = [("make", None, [(0.0, 1.0)]), ("decay", None, [(0.0, 1.0)])]
    spec = parse_spec(rfx.with_reactions(raw, species, reactions, controls))
    result = run(spec)
    _, p = get_model(spec.model).initial_values(spec)
    x = list(spec.model.species_ids).index("X")
    final = result.final.state
    n_a = float(p.amount_reference[x, 0] + final.amount_increment[x, 0])
    n_b = float(p.amount_reference[x, 1] + final.amount_increment[x, 1])
    g = fx.JUNCTION_AREA_M2 * P_X * 1e15  # 1/s between 1 pL cells at V = 0.
    steady_a = k0 * (k_dec + g) / (k_dec * (k_dec + 2 * g))  # fmol, V = 1 pL.
    assert n_a == pytest.approx(steady_a, rel=5e-4)
    assert n_b == pytest.approx(g * steady_a / (k_dec + g), rel=5e-4)


def neutral_row_on_the_junction():
    """The junction pair with the charged law carrying the neutral S."""
    raw = junction_pair()
    raw["model"][passive_routes.MODEL_KEY][0]["species"] = fx.SPECIES
    return raw


def crossing_beside_reactions():
    """The crossing junction pair as a composite with cells.operator.local_species_reactions@1 making X and K in
    cell_a: the microRNA's shape, where D310's refusal must hold as it does in plain @3."""
    raw = junction_pair(crossing=True, composite=True)
    species = [rfx.species("X", moieties={"N": 1}), dict(rfx.species("K"), counter_ion=True)]
    reactions = [rfx.mass_action("make", {"cells": ["cell_a"]}, {}, {"X": 1, "K": 1}, 1e-6)]
    return rfx.with_reactions(raw, species, reactions, [("make", None, [(0.0, 1.0)])])


@pytest.mark.parametrize(
    "build, message",
    [
        (neutral_row_on_the_junction, "carries a charged row, not the neutral S"),
        (crossing_beside_reactions,
         "on junction j_ab, which joins two capacitor components where one floats"),
    ],
    ids=["neutral row", "crossing junction in a composite"],
)  # fmt: skip
def test_the_charged_law_on_a_junction_refuses_a_neutral_row_and_a_crossing_composite(
    build, message
):
    """Host side: on a junction as on a patch, the charged law carries a charged row only; and the
    crossing junction's refusal (D310) holds in a composite beside cells.operator.local_species_reactions@1, as
    in plain @3 (the kind file's row): the kinds' definition checks run on the composite's path
    too (measured before this row: refused, and the same world without the crossing admitted)."""
    with pytest.raises(ConfigError, match=re.escape(message)):
        parse_spec(build())
