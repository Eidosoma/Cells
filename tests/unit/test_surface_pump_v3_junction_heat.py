"""The opt-in trapezoid_nonnegative@1 junction-heat booking of resolved_pump_tissue@3.

ARS(2,2,2) books route heat with the explicit weights (delta, 1 - delta), delta < 0,
so a junction whose voltage crosses zero within a step books a negative heat
increment, which the strict dissipation row test refuses (heredity pilot W1: an
abrupt Na-leak cue in a heterogeneous tissue, a 5 ms sheet collapse). With the
option the step books dt (q_start + q_end) / 2 instead. Shown here on a two-cell
world (cell 0 0.12 mV below cell 1, a cue on cell 0 at 2 ms) and on the
eight-population fixture: the default definition, fingerprint and trajectory
are unchanged; with the option the trajectory is the default's bitwise and only
booked junction heat differs; the default's cue step is refused (host and device,
same message) and the option's accepted, its energy ledger within bound; and a
seeded wrong-signed junction booking still trips both checks at the same row.
"""

import jax
import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.specs import ConfigError, parse_spec
from cells.core.surface_pump_v3_spec import (
    DEFAULT_JUNCTION_HEAT,
    NALEAK_LAW_ID,
    TRAPEZOID_JUNCTION_HEAT,
    control_values,
)
from cells.core.vector_windows import WorldCheckError, run_vector_windowed
from cells.core.windows import WindowPolicy
from cells.models import surface_pump, surface_pump_v3
from cells.numerics import surface_imex as imex
from validation.stationary import worlds
from validation.tissue import surface_pump_v3_fixtures as fixtures

MODEL = surface_pump_v3
STEPS = 6  # Cue on at step 2: the third step books a negative tableau junction heat.
ROW = 4


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def pair_raw(booking=None):
    """Two heredity cells (own held baths), one open E07 junction, a cue on cell 0."""
    states = [fixtures.kicked(fixtures.HEREDITY_STATES["H"], -0.12), fixtures.HEREDITY_STATES["H"]]
    raw = worlds.e07_sheet_definition(
        [s[:4] for s in states], [(0, 1)], gated=False, dt=1e-3, end_time=STEPS * 1e-3
    )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    leak = 9 * m["membranes"][0]["permeability_m_per_s"]["Na"]
    m["channels"].append(fixtures.channel("cue_0", 0, NALEAK_LAW_ID, "Na", leak, 1.0, []))
    e["channel_controls"].append(
        dict(
            channel_id="cue_0",
            schedule=[dict(time=0.0, availability=0.0), dict(time=2e-3, availability=1.0)],
        )
    )
    x["channel_capacity"] = len(m["channels"])
    e["observation_times"] = [k * 1e-3 for k in range(STEPS + 1)]
    if booking is not None:
        m["junction_heat_booking"] = booking
    return raw


def fixture_raw(booking=None):
    raw = fixtures.definition("release", solver=imex.ARS222_ID)
    raw["experiment"]["end_time"] = 0.0012
    raw["experiment"]["observation_times"] = [0.0, 0.0007, 0.0012]
    if booking is not None:
        raw["model"]["junction_heat_booking"] = booking
    return raw


def stepped(spec):
    """Every accepted state of a run by the model's own checked step (no row checks)."""
    from cells.core.grid import EventGrid

    state, p = MODEL.initial_values(spec)
    grid = EventGrid(spec)
    times = [grid[i] for i in range(len(grid))]
    controls = control_values(spec, times[:-1])
    step = jax.jit(MODEL.checked_step)
    rows = [state]
    for k in range(len(times) - 1):
        control = type(controls)(*(np.asarray(v[k]) for v in controls))
        state, ok = step(state, times[k + 1] - times[k], control, p, p.active)
        assert bool(ok)
        rows.append(state)
    return MODEL.STATE_TYPE(
        *(np.stack([np.asarray(r[k]) for r in rows]) for k in range(len(state)))
    )


def test_default_definitions_keep_their_fingerprints_and_the_option_is_recorded():
    default = parse_spec(pair_raw())
    assert default.model.junction_heat_booking == DEFAULT_JUNCTION_HEAT
    assert "junction_heat_booking" not in default.to_dict()["model"]
    assert parse_spec(pair_raw(DEFAULT_JUNCTION_HEAT)).fingerprint == default.fingerprint
    option = parse_spec(pair_raw(TRAPEZOID_JUNCTION_HEAT))
    assert option.to_dict()["model"]["junction_heat_booking"] == TRAPEZOID_JUNCTION_HEAT
    assert parse_spec(option.to_dict()) == option and option.fingerprint != default.fingerprint
    _, layout = MODEL.initial_values(option)
    assert layout.junction_heat_trapezoid.shape == (1,)
    assert MODEL.initial_values(default)[1].junction_heat_trapezoid.shape == (0,)
    with pytest.raises(ConfigError, match="junction_heat_booking"):
        parse_spec(pair_raw("trapezoid"))
    rk4 = fixtures.definition("release", solver="rk4")
    rk4["model"]["junction_heat_booking"] = TRAPEZOID_JUNCTION_HEAT
    with pytest.raises(ConfigError, match="IMEX"):
        parse_spec(rk4)


@pytest.mark.parametrize("make", [pair_raw, fixture_raw])
def test_the_option_changes_booked_junction_heat_only_and_never_lowers_it(make):
    default, option = (stepped(parse_spec(make(b))) for b in (None, TRAPEZOID_JUNCTION_HEAT))
    for name, a, b in zip(MODEL.STATE_TYPE._fields, default, option, strict=True):
        if name != "junction_dissipated_energy_pJ":
            np.testing.assert_array_equal(a, b, err_msg=name)
    heat = option.junction_dissipated_energy_pJ
    assert np.all(np.diff(heat, axis=0) >= 0)
    if make is pair_raw:  # The default books a negative increment at the cue step.
        assert np.diff(default.junction_dissipated_energy_pJ, axis=0)[2, 0] < -1e-10
        assert np.all(np.diff(heat, axis=0)[:, 0] > 0)


def test_the_cue_step_is_refused_by_default_and_accepted_with_the_option():
    default, option = (parse_spec(pair_raw(b)) for b in (None, TRAPEZOID_JUNCTION_HEAT))
    with pytest.raises(NumericalError) as host:
        run(default)
    assert str(host.value) == surface_pump.DISSIPATION_MESSAGE
    policy = WindowPolicy(STEPS, "checkpoints")
    with pytest.raises(WorldCheckError) as device:
        run_vector_windowed(BatchSpec((WorldSpec(1, default),), 1, 10**6, 2**31), policy)
    assert device.value.checks == ("dissipation",)
    assert surface_pump.DISSIPATION_MESSAGE in str(device.value)
    value = run(option)  # Host-checked rows: the energy ledger within its bound.
    history = MODEL.STATE_TYPE(*(np.asarray(v) for v in value.history))
    _, p = MODEL.initial_values(option)
    energy = [float(MODEL.balances(MODEL.STATE_TYPE(*(v[j] for v in history)), p)["energy"])
              for j in range(len(history.amount_increment))]  # fmt: skip
    assert max(abs(e) for e in energy) <= 1e-6
    # The device-checked vectorized run accepts it too (its arithmetic is the scalar
    # run's up to XLA's rewrites: test_vector_windows_v3_bitwise.py).
    batch = run_vector_windowed(BatchSpec((WorldSpec(1, option),), 1, 10**6, 2**31), policy)
    final = batch.worlds[1].final.state
    np.testing.assert_allclose(
        np.asarray(final.amount_increment), history.amount_increment[-1], rtol=1e-12, atol=0
    )
    assert np.all(np.diff(history.junction_dissipated_energy_pJ, axis=0) >= 0)


def test_a_seeded_wrong_signed_junction_booking_trips_host_and_device_alike():
    spec = parse_spec(pair_raw(TRAPEZOID_JUNCTION_HEAT))
    history = MODEL.STATE_TYPE(*(np.asarray(v) for v in run(spec).history))
    values = history._asdict()
    heat = values["junction_dissipated_energy_pJ"].copy()
    increment = heat[ROW] - heat[ROW - 1]
    assert increment[0] > 1e-12
    heat[ROW:] -= 2 * increment  # Row ROW books -increment; later rows keep theirs.
    corrupted = history._replace(junction_dissipated_energy_pJ=heat)
    _, p = MODEL.initial_values(spec)

    def rows(start, stop):
        return MODEL.STATE_TYPE(*(v[start:stop] for v in corrupted))

    def verdict(j):
        """Row j's own host verdict (test_surface_pump_v3_device_checks.host_verdict)."""
        try:
            MODEL.check_values(rows(j, j + 1), spec, steps=[j])
            if j:
                try:
                    MODEL.check_values(rows(j - 1, j), spec, steps=[j - 1])
                except NumericalError:
                    return None  # Row j-1 fails alone; row j's own tests passed.
                MODEL.check_values(rows(j - 1, j + 1), spec, steps=[j - 1, j])
        except NumericalError as error:
            return str(error)
        return None

    host = [verdict(j) for j in range(len(heat))]
    previous = type(corrupted)(*(np.concatenate((v[:1], v[:-1])) for v in corrupted))
    checks = jax.vmap(MODEL.device_checks, in_axes=(0, 0, None, None, 0))
    failed, _ = checks(
        previous, corrupted, p, MODEL.device_check_constants(spec), np.arange(len(heat))
    )
    device = [
        MODEL.device_failure_message(MODEL.DEVICE_CHECKS[int(np.argmax(f))]) if f.any() else None
        for f in np.asarray(failed)
    ]
    assert host == device
    assert host[ROW] == surface_pump.DISSIPATION_MESSAGE and host[:ROW] == [None] * ROW
