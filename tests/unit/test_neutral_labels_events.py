"""FR-42's replacement event report (D296; erratum E, docs/TEMPLATED_POLYMERISATION_LAWS.md
§9.18) as one compiled engine row: what leaves at a replacement is recorded by label (FR-38's
step 5).

One world compiled once (about 35 s on a light CPU; the owner's event update and the composite's
event line run only in a compiled composition, which the NumPy rows in
tests/unit/test_neutral_arrival_labels.py do not reach). Two cells; replacement@1 swaps cell_0's
occupant for a template at 2 ms, and cell_1 keeps its own. S is labelled base, old and newcomer:
cell_0 starts a quarter base and three quarters old, cell_1 all old, and every arrival joins
newcomer from 2 ms. Nothing moves S between nodes, so its shares change only at the event.
- Before the event the record is zero. From the step that leaves 2 ms, cell_0's record is its S
  just before the event times those shares, a quarter base and three quarters old, and it stays
  there (cumulative, one event). cell_1's stays zero.
- After the event cell_0's S is the template's, all newcomer, and cell_1 keeps its shares bit for
  bit.
"""

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from validation.tissue import secreted_species_fixtures as fx

LAW = "neutral_arrival_labels@1"
DT, END, EVENT = 1e-3, 4e-3, 2e-3
SHARES = {"cell_0": {"base": 0.25, "old": 0.75}, "cell_1": {"old": 1.0}}


def replaced_world():
    """The module docstring's world: two 1 pL cells at 1 mM S, cell_0 replaced at 2 ms by a template
    at 2 mM, every millisecond observed."""
    raw = fx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        faces=(),
        concentrations_mM={"cell_0": 1.0, "cell_1": 1.0},
        dt=DT,
        end=END,
        observation_times=fx.grid_times(END, DT, DT),
    )
    template = fx.template(raw, "cell_0", "fresh", s_mM=2.0)
    raw = fx.with_replacement(raw, [template], [(EVENT, "cell_0", "fresh", "carrier_1")])
    raw["model"]["operators"].append(
        dict(
            law=LAW,
            species=[
                dict(
                    id="S",
                    labels=["base", "old", "newcomer"],
                    initial=[dict(node=n, shares=dict(s)) for n, s in SHARES.items()],
                )
            ],
        )
    )
    raw["experiment"]["label_arrivals"] = [
        dict(species="S", schedule=[dict(time=EVENT, label="newcomer")])
    ]
    return raw


def test_a_replacement_records_what_left_by_label():
    """The record (label_removed_fmol [labelled species, label, cell]) and the shares at every
    observed millisecond (module docstring), from the compiled run's own observations."""
    spec = parse_spec(replaced_world())
    result = run(spec)
    obs = result.observations
    times = np.asarray(spec.experiment.observation_times)
    s = list(spec.model.species_ids).index("S")
    amount = np.asarray(obs.amount)[:, s, :]  # [time, cell]
    record = np.asarray(obs.label_removed_fmol)[:, 0]  # [time, label, cell]
    share = np.asarray(obs.label_share)[:, 0]
    before, after = times <= EVENT + 1e-12, times > EVENT + 1e-12
    assert before.sum() == 3 and after.sum() == 2  # 0, 1 and 2 ms; 3 and 4 ms.
    assert np.all(record[before] == 0.0)
    leaving = amount[before][-1, 0]  # cell_0's S just before the event: its 1 fmol.
    assert leaving == pytest.approx(1.0, rel=1e-15)
    for row in record[after]:
        assert row[:, 0].tolist() == [leaving * 0.25, leaving * 0.75, 0.0]
        assert np.all(row[:, 1] == 0.0)  # cell_1 was not replaced.
    assert amount[after][0, 0] == pytest.approx(2.0, rel=1e-15)  # The template's S.
    assert np.all(share[after][:, :, 0] == [0.0, 0.0, 1.0])  # Newcomer material only.
    kept = np.tile([0.0, 1.0, 0.0], (len(times), 1))  # cell_1's shares, bit for bit.
    assert np.asarray(share)[:, :, 1].tobytes() == kept.tobytes()
    assert np.asarray(obs.label_pool_removed_fmol).size == 0  # No pool reporter: zero-size.


# ------------------------------------------------------------------ amendment G: derived producers


def chase(kind):
    """FR-38's step-5 world (validation/gene_regulation/replace_restart.py), its producer declared
    `producers` and derived (amendment G), or hand-written correctly in the derivation's own
    convention: each generation's label, then its window's, and the source's schedule."""
    from cells.operators import species_labels as labels
    from validation.gene_regulation import replace_restart as rr

    raw = rr.chase_world()
    owner = next(o for o in raw["model"]["operators"] if o["law"] == labels.LAW_ID)
    arrivals = raw["experiment"]["label_arrivals"]
    g0, g1 = rr.G0, rr.G1
    if kind == "derived":
        window = {"label": "cohort", "from": 0.0, "to": rr.W}
        for entry in owner["species"]:
            entry.update(labels=["base"], producers=[dict(source=rr.CHAIN, windows=[window])])
        raw["experiment"]["label_arrivals"] = [e for e in arrivals if "source" not in e]
        return raw
    for entry in owner["species"]:
        entry["labels"] = ["base", g0, f"{g0}-cohort", g1, f"{g1}-cohort"]
    (own,) = (e for e in arrivals if e.get("source") == rr.CHAIN)
    own["schedule"] = [
        dict(time=0.0, label=f"{g0}-cohort"), dict(time=rr.W, label=g0), dict(time=rr.T_E, label=g1)
    ]  # fmt: skip
    return raw


def test_derived_producer_labels_are_a_correct_hand_written_declaration_bit_for_bit():
    """Amendment G (TEMPLATED_POLYMERISATION_LAWS §9.20, option (a); D307), host side, no compile:
    on the step-5 world the owner derives transcription's producer labels, cell_0-g<k>-tx and
    their cohort window's, and its source's schedule from replacement@1's occupants. The derived
    definition binds to the hand-written one's types, initial state, layout and every control
    array bit for bit, so the programs that run are unchanged. A definition round trip writes the
    declared producers back, not the labels, and derives the same again (a resume reads the
    definition)."""
    import copy

    from cells.definitions import pump_composite_spec as cs
    from cells.operators import species_labels as labels
    from cells.registry.models import get_model

    bound = {}
    for kind in ("derived", "hand-written"):
        spec = parse_spec(chase(kind))
        model = get_model(spec.model)
        state, p = model.initial_values(spec)
        controls = cs.control_values(spec, np.asarray(spec.experiment.observation_times))
        bound[kind] = (spec, state, p, controls)
    (spec, *mine), (_, *theirs) = bound.values()
    for a, b in zip(mine, theirs, strict=True):
        assert type(a)._fields == type(b)._fields
        pairs = zip(a, b, strict=True)
        assert all(np.asarray(x).tobytes() == np.asarray(y).tobytes() for x, y in pairs)
    owner = next(d for op, d, _ in cs.entries(spec) if op.LABEL_OWNER)
    expanded, schedules = labels.derived(spec, owner)
    assert expanded.species[0].labels == (
        "base", "cell_0-g0-tx", "cell_0-g0-tx-cohort", "cell_0-g1-tx", "cell_0-g1-tx-cohort"
    )  # fmt: skip
    own = ((0.0, "cell_0-g0-tx-cohort"), (1200.0, "cell_0-g0-tx"), (3000.0, "cell_0-g1-tx"))
    assert schedules == ((("R", "tx"), own),)  # Transcription's: its source is R's (label_sources).
    again = parse_spec(copy.deepcopy(spec.to_dict()))
    declared = next(d for op, d, _ in cs.entries(again) if op.LABEL_OWNER)
    assert declared == owner and labels.derived(again, declared) == (expanded, schedules)
    assert "producers" in spec.to_dict()["model"]["operators"][-1]["species"][0]


def test_derived_producer_labels_follow_cell_ids_and_events_not_the_cells_order(monkeypatch):
    """Amendment G, the requester's identity (cell, generation, chain) across cell reordering: two
    producer cells, one replaced twice. Listing the cells and their chains in the other order
    derives the same labels and schedules, named by cell ID and numbered by event order (planted
    occupants and sources, no world)."""
    from types import SimpleNamespace

    from cells.operators import species_common
    from cells.operators import species_labels as labels

    def life(cell, births):
        return tuple(species_common.Occupant(cell, b, 0.0, "newcomer", None, None) for b in births)

    lives = {"cell_a": life("cell_a", (0.0, 2.0, 5.0)), "cell_b": life("cell_b", (0.0,))}
    chains = (("tx_a", "R", "cell_a"), ("tx_b", "R", "cell_b"))
    entry = labels.Labelled(
        "R", ("base",), (), (("tx_a", (("pulse", 1.0, 3.0),)), ("tx_b", ()))
    )  # fmt: skip
    declaration = labels.Labels(labels.LAW_ID, (entry,))
    spec = SimpleNamespace(experiment=SimpleNamespace(end_time=8.0))
    out = []
    for order in (1, -1):
        source = SimpleNamespace(label_sources=lambda d, o=order: chains[::o])
        monkeypatch.setattr(labels, "reporters", lambda s, flag, r=source: ((r, None),))
        reordered = dict(list(lives.items())[::order])
        monkeypatch.setattr(species_common, "occupants", lambda s, r=reordered: r)
        out.append(labels.derived(spec, declaration))
    assert out[0] == out[1]
    expanded, schedules = out[0]
    assert expanded.species[0].labels == (
        "base", "cell_a-g0-tx_a", "cell_a-g0-tx_a-pulse", "cell_a-g1-tx_a", "cell_a-g1-tx_a-pulse",
        "cell_a-g2-tx_a", "cell_a-g2-tx_a-pulse", "cell_b-g0-tx_b",
    )  # fmt: skip
    assert dict(schedules)[("R", "tx_a")] == (
        (0.0, "cell_a-g0-tx_a"), (1.0, "cell_a-g0-tx_a-pulse"), (2.0, "cell_a-g1-tx_a-pulse"),
        (3.0, "cell_a-g1-tx_a"), (5.0, "cell_a-g2-tx_a"),
    )  # fmt: skip
    assert dict(schedules)[("R", "tx_b")] == ((0.0, "cell_b-g0-tx_b"),)


def test_a_batch_of_producer_worlds_is_refused():
    """Amendment G's batch limit, fail-closed: a producer world's label count follows its cells'
    replacement events, which the batch's signature check cannot read, so version 1 batches it with
    no other world. Two members whose producer cells see one and two events are refused by the
    batch's own check, and so are two identical members; a batch of one parses (parses only)."""
    from cells.definitions.specs import ConfigError
    from cells.execution.batch import parse_batch
    from validation.gene_regulation import replace_restart as rr

    def batch(*worlds):
        return dict(
            schema_version=1, kind="independent_worlds",
            worlds=[dict(world_id=k, simulation=w) for k, w in enumerate(worlds, start=1)],
            execution=dict(mapping="lax_map", max_worlds=8, max_padded_steps=10**6,
                           max_working_bytes=2**40),
        )  # fmt: skip

    twice = chase("derived")
    events = twice["experiment"]["replacement_events"]
    events.append(dict(events[0], time=rr.T_C, carrier_id=f"{events[0]['carrier_id']}_2"))
    for pair in ((chase("derived"), twice), (chase("derived"), chase("derived"))):
        with pytest.raises(ConfigError, match="matching model array axes"):
            parse_batch(batch(*pair))
    parse_batch(batch(chase("derived")))
