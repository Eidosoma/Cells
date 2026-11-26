"""Predict Kir2.1 spermine block at a second K level in the compiled FR-51 clamp.

Run with the FR-51 engine snapshot on PYTHONPATH. Each lab's first external-K
curve supplies every fit parameter. The absolute-voltage control and the two
reversal predictions share those parameters.
"""

import json
import math
from functools import partial
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
from scipy.optimize import least_squares
from scipy.special import expit
from validation.fr51.engine import raw_world

from cells.definitions.specs import parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.laws.channels import open_channel_block as block
from cells.laws.electrochemistry import CHARGE_PER_FMOL, F, R
from cells.registry.models import get_model

DATA = Path(__file__).with_name("data") / "kir_spermine_potassium.json"


def curve(v, params, thermal_mV):
    """Each midpoint is an absolute voltage in the training solution."""
    weight, mid1, mid2, z1, z2 = params
    return weight * expit((mid1 - v) * z1 / thermal_mV) + (1 - weight) * expit(
        (mid2 - v) * z2 / thermal_mV
    )


def fit_anchor(row, thermal_mV):
    v = np.asarray(row["voltage_mV"])
    y = np.asarray(row["relative"])
    midpoint, _ = half_crossing(row)
    fits = []
    for separation in (10, 25, 45):
        initial = [0.8, midpoint - 2, midpoint + separation, 4, 2]
        fit = least_squares(
            lambda p: curve(v, p, thermal_mV) - y,
            initial,
            bounds=([0, -180, -180, 0.05, 0.05], [1, 120, 120, 8, 8]),
            ftol=1e-13,
            xtol=1e-13,
            gtol=1e-13,
            max_nfev=4000,
        )
        if fit.success:
            fits.append(fit)
    return min(fits, key=lambda f: f.cost).x


def half_crossing(row):
    """Bracket and interpolate half of the paper's conductance reference."""
    v, y = np.array(row["voltage_mV"]), np.array(row["relative"])
    assert np.all(np.diff(v) > 0) and np.all((y > 0) & (y <= 1))
    indices = np.flatnonzero((y[:-1] >= 0.5) & (y[1:] < 0.5))
    assert len(indices) == 1
    i = indices[0]
    crossing = v[i] + (v[i + 1] - v[i]) * (0.5 - y[i]) / (y[i + 1] - y[i])
    return float(crossing), v[i : i + 2].tolist()


def rms(observed, predicted):
    return float(np.sqrt(np.mean((observed - predicted) ** 2)))


def clamp_ratios(ci, co, temp, blocker, params, anchor_root, voltage_mV):
    """Free, reversal-referenced and voltage-referenced Kir2.1 on one patch."""
    raw = raw_world("P1_K_equal", blocked=False)
    m = raw["model"]
    m["temperature_K"] = temp
    valence = {s["id"]: s["valence"] for s in m["species"]}
    for node, concentration in ((m["cells"][0], ci), (m["extracellular"][0], co)):
        amounts = node["initial_amount_fmol"]
        amounts["K"] = concentration * node["volume_pL"]
        node["fixed_charge_equivalent_fmol"] = node.get("initial_charge_C", 0) / CHARGE_PER_FMOL - (
            math.fsum(valence[s] * amount for s, amount in amounts.items())
        )
    weight, mid1, mid2, z1, z2 = params
    thermal = 1000 * R * temp / F

    def declaration(reference, training_reference):
        modes = [
            dict(
                weight=float(w),
                effective_valence=float(z),
                k0_mM=float(blocker * math.exp(z * (mid - training_reference) / thermal)),
            )
            for w, mid, z in ((weight, mid1, z1), (1 - weight, mid2, z2))
            if w > 0
        ]
        return dict(
            law=block.LAW_ID,
            blocker=dict(id="spermine", valence=4, side="inside", concentration_mM=blocker),
            reference=reference,
            modes=modes,
        )

    ch = dict(m["channels"][0], kinetic_law="cells.channel.kir2p1_mh2@1", initial_gate=[0.7, 0.6])
    m["channels"] = [
        dict(ch, id="blocked", block=declaration({"reversal_of": "K"}, anchor_root)),
        dict(ch, id="free"),
        dict(ch, id="voltage", block=declaration(block.MEMBRANE_VOLTAGE, 0.0)),
    ]
    raw["experiment"]["channel_controls"] = [
        dict(channel_id=ch["id"], schedule=[dict(time=0, availability=1.0)]) for ch in m["channels"]
    ]
    raw["execution"]["channel_capacity"] = 3
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, layout = model.initial_values(spec)
    control = model.Control(*(v[0] for v in control_values(spec, [0.0])))
    clamp = jax.jit(
        jax.vmap(
            partial(model.clamped_channel_flux, xp=jnp, block=True), in_axes=(None, None, None, 0)
        )
    )
    _, current, terms = clamp(state, control, layout, jnp.asarray(voltage_mV) / 1000)
    current = np.asarray(current)
    assert np.all(np.isfinite(current)) and np.all(current[:, 1] != 0)
    ratios = current[:, [0, 2]] / current[:, [1]]
    np.testing.assert_allclose(ratios, np.asarray(terms.block.u)[:, [0, 2]], rtol=3e-13, atol=0)
    return ratios


def external(study):
    anchor, *evaluations = study["conditions"]
    temp, ci = study["temperature_K"], study["internal_K_mM"]
    blocker = study["declared_spermine_mM"]
    thermal = 1000 * R * temp / F
    params = fit_anchor(anchor, thermal)
    anchor_root = 1000 * block.reversal_potential(ci, anchor["external_K_mM"], 1, temp)
    anchor_v = np.asarray(anchor["voltage_mV"])
    anchor_half, anchor_bracket = half_crossing(anchor)
    anchor_y = np.asarray(anchor["relative"])
    calibration = clamp_ratios(
        ci, anchor["external_K_mM"], temp, blocker, params, anchor_root, anchor_v
    )
    np.testing.assert_allclose(calibration[:, 0], curve(anchor_v, params, thermal), rtol=4e-13)
    np.testing.assert_allclose(calibration[:, 0], calibration[:, 1], rtol=4e-13)
    results = []
    for row in evaluations:
        co = row["external_K_mM"]
        root = 1000 * block.reversal_potential(ci, co, 1, temp)
        native_shift = root - anchor_root
        measured_shift = row["measured_reversal_mV"] - anchor["measured_reversal_mV"]
        voltages, obs = np.asarray(row["voltage_mV"]), np.asarray(row["relative"])
        # All shift comparisons use identical observations in the anchor's sampled
        # voltage range. Omit ratios within 2 mV of measured or calculated reversal.
        mask = (np.abs(voltages - root) > 2) & (np.abs(voltages - row["measured_reversal_mV"]) > 2)
        for shift in (native_shift, measured_shift):
            mask &= (voltages - shift >= anchor_v.min()) & (voltages - shift <= anchor_v.max())
        v, y = voltages[mask], obs[mask]
        assert len(v) >= 3
        # At the physical commands, read both references. In the measured-shift
        # diagnostic, the command correction makes V − E correspond to the
        # measured displacement. Only the normalized ratio transfers.
        shifts = np.array([native_shift, measured_shift, 0.0])
        commands = np.r_[v, v + native_shift - measured_shift]
        ratios = clamp_ratios(ci, co, temp, blocker, params, anchor_root, commands)
        predictions = np.stack((ratios[: len(v), 0], ratios[len(v) :, 0], ratios[: len(v), 1]))
        np.testing.assert_allclose(
            predictions, curve(v - shifts[:, None], params, thermal), rtol=5e-13
        )
        half, bracket = half_crossing(row)
        half_shift = half - anchor_half
        results.append(
            dict(
                external_K_mM=co,
                measured_reversal_mV=row["measured_reversal_mV"],
                cells_reversal_mV=float(root),
                measured_shift_mV=measured_shift,
                cells_shift_mV=float(native_shift),
                half_voltage_mV=half,
                half_bracket_mV=bracket,
                half_shift_mV=half_shift,
                half_shift_per_measured_reversal_mV=half_shift / measured_shift,
                voltage_mV=v.tolist(),
                observed=y.tolist(),
                excluded_mV=voltages[~mask].tolist(),
                predictions={
                    name: dict(relative=pred.tolist(), rms_absolute_fraction=rms(y, pred))
                    for name, pred in zip(
                        ("cells", "measured", "absolute_voltage"), predictions, strict=True
                    )
                },
                interpolated_anchor_rmse={
                    name: rms(y, np.interp(v - shift, anchor_v, anchor_y))
                    for name, shift in (("cells", native_shift), ("measured", measured_shift))
                },
            )
        )
    return dict(
        fit_external_K_mM=anchor["external_K_mM"],
        fit_measured_reversal_mV=anchor["measured_reversal_mV"],
        fit_cells_reversal_mV=float(anchor_root),
        fit_half_voltage_mV=anchor_half,
        fit_half_bracket_mV=anchor_bracket,
        fit_parameters_weight_mid1_mid2_z1_z2=params.tolist(),
        fit_rms_absolute_fraction=rms(anchor_y, calibration[:, 0]),
        evaluations=results,
    )


def internal(study):
    ci1, ci2 = study["internal_K_mM"]
    co, temp = study["external_K_mM"], study["temperature_K"]
    roots = 1000 * block.reversal_potential(np.array([ci1, ci2]), co, 1, temp)
    shift = float(roots[1] - roots[0])
    e1, e2 = study["figure_reversal_mV"]
    v1, v2 = study["figure_half_block_mV"]
    # The midpoint translation holds for any positive steepness. Five is an
    # admitted illustrative effective valence, not an estimate for this patch.
    predicted = v1 + shift
    ratios = clamp_ratios(
        ci2, co, temp, 0.020, [1, v1, v1, 5, 5], roots[0], np.array([predicted, v1])
    )
    np.testing.assert_allclose([ratios[0, 0], ratios[1, 1]], 0.5, atol=2e-14, rtol=0)
    return dict(
        figure_half_block_shift_mV=v2 - v1,
        figure_reversal_shift_mV=e2 - e1,
        cells_shift_mV=shift,
        absolute_voltage_shift_mV=0,
        compiled_half_fractions=[float(ratios[0, 0]), float(ratios[1, 1])],
        figure_regression_slope=study["reported_internal_slope"],
    )


if __name__ == "__main__":
    assert jax.config.x64_enabled and jax.default_backend() == "cpu"
    data = json.loads(DATA.read_text())
    print(
        json.dumps(
            dict(
                panama=external(data["panama2006_external_k"]),
                ishihara=external(data["ishihara2007_external_k"]),
                lopatin=internal(data["lopatin1996_internal_k"]),
            ),
            indent=2,
            allow_nan=False,
        )
    )
