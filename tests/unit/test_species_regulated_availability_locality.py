"""cells.operator.species_regulated_availability@1, A6: locality, with the criterion written before any run.

docs/INVENTORY_COUPLING_DESIGN.md §4.4 A6 (inventory-coupling-m2-20261114-01/HANDOFF.md). Two cells
of the heredity sheet that no junction joins (regulated_availability_fixtures.apart: cell_0 and
cell_4, each on its own held bath with its Kir and NaV populations and pump), 20 steps at 1 ms. R is
cleared in cell_0 by D150's turnover and read there by a state, whose fraction sets cell_0's Kir
population (kir_0); a neutral Q is declared too. One program; the arms are data:
* (i) the operator's locality: with the coupling on against off, every control of every element
  but kir_0 is bitwise unchanged at every saved row (and kir_0's is not); perturbing Q leaves every
  factor bitwise unchanged; the operator writes no species row (R's and Q's rows are bitwise equal
  with the coupling on and off);
* (ii) the engine's locality: cell_4's whole trajectory (every @3 state field restricted to its
  cell, membrane, bath and channel populations) is bitwise unchanged with the coupling on against
  off. If (ii) fails while (i) holds, a shared solve couples the components: that is reported, and
  nothing shared is edited (the stop rule).
"""

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.models import pump_composite_adapter as adapter
from validation.tissue import regulated_availability_fixtures as rf

A, B = "cell_0", "cell_4"
TARGET = "kir_0"
CONTROLS = (
    "membrane_availability",
    "junction_availability",
    "channel_availability",
    "pump_availability",
    "calcium_pump_availability",
)
_cache = {}


def go(on=True, q_mM=1e-3):
    key = (on, q_mM)
    if key not in _cache:
        raw = rf.apart({A, B}, extra=[("Q", q_mM)])
        raw = rf.with_coupling(
            raw,
            species=[rf.REGULATOR],
            states=[
                rf.state(
                    "s",
                    [A],
                    [("hill_activation", rf.REGULATOR, 1e-3, 1.0)],
                    on=5.0,
                    off=1.0,
                    initial=0.2,
                )
            ],
            couplings=[rf.coupling("c", "channel", [TARGET], ("state", "s"), "state_fraction")],
            switches={"c": [(0.0, int(on))]},
        )
        spec = parse_spec(rf.with_turnover(raw, A, 50.0))
        _cache[key] = (spec, run(spec))
    return _cache[key]


def column(result, name):
    return np.asarray(getattr(result.observations, name))


def test_i_the_operators_locality():
    spec, on = go(True)
    _, off = go(False)
    _, perturbed = go(True, q_mM=2e-3)
    channels = [c.id for c in spec.model.channels]
    k = channels.index(TARGET)
    for name in CONTROLS:
        a, b = column(on, name), column(off, name)
        if name == "channel_availability":
            assert not np.array_equal(a[:, k], b[:, k])  # The target is regulated.
            a, b = np.delete(a, k, axis=1), np.delete(b, k, axis=1)
        assert a.tobytes() == b.tobytes(), name
    assert column(on, "coupling_factor").tobytes() == column(perturbed, "coupling_factor").tobytes()
    species = list(spec.model.species_ids)
    for name in (rf.REGULATOR, "Q"):
        row = species.index(name)
        a = np.asarray(on.history.amount_increment)[:, row]
        b = np.asarray(off.history.amount_increment)[:, row]
        assert a.tobytes() == b.tobytes(), name


def restricted(spec, history, cell):
    """Every @3 state field of `history` restricted to `cell`'s entities, by field axis."""
    m = spec.model
    membranes = [i for i, p in enumerate(m.membranes) if p.inside == cell]
    ids = {m.membranes[i].id for i in membranes}
    outside = sorted(
        {
            j
            for i in membranes
            for j, o in enumerate(m.extracellular)
            if o.id == m.membranes[i].outside
        }
    )
    channels = [i for i, c in enumerate(m.channels) if c.membrane_id in ids]
    slots = dict(
        cell_slot=[[c.id for c in m.cells].index(cell)],
        extracellular_slot=outside,
        membrane_slot=membranes,
        channel_slot=channels,
        edge_slot=[],
        face_slot=[],
    )
    out = {}
    for name, axes in adapter.STATE_AXES.items():
        value = np.asarray(getattr(history, name))
        for axis, label in enumerate(axes, start=1):
            if label in slots:
                value = np.take(value, slots[label], axis=axis)
        out[name] = value
    return out


def test_ii_the_engines_locality():
    spec, on = go(True)
    _, off = go(False)
    a, b = restricted(spec, on.history, B), restricted(spec, off.history, B)
    differing = [name for name in a if a[name].tobytes() != b[name].tobytes()]
    assert not differing, differing
    near = restricted(spec, on.history, A)
    far = restricted(spec, off.history, A)
    assert any(near[n].tobytes() != far[n].tobytes() for n in near)  # cell_0 is moved.


def test_the_cells_share_no_junction_face_or_bath():
    spec, _ = go(True)
    assert not spec.model.junctions and not spec.model.faces
    assert len({p.outside for p in spec.model.membranes}) == 2
