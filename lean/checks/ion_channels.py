"""Check ten Na/K channel laws on one membrane of cells.model.resolved_pump_tissue@3."""

import json
import subprocess
from decimal import Decimal, localcontext
from functools import partial
from importlib import import_module
from itertools import product

import jax
import jax.numpy as jnp
import numpy as np
from scipy.integrate import solve_ivp

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.models import inner_laws
from cells.models import surface_pump_v3 as host
from cells.numerics import exponential_gates
from cells.registry import ids
from cells.registry import laws as registry
from cells.registry.models import get_model
from validation.betse.junction_transport.check import decimal_flux
from validation.tissue import kir_reference, kv1_reference, sodium_reference
from validation.tissue import surface_pump_v3_fixtures as fixture
from validation.tissue.surface_reference import F, R

# (kinetics, opening, permeant ion, m/h powers) from the independent equations.
REFERENCES = {
    name: (
        partial(kv1_reference.kinetics, family=family),
        partial(kv1_reference.opening, family=family),
        "K",
        (1, 2 if family == 1 else 1),
    )
    for name, family in kv1_reference.LAWS.items()
}
REFERENCES.update(
    {
        "cells.channel.kir2p1_mh2@1": (kir_reference.kinetics, kir_reference.opening, "K", (1, 2)),
        "cells.channel.nav1p2_m3h_regularized@1": (
            sodium_reference.kinetics,
            sodium_reference.opening,
            "Na",
            (3, 1),
        ),
        "cells.channel.kleak_always_open@1": (None, None, "K", (0, 0)),
        "cells.channel.naleak_always_open@1": (None, None, "Na", (0, 0)),
    }
)
DT, RELEASE, END = 2**-19, 2**-12, 2**-10
TIMES = np.array([0.0, RELEASE / 2, RELEASE, 2 * RELEASE, END])
V0 = -0.040
T = 298.15


def definition(laws):
    raw = fixture.heredity_cells(
        [(V0, 12.0, 140.0, 12.0)], dt=DT, end_time=END, observation_times=TIMES, temperature_K=T
    )
    model, experiment = raw["model"], raw["experiment"]
    patch = model["membranes"][0]
    patch["permeability_m_per_s"] = dict.fromkeys(patch["permeability_m_per_s"], 0.0)
    patch["pump"] = None
    experiment["pump_controls"] = []
    model["channels"] = []
    experiment["channel_controls"] = []
    for i, law in enumerate(laws):
        name = f"ch_{i:02d}"
        ion = REFERENCES[law.law_id][2]
        assert law.permeant == ((ion, 1, 1.0),)
        gates = [0.2 + 0.04 * i, 0.75 - 0.035 * i] if law.gated else []
        model["channels"].append(fixture.channel(name, 0, law.law_id, ion, 4e-9, 0.5, gates))
        experiment["channel_controls"].append(
            dict(
                channel_id=name,
                schedule=[
                    dict(time=0.0, availability=0.0),
                    dict(time=RELEASE, availability=0.25 + 0.05 * i),
                ],
            )
        )
    raw["execution"]["channel_capacity"] = len(laws) + 1
    return raw


def lean_declarations(laws):
    """Bind ions and powers for all laws, and coefficient tables for the five tabulated Kv laws."""
    lines = ["import CellsProofs.Transport.IonChannels", "open CellsProofs.Transport.IonChannels"]
    for law in laws:
        _, _, ion, (mp, hp) = REFERENCES[law.law_id]
        identity = ids.parts(law.law_id)
        assert (identity.namespace, identity.family, identity.major) == ("cells", "channel", 1)
        name = identity.name
        lean_ion = {"Na": "sodium", "K": "potassium"}[ion]
        lines.append(f"example : permeant .{name} = .{lean_ion} := rfl")
        lines.append(
            f"example (m h : ℝ) : opening .{name} m h = m^{mp} * h^{hp} := by unfold opening; ring"
        )
        if law.law_id not in kv1_reference.LAWS or kv1_reference.LAWS[law.law_id] == 5:
            continue
        module = import_module(registry.active().module(law.law_id))
        targets, times = [], []
        for gate in ("ACTIVATION", "INACTIVATION"):
            mid, slope = getattr(module, gate)
            targets.append(f"boltz v ({mid}) ({slope})")
            if hasattr(module, gate + "_TAU_S"):
                times.append(str(getattr(module, gate + "_TAU_S")))
            else:
                values = getattr(module, gate + "_TAU")
                if len(values) == 2:
                    intercept, slope = values
                    times.append(f"{intercept} - {slope} * v")
                else:
                    scale, mid, slope = values
                    times.append(f"{scale} * boltz v ({mid}) ({slope})")
        for decl, pair in (("targets", targets), ("times", times)):
            lines.append(f"example (v : ℝ) : {decl} .{name} v = ({', '.join(pair)}) := rfl")
    subprocess.run(["lake", "--quiet", "build", "+CellsProofs.Transport.IonChannels"], check=True)
    subprocess.run(
        ["lake", "env", "lean", "-DwarningAsError=true", "--stdin"],
        input="\n".join(lines),
        text=True,
        check=True,
    )


def stage_weights():
    """All eight gate/target corners, including the floats on either side of the series switch."""
    switch = exponential_gates.SERIES_LIMIT
    steps = np.array(
        [
            0.0,
            1e-15,
            np.nextafter(switch, 0.0),
            switch,
            np.nextafter(switch, 1.0),
            0.5,
            2.0,
            40.0,
            1000.0,
        ]
    )
    g, a, b = np.array(list(product((0.0, 1.0), repeat=3))).T[:, :, None]
    updated = np.asarray(jax.jit(exponential_gates.advance)(g, a, 1.0, b, 1.0, steps))
    weights = []
    with localcontext() as ctx:
        ctx.prec = 75
        for step in steps:
            z = Decimal.from_float(step)
            e = (-z).exp()
            end = 1 - (1 - e) / z if z else Decimal(0)
            weights.append([float(x) for x in (e, 1 - e - end, end)])
    old, start, end = np.array(weights).T
    expected = g * old + a * start + b * end
    assert np.all((updated >= 0) & (updated <= 1))
    np.testing.assert_allclose(updated, expected, atol=4 * np.finfo(float).eps, rtol=0)
    return dict(samples=updated.size, max_error=float(np.max(abs(updated - expected))))


def components(laws, structure, p):
    # Include all three NaV removable singularities and both sides of its activation series switch.
    volts = np.unique(
        [
            *(np.arange(-120, 61, 10) / 1000),
            -0.04,
            -0.065000123,
            -0.025,
            *(-0.025 + np.array([-1.01, -0.99, 0.99, 1.01]) * 0.009e-4),
        ]
    )
    codes = jnp.asarray(p.channel_laws)
    np.testing.assert_array_equal(codes[: len(laws)], [law.code for law in laws])
    vs = np.broadcast_to(volts[:, None], (len(volts), len(codes)))
    targets, times = jax.jit(lambda v: host.channel_kinetics(v, codes, structure=structure))(vs)
    pairs = np.array([(0.0, 0.0), (1.0, 1.0), (1.0, 0.0), (0.0, 1.0), (0.3, 0.7), (0.75, 0.2)])
    g = np.broadcast_to(pairs[:, :, None], (*pairs.shape, len(codes)))
    opened = jax.jit(lambda g: host.channel_opening(g, codes, structure=structure))(g)
    assert np.all((targets >= 0) & (targets <= 1)) and np.all(times > 0)
    errors = np.zeros(3)
    for i, law in enumerate(laws):
        kinetics, opening, _, _ = REFERENCES[law.law_id]
        if not kinetics:
            assert np.all(targets[:, :, i] == 0) and np.all(times[:, :, i] == 1)
            assert np.all(opened[:, i] == 1)
            continue
        expected = np.asarray([kinetics(v) for v in volts], dtype=float)
        for j, (actual, wanted) in enumerate(
            (
                (targets[:, :, i], expected[:, 0]),
                (times[:, :, i], expected[:, 1]),
                (opened[:, i], [float(opening(g)) for g in pairs]),
            )
        ):
            np.testing.assert_allclose(actual, wanted, rtol=5e-14, atol=5e-15, err_msg=law.law_id)
            errors[j] = max(errors[j], np.max(np.abs(np.asarray(actual) - wanted)))
    return dict(
        voltages=len(volts),
        gate_pairs=len(pairs),
        max_target_error=errors[0],
        max_tau_error_s=errors[1],
        max_opening_error=errors[2],
    )


def trajectory(raw):
    """Solve the one-cell material and capacitor balances from the integrated per-channel fluxes."""
    model, experiment = raw["model"], raw["experiment"]
    cell, bath, patch = model["cells"][0], model["extracellular"][0], model["membranes"][0]
    channels = model["channels"]
    count = len(channels)
    ion_index = np.array([("Na", "K").index(REFERENCES[ch["kinetic_law"]][2]) for ch in channels])
    initial = np.array([cell["initial_amount_fmol"][ion] for ion in ("Na", "K")])
    bath_conc = [bath["initial_amount_fmol"][ion] / bath["volume_pL"] for ion in ("Na", "K")]
    availability = np.array(
        [c["schedule"][1]["availability"] for c in experiment["channel_controls"]]
    )
    gates = np.array([ch["initial_gate"] or [0.0, 0.0] for ch in channels]).T
    start = np.vstack((gates, np.zeros(count))).ravel()

    def rhs(_, state, enabled):
        m, h, transfer = state.reshape(3, count)
        conc = (initial - np.bincount(ion_index, weights=transfer, minlength=2)) / cell["volume_pL"]
        voltage = V0 - transfer.sum() * F * 1e-15 / patch["capacitance_F"]
        slopes = np.zeros((3, count))
        for i, ch in enumerate(channels):
            kinetics, opening, _, _ = REFERENCES[ch["kinetic_law"]]
            if kinetics:
                target, tau = np.asarray(kinetics(voltage), dtype=float)
                slopes[:2, i] = (target - [m[i], h[i]]) / tau
            if enabled:
                weight = float(opening((m[i], h[i]))) if opening else 1.0
                ion = ion_index[i]
                slopes[2, i] = decimal_flux(
                    conc[ion],
                    bath_conc[ion],
                    voltage,
                    1,
                    T,
                    patch["area_m2"],
                    ch["max_permeability_m_per_s"],
                    1,
                    ch["abundance"] * availability[i] * weight,
                    {"F": F, "R": R},
                )
        return slopes.ravel()

    def integrate(times, state, enabled):
        sol = solve_ivp(
            rhs,
            (times[0], times[-1]),
            state,
            args=(enabled,),
            method="DOP853",
            t_eval=times,
            rtol=2e-12,
            atol=2e-15,
        )
        if not sol.success:
            raise RuntimeError(sol.message)
        return sol.y.T

    first = integrate(TIMES[TIMES <= RELEASE], start, False)
    second = integrate(TIMES[TIMES >= RELEASE], first[-1], True)
    states = np.concatenate((first[:-1], second))
    flux = [
        rhs(t, y, t >= RELEASE).reshape(3, count)[2] for t, y in zip(TIMES, states, strict=True)
    ]
    return states.reshape(len(TIMES), 3, count), np.array(flux)


def tissue(raw, spec):
    expected, flux = trajectory(raw)
    result = run(spec)
    obs = result.observations
    channels = raw["model"]["channels"]
    slots = len(channels)
    ions = [REFERENCES[ch["kinetic_law"]][2] for ch in channels]
    rows = [spec.model.species_ids.index(ion) for ion in ions]
    actual_flux = np.asarray(obs.channel_flux_fmol_s)[:, rows, np.arange(slots)]
    transfer = np.asarray(obs.channel_transferred)[:, rows, np.arange(slots)]
    gates = np.asarray(obs.channel_gate)[:, :, :slots]
    assert np.all((gates >= 0) & (gates <= 1))
    peak = np.max(abs(flux), axis=0)
    assert (peak > 0).all() and (np.sign(flux[-1]) == np.where(np.array(ions) == "Na", -1, 1)).all()
    np.testing.assert_array_equal(actual_flux[TIMES < RELEASE], 0)
    np.testing.assert_array_equal(transfer[TIMES <= RELEASE], 0)
    gated = [i for i, ch in enumerate(channels) if ch["initial_gate"]]
    assert (np.max(abs(gates[2] - gates[0]), axis=0)[gated] > 1e-6).all()
    material_atol = min(raw["execution"]["material_balance_atol_fmol"].values())
    np.testing.assert_allclose(gates, expected[:, :2], atol=2e-6, rtol=0)
    np.testing.assert_allclose(actual_flux / peak, flux / peak, atol=2e-6, rtol=0)
    np.testing.assert_allclose(transfer, expected[:, 2], atol=material_atol, rtol=0)
    off_route = np.ones(obs.channel_flux_fmol_s.shape[1:], dtype=bool)
    off_route[rows, np.arange(slots)] = False
    for data in (obs.channel_flux_fmol_s, obs.channel_transferred):
        np.testing.assert_array_equal(np.asarray(data)[:, off_route], 0)
    for ion in ("Na", "K"):
        row = spec.model.species_ids.index(ion)
        debit = -expected[:, 2, np.array(ions) == ion].sum(axis=-1)
        for value in (obs.amount_increment, obs.reservoir_supplied):
            np.testing.assert_allclose(value[:, row, 0], debit, atol=material_atol, rtol=0)
    capacitance = raw["model"]["membranes"][0]["capacitance_F"]
    voltage = V0 - expected[:, 2].sum(axis=-1) * F * 1e-15 / capacitance
    np.testing.assert_allclose(obs.membrane_voltage_V[:, 0], voltage, atol=1e-8, rtol=0)
    return dict(
        dt_s=DT,
        release_s=RELEASE,
        end_s=END,
        solver=raw["execution"]["solver"],
        max_gate_error=float(np.max(abs(gates - expected[:, :2]))),
        max_flux_error_over_channel_peak=float(np.max(abs(actual_flux - flux) / peak)),
        max_transfer_error_fmol=float(np.max(abs(transfer - expected[:, 2]))),
        final_voltage_V=float(obs.membrane_voltage_V[-1, 0]),
        final_transfer_fmol=dict(
            zip((ch["kinetic_law"] for ch in channels), transfer[-1], strict=True)
        ),
    )


if __name__ == "__main__":
    if jax.default_backend() != "cpu" or not jax.config.x64_enabled:
        raise RuntimeError("Run with JAX_PLATFORMS=cpu and JAX_ENABLE_X64=1")
    laws = sorted((inner_laws.CHANNEL_LAWS[k] for k in REFERENCES), key=lambda law: law.code)
    lean_declarations(laws)
    raw = definition(laws)
    spec = parse_spec(raw)
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    print(
        json.dumps(
            dict(
                model=raw["model"]["id"],
                stages=stage_weights(),
                components=components(laws, model.structure, p),
                tissue=tissue(raw, spec),
            ),
            indent=2,
            allow_nan=False,
        )
    )
