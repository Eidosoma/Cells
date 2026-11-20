"""Check asymmetric division and two bridge-closure laws against their analytic solutions."""

import json
import math
from decimal import Decimal, localcontext
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec as composite
from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.laws.electrochemistry import CHARGE_PER_FMOL, R
from cells.models import pump_composite_adapter as adapter
from cells.operators import bridge_closure, partition
from cells.registry.models import get_model
from tests import partition_fixtures as fx

FRACTION = 0.75
PATCH_FRACTION = 0.6
CARRIERS = {"K": 0.5, "M": 0.5}
TAU = 3 * fx.DT


def control_at(spec, model, time):
    return model.CONTROL_TYPE(*(v[0] for v in composite.control_values(spec, [time])))


def unmixing(amounts, carrier_fmol, temperature):
    # Evaluate both concentration shifts before converting the small net work to float.
    with localcontext() as context:
        context.prec = 65
        f, work = Decimal(FRACTION), Decimal(0)
        for amount, delta in zip(amounts, carrier_fmol, strict=True):
            n, d = Decimal(float(amount)), Decimal(float(delta))
            for base, shift in ((f * n, d), ((1 - f) * n, -d)):
                child = base + shift
                work += child * (child / base).ln()
        return float(work * Decimal(str(1e-3 * R * temperature)))


def event(spec, model, before, p):
    """One isolated compiled event starting from the solver's actual pre-division row."""
    op = next(o for o in model.operators if o.LAW_ID == partition.LAW_ID)
    control = control_at(spec, model, fx.EVENT)

    def apply(s, c, layout):
        return op.event(s, c, layout, xp=jnp, view=lambda v: model.view(layout, v, xp=jnp))

    after, ok = jax.device_get(jax.jit(apply)(before, control, p))
    assert ok
    old = p.amount_reference[:, 0] + before.amount_increment[:, 0]
    z = np.asarray(spec.model.valence)
    q_parent = p.initial_cell_charge_C[0] + CHARGE_PER_FMOL * math.fsum(
        z * before.amount_increment[:, 0]
    )
    mismatch = (PATCH_FRACTION - FRACTION) * q_parent
    delta = np.array(
        [
            mismatch * CARRIERS[species] / (valence * CHARGE_PER_FMOL)
            if species in CARRIERS
            else 0.0
            for species, valence in zip(spec.model.species_ids, z, strict=True)
        ]
    )
    np.testing.assert_allclose(CHARGE_PER_FMOL * np.dot(z, delta), mismatch, rtol=2e-15)
    daughters = p.amount_reference[:, 1:3] + after.amount_increment[:, 1:3]
    first = FRACTION * old + delta
    np.testing.assert_allclose(daughters, np.column_stack((first, old - first)), rtol=0, atol=3e-14)
    error = max(abs(daughters.sum(axis=1) - old))
    d_charge = p.initial_cell_charge_C[1:3] + CHARGE_PER_FMOL * (z @ after.amount_increment[:, 1:3])
    np.testing.assert_allclose(
        d_charge, [PATCH_FRACTION * q_parent, (1 - PATCH_FRACTION) * q_parent], rtol=0, atol=2e-24
    )
    initial_view = model.view(p, before, xp=np)
    final_view = model.view(p, after, xp=np)
    np.testing.assert_array_equal(initial_view.active, [True, False, False])
    np.testing.assert_array_equal(final_view.active, [False, True, True])
    v0 = q_parent / initial_view.membrane_capacitance[0]
    potentials = adapter.node_potentials(after, final_view, xp=np)
    volt = adapter.patch_voltages(potentials, final_view, xp=np)[1:3]
    np.testing.assert_allclose(volt, v0, rtol=0, atol=2e-12)
    expected_work = unmixing(old, delta, spec.model.temperature_K)
    measured_work = float(after.partition_work_pJ[0] - before.partition_work_pJ[0])
    assert expected_work > 0
    np.testing.assert_allclose(measured_work, expected_work, rtol=0, atol=5e-16)
    return dict(
        charge_mismatch_C=float(mismatch),
        carrier_offset_fmol=delta.tolist(),
        max_species_error_fmol=error,
        max_daughter_voltage_error_V=max(abs(volt - v0)),
        expected_unmixing_pJ=expected_work,
        booked_work_pJ=measured_work,
    )


def bridge_world(law):
    end = 8 * fx.DT
    raw = fx.divided(
        f=FRACTION, area_fraction=PATCH_FRACTION, carriers=CARRIERS, bridge=(law, TAU), end=end
    )
    raw["experiment"]["observation_times"] = [i * fx.DT for i in range(9)]
    spec = parse_spec(raw)
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    result = run(spec)
    h = result.history
    a0 = fx.APERTURE_M
    edge = [j.id for j in spec.model.junctions].index("bridge_1")
    junction = spec.model.junctions[edge]
    d = fx.diffusivity(raw)
    for s, permeability in zip(spec.model.species_ids, junction.permeability_m_per_s, strict=True):
        np.testing.assert_allclose(junction.area_m2 * permeability, 2 * a0 * d[s], rtol=2e-15)
    at_birth = None
    normalized = []
    max_flux_error = max_open = 0.0
    for i, t in enumerate(result.times):
        row = type(h)(*(v[i] for v in h))
        born = t > fx.EVENT
        assert bool(row.division_applied[0]) == born
        if t == fx.EVENT and law == "linear":
            at_birth = event(spec, model, row, p)
        ratio = float(bridge_closure.availability(row, p, xp=np)[edge])
        elapsed = max(0.0, float(t) - fx.EVENT)
        expected = max(0, 1 - elapsed / TAU) if law == "linear" else math.exp(-elapsed / TAU)
        np.testing.assert_allclose(ratio, expected, rtol=0, atol=8e-15)
        if born:
            c = control_at(spec, model, t)
            fully_open = row._replace(bridge_aperture_m=p.bridge_initial_aperture_m)
            actual = model.readouts(row, c, p, xp=np).field.rates.junction_flux_fmol_s[:, edge]
            open_flux = model.readouts(fully_open, c, p, xp=np).field.rates.junction_flux_fmol_s[
                :, edge
            ]
            max_open = max(max_open, max(abs(open_flux)))
            max_flux_error = max(max_flux_error, max(abs(actual - expected * open_flux)))
            normalized.append(ratio)
    assert max_open > 1e-12 and max_flux_error < 2e-14 * max_open
    transfer = float(np.max(np.abs(h.junction_transferred[:, :, edge])))
    assert transfer > 0
    if law == "linear":
        assert normalized[-1] == 0 and at_birth is not None
    else:
        assert all(a > 0 for a in normalized)
    report = dict(
        checked_steps=len(result.times) - 1,
        availability_after_birth=normalized,
        max_open_flux_fmol_s=max_open,
        max_absolute_flux_error_fmol_s=max_flux_error,
        max_cumulative_bridge_transfer_fmol=transfer,
    )
    if at_birth:
        report["division_event"] = at_birth
    return report


def bridge_measurements():
    data = json.loads(
        (Path(__file__).with_name("data") / "trafficking_division_measurements.json").read_text()
    )
    record = data["adarlevor2021_bridge_stalk@1"]
    (t0, d0), (t1, d1) = record["fit"]
    slope = (d0 - d1) / (t1 - t0)
    exp_tau = -(t1 - t0) / math.log(d1 / d0)
    return [
        dict(
            elapsed_min=t,
            measured_um=d,
            linear_um=max(0.0, d0 - slope * (t - t0)),
            exponential_um=d0 * math.exp(-(t - t0) / exp_tau),
        )
        for t, d in record["evaluation"]
    ]


if __name__ == "__main__":
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    print(
        json.dumps(
            dict(
                linear=bridge_world("linear"),
                exponential=bridge_world("exponential"),
                measured_stalk=bridge_measurements(),
            ),
            indent=2,
            allow_nan=False,
        )
    )
