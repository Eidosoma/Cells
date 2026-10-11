"""D094 independent saved-state mathematics; standard library only, no old oracle.

These are boundary identities, not a trajectory integrator. Decimal expressions
use 80 digits; accumulation of recorded float64 quantities uses math.fsum.
"""

import hashlib
import math
import struct
from decimal import Decimal, localcontext

VARIANTS = ("network_off", "empty_network", "blocked_channel", "active_channel")
VALENCE = (1, 1, -1, 2, -1, -1)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    require(type(value) in (int, float) and math.isfinite(value), "Invalid finite scalar")
    return value


def scalars(value, dimensions):
    if not dimensions:
        yield finite(value)
        return
    require(isinstance(value, list) and len(value) == dimensions[0], "Wrong array shape")
    for item in value:
        yield from scalars(item, dimensions[1:])


def array_bytes(record, dimensions):
    require(set(record) == {"dtype", "shape", "values", "bytes_sha256"}, "Array record keys")
    require(record["dtype"] == "<f8" and record["shape"] == dimensions, "Float64 layout differs")
    require(all(type(n) is int and n >= 0 for n in dimensions), "Invalid array extent")
    require(math.prod(dimensions) <= 1000000, "Oversized array")
    raw = b"".join(struct.pack("<d", v) for v in scalars(record["values"], dimensions))
    require(hashlib.sha256(raw).hexdigest() == record["bytes_sha256"], "Float64 bytes differ")
    return raw


def uniform(values):
    require(isinstance(values, list) and bool(values), "Empty uniform field")
    require(all(finite(v) == values[0] for v in values), "Nonuniform field")
    return values[0]


def owner_values(values, geometry):
    owners, count = geometry["membrane_owners"], geometry["cell_count"]
    require(len(values) == len(owners), "Owner/value extent differs")
    require(all(type(i) is int for i in owners) and set(owners) == set(range(count)), "Owners")
    return [
        uniform([v for v, o in zip(values, owners, strict=True) if o == i]) for i in range(count)
    ]


def integrate_faces(values, geometry):
    require(len(values) == geometry["membrane_count"], "Face density extent differs")
    return [
        math.fsum(
            finite(v) * area
            for v, area, owner in zip(
                values, geometry["membrane_areas_m2"], geometry["membrane_owners"], strict=True
            )
            if owner == i
        )
        for i in range(geometry["cell_count"])
    ]


def scaled(actual, expected, absolute, relative):
    finite(actual)
    finite(expected)
    require(absolute > 0 and relative >= 0, "Invalid tolerance")
    return abs(actual - expected) / (absolute + relative * abs(expected))


def near(actual, expected, absolute, relative=2e-11):
    if isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), "Contract shape")
        for a, b in zip(actual, expected, strict=True):
            near(a, b, absolute, relative)
    else:
        require(scaled(actual, expected, absolute, relative) <= 1, "Numerical contract differs")


def decimal(value):
    return Decimal(str(value))


def kinetics(voltage):
    v = decimal(finite(voltage))
    require(-0.12 <= voltage <= 0.06, "Kinetic voltage domain")
    with localcontext() as context:
        context.prec = 80
        targets = (
            1 / (1 + ((-v - Decimal(".006")) / Decimal(".0064")).exp()),
            1 / (1 + ((v + Decimal(".0253")) / Decimal(".0035")).exp()),
        )
        taus = (Decimal(".008330") - Decimal(".1163") * v, Decimal("1.620") - Decimal("15.5") * v)
        return targets, taus


def gate_values(voltage, gates, dt=None):
    """Continuous rates, or the native rational step when dt is supplied."""
    require(len(gates) == 2 and all(0 <= finite(q) <= 1 for q in gates), "Gate domain")
    require(dt is None or finite(dt) > 0, "Gate step domain")
    with localcontext() as context:
        context.prec = 80
        targets, taus = kinetics(voltage)
        if dt is None:
            return [
                float((target - decimal(q)) / tau)
                for target, q, tau in zip(targets, gates, taus, strict=True)
            ]
        return [
            float((tau * decimal(q) + decimal(dt) * target) / (tau + decimal(dt)))
            for target, q, tau in zip(targets, gates, taus, strict=True)
        ]


def inward_density(voltage, inside, outside, permeability, constants, temperature):
    require(inside > 0 and outside > 0 and permeability >= 0 and temperature > 0, "GHK domain")
    with localcontext() as context:
        context.prec = 80
        v, ci, co, p = map(decimal, (voltage, inside, outside, permeability))
        x = v * decimal(constants["F"]) / (decimal(constants["R"]) * decimal(temperature))
        require(abs(x) <= 50, "GHK voltage domain")
        if not x:
            return p * (co - ci)
        exponential = x.exp()
        return p * x * (co - ci * exponential) / (exponential - 1)


class Metrics:
    def __init__(self):
        self.values = {}

    def add(self, name, actual, expected, unit):
        if isinstance(expected, list):
            require(isinstance(actual, list) and len(actual) == len(expected), "Metric shape")
            for i, (a, b) in enumerate(zip(actual, expected, strict=True)):
                self.add(f"{name}/{i}", a, b, unit)
        else:
            require(name not in self.values, "Duplicate independent metric")
            self.values[name] = (finite(actual), finite(expected), unit)

    def audit(self, saved, tolerances):
        require(len(saved) == len(self.values), "Comparison coverage differs")
        require(len({r["id"] for r in saved}) == len(saved), "Duplicate saved metric")
        require({r["id"] for r in saved} == set(self.values), "Comparison identities differ")
        result = []
        for row in saved:
            name = row["id"]
            actual, expected, unit = self.values[name]
            require(row["unit"] == unit, "Comparison unit differs")
            # Independently check the measured identity and both saved columns.
            error = max(
                scaled(a, b, tolerances[unit], tolerances["relative"])
                for a, b in (
                    (actual, expected),
                    (row["actual"], actual),
                    (row["expected"], expected),
                )
            )
            result.append(
                {
                    "id": name,
                    "actual": actual,
                    "expected": expected,
                    "unit": unit,
                    "scaled_error": error,
                    "passed": error <= 1,
                }
            )
        return result


def order_for(variant):
    network, channel = variant != "network_off", variant in VARIANTS[2:]
    return (
        (["after_clear"] if network else [])
        + (["before_channel", "before_gate", "after_gate", "after_channel"] if channel else [])
        + (["before_network", "after_network"] if network else [])
        + ["before_ordinary", "after_ordinary", "after_voltage"]
    )


def geometry_contract(g):
    require(g["cell_count"] == 7 and g["membrane_count"] == 30, "Geometry extent differs")
    owner_values([0.0] * 30, g)
    for field, extent in (("cell_volumes_m3", 7), ("cell_areas_m2", 7), ("membrane_areas_m2", 30)):
        require(all(v > 0 for v in scalars(g[field], [extent])), "Nonpositive geometry")
    near(integrate_faces([1.0] * 30, g), g["cell_areas_m2"], 1e-24)
    require(g["specific_capacitance_F_per_m2"] == 0.01, "Capacitance differs")
    require(
        g["effective_bath_volume_m3"] == 30 * g["configured_bath_volume_m3"], "Bath extent differs"
    )
    require(g["grid_shape"] == [10, 10], "Environment grid differs")


def direct_charge(physical, g, constants):
    """Absolute all-six-species charge, independent of increment voltage checks."""
    rho = [
        math.fsum(z * constants["F"] * physical["inside_mM"][s][i] for s, z in enumerate(VALENCE))
        for i in range(g["cell_count"])
    ]
    near(physical["rho_C_per_m3"], rho, 2e-8)
    voltage = [
        q * volume / (area * g["specific_capacitance_F_per_m2"])
        for q, volume, area in zip(rho, g["cell_volumes_m3"], g["cell_areas_m2"], strict=True)
    ]
    near(owner_values(physical["voltage_V"], g), voltage, 2e-10)


def array_contract(row):
    n, m, count = 7, 30, 7
    shapes = {
        "inside_mM": [6, n],
        "outside_mM": [6, m],
        "at_membrane_mM": [6, m],
        "ordinary_density_mol_per_m2_s": [6, m],
        "junction_density_mol_per_m2_s": [6, m],
        "rho_C_per_m3": [n],
        "extra_rho_cells_C_per_m3": [n],
        "boundary_voltage_V": [100],
    }
    shapes |= {
        k: [m]
        for k in (
            "voltage_V",
            "extra_rho_env_C_per_m3",
            "extra_current_density_A_per_m2",
            "Jmem_A_per_m2",
            "Jn_A_per_m2",
            "I_mem_A",
        )
    }
    channel_fields = {
        "m": "m",
        "h": "h",
        "P": "P",
        "DChan": "DChan_m2_per_s",
        "chan_flux": "density_mol_per_m2_s",
    }
    if row["final"]["channel"] is not None:
        shapes |= {"channel/" + k: [m] for k in channel_fields}
    require(set(shapes) == set(row["final_arrays"]), "Final array membership differs")
    for name, shape in shapes.items():
        record = row["final_arrays"][name]
        array_bytes(record, shape)
        expected = (
            row["final"]["channel"][channel_fields[name.split("/")[1]]]
            if name.startswith("channel/")
            else row["final"]["physical"][name]
        )
        require(record["values"] == expected, "Final raw/array disagreement")
    histories = {
        "time": [],
        "cc_time": [6, n],
        "cc_env_time": [6, m],
        "vm_time": [m],
        "I_mem_time": [m],
        "rho_cells_time": [n],
        "rate_NaKATP_time": [m],
        "gjopen_time": [m],
        "dd_time": [6, m],
    }
    require(set(histories) == set(row["histories"]), "History membership differs")
    for name, shape in histories.items():
        array_bytes(row["histories"][name], [count, *shape])
    for name, target in (("rate_NaKATP_time", 0), ("gjopen_time", 1), ("dd_time", 0)):
        require(
            all(
                v == target
                for v in scalars(row["histories"][name]["values"], [count, *histories[name]])
            ),
            "Inactive history differs",
        )
    return len(shapes) + len(histories)


def stage_metrics(metrics, prefix, snapshot, initial, g):
    s, channel = snapshot["physical"], snapshot["channel"]
    vi = [v / 1e-15 for v in g["cell_volumes_m3"]]
    vo = g["effective_bath_volume_m3"] / 1e-15
    for field, shape in (
        ("inside_mM", [6, 7]),
        ("outside_mM", [6, 30]),
        ("at_membrane_mM", [6, 30]),
    ):
        require(all(v > 0 for v in scalars(s[field], shape)), "Nonpositive concentration")
    for name in (
        "ordinary_density_mol_per_m2_s",
        "junction_density_mol_per_m2_s",
        "extra_rho_cells_C_per_m3",
        "extra_rho_env_C_per_m3",
        "boundary_voltage_V",
    ):
        values = s[name]
        shape = (
            [6, 30]
            if name.endswith("mol_per_m2_s")
            else [
                7
                if name == "extra_rho_cells_C_per_m3"
                else 100
                if name == "boundary_voltage_V"
                else 30
            ]
        )
        require(
            all(v == 0 for v in scalars(values, shape)), "Unregistered transport or boundary charge"
        )
    for species in range(6):
        inside, outside = s["inside_mM"][species], uniform(s["outside_mM"][species])
        metrics.add(
            prefix + f"/membrane/{species}",
            s["at_membrane_mM"][species],
            [inside[o] for o in g["membrane_owners"]],
            "concentration_mM",
        )
        residual = math.fsum(
            [(a - b) * v for a, b, v in zip(inside, initial["inside_mM"][species], vi, strict=True)]
            + [(outside - uniform(initial["outside_mM"][species])) * vo]
        )
        metrics.add(prefix + f"/conservation/{species}", residual, 0.0, "amount_fmol")
        if species != 1:
            require(
                inside == initial["inside_mM"][species]
                and s["outside_mM"][species] == initial["outside_mM"][species],
                "Inactive species changed",
            )
    require(all(-0.12 <= v <= 0.06 for v in owner_values(s["voltage_V"], g)), "Voltage domain")
    if channel is not None:
        require(
            channel["modulator"] == 1 or channel["modulator"] == [1.0] * 30, "Modulation differs"
        )
        for key in ("m", "h"):
            require(all(0 <= q <= 1 for q in owner_values(channel[key], g)), "Hidden gate domain")
        product = [a * b for a, b in zip(channel["m"], channel["h"], strict=True)]
        metrics.add(prefix + "/derived_product", channel["derived_m_times_h"], product, "gate")
        if channel["P"] is not None:
            metrics.add(prefix + "/native_P", channel["P"], product, "gate")


def native_metrics(r, native, metrics):
    protocol, physics = r["protocol"], r["transport_protocol"]
    dt, constants = protocol["dt_s"], physics["constants"]
    counts, arrays = {}, 0
    require(
        set(native["rows"])
        == {v + "/" + mode for v in VARIANTS for mode in ("observed", "unobserved")},
        "Native pair coverage",
    )
    for variant in VARIANTS:
        row, partner = (native["rows"][variant + "/" + mode] for mode in ("observed", "unobserved"))
        require(
            {k: v for k, v in row.items() if k not in ("mode", "trace")}
            == {k: v for k, v in partner.items() if k not in ("mode", "trace")},
            "Observer changed outputs",
        )
        require(partner["trace"] is None, "Unobserved trace exists")
        for member in (row, partner):
            arrays += array_contract(member)
        g, trace = row["geometry"], row["trace"]
        geometry_contract(g)
        enabled, active = variant in VARIANTS[2:], variant == "active_channel"
        require(trace["gate_initializations"] == int(enabled), "Repeated gate initialization")
        require(
            trace["calls"]
            == dict.fromkeys(
                (
                    "run_sim_core",
                    "init_dynamics",
                    "clear_storage",
                    "initial_update_V",
                    "loop",
                    "loop_return",
                    "run_return",
                ),
                1,
            ),
            "Native lifecycle differs",
        )
        require(
            trace["pending"] is None
            and trace["hook_restored"] is True
            and len(trace["steps"]) == 8,
            "Incomplete trace",
        )
        require(trace["sampled_indices"] == list(range(1, 8)), "Sampling indices differ")
        near(trace["labels_s"], [i * protocol["duration_s"] / 7 for i in range(8)], 1e-20, 1e-15)
        require(
            trace["storage"]
            == [{"index": i, "raw_label_s": trace["labels_s"][i]} for i in range(1, 8)],
            "Storage clock differs",
        )
        initial = trace["initial"]["physical"]
        direct_charge(initial, g, constants)
        previous, accumulated = trace["initial"], [0.0] * 7
        vi, vo = [v / 1e-15 for v in g["cell_volumes_m3"]], g["effective_bath_volume_m3"] / 1e-15
        start_count = len(metrics.values)
        for i, step in enumerate(trace["steps"]):
            prefix = variant + f"/step/{i}"
            require(
                (
                    step["index"],
                    step["before_elapsed_s"],
                    step["after_elapsed_s"],
                    step["raw_label_s"],
                )
                == (i, i * dt, (i + 1) * dt, trace["labels_s"][i]),
                "Elapsed/native clock confusion",
            )
            require(step["order"] == order_for(variant), "Native stage ordering differs")
            b, final = step["before"]["physical"], step["after_voltage"]["physical"]
            require(step["before"]["channel"] == previous["channel"], "Inter-step gate reset")
            require(
                all(b[k] == previous["physical"][k] for k in ("inside_mM", "outside_mM")),
                "Inter-step transport",
            )
            metrics.add(
                prefix + "/read_previous_voltage",
                b["voltage_V"],
                previous["physical"]["voltage_V"],
                "voltage_V",
            )
            density = [0.0] * 30
            if enabled:
                before, after = step["before_gate"]["channel"], step["after_gate"]["channel"]
                for face, owner in enumerate(g["membrane_owners"]):
                    v = step["before_gate"]["physical"]["voltage_V"][face]
                    gates = [before["m"][face], before["h"][face]]
                    actual_gates = [after["m"][face], after["h"][face]]
                    metrics.add(
                        prefix + f"/gates/{face}", actual_gates, gate_values(v, gates, dt), "gate"
                    )
                    with localcontext() as context:
                        context.prec = 80
                        opened = decimal(actual_gates[0]) * decimal(actual_gates[1])
                        p = opened * decimal(physics["max_permeability_m_per_s"]) * int(active)
                        expected_density = float(
                            inward_density(
                                v,
                                b["inside_mM"][1][owner],
                                uniform(b["outside_mM"][1]),
                                p,
                                constants,
                                physics["temperature_K"],
                            )
                        )
                    metrics.add(prefix + f"/open/{face}", after["P"][face], float(opened), "gate")
                    metrics.add(
                        prefix + f"/diffusivity/{face}",
                        step["after_channel"]["channel"]["DChan_m2_per_s"][face],
                        float(p) * physics["thickness_m"],
                        "diffusivity_m2_per_s",
                    )
                    density[face] = expected_density
                metrics.add(
                    prefix + "/density",
                    step["after_channel"]["channel"]["density_mol_per_m2_s"],
                    density,
                    "density_mol_per_m2_s",
                )
                density = step["after_channel"]["channel"]["density_mol_per_m2_s"]
            flow = [q * 1e15 for q in integrate_faces(density, g)]
            current = [-constants["F"] * j for j in density]
            for name in ["before", *step["order"]]:
                snapshot = step[name]
                require((snapshot["channel"] is not None) == enabled, "Channel inventory differs")
                stage_metrics(metrics, prefix + "/" + name, snapshot, initial, g)
                after_transfer = name in (
                    "after_channel",
                    "before_network",
                    "after_network",
                    "before_ordinary",
                    "after_ordinary",
                    "after_voltage",
                )
                expected_ci = [
                    a + (dt * q / v if after_transfer else 0)
                    for a, q, v in zip(b["inside_mM"][1], flow, vi, strict=True)
                ]
                expected_co = uniform(b["outside_mM"][1]) - (
                    dt * math.fsum(flow) / vo if after_transfer else 0
                )
                metrics.add(
                    prefix + f"/{name}/K_inside",
                    snapshot["physical"]["inside_mM"][1],
                    expected_ci,
                    "concentration_mM",
                )
                metrics.add(
                    prefix + f"/{name}/K_outside",
                    uniform(snapshot["physical"]["outside_mM"][1]),
                    expected_co,
                    "concentration_mM",
                )
                if name in ("after_network", "before_ordinary", "after_ordinary", "after_voltage"):
                    metrics.add(
                        prefix + f"/{name}/current",
                        snapshot["physical"]["extra_current_density_A_per_m2"],
                        current,
                        "current_density_A_per_m2",
                    )
                if name in ("after_channel", "before_network", "after_network"):
                    metrics.add(
                        prefix + f"/{name}/network_current",
                        snapshot["network_current"],
                        current,
                        "current_density_A_per_m2",
                    )
            metrics.add(
                prefix + "/Jmem", final["Jmem_A_per_m2"], current, "current_density_A_per_m2"
            )
            owner_average = [
                q / area
                for q, area in zip(integrate_faces(current, g), g["cell_areas_m2"], strict=True)
            ]
            smoothed = [
                w * j + other * owner_average[o]
                for w, j, other, o in zip(
                    row["smooth_weight_mem"],
                    current,
                    row["smooth_weight_other"],
                    g["membrane_owners"],
                    strict=True,
                )
            ]
            metrics.add(prefix + "/Jn", final["Jn_A_per_m2"], smoothed, "current_density_A_per_m2")
            metrics.add(
                prefix + "/I_mem",
                final["I_mem_A"],
                [-j * a for j, a in zip(smoothed, g["membrane_areas_m2"], strict=True)],
                "current_A",
            )
            accumulated = [a + dt * q for a, q in zip(accumulated, flow, strict=True)]
            measured = [
                (a - b0) * v
                for a, b0, v in zip(final["inside_mM"][1], initial["inside_mM"][1], vi, strict=True)
            ]
            metrics.add(prefix + "/accumulated_transfer", measured, accumulated, "amount_fmol")
            expected_voltage = [
                v0 + q * constants["F"] * 1e-15 / (area * 0.01)
                for v0, q, area in zip(
                    owner_values(initial["voltage_V"], g),
                    accumulated,
                    g["cell_areas_m2"],
                    strict=True,
                )
            ]
            metrics.add(
                prefix + "/charge_voltage",
                owner_values(final["voltage_V"], g),
                expected_voltage,
                "voltage_V",
            )
            direct_charge(final, g, constants)
            require(
                all(q < 0 for q in flow) if active else all(q == 0 for q in flow),
                "Active/control flow differs",
            )
            previous = step["after_voltage"]
        require(row["final"] == previous, "Final state differs from completed step")
        for name, field in (
            ("cc_time", "inside_mM"),
            ("cc_env_time", "outside_mM"),
            ("vm_time", "voltage_V"),
            ("I_mem_time", "I_mem_A"),
            ("rho_cells_time", "rho_C_per_m3"),
        ):
            require(
                row["histories"][name]["values"]
                == [trace["steps"][i]["after_voltage"]["physical"][field] for i in range(1, 8)],
                "History/trace disagreement",
            )
        require(
            row["histories"]["time"]["values"] == trace["labels_s"][1:],
            "History time mapping differs",
        )
        counts[variant] = len(metrics.values) - start_count
    return {
        "native_comparisons_by_variant": counts,
        "array_records_reconstructed": arrays,
        "observer_pairs_checked": 4,
        "direct_charge_snapshots_checked": 36,
    }
