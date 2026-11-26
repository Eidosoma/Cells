"""Compiled face-free runs of cells.operator.local_species_reactions@1 against the independent references
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
* **Reactions at several sites** with their own multipliers (rfx.several_sites), against
  nr.run_half_steps with the same [R, N] multipliers (milestone 3).
The scheme's accuracy beside §11.1's figures (the pins) lives in
test_species_reactions_accuracy.py, a regression guard with loose bounds outside MG0c's judged
list (the lead's protocol review, ruling 7). Measured values go to
species_reactions_reference_runs.jsonl in the tier runner's CELLS_OUTPUT_ROOT. A few minutes of
compiles: tier 3.
"""

import json
import os
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
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


rt = rfx.reference_rt  # The engine's R and T, for the references.
engine_rows = rfx.engine_network_rows


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


def test_several_sites_with_their_own_multipliers_run_as_the_reference():
    """Milestone 3 (moved from milestone 2): reactions at several sites of unequal volumes, each
    with its own schedule (rfx.several_sites: cell_1 passive-only beside the mixed cell_0, a
    multiplier of 2.5 at one node, one changed mid-run), against nr.run_half_steps with the same
    [R, N] multipliers from the declared schedules."""
    raw = rfx.several_sites()
    multipliers = rfx.reference_multipliers(raw)
    nodes = [n["id"] for n in rfx.reference_nodes(raw)]
    cell_0, cell_1, ecs_2 = (nodes.index(n) for n in ("cell_0", "cell_1", "ecs_2"))
    removal = 4
    last = 2 * int(round(raw["experiment"]["end_time"] / raw["execution"]["dt"])) - 1
    assert (multipliers(0)[removal, ecs_2], multipliers(last)[removal, ecs_2]) == (1.0, 0.3)
    result, _ = against_reference(raw, multipliers, "several_sites")
    e = engine_rows(result)
    assert e["work"][-1][cell_1] == 0.0 < e["heat"][-1][cell_1]  # Passive-only: heat alone.
    assert e["work"][-1][cell_0] != 0.0  # Mixed.
    record(
        "several_sites",
        heat_pJ=e["heat"][-1].tolist(),
        work_pJ=e["work"][-1].tolist(),
        nodes=nodes,
    )
