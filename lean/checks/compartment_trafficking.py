"""Compare a round trip through an owned compartment and trace near-depletion in a checked run."""

import argparse
import json
import math
from unittest.mock import patch

import jax
import numpy as np

from cells.definitions import pump_composite_spec as composite
from cells.definitions.specs import parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.laws.electrochemistry import CHARGE_PER_FMOL
from cells.models import pump_composite_adapter as adapter
from cells.operators import compartments, membrane_state
from cells.registry.models import get_model
from validation.tissue import membrane_trafficking_fixtures as fx


def round_trip():
    dt = fx.DT
    turn = 2 * dt
    raw = fx.pooled_cells(2, seed=0.25, end=2 * turn, observation_times=[k * dt for k in range(5)])
    plasma = fx.patch(raw, "membrane_0")
    pool = fx.patch(raw, "pool_membrane_0")
    pool["capacitance_F"] *= 2  # A returned piece has the average capacitance of the mixed pool.
    route = fx.route(
        raw, retrieval={"kir_0": 1.0, "nav_0": 2.0}, recycling={"kir_0": 1.0, "nav_0": 0.5}
    )
    rate = 0.3 * plasma["area_m2"] / turn
    plan = fx.schedule(route["id"], [(0.0, rate), (turn, 0.0)], [(0.0, 0.0), (turn, rate)])
    spec = parse_spec(fx.with_trafficking(raw, [route], [plan]))
    model = get_model(spec.model)
    initial, p = model.initial_values(spec)
    owned = next(op for op in spec.model.operators if op.law == compartments.LAW_ID)
    identities = compartments.identity_map(spec.model, owned)
    assert [(r["owner"]["cell"], r["storage"]["node"]) for r in identities] == [
        ("cell_0", "pool_0"),
        ("cell_1", "pool_1"),
    ]
    assert all(
        r["membrane"]["inside"]["id"] == r["owner"]["cell"]
        and r["membrane"]["outside"]["id"] == r["id"]
        for r in identities
    )
    si, bi = int(p.trafficking_route_plasma[0]), int(p.trafficking_route_pool[0])
    a0, b0 = plasma["area_m2"], pool["area_m2"]
    c0, cb = plasma["capacitance_F"], pool["capacitance_F"]
    channels = [i for i, c in enumerate(spec.model.channels) if c.membrane_id == plasma["id"]]
    names = [spec.model.channels[i].id for i in channels]
    e = np.array([route["retrieval_enrichment"][n] for n in names])
    er = np.array([route["recycling_enrichment"][n] for n in names])
    u0 = np.asarray(membrane_state.units(initial, p, xp=np))[channels]
    bath = {n.id: i for i, n in enumerate(spec.model.extracellular)}
    peak = rate * turn
    group = u0 * (1 - (1 - peak / a0) ** e)
    z = np.asarray(spec.model.valence)
    max_material = max_voltage = max_units = 0.0
    voltages = []
    result = run(spec)
    for i, time in enumerate(result.times):
        h = result.history
        state = type(h)(*(v[i] for v in h))
        retrieved, returned = rate * min(time, turn), rate * max(time - turn, 0)
        net = retrieved - returned
        q = model.view(p, state, xp=np)
        np.testing.assert_allclose(
            q.membrane_area[[si, bi]], [a0 - net, b0 + net], atol=0, rtol=2e-15
        )
        dc = retrieved * c0 / a0 - returned * (cb + peak * c0 / a0) / (b0 + peak)
        np.testing.assert_allclose(
            q.membrane_capacitance[[si, bi]], [c0 - dc, cb + dc], atol=0, rtol=3e-15
        )
        reference = (
            u0 * (1 - (1 - retrieved / a0) ** e)
            if time <= turn
            else group * (1 - returned / (b0 + peak)) ** er
        )
        internal = state.trafficking_internalised_units[0, channels]
        surface = membrane_state.units(state, p, xp=np)[channels]
        max_units = max(
            max_units, max(abs(internal - reference)), max(abs(surface + internal - u0))
        )
        assert max_units <= 2e-10
        phi = adapter.node_potentials(state, q, xp=np)
        for identity in identities:
            owner, node, bounding = (identity[k]["slot"] for k in ("owner", "storage", "membrane"))
            # Each cell and its lumen communicate externally only with their own held bath.
            external = bath["bath_" + str(owner)]
            residual = (
                state.amount_increment[:, owner]
                + state.extracellular_amount_increment[:, node]
                - state.reservoir_supplied[:, external]
            )
            max_material = max(max_material, max(abs(residual)))
            charge = p.initial_outside_charge_C[node] + CHARGE_PER_FMOL * math.fsum(
                z * state.extracellular_amount_increment[:, node]
            )
            lumen_voltage = phi[p.active.size + node] - phi[owner]
            max_voltage = max(
                max_voltage, abs(lumen_voltage - charge / q.membrane_capacitance[bounding])
            )
            if owner == 0:
                voltages.append(float(lumen_voltage))
            else:
                assert abs(lumen_voltage) < 2e-12
    assert max_material < 2e-14 and max_voltage < 2e-12
    assert abs(voltages[2]) > 1e-3 and abs(dc) > 0.01 * c0
    kir = names.index("kir_0")
    np.testing.assert_allclose(internal[kir] / u0[kir], 0.3 * 0.25 / 0.55, rtol=3e-15)
    return dict(
        checked_steps=len(result.times) - 1,
        area_returned_m2=peak,
        initial_kir_units=u0[kir],
        kir_remaining_inside=internal[kir],
        kir_returned=group[kir] - internal[kir],
        change_in_plasma_capacitance_F=-dc,
        peak_retrieval_lumen_minus_owner_V=voltages[2],
        max_owner_species_residual_fmol=max_material,
        max_lumen_voltage_residual_V=max_voltage,
        max_population_residual_units=max_units,
    )


def uptake(enrichment):
    raw = fx.pooled_cells(seed=0.25, end=4 * fx.DT, observation_times=[k * fx.DT for k in range(5)])
    fx.patch(raw, "membrane_0")["area_m2"] = 2.0**-32
    for pop in raw["model"]["operators"][0]["populations"]:
        pop["reference_density_per_m2"] = 3.0 * 2**42
    row = fx.route(raw, retrieval={"kir_0": enrichment, "nav_0": 1.0})
    plan = fx.schedule(row["id"], [(0.0, fx.rate(raw, fraction=0.3, over=4 * fx.DT))])
    return parse_spec(fx.with_trafficking(raw, [row], [plan]))


def outcome(spec):
    try:
        result = run(spec)
    except NumericalError as error:
        return {"completed": False, "refusal": str(error)}
    return {"completed": True, "final_time_s": float(result.times[-1])}


def depletion():
    ordinary = outcome(uptake(1.0))
    assert ordinary["completed"]
    spec = uptake(1024.0)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    control = model.CONTROL_TYPE(*(v[0] for v in composite.control_values(spec, [0.0])))
    original = outcome(spec)
    step = jax.jit(model.checked_step)
    k = spec.model.species_ids.index("K")
    kir = next(i for i, channel in enumerate(spec.model.channels) if channel.id == "kir_0")
    patch_slot = int(p.channel_membranes[kir])
    declared = float(membrane_state.units(state, p, xp=np)[kir])
    assert declared == 3072
    trace = []
    for i in range(4):
        new, valid = jax.device_get(step(state, fx.DT, control, p, p.active))
        if not valid:
            break
        state = new
        count = float(membrane_state.units(state, p, xp=np)[kir])
        q = model.view(p, state, xp=np)
        obs = model.readouts(state, control, p, xp=np)
        ratio = float(q.membrane_area[patch_slot] / p.membrane_area[patch_slot])
        trace.append(
            dict(
                time_s=(i + 1) * fx.DT,
                units=count,
                retention_prediction_units=declared * ratio**1024,
                abundance=float(q.channel_abundance[kir]),
                K_flux_fmol_s=float(obs.ionic.channel_flux_fmol_s[k, kir]),
                host_readout_valid=bool(obs.valid),
            )
        )

    # A process-local diagnostic changes only the abundance readout at exactly zero units.
    prior = membrane_state.abundance

    def empty_is_zero(s, layout, *, xp):
        return xp.where(
            layout.channel_active & (membrane_state.units(s, layout, xp=xp) == 0),
            0.0,
            prior(s, layout, xp=xp),
        )

    jax.clear_caches()
    try:
        with patch.object(membrane_state, "abundance", empty_is_zero):
            zero_control = outcome(spec)
    finally:
        jax.clear_caches()
    assert zero_control["completed"]
    return dict(
        enrichment=1024,
        ordinary=ordinary,
        original=original,
        checked_step_trace=trace,
        exact_zero_control=zero_control,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-trajectory",
        action="store_true",
        help="require the unmodified depletion world and its zero-count readouts to pass",
    )
    args = parser.parse_args()
    assert jax.config.x64_enabled and jax.default_backend() == "cpu"
    report = {} if args.require_trajectory else {"cycle": round_trip()}
    report["depletion"] = issue = depletion()
    print(json.dumps(report, indent=2, allow_nan=False))
    trace = issue["checked_step_trace"]
    if args.require_trajectory and (
        not issue["original"]["completed"]
        or len(trace) != 4
        or any(
            not row["host_readout_valid"]
            or (row["units"] == 0 and (row["abundance"] != 0 or row["K_flux_fmol_s"] != 0))
            for row in trace
        )
    ):
        raise SystemExit("depletion trajectory or zero-population flux failed")
