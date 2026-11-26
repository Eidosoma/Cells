"""The one-cell store world against its code-blind references
(docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md, section 14, row 12). The world is
validation/calcium_store/worlds.py's store_world, of the registered laws, with the numbers of
validation/calcium_store/reference_spec. The references (validation/calcium_store/references)
were written from that folder alone, by someone who had read nothing of the engine, so a row here
reads their numbers (values.json) and runs no integrator.

The engine's steps are the composite's, in NumPy (host_step; row 13 holds them to the compiled
ones), so nothing compiles: 0.2, 0.1 and 0.05 ms to 8 ms, recorded at 2, 4, 6 and 8 ms; without
the buffers, 0.2 and 0.1 ms to 4 ms. The observables are each node's amounts, V_m, V_b, both
gates, each mover's transfer, heat and work, each reaction's extent, and the capacitor energy. An
observable's error at a step is its largest over the recorded times. Every ledger closes at each
of them.

- Band: at the finest step, the error is within 1.5 times the engine's own estimate (a third of
  the change from the step before, the rest of a second-order error) plus BAND_FLOOR of the
  observable's largest change. The estimate is the engine's alone, so no reference enters the
  band it is judged by. The references are within 5e-14 of that change (their README), far below
  both floors.
- Order: the error falls by 2^1.8 to 2^2.2 per halving, wherever it stays above ORDER_FLOOR of
  that change. Below it an observable whose leading error cancels, as the store's free buffer's
  does, need not show an order.
- Power: the references of a world with one thing changed (the release's sign; the pumps without
  their voltage; each constant 1% larger) each miss the band.
- The rates and heats at the start are the references' to rounding, with no step at all.
- The stage's material rate holds the references' material block: at both ends of the run it is
  at least the largest eigenvalue's modulus, and at least that with the release's opening held,
  and at most twice that.
- At equilibrium the world does not move at all: its patches, leaks, release, channel and exchanger
  carry exactly zero, and its pumps, at their stall, turn no cycle (planted, each moves it: 1e-15 RT
  of the fuel's drive, one rounding of the store's calcium, 1e-15 V on the store's patch). This one
  reads no reference.
- What is closed carries nothing: with every control at 0 only the gates move (in the two-cell
  world, the faces too), and a channel of abundance 0 conducts nothing (planted, each moves it: a
  closed patch's or junction's routes passing 1e-9 of themselves, or a hundredth of their flux).

Seconds: 20 on the shared CPUs, 18 of them 340 NumPy steps on one CPU (9 s where the CPU is
quiet), so tier 1. The reason (D224): no other row holds a store world, its order and its heats
to numbers that the engine's authors did not write.
"""

import math

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.models import surface_pump_v3
from tests.calcium_store_fixtures import bound, host_step
from validation.calcium_store import worlds
from validation.calcium_store.references import api

WORLD = worlds.specification()["store_world"]
TIMES = tuple(WORLD["times_s"][1:])
STEPS = dict(store_world=(2e-4, 1e-4, 5e-5), store_world_without_buffers=(2e-4, 1e-4))
ROWS = dict(store_world=4, store_world_without_buffers=2)  # How many of TIMES a run goes to.
CONTROLS = ["release_sign", "pump_without_voltage"] + [
    f"constants_one_percent: {name}" for name in WORLD["controls"]["list"][2]["constants"]
]
PASSIVE, CYCLES = "cells.kind.passive_routes@1", "cells.kind.transporter@1"
CONDITIONS = "cells.kind.species_condition@1"
# The references' names: {observable: their key}, {mover: theirs}, and a mover's one label.
SERIES = dict(
    V_m="V_m_change_V", V_b="V_b_change_V", m="m", h="h", capacitor="capacitor_energy_change_pJ"
)
MOVERS = dict(plasma="plasma_permeability", bounding="bounding_permeability") | {
    name: name
    for name in (*WORLD["calcium_routes"], "calcium_channel", *WORLD["pumps"], "exchanger")
}
LABELS = dict.fromkeys((*WORLD["pumps"], "exchanger"), "cycles")
GATES = ("m", "h")
REACTIONS = [r["id"] for r in WORLD["buffers"]["reactions"]]
SITES = WORLD["buffers"]["sites"]
R = 6.02214076e23 * 1.380649e-23
BAND_FLOOR, ORDER_FLOOR = 1e-8, 1e-7  # Of an observable's largest change.
ORDER = (1.8, 2.2)
START_BAND = 1e-12


# ------------------------------------------------------------------ the engine's runs


class Names:
    """Where a definition's entities sit in the state's rows, in the engine's own orders."""

    def __init__(self, spec):
        kinds = dict(spec.model.kinds)
        self.species = list(spec.model.species_ids)
        self.nodes = {x.id.removesuffix("_0"): i for i, x in enumerate(spec.model.extracellular)}
        self.routes = [r.id.removesuffix("_0") for r in kinds[PASSIVE]]
        self.populations = [t.id.removesuffix("_0") for t in kinds[CYCLES]]
        self.conditions = [c.id.removesuffix("_0") for c in kinds[CONDITIONS]]
        operators = [op for op in spec.model.operators if hasattr(op, "routes")]
        self.reactions = [
            (r.reaction, r.node.removesuffix("_0")) for op in operators for r in op.routes
        ]


def movers(names, values):
    """{observable: value} of a state's own accumulators, or of their rates (a derivative): a
    patch's own and a channel's transfer from the cell outward, a release's into the cell (the
    specification's signs), cycles forward."""
    ca = names.species.index("Ca")
    out = {}
    for i, (patch, data) in enumerate(WORLD["patches"].items()):
        for s in data["permeability_m_per_s"]:
            out[f"moved {patch} {s}"] = values.membrane_transferred[names.species.index(s), i]
        out[f"heat {patch}"] = values.membrane_dissipated_energy_pJ[i]
    for i, name in enumerate(names.routes):
        sign = 1.0 if name == "release" else -1.0
        out[f"moved {name}"] = sign * values.passive_transferred[ca, i]
        out[f"heat {name}"] = values.passive_dissipated_energy_pJ[i]
    out["moved calcium_channel"] = values.channel_transferred[ca, 0]
    out["heat calcium_channel"] = math.fsum(np.ravel(values.channel_dissipated_energy_pJ))
    for i, name in enumerate(names.populations):
        out[f"moved {name}"] = values.cycle_count[0, i]
        out[f"heat {name}"] = values.cycle_dissipated_energy_pJ[i]
        if name in WORLD["pumps"]:
            out[f"work {name}"] = values.cycle_metabolic_work_pJ[i]
    return out


def observables(spec, model, state, control, p):
    names = Names(spec)
    field = model.readouts(state, control, p, xp=np).field
    phi = np.asarray(field.potential_V)  # The cell, then the outside nodes.
    out = dict(
        V_m=phi[0] - phi[1 + names.nodes["outside"]],
        V_b=phi[0] - phi[1 + names.nodes["store"]],
        m=state.channel_gate[0, 0],
        h=state.channel_gate[1, 0],
        capacitor=field.capacitor_energy_pJ,
    )
    for node, data in WORLD["nodes"].items():
        outside = state.extracellular_amount_increment
        column = state.amount_increment[:, 0] if node == "cell" else outside[:, names.nodes[node]]
        for s in data["amounts_fmol"]:
            out[f"amount {node} {s}"] = column[names.species.index(s)]
    out |= movers(names, state)
    for i, (reaction, site) in enumerate(names.reactions):
        out[f"moved {reaction} {site}"] = state.reaction_extent_fmol[i]
    if names.reactions:
        out["heat buffers cell"] = state.reaction_dissipated_energy_pJ[0]
        out["heat buffers store"] = state.reaction_outside_dissipated_energy_pJ[
            names.nodes["store"]
        ]
    return {name: float(value) for name, value in out.items()}


class Run:
    """A run of one variant at one step: its observables at the first ROWS of TIMES, its start and
    its end. Every ledger that @3 and the operators check closes at each of those rows."""

    def __init__(self, variant, dt):
        buffers, end = variant == "store_world", round(TIMES[-1] / dt)
        self.spec = parse_spec(worlds.store_world(dt=dt, steps=end, buffers=buffers))
        self.model, self.start, self.control, self.p = bound(self.spec)
        state, states, every = self.start, [self.start], round(TIMES[0] / dt)
        steps = every * ROWS[variant]
        for k in range(1, steps + 1):
            state, valid = host_step(self.model, state, dt, self.control, self.p)
            assert valid, k
            if k % every == 0:
                states.append(state)
        history = type(state)(*(np.stack(x) for x in zip(*states, strict=True)))
        self.model.check_values(history, self.spec, steps=np.arange(0, steps + 1, every))
        self.end = state
        first, *rows = (self.at(s) for s in states)
        self.first = {name: value if name in GATES else 0.0 for name, value in first.items()}
        self.rows = {  # A gate as it is; every other observable as its change since the start.
            name: np.array([row[name] - value for row in rows]) + self.first[name]
            for name, value in first.items()
        }

    def at(self, state):
        return observables(self.spec, self.model, state, self.control, self.p)

    def start_rates(self):
        """The rates at the start, under the observables' names: the stage's own (readouts), and
        the columns of the operators and of the conditions (observe_history)."""
        state, names = self.start, Names(self.spec)
        values = self.model.readouts(state, self.control, self.p, xp=np)
        d, field = values.derivative, values.field
        out = movers(names, d)
        history = type(state)(*(np.stack([x]) for x in state))
        seen = self.model.observe_history(np.zeros(1), history, self.p, np.zeros(1), self.spec)
        rate, affinity = seen.reaction_rate_fmol_per_s[0], seen.reaction_affinity_RT[0]
        for i, (reaction, site) in enumerate(names.reactions):
            out[f"moved {reaction} {site}"] = rate[i]
            out[f"heat {reaction} {site}"] = (
                1e-3 * R * WORLD["temperature_K"] * rate[i] * affinity[i]
            )
        for i, name in enumerate(names.conditions):
            out[f"factor {name}"] = seen.species_condition_factor[0, i]
        for i, patch in enumerate(WORLD["patches"]):
            out[f"V {patch}"] = field.membrane_voltage_rate_V_s[i]
        target, tau = values.ionic.channel_targets[:, 0], values.ionic.channel_tau_s[:, 0]
        for i, gate in enumerate(GATES):
            out[gate] = (target[i] - state.channel_gate[i, 0]) / tau[i]
        return {name: float(value) for name, value in out.items()}

    def material_rate(self, state):
        """The stage's material rate (1/s) at a state, as the inner step reads it."""
        model, inner = self.model, self.model.inner
        potentials = model.readouts(state, self.control, self.p, xp=np).field.potential_V
        return float(
            surface_pump_v3.material_rate(
                inner.inner_state(state),
                model.control_view(self.control, state, self.p, xp=np),
                model.view(self.p, state, xp=np),
                xp=np,
                structure=inner.implementation.structure,
                potentials=np.asarray(potentials),
            )
        )


@pytest.fixture(scope="module")
def runs():
    return {v: [Run(v, dt) for dt in steps] for v, steps in STEPS.items()}


# ------------------------------------------------------------------ the references


def reference(variant, control=None):
    """{observable: its value at each of TIMES}, in the engine's parts: amounts, voltages and the
    capacitor energy as their changes since t = 0; a patch's heat over its species and a site's
    over its reactions, as the engine books them."""
    given = api.store_world(variant, control)
    series = {name: np.array(given[key][1:]) for name, key in SERIES.items()}
    for node, rows in given["amount_changes_fmol"].items():
        series |= {f"amount {node} {s}": np.array(x[1:]) for s, x in rows.items()}
    moved, heats = given["transfers_fmol"], given["heats_pJ"]
    for name, key in MOVERS.items():
        for label, x in moved[key].items():
            own = name if name == key else f"{name} {label}"
            series[f"moved {own}"] = np.array(x[1:])
        label = "total" if name != key else LABELS.get(name, "Ca")
        series[f"heat {name}"] = np.array(heats[key][label][1:])
    for name, x in given["works_pJ"].items():
        series[f"work {name}"] = np.array(x[1:])
    if variant == "store_world":
        for reaction in REACTIONS:
            for site in SITES:
                series[f"moved {reaction} {site}"] = np.array(moved[reaction][site][1:])
        for site in SITES:
            series[f"heat buffers {site}"] = sum(
                np.array(heats[reaction][site][1:]) for reaction in REACTIONS
            )
    return series


def start_rates(variant):
    """{observable: its rate at t = 0}, under Run.start_rates' names."""
    given = api.initial_rates(variant)
    rates, heats = given["rates_fmol_per_s"], given["heat_rates_pJ_per_s"]
    out = dict(m=given["dm_dt_per_s"], h=given["dh_dt_per_s"])
    out |= {"V plasma": given["dV_m_dt_V_per_s"], "V bounding": given["dV_b_dt_V_per_s"]}
    for name, key in MOVERS.items():
        for label, x in rates[key].items():
            out[f"moved {name if name == key else f'{name} {label}'}"] = x
        out[f"heat {name}"] = heats[key]["total" if name != key else LABELS.get(name, "Ca")]
    out |= {f"work {name}": x for name, x in given["work_rates_pJ_per_s"].items()}
    out |= {f"factor {name}": x for name, x in given["condition_factors"].items()}
    for reaction in REACTIONS:
        for site in SITES:
            out[f"moved {reaction} {site}"] = rates[reaction][site]
            out[f"heat {reaction} {site}"] = heats[reaction][site]
    return out


def blocks(variant):
    """[(the material block's largest modulus, with the release's opening held)] at both ends."""
    out = []
    for time in (0.0, TIMES[-1]):
        block = api.material_block(variant, time)
        names = ("release_opening_moving", "release_opening_held")
        out.append(tuple(block[name]["largest_modulus_per_s"] for name in names))
    return out


def change(run, truth, name):
    """An observable's largest change over the references' run."""
    return float(np.max(np.abs(truth[name] - run.first[name])))


def error(run, truth, name):
    series = run.rows[name]
    return float(np.max(np.abs(series - truth[name][: len(series)])))


def misses(pair, truth):
    """{observable: its error over the band} of those outside it, the last of the two runs judged by
    its change from the first."""
    coarse, fine = pair
    out = {}
    for name, series in fine.rows.items():
        estimate = float(np.max(np.abs(series - coarse.rows[name]))) / 3
        band = 1.5 * estimate + BAND_FLOOR * change(fine, truth, name)
        if not (found := error(fine, truth, name)) <= band:
            out[name] = found / band if band else math.inf
    return out


@pytest.mark.parametrize("variant", STEPS)
def test_the_store_world_meets_its_references_at_second_order(runs, variant):
    truth, series = reference(variant), runs[variant]
    assert set(truth) == set(series[0].rows)  # Every observable, and no other.
    assert misses(series[-2:], truth) == {}
    judged, out = 0, {}
    for name in truth:
        errors = [error(run, truth, name) for run in series]
        floor = ORDER_FLOOR * change(series[0], truth, name)
        for coarse, fine in zip(errors, errors[1:], strict=False):
            if fine >= floor > 0:
                judged += 1
                if not ORDER[0] <= math.log2(coarse / fine) <= ORDER[1]:
                    out[name] = errors
    assert out == {}
    assert judged >= 25 * (len(series) - 1)  # The order is judged on half of them, at least.


@pytest.mark.parametrize("control", CONTROLS)
def test_a_world_with_one_thing_changed_misses_the_band(runs, control):
    assert misses(runs["store_world"][-2:], reference("store_world", control))


def test_the_rates_at_the_start_are_the_references(runs):
    """Before any step: each mover's rate and heat rate, each reaction's, both factors, and the
    voltages' rates."""
    run = runs["store_world"][0]
    truth, found = start_rates("store_world"), run.start_rates()
    assert set(truth) == set(found)
    out = {}
    for name, value in truth.items():
        if not abs(found[name] - value) <= START_BAND * abs(value):
            out[name] = (found[name], value)
    assert out == {}


def moved_in_two_steps(raw, *, off=False):
    """(the fields that two steps move, the state after them), `off` with every control at 0."""
    spec = parse_spec(raw)
    model, start, control, p = bound(spec)
    if off:
        shut = {n: np.zeros_like(v) for n, v in control._asdict().items()}
        control = type(control)(**(shut | dict(passive_multiplier=control.passive_multiplier)))
    state = start
    for _ in range(2):
        state, valid = host_step(model, state, raw["execution"]["dt"], control, p)
        assert valid
    pairs = zip(start._fields, start, state, strict=True)
    return {name for name, a, b in pairs if not np.array_equal(a, b)}, state


def at_equilibrium(*, fuel=0.0, calcium=None, volts=0.0):
    """The fields that two steps move, of the world without buffers at equilibrium: every node has
    the cell's volume and its ions, no patch has a voltage, and the fuel has no drive. Each option
    plants a departure: the potential of ADP (RT), the store's calcium (fmol), its patch's volts."""
    data = worlds.store_data()
    nodes, cell = data["nodes"], data["nodes"]["cell"]
    cell["amounts_fmol"].update(dict.fromkeys(("ATP", "ADP", "Pi"), cell["volume_pL"]))  # 1 mM.
    data["fuel_potentials_RT"] = dict(ATP=0.0, ADP=fuel, Pi=0.0)
    for name in ("store", "outside"):  # One volume, so that equal amounts are equal to the bit.
        nodes[name]["volume_pL"] = cell["volume_pL"]
        nodes[name]["amounts_fmol"].update({s: cell["amounts_fmol"][s] for s in worlds.IONS})
    if calcium is not None:
        nodes["store"]["amounts_fmol"]["Ca"] = calcium
    for name, patch in data["patches"].items():
        patch["initial_voltage_V"] = volts if name == "bounding" else 0.0
    dt = STEPS["store_world"][0]
    return moved_in_two_steps(worlds.store_world(dt=dt, steps=2, buffers=False, data=data))[0]


def test_a_world_at_equilibrium_does_not_move_at_all():
    assert at_equilibrium() == {"channel_gate"}  # The gates relax, and nothing else moves.
    calcium = WORLD["nodes"]["cell"]["amounts_fmol"]["Ca"]
    assert "cycle_count" in at_equilibrium(fuel=1e-15)
    moved = at_equilibrium(calcium=math.nextafter(calcium, math.inf))
    assert {"passive_transferred", "cycle_count"} <= moved
    moved = at_equilibrium(volts=1e-15)
    every = {"membrane_transferred", "passive_transferred", "channel_transferred", "cycle_count"}
    assert every <= moved


def test_what_is_closed_carries_nothing():
    """With every control at 0 (the passive multiplier apart) a closed patch, a closed junction and
    a closed channel carry nothing: in two host steps only the gates move, and the faces' ions in
    the two-cell world. A channel of abundance 0 conducts nothing, and its step is valid.
    Seconds: 0.7 to 1.3 (measured), host steps and no compile. The reason (D224): no other row
    holds that a closed route passes no flux (the fresh reader of the retiring rows, 25 November
    2026)."""
    store, gates = worlds.store_world(dt=STEPS["store_world"][0], steps=2), {"channel_gate"}
    assert moved_in_two_steps(store, off=True)[0] == gates
    faces = {"extracellular_amount_increment", "face_transferred", "face_dissipated_energy_pJ"}
    two = worlds.two_cells(dt=1.25e-5, steps=5)
    assert moved_in_two_steps(two, off=True)[0] == gates | faces | {"junction_gate"}
    store["model"]["channels"][0]["abundance"] = 0.0
    end = moved_in_two_steps(store)[1]  # Its steps are valid (asserted there).
    assert not np.any(end.channel_transferred) and not np.any(end.channel_dissipated_energy_pJ)


def test_the_stages_material_rate_holds_the_references_block(runs):
    run = runs["store_world"][-1]
    for state, (largest, held_open) in zip(
        (run.start, run.end), blocks("store_world"), strict=True
    ):
        rate = run.material_rate(state)
        assert largest <= rate and held_open <= rate <= 2 * held_open
