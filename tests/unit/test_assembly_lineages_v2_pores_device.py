"""FR-31's pore clock on the device, for a tension that comes from F (OL6 slice S4, L1; the OL6
design note's §3.6 and §6.3; pore_device.py), in a single lineage.

Identities and closed forms in exact events only (no comparison with the rate equations, D304):
- a vesicle whose tension comes from F (an osmotic lumen, an area-changing join, no hold) ruptures
  where H, recomputed on the host from its own trace as Σ k_v(n_i)·τ_i (pore_device.rate on
  NumPy), reaches E (domain 7, key 0) at the recorded t_c, to 1e-12;
- it shares every chemistry draw with its pore-free twin until then: the traces are identical bit
  for bit up to t_c, and the twin's next event lies beyond it (the crossing draw was discarded);
- the opening books pore_clock.opening_from_f (w = 0), the books close, and the bundle has no hold
  column; the draw names its t*; the bundle states the device's clock rule and lifecycle order;
- the parse: σ from F is admitted in exact events, with σ_max ≤ σ_β/4 (tension_hold.sigma_from_f's
  refusal beyond it); Phase A's hold worlds keep their refusals (tests/unit/
  test_assembly_lineages_v2_pores.py, unchanged).
A new file for the slice's exact path (D224): one world and its twin compiled (the device clock's
program and the kernel's), about 75 s on a shared light CPU, most of it the osmotic and pore
verdicts and the two compiles. The population's rows are in
test_assembly_lineages_v2_pores_device_population.py.
"""

import copy
import functools
import json

import jax
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages_v2 import model, pore_clock, pore_device, records, runner
from tests.assembly_lineage_v2_fixtures import definition
from tests.unit.test_assembly_lineages_v2_rate_equations_pores import hazard, tense_world
from tests.unit.test_assembly_lineages_v2_rate_equations_vesicles import K_L, Q, vesicle_world

jax.config.update("jax_enable_x64", True)


def exact(world, horizon=50.0):
    d = definition(world, horizon=horizon, event_limit=10**7, molecules=2**19, chunk=16)
    d["experiment"]["trace"] = True
    return d


@functools.cache
def runs():
    spec = parse_spec(exact(tense_world()))
    return spec, runner.run(spec), runner.run(parse_spec(exact(vesicle_world())))


def test_the_pore_fires_where_h_from_the_trace_reaches_e(tmp_path):
    spec, run, _ = runs()
    assert run.status == "lysed" and run.pores["causes"] == {"pore": 1}
    (event,) = run.pores["events"]
    _, energy = pore_clock.threshold(model.layout(spec).base_key, 0, 0)
    assert event["threshold_E"] == energy and event["hold"] is None and event["work_kT"] == 0.0
    layout, structure = model.layout(spec), model.structure(spec)
    count_change, _ = runner.changes(layout, structure)
    pore = pore_device.constants(spec.model.world)
    counts = np.asarray(model.founder(spec), dtype=np.int64)
    h, last = 0.0, 0.0
    for t, code in zip(run.trace["event_time"], run.trace["event_channel"], strict=True):
        h += float(pore_device.rate(counts, layout, pore, np)) * (t - last)
        r = abs(int(code)) - 1
        counts = counts + count_change[r if code > 0 else structure.steps + r]
        last = t
    k = float(pore_device.rate(counts, layout, pore, np))
    assert event["rate_per_s"] == pytest.approx(k, rel=1e-12)
    h += k * (event["time_s"] - last)
    assert h == pytest.approx(energy, rel=1e-12) and event["clock_H"] == pytest.approx(energy,
                                                                                       rel=1e-12)
    work, heat, delta_f = pore_clock.opening_from_f(spec.model.world, event["area_m2"],
                                                    event["sigma_N_per_m"])  # fmt: skip
    assert (work, heat, delta_f) == (0.0, event["opening_heat_kT"], event["delta_F_kT"])
    assert run.closure["holds"] and "tension_hold_work_kT" not in run.rows
    assert run.pores["draws"] == [(0, 0, *pore_clock.threshold(model.layout(spec).base_key, 0, 0),
                                   event["time_s"])]  # fmt: skip
    records.write_run(tmp_path / "bundle", run)
    record = json.loads((tmp_path / "bundle" / "run.json").read_text())
    assert record["ssa"]["pore_clock"] == pore_device.CLOCK and record["tension_hold"] == []
    assert "candidate opening" in record["lifecycle"]["order"]
    assert record["pores"]["causes"] == {"pore": 1, "threshold": 0}


def test_it_shares_every_draw_with_its_pore_free_twin_until_the_opening():
    _, run, twin = runs()
    (event,) = run.pores["events"]
    n = len(run.trace["event_time"])
    assert n > 100 and run.trace["event_time"][-1] < event["time_s"]
    for name in ("event_time", "event_channel"):
        assert np.array_equal(run.trace[name], twin.trace[name][:n]), name
    assert twin.trace["event_time"][n] > event["time_s"]  # the crossing draw was discarded


def test_the_parse_admits_sigma_from_f_within_sigma_beta_over_four():
    assert pore_device.clocked(parse_spec(exact(tense_world())))
    wide = copy.deepcopy(exact(tense_world()))
    wide["model"]["world"]["hazard"] = hazard(2e-12, 30.0, Q * K_L * 12000 / 2.0)
    with pytest.raises(ConfigError, match="with sigma from F the tension reaches sigma_max"):
        parse_spec(wide)
