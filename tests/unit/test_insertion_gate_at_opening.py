"""insertion@2's gate at opening (docs/INNER_MODEL_V4_DESIGN.md §7.4 (o); the lead's ruling of 16
November 2026: option 1).

A gated population planted on the cleft cell's onset furrow (membrane_insertion_v2.check_onsets'
refusal lifted in this test only; it stays in the engine). On the host, at the operator's event:
- when the furrow opens, the population's gate is its declared initial gate, however far the
  padding's gate drifted while the patch was closed: onset early and late;
- before the onset the event leaves every gate as it is, and populations off the onset patch keep
  theirs at the onset;
- in a world of today's (no population on an onset patch) the write is idle: the onset mask is all
  false, and any gate passes through the onset unchanged.
"""

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.operators import membrane_insertion as v1
from cells.operators import membrane_insertion_v2 as v2
from cells.registry.models import get_model
from tests import membrane_insertion_fixtures as ifx
from tests.unit.test_membrane_insertion_v2 import as_v2, control_at, operator

DECLARED = [0.25, 0.75]  # Kv1.5's (m, h) as declared.
DRIFTED = [0.9, 0.05]  # What the padding's code-0 gate could hold after any closed time.


def lifted(base, schedule):
    """check_onsets without its channel refusal (this test only): the other onset rules kept."""
    m = base.model
    patches, nodes, _ = v1.onset_entities(base, schedule)
    for p in m.membranes:
        if p.id in patches and (p.pump is not None or p.calcium_pump is not None):
            raise ConfigError("Pumps on an onset patch are later work")
    for node in m.extracellular:
        if node.id in nodes and (node.reservoir or node.initial_charge_C != 0.0):
            raise ConfigError("An onset node is finite, with a zero charge anchor")


def cleft(onset, *, planted=True):
    raw = as_v2(ifx.with_operators(ifx.cleft_cell(), ifx.furrow_insertion(onset=onset)))
    if planted:
        m, e, x = raw["model"], raw["experiment"], raw["execution"]
        m["channels"].append(
            dict(
                id="furrow_kv",
                membrane_id="furrow",
                kinetic_law="cells.channel.kv1p5_mh@1",
                max_permeability_m_per_s=1e-9,
                abundance=1.0,
                initial_gate=DECLARED,
                permeant_ions=[dict(species_id="K", relative_permeability=1.0)],
            )
        )
        e["channel_controls"].append(
            dict(channel_id="furrow_kv", schedule=[dict(time=0.0, availability=1.0)])
        )
        x["channel_capacity"] = len(m["channels"])
        state = next(op for op in m["operators"] if op["law"] == ifx.STATE)
        state["populations"].append(
            dict(
                channel_id="furrow_kv",
                functional_unit="furrow",
                catalogue=None,
                reference_density_per_m2=ifx.DENSITY,
            )
        )
    return raw


def bound(raw):
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    return spec, model, state, p


def drifted(state, columns):
    gate = np.array(state.channel_gate, copy=True)
    for k in columns:
        gate[:2, k] = DRIFTED
    return state._replace(channel_gate=gate)


def test_the_refusal_stays_in_the_engine():
    with pytest.raises(ConfigError, match="Channel populations on an onset patch"):
        parse_spec(cleft(0.002))


@pytest.mark.parametrize("onset", [0.001, 0.003])  # Early and late in the 6 ms world.
def test_a_population_on_an_onset_patch_starts_at_its_declared_gate(monkeypatch, onset):
    monkeypatch.setattr(v2, "check_onsets", lifted)
    spec, model, state, p = bound(cleft(onset))
    channels = [c.id for c in spec.model.channels]
    k = channels.index("furrow_kv")
    assert bool(p.insertion_onset_channel[k]) and list(p.insertion_onset_gate[:2, k]) == DECLARED
    assert not np.asarray(p.insertion_onset_channel)[
        [j for j in range(len(channels)) if j != k]
    ].any()
    op, start = operator(model, v2.LAW_ID), drifted(state, range(len(channels)))
    before, ok = op.event(start, control_at(spec, model, onset - 0.001), p, xp=np)
    assert ok and np.array_equal(before.channel_gate, start.channel_gate)  # Not yet open.
    after, ok = op.event(start, control_at(spec, model, onset), p, xp=np)
    assert ok and after.insertion_opened[[m.id for m in spec.model.membranes].index("furrow")]
    assert list(after.channel_gate[:2, k]) == DECLARED  # Whatever it drifted to while closed.
    others = [j for j in range(len(channels)) if j != k]
    assert np.array_equal(after.channel_gate[:, others], start.channel_gate[:, others])


def test_in_a_world_of_todays_the_write_is_idle():
    spec, model, state, p = bound(cleft(0.002, planted=False))
    assert not np.asarray(p.insertion_onset_channel).any()
    assert not np.asarray(p.insertion_onset_gate).any()
    start = drifted(state, range(len(spec.model.channels)))
    after, ok = operator(model, v2.LAW_ID).event(start, control_at(spec, model, 0.002), p, xp=np)
    assert ok and np.array_equal(after.channel_gate, start.channel_gate)
