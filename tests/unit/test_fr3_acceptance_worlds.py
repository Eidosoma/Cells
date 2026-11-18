"""FR-3's engine-layout adapter against the references' registered worlds (tier 1, no run).

validation/tissue/site_occupancy_acceptance_fixtures builds every registered world of
validation/fr3/references/reference_inputs.json as an engine definition. Here, with no engine
run: every world, ladder rung and control variant is admitted (parse and the clock's step
checks); the engine's layout holds the references' registered capacities and K_d
(designs/fr3_reference_values.json) and the declared anchors; the records sit on the step grid at
the registered times; only an internalising population gets an internalisation schedule; the
inputs file is the one the references' design records (its git blob); and each control world
differs from its registered world in exactly its declared change.
"""

import json

import numpy as np
import pytest

from cells.core.runner import timeline
from cells.core.specs import parse_spec
from cells.models.registry import get_model
from validation.tissue import site_occupancy_acceptance_fixtures as af
from validation.tissue import site_occupancy_acceptance_qualification as generator

VALUES = json.loads((af.DESIGN.parent / "fr3_reference_values.json").read_text())["worlds"]


def admitted(raw):
    spec = parse_spec(raw)
    timeline(spec)
    return spec


@pytest.mark.parametrize("world_id", af.world_ids())
def test_every_registered_world_is_admitted_with_the_registered_layout(world_id):
    world = af.registered(world_id)
    spec = admitted(af.registered_world(world_id))
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    capacity = np.asarray(p.site_capacity_fmol)
    registered = VALUES[world_id]
    np.testing.assert_allclose(capacity, registered["sites_fmol"], rtol=1e-15, atol=0)
    np.testing.assert_allclose(np.asarray(p.site_off_rate) / np.asarray(p.site_on_rate),
                               registered["K_d_mM"], rtol=1e-15, atol=0)
    theta = [pop["initial_occupancy"] for pop in world["populations"]]
    np.testing.assert_allclose(np.asarray(p.site_bound_anchor_fmol), capacity * theta, rtol=1e-15)
    dt = spec.execution.dt
    assert [generator.ms(t) for t in spec.experiment.observation_times] == sorted(
        {generator.ms(t) for t in world["record_times_s"]})
    assert all(round(t / dt) * dt == t for t in spec.experiment.observation_times)
    raw = af.registered_world(world_id)
    routes = {(c["population"], c["route"]) for c in raw["experiment"]["site_controls"]}
    internalising = {pop["id"] for pop in world["populations"] if pop["internalisation"]}
    assert {pid for pid, route in routes if route == "internalisation"} == internalising
    s = list(spec.model.species_ids).index(af.LIGAND)
    for node in (*spec.model.cells, *spec.model.extracellular):
        if node.id in world["nodes"]:
            declared = world["nodes"][node.id]["L_mM"]
            assert node.initial_amount_fmol[s] / node.volume_pL == pytest.approx(declared,
                                                                               rel=1e-15)


def test_the_ladder_and_every_control_world_are_admitted():
    for dt in af.LADDER_S:
        admitted(af.registered_world(af.LADDER_WORLD, dt=dt))
    for world in (af.rates(af.LADDER_WORLD, "k_on"), af.rates(af.LADDER_WORLD, "k_off"),
                  af.rates(af.LADDER_WORLD, "k_int"), af.alpha_ignored("q1_eps_1e-1_alpha_half"),
                  af.binding_multiplier("q3_binding_multiplier", "ignored"),
                  af.binding_multiplier("q3_binding_multiplier", "squared"),
                  af.internalisation_multiplier_ignored("q5_class_switch"),
                  af.cell_volume("q5_inward", "cell_0", 1.0),
                  af.cell_volume("q1_eps_1e-1", "cell_0", 1.0),
                  *(af.kinetic_factor(f"q4_alpha_1_{r}", a) for r in ("low", "high")
                    for a in (0.5, 0.25)),
                  *(af.affinity_factor(f"q4_alpha_1_{r}", a) for r in ("low", "high")
                    for a in (0.5, 0.25)),
                  *(generator.batch_world(v) for v in generator.BATCH_VARIANTS),
                  generator.moved_switch(), generator.idle_world(), generator.twin(),
                  generator.twin(changed=True)):
        admitted(af.build(world))
    admitted(af.build(generator.idle_world(), operator=False))
    admitted(af.build(generator.idle_world(), populations=False))


def test_each_control_changes_only_its_declaration():
    base = af.registered(af.LADDER_WORLD)
    changed = af.rates(af.LADDER_WORLD, "k_int")
    assert changed["populations"][0]["internalisation"]["rate_per_s"] == pytest.approx(
        1.01 * base["populations"][0]["internalisation"]["rate_per_s"])
    changed["populations"][0]["internalisation"] = base["populations"][0]["internalisation"]
    assert changed == base
    k = af.kinetic_factor("q4_alpha_1_high", 0.25)
    assert k["populations"][0]["accessible_fraction"] == 1.0
    assert [e["binding"]["r0"] for e in k["site_controls"]] == [0.25]
    a = af.affinity_factor("q4_alpha_1_high", 0.25)
    one = af.registered("q4_alpha_1_high")["populations"][0]
    assert a["populations"][0]["association_rate_per_mM_per_s"] == pytest.approx(
        0.25 * one["association_rate_per_mM_per_s"])
    moved = generator.moved_switch()
    times = [generator.ms(e["time_s"]) for e in moved["site_controls"]]
    assert times == [0, 5001, 10000]


def test_the_inputs_are_the_registered_file():
    design = json.loads(af.DESIGN.read_text())
    assert generator.git_blob(af.INPUTS.read_bytes()) == design["inputs"]["git_blob"]
    assert tuple(af.inputs()["dt_ladder_s"]) == af.LADDER_S
