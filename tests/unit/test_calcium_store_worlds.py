"""The one-cell store world against its code-blind references
(docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md, section 14, row 12). The world is
validation/calcium_store/worlds.py's store_world, of the registered laws, with the numbers of
validation/calcium_store/reference_spec. The references (validation/calcium_store/references)
were written from that folder alone, by someone who had read nothing of the engine, so a row here
reads their numbers (values.json) and runs no integrator.

The engine's steps are the composite's own, in NumPy (host_step), so nothing compiles: 0.2, 0.1
and 0.05 ms to 8 ms, recorded at 2, 4, 6 and 8 ms; without the buffers, 0.2 and 0.1 ms to 4 ms.
The observables are each node's amounts, V_m, V_b, both gates, each mover's transfer, heat and
work, each reaction's extent, and the capacitor energy. An observable's error at a step is its
largest over the recorded times. Every ledger closes at each of them.

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

Seconds: 15, in NumPy on one CPU, so tier 1.
"""

import math

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.schedule import control_values
from cells.models import surface_pump_v3
from cells.registry.models import get_model
from validation.calcium_store import worlds
from validation.calcium_store.references import api

WORLD = worlds.specification()["store_world"]
TIMES = tuple(WORLD["times_s"][1:])
STEPS = dict(store_world=(2e-4, 1e-4, 5e-5), store_world_without_buffers=(2e-4, 1e-4))
ROWS = dict(store_world=4, store_world_without_buffers=2)  # How many of TIMES a run goes to.
CONTROLS = ["release_sign", "pump_without_voltage"] + [
    f"constants_one_percent: {name}" for name in WORLD["controls"]["list"][2]["constants"]
]
PASSIVE, CYCLES = "cells.passive_routes@1", "cells.transporter@1"
CONDITIONS = "cells.species_condition@1"
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


def bound(variant, dt):
    """(spec, model, state, control, layout) of the world at step dt."""
    raw = worlds.store_world(dt=dt, steps=round(TIMES[-1] / dt), buffers=variant == "store_world")
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    return spec, model, state, type(controls)(*(np.asarray(v[0]) for v in controls)), p


def host_step(model, state, dt, control, p):
    """One composite step in NumPy, as split_step takes it: each operator's half-step, the inner
    model's IMEX step at the view, the half-steps in reverse."""
    valid = True
    for op in model.splits:
        state, ok = model._half_step(op, state, 0.5 * dt, control, p, xp=np)
        valid &= bool(ok)
    moved, ok = model.inner.imex_step(
        model.inner.inner_state(state),
        dt,
        model.control_view(control, state, p, xp=np),
        model.view(p, state, xp=np),
        xp=np,
    )
    valid &= bool(ok)
    state = state._replace(**moved._asdict())
    for op in reversed(model.splits):
        state, ok = model._half_step(op, state, 0.5 * dt, control, p, xp=np)
        valid &= bool(ok)
    return state, valid


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
        self.spec, self.model, self.start, self.control, self.p = bound(variant, dt)
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


def test_the_stages_material_rate_holds_the_references_block(runs):
    run = runs["store_world"][-1]
    for state, (largest, held_open) in zip(
        (run.start, run.end), blocks("store_world"), strict=True
    ):
        rate = run.material_rate(state)
        assert largest <= rate and held_open <= rate <= 2 * held_open
