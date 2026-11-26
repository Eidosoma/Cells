"""FR-26's acceptance (D244, W): occupied sites and an active reaction across one replacement,
compiled through the runner. One world, about 35 s on one core.

Its reason: it is the request's minimal acceptance. The event rows (test_site_occupancy.py) cannot
show the reaction and the binding running on both sides of the event, nor the runner's host checks
on every row across it.

The world (site_occupancy_fixtures.replaced_sites): two cells with contact patches on ecs_0, cell_1
replaced at 20 ms from template T; an outward population o1 on contact_1 (theta0 0.5) and an
inward one i1 on wall_cell_1 (theta0 0.3), both reset by cells.operator.site_occupant_replacement@1 (theta' 0.1
and 0.9, binding multipliers 2 and 0.5 against the founder's 1); o0 on cell_0's contact_0; and
D152's S -> P in cell_1 (k 2/s), its multiplier 1 for the founder and 0.25 for T's newcomer. ARS at
1 ms, 40 steps. On every row the runner's host checks pass (every ledger, the energy ledger
included), and for each of S and P the balance of the design's §4.8 holds:

    sum of the free amounts + sum of the bound = their start + the held baths' supply
        + replacement's supplied - removed + W's arrived - departed + D152's produced - consumed.

Planted: the balance without W's departed term misses from the event row on by the bound amount
that left with the occupant.

The event row's observation (D264 finding 2, a tester's report). The row at t_e is the state the
step ending there left, before the event: the departing occupant's. Its exported reaction rate is
the departing occupant's, k S x 1, not the founder's S times the newcomer's 0.25 (0.00048 fmol/s,
where the departing rate is 0.00192 and the incoming 0.00050). The next row's is the incoming
occupant's, k S x 0.25 (pump_composite's observe_history: an occupant event's row observes with
the controls held over the step that ended there).
"""

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.registry.inventory_species import add_inventory_species
from cells.registry.models import get_model
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import site_occupancy_fixtures as sfx
from validation.tissue import species_reactions_fixtures as rfx

T_E, END, DT = 0.02, 0.04, 1e-3


def world():
    pops = [
        sfx.population("o1", patch="contact_1", theta0=0.5),
        sfx.population("i1", patch="wall_cell_1", face="inside", theta0=0.3),
        sfx.population("o0", patch="contact_0", theta0=0.4),
    ]
    raw = sfx.replaced_sites(
        pops,
        {"o1": (0.1, 2.0, None), "i1": (0.9, 0.5, None)},
        t_e=T_E,
        dt=DT,
        end=END,
        observation_times=fx.grid_times(END, DT, DT),
    )
    raw = add_inventory_species(
        raw, "P", trace_mM=1e-9, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
    )
    species = [
        rfx.species(fx.SPECIES, moieties={"X": 1}),
        rfx.species("P", moieties={"X": 1}, mu=-1.0),
    ]
    reaction = rfx.mass_action("convert", {"cells": ["cell_1"]}, {fx.SPECIES: 1}, {"P": 1}, 2.0)
    raw = rfx.with_reactions(raw, species, [reaction], [("convert", None, [(0.0, 1.0)])])
    block = raw["model"]["operators"][-1]
    block["templates"] = [dict(template_id="T", multipliers={"convert": 0.25})]
    return raw


def balance(spec, h, p, s, *, without_departed=False):
    """[row] the §4.8 residual of species row s (fmol)."""
    cells = np.asarray(p.amount_reference)[s] + np.asarray(h.amount_increment)[:, s, :]
    finite = ~np.asarray(p.reservoir)
    outside = (
        np.asarray(p.extracellular_amount_reference)[s]
        + np.asarray(h.extracellular_amount_increment)[:, s, :]
    )
    free = cells.sum(axis=1) + outside[:, finite].sum(axis=1)
    ligand = s == list(spec.model.species_ids).index(fx.SPECIES)
    bound = (
        (np.asarray(p.site_bound_anchor_fmol) + np.asarray(h.site_bound_increment_fmol)).sum(axis=1)
        if ligand
        else np.zeros(free.shape)
    )
    supply = np.asarray(h.reservoir_supplied)[:, s, :].sum(axis=1)
    replaced = (
        np.asarray(h.replacement_supplied_fmol)[:, s, :]
        - np.asarray(h.replacement_removed_fmol)[:, s, :]
    ).sum(axis=1)
    departed = np.asarray(h.site_departed_fmol).sum(axis=1) if ligand else 0.0
    arrived = np.asarray(h.site_arrived_fmol).sum(axis=1) if ligand else 0.0
    reacted = (
        np.asarray(h.reaction_produced_fmol)[:, s, :]
        - np.asarray(h.reaction_consumed_fmol)[:, s, :]
    ).sum(axis=1)
    reacted = reacted + (
        np.asarray(h.reaction_outside_produced_fmol)[:, s, :]
        - np.asarray(h.reaction_outside_consumed_fmol)[:, s, :]
    ).sum(axis=1)
    if without_departed:
        departed = 0.0
    total = free + bound
    expected = total[0] + supply + replaced + arrived - departed + reacted
    return total - expected


def test_occupied_sites_and_an_active_reaction_cross_one_replacement():
    spec = parse_spec(world())
    result = run(spec)  # The runner's host checks on every accepted row; a failure raises.
    _, p = get_model(spec.model).initial_values(spec)
    h = result.history
    times = np.asarray(result.times, dtype=float)
    k = int(np.flatnonzero(times == T_E)[0])
    ids = list(spec.model.species_ids)
    for name in (fx.SPECIES, "P"):
        residual = balance(spec, h, p, ids.index(name))
        assert np.max(np.abs(residual)) <= 1e-15, (name, np.max(np.abs(residual)))
    s = ids.index(fx.SPECIES)
    planted = balance(spec, h, p, s, without_departed=True)
    departed = np.asarray(h.site_departed_fmol)[k + 1].sum()
    assert abs(planted[k + 1] + departed) <= 1e-15 and departed > 0  # Short by B that left.
    produced = np.asarray(h.reaction_produced_fmol)[:, ids.index("P"), :].sum(axis=1)
    assert produced[k] > 0 and produced[-1] > produced[k + 1] > produced[k]  # Both sides.
    bound = np.asarray(p.site_bound_anchor_fmol) + np.asarray(h.site_bound_increment_fmol)
    capacity = np.asarray(p.site_capacity_fmol)
    theta = bound / capacity
    assert abs(theta[k, 0] - 0.5) < 0.05 and abs(theta[k + 1, 0] - 0.1) < 0.05  # Reset at t_e.
    # The event row reports the departing occupant, the next row the incoming one (D264).
    j = int(np.flatnonzero(np.asarray(spec.experiment.observation_times, dtype=float) == T_E)[0])
    rate = np.asarray(result.observations.reaction_rate_fmol_per_s)[:, 0]
    cell_s = np.asarray(p.amount_reference)[s, 1] + np.asarray(h.amount_increment)[:, s, 1]
    assert rate[j] == pytest.approx(2.0 * 1.0 * cell_s[k], rel=1e-14)
    assert rate[j + 1] == pytest.approx(2.0 * 0.25 * cell_s[k + 1], rel=1e-14)
