"""Independent, instantaneous source-coordinate pair equations (SPEC-003).

No Cells or BITSEY imports. Not a production model, integrator, or physical EMT
calibration. The polynomial regulatory oracle predates this coupling contract.
"""

import json
from pathlib import Path

import numpy as np

from tests.reference_emt import reference_rhs

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "configs/reference/source_emt_pair_panel_v1.json"
PRIMARY = ("Na", "K", "Cl", "miR200_total", "Zeb_mRNA_total", "ZEB_prot")
CONTEXT = ("P", "snail", "ST")
PACKET = (
    "Na",
    "K",
    "Cl",
    "P",
    "snail",
    "miR200_total",
    "Zeb_mRNA_total",
    "ZEB_prot",
    "miR200_free",
    "bound0",
    "bound1",
    "bound2",
    "bound3",
    "bound4",
    "bound5",
    "bound6",
    "ST",
)
PRIMARY_INDEX = [PACKET.index(name) for name in PRIMARY]
CONTEXT_INDEX = [PACKET.index(name) for name in CONTEXT]
DERIVED_INDEX = list(range(8, 16))
Z = np.array([1.0, 1.0, -1.0])
CONTROL_SHAPES = {"leak": (3, 2), "pump": (2,), "ion_contact": (), "mirna_contact": ()}


def load_panel(path=PANEL):
    panel = json.loads(Path(path).read_text())
    if panel["schema_version"] != 1 or panel["model_contract"] != "bitsey_emt_pair@1-design":
        raise ValueError("Unexpected reference panel identity")
    if tuple(panel["primary_rows"]) != PRIMARY or tuple(panel["context_rows"]) != CONTEXT:
        raise ValueError("Reference row semantics differ")
    return panel


def checked_array(value, shape, name, *, positive=False, upper=None):
    a = np.asarray(value, dtype=np.float64)
    if a.shape != shape or not np.isfinite(a).all() or np.any(a < 0):
        raise ValueError(f"Invalid {name}")
    if (positive and np.any(a <= 0)) or (upper is not None and np.any(a > upper)):
        raise ValueError(f"Outside {name} domain")
    return a


def validate_state(primary, context):
    primary = checked_array(primary, (6, 2), "primary")
    context = checked_array(context, (3, 2), "context")
    checked_array(primary[:3], (3, 2), "ionic concentration", positive=True)
    if np.any(primary[:3] < 1e-6) or np.any(primary[:3] > 1000):
        raise ValueError("Outside bounded ionic design domain")
    if np.any(primary[3:] > 1000) or np.any(context[1] > 1000):
        raise ValueError("Outside bounded regulatory design domain")
    return primary, context


def initial_state(panel, case):
    if case["initial"] == "prepared":
        packets = [cell["raw_packet"] for cell in panel["preparation"]["cells"]]
        if any(set(packet) != set(PACKET[:-1]) for packet in packets) or len(packets) != 2:
            raise ValueError("Incomplete prepared source packet")
        primary = np.array([[packet[name] for packet in packets] for name in PRIMARY])
        context = np.array([[packet["P"], packet["snail"], 0.0] for packet in packets]).T
    else:
        data = panel["constructed_initials"][case["initial"]]
        primary, context = np.array(data["primary"]), np.array(data["context"])
    return validate_state(primary, context)


def controls_at(panel, case, time=0):
    if not np.isfinite(time) or time < 0 or time > case["end_time"]:
        raise ValueError("Outside case time span")
    controls = dict(panel["default_controls"])
    changes = [case.get("controls", {})]
    previous = 0
    for event in case.get("events", []):
        if not np.isfinite(event["time"]) or not previous < event["time"] < case["end_time"]:
            raise ValueError("Events must be strictly ordered and internal")
        previous = event["time"]
        if event["time"] <= time:
            changes.append(event["set"])
        # Validate future changes too, not only the currently active controls.
        for name, value in event["set"].items():
            if name not in CONTROL_SHAPES:
                raise ValueError("Unknown control")
            checked_array(value, CONTROL_SHAPES[name], name, upper=1)
    for change in changes:
        if set(change) - CONTROL_SHAPES.keys():
            raise ValueError("Unknown control")
        controls.update(change)
    if set(controls) != CONTROL_SHAPES.keys():
        raise ValueError("Incomplete controls")
    return {
        name: checked_array(value, CONTROL_SHAPES[name], name, upper=1)
        for name, value in controls.items()
    }


def geometry(panel):
    p = panel["parameters"]
    area = 4 * np.pi * p["cell_r"] ** 2
    volume = (4 / 3) * np.pi * p["cell_r"] ** 3
    return area, volume


def voltage(primary, context, panel):
    p = panel["parameters"]
    area, volume = geometry(panel)
    return (Z @ primary[:3] - context[0]) * p["F"] * volume / (area * p["cm"])


def derived_packet(primary, context):
    """Reconstruct plotting caches; never treat them as integrated coordinates."""
    primary, context = validate_state(primary, context)
    packet = np.zeros((17, 2))
    packet[PRIMARY_INDEX] = primary
    packet[CONTEXT_INDEX] = context
    packet[8] = primary[3]
    r = primary[3] / 40
    packet[9:16] = primary[4] * r[None, :] ** np.arange(7)[:, None] / (1 + r) ** 6
    return packet


def membrane_flux(primary, vm, diffusion, controls, panel):
    p = panel["parameters"]
    bath = np.asarray(panel["bath_ions"])
    # Independent Bernoulli form, retaining the source's all-element epsilon.
    x = Z[:, None] * vm * (p["F"] / (p["R"] * p["T"])) + 1e-25
    bernoulli_negative = x / -np.expm1(-x)
    leak = (
        diffusion
        / p["tm"]
        * bernoulli_negative
        * (bath[:, None] * np.exp(-x) - primary[:3])
        * controls["leak"]
    )
    nai, ki = primary[:2]
    nao, ko = bath[:2]
    # Activity product rearranged from the native individual 1e-3 factors.
    omega = (p["cADP"] * p["cPi"] / p["cATP"]) * 1e-3 * (nao / nai) ** 3 * (ki / ko) ** 2
    reverse_ratio = omega * np.exp((p["deltaGATP"] - p["F"] * vm) / (p["R"] * p["T"]))
    sat_na = (nai / p["KmNK_Na"]) ** 3
    sat_k = (ko / p["KmNK_K"]) ** 2
    sat_atp = p["cATP"] / p["KmNK_ATP"]
    cycle = (
        p["alpha_NaK"]
        * (sat_na / (1 + sat_na))
        * (sat_k / (1 + sat_k))
        * (sat_atp / (1 + sat_atp))
        * (1 - reverse_ratio)
        * controls["pump"]
        * np.any(diffusion > 0, axis=0)
    )
    pump = np.array([-3.0, 2.0, 0.0])[:, None] * cycle
    return leak, pump, cycle


def upwind_flux(values, valence, diffusion, delta_v, edge, panel):
    p = panel["parameters"]
    start, end = edge
    x = np.asarray(valence) * p["q"] * delta_v / (p["kb"] * p["T"])
    donor = np.where(x >= 0, values[:, start], values[:, end])
    return np.asarray(diffusion) / p["GJ_len"] * (values[:, start] - values[:, end] + x * donor)


def gate_scales(delta_v, panel, case):
    if case["gate"] is None:
        return np.ones(4)
    a1, v1, a2, v2, residual, maximum = panel["gate_parameters"][case["gate"]]
    if case.get("swap_hemichannels", False):
        a1, v1, a2, v2 = a2, v2, a1, v1
    opening = 1 / (1 + np.exp(a1 * (-delta_v - v1)) + np.exp(a2 * (delta_v - v2)))
    return np.array([residual + (maximum - residual) * opening] * 3 + [maximum * opening])


def evaluate(primary, context, panel, case, time=0):
    """Return instantaneous decomposed rates, not an integrated trajectory."""
    primary, context = validate_state(primary, context)
    controls = controls_at(panel, case, time)
    diffusion = checked_array(
        case.get("membrane_diffusion", panel["membrane_diffusion"]), (3, 2), "diffusion"
    )
    edge = case.get("edge", [0, 1])
    if edge not in ([0, 1], [1, 0]):
        raise ValueError("Expected one oriented pair edge")
    vm = voltage(primary, context, panel)
    delta_v = vm[edge[0]] - vm[edge[1]]
    p = panel["parameters"]
    if np.max(np.abs(vm)) > 0.2 or abs(delta_v) > 0.2:
        raise ValueError("Outside source voltage design domain")
    if (
        max(
            np.max(np.abs(vm)) * p["F"] / (p["R"] * p["T"]),
            abs(delta_v) * p["q"] / (p["kb"] * p["T"]),
        )
        > 50
    ):
        raise ValueError("Outside electrical exponent domain")
    leak, pump, cycle = membrane_flux(primary, vm, diffusion, controls, panel)
    local = reference_rhs(time, primary[3:], context[1])
    scales = gate_scales(delta_v, panel, case)
    ion_diffusion = checked_array(panel["junction_ion_diffusion"], (3,), "ionic contact diffusion")
    mirna_diffusion = checked_array(
        panel["junction_mirna_diffusion"], (), "miRNA contact diffusion"
    )
    ion_flux = upwind_flux(primary[:3], Z, ion_diffusion, delta_v, edge, panel)
    mir_flux = upwind_flux(primary[3:4], [-1.0], [mirna_diffusion], delta_v, edge, panel)[0]
    junction = (
        np.concatenate((ion_flux * controls["ion_contact"], [mir_flux * controls["mirna_contact"]]))
        * scales
    )
    area, volume = geometry(panel)
    contact_rate = np.zeros((6, 2))
    contact_rate[:4, edge[0]] = -junction * area / volume
    contact_rate[:4, edge[1]] = junction * area / volume
    membrane_rate = np.zeros((6, 2))
    membrane_rate[:3] = (leak + pump) * area / volume
    local_rate = np.zeros((6, 2))
    local_rate[3:] = local
    return {
        "voltage": vm,
        "delta_v": np.asarray(delta_v),
        "gate_scales": scales,
        "leak_flux": leak,
        "pump_flux": pump,
        "pump_cycle_flux": cycle,
        "local_rate": local_rate,
        "junction_flux": junction,
        "contact_rate": contact_rate,
        "membrane_rate": membrane_rate,
        "primary_rate": membrane_rate + local_rate + contact_rate,
        "packet": derived_packet(primary, context),
    }
