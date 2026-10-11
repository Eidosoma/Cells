"""Independent Cells state/readout/restart bindings and numeric-only checkpoint decoder."""

import ast
import hashlib
import json
import math
import struct
import zipfile

import feedback_audit_math as am

require, ind, ready = am.require, am.ind, am.ready


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def decode_npy(raw):
    require(raw[:8] == b"\x93NUMPY\x01\x00", "Unregistered NPY version")
    size = struct.unpack("<H", raw[8:10])[0]
    require(0 < size <= 4096 and len(raw) >= 10 + size, "Invalid NPY header length")
    header = ast.literal_eval(raw[10 : 10 + size].decode("ascii"))
    require(
        set(header) == {"descr", "shape", "fortran_order"} and header["fortran_order"] is False,
        "Invalid NPY header fields/layout",
    )
    shape, dtype = header["shape"], header["descr"]
    require(
        isinstance(shape, tuple) and all(type(n) is int and n >= 0 for n in shape),
        "Invalid NPY dimensions",
    )
    require(
        dtype in ("<f8", "<i8", "|b1") and math.prod(shape) <= 1000000, "Unsafe NPY dtype/extent"
    )
    payload = raw[10 + size :]
    width, code = (1, "B") if dtype == "|b1" else (8, "d" if dtype == "<f8" else "q")
    require(len(payload) == math.prod(shape) * width, "NPY payload length")
    values = [v[0] for v in struct.iter_unpack("<" + code, payload)]
    if dtype == "|b1":
        require(all(v in (0, 1) for v in values), "Noncanonical boolean checkpoint")
        values = list(map(bool, values))
    else:
        require(all(math.isfinite(v) for v in values), "Nonfinite checkpoint")
    iterator = iter(values)

    def reshape(dimensions):
        return (
            [reshape(dimensions[1:]) for _ in range(dimensions[0])]
            if dimensions
            else next(iterator)
        )

    return {"dtype": dtype, "shape": list(shape), "values": reshape(shape)}


def decode_npz(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(
            len(names) == len(set(names))
            and all(n.endswith(".npy") and "/" not in n for n in names),
            "Invalid NPZ membership",
        )
        require(
            sum(v.file_size for v in archive.infolist()) <= 128 * 1024**2,
            "Checkpoint decode budget",
        )
        return {name[:-4]: decode_npy(archive.read(name)) for name in names}


def layout(definition):
    """Rebuild every layout field from declared owners, capacities and chemistry."""
    model, x = definition["model"], definition["execution"]
    n, nm, nk, ne, no = (
        x[k]
        for k in (
            "capacity",
            "membrane_capacity",
            "channel_capacity",
            "edge_capacity",
            "extracellular_capacity",
        )
    )
    entries = model["cells"]
    count, channels = len(entries), sum(e["channel"] is not None for e in entries)
    result = {}

    def put(name, values, dtype="<f8"):
        shape = []
        node = values
        while isinstance(node, list):
            shape.append(len(node))
            node = node[0] if node else 0
        result[name] = {"dtype": dtype, "shape": shape, "values": values}

    for mask, ids, capacity, live in (
        ("active", "ids", n, count),
        ("membrane_active", "membrane_ids", nm, count),
        ("channel_active", "channel_ids", nk, channels),
        ("junction_active", "junction_ids", ne, 0),
        ("extracellular_active", "extracellular_ids", no, 1),
    ):
        put(mask, [i < live for i in range(capacity)], "|b1")
        put(ids, [i + 1 if i < live else -1 for i in range(capacity)], "<i8")
    put("species_codes", [1, 2, 3], "<i8")
    put("valence", [[s["valence"]] for s in model["species"]], "<i8")
    put("stoichiometry", [[0] * nm for _ in range(3)], "<i8")
    put(
        "amount_reference",
        [
            [e["cell"]["initial_amount_fmol"][s] for e in entries] + [0.0] * (n - count)
            for s in ready.SPECIES
        ],
    )
    put(
        "extracellular_amount_reference",
        [
            [model["extracellular"]["initial_amount_fmol"][s]] + [0.0] * (no - 1)
            for s in ready.SPECIES
        ],
    )
    for name, capacity in (
        ("permeability", nm),
        ("junction_permeability", ne),
        ("junction_residual", ne),
    ):
        put(name, [[0.0] * capacity for _ in range(3)])
    put("temperature", [model["temperature_K"]] * no)
    for name, capacity in (("owners", nm), ("cell_membranes", n), ("channel_membranes", nk)):
        live = channels if name == "channel_membranes" else count
        put(name, list(range(live)) + [0] * (capacity - live), "<i8")
    for name, capacity in (("outside_owners", nm), ("senders", ne), ("receivers", ne)):
        put(name, [0] * capacity, "<i8")
    put("channel_species", [1] * channels + [0] * (nk - channels), "<i8")
    put("channel_laws", [1] * channels + [-1] * (nk - channels), "<i8")
    for name, capacity, default in (
        ("volume", n, 1.0),
        ("voltage_reference", n, 0.0),
        ("fixed_charge_equivalent", n, 0.0),
        ("area", nm, 1.0),
        ("specific_capacitance", nm, 1.0),
        ("capacitance", nm, 1.0),
        ("pump_capacity", nm, 0.0),
        ("pump_drive", nm, 0.0),
        ("channel_permeability", nk, 0.0),
        ("channel_abundance", nk, 0.0),
        ("junction_area", ne, 1.0),
        ("junction_sensitivity", ne, 1.0),
        ("junction_half_voltage", ne, 0.0),
        ("junction_tau", ne, 1.0),
        ("extracellular_volume", no, 1.0),
        ("extracellular_fixed_charge_equivalent", no, 0.0),
    ):
        put(name, [default] * capacity)
    for i, entry in enumerate(entries):
        cell, membrane, channel = entry["cell"], entry["membrane"], entry["channel"]
        fields = {
            "volume": cell["volume_pL"],
            "voltage_reference": cell["initial_voltage_V"],
            "fixed_charge_equivalent": cell["fixed_charge_equivalent_fmol"],
            "area": membrane["area_m2"],
            "specific_capacitance": membrane["specific_capacitance_F_per_m2"],
            "capacitance": membrane["area_m2"] * membrane["specific_capacitance_F_per_m2"],
        }
        if channel is not None:
            fields |= {
                "channel_permeability": channel["max_permeability_m_per_s"],
                "channel_abundance": channel["abundance"],
            }
        for name, value in fields.items():
            result[name]["values"][i] = value
    bath = model["extracellular"]
    result["extracellular_volume"]["values"][0] = bath["volume_pL"]
    result["extracellular_fixed_charge_equivalent"]["values"][0] = bath[
        "fixed_charge_equivalent_fmol"
    ]
    # The small initial cancellation residual is independently bounded, not reanchored.
    put(
        "initial_countercharge_C",
        96485.33212331001
        * 1e-15
        * math.fsum(
            [
                bath["fixed_charge_equivalent_fmol"],
                *(s["valence"] * bath["initial_amount_fmol"][s["id"]] for s in model["species"]),
            ]
        ),
    )
    result["initial_countercharge_C"]["values"] = math.fsum(
        [
            result["initial_countercharge_C"]["values"],
            *(
                e["membrane"]["area_m2"]
                * e["membrane"]["specific_capacitance_F_per_m2"]
                * e["cell"]["initial_voltage_V"]
                for e in entries
            ),
        ]
    )
    return result


def checkpoint(directory, record, index, source_hashes, read_json, file_sha):
    manifest = read_json(directory / "manifest.json")
    fields = {
        "schema_version",
        "kind",
        "spec",
        "spec_sha256",
        "clock",
        "random_state",
        "runtime",
        "source_hashes",
        "state_sha256",
        "manifest_sha256",
    }
    require(
        set(manifest) == fields
        and manifest["manifest_sha256"]
        == digest({k: v for k, v in manifest.items() if k != "manifest_sha256"}),
        "Checkpoint manifest checksum/fields",
    )
    require(
        manifest["schema_version"] == 1
        and manifest["kind"] == "cells_complete_numerical_checkpoint"
        and manifest["random_state"] is None,
        "Checkpoint schema/kind",
    )
    require(
        manifest["runtime"] == record["runtime"] and manifest["source_hashes"] == source_hashes,
        "Checkpoint source/runtime",
    )
    require(
        manifest["spec"] == record["canonical_definition"] == record["definition"]
        and manifest["spec_sha256"] == digest(manifest["spec"]),
        "Checkpoint complete definition",
    )
    require(
        manifest["state_sha256"] == file_sha(directory / "state.npz"), "Checkpoint NPZ checksum"
    )
    require(
        manifest["clock"]
        == {
            "time": record["times"]["values"][index],
            "step_index": record["start_step"] + index,
            "event_index": 0,
        },
        "Checkpoint complete clock",
    )
    expected = layout(record["definition"])
    expected |= {
        name: {"dtype": "<f8", "shape": shape, "values": record["history"][name]["values"][index]}
        for name, shape in ready.STATE_SHAPES.items()
    }
    actual = decode_npz(directory / "state.npz")
    require(set(actual) == set(expected), "Checkpoint state/layout membership")
    for name in expected:
        require(
            actual[name]["dtype"] == expected[name]["dtype"]
            and actual[name]["shape"] == expected[name]["shape"],
            "Checkpoint dtype/shape",
        )
        if name == "initial_countercharge_C":
            ind.near(actual[name]["values"], expected[name]["values"], 1e-20)
        else:
            require(
                actual[name]["values"] == expected[name]["values"],
                "Checkpoint state/layout value: " + name,
            )
    return len(actual)


def unpack_record(record):
    for value in [record["times"], *record["history"].values(), *record["observations"].values()]:
        ind.array_bytes(value, value["shape"])
    return (
        record["times"]["values"],
        {k: v["values"] for k, v in record["history"].items()},
        {k: v["values"] for k, v in record["observations"].items()},
    )


def packed(history, index, enabled):
    return (
        history["amount_increment"][index][1][:7]
        + (history["gate"][index][0][:7] + history["gate"][index][1][:7] if enabled else [])
        + history["dissipated_energy_pJ"][index][:7]
    )


def points(observations):
    return [
        {
            "gate": [v[:7] for v in observations["gate"][i]],
            "voltage_V": observations["voltage_V"][i][:7],
            "cell_K_fmol": observations["amount"][i][1][:7],
            "bath_K_fmol": observations["extracellular_amount"][i][1][0],
            "transfer_fmol": observations["channel_transferred"][i][:7],
            "flux_fmol_per_s": observations["channel_flux_fmol_per_s"][i][:7],
            "permeability_m_per_s": observations["channel_effective_permeability_m_per_s"][i][:7],
            "inward_current_A": observations["membrane_current_A"][i][:7],
            "energy_pJ": observations["dissipated_energy_pJ"][i][:7],
        }
        for i in range(len(observations["times"]))
    ]


class Cells:
    def __init__(self, r, records, resumed):
        self.r, self.records, self.resumed = r, records, resumed
        self.values = {key: unpack_record(row) for key, row in records.items()}
        self.resumed_values = {key: unpack_record(row) for key, row in resumed.items()}
        self.points, self.own_points = {}, {}
        for key, row in records.items():
            self.validate(key, row)

    def validate(self, key, row):
        p, definition = (
            self.r["reference_parameters"][key.split("/")[0]],
            self.r["cells_definitions"][key],
        )
        enabled = any(p["channel_enabled"])
        times, history, obs = self.values[key]
        dt, end = definition["execution"]["dt"], definition["experiment"]["end_time"]
        count = round(end / dt)
        require(
            row["id"] == key and row["definition"] == row["canonical_definition"] == definition,
            "Cells definition identity",
        )
        require(
            row["runtime"] == self.r["preparation_registration"]["cells_runtime"],
            "Cells runtime identity",
        )
        require(
            row["start_step"] == 0
            and row["final_step_index"] == count
            and times == [i * dt for i in range(count)] + [end],
            "Cells full accepted clock",
        )
        require(set(history) == set(ready.STATE_SHAPES), "Cells complete history membership")
        initial = ready.expected_initial(enabled)
        for name, shape in ready.STATE_SHAPES.items():
            require(
                row["history"][name]["shape"] == [count + 1, *shape]
                and history[name][0] == initial[name],
                "Cells history shape/initial state",
            )
        for j in range(len(times)):
            state = {name: values[j] for name, values in history.items()}
            inactive = [
                state[k]
                for k in (
                    "leak_transferred",
                    "pump_cycles",
                    "junction_gate",
                    "junction_transferred",
                    "junction_dissipated_energy_pJ",
                )
            ]
            inactive += [
                state["amount_increment"][0],
                state["amount_increment"][2],
                state["extracellular_amount_increment"][0],
                state["extracellular_amount_increment"][2],
                [v[7:] for v in state["amount_increment"]],
                [v[1:] for v in state["extracellular_amount_increment"]],
                [v[7:] for v in state["gate"]],
                state["channel_transferred"][7:],
                state["dissipated_energy_pJ"][7:],
            ]
            if not enabled:
                inactive += [state["gate"]]
            if not key.startswith("active_channel/"):
                inactive += [
                    state["amount_increment"],
                    state["extracellular_amount_increment"],
                    state["dissipated_energy_pJ"],
                ]
            require(all(v == 0 for v in am.flat(inactive)), "Cells inactive state/padding")
            own = am.readout(p, packed(history, j, enabled))
            require(all(v >= -1e-12 for v in own["energy_pJ"]), "Cells negative dissipation")
        require(
            obs["times"] == self.r["protocol"]["common_times_s"], "Cells common observation grid"
        )
        self.points[key] = points(obs)
        self.own_points[key] = [
            am.readout(p, packed(history, round(t / dt), enabled)) for t in obs["times"]
        ]

    def resolve_state(self, name):
        parts = name.split("/")
        key, action, index, tail = "/".join(parts[:3]), parts[3], int(parts[4]), parts[5:]
        _times, history, obs = self.values[key]
        p = self.r["reference_parameters"][parts[0]]
        if action == "transfer":
            actual, expected, unit = (
                history["channel_transferred"][index][:7],
                history["amount_increment"][index][1][:7],
                "state",
            )
        elif action == "bath":
            actual, expected, unit = (
                history["extracellular_amount_increment"][index][1][0],
                -math.fsum(history["amount_increment"][index][1][:7]),
                "state",
            )
        elif action == "energy":
            actual, expected, unit = (
                math.fsum(history["dissipated_energy_pJ"][index][:7]),
                am.dissipated(p, history["amount_increment"][index][1][:7]),
                "energy",
            )
        elif action == "sample":
            field, tail = tail[0], tail[1:]
            accepted_index = round(
                obs["times"][index] / self.records[key]["definition"]["execution"]["dt"]
            )
            actual, expected = obs[field][index], history[field][accepted_index]
            unit = "gate" if field == "gate" else "state"
        else:
            require(action == "constitutive", "Unknown Cells state identity")
            field, tail = tail[0], tail[1:]
            actual, expected = self.points[key][index][field], self.own_points[key][index][field]
            unit = {
                "gate": "gate",
                "voltage_V": "voltage_V",
                "cell_K_fmol": "amount_fmol",
                "bath_K_fmol": "amount_fmol",
                "transfer_fmol": "amount_fmol",
                "flux_fmol_per_s": "flux_fmol_per_s",
                "permeability_m_per_s": "permeability_m_per_s",
                "inward_current_A": "current_A",
                "energy_pJ": "energy_pJ",
            }[field]
        return am.component(actual, tail), am.component(expected, tail), unit

    def resolve_pair(self, name, key=None):
        parts = name.split("/")
        if key is None:
            variant, group, field, *tail = parts
            dt = self.r["protocol"]["cells_eager_step_s"]
            a, b = (
                self.values[variant + f"/{backend}/dt_{dt:.8g}"]
                for backend in ("jax_jit", "jax_eager")
            )
            start = 0
        else:
            require("/".join(parts[:3]) == key, "Restart case identity")
            group, field, *tail = parts[3:]
            a, b = self.values[key], self.resumed_values[key]
            start = round(
                self.r["protocol"]["restart_time_s"] / self.r["protocol"]["restart_step_s"]
            )
            resumed = self.resumed[key]
            require(
                resumed["definition"] == self.records[key]["definition"]
                and resumed["runtime"] == self.records[key]["runtime"]
                and resumed["start_step"] == start
                and resumed["final_step_index"] == self.records[key]["final_step_index"],
                "Restart full metadata",
            )
        require(a[0][start:] == b[0], "Restart/backend accepted grid")
        if group == "history":
            actual, expected = a[1][field][start:], b[1][field]
        else:
            require(group == "observations", "Unknown restart/backend field")
            actual = [
                value
                for time_s, value in zip(a[2]["times"], a[2][field], strict=True)
                if time_s >= b[0][0]
            ]
            expected = b[2][field]
        return (
            am.component(actual, tail),
            am.component(expected, tail),
            "gate" if field == "gate" else "state",
        )
