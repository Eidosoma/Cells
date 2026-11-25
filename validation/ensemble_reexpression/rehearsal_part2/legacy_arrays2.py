"""The legacy runs of the invented worlds of Part 2, as PART2.md section 6.1 names them.

A child's run is the folder's `window-*.npz` (Part 1's reader), a cluster's `checkpoint/state.npz`
and `observations/tick-*.json`. The chemical rows and the reactions are in the IDs' sorted order;
every other index is the entity's position in the definition's list. The two heats of reactions are
the sums over the compartment's reactions (the judge's sum), and `exchange_x`, `heat_membrane`,
`heat_junction` and `heat_store_leak` are the captured sums (section 6.2).
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "rehearsal"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import legacy_arrays as one  # noqa: E402
import make_inputs2 as m  # noqa: E402
import rules  # noqa: E402

STEPS, REDUCTION = one.STEPS, one.REDUCTION
windows, differences, sig, natural = one.windows, one.differences, one.sig, one.natural


def rows_at(times, wanted, tolerance=1e-12):
    """The index of each wanted time among `times`, matched within 1e-12 s (SPEC section 4)."""
    index = []
    for t in wanted:
        near = np.flatnonzero(np.abs(times - t) <= tolerance)
        if len(near) != 1:
            raise ValueError(f"{len(near)} rows at {t!r}")
        index.append(int(near[0]))
    return index


def child_of(world):
    return m.CLUSTERS[world]["child"] if world in m.CLUSTERS else world


def order(world):
    """{kind: [ids]} of a world's definition lists, and the sorted chemical axes."""
    w = m.WORLDS[child_of(world)]
    membrane, chan = m.names(w)
    return dict(
        species=list(m.SPECIES),
        cells=list(w["cells"]),
        membranes=list(membrane.values()),
        channels=[chan[c] for c in w["cells"] if c in chan],
        junctions=list(w["junctions"]),
        faces=list(w["faces"]),
        regions=["bath", *(o for o in w["outside"] if o != "bath")],
        chemical=sorted(m.rows(w)),
        reactions=sorted(m.reactions(w)),
        plasma="plasma" in w,
        cav="cav" in w,
    )


def compared(world):
    """The compared times of a child's rows: the fine grid, then the coarse one (section 5)."""
    out = []
    for first, last, spacing in (world["fine"], world["coarse"]):
        n = round((last - first) / spacing)
        out += [first + i * spacing for i in range(n + 1)]
    return out


def entries(world, get):
    """{entry: array [time, entity]} of the rows' entries. `get(name)` is the array [time, ...] of
    the captured state field."""
    o = order(world)
    w = m.WORLDS[child_of(world)]
    n = {k: len(v) for k, v in o.items() if isinstance(v, list)}
    nc, nm = n["cells"], n["membranes"]
    out = {}
    for i, x in enumerate(o["species"]):
        out[f"n_out_{x}"] = get("extracellular_amount_increment")[:, i, : n["regions"]]
        out[f"leak_{x}"] = get("leak_transferred")[:, i, :nm]
        if n["junctions"]:
            out[f"junction_{x}"] = get("junction_transferred")[:, i, : n["junctions"]]
        out[f"face_{x}"] = get("face_transferred")[:, i, : n["faces"]]
        out[f"exchange_{x}"] = get("amount_increment")[:, i, :nc]
    if n["channels"]:
        out["channel_K"] = get("channel_transferred")[:, : n["channels"]]
        out["gate_m"] = get("gate")[:, 0, : n["channels"]]
        out["gate_h"] = get("gate")[:, 1, : n["channels"]]
    out["pump"] = get("pump_cycles")[:, :nm]
    if n["junctions"]:
        out["junction_gate"] = get("junction_gate")[:, : n["junctions"]]
        out["heat_junction"] = get("junction_dissipated_energy_pJ")[:, : n["junctions"]]
    out["heat_face"] = get("face_dissipated_energy_pJ")[:, : n["faces"]]
    out["heat_membrane"] = get("dissipated_energy_pJ")[:, :nm]
    # The chemical rows: [time, store, row, part] with part 0 the cytosol, 1 the store.
    chemical = get("chemical_amount_increment")
    for j, c in enumerate(o["chemical"]):
        out[f"cyt_{c}"] = chemical[:, :nc, j, 0]
        out[f"store_{c}"] = chemical[:, :nc, j, 1]
    passive = get("er_passive_transferred")
    out["store_leak_Ca"] = passive[:, :nc, o["chemical"].index("Ca")]
    out["store_leak_K"] = passive[:, :nc, o["chemical"].index("K")]
    out["store_pump"] = get("er_pump_transferred")[:, :nc, 0]
    out["store_release"] = get("er_release_transferred")[:, :nc, 0]
    transport = get("er_transport_dissipated_energy_pJ")
    out["heat_store_leak"] = transport[:, :nc, 0]
    out["heat_store_pump"] = transport[:, :nc, 1]
    out["heat_store_release"] = transport[:, :nc, 2]
    extent, heat = get("reaction_extent"), get("reaction_dissipated_energy_pJ")
    parts = {r: v[0] for r, v in m.reactions(w).items()}
    for part, name in (("cytosol", "heat_reactions_cytosol"), ("er", "heat_reactions_store")):
        mine = [j for j, r in enumerate(o["reactions"]) if parts[r] == part]
        out[name] = heat[:, :nc][:, :, mine].sum(-1)
    for j, r in enumerate(o["reactions"]):
        out[f"extent_{r}"] = extent[:, :nc, j]
    if o["plasma"]:
        out["ca_pump"] = get("plasma_pump_cycles")[:, :nm]
        out["exchanger"] = get("plasma_exchange_cycles")[:, :nm]
        out["heat_ca_pump"] = get("plasma_dissipated_energy_pJ")[:, 0, :nm]
        out["heat_exchanger"] = get("plasma_dissipated_energy_pJ")[:, 1, :nm]
    if o["cav"]:
        out["ca_channel"] = get("calcium_channel_transferred")[:, :nm]
        out["heat_ca_channel"] = get("calcium_channel_dissipated_energy_pJ")[:, :nm]
        out["ca_gate_m"] = get("calcium_gate")[:, 0, :nm]
        out["ca_gate_h"] = get("calcium_gate")[:, 1, :nm]
    return out


def chemical_order(world):
    """The captured axis of the chemical rows is the definition's parsed order; the reader checks it
    against the sorted one (section 6)."""
    return order(world)["chemical"]


def entries_of_windows(world, arrays):
    """A child's entries at its compared times, with the three potentials."""
    w, o = m.WORLDS[world], order(world)
    row = rows_at(arrays["times"], compared(w))
    pot = rows_at(arrays["observations.times"], w["potentials"])
    out = entries(world, lambda name: arrays["history." + name][row])
    out["voltage"] = arrays["observations.plasma_voltage_V"][pot][:, : len(o["membranes"])]
    keep = [i for i, r in enumerate(o["regions"]) if r != "bath"]
    out["phi_out"] = arrays["observations.extracellular_potential_V"][pot][:, keep]
    out["store_voltage"] = arrays["observations.er_voltage_V"][pot][:, : len(o["cells"])]
    return out


def assembly(folder, world):
    """The final checkpoint's arrays and the summaries of a cluster's run: {name: array}."""
    folder = Path(folder)
    with np.load(folder / "checkpoint" / "state.npz", allow_pickle=False) as arrays:
        out = {k: arrays[k] for k in arrays.files}
    registration = json.loads((folder / "registration.json").read_text())
    dt = registration["definition"]["ionic"]["execution"]["dt"]
    rows = [
        json.loads((folder / "observations" / f"tick-{round(t / dt):07d}.json").read_text())
        for t in m.CLUSTERS[world]["summaries"]
    ]
    out["summary_voltage_V"] = np.array([r["final_voltage_V"] for r in rows])
    out["summary_channel_fmol"] = np.array([r["channel_transferred_fmol"] for r in rows])
    out["summary_er_voltage_V"] = np.array([r["calcium"]["er_voltage_V"] for r in rows])
    out["summary_cytosol_fmol"] = np.array([r["calcium"]["cytosol_amounts_fmol"] for r in rows])
    out["summary_species"] = np.array(rows[0]["calcium"]["species_ids"])
    return out


def entries_of_assembly(world, arrays, k):
    """{entry: array [time, entity]} of world ID `k` of a cluster's run, at its compared times."""
    o, w = order(world), m.WORLDS[child_of(world)]
    out = entries(world, lambda name: arrays["ionic_" + name][k][None])
    nc, nm = len(o["cells"]), len(o["membranes"])
    out["voltage"] = arrays["summary_voltage_V"][:, k, :nm]
    out["store_voltage"] = arrays["summary_er_voltage_V"][:, k, :nc]
    out["channel_K_summary"] = arrays["summary_channel_fmol"][:, k, : len(o["channels"])]
    names = [str(x) for x in arrays["summary_species"]]
    for x in o["species"]:
        amounts = arrays["summary_cytosol_fmol"][:, k, names.index(x), :nc]
        initial = np.array([w["cells"][c]["amounts"][x] for c in o["cells"]])
        out[f"cyt_{x}_summary"] = amounts - initial
    return out


def run_folder(roots, world, step, seed=None):
    return one.run_folder(roots, world, step, seed)


def families(world):
    """[(seed index, world ID)] of a cluster's judged families, or [None]."""
    if world not in m.CLUSTERS:
        return [None]
    return [(s, k) for s in range(m.SEEDS) for k in range(m.IDS)]


def load(root, world, family=None, steps=STEPS):
    if family is None:
        return [entries_of_windows(world, windows(run_folder(root, world, s))) for s in steps]
    seed, k = family
    return [
        entries_of_assembly(world, assembly(run_folder(root, world, s, seed), world), k)
        for s in steps
    ]


def steps_of(world):
    """(the legacy run's finest step count, the candidate's finest, the retry's)."""
    w = m.WORLDS[child_of(world)]
    last = w["candidate"][-1]
    return (
        rules.grid_steps(w["end"], w["legacy"] / 4),
        rules.grid_steps(w["end"], last),
        rules.grid_steps(w["end"], last / 2),
    )
