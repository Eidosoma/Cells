"""Independent paired Cells validation and raw-byte checkpoint replay, no NumPy."""

import ast
import hashlib
import math
import struct
import zipfile

import feedback_audit_math as am
import history_audit_context as ctx
from feedback_audit_cells import Cells as PriorCells
from feedback_audit_cells import digest, packed, points

require, ind, ready = am.require, am.ind, am.ready


def initial_from_definition(definition):
    state = {name: ready.zeros(shape) for name, shape in ready.STATE_SHAPES.items()}
    channels = [
        entry["channel"] for entry in definition["model"]["cells"] if entry["channel"] is not None
    ]
    require(len(channels) <= len(state["gate"][0]), "Initial channel extent")
    for i, channel in enumerate(channels):
        gates = channel["initial_gate"]
        require(set(gates) == {"m", "h"}, "Initial gate fields")
        for j, name in enumerate(("m", "h")):
            value = ind.finite(gates[name])
            require(0 <= value <= 1, "Initial gate domain")
            state["gate"][j][i] = value
    return state


class Cells(PriorCells):
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
        initial = initial_from_definition(definition)
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


def raw_array(raw):
    require(raw[:8] == b"\x93NUMPY\x01\x00" and len(raw) >= 10, "Numeric checkpoint NPY version")
    size = int.from_bytes(raw[8:10], "little")
    require(0 < size <= 4096 and len(raw) >= 10 + size, "Numeric checkpoint header length")
    header = ast.literal_eval(raw[10 : 10 + size].decode("ascii"))
    require(
        isinstance(header, dict)
        and set(header) == {"descr", "shape", "fortran_order"}
        and header["fortran_order"] is False,
        "Numeric checkpoint header fields",
    )
    dtype, shape = header["descr"], header["shape"]
    require(
        dtype in ("<f8", "<i8", "|b1")
        and isinstance(shape, tuple)
        and all(type(n) is int and n >= 0 for n in shape)
        and math.prod(shape) <= 1000000,
        "Numeric checkpoint dtype/extent",
    )
    payload = raw[10 + size :]
    width, code = (1, "B") if dtype == "|b1" else (8, "d" if dtype == "<f8" else "q")
    require(len(payload) == math.prod(shape) * width, "Numeric checkpoint payload length")
    require(
        all(
            (v[0] in (0, 1) if dtype == "|b1" else math.isfinite(v[0]))
            for v in struct.iter_unpack("<" + code, payload)
        ),
        "Numeric checkpoint scalar domain",
    )
    return {"dtype": dtype, "shape": list(shape), "sha256": hashlib.sha256(payload).hexdigest()}


def raw_checkpoint(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(
            len(names) == len(set(names))
            and len(names) == 54
            and all(n.endswith(".npy") and "/" not in n for n in names),
            "Numeric checkpoint membership",
        )
        require(
            sum(v.file_size for v in archive.infolist()) <= 128 * 1024**2,
            "Numeric checkpoint decode cap",
        )
        return {name[:-4]: raw_array(archive.read(name)) for name in names}


def layout_contract(variant, history, backend):
    earlier = ctx.prior.CAPTURE / "cells" / variant / "jax_jit/dt_5e-05/final-checkpoint/state.npz"
    layout = {k: v for k, v in raw_checkpoint(earlier).items() if k not in ready.STATE_SHAPES}
    prepared = ctx.c.read(ctx.pilot.review.CAPTURE / "cells.json")["rows"]
    expected = prepared[variant + "/" + history + "/" + backend]["layout_sha256"]
    require(
        {k: v["sha256"] for k, v in layout.items()} == expected and len(layout) == 44,
        "Audited initial-layout link",
    )
    return layout


def checkpoint(directory, record, index, source_hashes, layout):
    manifest = ctx.c.read(directory / "manifest.json")
    require(
        set(manifest)
        == {
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
        },
        "Paired checkpoint manifest fields",
    )
    require(
        manifest["manifest_sha256"]
        == digest({k: v for k, v in manifest.items() if k != "manifest_sha256"}),
        "Paired checkpoint manifest digest",
    )
    require(
        manifest["schema_version"] == 1
        and manifest["kind"] == "cells_complete_numerical_checkpoint"
        and manifest["random_state"] is None,
        "Paired checkpoint kind",
    )
    require(
        manifest["spec"] == record["definition"] == record["canonical_definition"]
        and manifest["spec_sha256"] == digest(record["canonical_definition"]),
        "Paired checkpoint definition",
    )
    require(
        manifest["runtime"] == record["runtime"] and manifest["source_hashes"] == source_hashes,
        "Paired checkpoint runtime/source",
    )
    require(
        manifest["clock"]
        == {
            "time": record["times"]["values"][index],
            "step_index": record["start_step"] + index,
            "event_index": 0,
        },
        "Paired checkpoint full clock",
    )
    require(
        manifest["state_sha256"] == ctx.c.sha(directory / "state.npz"),
        "Paired checkpoint file digest",
    )
    expected = layout | {
        name: {
            "dtype": "<f8",
            "shape": shape,
            "sha256": ctx.pilot.review.numeric_digest(
                {"dtype": "<f8", "values": record["history"][name]["values"][index]}
            ),
        }
        for name, shape in ready.STATE_SHAPES.items()
    }
    require(
        raw_checkpoint(directory / "state.npz") == expected, "Paired complete state/layout bytes"
    )
    return len(expected)
