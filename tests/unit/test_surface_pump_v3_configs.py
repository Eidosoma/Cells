"""cells.model.resolved_pump_tissue@3: the shipped channel configs and the temperature dependence (a
shard of the former test_surface_pump_v3.py).

NEEDS A CHECKOUT: it reads configs/, which is outside an execution snapshot's scope
(src/cells, validation, tests, pyproject.toml). It is skipped when configs/ is missing and
carries the `needs_checkout` marker.
"""

import json
import os
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.laws.channels import voltage_gates
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


@pytest.mark.needs_checkout
@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "configs").is_dir(),
    reason="needs a checkout: configs/ is outside the execution snapshot's scope",
)
def test_round_trip_configs_and_temperatures():
    root = Path(__file__).resolve().parents[2]
    for name in ("resolved_pump_tissue_channels.json", "resolved_pump_tissue_channels_cell.json"):
        spec = parse_spec(json.loads((root / "configs" / name).read_text()))
        model = get_model(spec.model)
        assert isinstance(model, surface_pump_v3.InnerImplementation)
        assert model.declared_channel_laws and spec.model.channels
        assert parse_spec(spec.to_dict()) == spec
    # Kv1.5 at 298 and 310 K: the gates have no temperature term (as the source
    # law); the constant-field flux and its affinity use the declared temperature.
    voltage = np.array([-0.05])
    values = []
    for temperature in (298.15, 310.0):
        spec, state, p, control = initial(
            fixtures.definition("clamped", solver=imex.ARS222_ID, temperature_K=temperature)
        )
        assert spec.model.temperature_K == temperature
        values.append(surface_pump_v3.readouts(state, control, p, xp=np))
        target, tau = surface_pump_v3.channel_kinetics(voltage, np.array([0]), xp=np)
        expected = voltage_gates.kinetics(voltage, xp=np)
        np.testing.assert_array_equal(target, expected[0])
        np.testing.assert_array_equal(tau, expected[1])
    flux = [v.channel_flux_fmol_s for v in values]
    assert scaled_difference(*flux) > 1e-3  # The fixed charge sets V; GHK moves with T.
