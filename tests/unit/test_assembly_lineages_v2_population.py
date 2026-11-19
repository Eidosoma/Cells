"""OL2 milestone 3 in cells.assembly_lineages@2: the diagnostic record, Poisson shear times and
§0.2d item 9 (slice 1); the shared pool, population division and serial transfer follow
(docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md §1.8, §2.1, §2.6; the design note's §0.2d items 5, 6, 9, 10).

Each claim with a planted error it must catch (D187):
- P1: the diagnostic record of a single-lineage division run states every draw: each committed
  draw's uniforms, recomputed from its address, are the device's own; each schedule stop discards
  one counted draw (a run that ends at a stop has no ending draw); the step events rebuild the
  rows' counts
  (planted: a draw record missing its discarded draws no longer matches the device's sequence);
- P2: Poisson shear times are −ln(u)/λ gaps on the schedule's own stream (domain 6, its index),
  each gap its own draw from counter 0, the gap past the horizon recorded; the run's stream
  identity states domains 5 and 6 (planted: gaps drawn as one block differ);
- P3: every run of the family refuses to start with threefry's partitionable flag off, and the
  bundle's environment record states the flag (§0.2d item 9).

World-compiling cost: one program (the division test's world, three runs of one structure); its
seconds on the timed lane are stated with its tier row. Reason: the record is the run's own.
"""

import json
import math

import numpy as np
import pytest

from cells.definitions.specs import ConfigError
from cells.models.assembly_lineages_v2 import diagnostic, division, records, runner, streams
from tests.unit.test_assembly_lineages_v2_division import TIMES, spec_of, world_a


def with_diagnostic(spec):
    import dataclasses

    return dataclasses.replace(
        spec, experiment=dataclasses.replace(spec.experiment, diagnostic=True)
    )


def test_the_diagnostic_record_states_every_draw_and_rebuilds_the_rows(tmp_path):
    s = with_diagnostic(spec_of(world_a()))
    run = runner.run(s).check()
    body, arrays = run.diagnostic["body"], run.diagnostic["arrays"]
    fates = arrays["draw_fate"]
    committed = fates == diagnostic.COMMITTED
    # Every committed draw is the device's own (checked in build; here against the trace too).
    assert committed.sum() == len(run.trace["event_channel"])
    np.testing.assert_array_equal(arrays["draw_uniforms"][committed],
                                  run.diagnostics["event_uniforms"])  # fmt: skip
    # One discarded draw per schedule stop, at the occupant's next counter. The last stop is the
    # horizon (10 s), so no later draw ends the run.
    assert (fates == diagnostic.DISCARDED).sum() == len(TIMES)
    assert (fates == diagnostic.ENDED).sum() == 0
    keys, counters = arrays["draw_key"], arrays["draw_counter"]
    for key in np.unique(keys):
        assert counters[keys == key].tolist() == list(range((keys == key).sum()))
    # Planted: without the discarded draws, the counters no longer run 0, 1, 2, ... per key.
    kept = fates != diagnostic.DISCARDED
    assert any(counters[kept & (keys == key)].tolist() != list(range((kept & (keys == key)).sum()))
               for key in np.unique(keys))  # fmt: skip
    # The step events rebuild the rows: the last event's state is the end row's.
    world = s.model.world
    vesicle, pool = diagnostic._split(world, run.rows["place_count"][-1])
    assert arrays["event_vesicle_after"][-1].tolist() == vesicle.tolist()
    assert arrays["event_pool_after"][-1].tolist() == pool.tolist()
    np.testing.assert_allclose(np.cumsum(arrays["event_heat_kT"])[-1],
                               run.rows["event_heat_kT"][-1], rtol=1e-12)  # fmt: skip
    # Each attempt's block is its address's draw; the states and the environment are stated.
    attempts = [a for stop in body["shear_events"] for a in stop["attempts"]]
    assert len(attempts) == len(run.division["fissions"]["fission_time"])
    first = attempts[0]
    block = arrays["attempt_uniforms"][: first["uniforms_count"]]
    layout = runner.model.layout(s)
    np.testing.assert_array_equal(
        block, division.block(layout.base_key, first["key"], 0, len(block))
    )
    assert body["environment"]["jax_threefry_partitionable"] is True
    assert body["end"] == run.status and body["states"]["final"]["slots"][0]["key"] == 5
    records.write_run(tmp_path / "d", run)
    assert json.loads((tmp_path / "d" / "diagnostic.json").read_text())["fates"] == list(
        diagnostic.FATES
    )
    manifest = json.loads((tmp_path / "d" / "manifest.json").read_text())
    assert manifest["runtime"]["jax_threefry_partitionable"] is True
    assert set(manifest["files_sha256"]) >= {"diagnostic.json", "diagnostic.npz"}


def test_poisson_shear_times_are_gaps_on_the_schedule_s_own_stream():
    w = world_a()
    d = spec_of(w)
    import dataclasses

    poisson = division.Schedule(3, "shear", 2, None, 0.5, None)
    s = dataclasses.replace(d, experiment=dataclasses.replace(d.experiment, schedules=(poisson,)))
    layout = runner.model.layout(s)
    events, draws = division.timeline(s.experiment.schedules, 10.0, layout.base_key)
    key = streams.stream_key_data(layout.base_key, 3, "schedule")
    t, want = 0.0, []
    for counter, (index, c, u, use, time) in enumerate(draws):
        assert (index, c, use) == (3, counter, "gap")
        assert u == float(np.asarray(streams.uniforms(key, counter, 1))[0])
        t -= math.log(u) / 0.5
        assert time == t
        want.append(t)
    assert want[-1] > 10.0 and all(x <= 10.0 for x in want[:-1])  # the gap past the horizon
    assert [e[0] for e in events] == want[:-1]
    planted = np.asarray(streams.uniforms(key, 0, len(draws)))  # one block, not one draw each
    assert planted[1] != draws[1][2]
    from cells.models.assembly_lineages_v2.spec import stream_identity

    stated = stream_identity(s)
    assert stated["domains"]["world"] == 5 and stated["domains"]["schedule"] == 6
    assert stated["reserved_domains"] == ["label"]
    assert "schedule" not in stream_identity(spec_of(w))["domains"]  # declared times: unchanged


def test_every_run_refuses_a_threefry_that_is_not_partitionable():
    import jax

    from cells.definitions.specs import parse_spec
    from tests.assembly_lineage_v2_fixtures import definition, world

    plain = parse_spec(definition(world()))  # an OL1 world: no geometry, no division
    jax.config.update("jax_threefry_partitionable", False)
    try:
        with pytest.raises(ConfigError, match="§0.2d item 9"):
            runner.run(plain)
    finally:
        jax.config.update("jax_threefry_partitionable", True)
