"""Worlds and planted declarations for the run view's tests (cells/records/run_view.py).

The worked example's world, short: one cell secreting S into a finite node that leaks to its held
bath (validation/tissue/secreted_species_fixtures; cells.operator.scheduled_species_turnover@1 and
cells.operator.scheduled_species_exchange@1). Declarations an operator does not carry yet are planted for a
test's duration only (plant), never in a source file: the secretion world's (declare_secretion)
and S5's partition world's (declare_division: the membrane state and the partition).
"""

import json

import numpy as np

from cells.definitions.specs import parse_spec
from cells.models import pump_composite
from cells.operators import OPERATORS
from cells.records import run_view
from validation.tissue import secreted_species_fixtures as fx

DT = 1e-3
TURNOVER = "cells.operator.scheduled_species_turnover@1"
EXCHANGE = "cells.operator.scheduled_species_exchange@1"
PARTITION = "cells.operator.isopotential_partition@1"
STATE = "cells.operator.membrane_entity_state@1"
INJECTION = "cells.operator.electrode_current_injection@1"
# A 3 M KCl filling's proportion, with M as the heredity world's anion (as
# tests/unit/test_current_injection_runs.py declares it).
CARRIERS = {"K": 0.4912, "M": 0.5088}


def reference_constants():
    """The constants a view adds for the inner model's increments (@3's RECORD_REFERENCES)
    whose fixed references no view field states already (run_view.VIEW_FIELD_AXES)."""
    from cells.models import surface_pump_v3 as tissue3

    return set(tissue3.RECORD_REFERENCES.values()) - set(run_view.VIEW_FIELD_AXES)


def secretion(end=0.01, every=0.002, produce=1e-4, **world):
    """The worked example's world (a cell secretes S into a node that leaks to its bath), short:
    by default 10 steps and six observations (0 to 10 ms, every 2 ms)."""
    builder = fx.world if world else fx.secreting_cell
    raw = builder(
        end=end, dt=DT, solver=fx.IMEX, observation_times=fx.grid_times(end, DT, every), **world
    )
    cell = (world.get("cells") or (("cell_0", 1.0),))[0][0]
    raw = fx.with_turnover(
        raw,
        [("produce", cell, "production"), ("clear", "ecs_0", "clearance")],
        [("produce", cell, [(0.0, produce)]), ("clear", None, [(0.0, 0.5)])],
    )
    raw = fx.with_exchange(
        raw,
        [
            ("secrete", "contact_0", "export", "first_order"),
            ("sink", "contact_0", "import", "saturable"),
        ],
        [("secrete", cell, [(0.0, 0.1)]), ("sink", cell, [(0.0, 1e6, 5e-4)])],
    )
    return parse_spec(raw)


def injection_world(currents, *, end=0.004, every=None):
    """One heredity cell facing its held bath, with an electrode in it
    (tests/unit/test_current_injection_runs.py's world): currents ((step, current_A), ...), each
    change at an exact step; observed at 0 and the end, or every `every` seconds."""
    from cells.definitions import pump_composite_spec as cs
    from validation.tissue import pump_water_fixtures as water

    base = water.heredity_cell("H", dt=DT, end_time=end)
    base["experiment"]["observation_times"] = (
        [0.0, end] if every is None else fx.grid_times(end, DT, every)
    )
    raw = cs.frozen_definition(base)
    cell = raw["model"]["cells"][0]["id"]
    raw["model"]["operators"] = [
        dict(law=INJECTION, electrodes=[dict(cell_id=cell, carriers=dict(CARRIERS))])
    ]
    raw["experiment"]["injection_controls"] = [
        dict(cell_id=cell, schedule=[dict(time=k * DT, current_A=i) for k, i in currents])
    ]
    return raw


def plant(patch, law, **declarations):
    """Set declarations on a registered operator's class through a MonkeyPatch."""
    for name, value in declarations.items():
        patch.setattr(type(OPERATORS[law]), name, value, raising=False)


def layers(layer_id, label, representation="prescribed"):
    return (dict(id=layer_id, label=label, representation=representation),)


def declare_secretion(patch):
    """Turnover's and exchange's layers, as their files declare them (with the rest of their run
    view's declarations), kept here so a test states what it relies on; and no engine source, so
    a view reads the same from a checkout and from a frozen snapshot (run_view._engine_source)."""
    plant(patch, TURNOVER, VIEW_LAYERS=layers("turnover", "Species turnover"))
    plant(patch, EXCHANGE, VIEW_LAYERS=layers("exchange", "Species exchange"))
    patch.setattr(run_view, "_engine_source", lambda root=None: None)


def division_set(self, spec, declaration):
    """The partition's division axis as the view's set."""
    return {
        "division_slot": {
            "id": "division",
            "ids": tuple(d.id for d in declaration.divisions),
            "holds": "division",
        }
    }


def declare_division(patch):
    """The membrane state's and the partition's view declarations (S5's partition world), and no
    engine source (as declare_secretion)."""
    patch.setattr(run_view, "_engine_source", lambda root=None: None)
    plant(
        patch,
        STATE,
        VIEW_LAYERS=layers("membrane_state", "Membrane entity state", "simulated"),
        UNITS={"population_abundance_increment": "1", "population_units": "1"},
        OBSERVATION_AXES={
            "membrane_area_m2": ("membrane_slot",),
            "membrane_capacitance_F": ("membrane_slot",),
            "population_units": ("channel_slot",),
        },
    )
    plant(
        patch,
        PARTITION,
        VIEW_LAYERS=layers("division", "Cell division"),
        UNITS={"division_applied": "1", "partition_units_moved": "1", "partition_slot_phase": "1"},
        OBSERVATION_AXES={"partition_slot_phase": ("cell_slot",)},
        view_sets=division_set,
    )


def load(directory):
    return json.loads((directory / run_view.FILE).read_text())


def observed(directory, view, array, base="observation"):
    """(times, values) of an array on a time base (the observed rows by default), over the files
    its view names, in order."""
    base = next(b for b in view["time"]["bases"] if b["id"] == base)
    times, values = [], []
    for part in base["files"]:
        with np.load(directory / part["file"], allow_pickle=False) as saved:
            times.append(saved[base["array"]])
            values.append(saved[array])
    return np.concatenate(times), np.concatenate(values)


def capture(patch):
    """The views the host observer forms inside observe_history, in order: the composite's own
    view function, wrapped through a MonkeyPatch (door S's bitwise check)."""
    seen, inside = [], [False]
    observe = pump_composite.Composition.observe_history
    form = pump_composite.Composition.view

    def observing(self, *args, **kwargs):
        inside[0] = True
        try:
            return observe(self, *args, **kwargs)
        finally:
            inside[0] = False

    def viewing(self, p, state, **kwargs):
        q = form(self, p, state, **kwargs)
        if inside[0]:
            seen.append(q)
        return q

    patch.setattr(pump_composite.Composition, "observe_history", observing)
    patch.setattr(pump_composite.Composition, "view", viewing)
    return seen


def same_as_observed(directory, view, seen):
    """Each merged-view record of a saved run equals, bitwise and in dtype, the views the observer
    formed (capture), row by row; the number of records checked."""
    records = [r for r in view["records"] if r["id"].startswith(run_view.VIEW_PREFIX)]
    for record in records:
        _, values = observed(directory, view, record["array"])
        expected = np.stack([np.asarray(getattr(q, record["field"])) for q in seen])
        assert values.dtype == expected.dtype, record["id"]
        assert np.array_equal(values, expected), record["id"]
    return len(records)
