"""Compiled face-free runs of local_species_reactions@1 against the independent references
(validation/reactions, used through REFERENCES_USAGE.md only; D152 v1, milestone 2; §3.4 guards 1,
4 and 5).

* **The implementation** (the guard): whole compiled runs in the face-free world, where @3 moves no
  network row so each step is two operator half-steps, against nr.run_half_steps from the raw
  declaration (amounts, volumes, parameters, the engine's R and T): the amounts, extents, heat,
  work and standard term at every row, to rounding accumulated over the run (1e-10 of their
  scales). On probe 2d's share onsets (traces 1e-12, 1e-9, 1e-6 mM), probe 2e's crossings, the
  class switch (callable multipliers) and the reversal onset at the first step and at a mid-run
  switch-on; and a passive relaxation, whose end state and total heat are
  dr.passive_equilibrium's.
* **The scheme's accuracy**, set beside the note's figures (recorded; the pins in §11.1 are
  proposals, not tuned): the share onset's first half-step and whole heat and work at 5 s against
  dr.integrate_node (probe 2d's grid: h = 0.05, 0.025, 0.0125 s); the background guard (the whole
  heat's relative change for a thousandfold trace, the engine's against the true heat's); the
  crossing step's heat (probe 2e); the reversal onset's first half-step against its true heat
  (probe 2g's per-step factors).
Measured values go to species_reactions_reference_runs.jsonl in the tier runner's
CELLS_OUTPUT_ROOT. A few minutes of compiles and integrations: tier 3.
"""

import json
import os
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models.operators import species_reactions as sr
from cells.models.registry import get_model
from cells.processes.electrochemistry import R
from validation.reactions import dissipation_reference as dr
from validation.reactions import network_reference as nr
from validation.tissue import species_reactions_fixtures as rfx

jax.config.update("jax_enable_x64", True)
REL = 1e-10  # Rounding accumulated over runs of up to 400 half-steps.
EPS = np.finfo(float).eps


def record(test, **values):
    root = os.environ.get("CELLS_OUTPUT_ROOT")
    if root:
        path = Path(root) / "species_reactions_reference_runs.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as out:
            out.write(json.dumps(dict(test=test, **values), default=float) + "\n")


def rt(raw):
    return nr.rt_pJ_per_fmol(R, raw["model"]["temperature_K"])


def engine_rows(result):
    """The engine's network amounts [T, S, N] and node fields [T, N] on the combined node axis
    (cells, then outside nodes), and its route extents [T, routes]."""
    model = get_model(result.spec.model)
    _, p = model.initial_values(result.spec)
    h = result.history
    increment = np.concatenate(
        (np.asarray(h.amount_increment), np.asarray(h.extracellular_amount_increment)), axis=2
    )
    anchor = np.concatenate(
        (np.asarray(p.amount_reference), np.asarray(p.extracellular_amount_reference)), axis=1
    )
    rows = np.asarray(p.reaction_rows)

    def nodes(cell, outside):
        return np.concatenate(
            (np.asarray(getattr(h, cell)), np.asarray(getattr(h, outside))), axis=1
        )

    return dict(
        amounts=anchor[rows][None] + increment[:, rows],
        heat=nodes("reaction_dissipated_energy_pJ", "reaction_outside_dissipated_energy_pJ"),
        work=nodes("reaction_work_pJ", "reaction_outside_work_pJ"),
        standard=nodes("reaction_standard_energy_pJ", "reaction_outside_standard_energy_pJ"),
        magnitude=nodes("reaction_energy_magnitude_pJ", "reaction_outside_energy_magnitude_pJ"),
        extents=np.asarray(h.reaction_extent_fmol),
    )


def against_reference(raw, multipliers, label):
    """A compiled run against nr.run_half_steps at every accepted row (module docstring)."""
    result = run(parse_spec(raw))
    e = engine_rows(result)
    net, sites = rfx.reference_network(raw), rfx.reference_sites(raw)
    amounts, volumes = rfx.reference_amounts(raw)
    dt = raw["execution"]["dt"]
    count = 2 * int(round(float(result.times[-1]) / dt))
    ref = nr.run_half_steps(
        net, amounts, volumes, dt / 2, count, rt(raw), multipliers=multipliers, sites=sites
    )
    assert ref.refused_at is None, ref.refusal
    declaration = result.spec.model.operators[0]
    reactions = [r.id for r in declaration.reactions]
    nodes = [n["id"] for n in rfx.reference_nodes(raw)]
    routes = [(reactions.index(r.reaction), nodes.index(r.node)) for r in declaration.routes]
    active = sites.any(axis=0)
    worst = dict(amounts=0.0, energy=0.0, extents=0.0)
    for row, t in enumerate(np.asarray(result.times)):
        k = 2 * int(round(float(t) / dt))
        a, b = e["amounts"][row][:, active], ref.amounts[k][:, active]
        floor = 8 * EPS * amounts[:, active]  # The anchored representation's resolution.
        assert np.all(np.abs(a - b) <= REL * np.abs(b) + floor), (label, row)
        worst["amounts"] = max(worst["amounts"], float(np.max(np.abs(a - b) / np.abs(b))))
        scale = e["magnitude"][row][active] + 1e-300
        for name in ("heat", "work", "standard"):
            diff = np.abs(e[name][row][active] - getattr(ref, name)[k][active])
            assert np.all(diff <= REL * scale), (label, name, row, diff, scale)
            worst["energy"] = max(worst["energy"], float(np.max(diff / scale)))
        extents = np.zeros(ref.extents[k].shape)
        for (r, i), value in zip(routes, e["extents"][row], strict=True):
            extents[r, i] = value
        size = np.max(np.abs(ref.extents[: k + 1]), axis=0) + 1e-300
        assert np.all(np.abs(extents - ref.extents[k]) <= REL * size), (label, row)
        worst["extents"] = max(
            worst["extents"], float(np.max(np.abs(extents - ref.extents[k]) / size))
        )
    record("implementation", world=label, rows=len(result.times), half_steps=count, **worst)
    return result, ref


# ------------------------------------------------------------------ the implementation


@pytest.mark.parametrize("trace", [1e-12, 1e-9, 1e-6])
def test_the_share_onset_runs_as_the_reference(trace):
    against_reference(rfx.enzyme_recipe(trace, end=1.0, dt=0.025), None, f"share_{trace:g}")


@pytest.mark.parametrize(("sink", "dt", "offset"), [(1.0, 0.1, 0.01), (10.0, 0.05, 0.01)])
def test_the_crossing_runs_as_the_reference(sink, dt, offset):
    raw = rfx.crossing(end=10 * dt, dt=dt, sink=sink, offset=offset)
    against_reference(raw, None, f"crossing_{sink:g}")


def test_the_class_switch_runs_as_the_reference():
    raw = rfx.enzyme_recipe(
        None,
        resolved=True,
        catalysis=[(0.0, 1.0), (0.02, 0.0), (0.03, 1.0)],
        end=0.05,
        dt=1e-3,
        observation_times=[0.0, 0.02, 0.03, 0.05],
    )

    def multipliers(k):  # Half-step k covers [k h, (k + 1) h), h = 0.5 ms: off from 20 to 30 ms.
        return np.array([1.0, 0.0 if 40 <= k < 60 else 1.0])

    against_reference(raw, multipliers, "class_switch")


def test_the_reversal_onset_runs_as_the_reference_at_the_start_and_mid_run():
    against_reference(rfx.reversal_onset(1e-12, end=0.1, dt=0.025), None, "onset_start")

    def multipliers(k):  # Both routes off until 50 ms (half-step 4 at h = 12.5 ms).
        return np.full(2, 0.0 if k < 4 else 1.0)

    raw = rfx.reversal_onset(1e-12, end=0.15, dt=0.025, switch_on=0.05)
    against_reference(raw, multipliers, "onset_mid_run")


def test_a_passive_relaxation_ends_at_the_references_equilibrium():
    raw = rfx.passive_relaxation(end=40.0, dt=0.1)
    result, _ = against_reference(raw, None, "passive_relaxation")
    net = rfx.reference_network(raw)
    amounts, volumes = rfx.reference_amounts(raw)
    equilibrium = dr.passive_equilibrium(net, amounts[:, 0], volumes[0], rt(raw))
    e = engine_rows(result)
    end = e["amounts"][-1][:, 0]
    assert np.all(np.abs(end - equilibrium.amounts) <= 1e-12 * equilibrium.amounts)
    heat = e["heat"][-1][0]
    assert abs(heat - (-equilibrium.delta_G)) <= 1e-12 * abs(equilibrium.delta_G)
    record("passive_relaxation", heat_pJ=heat, equilibrium_drop_pJ=-equilibrium.delta_G)


# ------------------------------------------------------------------ the scheme's accuracy


def first_half_step(raw, h):
    """The engine's first half-step (its host form) and the true heat and work over [0, h]."""
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    routes = len(spec.model.operators[0].routes)
    terms = sr.half_step_terms(state, np.ones(routes), h, p, xp=np)
    net, sites = rfx.reference_network(raw), rfx.reference_sites(raw)
    amounts, volumes = rfx.reference_amounts(raw)
    true = dr.integrate_node(net, amounts, volumes, rt(raw), [0.0, h], sites=sites)
    return terms, true


def relative(booked, true):
    return (booked - true) / abs(true)


@pytest.mark.parametrize("trace", [1e-12, 1e-9, 1e-6])
def test_the_share_onsets_accuracy_beside_probe_2d(trace):
    """Probe 2d's grid: the first half-step and the whole heat and work at 5 s, against the exact
    node kinetics (the note's §3.3 table: the attribution column)."""
    out = {}
    for h in (0.05, 0.025, 0.0125):
        raw = rfx.enzyme_recipe(trace, end=5.0, dt=2 * h, observation_times=[0.0, 5.0])
        terms, true = first_half_step(raw, h)
        first_heat = relative(terms.heat[0], true.heat[-1][0])
        first_work = relative(terms.work[0], true.work[-1][0])
        result = run(parse_spec(raw))
        e = engine_rows(result)
        net, sites = rfx.reference_network(raw), rfx.reference_sites(raw)
        amounts, volumes = rfx.reference_amounts(raw)
        exact = dr.integrate_node(net, amounts, volumes, rt(raw), [0.0, 5.0], sites=sites)
        whole_heat = relative(e["heat"][-1][0], exact.heat[-1][0])
        whole_work = relative(e["work"][-1][0], exact.work[-1][0])
        out[h] = dict(
            first_heat=first_heat,
            first_work=first_work,
            heat_5s=whole_heat,
            work_5s=whole_work,
            true_heat_5s_pJ=exact.heat[-1][0],
            engine_heat_5s_pJ=e["heat"][-1][0],
        )
        assert abs(first_heat) < 1e-2 and abs(whole_heat) < 2e-3, (h, out[h])
    record("share_accuracy", trace=trace, by_half_step=out)


def test_the_background_guard_beside_probe_2d():
    """§3.4 guard 5: a thousandfold negligible trace (1e-12 -> 1e-9 mM) moves the engine's whole
    heat and work at 5 s (h = 0.025 s) as it moves the true heat and work."""
    values = {}
    for trace in (1e-12, 1e-9):
        raw = rfx.enzyme_recipe(trace, end=5.0, dt=0.05, observation_times=[0.0, 5.0])
        e = engine_rows(run(parse_spec(raw)))
        net, sites = rfx.reference_network(raw), rfx.reference_sites(raw)
        amounts, volumes = rfx.reference_amounts(raw)
        exact = dr.integrate_node(net, amounts, volumes, rt(raw), [0.0, 5.0], sites=sites)
        values[trace] = (e["heat"][-1][0], exact.heat[-1][0], e["work"][-1][0], exact.work[-1][0])
    (h12, t12, w12, tw12), (h9, t9, w9, tw9) = values[1e-12], values[1e-9]
    engine, true = (h9 - h12) / h12, (t9 - t12) / t12
    engine_w, true_w = (w9 - w12) / abs(w12), (tw9 - tw12) / abs(tw12)
    record(
        "background",
        engine_heat_change=engine,
        true_heat_change=true,
        engine_work_change=engine_w,
        true_work_change=true_w,
    )
    assert abs(engine - true) < 1e-5 and abs(engine_w - true_w) < 1e-5, (engine, true)


@pytest.mark.parametrize(
    ("sink", "h", "offset"), [(1.0, 0.025, 0.01), (1.0, 0.05, 0.01), (10.0, 0.025, 0.01)]
)
def test_the_crossing_steps_quadrature_beside_probe_2f(sink, h, offset):
    """The crossing half-step takes the quadrature, positive, and overbooks its true heat (probe
    2f: +7.9% to +127% with h L, at the sweep's crossing)."""
    raw = rfx.crossing(end=2 * h, dt=2 * h, sink=sink, offset=offset)
    terms, true = first_half_step(raw, h)
    assert not terms.nonreversing[0] and terms.heat[0] > 0
    error = relative(terms.heat[0], true.heat[-1][0])
    record(
        "crossing_accuracy", sink=sink, h=h, offset=offset, hL=float(terms.max_hl), heat_error=error
    )
    assert error > -1e-6


@pytest.mark.parametrize("trace", [1e-12, 1e-9, 1e-6])
def test_the_reversal_onsets_size_beside_probe_2g(trace):
    """The known limit, documented (§3.3, option (a)): the onset half-step's booked heat over its
    true heat, at probe 2g's half-steps."""
    factors = {}
    for h in (0.025, 0.0125):
        raw = rfx.reversal_onset(trace, end=2 * h, dt=2 * h)
        terms, true = first_half_step(raw, h)
        factors[h] = dict(
            reverses=bool(not terms.nonreversing[0]),
            factor=terms.heat[0] / true.heat[-1][0],
            heat_pJ=terms.heat[0],
            true_heat_pJ=true.heat[-1][0],
        )
    record("reversal_onset_size", trace=trace, by_half_step=factors)
    assert all(v["reverses"] for v in factors.values())
