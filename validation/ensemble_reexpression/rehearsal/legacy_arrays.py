"""The legacy runs of the invented worlds as READOUTS.md section 2 names them.

A `windows` world's runs are the folder's `window-*.npz`, read in the natural order of their names;
a row that two windows share belongs to the earlier one (SPEC section 4). An assembly world's are
`checkpoint/state.npz` and, for the clusters, `observations/tick-*.json` (READOUTS section 4). An
index is the entity's position in the definition's list, in the order the definition gives them.
"""

import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_inputs  # noqa: E402
import rules  # noqa: E402

STEPS = ("h", "h2", "h4")
REDUCTION = {"h": 1, "h2": 2, "h4": 4}


def natural(path):
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", str(path))]


def order(world):
    """{kind: [ids]} of a world's definition lists, and the regions' order in the legacy arrays."""
    w = make_inputs.WORLDS[world]
    membrane, chan = make_inputs.names(w)
    local = next(o for o, v in w["outside"].items() if v["faces"])
    return dict(
        species=list(make_inputs.SPECIES),
        cells=list(w["cells"]),
        membranes=list(membrane.values()),
        channels=[chan[c] for c in w["cells"] if c in chan],
        junctions=list(w["junctions"]),
        faces=list(w["faces"]),
        regions=[local, *(o for o in w["outside"] if o != local)],
        gauge=w["gauge"],
    )


# ------------------------------------------------------------------ the runs


def windows(folder):
    """{array name: array over the accepted rows}, with the shared rows of two windows once."""
    files = sorted(Path(folder).glob("window-*.npz"), key=natural)
    out, observed = {}, {}
    for i, path in enumerate(files):
        with np.load(path, allow_pickle=False) as arrays:
            for key in arrays.files:
                if key.startswith("observations."):
                    observed.setdefault(key, []).append(arrays[key])
                elif key == "times" or key.startswith("history."):
                    v = arrays[key]
                    out.setdefault(key, []).append(v if i == 0 else v[1:])
    result = {k: np.concatenate(v) for k, v in out.items()}
    result.update({k: np.concatenate(v) for k, v in observed.items()})
    return result


def rows_at(times, wanted):
    """The index of each wanted time among `times`, matched within 1e-12 s (SPEC section 4)."""
    index = []
    for t in wanted:
        near = np.flatnonzero(np.abs(times - t) <= 1e-12)
        if len(near) != 1:
            raise ValueError(f"{len(near)} rows at {t!r}")
        index.append(int(near[0]))
    return index


def entries_of_windows(world, arrays):
    """{entry: array [time, entity]} of a `jupiter` or `integrated` world, at its compared times."""
    w, o = make_inputs.WORLDS[world], order(world)
    h = arrays
    grid = [i * w["spacing"] for i in range(round(w["end"] / w["spacing"]) + 1)]
    row = rows_at(h["times"], grid)
    pot = rows_at(h["observations.times"], w["potentials"])
    n = {k: len(o[k]) for k in ("cells", "membranes", "channels", "junctions", "faces", "regions")}
    out = {}
    for i, x in enumerate(o["species"]):
        out[f"n_cell_{x}"] = h["history.amount_increment"][row, i, : n["cells"]]
        out[f"n_out_{x}"] = h["history.extracellular_amount_increment"][row, i, : n["regions"]]
        if any(w["leaks"][c][x] for c in w["cells"]):
            out[f"leak_{x}"] = h["history.leak_transferred"][row, i, : n["membranes"]]
        if n["junctions"]:
            out[f"junction_{x}"] = h["history.junction_transferred"][row, i, : n["junctions"]]
        if n["faces"]:
            out[f"face_{x}"] = h["history.face_transferred"][row, i, : n["faces"]]
    if n["channels"]:
        out["channel_K"] = h["history.channel_transferred"][row][:, : n["channels"]]
        out["gate_m"] = h["history.gate"][row, 0, : n["channels"]]
        out["gate_h"] = h["history.gate"][row, 1, : n["channels"]]
    if w["pumps"]:
        out["pump"] = h["history.pump_cycles"][row][:, : n["membranes"]]
    if n["junctions"]:
        out["junction_gate"] = h["history.junction_gate"][row][:, : n["junctions"]]
        out["heat_junction"] = h["history.junction_dissipated_energy_pJ"][row][:, : n["junctions"]]
    if n["faces"]:
        out["heat_face"] = h["history.face_dissipated_energy_pJ"][row][:, : n["faces"]]
    if w["pumps"] or w["channels"]:
        out["heat_membrane"] = h["history.dissipated_energy_pJ"][row][:, : n["membranes"]]
    out["voltage"] = h["observations.voltage_V"][pot][:, : n["membranes"]]
    if w["consumer"] == "jupiter":
        keep = [i for i, r in enumerate(o["regions"]) if r != o["gauge"]]
        out["phi_out"] = h["observations.extracellular_potential_V"][pot][:, keep]
    return out


def assembly(folder, world):
    """The final checkpoint's arrays and, for a cluster, its summaries: {name: array}."""
    folder = Path(folder)
    with np.load(folder / "checkpoint" / "state.npz", allow_pickle=False) as arrays:
        out = {k: arrays[k] for k in arrays.files}
    if make_inputs.WORLDS[world]["consumer"] == "cell":
        result = json.loads((folder / "result.json").read_text())
        out["final_voltage_V"] = np.array(result["final_voltage_V"])[:, None, None]
    else:
        summaries = make_inputs.WORLDS[world]["summaries"]
        rows = []
        dt = json.loads((folder / "registration.json").read_text())["definition"]["ionic"][
            "execution"
        ]["dt"]
        for t in summaries:
            rows.append(
                json.loads((folder / "observations" / f"tick-{round(t / dt):07d}.json").read_text())
            )
        out["summary_voltage_V"] = np.array([r["final_voltage_V"] for r in rows])
        out["summary_channel_fmol"] = np.array([r["channel_transferred_fmol"] for r in rows])
    return out


def entries_of_assembly(world, arrays, k):
    """{entry: array [time, entity]} of world ID `k` of an assembly run, at its compared times."""
    w, o = make_inputs.WORLDS[world], order(world)
    n = {
        key: len(o[key])
        for key in ("cells", "membranes", "channels", "junctions", "faces", "regions")
    }

    def get(name):
        return arrays["ionic_" + name][k]

    out = {}
    for i, x in enumerate(o["species"]):
        out[f"n_cell_{x}"] = get("amount_increment")[None, i, : n["cells"]]
        out[f"n_out_{x}"] = get("extracellular_amount_increment")[None, i, : n["regions"]]
        out[f"leak_{x}"] = get("leak_transferred")[None, i, : n["membranes"]]
        if n["junctions"]:
            out[f"junction_{x}"] = get("junction_transferred")[None, i, : n["junctions"]]
        if n["faces"]:
            out[f"face_{x}"] = get("face_transferred")[None, i, : n["faces"]]
    out["channel_K"] = get("channel_transferred")[None, : n["channels"]]
    out["gate_m"] = get("gate")[0][None, : n["channels"]]
    out["gate_h"] = get("gate")[1][None, : n["channels"]]
    out["pump"] = get("pump_cycles")[None, : n["membranes"]]
    if n["junctions"]:
        out["junction_gate"] = get("junction_gate")[None, : n["junctions"]]
        out["heat_junction"] = get("junction_dissipated_energy_pJ")[None, : n["junctions"]]
    if n["faces"]:
        out["heat_face"] = get("face_dissipated_energy_pJ")[None, : n["faces"]]
    out["heat_membrane"] = get("dissipated_energy_pJ")[None, : n["membranes"]]
    if w["consumer"] == "cell":
        out["voltage"] = arrays["final_voltage_V"][k][:, : n["cells"]]
    else:
        out["voltage"] = arrays["summary_voltage_V"][:, k, : n["cells"]]
        out["channel_K_summary"] = arrays["summary_channel_fmol"][:, k, : n["channels"]]
    return out


def run_folder(roots, world, step, seed=None):
    """A run's folder. `roots` is one capture folder, or several separated by `:`, of which the
    first that holds the run is meant."""
    name = f"{world}-{step}" if seed is None else f"{world}-{step}-s{seed}"
    options = [Path(r) / "runs" / name for r in str(roots).split(":")]
    return next((o for o in options if o.exists()), options[0])


def families(world):
    """[(seed index, world ID)] of an assembly world's judged families, or [None]."""
    if make_inputs.WORLDS[world]["consumer"] not in ("cell", "base"):
        return [None]
    return [(s, k) for s in range(make_inputs.SEEDS) for k in range(make_inputs.IDS)]


def load(root, world, family=None, steps=STEPS):
    """The three legacy runs of a family as entries: [{entry: array}] for h, h2, h4."""
    if family is None:
        return [entries_of_windows(world, windows(run_folder(root, world, s))) for s in steps]
    seed, k = family
    return [
        entries_of_assembly(world, assembly(run_folder(root, world, s, seed), world), k)
        for s in steps
    ]


# ------------------------------------------------------------------ classes, CRITERIA section 4.3


def differences(three):
    """{entry: (d2, d1, U_l, largest)} of three runs at h, h/2, h/4."""
    l1, l2, l3 = three
    out = {}
    for e in l3:
        d2 = float(np.max(np.abs(l2[e] - l1[e]), initial=0.0))
        d1 = float(np.max(np.abs(l3[e] - l2[e]), initial=0.0))
        out[e] = (d2, d1, max(d1 / 15, d2 / 240), float(np.max(np.abs(l3[e]), initial=0.0)))
    return out


def steps_of(world):
    """(the legacy run's finest step count, the candidate's finest step count)."""
    w = make_inputs.WORLDS[world]
    return (
        rules.grid_steps(w["end"], w["legacy"] / 4),
        rules.grid_steps(w["end"], w["candidate"][-1]),
    )


def zero_scale(world, scales, entry):
    key = rules.base(entry, scales)
    return key in scales and scales[key] == 0.0


def sig(x, digits=3):
    return float(f"{x:.{digits}g}")
