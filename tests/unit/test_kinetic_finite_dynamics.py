"""Complete stage composition, interpolation guards and independent equation contact."""

import copy
import sys
from decimal import Decimal, localcontext

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.schedule import PhysicalIonicGraphControl, control_values
from cells.core.specs import parse_spec
from cells.models import finite_extracellular as old
from cells.models import kinetic_finite_bounds as bounds
from cells.models import kinetic_finite_extracellular as model
from cells.observers import sample_hermite_history
from cells.processes.electrochemistry import F, R
from tests.kinetic_finite_fixtures import ROOT, canonical, definition, evidence, spec_for

sys.path.insert(0, str(ROOT / "validation/betse/pump_coupled"))
import coupled_reference as reference  # noqa: E402

PLAN, _ = evidence()
CASES = PLAN["cases"]


def held(spec, time=0.0):
    return PhysicalIonicGraphControl(*(v[0] for v in control_values(spec, [time])))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_same_stage_complete_rhs_against_independent_scalar_equations(case):
    spec = spec_for(case)
    state, layout = model.initial_values(spec)
    # Perturb a complete conserved state, not just initial values. Neutral NaCl
    # movement makes the same finite bath visible at the next stage.
    state.amount_increment[[0, 2], 0] = 0.003
    state.leak_transferred[[0, 2], 0] = 0.003
    state.extracellular_amount_increment[[0, 2], 0] = -0.003
    assert model.domain_valid(state, layout, layout.active, xp=np)
    c = held(spec)
    expected = reference.rhs(
        case,
        canonical(state._asdict(), len(case["volume_pL"])),
        [case["controls"][0]["pump"], case["controls"][0]["leak"]],
    )
    for xp in (np, jnp):
        y, p, u = jax.device_put((state, layout, c)) if xp is jnp else (state, layout, c)
        actual = model.rhs(y, u, p, p.active, xp=xp)
        np.testing.assert_allclose(
            canonical(actual._asdict(), len(case["volume_pL"])), expected, atol=3e-13, rtol=3e-12
        )
        np.testing.assert_allclose(
            np.sum(actual.amount_increment, axis=-1),
            -np.sum(actual.extracellular_amount_increment, axis=-1),
            atol=1e-15,
        )
        assert np.all(actual.dissipated_energy_pJ >= 0)


def test_labels_and_species_order_are_data():
    raw = definition(CASES[-1])
    original = parse_spec(raw)
    # Rename labels everywhere, then permute the species axis; roles keep their
    # biochemical meaning without spelling-based dispatch.
    import json

    changed = json.loads(json.dumps(raw).replace('"Na"', '"cation_A"').replace('"K"', '"cation_B"'))
    changed["model"]["species"] = changed["model"]["species"][::-1]
    spec = parse_spec(changed)
    a, g = model.initial_values(original)
    b, h = model.initial_values(spec)
    x = model.rhs(a, held(original), g, g.active, xp=np)
    y = model.rhs(b, held(spec), h, h.active, xp=np)
    for name in model.STATE_TYPE._fields:
        expected = getattr(x, name)
        actual = getattr(y, name)
        if model.STATE_AXES[name][0] == "species":
            actual = actual[::-1]
        np.testing.assert_allclose(actual, expected, atol=1e-15, rtol=1e-14)


@pytest.mark.parametrize("padded", [False, True])
def test_absent_zero_capacity_and_blocked_pumps_have_zero_flux(padded):
    for absence in ("absent", "zero_capacity", "blocked"):
        raw = definition(CASES[-1], padded=padded)
        p = raw["model"]["cells"][1]["membrane"]
        if absence == "absent":
            p["pump"] = None
        elif absence == "zero_capacity":
            p["pump"]["capacity_fmol_per_s"] = 0
        else:
            raw["experiment"]["membrane_controls"][1]["pump"][0]["multiplier"] = 0
        spec = parse_spec(raw)
        y, layout = model.initial_values(spec)
        rate = model.rhs(y, held(spec), layout, layout.active, xp=np)
        assert rate.pump_cycles[0] > 0 and rate.pump_cycles[1] == 0
        assert np.all(rate.pump_cycles[2:] == 0)
        assert model.domain_valid(y, layout, layout.active, xp=np)
        # Blocking/absence cannot turn negative physical inventory into a valid
        # state. Predicate-only neutral arithmetic must not emit log warnings.
        y.amount_increment[0, 1] = -2 * layout.amount_reference[0, 1]
        with np.errstate(divide="raise", invalid="raise", over="raise"):
            assert not model.domain_valid(y, layout, layout.active, xp=np)


def synthetic_interval(initial_affinity, derivative):
    raw = definition(CASES[0])
    spec = parse_spec(raw)
    y, layout = model.initial_values(spec)
    affinity = model.readouts(y, held(spec).membrane, layout, xp=np)[-1][0]
    raw["model"]["cells"][0]["membrane"]["pump"]["metabolism"]["delta_g0_J_per_mol"] += (
        initial_affinity * R * spec.model.temperature_K - affinity
    )
    spec = parse_spec(raw)
    y, layout = model.initial_values(spec)
    history = model.STATE_TYPE(*(np.stack((v, v)) for v in y))
    f0 = model.STATE_TYPE(*(np.zeros_like(v[:1]) for v in history))
    f1 = model.STATE_TYPE(*(np.zeros_like(v[:1]) for v in history))
    for slope, sign in ((f0, -1), (f1, 1)):
        slope.amount_increment[0, [0, 2], 0] = sign * derivative
        slope.extracellular_amount_increment[0, [0, 2], 0] = -sign * derivative
    return spec, history, f0, f1, layout


def test_unsafe_pump_cubic_interior_with_valid_endpoints():
    spec, y, f0, f1, layout = synthetic_interval(79.0, 32.0)
    times = np.array([0.0, 1.0])
    assert model.domain_valid(y, layout, layout.active, xp=np)
    old.check_interpolants(times, y, f0, f1, layout)
    middle = model.STATE_TYPE(
        *(sample_hermite_history(times, a, [0.5], b, c) for a, b, c in zip(y, f0, f1, strict=True))
    )
    assert not model.domain_valid(middle, layout, layout.active, xp=np)
    with pytest.raises(NumericalError, match="Unable to certify kinetic"):
        model.check_interpolants(times, y, f0, f1, layout)
    blocked = copy.deepcopy(spec.to_dict())
    blocked["experiment"]["membrane_controls"][0]["pump"][0]["multiplier"] = 0
    blocked = parse_spec(blocked)
    assert model.readouts(middle, held(blocked).membrane, layout, xp=np)[2][0, 0] == 0
    assert not model.domain_valid(middle, layout, layout.active, xp=np)


def test_conservative_refusal_is_not_claimed_as_actual_domain_escape():
    spec, y, f0, f1, layout = synthetic_interval(78.9, 12.0)
    times = np.array([0.0, 1.0])
    samples = model.STATE_TYPE(
        *(
            sample_hermite_history(times, a, np.linspace(0, 1, 501), b, c)
            for a, b, c in zip(y, f0, f1, strict=True)
        )
    )
    assert model.domain_valid(samples, layout, layout.active, xp=np)
    # All actual extrema here are at the midpoint; the Bernstein hull is wider.
    with pytest.raises(NumericalError, match="Unable to certify"):
        model.check_interpolants(times, y, f0, f1, layout)


def test_cubic_hull_encloses_independent_80_digit_polynomials():
    rng = np.random.default_rng(827)
    times = np.array([0.1, 0.100001])
    values = rng.normal(size=(2, 40))
    a, b = rng.normal(size=(2, 1, 40)) * 1e6
    lo, hi = bounds.cubic_hull(times, values, a, b)
    with localcontext() as context:
        context.prec = 80
        d = Decimal.from_float
        h = d(times[1]) - d(times[0])
        for i in range(40):
            v0, v1, left, right = (d(v) for v in (values[0, i], values[1, i], a[0, i], b[0, i]))
            for k in range(101):
                t = Decimal(k) / 100
                exact = (
                    (2 * t**3 - 3 * t * t + 1) * v0
                    + (t**3 - 2 * t * t + t) * h * left
                    + (-2 * t**3 + 3 * t * t) * v1
                    + (t**3 - t * t) * h * right
                )
                assert d(lo[0, i]) <= exact <= d(hi[0, i])


def test_log_affinity_enclosure_at_high_precision_boundary():
    spec, y, f0, f1, layout = synthetic_interval(80 - 2e-12, 0.0)
    enclosed = bounds.pump_enclosures(np.array([0.0, 1.0]), y, f0, f1, layout)
    with localcontext() as ctx:
        ctx.prec = 80
        d = Decimal.from_float
        rt = d(R) * d(spec.model.temperature_K)
        p = spec.model.membranes[0].pump.metabolism
        drive = (
            d(p.delta_g0_J_per_mol) / rt
            + d(p.adp_mM).ln()
            + d(p.pi_mM).ln()
            - d(p.atp_mM).ln()
            - Decimal(1000).ln()
        )
        mu_na = Decimal(12).ln() - Decimal(140).ln() + d(F) * d(-0.08) / rt
        mu_k = Decimal(140).ln() - Decimal(4).ln() + d(F) * d(-0.08) / rt
        for (lo, hi), exact in zip(
            enclosed, (mu_na, mu_k, drive - 3 * mu_na + 2 * mu_k), strict=True
        ):
            assert d(lo[0, 0]) < exact < d(hi[0, 0])
    with pytest.raises(NumericalError, match="Unable to certify"):
        model.check_interpolants(np.array([0.0, 1.0]), y, f0, f1, layout)
