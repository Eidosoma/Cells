"""Independent ordered setters, full-node transport and 80-digit bath accounting.

No Cells or JAX imports. Scalar Decimal setters do not use the production
last-writer coefficient compiler. Physical budgets use original declared
anchors and explicit owner loops, including the initial controller operation.
"""

import ast
import hashlib
import math
from copy import deepcopy
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np

from validation.tissue import surface_dynamics_reference as passive
from validation.tissue import surface_kinetic_reference as active

F, R = active.F, active.R
ORDER = ("K_env", "Cl_env", "Na_env")
EXTRA = (
    "bath_events",
    "bath_site_ids",
    "enabled_Cl",
    "phase",
    "timing_policy",
    "controller_policy",
    "baseline_policy",
)
PARENTS = {
    "resolved_passive_bath_events@1": "resolved_tissue@1",
    "resolved_active_bath_events@1": "resolved_tissue@12",
}


def decimal(value):
    return Decimal(str(float(value)))


def parent_definition(raw):
    value = deepcopy(raw)
    value["model"]["id"] = PARENTS[value["model"]["id"]]
    for key in EXTRA:
        value["model"].pop(key)
    return value


def bind(raw):
    m = raw["model"]
    if (
        m["timing_policy"] != "phase_clock_rk_stage_native_logistic@1"
        or m["controller_policy"] != "explicit_ideal_reservoir_dose_voltage_compensation_work@1"
        or m["baseline_policy"] != "each_declared_reservoir_reference_concentration@1"
        or m["phase"] not in ("INIT", "SIM")
        or type(m["enabled_Cl"]) is not bool
    ):
        raise ValueError("Unsupported bath controllers")
    sites = m["bath_site_ids"]
    owners = {v["id"]: v for v in m["extracellular"]}
    if (
        type(sites) is not list
        or len(sites) != len(set(sites))
        or any(v not in owners or not owners[v]["reservoir"] for v in sites)
    ):
        raise ValueError("Baths require explicit unique ideal reservoirs")
    events = m["bath_events"]
    kinds = [v["kind"] for v in events]
    if kinds != [v for v in ORDER if v in kinds] or events and not sites:
        raise ValueError("Require ordered unique native bath setters and targets")
    valence = {v["id"]: v["valence"] for v in m["species"]}
    for event in events:
        if (
            any(
                isinstance(event[k], bool)
                or not isinstance(event[k], (float, int))
                or not math.isfinite(event[k])
                for k in ("on_s", "off_s", "change_s", "amplitude")
            )
            or not 0 <= event["on_s"] < event["off_s"] <= raw["experiment"]["end_time"]
            or event["change_s"] <= 0
        ):
            raise ValueError("Invalid bath window/amplitude")
        if event["kind"] == "Cl_env" and not m["enabled_Cl"]:
            continue
        ion = event["kind"].split("_")[0]
        other = "Na" if ion == "Cl" else "M"
        for name in (ion, other):
            if valence.get(name) != (1 if name in ("Na", "K") else -1):
                raise ValueError("Missing or incompatible ion/counterion")
    is_active = PARENTS[m["id"]] == "resolved_tissue@12"
    module = active if is_active else passive
    parent = module.bind(parent_definition(raw))
    shapes = parent["shapes"] | {
        "reservoir_chemical_work_pJ": (len(m["extracellular"]),),
        "phase_clock_s": (1,),
    }
    context = dict(raw=deepcopy(raw), parent=parent, shapes=shapes, active=is_active)
    # Independent conservative all-pulse positivity bound, after last writes.
    for name in sites:
        row = owners[name]
        coefficients = {v: 0.0 for v in valence}
        for event in events:
            if event["kind"] == "Cl_env" and not m["enabled_Cl"]:
                continue
            ion = event["kind"].split("_")[0]
            other = "Na" if ion == "Cl" else "M"
            amount = event["amplitude"] * row["initial_amount_fmol"][ion]
            coefficients[ion] = coefficients[other] = amount
        if any(
            not math.isfinite(coefficients[ion])
            or row["initial_amount_fmol"][ion] + min(0, coefficients[ion]) <= 0
            or not math.isfinite(row["initial_amount_fmol"][ion] + max(0, coefficients[ion]))
            for ion in valence
        ):
            raise ValueError("Bath program leaves positive finite inventory")
    return context


def initial(c):
    module = active if c["active"] else passive
    return np.r_[
        module.initial(c["parent"]), np.zeros(c["shapes"]["reservoir_chemical_work_pJ"]), 0.0
    ]


def flatten(c, fields):
    return passive.flatten(c, fields)


def unpack(c, flat):
    return passive.unpack(c, flat)


def program(c, time):
    m = c["raw"]["model"]
    species = [v["id"] for v in m["species"]]
    outside = [v["id"] for v in m["extracellular"]]
    shape = (len(species), len(outside))
    dose, rate = np.zeros(shape), np.zeros(shape)
    pulse = np.zeros(3)
    with localcontext() as ctx:
        ctx.prec = 80
        for event in m["bath_events"]:
            if m["phase"] != "SIM" or event["kind"] == "Cl_env" and not m["enabled_Cl"]:
                continue
            gain = Decimal(10) / decimal(event["change_s"])
            a = 1 / (1 + (-gain * (decimal(time) - decimal(event["on_s"]))).exp())
            b = 1 / (1 + (-gain * (decimal(time) - decimal(event["off_s"]))).exp())
            p, dp = a - b, gain * (a * (1 - a) - b * (1 - b))
            pulse[ORDER.index(event["kind"])] = float(p)
            ion = event["kind"].split("_")[0]
            other = "Na" if ion == "Cl" else "M"
            for name in m["bath_site_ids"]:
                j = outside.index(name)
                owner = m["extracellular"][j]
                # Literal baseline overwrite: each later setter replaces both
                # named rows; it does not add to an earlier counterion dose.
                coefficient = decimal(event["amplitude"]) * decimal(
                    owner["initial_amount_fmol"][ion]
                )
                for row in (species.index(ion), species.index(other)):
                    dose[row, j], rate[row, j] = float(coefficient * p), float(coefficient * dp)
        charge, current, chemical, chemical_rate = (np.zeros(len(outside)) for _ in range(4))
        for j, owner in enumerate(m["extracellular"]):
            owner_charge, owner_current = Decimal(0), Decimal(0)
            for i, ion in enumerate(species):
                n0, dn, ndot = (
                    decimal(v) for v in (owner["initial_amount_fmol"][ion], dose[i, j], rate[i, j])
                )
                volume = decimal(owner["volume_pL"])
                if n0 + dn <= 0:
                    raise ValueError("Nonpositive programmed bath")
                owner_charge += decimal(F) * Decimal("1e-15") * m["species"][i]["valence"] * dn
                owner_current += decimal(F) * Decimal("1e-15") * m["species"][i]["valence"] * ndot
                chemical[j] += float(
                    Decimal("0.001")
                    * decimal(R)
                    * decimal(m["temperature_K"])
                    * ((n0 + dn) * (((n0 + dn) / volume).ln() - 1) - n0 * ((n0 / volume).ln() - 1))
                )
                chemical_rate[j] += float(
                    Decimal("0.001")
                    * decimal(R)
                    * decimal(m["temperature_K"])
                    * ((n0 + dn) / volume).ln()
                    * ndot
                )
            charge[j], current[j] = float(owner_charge), float(owner_current)
    voltage = np.asarray([v["boundary_potential_V"] for v in m["extracellular"]])
    electric, electric_rate = 1e12 * voltage * charge, 1e12 * voltage * current
    return dict(
        pulse=pulse,
        dose_fmol=dose,
        dose_rate_fmol_s=rate,
        charge_C=charge,
        charge_rate_A=current,
        chemical_work_pJ=chemical,
        chemical_power_pJ_s=chemical_rate,
        electrochemical_work_pJ=chemical + electric,
        electrochemical_power_pJ_s=chemical_rate + electric_rate,
        electrode_work_pJ=-electric,
        electrode_power_pJ_s=-electric_rate,
    )


def current_context(c, time, *, held_time=None):
    current = dict(c["parent"])
    s = program(c, time)
    current["ao"] = current["ao"] + s["dose_fmol"]
    current["qo"] = current["qo"] + s["charge_C"]
    if held_time is not None:
        current["raw"] = deepcopy(current["raw"])
        for kind in ("membrane", "junction", "channel", "pump"):
            for group in current["raw"]["experiment"].get(kind + "_controls", []):
                a = next(
                    v["availability"] for v in reversed(group["schedule"]) if v["time"] <= held_time
                )
                group["schedule"] = [dict(time=0.0, availability=a)]
    return current, s


def evaluate(c, state, *, held_time=None):
    values = unpack(c, state)
    time = float(values["phase_clock_s"][0])
    current, s = current_context(c, time, held_time=held_time)
    parent_flat = passive.flatten(current, values)
    module = active if c["active"] else passive
    slope, phi, proof = module.evaluate(current, parent_flat, time)
    d = module.unpack(current, slope)
    chemical = (
        1e-3
        * R
        * current["layout"]["temperature"]
        * np.sum(np.log(current["ao"] / current["vo"]) * d["reservoir_supplied"], axis=0)
    )
    return np.r_[slope, chemical, 1.0], phi, proof | dict(program=s)


def physical_fields(c, state):
    values = {k: np.array(v, copy=True) for k, v in unpack(c, state).items()}
    s = program(c, float(values["phase_clock_s"][0]))
    values["extracellular_amount_increment"] += s["dose_fmol"]
    values["reservoir_supplied"] += s["dose_fmol"]
    values["electrode_charge_transferred_C"] -= s["charge_C"]
    values["reservoir_work_pJ"] += s["electrochemical_work_pJ"]
    values["electrode_work_pJ"] += s["electrode_work_pJ"]
    values["reservoir_chemical_work_pJ"] += s["chemical_work_pJ"]
    return values


def _membrane_total(c, values):
    m = c["raw"]["model"]
    species = [v["id"] for v in m["species"]]
    mids = [v["id"] for v in m["membranes"]]
    total = np.array(values["membrane_transferred"], copy=True)
    if c["active"]:
        for j, population in enumerate(m["channels"]):
            total[:, mids.index(population["membrane_id"])] += values["channel_transferred"][:, j]
        for j, patch in enumerate(m["membranes"]):
            if patch["pump"] is not None:
                roles = patch["pump"]["roles"]
                total[species.index(roles["sodium"]), j] += 3 * values["pump_cycles"][j]
                total[species.index(roles["potassium"]), j] -= 2 * values["pump_cycles"][j]
    return total


def field_observables(c, state, slope, phi, *, held_time=None):
    values, d = (unpack(c, v) for v in (state, slope))
    time = float(values["phase_clock_s"][0])
    current, s = current_context(c, time, held_time=held_time)
    m, p = current["raw"]["model"], current["layout"]
    stage = passive.stage(current, passive.flatten(current, values), time)
    if c["active"]:
        stage["junction_open"] = np.asarray(stage["junction_open"]) * values["junction_gate"]
    matrix, nodes, reservoir, _, floating, _ = active.electrical.topology(stage)
    z = np.asarray(p["valence"])
    n = len(m["cells"])
    ionic = (
        F
        * 1e-15
        * np.sum(z * np.c_[d["amount_increment"], d["extracellular_amount_increment"]], axis=0)
    )
    pins = ~nodes | reservoir
    for group in floating:
        pins[group[0]] = True
    free = np.flatnonzero(~pins)
    dv = np.zeros_like(phi)
    dv[free] = np.linalg.solve(matrix[np.ix_(free, free)], ionic[free])
    inside, outside = ([v["id"] for v in m[k]] for k in ("cells", "extracellular"))
    voltage, vdot = (
        np.asarray(
            [
                v[inside.index(row["inside"])] - v[n + outside.index(row["outside"])]
                for row in m["membranes"]
            ]
        )
        for v in (phi, dv)
    )
    chemical = (
        1e-3
        * R
        * m["temperature_K"]
        * (
            np.sum(np.log(stage["ci"]) * d["amount_increment"])
            + np.sum(np.log(stage["co"]) * d["extracellular_amount_increment"])
        )
    )
    capacitor = 1e12 * np.sum(
        [
            row["capacitance_F"] * v * rate
            for row, v, rate in zip(m["membranes"], voltage, vdot, strict=True)
        ]
    )
    heat = sum(float(np.sum(v)) for k, v in d.items() if k.endswith("_dissipated_energy_pJ"))
    rw, ew = (float(np.sum(d[k])) for k in ("reservoir_work_pJ", "electrode_work_pJ"))
    metabolic = float(np.sum(d["metabolic_work_pJ"])) if c["active"] else 0.0
    return dict(
        membrane_flux_fmol_s=_membrane_total(c, d),
        membrane_voltage_V=voltage,
        membrane_voltage_rate_V_s=vdot,
        junction_flux_fmol_s=d["junction_transferred"],
        face_flux_fmol_s=d["face_transferred"],
        reservoir_supply_fmol_s=d["reservoir_supplied"] + s["dose_rate_fmol_s"],
        electrode_current_A=d["electrode_charge_transferred_C"] - s["charge_rate_A"],
        electrode_charge_C=np.where(
            p["reservoir"],
            (matrix @ phi)[n:]
            - current["qo"]
            - F * 1e-15 * np.sum(z * values["extracellular_amount_increment"], axis=0),
            0.0,
        ),
        chemical_energy_rate_pJ_s=chemical + s["chemical_power_pJ_s"].sum(),
        capacitor_energy_rate_pJ_s=capacitor,
        dissipation_pJ_s=heat,
        reservoir_power_pJ_s=rw + s["electrochemical_power_pJ_s"].sum(),
        electrode_power_pJ_s=ew + s["electrode_power_pJ_s"].sum(),
        # The reversible controller cancels analytically. Evaluate transport's
        # residual separately to avoid subtracting large prescribed source powers.
        energy_balance_pJ_s=chemical + capacitor + heat - rw - ew - metabolic,
    )


def conservation(c, state):
    """Independent original-anchor material, capacitor, electrode and work proof."""
    values = physical_fields(c, state)
    transport = unpack(c, state)
    dose = program(c, float(transport["phase_clock_s"][0]))["dose_fmol"]
    m, p = c["parent"]["raw"]["model"], c["parent"]["layout"]
    ci, co = ([v["id"] for v in m[k]] for k in ("cells", "extracellular"))
    di, do = values["amount_increment"], values["extracellular_amount_increment"]
    local, outside = np.array(di, copy=True), np.array(do, copy=True)
    total = _membrane_total(c, values)
    for j, route in enumerate(m["membranes"]):
        local[:, ci.index(route["inside"])] += total[:, j]
        outside[:, co.index(route["outside"])] -= total[:, j]
    for kind, rows, ledger in (
        ("junction", local, "junction_transferred"),
        ("face", outside, "face_transferred"),
    ):
        names = ci if kind == "junction" else co
        for j, route in enumerate(m[kind + "s"]):
            rows[:, names.index(route["sender"])] += values[ledger][:, j]
            rows[:, names.index(route["receiver"])] -= values[ledger][:, j]
    outside -= values["reservoir_supplied"]
    stage = passive.stage(c["parent"], passive.initial(c["parent"]), 0.0)
    matrix, nodes, reservoir, _, floating, _ = active.electrical.topology(stage)
    pins = ~nodes | reservoir
    for group in floating:
        pins[group[0]] = True
    free = np.flatnonzero(~pins)
    initial_phi = np.r_[np.zeros(len(ci)), [v["boundary_potential_V"] for v in m["extracellular"]]]
    q0 = np.r_[c["parent"]["qi"], c["parent"]["qo"]]
    initial_phi[free] = np.linalg.solve(
        matrix[np.ix_(free, free)],
        q0[free] - matrix[np.ix_(free, np.flatnonzero(pins))] @ initial_phi[pins],
    )
    # Keep the declared additive controller and saved transport contributions
    # separate until the residual has been formed. Rounding their physical
    # totals first can erase a small transported charge beside a large dose.
    # These sums use the independent ordered-setter dose and every saved ion
    # and electrode ledger; they do not replace a measured residual with zero.
    with localcontext() as ctx:
        ctx.prec = 80
        scale = decimal(F) * Decimal("1e-15")

        def ionic_charge(amounts, extra=None):
            return [
                scale
                * sum(
                    (
                        decimal(ion["valence"])
                        * (
                            decimal(amounts[i, j])
                            + (decimal(extra[i, j]) if extra is not None else 0)
                        )
                        for i, ion in enumerate(m["species"])
                    ),
                    Decimal(0),
                )
                for j in range(amounts.shape[1])
            ]

        delta_charge = ionic_charge(transport["amount_increment"]) + ionic_charge(
            transport["extracellular_amount_increment"], dose
        )
        controller_charge = ionic_charge(dose)
        supplied_charge = ionic_charge(transport["reservoir_supplied"], dose)
        electrode_charge = [
            decimal(value) - programmed
            for value, programmed in zip(
                transport["electrode_charge_transferred_C"], controller_charge, strict=True
            )
        ]
        global_charge = float(sum(electrode_charge) + sum(supplied_charge))
    delta_q = np.asarray([float(value) for value in delta_charge])
    dv = np.zeros_like(initial_phi)
    dv[free] = np.linalg.solve(matrix[np.ix_(free, free)], delta_q[free])
    cap = matrix @ dv
    n = len(ci)
    with localcontext() as ctx:
        ctx.prec = 80
        electrode = np.asarray(
            [
                float(
                    value - (decimal(cap[n + j]) - delta_charge[n + j] if p["reservoir"][j] else 0)
                )
                for j, value in enumerate(electrode_charge)
            ]
        )
        chemical, electric = Decimal(0), Decimal(0)
        for owners, delta in ((m["cells"], di), (m["extracellular"], do)):
            for j, owner in enumerate(owners):
                for i, species in enumerate(m["species"]):
                    a = decimal(owner["initial_amount_fmol"][species["id"]])
                    d, volume = decimal(delta[i, j]), decimal(owner["volume_pL"])
                    if a + d <= 0:
                        raise ValueError("Nonpositive physical inventory")
                    chemical += (
                        Decimal("0.001")
                        * decimal(R)
                        * decimal(m["temperature_K"])
                        * ((a + d) * (((a + d) / volume).ln() - 1) - a * ((a / volume).ln() - 1))
                    )
        for patch in m["membranes"]:
            i, j = ci.index(patch["inside"]), n + co.index(patch["outside"])
            v0, change = decimal(initial_phi[i] - initial_phi[j]), decimal(dv[i] - dv[j])
            electric += (
                Decimal("0.5e12") * decimal(patch["capacitance_F"]) * change * (2 * v0 + change)
            )
        heat = sum(
            (
                decimal(v)
                for k, row in values.items()
                if k.endswith("_dissipated_energy_pJ")
                for v in row.flat
            ),
            Decimal(0),
        )
        work = sum(
            (
                decimal(v)
                for k in ("reservoir_work_pJ", "electrode_work_pJ")
                for v in values[k].flat
            ),
            Decimal(0),
        )
        if c["active"]:
            work += sum((decimal(v) for v in values["metabolic_work_pJ"].flat), Decimal(0))
        energy = float(chemical + electric + heat - work)
    supply_charge = np.asarray([float(value) for value in supplied_charge])
    voltage = np.asarray([v["boundary_potential_V"] for v in m["extracellular"]])
    return dict(
        local_fmol=local,
        outside_fmol=outside,
        global_fmol=di.sum(axis=1) + do.sum(axis=1) - values["reservoir_supplied"].sum(axis=1),
        capacitor_charge_C=np.where(nodes & ~reservoir, cap - delta_q, 0.0),
        electrode_charge_C=electrode,
        global_charge_C=global_charge,
        energy_residual_pJ=energy,
        chemical_change_pJ=float(chemical),
        capacitor_change_pJ=float(electric),
        dissipated_energy_pJ=float(heat),
        work_pJ=float(work),
        chemical_work_residual_pJ=values["reservoir_work_pJ"]
        - values["reservoir_chemical_work_pJ"]
        - 1e12 * voltage * supply_charge,
        electrode_work_residual_pJ=values["electrode_work_pJ"]
        - 1e12 * voltage * values["electrode_charge_transferred_C"],
    )


def dependency_manifest(root):
    """Hash module-import closure; audit own and legacy equation bodies too.

    Accepted helper modules can also contain separate, uncalled comparison
    drivers (e.g. junction_transport.check.check). Their function-local imports
    do not execute when importing the independent decimal_flux helper.
    """
    root = Path(root).resolve()
    pending = [Path(__file__).resolve()]
    result = {}
    while pending:
        path = pending.pop()
        relative = str(path.relative_to(root))
        if relative in result:
            continue
        legacy = path.parent == root / "tests" and path.name.startswith("reference_")
        if not path.is_relative_to(root / "validation") and not legacy:
            raise ValueError("Non-reference project dependency: " + relative)
        source = path.read_bytes()
        result[relative] = hashlib.sha256(source).hexdigest()
        tree = ast.parse(source)
        parents = {
            child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)
        }
        for node in ast.walk(tree):
            ancestor = parents.get(node)
            nested = False
            while ancestor is not None:
                nested |= isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
                ancestor = parents.get(ancestor)
            if nested and path != Path(__file__).resolve() and not legacy:
                continue
            if isinstance(node, ast.Import):
                names = [value.name for value in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    package = list(path.relative_to(root).with_suffix("").parts[:-1])
                    base = ".".join(package[: len(package) - node.level + 1])
                    module = base + ("." + node.module if node.module else "")
                else:
                    module = node.module or ""
                names = [module, *(module + "." + value.name for value in node.names)]
            else:
                continue
            for name in names:
                if name.split(".")[0] in {"cells", "jax", "jaxlib"}:
                    raise ValueError("Production/JAX import in reference: " + relative)
                candidate = root.joinpath(*name.split("."))
                for local in (candidate.with_suffix(".py"), candidate / "__init__.py"):
                    if local.is_file():
                        pending.append(local.resolve())
    return dict(sorted(result.items()))
