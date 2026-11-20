"""Compare scheduled cell replacement with pre-event inventories and physical endpoints."""

import argparse
import json
import math
import statistics
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec as composite
from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.runner import run
from cells.laws.electrochemistry import CHARGE_PER_FMOL, R
from cells.registry.models import get_model
from tests import replacement_water_fixtures as fixtures

DT = fixtures.DT
ENERGY_ATOL = 2e-11  # pJ, including subtraction of independently evaluated absolute energies


def sheet(version):
    raw = fixtures.sheet(end=3 * DT, observed=[0, DT, 2 * DT, 3 * DT])
    for bath in raw["model"]["extracellular"]:
        bath["boundary_potential_V"] = 0.01
    a, b = fixtures.ring_neighbours(raw)
    volume = raw["model"]["cells"][0]["volume_pL"]
    templates = fixtures.templates(raw, {"h": 1.04 * volume} if version == 2 else None)
    events = [(DT, a, None, "copy", b), (DT, b, "h", "from_template")]
    if version == 1:
        definition = composite.frozen_definition(fixtures.replacement_v1(raw, templates, events))
    else:
        definition = fixtures.over_water(raw, templates, events, impermeant_fmol=5.0)
    spec = parse_spec(definition)
    ids = [c.id for c in spec.model.cells]
    return spec, ids.index(a), ids.index(b), templates[0]


def endpoints(model, amounts, volumes):
    """Ideal chemical energy at actual volume; elastic energy relative to the declared volume."""
    rt = 1e-3 * R * model.temperature_K
    energy = []
    water_rows = (
        {r.compartment_id: r for r in model.operators[0].compartments}
        if (len(model.operators) == 2)
        else {}
    )
    for i, cell in enumerate(model.cells):
        v, ref = volumes[i], cell.volume_pL
        ideal = rt * math.fsum(n * (math.log(n / v) - 1) for n in amounts[:, i])
        elastic = extra = 0.0
        if row := water_rows.get(cell.id):
            k = row.bulk_modulus_Pa / row.reference_volume_pL
            # Integrate the linear pressure between the two endpoints by its mean.
            avg_pressure = row.pressure_offset_Pa + k * ((ref + v) / 2 - row.reference_volume_pL)
            elastic = avg_pressure * (v - ref) / 1000
            extra = -rt * row.impermeant_amount_fmol * math.log(v / ref)
        energy.append(ideal + elastic + extra)
    return np.asarray(energy)


def electric(model, old, new):
    """Each cell in this fixture has a single membrane facing its own held electrode."""
    ids = [c.id for c in model.cells]
    baths = [b.id for b in model.extracellular]
    assert sorted(m.inside for m in model.membranes) == sorted(ids)
    assert sorted(m.outside for m in model.membranes) == sorted(baths)
    assert all(b.reservoir for b in model.extracellular)
    z = np.asarray(model.valence)
    field = []
    image = np.zeros(len(baths))
    for m in model.membranes:
        i, j = ids.index(m.inside), baths.index(m.outside)
        cell = model.cells[i]
        reference = cell.initial_amount_fmol
        dq = CHARGE_PER_FMOL * math.fsum(z * (new[:, i] - old[:, i]))
        q0 = cell.initial_charge_C + CHARGE_PER_FMOL * math.fsum(z * (old[:, i] - reference))
        field.append(1e12 * dq * (2 * q0 + dq) / (2 * m.capacitance_F))
        image[j] = -dq
    work = 1e12 * np.asarray([b.boundary_potential_V for b in model.extracellular]) * image
    return math.fsum(field), image, work


def check_version(version):
    spec, a, b, template = sheet(version)
    model = get_model(spec.model)
    initial, params = model.initial_values(spec)
    op = model.operators[-1]
    control = model.CONTROL_TYPE(*(v[0] for v in composite.control_values(spec, [DT])))
    ref = np.array([c.initial_amount_fmol for c in spec.model.cells]).T
    vref = np.array([c.volume_pL for c in spec.model.cells])
    ns = len(vref)
    k, m = (spec.model.species_ids.index(s) for s in ("K", "M"))
    inc = np.array(initial.amount_increment)
    inc[[k, m], a] = -0.3
    inc[[k, m], b] = 0.25
    inc[k, a] -= 0.0002
    inc[k, b] += 0.0001  # Charge tag makes the field and electrode bookings observable.
    before = initial._replace(amount_increment=inc)
    v0 = vref.copy()
    if version == 2:
        dv = np.array(initial.volume_increment_pL)
        dv[[a, b]] = 0.05 * vref[[a, b]]
        before = before._replace(volume_increment_pL=dv)
        v0 += dv[:ns]
    v1 = v0.copy()
    v1[b] = template["volume_pL"]
    old = ref + inc[:, :ns]
    arrival = old.copy()
    arrival[:, a] = old[:, b]
    arrival[:, b] = [template["amounts_fmol"][s] for s in spec.model.species_ids]
    due = np.zeros(ns, dtype=bool)
    due[[a, b]] = True
    compiled_event = jax.jit(lambda s, c, p: op.event(s, c, p, xp=jnp))
    after, ok = jax.device_get(compiled_event(before, control, params))
    assert ok
    np.testing.assert_array_equal(after.generation[:ns], due)
    np.testing.assert_allclose(ref + after.amount_increment[:, :ns], arrival, rtol=0, atol=2e-14)
    np.testing.assert_array_equal(after.replacement_removed_fmol[:, :ns], old * due)
    np.testing.assert_array_equal(after.replacement_supplied_fmol[:, :ns], arrival * due)
    assert not np.array_equal(arrival[:, a], arrival[:, b])
    dq = CHARGE_PER_FMOL * (np.asarray(spec.model.valence) @ (arrival - old))
    np.testing.assert_allclose(after.replacement_charge_C[:ns], dq, rtol=0, atol=2e-24)

    field, image, work = electric(spec.model, old, arrival)
    np.testing.assert_allclose(after.electrode_charge_transferred_C[:ns], image, rtol=0, atol=2e-24)
    np.testing.assert_allclose(after.electrode_work_pJ[:ns], work, rtol=0, atol=2e-14)
    assert abs(field) > 1e-5 and np.max(abs(work)) > 1e-5
    predicted = endpoints(spec.model, arrival, v1) - endpoints(spec.model, old, v0)
    predicted[due] += (field - math.fsum(work)) / due.sum()
    booked = after.replacement_free_energy_pJ[:ns].copy()
    report = {"field_change_pJ": field, "max_abs_electrode_work_pJ": float(max(abs(work)))}
    if version == 2:
        np.testing.assert_array_equal(after.replacement_volume_removed_pL[:ns], v0 * due)
        np.testing.assert_array_equal(after.replacement_volume_supplied_pL[:ns], v1 * due)
        np.testing.assert_array_equal(vref + after.volume_increment_pL[:ns], v1)
        dw = after.replacement_water_free_energy_pJ[:ns]
        delta_n = math.fsum(arrival[:, a] - old[:, a])
        unchanged_volume_work = (
            -1e-3 * R * spec.model.temperature_K * delta_n * math.log(v0[a] / vref[a])
        )
        np.testing.assert_allclose(dw[a], unchanged_volume_work, rtol=0, atol=2e-13)
        assert v1[a] == v0[a] and abs(dw[a]) > 0.01
        booked += dw
        report.update(
            copy_volume_pL=v0[a], copy_net_osmoles_fmol=delta_n, copy_water_energy_pJ=float(dw[a])
        )
    np.testing.assert_allclose(booked, predicted, atol=ENERGY_ATOL, rtol=0)
    report["max_endpoint_residual_pJ"] = float(max(abs(booked - predicted)))
    again, ok = op.event(after, control, params, xp=np)
    assert ok
    for x, y in zip(again, after, strict=True):
        np.testing.assert_array_equal(x, y)

    # The normal checked solver applies an event at the start of the next step at DT.
    result = run(spec)
    h = result.history
    np.testing.assert_array_equal(result.times, [0.0, DT, 2 * DT, 3 * DT])
    np.testing.assert_array_equal(h.generation[1, :ns], np.zeros(ns))
    np.testing.assert_array_equal(h.generation[2:, :ns], np.tile(due, (2, 1)))
    old_run = ref + np.asarray(h.amount_increment[1, :, :ns])
    np.testing.assert_array_equal(h.replacement_removed_fmol[-1, :, :ns], old_run * due)
    np.testing.assert_array_equal(h.replacement_supplied_fmol[-1, :, a], old_run[:, b])
    if version == 2:
        vol_run = vref + np.asarray(h.volume_increment_pL[1, :ns])
        np.testing.assert_array_equal(h.replacement_volume_removed_pL[-1, :ns], vol_run * due)
        np.testing.assert_array_equal(
            h.replacement_volume_supplied_pL[-1, [a, b]], [vol_run[b], v1[b]]
        )
    report["checked_run_steps"] = 3
    return report


def boundary_cases():
    raw = fixtures.sheet(end=2 * DT)
    site, _ = fixtures.ring_neighbours(raw)
    ref = next(c["volume_pL"] for c in raw["model"]["cells"] if c["id"] == site)
    lower = ref - 0.75 * ref
    first = math.nextafter(lower, math.inf)
    second = math.nextafter(first, math.inf)
    relaxed = math.nextafter(lower, -math.inf)
    records = {}
    for case, bound, target in (
        ("at_lower", lower, lower),
        ("first_interior", lower, first),
        ("second_interior", lower, second),
        ("relaxed_lower_same_template", relaxed, first),
    ):
        decl = fixtures.over_water(
            raw, fixtures.templates(raw, {"h": target}), [(DT, site, "h", "new")], availability=0.0
        )
        row = next(
            r for r in decl["model"]["operators"][0]["compartments"] if r["compartment_id"] == site
        )
        row["minimum_volume_pL"] = bound
        try:
            parse_spec(decl)
            message = None
        except ConfigError as exc:
            message = str(exc)
        records[case] = dict(
            lower_pL=bound,
            target_pL=target,
            reconstructed_pL=ref + (target - ref),
            admitted=message is None,
            refusal=message,
        )
    assert not records["at_lower"]["admitted"]
    assert (
        records["second_interior"]["admitted"]
        and records["relaxed_lower_same_template"]["admitted"]
    )
    return records


def paired_volumes():
    path = Path(__file__).with_name("data") / "cell_replacement_measurements.json"
    data = json.loads(path.read_text())["xie2020_paired_epidermal_volumes@1"]["paired_volumes"]
    parents, daughters = zip(*data, strict=True)
    changes = [d - p for p, d in data]
    return {
        "pairs": len(data),
        "decreases": sum(d < 0 for d in changes),
        "mean_parent_um3": statistics.mean(parents),
        "mean_daughter_sum_um3": statistics.mean(daughters),
        "mean_paired_change_um3": statistics.mean(changes),
        "paired_change_sample_sd_um3": statistics.stdev(changes),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--boundary-only", action="store_true", help="run only definition admission checks"
    )
    parser.add_argument(
        "--require-interior",
        action="store_true",
        help="fail if the first interior volume is refused",
    )
    args = parser.parse_args()
    report = {}
    if not args.boundary_only:
        assert jax.config.x64_enabled and jax.default_backend() == "cpu"
        report.update({f"v{v}": check_version(v) for v in (1, 2)})
        report["measured_epidermal_divisions"] = paired_volumes()
    report["boundary"] = boundary_cases()
    print(json.dumps(report, indent=2, allow_nan=False))
    if args.require_interior and not report["boundary"]["first_interior"]["admitted"]:
        raise SystemExit("strictly interior template refused")
