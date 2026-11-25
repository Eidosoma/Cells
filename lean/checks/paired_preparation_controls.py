"""Compare reported preparation inputs with native channel, pump and binding laws."""

import json
import math
from pathlib import Path

import clamped_channel_current as clamp
import jax
import jax.numpy as jnp
import numpy as np
from paired_law_replays import kir_slopes
from paired_membrane_physiology import proton_flux, proton_reversals, root_mV

from cells.definitions.specs import parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.laws.electrochemistry import F, R
from cells.laws.pumps import proton_pump
from cells.laws.reactions import rapid_binding
from cells.registry.models import get_model

DATA = Path(__file__).with_name("data")


@jax.jit
def pump_flux(voltage, cyt, lumen, temperature, n, calibrated_dg0):
    # ATP is supplied at 5 mM. Fixed positive ADP and Pi set a reference for the fitted
    # energy offset. They cancel when comparing the roots within a fixed-fuel series.
    state = proton_pump.Inputs(
        10 ** (3 - cyt), 10 ** (3 - lumen), voltage, 5.0, 1.0, 1.0, temperature
    )
    params = proton_pump.Parameters(1.0, n, 1e-4, 0.1, calibrated_dg0, cyt, 0.1)
    return proton_pump.kinetics(state, params, 1.0, xp=jnp).cycles_fmol_s


def plant_reversals(study):
    cyt = study["cytosolic_pH"]
    anchor, *observed = study["Erev_mV"]
    assert study["lumen_pH"][0] == cyt
    output = []
    for temp in (293.15, 298.15):
        predictions = []
        for n in (1, 2, 3, 4):
            log_q = math.log(1 / (5.0 * proton_pump.STANDARD_STATE_mM))
            dg0 = n * F * anchor * 1e-3 - R * temp * log_q
            roots = [root_mV(pump_flux, cyt, ph, temp, n, dg0) for ph in study["lumen_pH"]]
            np.testing.assert_allclose(roots[0], anchor, atol=1e-9, rtol=0)
            predictions.append(roots)
        np.testing.assert_allclose(np.ptp(predictions, axis=0), 0.0, atol=1e-9)
        output.append({"temperature_K": temp, "anchored_mV": predictions[0]})
    return {"observed_mV": [anchor, *observed], "conditional_predictions": output}


@jax.jit
def oxygen_occupancy(pressure_over_p50):
    # At one temperature and in one medium the oxygen solubility cancels in pO2/P50.
    # Express this activity in units of the preparation's own Kd for the two form weights.
    u = jnp.log(pressure_over_p50[None, :])
    _, forms = rapid_binding.speciation(
        u,
        jnp.ones_like(u),
        jnp.zeros((1, 2)),
        jnp.array([[[0], [1]]]),
        jnp.ones((1, 2), dtype=bool),
        xp=jnp,
    )
    return forms[0, 1]


def myoglobin(studies):
    human, horse = studies["rossi1958"], studies["schenkman1997"]
    pressure = np.array(human["pressure_Torr"])
    predicted = np.asarray(oxygen_occupancy(pressure / human["fit_P50_Torr"]))
    evaluation = human["evaluation_indices"]
    assert not set(evaluation) & set(human["fit_indices"])
    delta = predicted[evaluation] - np.array(human["occupancy"])[evaluation]
    p50 = horse["P50_Torr"]
    half = float(oxygen_occupancy(jnp.array([p50]) / p50)[0])
    np.testing.assert_allclose(half, 0.5, atol=1e-14)
    return {
        "human_evaluation_occupancy": predicted[evaluation].tolist(),
        "human_evaluation_RMSE": float(np.sqrt(np.mean(delta**2))),
        "equine_fraction_at_fitted_P50": half,
    }


def kir_availability_control():
    raw = clamp.specimen(1.0)
    index = next(
        i for i, ch in enumerate(raw["model"]["channels"]) if ch["kinetic_law"] == "kir2p1_mh2@1"
    )
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, layout = model.initial_values(spec)
    control = model.Control(*(v[0] for v in control_values(spec, [0.0])))
    voltage = jnp.array([-0.020, -0.010, 0.010, 0.020])

    @jax.jit
    def currents(availability):
        fixed = control._replace(channel=control.channel * availability)
        return jax.vmap(
            lambda v: model.clamped_channel_flux(state, fixed, layout, v, xp=jnp)[1][index]
        )(voltage)

    free = np.asarray(currents(1.0))
    assert np.all(free != 0)
    relative = np.asarray(currents(0.5)) / free
    np.testing.assert_allclose(relative, 0.5, rtol=2e-14)
    return {"voltage_mV": (1000 * voltage).tolist(), "half_over_full": relative.tolist()}


def main():
    assert jax.config.x64_enabled and jax.default_backend() == "cpu"
    studies = json.loads((DATA / "paired_preparation_controls.json").read_text())
    data = json.loads((DATA / "paired_replay_measurements.json").read_text())
    kir = data["ishihara2018_kir21_unitary@1"]
    assert kir["external_K_mM"] == studies["ishihara2018"]["nominal_K_mM"]
    kir["external_K_mM"] = studies["ishihara2018"]["total_K_mM"]
    ramsey = studies["ramsey2006"]
    cherny = studies["cherny1995"]
    nominal = root_mV(proton_flux, 10**-3.5, 10**-4.5, cherny["temperature_C"] + 273.15)
    steep, other = studies["ishihara2004"], studies["panama2006"]
    z = [
        1000 * R * (273.15 + t) / (F * steep["mV_per_efold"]) for t in steep["temperature_range_C"]
    ]
    assert min(z) > steep["blocker_charge"] and other["effective_valence"] > steep["blocker_charge"]
    return {
        "kir_slope_ratios_at_total_K": kir_slopes(data),
        "cherny_mV_per_pH": {
            "nominal": nominal,
            "observed": cherny["measured_mV_per_bath_minus_pipette_pH"],
        },
        "ramsey": [proton_reversals(ramsey, "Erev_mV", t) for t in ramsey["temperature_range_C"]],
        "plant_pump": plant_reversals(studies["rienmuller2012"]),
        "myoglobin": myoglobin(studies),
        "native_kir_prescribed_availability": kir_availability_control(),
        "spermine_fit_conversion": {
            "ishihara_effective_valence_range": z,
            "panama_mV_per_efold": 1000
            * R
            * other["fit_temperature_K"]
            / (F * other["effective_valence"]),
        },
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, allow_nan=False))
