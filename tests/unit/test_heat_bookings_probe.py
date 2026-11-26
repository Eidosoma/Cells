"""Seam D's booking probe (CORE_SEAMS_STEP0 §5.1, confirmed in §6.1; CORE_SEAMS_DESIGN §6.1-6.2).

A heredity cell with a K+ and a Na+ leak starts 15 mV below E_K and relaxes through it. Under
ARS(2,2,2) the tableau books a negative K+ heat increment on the step that crosses, which the
dissipation check refuses, at dt G/C = 0.03. With `heat_bookings: {"channels":
"cells.heat.trapezoid_nonnegative@1"}` the same run is admitted with every channel heat element
non-decreasing; the control arm is admitted under both. The planted error, the tableau's weights
left in a class declared trapezoid, must again fail the dissipation check. Water@1, whose
composition carries the structure, books the pick too.
"""

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.models import surface_pump_v3
from cells.registry.models import get_model
from tests.unit.test_heat_bookings import (
    CONTROL,
    CROSSED_STEPS,
    CROSSING,
    DISSIPATION_REFUSAL,
    TRAPEZOID,
    _clear_compiled,
    probe_world,
)
from validation.tissue import pump_water_fixtures as wfx


def test_the_tableau_refuses_the_crossing_and_the_trapezoid_admits_it():
    with pytest.raises(NumericalError, match=DISSIPATION_REFUSAL):
        run(parse_spec(probe_world(CROSSING, steps=CROSSED_STEPS)))
    spec = parse_spec(probe_world(CROSSING, bookings={"channels": TRAPEZOID}, steps=CROSSED_STEPS))
    assert spec.model.heat_bookings == (("channels", TRAPEZOID),)
    result = run(spec)
    heat = np.asarray(result.history.channel_dissipated_energy_pJ)
    assert np.all(np.diff(heat, axis=0) >= 0) and np.all(heat >= 0)
    for bookings in (None, {"channels": TRAPEZOID}):  # The control is admitted either way.
        run(parse_spec(probe_world(CONTROL, bookings=bookings, steps=CROSSED_STEPS)))


def test_the_planted_tableau_weights_in_a_trapezoid_class_fail_the_dissipation_check(monkeypatch):
    _clear_compiled()
    monkeypatch.setattr(surface_pump_v3, "trapezoid_fields", lambda structure: ())
    try:
        spec = parse_spec(
            probe_world(CROSSING, bookings={"channels": TRAPEZOID}, steps=CROSSED_STEPS)
        )
        with pytest.raises(NumericalError, match=DISSIPATION_REFUSAL):
            run(spec)
    finally:
        monkeypatch.undo()
        _clear_compiled()


def test_the_water_family_books_through_its_compositions_structure():
    """Water@1 runs @3 through a composition whose inner carries the structure, picks included,
    so the family books what the definition picks: the probe's crossing, refused by the tableau,
    is admitted under the trapezoid there too."""
    with pytest.raises(NumericalError, match=DISSIPATION_REFUSAL):
        run(parse_spec(wfx.with_water(probe_world(CROSSING, steps=CROSSED_STEPS))))
    spec = parse_spec(
        wfx.with_water(probe_world(CROSSING, bookings={"channels": TRAPEZOID}, steps=CROSSED_STEPS))
    )
    assert spec.model.heat_bookings == (("channels", TRAPEZOID),)
    assert (
        get_model(spec.model).composition.inner.structure.heat_bookings == spec.model.heat_bookings
    )
    heat = np.asarray(run(spec).history.channel_dissipated_energy_pJ)
    assert np.all(np.diff(heat, axis=0) >= 0)
