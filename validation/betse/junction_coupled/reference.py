"""Independent free-voltage gate/transport ODE; no production Cells imports."""

import importlib.util
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

_spec = importlib.util.spec_from_file_location(
    "independent_junction_transport", Path(__file__).parents[1] / "junction_trajectory/reference.py"
)
transport = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(transport)


def bind(raw):
    model = raw["model"]
    ids = [s["id"] for s in model["species"]]
    cells, edges = model["cells"], model["junctions"]
    if any(
        c["membrane"]["pump"] is not None
        or c["channel"] is not None
        or any(c["membrane"]["passive"]["permeability_m_per_s"].values())
        for c in cells
    ):
        raise ValueError("This independent reference requires junction-only transport")
    names = [c["cell"]["id"] for c in cells]
    senders = np.asarray([names.index(e["from_cell"]) for e in edges])
    receivers = np.asarray([names.index(e["to_cell"]) for e in edges])
    incidence = np.zeros((len(cells), len(edges)))
    incidence[senders, np.arange(len(edges))] = -1
    incidence[receivers, np.arange(len(edges))] = 1
    groups = {g["junction_id"]: g["schedule"] for g in raw["experiment"]["junction_controls"]}
    return {
        "initial_amount_fmol": np.asarray(
            [[c["cell"]["initial_amount_fmol"][s] for c in cells] for s in ids]
        ),
        "volume_pL": np.asarray([c["cell"]["volume_pL"] for c in cells]),
        "initial_voltage_V": np.asarray([c["cell"]["initial_voltage_V"] for c in cells]),
        "capacitance_F": np.asarray(
            [
                c["membrane"]["area_m2"] * c["membrane"]["specific_capacitance_F_per_m2"]
                for c in cells
            ]
        ),
        "senders": senders,
        "receivers": receivers,
        "incidence": incidence,
        "valence": np.asarray([s["valence"] for s in model["species"]]),
        "permeability_m_s": np.asarray(
            [[e["permeability_m_per_s"][s] for e in edges] for s in ids]
        ),
        "edge_area_m2": np.asarray([e["area_m2"] for e in edges]),
        "temperature_K": model["temperature_K"],
        "F": 6.02214076e23 * 1.602176634e-19,
        "R": 6.02214076e23 * 1.380649e-23,
        "threshold": np.asarray([e["gate"]["threshold_voltage_V"] for e in edges]),
        "minimum": np.asarray([e["gate"]["minimum_open_fraction"] for e in edges]),
        "initial_gate": np.asarray([e["gate"]["initial_gate"] for e in edges]),
        "schedules": [groups[e["id"]] for e in edges],
        "end": raw["experiment"]["end_time"],
    }


def unpack(c, y):
    e = len(c["initial_gate"])
    return (*transport.unpack(c, y[..., :-e]), y[..., -e:])


def rhs(c, availability, y):
    delta, _, _, gate = unpack(c, y)
    concentration = (c["initial_amount_fmol"] + delta) / c["volume_pL"]
    voltage = transport.voltage(c, delta)
    dv = voltage[c["senders"]] - voltage[c["receivers"]]
    if np.min(concentration) <= 0 or np.max(np.abs(dv)) > 0.120:
        raise ValueError("Independent coupled reference left its physical domain")
    flux, power = transport.edge_rates(c | {"opening": availability * gate}, concentration, voltage)
    offset_mV = 1000 * (np.abs(dv) - c["threshold"])
    alpha = 0.0013 * np.exp(-0.077 * offset_mV)
    beta = 0.0013 * np.exp(0.14 * offset_mV)
    beta = beta / (1 + 50 * beta)
    derivative = 1000 * (alpha * (1 - gate) - beta * (gate - c["minimum"]))
    return np.concatenate(((flux @ c["incidence"].T).ravel(), flux.ravel(), power, derivative))


def integrate(c, settings, times, method):
    count = c["initial_amount_fmol"].size + c["permeability_m_s"].size + len(c["initial_gate"])
    value = np.r_[np.zeros(count), c["initial_gate"]]
    result = np.empty((len(times), len(value)))
    boundaries = sorted({0.0, c["end"], *(r["time"] for g in c["schedules"] for r in g)})
    steps = 0
    for start, end in zip(boundaries[:-1], boundaries[1:], strict=True):
        availability = np.asarray(
            [
                next(r["open_fraction"] for r in reversed(g) if r["time"] <= start)
                for g in c["schedules"]
            ]
        )
        answer = solve_ivp(
            lambda t, y, availability=availability: rhs(c, availability, y),
            (start, end),
            value,
            method=method,
            rtol=settings["rtol"],
            atol=settings["atol"],
            max_step=settings["max_step_s"],
            dense_output=True,
        )
        if not answer.success or not np.isfinite(answer.y).all():
            raise ValueError("Independent coupled reference failed: " + answer.message)
        chosen = (times >= start) & (times <= end)
        result[chosen] = answer.sol(times[chosen]).T
        value = answer.y[:, -1]
        steps += len(answer.t) - 1
    return result, steps


def physical(history):
    size = len(history.amount_increment)
    return np.concatenate(
        (
            np.asarray(history.amount_increment).reshape(size, -1),
            np.asarray(history.junction_transferred).reshape(size, -1),
            np.asarray(history.junction_dissipated_energy_pJ),
            np.asarray(history.junction_gate),
        ),
        axis=-1,
    )


def difference(c, actual, expected):
    da, ta, ea, ga = unpack(c, actual)
    db, tb, eb, gb = unpack(c, expected)
    maximum = transport.maximum
    return {
        "voltage_V": maximum(transport.voltage(c, da) - transport.voltage(c, db)),
        "amount_fmol": max(maximum(da - db), maximum(ta - tb)),
        "energy_pJ": maximum(ea - eb),
        "gate": maximum(ga - gb),
    }
