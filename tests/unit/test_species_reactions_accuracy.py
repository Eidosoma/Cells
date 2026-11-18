"""The scheme's accuracy beside the design note's figures (D152 v1; §11.1's pins): a regression
guard with loose bounds outside MG0c's judged list (the lead's protocol review, ruling 7).

The mixed-node heat and work split is guarded here, not qualified, until the first mixed-node
protocol (the scope line of MG0c's protocol). The tests:
- the share onset's first half-step, and its whole heat and work at 5 s, against dr.integrate_node
  (probe 2d's grid: h = 0.05, 0.025 and 0.0125 s);
- the background guard: the whole heat's relative change for a thousandfold trace, the engine's
  against the true heat's;
- the crossing step's heat (probe 2e);
- the reversal onset's first half-step against its true heat (probe 2g's per-step factors).
They use the independent references (validation/reactions, through REFERENCES_USAGE.md only).
Moved unchanged from test_species_reactions_reference_runs.py, whose helpers now live in the
fixtures (rfx.reference_rt, rfx.engine_network_rows). Measured
values go to species_reactions_accuracy.jsonl in the tier runner's CELLS_OUTPUT_ROOT.
"""

import json
import os
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.operators import species_reactions as sr
from cells.registry.models import get_model
from validation.reactions import dissipation_reference as dr
from validation.tissue import species_reactions_fixtures as rfx

jax.config.update("jax_enable_x64", True)
rt = rfx.reference_rt  # The engine's R and T, for the references.
engine_rows = rfx.engine_network_rows


def record(test, **values):
    root = os.environ.get("CELLS_OUTPUT_ROOT")
    if root:
        path = Path(root) / "species_reactions_accuracy.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as out:
            out.write(json.dumps(dict(test=test, **values), default=float) + "\n")


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
