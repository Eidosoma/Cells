"""Pure, static conditioned-voltage algebra; not a production cell or integrator."""

import math
from dataclasses import asdict, dataclass, replace
from itertools import product

BOLTZMANN = 1.380649e-23
ELEMENTARY_CHARGE = 1.602176634e-19


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def thermal_voltage_mV(temperature_K):
    temperature = finite(temperature_K, "temperature_K")
    if temperature <= 0:
        raise ValueError("Temperature must be positive")
    thermal = 1000 * BOLTZMANN * temperature / ELEMENTARY_CHARGE
    if not math.isfinite(thermal) or thermal <= 0:
        raise ValueError("Thermal voltage outside finite positive domain")
    return thermal


@dataclass(frozen=True)
class Reading:
    identity: str
    potassium_mM: float
    voltage_mV: float
    reading_bound_mV: float

    def __post_init__(self):
        if not isinstance(self.identity, str) or not self.identity.strip():
            raise ValueError("Reading needs an identity")
        if finite(self.potassium_mM, "potassium_mM") < 0:
            raise ValueError("Potassium cannot be negative")
        finite(self.voltage_mV, "voltage_mV")
        if finite(self.reading_bound_mV, "reading_bound_mV") < 0:
            raise ValueError("Reading bound cannot be negative")


@dataclass(frozen=True)
class Curve:
    a_dimensionless: float
    b_per_mM: float
    temperature_K: float
    dose_domain_mM: tuple[float, float]

    def __post_init__(self):
        finite(self.a_dimensionless, "a")
        finite(self.b_per_mM, "b")
        thermal_voltage_mV(self.temperature_K)
        if not isinstance(self.dose_domain_mM, tuple) or len(self.dose_domain_mM) != 2:
            raise ValueError("Dose domain must be an immutable pair")
        low, high = (finite(x, "domain endpoint") for x in self.dose_domain_mM)
        if not 0 <= low < high:
            raise ValueError("Dose domain must be nonnegative and increasing")
        for dose in (low, high):
            self.voltage_at(dose)

    def voltage_at(self, potassium_mM):
        dose = finite(potassium_mM, "potassium_mM")
        if not self.dose_domain_mM[0] <= dose <= self.dose_domain_mM[1]:
            raise ValueError("Dose outside declared domain")
        argument = self.a_dimensionless + self.b_per_mM * dose
        if not math.isfinite(argument) or argument <= 0:
            raise ValueError("Nonpositive or nonfinite logarithm argument")
        result = thermal_voltage_mV(self.temperature_K) * math.log(argument)
        return finite(result, "predicted voltage")


def fit_two_points(first, second, temperature_K, dose_domain_mM):
    """Only fitting readings enter this function; no evaluation voltage is accepted."""
    if first.identity == second.identity or first.potassium_mM >= second.potassium_mM:
        raise ValueError("Need two distinct, increasing-dose fitting readings")
    thermal = thermal_voltage_mV(temperature_K)
    try:
        z1 = math.exp(first.voltage_mV / thermal)
        z2 = math.exp(second.voltage_mV / thermal)
    except OverflowError as error:
        raise ValueError("Fitting exponent outside finite positive domain") from error
    if not all(math.isfinite(z) and z > 0 for z in (z1, z2)):
        raise ValueError("Fitting exponent outside finite positive domain")
    slope = (z2 - z1) / (second.potassium_mM - first.potassium_mM)
    curve = Curve(z1 - slope * first.potassium_mM, slope, temperature_K, dose_domain_mM)
    curve.voltage_at(first.potassium_mM)
    curve.voltage_at(second.potassium_mM)
    return curve


def reading_corners(first, second):
    for sign1, sign2 in product((-1, 1), repeat=2):
        yield (
            replace(first, voltage_mV=first.voltage_mV + sign1 * first.reading_bound_mV),
            replace(second, voltage_mV=second.voltage_mV + sign2 * second.reading_bound_mV),
        )


def forecast(first, second, target_potassium_mM, temperature_K, dose_domain_mM):
    """Prediction and full-box reading sensitivity, without a target measurement."""
    curve = fit_two_points(first, second, temperature_K, dose_domain_mM)
    prediction = curve.voltage_at(target_potassium_mM)
    corners = []
    for point1, point2 in reading_corners(first, second):
        corner_curve = fit_two_points(point1, point2, temperature_K, dose_domain_mM)
        voltage = corner_curve.voltage_at(target_potassium_mM)
        corners.append(
            {
                "fit_readings_mV": [point1.voltage_mV, point2.voltage_mV],
                "curve": asdict(corner_curve),
                "prediction_mV": voltage,
                "change_from_first_fit_mV": voltage - point1.voltage_mV,
            }
        )
    voltages = [corner["prediction_mV"] for corner in corners]
    changes = [corner["change_from_first_fit_mV"] for corner in corners]
    return {
        "fit_ids": [first.identity, second.identity],
        "fit_readings": [asdict(first), asdict(second)],
        "curve": asdict(curve),
        "thermal_voltage_mV": thermal_voltage_mV(temperature_K),
        "target_potassium_mM": target_potassium_mM,
        "prediction_mV": prediction,
        "prediction_reading_box_mV": [min(voltages), max(voltages)],
        "change_from_first_fit_mV": prediction - first.voltage_mV,
        "change_reading_box_mV": [min(changes), max(changes)],
        "reading_corners": corners,
    }


def compare_prediction(prediction, measured):
    """Attach an evaluation reading to an already computed forecast; never refit."""
    if measured.identity in prediction["fit_ids"]:
        raise ValueError("An evaluation reading cannot be a fitting reading")
    if measured.potassium_mM != prediction["target_potassium_mM"]:
        raise ValueError("Evaluation dose does not match forecast")
    first = Reading(**prediction["fit_readings"][0])
    low = measured.voltage_mV - measured.reading_bound_mV
    high = measured.voltage_mV + measured.reading_bound_mV
    predicted_low, predicted_high = prediction["prediction_reading_box_mV"]
    error = prediction["prediction_mV"] - measured.voltage_mV
    no_response_error = first.voltage_mV - measured.voltage_mV
    return {
        "evaluation_id": measured.identity,
        "measured_voltage_mV_approx": measured.voltage_mV,
        "measured_reading_bound_mV": measured.reading_bound_mV,
        "measured_reading_box_mV": [low, high],
        "signed_error_mV": error,
        "absolute_error_mV": abs(error),
        "signed_error_reading_box_mV": [predicted_low - high, predicted_high - low],
        "measured_change_from_first_fit_mV_approx": measured.voltage_mV - first.voltage_mV,
        "measured_change_reading_box_mV": [
            low - (first.voltage_mV + first.reading_bound_mV),
            high - (first.voltage_mV - first.reading_bound_mV),
        ],
        "no_response": {
            "prediction_mV": first.voltage_mV,
            "prediction_reading_box_mV": [
                first.voltage_mV - first.reading_bound_mV,
                first.voltage_mV + first.reading_bound_mV,
            ],
            "change_mV": 0.0,
            "change_reading_box_mV": [0.0, 0.0],
            "signed_error_mV": no_response_error,
            "absolute_error_mV": abs(no_response_error),
            "signed_error_reading_box_mV": [
                first.voltage_mV - first.reading_bound_mV - high,
                first.voltage_mV + first.reading_bound_mV - low,
            ],
        },
        "biological_acceptance": "not_assessable",
        "confidence_interval": False,
    }
