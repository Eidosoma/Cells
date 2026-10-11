"""Independent saved-trajectory arithmetic; no NumPy, simulator or ODE imports."""

import hashlib
import math
import struct

import alignment as a
import cluster_alignment as cluster
import contact as c
import trajectory_context as ctx


def numbers(value):
    if isinstance(value, list):
        return [v for part in value for v in numbers(part)]
    c.require(type(value) in (int, float) and math.isfinite(value), "Nonfinite/nonnumeric value")
    return [value]


def shaped(value, shape):
    if not shape:
        c.require(not isinstance(value, list), "Unexpected array axis")
        return numbers(value)
    c.require(isinstance(value, list) and len(value) == shape[0], "Array shape differs")
    return [v for part in value for v in shaped(part, shape[1:])]


def unpack(record):
    c.require(record["dtype"] == "<f8", "Wrong stored precision/byte order")
    c.require(all(type(n) is int and n >= 0 for n in record["shape"]), "Invalid shape")
    flat = shaped(record["values"], record["shape"])
    digest = hashlib.sha256(b"".join(struct.pack("<d", v) for v in flat)).hexdigest()
    c.require(digest == record["bytes_sha256"], "Exported array bytes differ")
    return record["values"]


class Checks:
    def __init__(self):
        self.count = 0
        self.maximum = 0.0
        self.worst = None
        self.failures = []
        self.failed_count = 0

    def compare(self, label, actual, expected, unit, limits):
        score = c.normalized_error(actual, expected, limits[unit], limits["relative"])
        self.count += 1
        row = {"id": label, "actual": actual, "expected": expected, "normalized_error": score}
        if self.worst is None or score > self.maximum:
            self.maximum, self.worst = score, row
        if score > 1:
            self.failed_count += 1
            if len(self.failures) < 100:
                self.failures.append(row)


def rate_by_cell(density, g):
    shaped(density, [6, 30])
    return [
        [
            math.fsum(
                density[s][j] * g["membrane_areas_m2"][j]
                for j, owner in enumerate(g["membrane_owners"])
                if owner == i
            )
            / 1e-15
            for i in range(7)
        ]
        for s in range(6)
    ]


def native_record(registered, record, case, profile, dt, checks):
    p, b, g = registered["protocol"], registered["base_protocol"], registered["geometry"]
    limits, constants = p["instantaneous_tolerances"], b["profiles"][profile]
    identifier = ctx.key(case["id"], profile, dt)
    count = round(p["duration_s"] / dt)
    c.require(record["id"] == identifier and record["dt_s"] == dt, "Native run identity differs")
    c.require(
        record["constants"] == constants and record["configured_steps"] == count,
        "Native parameters differ",
    )
    c.require(
        record["geometry"] == {key: g[key] for key in cluster.GEOMETRY_FIELDS},
        "Native geometry correspondence differs",
    )
    c.require(
        record["settings"] == registered["settings"] and record["rho_channel"] == 1,
        "Native mechanisms differ",
    )
    c.require(
        record["species"] == b["expected_species"] and record["valence"] == b["expected_valence"],
        "Native ion table differs",
    )
    c.require(
        record["native_pickle_present"] is True, "Native phase did not complete serialization"
    )
    c.require(
        set(record["ordinary"]) == set(ctx.ORDINARY_NAMES)
        and set(record["final"]) == set(ctx.FINAL_NAMES),
        "Native exported field coverage differs",
    )
    for s, row in enumerate(record["permeability_m_per_s"]):
        c.require(
            len(row) == 30
            and all(
                math.isclose(
                    v, b["permeability_m_per_s"][s] * case["availability"], rel_tol=2e-15, abs_tol=0
                )
                for v in row
            ),
            "Native permeability differs",
        )
    c.require(len(record["permeability_m_per_s"]) == 6, "Native permeability coverage differs")
    trace = record["trace"]
    c.require(
        trace["loop_calls"] == trace["loop_returns"] == 1
        and trace["concentration_updates"] == count
        and trace["hook_restored"] is True,
        "Observer incomplete",
    )
    c.require(
        len(trace["steps"]) == len(trace["labels_s"]) == count
        and trace["sampled_indices"] == list(range(1, count)),
        "Native clock coverage differs",
    )
    c.require(
        trace["storage"]
        == [{"index": k, "raw_label_s": trace["labels_s"][k]} for k in range(1, count)],
        "Native storage indices differ",
    )
    c.require(
        all(
            math.isclose(v, k * count * dt / (count - 1), rel_tol=1e-14, abs_tol=1e-18)
            for k, v in enumerate(trace["labels_s"])
        ),
        "Raw native labels differ",
    )
    vi = [v / 1e-15 for v in g["cell_volumes_m3"]]
    vo = g["effective_bath_volume_m3"] / 1e-15
    zs = b["expected_valence"]
    zero = [[0.0] * 30 for _ in range(6)]
    cumul = [[0.0] * 7 for _ in range(6)]
    states, transfers, rates = [trace["initial"]], [[[0.0] * 7 for _ in range(3)]], []

    def state(label, saved, density):
        shaped(saved["inside_mM"], [6, 7])
        shaped(saved["outside_mM"], [6, 30])
        c.require(
            all(v > 0 for v in numbers(saved["inside_mM"]) + numbers(saved["outside_mM"])),
            "Nonpositive native inventory",
        )
        c.require(
            all(all(v == row[0] for v in row) for row in saved["outside_mM"]),
            "Outside is not well mixed",
        )
        shaped(saved["voltage_V"], [30])
        shaped(saved["inward_current_A"], [30])
        shaped(saved["rho_C_per_m3"], [7])
        c.require(
            shaped(saved["boundary_voltage_V"], [100]) == [0.0] * 100, "Boundary voltage is nonzero"
        )
        local_rates = rate_by_cell(density, g)
        for i in range(7):
            rho = constants["F"] * math.fsum(zs[s] * saved["inside_mM"][s][i] for s in range(6))
            voltage = rho * g["cell_volumes_m3"][i] / (0.01 * g["cell_areas_m2"][i])
            checks.compare(
                f"{label}/rho/{i}", saved["rho_C_per_m3"][i], rho, "charge_density_C_per_m3", limits
            )
            for j, owner in enumerate(g["membrane_owners"]):
                if owner == i:
                    checks.compare(
                        f"{label}/voltage/{j}", saved["voltage_V"][j], voltage, "voltage_V", limits
                    )
            actual = math.fsum(
                saved["inward_current_A"][j]
                for j, owner in enumerate(g["membrane_owners"])
                if owner == i
            )
            expected = (
                constants["F"] * 1e-15 * math.fsum(zs[s] * local_rates[s][i] for s in range(6))
            )
            checks.compare(f"{label}/current/{i}", actual, expected, "current_A", limits)

    initial = trace["initial"]
    state(identifier + "/initial", initial, zero)
    for s in range(6):
        for i in range(7):
            checks.compare(
                f"{identifier}/initial_ci/{s}/{i}",
                initial["inside_mM"][s][i],
                b["inside_mM"][s],
                "concentration_mM",
                limits,
            )
        for j in range(30):
            checks.compare(
                f"{identifier}/initial_co/{s}/{j}",
                initial["outside_mM"][s][j],
                b["outside_mM"][s],
                "concentration_mM",
                limits,
            )
    previous_density = zero
    cumulative_limits = limits | {"amount_fmol": p["cumulative_amount_atol_fmol"]}
    for k, step in enumerate(trace["steps"]):
        label = f"{identifier}/step/{k}"
        c.require(
            step["index"] == k and step["raw_label_s"] == trace["labels_s"][k],
            "Step correspondence differs",
        )
        c.require(
            step["before_elapsed_s"] == k * dt and step["after_elapsed_s"] == (k + 1) * dt,
            "Derived native update clock differs",
        )
        before, after, density = step["before"], step["after"], step["density_mol_per_m2_s"]
        previous = states[-1]
        c.require(
            before["inside_mM"] == previous["inside_mM"]
            and before["outside_mM"] == previous["outside_mM"],
            "Native amount history is discontinuous",
        )
        # Native electroflux adds a 1e-25 V nonce in-place before this observation.
        c.require(
            all(
                abs(v - old) < 1e-22
                for v, old in zip(before["voltage_V"], previous["voltage_V"], strict=True)
            ),
            "Native pre-update voltage discontinuity",
        )
        state(label + "/before", before, previous_density)
        state(label + "/after", after, density)
        c.require(
            shaped(step["junction_density_mol_per_m2_s"], [6, 30]) == [0.0] * 180,
            "Disabled junction transported",
        )
        local_rates = rate_by_cell(density, g)
        for s in range(6):
            if s >= 3 or case["availability"] == 0:
                c.require(all(v == 0 for v in density[s]), "Disabled membrane route transported")
            for j, owner in enumerate(g["membrane_owners"]):
                point = {
                    "inside_mM": before["inside_mM"][s][owner],
                    "outside_mM": before["outside_mM"][s][j],
                    "voltage_V": before["voltage_V"][j],
                    "valence": zs[s],
                    "temperature_K": 310.15,
                    "area_m2": g["membrane_areas_m2"][j],
                    "permeability_m_per_s": b["permeability_m_per_s"][s] * case["availability"],
                }
                checks.compare(
                    f"{label}/GHK/{s}/{j}",
                    density[s][j] * point["area_m2"] / 1e-15,
                    c.oracle(point, constants),
                    "flux_fmol_per_s",
                    limits,
                )
            for i in range(7):
                increment = (after["inside_mM"][s][i] - before["inside_mM"][s][i]) * vi[i]
                checks.compare(
                    f"{label}/step_amount/{s}/{i}",
                    increment,
                    local_rates[s][i] * dt,
                    "amount_fmol",
                    limits,
                )
                cumul[s][i] += local_rates[s][i] * dt
                total = (after["inside_mM"][s][i] - initial["inside_mM"][s][i]) * vi[i]
                checks.compare(
                    f"{label}/integrated_amount/{s}/{i}",
                    total,
                    cumul[s][i],
                    "amount_fmol",
                    cumulative_limits,
                )
            outside = (after["outside_mM"][s][0] - before["outside_mM"][s][0]) * vo
            checks.compare(
                f"{label}/outside_step/{s}",
                outside,
                -math.fsum(local_rates[s]) * dt,
                "amount_fmol",
                limits,
            )
            total_outside = (after["outside_mM"][s][0] - initial["outside_mM"][s][0]) * vo
            checks.compare(
                f"{label}/outside_integral/{s}",
                total_outside,
                -math.fsum(cumul[s]),
                "amount_fmol",
                cumulative_limits,
            )
        if case["availability"] == 0:
            c.require(
                after["inside_mM"] == initial["inside_mM"]
                and after["outside_mM"] == initial["outside_mM"]
                and after["voltage_V"] == initial["voltage_V"],
                "Blocked native state changed",
            )
        states.append(after)
        transfers.append([list(row) for row in cumul[:3]])
        rates.append(local_rates[:3])
        previous_density = density
    ordinary = {name: unpack(array) for name, array in record["ordinary"].items()}
    c.require(ordinary["time"] == trace["labels_s"][1:], "Native stored time labels differ")
    for field, name in (
        ("inside_mM", "cc_time"),
        ("outside_mM", "cc_env_time"),
        ("voltage_V", "vm_time"),
        ("inward_current_A", "I_mem_time"),
        ("rho_C_per_m3", "rho_cells_time"),
    ):
        c.require(
            ordinary[name] == [step["after"][field] for step in trace["steps"][1:]],
            "Observer and ordinary native storage differ",
        )
    final = {name: unpack(array) for name, array in record["final"].items()}
    for field, name in (
        ("inside_mM", "cc_cells"),
        ("outside_mM", "cc_env"),
        ("voltage_V", "vm"),
        ("inward_current_A", "I_mem"),
        ("rho_C_per_m3", "rho_cells"),
    ):
        c.require(final[name] == states[-1][field], "Final native state differs")
    canonical = []
    for t in p["common_times_s"]:
        index = round(t / dt)
        c.require(
            math.isclose(t, index * dt, rel_tol=0, abs_tol=1e-18), "Common time is off native grid"
        )
        saved = states[index]
        canonical.append(
            {
                "voltage_V": [saved["voltage_V"][g["membrane_owners"].index(i)] for i in range(7)],
                "amount_fmol": [
                    (saved["inside_mM"][s][i] - initial["inside_mM"][s][i]) * vi[i]
                    for s in range(3)
                    for i in range(7)
                ]
                + [
                    (saved["outside_mM"][s][0] - initial["outside_mM"][s][0]) * vo for s in range(3)
                ],
                "transfer_fmol": numbers(transfers[index]),
                "flux_fmol_per_s": numbers(rates[index]) if index < count else [],
                "current_A": [
                    constants["F"] * 1e-15 * math.fsum(zs[s] * rates[index][s][i] for s in range(3))
                    for i in range(7)
                ]
                if index < count
                else [],
            }
        )
    return canonical


def cells_record(registered, record, case, backend, dt, checks):
    p, b, g = registered["protocol"], registered["base_protocol"], registered["geometry"]
    identifier = ctx.key(case["id"], backend, dt)
    c.require(
        record["id"] == identifier
        and record["definition"] == registered["cells_definitions"][identifier],
        "Cells definition differs",
    )
    c.require(record["definition"] == ctx.definition(case, dt, backend), "Cells mapping differs")
    times = unpack(record["times"])
    n = round(p["duration_s"] / dt)
    c.require(
        len(times) == n + 1
        and record["final_step_index"] == n
        and all(math.isclose(t, i * dt, rel_tol=0, abs_tol=1e-18) for i, t in enumerate(times)),
        "Cells accepted clock differs",
    )
    history = {name: unpack(value) for name, value in record["history"].items()}
    c.require(
        set(history)
        == {
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
        },
        "Cells history incomplete",
    )
    c.require(all(len(v) == len(times) for v in history.values()), "Cells history length differs")
    for name in (
        "pump_cycles",
        "gate",
        "channel_transferred",
        "junction_gate",
        "junction_transferred",
        "junction_dissipated_energy_pJ",
    ):
        c.require(all(v == 0 for v in numbers(history[name])), "Inactive state/history changed")
    c.require(
        all(all(v == 0 for v in numbers(series[0])) for series in history.values()),
        "Cells did not start from declared preparation",
    )
    if case["availability"] == 0:
        c.require(
            all(all(v == 0 for v in numbers(series)) for series in history.values()),
            "Blocked Cells history changed",
        )
    limits = p["instantaneous_tolerances"] | {"amount_fmol": p["cumulative_amount_atol_fmol"]}
    for k in range(len(times)):
        inside, outside, leak = (
            history["amount_increment"][k],
            history["extracellular_amount_increment"][k],
            history["leak_transferred"][k],
        )
        shaped(inside, [3, 8])
        shaped(outside, [3, 2])
        shaped(leak, [3, 9])
        for s in range(3):
            c.require(
                inside[s][7] == outside[s][1] == 0 and leak[s][7:] == [0, 0],
                "Inactive owner changed",
            )
            for i in range(7):
                checks.compare(
                    f"{identifier}/owned_transfer/{k}/{s}/{i}",
                    inside[s][i],
                    leak[s][i],
                    "amount_fmol",
                    limits,
                )
            checks.compare(
                f"{identifier}/global_material/{k}/{s}",
                math.fsum(inside[s]) + outside[s][0],
                0,
                "amount_fmol",
                limits,
            )
    obs = {name: unpack(value) for name, value in record["observations"].items()}
    c.require(obs["times"] == p["common_times_s"], "Cells observations differ")
    canonical = []
    for j, t in enumerate(obs["times"]):
        k = round(t / dt)
        inside, outside = (
            history["amount_increment"][k],
            history["extracellular_amount_increment"][k],
        )
        c.require(
            obs["amount_increment"][j] == inside
            and obs["extracellular_amount_increment"][j] == outside,
            "On-grid Cells observations differ",
        )
        voltages = obs["voltage_V"][j][:7]
        shaped(obs["voltage_V"][j], [9])
        c.require(obs["voltage_V"][j][7:] == [0, 0], "Inactive membrane voltage changed")
        for i in range(7):
            expected = (
                b["profiles"]["matched_constants"]["F"]
                * 1e-15
                * math.fsum(b["expected_valence"][s] * inside[s][i] for s in range(3))
                / (g["cell_areas_m2"][i] * 0.01)
            )
            checks.compare(
                f"{identifier}/charge/{j}/{i}",
                voltages[i],
                expected,
                "voltage_V",
                p["instantaneous_tolerances"],
            )
        instant = p["instantaneous_tolerances"]
        constant = b["profiles"]["matched_constants"]
        vo = g["effective_bath_volume_m3"] / 1e-15
        for s in range(3):
            co = b["outside_mM"][s] + outside[s][0] / vo
            c.require(co > 0, "Nonpositive Cells outside inventory")
            checks.compare(
                f"{identifier}/outside_amount/{j}/{s}",
                obs["extracellular_amount"][j][s][0],
                co * vo,
                "amount_fmol",
                limits,
            )
            checks.compare(
                f"{identifier}/outside_concentration/{j}/{s}",
                obs["extracellular_concentration_mM"][j][s][0],
                co,
                "concentration_mM",
                instant,
            )
            for i in range(7):
                vi = g["cell_volumes_m3"][i] / 1e-15
                amount = b["inside_mM"][s] * vi + inside[s][i]
                c.require(amount > 0, "Nonpositive Cells intracellular inventory")
                checks.compare(
                    f"{identifier}/amount/{j}/{s}/{i}",
                    obs["amount"][j][s][i],
                    amount,
                    "amount_fmol",
                    limits,
                )
                checks.compare(
                    f"{identifier}/concentration/{j}/{s}/{i}",
                    obs["concentration_mM"][j][s][i],
                    amount / vi,
                    "concentration_mM",
                    instant,
                )
                c.require(
                    obs["leak_transferred"][j][s][i] == history["leak_transferred"][k][s][i],
                    "On-grid transfer observation differs",
                )
                point = {
                    "inside_mM": amount / vi,
                    "outside_mM": co,
                    "voltage_V": voltages[i],
                    "valence": b["expected_valence"][s],
                    "temperature_K": 310.15,
                    "area_m2": g["cell_areas_m2"][i],
                    "permeability_m_per_s": b["permeability_m_per_s"][s] * case["availability"],
                }
                actual_flux = obs["leak_flux_fmol_per_s"][j][s][i]
                checks.compare(
                    f"{identifier}/GHK/{j}/{s}/{i}",
                    actual_flux,
                    c.oracle(point, constant),
                    "flux_fmol_per_s",
                    instant,
                )
                if case["availability"] == 0:
                    c.require(actual_flux == 0, "Blocked Cells flux is nonzero")
            checks.compare(
                f"{identifier}/outside_rate/{j}/{s}",
                obs["extracellular_rate_fmol_per_s"][j][s][0],
                -math.fsum(obs["leak_flux_fmol_per_s"][j][s][:7]),
                "flux_fmol_per_s",
                instant,
            )
        for i in range(7):
            expected_current = (
                constant["F"]
                * 1e-15
                * math.fsum(
                    b["expected_valence"][s] * obs["leak_flux_fmol_per_s"][j][s][i]
                    for s in range(3)
                )
            )
            checks.compare(
                f"{identifier}/current/{j}/{i}",
                obs["membrane_current_A"][j][i],
                expected_current,
                "current_A",
                instant,
            )
        canonical.append(
            {
                "voltage_V": voltages,
                "amount_fmol": [v for row in inside for v in row[:7]] + [row[0] for row in outside],
                "transfer_fmol": [v for row in obs["leak_transferred"][j] for v in row[:7]],
                "flux_fmol_per_s": [v for row in obs["leak_flux_fmol_per_s"][j] for v in row[:7]]
                if t < p["duration_s"]
                else [],
                "current_A": obs["membrane_current_A"][j][:7] if t < p["duration_s"] else [],
            }
        )
    return canonical


def difference(label, left, right, limits, checks):
    maxima = {
        unit: 0.0
        for unit in ("voltage_V", "amount_fmol", "transfer_fmol", "flux_fmol_per_s", "current_A")
    }
    converted = limits | {"transfer_fmol": limits.get("transfer_fmol", limits["amount_fmol"])}
    for k, (a_row, b_row) in enumerate(zip(left, right, strict=True)):
        c.require(set(a_row) == set(b_row) == set(maxima), "Comparison quantities differ")
        for unit in maxima:
            for i, (v, w) in enumerate(zip(a_row[unit], b_row[unit], strict=True)):
                maxima[unit] = max(maxima[unit], abs(v - w))
                checks.compare(f"{label}/{k}/{unit}/{i}", v, w, unit, converted)
    return maxima


def audit_data(registered, output):
    p = registered["protocol"]
    c.require(
        p == c.read(ctx.PROTOCOL) and registered["base_protocol"] == c.read(a.PROTOCOL),
        "Protocol differs",
    )
    c.require(registered["geometry"] == ctx.native_geometry(), "Geometry source differs")
    c.require(
        registered["settings"] == c.read(ctx.evidence.SESSION / "betse.json")["settings"],
        "Registered mechanisms differ",
    )
    c.require(
        registered["cells_runtime"] == c.read(ctx.PRESERVATION)["runtime"],
        "Registered runtime differs",
    )
    native, local = c.read(output / "betse.json"), c.read(output / "cells.json")
    a.provenance(registered, native, local)
    c.require(
        native["engine"] == "actual_betse_full_init_loop"
        and local["engine"] == "unchanged_cells_checked_rk4_runner",
        "Not actual full engines",
    )
    c.require(
        native["trajectory_run"] is local["trajectory_run"] is True
        and local["device"] == "cpu"
        and local["x64_enabled"] is True
        and local["jit_disabled"] is False,
        "Execution context differs",
    )
    for record in (native, local):
        c.require(
            record["registration_sha256"] == c.sha(output / "registration.json"),
            "Worker inputs differ",
        )
        c.require(
            not any(w["category"] in p["forbidden_warning_categories"] for w in record["warnings"]),
            "Numerical runtime warning",
        )
    expected_native = {
        ctx.key(case["id"], profile, dt)
        for case in p["cases"]
        for profile in p["native_constant_profiles"]
        for dt in p["native_steps_s"]
    }
    c.require(
        set(native["results"]) == expected_native
        and set(local["results"]) == set(registered["cells_definitions"]),
        "Trajectory coverage differs",
    )
    checks, native_values, cells_values, refinements = Checks(), {}, {}, {}
    for case in p["cases"]:
        for profile in p["native_constant_profiles"]:
            for dt in p["native_steps_s"]:
                identifier = ctx.key(case["id"], profile, dt)
                pair = native["results"][identifier]
                c.require(
                    set(pair) == {"observed", "unobserved"}, "Noninterference partner missing"
                )
                records = {mode: c.read(output / path) for mode, path in pair.items()}
                for mode, record in records.items():
                    c.require(
                        record["mode"] == mode and record["id"] == identifier,
                        "Native partner identity differs",
                    )
                    c.require(
                        record["native_yaml_sha256"]
                        == c.sha((output / pair[mode]).parent / "native.yaml"),
                        "Native input YAML changed",
                    )
                c.require(
                    records["observed"]["ordinary"] == records["unobserved"]["ordinary"]
                    and records["observed"]["final"] == records["unobserved"]["final"]
                    and records["unobserved"]["trace"] is None,
                    "Observer noninterference failed",
                )
                for field in (
                    "dt_s",
                    "constants",
                    "geometry",
                    "settings",
                    "rho_channel",
                    "species",
                    "valence",
                    "permeability_m_per_s",
                    "configured_steps",
                    "native_pickle_present",
                ):
                    c.require(
                        records["observed"][field] == records["unobserved"][field],
                        "Noninterference partner parameters differ",
                    )
                native_values[identifier] = native_record(
                    registered, records["observed"], case, profile, dt, checks
                )
            keys = [ctx.key(case["id"], profile, dt) for dt in p["native_steps_s"]]
            # Coarse-to-middle is a contraction witness, not a selected-step acceptance.
            coarse = difference(
                "native_coarse/" + keys[0],
                native_values[keys[0]],
                native_values[keys[1]],
                {k: 1e100 for k in p["trajectory_tolerances"]},
                Checks(),
            )
            fine = difference(
                "native_refinement/" + keys[1],
                native_values[keys[1]],
                native_values[keys[2]],
                p["trajectory_tolerances"],
                checks,
            )
            for unit in fine:
                floor = p["instantaneous_tolerances"][
                    "amount_fmol" if unit == "transfer_fmol" else unit
                ]
                c.require(
                    fine[unit] <= p["refinement"]["native_contraction_max"] * coarse[unit] + floor,
                    "Native refinement does not contract above roundoff",
                )
            refinements[case["id"] + "/" + profile] = {
                "coarse_to_middle": coarse,
                "middle_to_fine": fine,
            }
        for backend in p["cells_backends"]:
            for dt in p["cells_steps_s"]:
                identifier = ctx.key(case["id"], backend, dt)
                record = c.read(output / local["results"][identifier])
                cells_values[identifier] = cells_record(
                    registered, record, case, backend, dt, checks
                )
            keys = [ctx.key(case["id"], backend, dt) for dt in p["cells_steps_s"]]
            refinements[case["id"] + "/" + backend] = difference(
                "cells_refinement/" + keys[0],
                cells_values[keys[0]],
                cells_values[keys[1]],
                p["instantaneous_tolerances"],
                checks,
            )
            target = native_values[
                ctx.key(case["id"], "matched_constants", p["native_steps_s"][-1])
            ]
            refinements[case["id"] + "/cross/" + backend] = difference(
                "cross/" + keys[-1],
                cells_values[keys[-1]],
                target,
                p["trajectory_tolerances"],
                checks,
            )
        for dt in p["cells_steps_s"]:
            keys = [ctx.key(case["id"], backend, dt) for backend in p["cells_backends"]]
            difference(
                "backend/" + keys[0],
                cells_values[keys[0]],
                cells_values[keys[1]],
                p["instantaneous_tolerances"],
                checks,
            )
    return {
        "status": "pass" if checks.failed_count == 0 else "failed",
        "comparisons": checks.count,
        "failed_comparisons": checks.failed_count,
        "maximum_normalized_error": checks.maximum,
        "worst": checks.worst,
        "first_failures": checks.failures,
        "refinements_and_cross_differences": refinements,
        "native_observed_runs": len(native_values),
        "native_unobserved_runs": len(native_values),
        "cells_runs": len(cells_values),
        "native_steps_observed": len(p["cases"])
        * len(p["native_constant_profiles"])
        * sum(round(p["duration_s"] / dt) for dt in p["native_steps_s"]),
        "trajectory_run": True,
        "biological_validation": False,
    }
