"""FR-31's pore clock on the device in a population (OL6 slice S4, L1; pore_device.py).

Identities in exact events only (no comparison with the rate equations, D304): two deflating
vesicles on one small pool, their tension from F, each rupture at its own t_c, where H reaches its
own E (domain 7, its key, counter 0); the run shares every draw with its pore-free twin until the
first opening; each slot frees at its rupture and the books close; a checkpoint between the
ruptures carries the clocks in its host document, and its restart resumes bit for bit (planted: a
changed threshold, refused).
A new file for the population's device clock (D224): one population world and its twin compiled,
about 80 s on a shared light CPU, most of it the osmotic and pore verdicts and the compiles.
"""

import copy
import dataclasses
import functools

import jax
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, digest, parse_spec
from cells.models.assembly_lineages_v2 import checkpoints, pore_clock, runner
from tests.unit.test_assembly_lineages_v2_rate_equations_pores import hazard
from tests.unit.test_assembly_lineages_v2_rate_equations_vesicles import (
    K_L,
    Q,
    population_definition,
    population_world,
)

jax.config.update("jax_enable_x64", True)


def exact(world):
    d = copy.deepcopy(population_definition(world, horizon=20.0, schedules=None))
    x = d["execution"]
    del x["representation"]
    x["molecule_capacity"], x["chunk_events"] = 2**20, 16
    d["experiment"] |= {"trace": True, "event_limit": 10**7}
    return d


def worlds():
    twin = population_world([12000, 11000], 0.97, slots=2)
    twin["founder"]["L@pool"] = 1000
    pores = copy.deepcopy(twin)
    pores["hazard"] = hazard(4e-12, 30.0, Q * K_L * 12000 / 2.0)
    return pores, twin


@functools.cache
def runs():
    pores, twin = worlds()
    spec = parse_spec(exact(pores))
    return spec, runner.run(spec), runner.run(parse_spec(exact(twin)))


def test_each_slot_ruptures_at_its_own_t_c_and_the_books_close():
    spec, run, _ = runs()
    events = run.pores["events"]
    assert run.pores["causes"]["pore"] == 2 and sorted(e["slot"] for e in events) == [0, 1]
    base = spec_base(spec)
    for e in events:
        _, energy = pore_clock.threshold(base, e["key"], 0)
        assert e["threshold_E"] == energy and e["hold"] is None
        assert e["clock_H"] == pytest.approx(energy, rel=1e-12)
    assert [d[0] for d in run.pores["draws"]] == [0, 1 << 32]
    assert run.closure["holds"] and not np.asarray(run.final["alive"]).any()


def test_the_population_shares_every_draw_with_its_twin_until_the_first_opening():
    _, run, twin = runs()
    first = min(e["time_s"] for e in run.pores["events"])
    n = int(np.sum(run.trace["event_time"] <= first))
    assert n > 100
    for name in ("event_time", "event_channel", "event_group"):
        assert np.array_equal(run.trace[name][:n], twin.trace[name][:n]), name


def test_a_cut_between_the_ruptures_resumes_bit_for_bit_with_its_clocks():
    spec, run, _ = runs()
    times = sorted(e["time_s"] for e in run.pores["events"])
    cut = int(np.sum(run.trace["event_time"] <= (times[0] + times[1]) / 2))
    first = runner.run(spec, stop=cut)
    checkpoint = checkpoints.make(first)
    assert len(checkpoint.host["doc"]["pore_clocks"]) == 1  # one vesicle lives, its clock saved
    resumed = runner.run(spec, start=checkpoint)
    for name in ("event_time", "event_channel"):
        assert np.array_equal(resumed.trace[name], run.trace[name][cut:]), name
    assert resumed.pores["events"] == [e for e in run.pores["events"] if e["time_s"] > times[0]]
    host = copy.deepcopy(checkpoint.host)  # planted: a changed threshold, re-digested
    host["doc"]["pore_clocks"][0]["threshold_E"] += 1e-9
    state = checkpoints.state_digest(checkpoint.lane, host)
    planted = dataclasses.replace(checkpoint, host=host, digest=digest(
        {"definition": spec.fingerprint, "clock": checkpoint.clock, "state": state}))
    with pytest.raises(ConfigError, match="pore clocks are not its definition's"):
        runner.run(spec, start=planted)


def spec_base(spec):
    from cells.models.assembly_lineages_v2 import model

    return model.layout(spec).base_key
