"""stationary_continuation_analysis@1 on resolved_pump_water@1 (compliant volumes).

The slow mode carries the volumes as dynamical coordinates (1e-3 of the
declared volume): a cell facing a held bath has no volume law, a cell whose
water routes are closed keeps a closed-volume law, and the fast mode freezes
the volumes with the composition. The H cell's stationary state with water is
found by Newton from its fixed-volume composition; it satisfies the stationary
identity of a cell whose anion M has passive routes only (M at its Nernst
distribution, electroneutrality and osmotic balance):

    V = (N_P + (I + q/F - X)/2) / ((c_b + dP/RT)/2 - M_b exp(F Vm / RT))

and it is a fixed point of the split step map. Models without volume fields
(resolved_pump_tissue@1-3) keep exactly their blocks and laws.
"""

import math

import jax
import numpy as np
import pytest

from cells.analysis import stationary as sa
from cells.core.specs import parse_spec
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R
from validation.stationary import worlds
from validation.tissue import pump_water_fixtures as fixtures

AQUAPORIN_PF = 5e-4


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def water_cell(state="H", **water):
    raw = fixtures.heredity_cell(state, dt=1e-3, end_time=1.0)
    return parse_spec(fixtures.with_water(raw, **water))


def test_volume_blocks_and_laws():
    pb = sa.problem(water_cell(pf_m_s=AQUAPORIN_PF))
    kinds = {b.field: b.kind for b in pb.blocks}
    assert kinds["volume_increment_pL"] == "volume"
    assert "extracellular_volume_increment_pL" not in kinds  # Only a held bath outside.
    laws = [law["kind"] for law in pb.reduction().laws]
    assert "closed_water_volume" not in laws  # The bath supplies water.
    sealed = sa.problem(water_cell(availability=0.0))
    assert "closed_water_volume" in [law["kind"] for law in sealed.reduction().laws]
    fast = sa.problem(water_cell(), mode="fast")
    assert all(b.kind != "volume" for b in fast.blocks)


def test_models_without_volumes_keep_their_blocks_and_laws():
    from validation.tissue import surface_pump_v3_fixtures as v3

    raw = v3.heredity_cells([v3.HEREDITY_STATES["H"][:4]], end_time=1.0)
    for spec in (parse_spec(raw), parse_spec(worlds.default_world_cell())):
        pb = sa.problem(spec)
        assert all(b.kind in ("amount", "gate") for b in pb.blocks)
        assert all(b.field in sa.DYNAMIC_FIELDS for b in pb.blocks)
        assert all(law["kind"] != "closed_water_volume" for law in pb.reduction().laws)


@pytest.fixture(scope="module")
def stationary_h():
    spec = water_cell(pf_m_s=AQUAPORIN_PF)
    pb = sa.problem(spec)
    solution = sa.newton(pb, pb.anchor)
    return spec, pb, solution


def test_h_stationary_state_with_water_satisfies_the_identity(stationary_h):
    spec, pb, solution = stationary_h
    assert solution.converged, solution.message
    state, p, _ = pb.embed(solution.u)
    state, p = sa._numpy(state), sa._numpy(p)
    volume = float(p.volume[0] + state.volume_increment_pL[0])
    described = sa.describe(pb, solution.u)
    vm = described["membrane_voltage_V"]["membrane_0"]
    m = spec.model
    ids = m.species_ids
    amount = p.amount_reference[:, 0] + state.amount_increment[:, 0]
    z = np.asarray(m.valence, dtype=float)
    cell = m.cells[0]
    fixed = cell.fixed_charge_equivalent_fmol
    charge = float(
        p.initial_cell_charge_C[0] + CHARGE_PER_FMOL * np.sum(z * state.amount_increment[:, 0])
    )
    bath = m.extracellular[0]
    c_bath = sum(bath.initial_amount_fmol[ids.index(s)] for s in ids) / bath.volume_pL
    m_bath = bath.initial_amount_fmol[ids.index("M")] / bath.volume_pL
    w = m.water.compartments[0]
    pressure = w.bulk_modulus_Pa * (volume / w.reference_volume_pL - 1) + w.pressure_offset_Pa
    rt = R * m.temperature_K
    numerator = (
        amount[ids.index("P")] + (w.impermeant_amount_fmol + charge / CHARGE_PER_FMOL - fixed) / 2
    )
    denominator = (c_bath + pressure / rt) / 2 - m_bath * math.exp(F * vm / rt)
    assert volume == pytest.approx(numerator / denominator, rel=1e-9)
    # H shrinks: the fixed-volume H state (284 mM) is hypotonic to the 300 mM bath.
    assert volume < float(p.volume[0])
    osmolarity = (np.sum(amount) + w.impermeant_amount_fmol) / volume
    assert osmolarity == pytest.approx(c_bath + pressure / rt, rel=1e-9)


def test_h_stationary_state_is_a_fixed_point_of_the_split_step(stationary_h):
    _, pb, solution = stationary_h
    residual = pb.evaluate(solution.u, formulation="step_map", steps=4)[0]
    assert np.max(np.abs(residual)) < 1e-6
