"""Reproduce the whole-current Kv1.1, Kv1.4 and NaV1.2 comparisons in the evidence note.

The registered Cells laws supply the gate rates and open fractions. Each clamp
step is integrated analytically at fixed voltage and concentrations. At each
test voltage the constant-field factor cancels when normalizing current magnitude.
Sample spacings below are for model traces.
"""

import json

import numpy as np
from scipy.optimize import brentq, minimize_scalar

from cells.laws.channels import kv1p1_mh2, kv1p4_mh, nav1p2_m3h_regularized


def kinetics(law, voltage_mV):
    return law.kinetics(np.array([voltage_mV * 1e-3]), xp=np)


def gate_step(law, voltage_mV, initial, times_ms):
    target, tau_s = kinetics(law, voltage_mV)
    return target + (initial - target) * np.exp(-times_ms / (1e3 * tau_s))


def kv11_decay():
    """Ranjan et al., Figure 2C and supplementary Equation 5."""
    law = kv1p1_mh2.LAW
    step_mV, pulse_ms, spacing_ms = -20.0, 1500.0, 0.5
    times = np.arange(round(pulse_ms / spacing_ms) + 1) * spacing_ms

    def fit_from_hold(hold_mV):
        initial, _ = kinetics(law, hold_mV)
        current = law.opening(gate_step(law, step_mV, initial, times), xp=np)
        peak = np.argmax(current)
        elapsed = times[peak:] - times[peak]
        tail = current[peak:] / current[peak]

        def squared_residual(log_tau):
            # For each tau, solve for the free offset and amplitude by linear least squares.
            exponential = np.exp(-elapsed / np.exp(log_tau))
            design = np.column_stack((np.ones_like(elapsed), exponential))
            coefficients, *_ = np.linalg.lstsq(design, tail, rcond=None)
            return np.sum((design @ coefficients - tail) ** 2)

        fit = minimize_scalar(
            squared_residual, bounds=(np.log(10.0), np.log(30000.0)), method="bounded"
        )
        if not fit.success:
            raise RuntimeError(f"Kv1.1 decay fit failed at holding voltage {hold_mV} mV")
        return {
            "equilibrated_hold_mV": hold_mV,
            "fit_start_at_peak_ms": float(times[peak]),
            "model_decay_tau_ms": float(np.exp(fit.x)),
            "model_end_fraction_of_peak": float(tail[-1]),
        }

    return {
        "law": law.law_id,
        "step_mV": step_mV,
        "model_sample_spacing_ms": spacing_ms,
        "fit_end_at_pulse_end_ms": pulse_ms,
        "fit_definition": "Fit current/peak = C + A exp(-(t - t_peak)/tau) from peak to pulse end",
        "experiment": "25 °C, 313.25 ± 81.7 ms (mean ± SD), 67 cells for the panel",
        "primary_hold": fit_from_hold(-80.0),
        "holding_sensitivity": [fit_from_hold(hold) for hold in (-90.0, -70.0)],
    }


def kv14_endpoints():
    """Current remaining after the Stühmer and Roeper voltage steps from a −80 mV hold."""
    law = kv1p4_mh.LAW
    initial, _ = kinetics(law, -80.0)
    spacing_ms = 0.1
    pulses = []
    for step_mV, duration_ms in ((0.0, 3200.0), (40.0, 200.0)):
        times = np.arange(round(duration_ms / spacing_ms) + 1) * spacing_ms
        current = law.opening(gate_step(law, step_mV, initial, times), xp=np)
        peak = np.argmax(current)
        pulses.append(
            dict(
                step_mV=step_mV,
                duration_ms=duration_ms,
                peak_time_ms=float(times[peak]),
                model_end_fraction_of_peak=float(current[-1] / current[peak]),
            )
        )
    return dict(
        law=law.law_id,
        equilibrated_hold_mV=-80.0,
        model_sample_spacing_ms=spacing_ms,
        pulses=pulses,
    )


def nav12_kinetics():
    """Begemann et al., Figure 2 and Table 2."""
    law = nav1p2_m3h_regularized.LAW
    hold_mV, pulse_ms = -120.0, 10.0
    rise_spacing_ms, test_spacing_ms = 0.00025, 0.001
    rise_times = np.arange(round(pulse_ms / rise_spacing_ms) + 1) * rise_spacing_ms
    test_times = np.arange(round(pulse_ms / test_spacing_ms) + 1) * test_spacing_ms
    initial, _ = kinetics(law, hold_mV)

    current = law.opening(gate_step(law, 0.0, initial, rise_times), xp=np)
    peak = np.argmax(current)
    rising_fraction = current[: peak + 1] / current[peak]
    time_10, time_90 = np.interp([0.1, 0.9], rising_fraction, rise_times[: peak + 1])

    def test_peak(prepulse_mV):
        conditioned = gate_step(law, prepulse_mV, initial, 500.0)
        test_current = law.opening(gate_step(law, 5.0, conditioned, test_times), xp=np)
        return np.max(test_current)

    reference_peak = test_peak(hold_mV)
    midpoint_mV = brentq(lambda v: test_peak(v) / reference_peak - 0.5, hold_mV, -20.0)

    return {
        "law": law.law_id,
        "equilibrated_hold_mV": hold_mV,
        "rise_step_mV": 0.0,
        "model_rise_sample_spacing_ms": rise_spacing_ms,
        "rise_and_test_pulse_windows_ms": [0.0, pulse_ms],
        "rise_definition": "Interpolate first 10% and 90% crossings of pulse peak on rising limb",
        "model_10_to_90_rise_ms": float(time_90 - time_10),
        "prepulse_duration_ms": 500.0,
        "test_step_mV": 5.0,
        "model_test_sample_spacing_ms": test_spacing_ms,
        "midpoint_definition": (
            "Prepulse voltage yielding 50% of the +5 mV test peak after a -120 mV prepulse"
        ),
        "model_inactivation_midpoint_mV": midpoint_mV,
        "experiment": (
            "Room temperature, 0.38 ± 0.05 ms rise at 0 mV and −63.53 ± 0.79 mV fitted "
            "inactivation midpoint (mean ± SEM, n = 9 for each endpoint)"
        ),
    }


if __name__ == "__main__":
    print(
        json.dumps(
            {"kv11": kv11_decay(), "kv14": kv14_endpoints(), "nav12": nav12_kinetics()},
            indent=2,
            allow_nan=False,
        )
    )
