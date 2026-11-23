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
