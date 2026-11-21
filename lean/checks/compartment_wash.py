"""Compare finite-well wash events with an independent inventory and dilution calculation."""

import json
import math
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec as composite
from cells.definitions.specs import parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.operators import site_occupancy, wash_schedule
from cells.registry.models import get_model
from validation.tissue import wash_schedule_fixtures as well


def prepared(fractions, free, volume, buffer, *, sites):
    dt = 1 / 64
    raw = well.well(free=free, volume=volume, sites=sites, dt=dt, end=(len(fractions) + 2) * dt)
    times = [(i + 1) * dt for i in range(len(fractions))]
    events = [(t, "well", f, {well.TRACER: buffer}) for f, t in zip(fractions, times, strict=True)]
    return parse_spec(well.with_wash(raw, ["well"], events)), times


def exchanges(fractions):
    free, volume, buffer = 60.0, well.V_WELL, well.TRACE_mM
    spec, times = prepared(fractions, free, volume, buffer, sites=True)
    model = get_model(spec.model)
    initial, p = model.initial_values(spec)
    state = initial
    op = next(op for op in model.events if op.LAW_ID == wash_schedule.LAW_ID)
    event = jax.jit(lambda row, ctrl: op.event(row, ctrl, p, xp=jnp))
    s = spec.model.species_ids.index(well.TRACER)
    w = [node.id for node in spec.model.extracellular].index("well")
    ions = np.array(spec.model.valence) != 0
    target = buffer * volume
    sample = supply = 0.0
    retained = 1.0
    errors = []
    for t, f in zip(times, fractions, strict=True):
        control = model.CONTROL_TYPE(*(v[0] for v in composite.control_values(spec, [t])))
        before = target + retained * (free - target)
        sample += f * before
        supply += f * target
        retained *= 1 - f
        state, valid = event(state, control)
        assert bool(valid)
        amount = float(p.extracellular_amount_reference[s, w] + state.extracellular_amount_increment[s, w])
        expected = target + retained * (free - target)
        errors.extend((abs(amount - expected), abs(float(state.wash_collected_fmol[s, w]) - sample),
                       abs(float(state.wash_supplied_fmol[s, w]) - supply),
                       abs(amount + sample - supply - free)))
        np.testing.assert_array_equal(state.wash_collected_fmol[ions, w], state.wash_supplied_fmol[ions, w])
        np.testing.assert_array_equal(state.extracellular_amount_increment[ions, w],
                                      initial.extracellular_amount_increment[ions, w])
        for field in site_occupancy.STATE_AXES:
            np.testing.assert_array_equal(getattr(state, field), getattr(initial, field))
        heat = float(state.wash_last_mixing_heat_pJ[w])
        assert heat == 0.0 if f == 1 else math.isfinite(heat) and heat >= 0
    assert max(errors) <= 8 * np.spacing(free)
    return dict(fractions=fractions, final_free_fmol=amount, collected_fmol=sample,
                supplied_fmol=supply, max_amount_error_fmol=max(errors))


def whole_wash(exponent):
    # Exactly representable binary values probe the host's documented anchor limit.
    free, volume = 64.0, float(2**20)
    buffer = math.ldexp(free / volume, -exponent)
    spec, _ = prepared([1.0], free, volume, buffer, sites=False)
    s = spec.model.species_ids.index(well.TRACER)
    w = [node.id for node in spec.model.extracellular].index("well")
    expected = volume * buffer
    row = dict(initial_fmol=free, target_fmol=expected, initial_to_target=2**exponent)
    try:
        result = run(spec)
    except NumericalError as exc:
        if exponent != 60:
            raise
        return dict(row, completed=False, refusal=str(exc))
    actual = float(free + result.history.extracellular_amount_increment[-1, s, w])
    assert actual == expected
    return dict(row, completed=True, stored_fmol=actual)


def dilution_data():
    data = json.loads(Path(__file__).with_name("data").joinpath("vloemans2024_dilution.json").read_text())
    rows = []
    for case in data["single_exchange"] + data["repeated_exchange"]:
        f, measured = case["fraction"], case["measured"]
        prediction = [measured[0] * (1 - f) ** i for i in range(len(measured))]
        rows.append(dict(fraction=f, measured=measured, predicted=prediction))
    return rows


if __name__ == "__main__":
    assert jax.config.x64_enabled and jax.default_backend() == "cpu"
    report = dict(compiled_events=[exchanges(fs) for fs in ([0.5, 0.25], [0.8] * 3, [0.9] * 3, [1.0])],
                  whole_wash_runs=[whole_wash(e) for e in (1, 50, 60)],
                  fluorescein_ug_per_mL=dilution_data())
    print(json.dumps(report, indent=2, allow_nan=False))
