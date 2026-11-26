"""The structure of cells.model.assembly_lineages@2's kernel and records (OL1), with no value computed.

Structural only (no rate, free energy or event of OL1's laws is computed; programs are traced
abstractly). Each claim with a planted error it must catch (D187):
- each step's entries are its distinct places in place order, with exact no-op padding, and give
  back the declared stoichiometry; held places are flagged and the membrane's change is the
  step's (planted: one coefficient changed);
- the channel table lists every step's forward, then every reverse, in fold order, with the trace's
  codes (planted: a table with two rows exchanged);
- version 2 draws from @1's streams: domains 0-3 give @1's keys exactly, and the reserved domains
  (label, world) are refused (planted: a key from another domain differs); a block, drawn at the
  next power of two, is the plain draw bitwise (planted: a suffix of the larger draw);
- one program per structure: worlds that differ only in values share a structure and trace for
  any lane count; a convention selects another program (planted: a token changed);
- the bundle declares every array the runner writes.
"""

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages import streams as v1_streams
from cells.models.assembly_lineages_v2 import kernel, model, records, runner, streams
from tests.assembly_lineage_v2_fixtures import definition, world


def spec(**kw):
    return parse_spec(definition(world(**kw)))


def stoichiometry(layout, r):
    """{place index: (alpha, beta)} of step r, from its entries (padding skipped)."""
    out = {}
    for k in range(kernel.ENTRIES):
        a, b = int(layout.entry_alpha[r, k]), int(layout.entry_beta[r, k])
        if a + b:
            out[int(layout.entry_place[r, k])] = (a, b)
    return out


def declared(world_, step):
    index = {p.name: i for i, p in enumerate(world_.places)}
    reactants, products = dict(step.reactants), dict(step.products)
    return {
        index[n]: (reactants.get(n, 0), products.get(n, 0)) for n in set(reactants) | set(products)
    }


def test_entries_are_each_step_s_distinct_places_with_no_op_padding():
    s = spec()
    w, layout = s.model.world, model.layout(s)
    for r, step in enumerate(w.steps):
        assert stoichiometry(layout, r) == declared(w, step)
        real = (layout.entry_alpha[r] + layout.entry_beta[r]) > 0
        assert list(real) == sorted(real, reverse=True)  # Real entries first, then padding.
        assert np.all(layout.entry_place[r][~real] == 0)
        places = layout.entry_place[r][real]
        assert list(places) == sorted(places)
        held = [w.places[p].held for p in places]
        assert list(layout.entry_held[r][real]) == held
        membrane = sum(
            b - a for p, (a, b) in declared(w, step).items() if w.places[p].phase == "membrane"
        )
        assert layout.step_moves[r] == membrane
        assert layout.locus_membrane[r] == (step.locus == "membrane")
    assert not layout.step_active[len(w.steps) :].any()
    # Planted: one coefficient changed is seen.
    planted = layout._replace(entry_alpha=layout.entry_alpha.copy())
    planted.entry_alpha[1, 0] += 1
    assert stoichiometry(planted, 1) != declared(w, w.steps[1])


def test_the_channel_table_lists_forwards_then_reverses_with_their_codes():
    w = spec().model.world
    table = kernel.channel_table(w)
    rows, R = table["rows"], len(w.steps)
    assert [r["row"] for r in rows] == list(range(2 * R))
    assert [r["event_channel"] for r in rows] == [*range(1, R + 1), *range(-1, -R - 1, -1)]
    for r, step in enumerate(w.steps):
        forward, reverse = rows[r], rows[R + r]
        assert forward["step"] == reverse["step"] == step.id
        assert forward["reactants"] == reverse["products"] == dict(step.reactants)
        assert forward["products"] == reverse["reactants"] == dict(step.products)
    planted = rows[:]
    planted[0], planted[1] = planted[1], planted[0]
    assert [r["event_channel"] for r in planted] != [r["event_channel"] for r in rows]


def test_version_2_draws_from_1_s_streams():
    base = streams.base_key_data(7, 1, 2, 3)
    assert np.array_equal(base, v1_streams.base_key_data(7, 1, 2, 3))
    for domain, name in streams.V1_NAMES.items():
        mine = np.asarray(streams.stream_key_data(base, 5, domain))
        theirs = np.asarray(v1_streams.stream_key_data(base, 5, name))
        assert np.array_equal(mine, theirs) and streams.DOMAINS[domain] == v1_streams.DOMAINS[name]
    for reserved in streams.RESERVED:
        with pytest.raises(ValueError, match="reserved"):
            streams.stream_key_data(base, 5, reserved)
    other = np.asarray(streams.stream_key_data(base, 5, "partition"))  # Planted: another domain.
    assert not np.array_equal(other, np.asarray(streams.stream_key_data(base, 5, "events")))
    # A block (a partition's draw, at the next power of two) is the plain draw, bitwise.
    for count in (2, 3):
        plain = np.asarray(streams.uniforms(other, 7, count))
        assert np.array_equal(np.asarray(streams.block(other, 7, count)), plain), count
    planted = np.asarray(streams.uniforms(other, 7, 4))[-3:]  # Planted: a suffix, not the prefix.
    assert not np.array_equal(planted, np.asarray(streams.block(other, 7, 3)))


def test_one_program_per_structure_traces_for_any_lane_count():
    a = spec()
    b_world = world()
    b_world["steps"][0]["forward_rate_per_s"] = 3.0
    b_world["founder"]["L@pool"] = 7
    b = parse_spec(definition(b_world))
    assert model.structure(a) == model.structure(b)
    structure = model.structure(a)
    program = kernel.program(structure)
    for lanes in (1, 3):
        layout = jax.tree_util.tree_map(lambda *xs: np.stack(xs), *[model.layout(a)] * lanes)
        founders = jax.ShapeDtypeStruct((lanes, structure.places), np.int64)
        lane = jax.eval_shape(program.initial, founders, layout)
        assert lane.counts.shape == (lanes, structure.places)
        assert lane.rates.shape == lane.fired.shape == (lanes, 2 * structure.steps)
        after, events = jax.eval_shape(program.advance, lane, layout)
        assert events.channel.shape == (structure.chunk, lanes)
        assert after.status.shape == (lanes,)
    # Planted: a convention changed selects another program.
    other = spec(measure="multinomial_less_one", last="extinct", catalysis=False)
    assert model.structure(other) != structure


def test_the_bundle_declares_every_array_the_runner_writes():
    rows = {
        "row_time", "row_event", "row_kind", "place_count", "reservoir_supplied",
        "channel_fired", "event_heat_kT", "reservoir_work_kT", "free_energy_kT",
        "ledger_residual_kT",
    }  # fmt: skip
    written = rows | {"event_time", "event_channel", "event_uniforms"}
    assert set(records.RECORDS) == written
    for entry in records.RECORDS.values():
        assert entry["base"] in records.BASES and entry["unit"]
    assert records.ROW_LEGEND == {"0": "start", "1": "periodic", "2": "end", "3": "observed"}
    assert runner.ROW_KINDS == ("start", "periodic", "end", "observed")
