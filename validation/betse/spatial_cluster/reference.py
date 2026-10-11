"""Independent scalar loops, reduced Kirchhoff solve and adaptive ODE integration.

No Cells, JAX, production transport, layout or observer imports. The reference
uses active owners only, explicit per-route transfers and its own state packing.
"""

import math

import numpy as np
from scipy.integrate import solve_ivp

F = 6.02214076e23 * 1.602176634e-19
R = 6.02214076e23 * 1.380649e-23
FIELDS = (
    "amount_increment",
    "leak_transferred",
    "pump_cycles",
    "dissipated_energy_pJ",
    "gate",
    "channel_transferred",
    "junction_gate",
    "junction_transferred",
    "junction_dissipated_energy_pJ",
    "extracellular_amount_increment",
    "face_transferred",
    "face_dissipated_energy_pJ",
)


def bind(raw):
    m = raw["model"]
    cells = m["cells"]
    outside = [m["extracellular"], *m["surroundings"]]
    ids = [s["id"] for s in m["species"]]
    channels = [(i, c["channel"]) for i, c in enumerate(cells) if c["channel"] is not None]
    s, n, k, e, o, f = (
        len(ids),
        len(cells),
        len(channels),
        len(m["junctions"]),
        len(outside),
        len(m["faces"]),
    )
    shapes = ((s, n), (s, n), (n,), (n,), (2, k), (k,), (e,), (s, e), (e,), (s, o), (s, f), (f,))
    offsets = np.r_[0, np.cumsum([math.prod(shape) for shape in shapes])]
    return dict(
        raw=raw,
        model=m,
        cells=cells,
        outside=outside,
        outside_owners=np.asarray(
            [[o["id"] for o in outside].index(cell["membrane"]["outside"]) for cell in cells]
        ),
        ids=ids,
        channels=channels,
        shapes=shapes,
        offsets=offsets,
        z=np.asarray([s["valence"] for s in m["species"]]),
        rt=R * m["temperature_K"],
        initial=np.asarray([[c["cell"]["initial_amount_fmol"][s] for c in cells] for s in ids]),
        outside_initial=np.asarray([[c["initial_amount_fmol"][s] for c in outside] for s in ids]),
        volume=np.asarray([c["cell"]["volume_pL"] for c in cells]),
        outside_volume=np.asarray([c["volume_pL"] for c in outside]),
        cap=np.asarray(
            [
                c["membrane"]["area_m2"] * c["membrane"]["specific_capacitance_F_per_m2"]
                for c in cells
            ]
        ),
        v0=np.asarray([c["cell"]["initial_voltage_V"] for c in cells]),
    )


def unpack(c, y):
    return {
        name: y[..., a:b].reshape((*y.shape[:-1], *shape))
        for name, shape, a, b in zip(
            FIELDS, c["shapes"], c["offsets"][:-1], c["offsets"][1:], strict=True
        )
    }


def flatten(c, values):
    arrays = []
    for name, shape in zip(FIELDS, c["shapes"], strict=True):
        a = np.asarray(values[name])[(..., *(slice(0, n) for n in shape))]
        arrays.append(a.reshape((*a.shape[: -len(shape)], math.prod(shape))))
    return np.concatenate(arrays, axis=-1)


def initial(c):
    y = np.zeros(c["offsets"][-1])
    v = unpack(c, y)
    for i, (_, ch) in enumerate(c["channels"]):
        v["gate"][:, i] = [ch["initial_gate"][k] for k in ("m", "h")]
    for i, edge in enumerate(c["model"]["junctions"]):
        v["junction_gate"][i] = edge["gate"]["initial_gate"]
    return y


def voltage(c, delta):
    return c["v0"] + F * 1e-15 / c["cap"] * np.sum(c["z"][:, None] * delta, axis=-2)


def bernoulli(x):
    if abs(x) < 1e-5:
        return 1 - x / 2 + x * x / 12 - x**4 / 720 + x**6 / 30240
    return x / math.expm1(x)


def bulk(c, outside):
    faces, ids, rt = c["model"]["faces"], c["ids"], c["rt"]
    names = [o["id"] for o in c["outside"]]
    n, nf = len(names), len(faces)
    incidence = np.zeros((n, nf))
    means, logs, factor = (np.zeros((len(ids), nf)) for _ in range(3))
    for j, edge in enumerate(faces):
        a, b = names.index(edge["sender"]), names.index(edge["receiver"])
        incidence[a, j], incidence[b, j] = 1.0, -1.0
        for s, name in enumerate(ids):
            left, right = outside[s, a], outside[s, b]
            if left == right:
                mean, log = left, 0.0
            else:
                log = math.log1p((left - right) / right)
                mean = (left - right) / log
            means[s, j], logs[s, j] = mean, log
            factor[s, j] = edge["diffusivity_m2_per_s"][name] * edge["area_m2"] / edge["length_m"]
    weight = means * factor
    conductance = F * F / rt * np.sum(c["z"][:, None] ** 2 * weight, axis=0)
    diffusion = F * np.sum(c["z"][:, None] * weight * logs, axis=0)
    matrix = (incidence * conductance) @ incidence.T
    target = -incidence @ diffusion
    gauge = names.index(c["model"]["closure"]["gauge_reference"])
    free = [i for i in range(n) if i != gauge]
    potential = np.zeros(n)
    if free:
        potential[free] = np.linalg.solve(matrix[np.ix_(free, free)], target[free])
    mu = rt * logs + c["z"][:, None] * F * (potential @ incidence)
    flux = weight / (rt * 1e-15) * mu
    power = 1e-3 * np.sum(flux * mu, axis=0)
    current = F * 1e-15 * np.sum(c["z"][:, None] * flux, axis=0)
    current_scale = max(
        np.max(np.abs(diffusion), initial=0),
        np.max(np.abs(conductance * (potential @ incidence)), initial=0),
    )
    if (
        not np.isfinite(flux).all()
        or np.max(np.abs(incidence @ current), initial=0) > 1e-23 + 2e-12 * current_scale
    ):
        raise ValueError("Independent field residual or finite-value failure")
    return potential, flux, power, incidence


def control_at(raw, t):
    result = {}
    for kind in ("membrane", "channel", "junction"):
        for group in raw["experiment"][kind + "_controls"]:
            key = group[kind + "_id"]
            for name in ("leak", "pump") if kind == "membrane" else ("schedule",):
                result[key, name] = next(p for p in reversed(group[name]) if p["time"] <= t)
    return result


def rhs(c, control, y, *, inside_amount=None, coupled_field=None):
    v = unpack(c, y)
    answer = np.zeros_like(y)
    d = unpack(c, answer)
    ci = (c["initial"] + v["amount_increment"] if inside_amount is None else inside_amount) / c[
        "volume"
    ]
    co = (c["outside_initial"] + v["extracellular_amount_increment"]) / c["outside_volume"]
    vm = voltage(c, v["amount_increment"])
    if min(ci.min(), co.min()) <= 0 or not np.isfinite(y).all():
        raise ValueError("Independent reference left positive inventory domain")
    owners = c["outside_owners"]
    field_values = None if coupled_field is None else coupled_field(c, ci, co, vm, v, control)
    mu = c["rt"] * np.log(ci / co[:, owners]) + c["z"][:, None] * F * vm
    for i, entry in enumerate(c["cells"]):
        owner = owners[i]
        p = entry["membrane"]
        leak_control = control[p["id"], "leak"]["multipliers"]
        for s, name in enumerate(c["ids"]):
            x = c["z"][s] * F * vm[i] / c["rt"]
            d["leak_transferred"][s, i] = (
                p["area_m2"]
                * p["passive"]["permeability_m_per_s"][name]
                * leak_control[name]
                / 1e-15
                * (co[s, owner] * bernoulli(x) - ci[s, i] * bernoulli(-x))
            )
        membrane = d["leak_transferred"][:, i].copy()
        power = float(np.dot(membrane, mu[:, i]))
        pump = p["pump"]
        if pump is not None:
            pools = pump["metabolism"]
            na, k = (c["ids"].index(pump["roles"][name]) for name in ("sodium", "potassium"))
            drive = pools["delta_g0_J_per_mol"] + c["rt"] * math.log(
                pools["adp_mM"] * pools["pi_mM"] / (1000 * pools["atp_mM"])
            )
            affinity = drive - 3 * mu[na, i] + 2 * mu[k, i]
            saturation = (
                ci[na, i] ** 3
                / (ci[na, i] ** 3 + pump["km_na_mM"] ** 3)
                * co[k, owner] ** 2
                / (co[k, owner] ** 2 + pump["km_k_mM"] ** 2)
                * pools["atp_mM"]
                / (pools["atp_mM"] + pump["km_atp_mM"])
            )
            cycles = (
                pump["capacity_fmol_per_s"]
                * control[p["id"], "pump"]["multiplier"]
                * saturation
                * (-math.expm1(affinity / c["rt"]))
            )
            d["pump_cycles"][i] = cycles
            membrane[na] -= 3 * cycles
            membrane[k] += 2 * cycles
            power += cycles * affinity
        d["amount_increment"][:, i] += membrane
        d["extracellular_amount_increment"][:, owner] -= membrane
        d["dissipated_energy_pJ"][i] = -1e-3 * power
    for j, (i, ch) in enumerate(c["channels"]):
        targets = (
            1 / (1 + math.exp(-(vm[i] + 0.0060) / 0.0064)),
            1 / (1 + math.exp((vm[i] + 0.0253) / 0.0035)),
        )
        tau = (0.008330 - 0.1163 * vm[i], 1.620000 - 15.500 * vm[i])
        d["gate"][:, j] = (targets - v["gate"][:, j]) / tau
        s = c["ids"].index(ch["species_id"])
        x = c["z"][s] * F * vm[i] / c["rt"]
        permeability = (
            ch["max_permeability_m_per_s"]
            * ch["abundance"]
            * np.prod(v["gate"][:, j])
            * control[ch["id"], "schedule"]["availability"]
        )
        flux = (
            c["cells"][i]["membrane"]["area_m2"]
            * permeability
            / 1e-15
            * (co[s, owners[i]] * bernoulli(x) - ci[s, i] * bernoulli(-x))
        )
        d["channel_transferred"][j] = flux
        d["amount_increment"][s, i] += flux
        d["extracellular_amount_increment"][s, owners[i]] -= flux
        d["dissipated_energy_pJ"][i] -= 1e-3 * flux * mu[s, i]
    cell_names = [entry["cell"]["id"] for entry in c["cells"]]
    for j, edge in enumerate(c["model"]["junctions"]):
        a, b = (cell_names.index(edge[k]) for k in ("from_cell", "to_cell"))
        dv = vm[a] - vm[b] if field_values is None else field_values["junction_voltage_V"][j]
        g = edge["gate"]
        shift = 1000 * (abs(dv) - g["threshold_voltage_V"])
        alpha = 0.0013 * math.exp(-0.077 * shift)
        beta = 0.0013 * math.exp(0.14 * shift)
        beta /= 1 + 50 * beta
        gate = v["junction_gate"][j]
        d["junction_gate"][j] = 1000 * (
            alpha * (1 - gate) - beta * (gate - g["minimum_open_fraction"])
        )
        availability = control[edge["id"], "schedule"]["open_fraction"]
        for s, name in enumerate(c["ids"]):
            x = c["z"][s] * F * dv / c["rt"]
            flux = (
                edge["area_m2"]
                * edge["permeability_m_per_s"][name]
                * gate
                * availability
                / 1e-15
                * (ci[s, a] * bernoulli(-x) - ci[s, b] * bernoulli(x))
            )
            d["junction_transferred"][s, j] = flux
            d["amount_increment"][s, a] -= flux
            d["amount_increment"][s, b] += flux
            d["junction_dissipated_energy_pJ"][j] += (
                1e-3 * flux * (c["rt"] * math.log(ci[s, a] / ci[s, b]) + c["z"][s] * F * dv)
            )
    if field_values is None:
        _, flux, power, incidence = bulk(c, co)
    else:
        flux, power = (
            field_values[k] for k in ("face_flux_fmol_per_s", "face_dissipation_rate_pJ_per_s")
        )
        incidence = np.zeros((len(c["outside"]), len(c["model"]["faces"])))
        names = [o["id"] for o in c["outside"]]
        for j, face in enumerate(c["model"]["faces"]):
            incidence[names.index(face["sender"]), j] = 1
            incidence[names.index(face["receiver"]), j] = -1
    d["face_transferred"][:] = flux
    d["face_dissipated_energy_pJ"][:] = power
    d["extracellular_amount_increment"] -= flux @ incidence.T
    return answer


def integrate(raw, setting, *, rhs_cap=100000, evaluate_rhs=rhs):
    c = bind(raw)
    times = np.asarray(raw["experiment"]["observation_times"])
    boundaries = {0.0, raw["experiment"]["end_time"]}
    for kind in ("membrane", "channel", "junction"):
        for group in raw["experiment"][kind + "_controls"]:
            for key in ("leak", "pump") if kind == "membrane" else ("schedule",):
                boundaries.update(p["time"] for p in group[key])
    boundaries = sorted(boundaries)
    value = initial(c)
    output = np.empty((len(times), len(value)))
    calls, steps = 0, 0
    for start, end in zip(boundaries[:-1], boundaries[1:], strict=True):
        controls = control_at(raw, start)

        def evaluate(t, y, controls=controls):
            nonlocal calls
            calls += 1
            if calls > rhs_cap:
                raise ValueError("Independent reference RHS budget exceeded")
            return evaluate_rhs(c, controls, y)

        result = solve_ivp(
            evaluate,
            (start, end),
            value,
            method=setting["method"],
            rtol=setting["rtol"],
            atol=setting["atol"],
            max_step=setting["max_step_s"],
            dense_output=True,
        )
        if not result.success or not np.isfinite(result.y).all():
            raise ValueError("Independent adaptive integration failed: " + result.message)
        selected = (times >= start) & (times <= end)
        output[selected] = result.sol(times[selected]).T
        value = result.y[:, -1]
        steps += len(result.t) - 1
    return dict(times_s=times.tolist(), state=output.tolist(), rhs_calls=calls, steps=steps)
