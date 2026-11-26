"""cells.model.resolved_pump_tissue@3: the heredity cell's pre-screen states and the CPU/L4 agreement (a
shard of the former test_surface_pump_v3.py).
"""

import os

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.definitions.surface_pump_v3_spec import NALEAK_LAW_ID, control_values
from cells.execution.runner import run
from cells.models import surface_pump_v3
from cells.numerics import surface_imex as imex
from cells.registry.models import get_model
from validation.tissue import surface_pump_v3_fixtures as fixtures

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
SOLVERS = (imex.EULER_ID, imex.ARS222_ID)
CHANNEL_FIELDS = ("channel_gate", "channel_transferred", "channel_dissipated_energy_pJ")
CHANNEL_OBSERVATIONS = (
    *CHANNEL_FIELDS,
    "channel_flux_fmol_s",
    "channel_targets",
    "channel_tau_s",
    "channel_availability",
)


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def scaled_difference(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    scale = max(np.max(np.abs(a), initial=0), np.max(np.abs(b), initial=0))
    return 0.0 if scale == 0 else float(np.max(np.abs(a - b)) / scale)


def initial(raw):
    spec = parse_spec(raw)
    state, layout = get_model(spec.model).initial_values(spec)
    controls = control_values(spec, [0.0])
    return spec, state, layout, type(controls)(*(v[0] for v in controls))


@pytest.fixture(autouse=True)
def clear_compiled_programs():
    """Release the compiled programs after every test: these tests compile many programs
    and one process otherwise keeps them all (the unsplit file hit a 4 GB cap in tier 3)."""
    yield
    jax.clear_caches()


def test_heredity_cell_holds_and_switches_the_prescreen_states():
    """Six independent cells at 1 ms: the two states, their stability, a write, an erase.

    The pre-screen's slow steady states (H -79.556 mV, D -21.518 mV) are
    stationary: rates vanish and Vm holds to 1 uV for 2 s. A 5 mV charge kick
    relaxes back with the pre-screen's fastest time constant (0.258 s H, 0.089 s
    D; dynamic Kir2.1 h gates lengthen H's by about 6%). A 9x Na-leak cue for
    0.3 s writes D's depolarized branch from H, and a 0.5 s NaV1.2 block erases
    D to the hyperpolarized branch; both persist after the cue.
    """
    states = fixtures.HEREDITY_STATES
    h, d = states["H"], states["D"]
    cells = [h[:4], d[:4], fixtures.kicked(h, 5), fixtures.kicked(d, -5), h[:4], d[:4]]
    times = [0.0, 0.1, 0.25, 0.35, 0.55, 1.0, 2.0]
    raw = fixtures.heredity_cells(
        cells,
        end_time=2.0,
        observation_times=times,
        gate_voltages=[h[0], d[0], h[0], d[0], h[0], d[0]],
    )
    m, e = raw["model"], raw["experiment"]
    cue = 9 * fixtures.HEREDITY_PERMEABILITY["Na"]
    m["channels"].append(fixtures.channel("cue_4", 4, NALEAK_LAW_ID, "Na", cue, 1.0, []))
    e["channel_controls"].append(
        dict(
            channel_id="cue_4",
            schedule=[
                dict(time=0.0, availability=0.0),
                dict(time=0.05, availability=1.0),
                dict(time=0.35, availability=0.0),
            ],
        )
    )
    blocked = next(g for g in e["channel_controls"] if g["channel_id"] == "nav_5")
    blocked["schedule"] = [
        dict(time=0.0, availability=1.0),
        dict(time=0.05, availability=0.0),
        dict(time=0.55, availability=1.0),
    ]
    raw["execution"]["channel_capacity"] += 1
    spec, state, p, control = initial(raw)
    law = surface_pump_v3.readouts(state, control, p, xp=np)
    assert law.valid
    assert np.all(np.abs(law.field.membrane_voltage_rate_V_s[:2]) < 1e-9)
    assert np.all(np.abs(law.derivative.amount_increment[:3, :2] / p.volume[:2]) < 1e-12)
    value = run(spec)
    d_ = value.diagnostics
    assert d_["max_energy_balance_relative"] <= surface_pump_v3.ENERGY_RTOL[imex.ARS222_ID]
    assert d_["max_global_charge_bound_ratio"] <= 1.0
    vm = np.asarray(value.observations.membrane_voltage_V)
    np.testing.assert_allclose(vm[:, 0], h[0], rtol=0, atol=1e-6)
    np.testing.assert_allclose(vm[:, 1], d[0], rtol=0, atol=1e-6)
    for cell, state_, sign in ((2, h, 1), (3, d, -1)):
        deviation = sign * (vm[:, cell] - state_[0])
        tau = 0.15 / np.log(deviation[1] / deviation[2])
        assert abs(tau / state_[4] - 1) < 0.15, (cell, tau)
        assert abs(vm[-1, cell] - state_[0]) < 5e-5
    assert -0.020 < vm[-1, 4] < -0.010 and vm[3, 4] > -0.010  # Written, held after release.
    assert vm[4, 5] < -0.070 and vm[-1, 5] < -0.085  # Erased, held after unblocking.


def test_cpu_and_gpu_trajectories_agree():
    """Channel fixture (IMEX) and a heredity cell at 1 ms agree on CPU and L4."""
    if not any(d.platform == "gpu" for d in jax.devices()):
        pytest.skip("Requires the L4 GPU environment")
    states = fixtures.HEREDITY_STATES
    definitions = (
        lambda backend: fixtures.definition("release", solver=imex.ARS222_ID, backend=backend),
        lambda backend: fixtures.heredity_cells(
            [states["H"][:4], fixtures.kicked(states["D"], -5)],
            end_time=0.25,
            backend=backend,
            gate_voltages=[states["H"][0], states["D"][0]],
        ),
    )
    for definition in definitions:
        values = {}
        for backend in ("cpu", "gpu"):
            value = run(parse_spec(definition(backend)))
            assert all(v.device.platform == backend for v in value.final.state)
            values[backend] = value
        for key in surface_pump_v3.STATE_TYPE._fields:
            a, b = (np.asarray(getattr(values[k].history, key)) for k in ("cpu", "gpu"))
            assert scaled_difference(a, b) <= 3e-12, key
