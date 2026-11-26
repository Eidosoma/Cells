"""cells.operator.species_regulated_availability@1: the 1 ms errors of A4 and A5 against their references, pinned.

docs/INVENTORY_COUPLING_DESIGN.md §10. A regression guard, not a qualification (the lead's ruling,
14 November 2026): the protocol's `regression_pins_1ms` (validation/tissue/
regulated_availability_protocol.json), twice the development error at 1 ms, at least 100 floors
and 1e-13 for dimensionless quantities. Two compiled programs (A4's and A5's coupled worlds at
1 ms) against validation/coupling's R-feedback and R-cell (through REFERENCES_USAGE.md's API).
"""

import json
from pathlib import Path

import pytest

from validation.coupling import cells_reference as rc
from validation.tissue import regulated_availability_dt_study as generator
from validation.tissue import regulated_availability_references as rr

PROTOCOL = json.loads(
    (Path(generator.__file__).with_name("regulated_availability_protocol.json")).read_text()
)
PINS = PROTOCOL["regression_pins_1ms"]["pins"]


@pytest.mark.parametrize("world", ["a4", "a5"])
def test_the_1ms_errors_stay_within_their_pins(world):
    make, spec_ = (
        (generator.a4_world(), generator.A4) if world == "a4" else (rr.cell_world, generator.A5)
    )
    w = make()
    record = tuple(generator.grid_records(spec_["end"], spec_["every"], generator.DTS[0]))
    reference = rc.simulate(w, spec_["end"], record=record)
    initial = {
        c: (reference.initial[c]["V"], reference.initial[c]["background_fmol"]) for c in w.cells
    }
    engine, info = generator.engine_run(
        w, dt=generator.DTS[0], end=spec_["end"], every=spec_["every"], initial=initial
    )
    errors = generator.record_errors(w, engine, reference, record, reference.slots)
    assert info["gate_held_at_1"]
    over = {
        x: (max(v), PINS[f"{world}.coupled.{x}"])
        for x, v in errors.items()
        if f"{world}.coupled.{x}" in PINS and max(v) > PINS[f"{world}.coupled.{x}"]
    }
    assert not over, over
