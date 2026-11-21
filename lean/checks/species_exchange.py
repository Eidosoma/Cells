"""Neutral saturable uptake in a finite pool, two competing cells and a red-cell rate series."""

import json
from itertools import pairwise, product
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.pump_composite_spec import control_values
from cells.definitions.specs import parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.operators import species_exchange as exchange
from cells.registry.models import get_model
from validation.core_seams.references import exact
from validation.fr1.references.forms import saturable_release
from validation.tissue import secreted_species_fixtures as fixture


def component_panel():
    rows = np.asarray(
        list(product((2**-24, 0.125, 8.0), (1 / 32, 0.5, 1, 8), (0, 1 / 64, 0.25, 0.75)))
    )
    n, ratio, dose = rows.T
    h = 0.125
    b, a = n * ratio, n * dose / h
    reference = np.array(
        [
            saturable_release(ni, ni / 2, ai, bi, [h])["n_o_fmol"][0]
            for ni, ai, bi in zip(n, a, b, strict=True)
        ]
    )
    result = {}
    compiled = jax.jit(lambda n, a, b: exchange.saturable_removed(n, a, b, h, xp=jnp))
    for backend, (moved, ok) in (
        ("numpy", exchange.saturable_removed(n, a, b, h, xp=np)),
        ("compiled", compiled(n, a, b)),
    ):
        moved = np.asarray(moved)
        left = n - moved
        assert moved.dtype == np.float64 and np.all(ok)
        assert np.all((moved >= 0) & (left > 0)) and np.all(moved[dose == 0] == 0)
        err = float(np.max(abs(left - reference) / n))
        assert err < 8 * exact.EPS
        with exact.context():
            worst = 0.0
            for ni, bi, ai, rem in zip(n, b, a, left, strict=True):
                start, end = exact.dec(ni), exact.dec(rem)
                residual = (
                    exact.dec(bi) * (start / end).ln() + start - end - exact.dec(ai) * exact.dec(h)
                )
                worst = max(worst, float(abs(residual) / start))
        assert worst < 16 * exact.EPS
        result[backend] = dict(
            cases=len(n), max_error_over_start=err, max_residual_over_start=worst
        )
    return result


def uptake_world(steps, *, reverse=False):
    end = 0.5
    rates = {"cell_0": 0.875, "cell_1": 2.625}  # fmol/s at saturation on each patch.
    contacts = [(f"contact_{i}", cell, "ecs_0") for i, cell in enumerate(rates)]
    raw = fixture.world(
        cells=(("cell_0", 0.75), ("cell_1", 1.5)),
        nodes=(("ecs_0", 2.0),),
        faces=(),
        contacts=contacts,
        dt=end / steps,
        end=end,
        concentrations_mM={"cell_0": 0.05, "cell_1": 0.1, "ecs_0": 0.5},
    )
    area = {p["id"]: p["area_m2"] for p in raw["model"]["membranes"]}
    routes, controls = [], []
    for patch, cell, _ in reversed(contacts) if reverse else contacts:
        rid = f"uptake_{cell}"
        routes.append((rid, patch, "import", "saturable"))
        controls.append((rid, cell, [(0.0, rates[cell] / area[patch], 0.25)]))
    spec = parse_spec(fixture.with_exchange(raw, routes, controls))
    hist = run(spec).history
    row = list(spec.model.species_ids).index(fixture.SPECIES)
    node = next(i for i, n in enumerate(raw["model"]["extracellular"]) if n["id"] == "ecs_0")
    gains = np.asarray(hist.amount_increment)[:, row, :]
    loss = -np.asarray(hist.extracellular_amount_increment)[:, row, node]
    moved = np.asarray(hist.exchange_moved_fmol)
    by_cell = moved[:, ::-1] if reverse else moved
    np.testing.assert_allclose(gains, -by_cell, rtol=12 * exact.EPS, atol=0)
    np.testing.assert_allclose(gains.sum(axis=1), loss, rtol=12 * exact.EPS, atol=0)
    n0, volume = 1.0, 2.0
    times = np.arange(steps + 1) * (end / steps)
    ref = saturable_release(n0, 0.0, sum(rates.values()), 0.25 * volume, times)
    left = n0 - loss
    assert np.all(left > 0) and np.all(np.diff(left) < 0)
    pool_error = float(np.max(np.abs(left - ref["n_o_fmol"])))
    assert pool_error < 16 * exact.EPS * n0
    expected = (n0 - ref["n_o_fmol"][-1]) * rates["cell_0"] / sum(rates.values())
    error = float(gains[-1, 0] - expected)
    cell_nodes = raw["model"]["cells"]
    volumes = [n["volume_pL"] for n in cell_nodes] + [volume]
    start = [n["initial_amount_fmol"][fixture.SPECIES] for n in cell_nodes] + [n0]
    # Evaluate the ideal free energy at the actual endpoints of each stored row.
    with exact.context():

        def energy(amounts):
            return sum(
                exact.dec(n) * ((exact.dec(n) / exact.dec(v)).ln() - 1)
                for n, v in zip(amounts, volumes, strict=True)
            )

        rt = exact.RT_J_per_mol(raw["model"]["temperature_K"]) * exact.dec("0.001")
        baseline = energy(start)
        ref_work = [
            float(rt * (energy([start[0] + g[0], start[1] + g[1], no]) - baseline))
            for g, no in zip(gains, left, strict=True)
        ]
    work_error = float(np.max(np.abs(np.sum(hist.exchange_work_pJ, axis=1) - ref_work)))
    assert work_error < 1e-13 * max(abs(np.asarray(ref_work)))
    return dict(
        steps=steps,
        first_route=routes[0][0],
        final_outside_fmol=float(left[-1]),
        cell0_gained_fmol=float(gains[-1, 0]),
        simultaneous_cell0_fmol=float(expected),
        cell0_error_fmol=error,
        max_pool_error_fmol=pool_error,
        max_work_error_pJ=work_error,
    )


def depletion(log_drop):
    """A single closed-pair step with a known residual and stored amount near depletion."""
    start, km, h = 1.0, 1.0, 1.0
    with exact.context():
        u = -exact.dec(log_drop)
        a = float(-u + 1 - u.exp())
    raw = fixture.face_free(pool_mM=1, node_mM=start, end=h, dt=h)
    area = next(p["area_m2"] for p in raw["model"]["membranes"] if p["id"] == "contact_0")
    spec = parse_spec(
        fixture.with_exchange(
            raw,
            [("uptake", "contact_0", "import", "saturable")],
            [("uptake", "cell_0", [(0.0, a / area, km)])],
        )
    )
    # Use the capacity represented by the model, including the rate/area unit conversion.
    actual_a = (a / area) * area
    exact_end = saturable_release(start, 1.0, actual_a, km, [h])["n_o_fmol"][0]
    row = list(spec.model.species_ids).index(fixture.SPECIES)
    node = next(i for i, n in enumerate(raw["model"]["extracellular"]) if n["id"] == "ecs_0")
    spacing = start - np.nextafter(start, 0.0)
    result = dict(
        log_drop=log_drop,
        expected_outside_fmol=float(exact_end),
        anchor_spacing_fmol=float(spacing),
    )
    try:
        hist = run(spec).history
    except NumericalError as exc:
        if exact_end >= spacing / 2 or "domain failure" not in str(exc):
            raise
        state, p = get_model(spec.model).initial_values(spec)
        controls = control_values(spec, [0.0])
        control = type(controls)(*(v[0] for v in controls))
        for i in range(2):
            before = start + state.extracellular_amount_increment[row, node]
            _, converged = exchange.saturable_removed(before, actual_a, km, h / 2, xp=np)
            assert converged
            # The rejected zero-pool trial evaluates log(0) in the energy booking.
            with np.errstate(divide="ignore", invalid="ignore"):
                state, valid = exchange.exchange_half_step(state, control, h / 2, p, xp=np)
            assert bool(valid) == (i == 0)
        assert start + state.extracellular_amount_increment[row, node] == 0
        return dict(
            result,
            admitted=False,
            both_scalar_solves_converged=True,
            final_trial_outside_fmol=0.0,
            reason=str(exc),
        )
    left = float(start + hist.extracellular_amount_increment[-1, row, node])
    moved = float(-hist.exchange_moved_fmol[-1, 0])
    assert left > 0 and abs(moved - (start - left)) <= 4 * exact.EPS * start
    assert abs(left - exact_end) <= spacing
    return dict(
        result,
        admitted=True,
        stored_outside_fmol=left,
        relative_outside_error=left / exact_end - 1,
        absolute_outside_error_fmol=abs(left - exact_end),
    )


def solver_refinement():
    """Check the residual guard on a stiff but representable depletion."""
    start = 5e-4
    a, b = 0.9999 * start, 1e-5 * start
    expected = saturable_release(start, 0.0, a, b, [1.0])["n_o_fmol"][0]
    rows = []
    for steps in (1, 32):
        n = start
        residual = None
        for _ in range(steps):
            moved, valid = exchange.saturable_removed(n, a, b, 1 / steps, xp=np)
            if not valid:
                break
            n -= moved
        if valid:
            with exact.context():
                ni, nf = exact.dec(start), exact.dec(n)
                used = exact.dec(b) * (ni / nf).ln() + ni - nf
                residual = float(abs(used - exact.dec(a)))
            # Successive doses add. The summed absolute-term scale is the
            # spent dose plus the imposed dose. Allow rounding the stored amounts.
            assert residual <= exchange.NEWTON_RTOL * (float(used) + a) + 32 * exact.EPS * start
            assert abs(n - expected) <= residual + np.spacing(expected)
        assert valid or steps == 1
        rows.append(
            dict(
                steps=steps,
                converged=bool(valid),
                final_outside_fmol=float(n) if valid else None,
                final_dose_residual_fmol=residual,
            )
        )
    return dict(reference_fmol=float(expected), runs=rows)


def measured_rates():
    data = json.loads((Path(__file__).with_name("data") / "sage2014_zero_trans.json").read_text())
    observations = {row["external_mM"]: row for row in data["points"]}
    low, high = data["fit_mM"]

    def fit(v1, v2):
        vmax = (high - low) / (high / v2 - low / v1)
        return vmax, low * (vmax / v1 - 1)

    lo, hi = observations[low], observations[high]
    vmax, km = fit(lo["rate"], hi["rate"])
    fits = [
        fit(lo["rate"] + s * lo["se"], hi["rate"] + t * hi["se"])
        for s, t in product((-1, 1), repeat=2)
    ]

    # At one reference volume unit, n=c and b=K_M. Differentiate the actual
    # scalar step at zero duration to compare rates in the authors' vertical scale.
    def uptake(h, c):
        return 1000 * exchange.saturable_removed(c, vmax / 1000, km, h, xp=jnp)[0]

    slope = jax.jit(jax.grad(uptake, argnums=0))
    rows = []
    for c in data["held_out_mM"]:
        observed = observations[c]
        predicted = float(slope(0.0, c))
        np.testing.assert_allclose(predicted, vmax * c / (km + c), rtol=4e-15)
        sens = [v * c / (k + c) for v, k in fits]
        rows.append(
            dict(
                external_mM=c,
                observed=observed["rate"],
                se=observed["se"],
                predicted=predicted,
                calibration_sensitivity=[min(sens), max(sens)],
            )
        )
    return dict(vmax=vmax, km_mM=km, held_out=rows)


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    panel = component_panel()
    worlds = []
    for reverse in (False, True):
        series = [uptake_world(s, reverse=reverse) for s in (2, 4, 8)]
        errors = [w["cell0_error_fmol"] for w in series]
        assert all(3.5 < coarse / fine < 4.5 for coarse, fine in pairwise(errors))
        worlds.extend(series)
    assert worlds[0]["cell0_error_fmol"] * worlds[3]["cell0_error_fmol"] < 0
    print(
        json.dumps(
            dict(
                component=panel,
                shared_pool=worlds,
                solver_refinement=solver_refinement(),
                depletion=[depletion(x) for x in (4, 20, 35, 38)],
                biology=measured_rates(),
            ),
            indent=2,
            allow_nan=False,
        )
    )
