"""FR-43 part 2B (D315): one pool at changing volume, the engine's own checks (no reference).

validation/tissue/shared_inventory_fixtures.swelling_cell: one quiescent cell swelling under water
(declared first) against a bath at 0.4 of its osmolarity, with the impermeant tracer S and D152's
passive A + B <-> C beside it. Both read the cell's volume current at their split parts.
- C2.5: with every multiplier 0, S keeps its amount bit for bit at every row, its concentration is
  n0 / V(t) at every row to rounding, and it is half the start where V first reaches 2 V0.
- C2.7: F(N, V) + U(V) - F(N0, V0) - U(V0) = booked work - booked heat (the network's and the bath's
  water work; the network's and water's heat). F is computed here from the engine's amounts and
  volume, not from its ledger code; U = 0 (no modulus). The residual shrinks at second order
  between dt and dt/2 (ratio in [3.6, 4.4], Strang over second-order half-steps), and the network
  reading the declared volume V0 instead is refused by the engine's own energy ledger.
Its reason and cost: three runs of the swelling cell over 10 s (seconds as the tier tool measures).
"""

import math

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.laws.electrochemistry import R
from cells.operators import species_reactions as sr
from cells.registry.models import get_model
from validation.tissue import shared_inventory_fixtures as sif

END = 10.0  # s: C2.7's horizon, most of the way to 2 V0 (reached at about 12.8 s).
DT = 0.01


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def outcome(raw):
    spec = parse_spec(raw)
    result = run(spec)  # Every host check on every accepted row.
    _, p = get_model(spec.model).initial_values(spec)
    ids = list(spec.model.species_ids)
    h = result.history
    n = np.asarray(p.amount_reference)[:, 0][None, :] + np.asarray(h.amount_increment)[:, :, 0]
    v = np.asarray(p.volume)[0] + np.asarray(h.volume_increment_pL)[:, 0]
    return spec, ids, h, n, v


def test_c25_a_tracer_keeps_its_amount_and_dilutes_with_the_volume():
    spec, ids, _, n, v = outcome(sif.swelling_cell(network_multiplier=0.0, dt=DT, end=40.0))
    s = n[:, ids.index("S")]
    assert np.all(s == s[0])  # Bit for bit at every row.
    assert float(np.max(np.abs((s / v) * v - s[0]))) <= 4 * np.finfo(float).eps * s[0]
    crossed = np.flatnonzero(v >= 2 * v[0])
    assert len(crossed), "the cell never reached 2 V0"
    halved = (s[crossed[0]] / v[crossed[0]]) / (s[0] / v[0])
    assert 0.49 < halved <= 0.5, halved


def endpoint_residual(raw):
    """max |dF - (work - heat)| over the energy scale (largest |dF| + |heat| + |work|)."""
    spec, ids, h, n, v = outcome(raw)
    rt = 1e-3 * R * raw["model"]["temperature_K"]  # pJ/fmol.
    network = next(o for o in raw["model"]["operators"] if o["law"] == sr.LAW_ID)
    standard = np.zeros(len(ids))
    for s in network["species"]:  # Every other row's standard term is constant: it cancels.
        standard[ids.index(s["id"])] = rt * (
            s["standard_mu_RT"] - math.log(network["standard_concentration_mM"])
        )
    free = np.sum(rt * n * (np.log(n / v[:, None]) - 1.0) + standard[None, :] * n, axis=1)
    work = np.asarray(h.reaction_work_pJ)[:, 0] + np.asarray(h.bath_water_work_pJ).sum(axis=1)
    heat = np.asarray(h.reaction_dissipated_energy_pJ)[:, 0] + np.asarray(
        h.water_dissipated_energy_pJ
    ).sum(axis=1)
    residual = (free - free[0]) - (work - heat)
    scale = float(np.max(np.abs(free - free[0])) + np.max(np.abs(heat)) + np.max(np.abs(work)))
    return float(np.max(np.abs(residual))) / scale


def test_c27_the_energy_identity_closes_at_second_order_and_the_v0_plant_is_refused():
    coarse = endpoint_residual(sif.swelling_cell(dt=DT, end=END))
    fine = endpoint_residual(sif.swelling_cell(dt=DT / 2, end=END))
    assert 3.6 <= coarse / fine <= 4.4, (coarse, fine)
    original = sr.LocalSpeciesReactions.half_step

    def planted(self, *args, view=None, **kwargs):  # The declared volume V0: no view.
        return original(self, *args, **kwargs)

    jax.clear_caches()  # The runner's compiled rollout is cached per model: retrace the plant.
    sr.LocalSpeciesReactions.half_step = planted
    try:
        with pytest.raises(NumericalError, match="energy"):
            run(parse_spec(sif.swelling_cell(dt=DT, end=END)))
    finally:
        sr.LocalSpeciesReactions.half_step = original
        jax.clear_caches()
