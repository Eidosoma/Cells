"""The reference-side files of the rehearsal, formed from the legacy runs alone.

    reference.py classes SCIENCE F                 legacy_rehearsal.json: the legacy side's classes
                                                   and its pins
    reference.py identities SCIENCE                READOUTS section 5's balances and energy identity
                                                   of every legacy run at h/4, against their bounds
                                                   (a check of the formulas)
    reference.py paths POOLS SCIENCE F             reference_paths_rehearsal.json, and the pools
                                                   against the coupled runs
    reference.py margins SCIENCE PLANTS POOLS F    margins_rehearsal.json
    reference.py pool-runs POOLS F                 the pool runs' entry of the plants manifest

SCIENCE is the capture's output folder (`runs/`, `MANIFEST.json`), or several separated by `:`,
PLANTS the plant driver's, POOLS the pool runs' npz files. Standard library and numpy; no engine, no
builder's and no judge's code.
"""

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import legacy_arrays as la  # noqa: E402
import make_inputs  # noqa: E402
import rules  # noqa: E402

HERE = Path(__file__).resolve().parent
SNAPSHOT = Path("/mnt/workspaces/Cells/legacy-captures-20261125/snapshot-76a498ae")
REVISION = "76a498ae118c6d706cee0b5a6d278b1f5dae7a90"


def inputs():
    return json.loads((HERE / "inputs_rehearsal.json").read_text())


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=1, allow_nan=False) + "\n")


def sha256(path):
    import hashlib

    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


# ------------------------------------------------------------------ classes


def world_classes(world, science, data):
    """The legacy side's own classes of one world, in legacy_part1.json's layout."""
    w = data["worlds"][world]
    scales = w["scales"]
    steps, _ = la.steps_of(world)
    entry_names, rows = [], {}
    for family in la.families(world):
        diffs = la.differences(la.load(science, world, family))
        for e, (d2, d1, _, largest) in diffs.items():
            rows.setdefault(e, []).append((d2, d1, largest))
    zero, out = [], {}
    for e, values in rows.items():
        key = rules.base(e, scales)
        if scales[key] == 0.0:
            zero.append(e)
            continue
        theta = rules.legacy_threshold(steps, scales[key])
        if len(values) == 1:
            d2, d1, largest = values[0]
            out[e] = dict(
                **{"class": rules.order_class(d2, d1, theta)},
                observed_order=None if d1 == 0 or d2 == 0 else la.sig(math.log2(d2 / d1)),
                d2=la.sig(d2),
                d1=la.sig(d1),
                threshold=la.sig(theta),
                largest=la.sig(largest),
            )
        else:
            classes = {}
            for d2, d1, _ in values:
                c = rules.order_class(d2, d1, theta)
                classes[c] = classes.get(c, 0) + 1
            out[e] = dict(
                classes=classes,
                largest_d2=la.sig(max(v[0] for v in values)),
                largest_d1=la.sig(max(v[1] for v in values)),
                threshold=la.sig(theta),
                largest=la.sig(max(v[2] for v in values)),
                smallest_of_the_families_largest=la.sig(min(v[2] for v in values)),
            )
        entry_names.append(e)
    block = dict(
        captured_steps_s=[make_inputs.WORLDS[world]["legacy"] / k for k in (1, 2, 4)],
        captured_step_counts=[
            rules.grid_steps(
                make_inputs.WORLDS[world]["end"], make_inputs.WORLDS[world]["legacy"] / k
            )
            for k in (1, 2, 4)
        ],
    )
    if make_inputs.WORLDS[world]["consumer"] in ("cell", "base"):
        block["families"] = f"{make_inputs.SEEDS} seeds x world IDs 0 to {make_inputs.IDS - 1}"
    block["entries"] = out
    if zero:
        block["zero_entries"] = zero
    return block


def capture_block(science):
    """A capture set's pins, in legacy_part1.json's layout."""
    science = Path(science)
    manifest = json.loads((science / "MANIFEST.json").read_text())
    origin, started = Path(manifest["origin"]["path"]), manifest["run"]
    snapshot = json.loads((SNAPSHOT / "SNAPSHOT.json").read_text())
    if manifest["snapshot"]["manifest_sha256"] != sha256(SNAPSHOT / "SNAPSHOT.json"):
        raise SystemExit("the runs are not of the snapshot")
    return dict(
        root=str(science.parent),
        science=science.name,
        science_manifest_sha256=sha256(science / "MANIFEST.json"),
        origin=origin.name,
        origin_manifest_sha256=sha256(origin / "manifest.json"),
        snapshot="snapshot-76a498ae",
        snapshot_manifest_sha256=sha256(SNAPSHOT / "SNAPSHOT.json"),
        snapshot_revision=snapshot["git_revision"],
        cpu_model=started["cpu_model"],
        python=started["python"].split()[0],
        jax=_environment(science, "jax"),
        jaxlib=_environment(science, "jaxlib"),
        numpy=np.__version__,
    )


def classes(science, target):
    """`science` is one capture folder, or several separated by `:`: the first is the block
    `captures`, and `science-<name>` is `captures_<name>`."""
    data = inputs()
    sets = [Path(p) for p in str(science).split(":")]
    blocks = {}
    for i, folder in enumerate(sets):
        name = "captures" if i == 0 else "captures_" + folder.name.removeprefix("science-")
        blocks[name] = capture_block(folder)
    worlds = {w: world_classes(w, science, data) for w in data["worlds"]}
    record = dict(
        schema="ensemble-reexpression legacy side, version 1",
        part=1,
        **blocks,
        threshold_rule="10 x 8 x 2^-52 x (S + 1) x s, S the steps of the finest captured run, s "
        "inputs_rehearsal.json's scale",
        worlds=worlds,
    )
    write_json(target, record)
    counts = {}
    for b in worlds.values():
        for v in b["entries"].values():
            for c, n in ({v["class"]: 1} if "class" in v else v["classes"]).items():
                counts[c] = counts.get(c, 0) + n
    print("classes over all entries:", counts)
    for w, b in worlds.items():
        odd = {
            e: (v.get("class") or v["classes"])
            for e, v in b["entries"].items()
            if (v.get("class") not in (None, "unresolved", "resolved"))
            or ("classes" in v and set(v["classes"]) - {"unresolved", "resolved"})
        }
        if odd:
            print(" ", w, odd)


def _environment(science, key):
    for job in sorted((Path(science) / "runs").iterdir()):
        run = job / "run.json"
        if run.exists():
            env = json.loads(run.read_text())["environment"]
            if key == "jax":
                return env["jax"]
    import importlib.metadata

    return importlib.metadata.version(key)


# ------------------------------------------------------------------ identities, READOUTS section 5


def drive(block, mid):
    p = block.membranes[mid]["pump"]
    m = p["metabolism"]
    return m["delta_g0_J_per_mol"] + block.RT * (
        math.log(m["adp_mM"]) + math.log(m["pi_mM"]) - math.log(m["atp_mM"]) - math.log(1000.0)
    )


def balances(world, entries):
    """{name: max |value| / bound} of the balances, over every entity and compared time, for a
    run at the captured h/4 (READOUTS section 5)."""
    data = inputs()["worlds"][world]
    block = rules.Block(data["ionic"])
    o = la.order(world)
    scales = data["scales"]
    steps = rules.grid_steps(block.end, make_inputs.WORLDS[world]["legacy"] / 4)
    nu = {"Na": -3.0, "K": 2.0, "Cl": 0.0}
    cells, regions = o["cells"], o["regions"]
    members = {mid: (m["inside"], m["outside"]) for mid, m in block.membranes.items()}
    out = {}
    get = entries.get
    t = range(len(get("n_cell_Na")))

    def leak(x):
        return get(f"leak_{x}", np.zeros((len(t), len(members))))

    for x in block.x:
        n_cell, n_out = get(f"n_cell_{x}"), get(f"n_out_{x}")
        worst = 0.0
        for j, c in enumerate(cells):
            mine = [i for i, (mid, (a, _)) in enumerate(members.items()) if a == c]
            total = 0.0
            for i in mine:
                total = total + leak(x)[:, i]
                mid = list(members)[i]
                for k, cid in enumerate(o["channels"]):
                    if block.channels[cid]["membrane_id"] == mid and x == "K":
                        total = total + get("channel_K")[:, k]
                if "pump" in entries:
                    total = total + nu[x] * get("pump")[:, i]
            for k, j_id in enumerate(o["junctions"]):
                e = block.junctions[j_id]
                sign = (-1.0 if e["from_cell"] == c else 0.0) + (1.0 if e["to_cell"] == c else 0.0)
                if sign:
                    total = total + sign * get(f"junction_{x}")[:, k]
            worst = max(worst, float(np.max(np.abs(n_cell[:, j] - total))))
        bound = rules.e_round(steps, scales[f"n_cell_{x}"])
        out[f"cell balance {x}"] = worst / bound if bound else worst
        worst = 0.0
        for j, r in enumerate(regions):
            total = 0.0
            for i, (mid, (_, outside)) in enumerate(members.items()):
                if outside != r:
                    continue
                total = total - leak(x)[:, i]
                for k, cid in enumerate(o["channels"]):
                    if block.channels[cid]["membrane_id"] == mid and x == "K":
                        total = total - get("channel_K")[:, k]
                if "pump" in entries:
                    total = total - nu[x] * get("pump")[:, i]
            for k, f_id in enumerate(o["faces"]):
                e = block.faces[f_id]
                sign = (-1.0 if e["sender"] == r else 0.0) + (1.0 if e["receiver"] == r else 0.0)
                if sign:
                    total = total + sign * get(f"face_{x}")[:, k]
            worst = max(worst, float(np.max(np.abs(n_out[:, j] - total))))
        scale = scales[f"n_out_{x}"]
        out[f"region balance {x}"] = worst / rules.e_round(steps, scale) if scale else worst
        closed = np.abs(n_cell.sum(1) + n_out.sum(1))
        bound = rules.e_round(
            steps, len(cells) * scales[f"n_cell_{x}"] + len(regions) * scales[f"n_out_{x}"]
        )
        out[f"closed world {x}"] = float(np.max(closed)) / bound if bound else float(np.max(closed))
    return out


def identities(science):
    worst = {}
    for world in inputs()["worlds"]:
        seed = 0 if make_inputs.WORLDS[world]["consumer"] in ("cell", "base") else None
        if not la.run_folder(science, world, "h4", seed).exists():
            continue
        if make_inputs.WORLDS[world]["consumer"] in ("cell", "base"):
            families = [(s, k) for s in range(make_inputs.SEEDS) for k in range(make_inputs.IDS)]
        else:
            families = [None]
        for family in families:
            entries = la.load(science, world, family, steps=("h4",))[0]
            row = balances(world, entries)
            energy = energy_identity(world, entries)
            row.update(energy)
            for k, v in row.items():
                worst.setdefault(k, (0.0, None))
                if v > worst[k][0]:
                    worst[k] = (v, f"{world} {family}")
    for k, (v, w) in sorted(worst.items()):
        print(f"{k}: largest |value| / bound {v:.2e} ({w})")
    return worst


def energy_identity(world, entries):
    """The energy identity and the capacitor, READOUTS section 5, over the compared times."""
    data = inputs()["worlds"][world]
    block = rules.Block(data["ionic"])
    o = la.order(world)
    scales = data["scales"]
    steps = rules.grid_steps(block.end, make_inputs.WORLDS[world]["legacy"] / 4)
    cells, regions = o["cells"], o["regions"]
    get = entries.get
    rt = block.RT
    chemical = 0.0
    for group, names in (("n_cell", cells), ("n_out", regions)):
        for j, name in enumerate(names):
            comp = block.cells.get(name) or block.outside[name]
            for x in block.x:
                d = get(f"{group}_{x}")[:, j]
                n0, vol = comp["initial_amount_fmol"][x], comp["volume_pL"]
                chemical = chemical + 1e-3 * rt * (
                    d * (math.log(n0 / vol) - 1) + (n0 + d) * np.log1p(d / n0)
                )
    electric = 0.0
    for m in block.membranes.values():
        j = cells.index(m["inside"])
        dn = sum(block.z[x] * get(f"n_cell_{x}")[:, j] for x in block.x)
        dv = rules.F * rules.FMOL / m["capacitance_F"] * dn
        v0 = block.cells[m["inside"]]["initial_voltage_V"]
        electric = electric + 0.5e12 * m["capacitance_F"] * dv * (2 * v0 + dv)
    heat = 0.0
    for name in ("heat_membrane", "heat_junction", "heat_face"):
        if name in entries:
            heat = heat + get(name).sum(1)
    work = 0.0
    if "pump" in entries:
        for i, mid in enumerate(block.membranes):
            work = work - 1e-3 * drive(block, mid) * get("pump")[:, i]
    energy = chemical + electric + heat - work
    out = {}
    worst = float(np.max(np.abs(energy)))
    out["energy identity"] = worst / (
        rules.e_round(steps, scales["energy_identity"]) + rules.CLOSE * scales["energy_identity"]
    )
    return out


# ------------------------------------------------------------------ the pools


def pool_set(path):
    """{(world, cell, seed): (paths by world ID, final arrays)} of a pool run's npz."""
    d = np.load(path)
    keys = sorted({k.rsplit("/path/", 1)[0] for k in d.files if "/path/" in k})
    out = {}
    for key in keys:
        world, cell, seed = key.split("/")
        paths = {}
        for k in d.files:
            if k.startswith(key + "/path/"):
                paths[int(k.rsplit("/", 1)[1])] = d[k]
        finals = {k.rsplit("/", 1)[1]: d[k] for k in d.files if k.startswith(key + "/final/")}
        out[(world, cell, int(seed[1:]))] = (paths, finals)
    return out


def coupled_pool(science, world, step, seed):
    folder = la.run_folder(science, world, step, seed)
    with np.load(folder / "checkpoint" / "state.npz", allow_pickle=False) as arrays:
        return {k[len("pool_") :]: arrays[k] for k in arrays.files if k.startswith("pool_")}


def exposure_check(paths, end, exposure, segments):
    """(largest |sum of the intervals of availability 1 less the captured exposure|, its bound)."""
    worst = 0.0
    for k, p in paths.items():
        t, a, total = 0.0, 1.0, 0.0
        for when, value in p:
            total += a * (when - t)
            t, a = when, value
        total += a * (end - t)
        bound = 2 * rules.EPS * end * (2 + int(segments[k]))
        worst = max(worst, abs(total - float(exposure[k])) / bound)
    return worst


def paths(pools_npz, science, target):
    data = inputs()
    pools = pool_set(pools_npz)
    worlds, events, ok = {}, 0, True
    for (world, cell, seed), (by_world, finals) in sorted(pools.items()):
        w = data["worlds"][world]
        target_block = worlds.setdefault(world, {}).setdefault(f"s{seed}", {})
        target_block[cell] = {
            str(k): [[float(t), int(a)] for t, a in by_world[k]] for k in sorted(by_world)
        }
        events += sum(len(v) for v in by_world.values())
        index = list(w["pools"]).index(cell)
        # The pool alone against the coupled runs, every array, at h, h/2 and h/4.
        for step in la.STEPS:
            coupled = coupled_pool(science, world, step, seed)
            for name, value in finals.items():
                c = coupled[name]
                c = c if w["consumer"] == "cell" else c[:, index]
                if c.dtype != value.dtype or c.tobytes() != value.tobytes():
                    ok = False
                    print("DIFFERS", world, cell, seed, step, name)
        # The exposure (class R) against the captured one at h/4.
        folder = la.run_folder(science, world, "h4", seed)
        with np.load(folder / "checkpoint" / "state.npz", allow_pickle=False) as arrays:
            exposure, segments = arrays["availability_exposure_s"], arrays["segments"]
        exposure = exposure if w["consumer"] == "cell" else exposure[:, index]
        ratio = exposure_check(by_world, w["ionic"]["end_s"], exposure, segments)
        print(
            f"{world} {cell} s{seed}: {sum(len(v) for v in by_world.values())} events, "
            f"exposure ratio {ratio:.2f} of its bound"
        )
        ok &= ratio <= 1.0
    record = dict(
        schema="ensemble-reexpression reference paths, version 1",
        made_by="the frozen snapshot's own pool code, run alone on the invented pool definitions",
        entry="one [time_s, availability after the event] per committed event, in order; "
        "availability 1 before the first",
        events=events,
        worlds=worlds,
    )
    write_json(target, record)
    print(f"{events} events; pool arrays equal to the coupled runs' at every step: {ok}")
    return 0 if ok else 1


# ------------------------------------------------------------------ margins, PLANTS.md sections 1
# and 8


MECHANISMS = {
    "leak permeability": (("leak_Na", "leak_K", "leak_Cl"), "leak"),
    "channel permeability": (("channel_K", "channel_K_summary"), "channel"),
    "channel kinetics": (("gate_m", "gate_h"), "kinetics"),
    "Na/K pump": (("pump",), "pump"),
    "junction permeability": (("junction_Na", "junction_K", "junction_Cl"), "junction"),
    "junction gate": (("junction_gate",), "jgate"),
    "faces": (("face_Na", "face_K", "face_Cl"), "face"),
}
CLOSURE = "electrical closure"


def ratio4(x):
    return la.sig(x, 4)


class Margins:
    """The margins of one world, from its control and its planted runs at h/4."""

    def __init__(self, world, science, plants_root, seed=0):
        self.world, self.science, self.root, self.seed = (
            world,
            Path(science),
            Path(plants_root),
            seed,
        )
        self.data = inputs()["worlds"][world]
        self.scales, self.refs, self.closure = (
            self.data["scales"],
            self.data["amount_refs"],
            self.data["closure_terms_V"],
        )
        self.assembly = self.data["consumer"] in ("cell", "base")
        self.S_l, self.S_c = la.steps_of(world)
        self.families = [(seed, k) for k in range(make_inputs.IDS)] if self.assembly else [None]
        self.honest = {f: la.differences(la.load(self.science, world, f)) for f in self.families}
        self.control = {f: self._run(f"control {world} h4", f) for f in self.families}

    def _run(self, name, family):
        folder = self.root / name / "run"
        if family is None:
            return la.entries_of_windows(self.world, la.windows(folder))
        return la.entries_of_assembly(self.world, la.assembly(folder, self.world), family[1])

    def band(self, entry, family):
        s, ref = self._scale(entry), self.refs.get(rules.base(entry, self.scales), 0.0)
        closure = rules.e_close(entry, self.scales, self.closure)
        _, _, u_l, _ = self.honest[family][entry]
        return (
            2 * u_l
            + rules.e_round(self.S_c, s)
            + rules.e_round(self.S_l, s)
            + closure
            + (rules.e_store(self.S_c, ref) if self._reads_amounts(entry) else 0.0)
        )

    def _scale(self, entry):
        return self.scales[rules.base(entry, self.scales)]

    def _reads_amounts(self, entry):
        return rules.base(entry, self.scales) in self.refs

    def distance(self, plant_run, entry, family):
        planted = plant_run[family][entry]
        return float(np.max(np.abs(planted - self.control[family][entry]), initial=0.0))

    def largest(self, entry, family):
        return float(np.max(np.abs(self.control[family][entry]), initial=0.0))

    def planted(self, name):
        return {f: self._run(name, f) for f in self.families}

    def measure(self, run, entry):
        """(ratio, margin, largest, band) over the families: the smallest of each."""
        rows = []
        for f in self.families:
            largest = self.largest(entry, f)
            distance, band = self.distance(run, entry, f), self.band(entry, f)
            rows.append((distance / largest if largest else 0.0, distance / band, largest, band))
        smallest = min(rows, key=lambda r: r[1])
        return (
            min(r[0] for r in rows),
            min(r[1] for r in rows),
            smallest[2],
            smallest[3],
        )


POWER = ("leak", "channel", "kinetics", "pump", "junction", "jgate", "face", "faceK")
NAMED = {  # PLANTS.md section 4: the named entries of each structural plant (and its world ID).
    "ST1 pump direction": (("n_cell_Na", "n_cell_K", "voltage"), None, "inv_cluster"),
    "ST2 leak valence of Cl": (("leak_Cl",), None, "inv_cluster"),
    "ST3 inactivation gate left out": (("channel_K",), None, "inv_cluster"),
    "ST4 junction voltage sign": (
        ("junction_Na", "junction_K", "junction_Cl"),
        None,
        "inv_cluster",
    ),
    "ST5 Na and K face diffusivities exchanged": (("face_Na", "face_K"), None, "inv_cluster"),
    "ST8 pump released on one membrane": (("pump",), None, "inv_release"),
    "ST9 the schedule is not applied": (
        ("junction_Na", "junction_K", "junction_Cl"),
        None,
        "inv_junctions",
    ),
    "ST6 availability on the other cell's channel": (("channel_K",), 2, "inv_base"),
    "ST10 availability held over the step, base": (("channel_K",), 2, "inv_base"),
    "ST7 availability inverted": (("channel_K",), 1, "inv_cell"),
    "ST10 availability held over the step, cell": (("channel_K",), 1, "inv_cell"),
}
ST_RENAMED = {  # Part 1's names in margins.json for the runs that differ only by their world.
    "ST10 availability held over the step, base": "ST10 availability held over the step",
    "ST10 availability held over the step, cell": "ST10 availability held over the step",
}


def entry_block(m, entry, runs, home_plant):
    """One entry of `margins.json`'s layout: its ratio and margin, and every home plant's."""
    measured = {p: m.measure(run, entry) for p, run in runs.items()}
    best = max(measured, key=lambda p: measured[p][0])
    out = dict(home=home_plant is not None)
    use = home_plant if home_plant is not None else best
    ratio, margin, largest, band = measured[use]
    out.update(
        ratio=ratio4(ratio),
        ratio_from=use,
        margin=ratio4(margin),
        band_at_U_c_0=ratio4(band),
        largest=ratio4(largest),
        home_plants=(
            {home_plant: dict(ratio=ratio4(ratio), margin=ratio4(margin))} if home_plant else {}
        ),
    )
    if home_plant is not None and best != home_plant:
        r, g, _, _ = measured[best]
        out.update(best_ratio=ratio4(r), best_from=best, best_margin=ratio4(g))
    return out


def world_margins(world, science, plants, refused):
    m = Margins(world, science, plants)
    present = [e for e in m.control[m.families[0]] if m.scales[rules.base(e, m.scales)] != 0.0]
    runs = {}
    for p in POWER:
        folder = Path(plants) / f"PW-{p} {world}"
        if folder.exists():
            runs[p] = m.planted(folder.name)
    homes = {}
    for mechanism, (names, plant) in MECHANISMS.items():
        if plant not in runs:
            continue
        for e in names:
            if e in present:
                homes[e] = (mechanism, plant)
    if "voltage" in present:  # Its plant is the one that moves it most (PLANTS.md section 2).
        measured = {p: m.measure(run, "voltage")[0] for p, run in runs.items()}
        homes["voltage"] = (CLOSURE, max(measured, key=measured.get))
    if "phi_out" in present and "faceK" in runs:
        homes["phi_out"] = (CLOSURE, "faceK")
    entries = {e: entry_block(m, e, runs, homes[e][1] if e in homes else None) for e in present}
    mechanisms = {}
    for e, (mechanism, plant) in homes.items():
        mechanisms.setdefault(mechanism, {})[e] = {
            plant: dict(
                ratio=entries[e]["home_plants"][plant]["ratio"],
                margin=entries[e]["home_plants"][plant]["margin"],
            )
        }
    structural = {}
    for name, (named, k, where) in NAMED.items():
        if where != world:
            continue
        run_name = name
        if name in refused:
            run_name = f"{name}, own ledgers off"
        run = m.planted(run_name)
        block = dict(named=list(named))
        if k is not None:
            block["world"] = k
        block["run"] = run_name
        family = m.families[0] if k is None else (m.seed, k)
        for e in named:
            d, b = m.distance(run, e, family), m.band(e, family)
            block[e] = dict(distance=ratio4(d), margin=ratio4(d / b))
        if k is not None:
            block["recorded_channel_K_relative_per_world"] = [
                ratio4(m.distance(run, "channel_K", f) / m.largest("channel_K", f))
                for f in m.families
            ]
        structural[ST_RENAMED.get(name, name)] = block
    return dict(S_c=m.S_c, S_l=m.S_l, entries=entries, structural=structural, mechanisms=mechanisms)


def control_check(science, plants):
    """The controls of the plant driver equal the honest runs at h/4, bit for bit."""
    rows, ok = [], True
    for world in inputs()["worlds"]:
        consumer = make_inputs.WORLDS[world]["consumer"]
        honest = la.run_folder(science, world, "h4", 0 if consumer in ("cell", "base") else None)
        planted = Path(plants) / f"control {world} h4" / "run"
        a, b = all_arrays(honest), all_arrays(planted)
        same = a.keys() == b.keys() and all(
            x.dtype == b[k].dtype and x.shape == b[k].shape and x.tobytes() == b[k].tobytes()
            for k, x in a.items()
        )
        ok &= same
        rows.append((world, len(a), same))
    for world, n, same in rows:
        print(f"control {world} h4: {n} arrays {'equal bit for bit' if same else 'DIFFER'}")
    return ok


def all_arrays(folder):
    out = {}
    for path in sorted(Path(folder).rglob("*.npz"), key=la.natural):
        with np.load(path, allow_pickle=False) as arrays:
            for k in arrays.files:
                out[f"{path.relative_to(folder)}:{k}"] = arrays[k]
    return out


def pool_plants(pools_dir):
    """PW-pool: the snapshot's own pool with one rate x 1.01 against the pool alone."""
    base = pool_set(Path(pools_dir) / "pools.npz")
    out = {
        "what": "PW-pool: the snapshot's own pool alone, on the invented definitions with one "
        "rate x 1.01. Class E has no margin: the distance is whether anything changes"
    }
    from pool_paths import RATES

    for rate in RATES:
        changed = pool_set(Path(pools_dir) / f"pools-{rate}.npz")
        for (world, cell, seed), (_, finals) in sorted(base.items()):
            if seed:
                continue
            _, other = changed[(world, cell, seed)]
            arrays = [k for k in finals if finals[k].tobytes() != other[k].tobytes()]
            out[f"{world} {cell} {rate}"] = dict(
                arrays_changed=arrays,
                worlds_whose_event_count_differs=int(
                    np.sum(finals["event_count"] != other["event_count"])
                ),
                worlds_whose_last_event_time_differs=int(
                    np.sum(finals["last_event_time_s"] != other["last_event_time_s"])
                ),
                worlds=int(len(finals["event_count"])),
            )
    return out


def pool_runs(pools_dir, target):
    """The pool runs' provenance, as plants_manifest.json's `pool_plants` holds it."""
    folder, script = Path(pools_dir).resolve(), HERE / "pool_paths.py"
    files = sorted(folder.glob("*.npz"))
    environment = {
        "PYTHONPATH": f"{SNAPSHOT}/src:{SNAPSHOT}",
        "JAX_PLATFORMS": "cpu",
        "JAX_ENABLE_X64": "1",
        "JAX_ENABLE_COMPILATION_CACHE": "false",
        "CUDA_VISIBLE_DEVICES": "",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
    }
    write_json(
        target,
        [
            dict(
                name="pool_plant",
                command=[
                    "/mnt/workspaces/Cells/venv-cpu/bin/python",
                    "-B",
                    str(script.relative_to(HERE.parents[2])),
                    "all",
                    str(folder),
                ],
                cpu="6,7,22,23, niced, through run_detached.sh",
                environment=environment,
                script_sha256=sha256(script),
                outputs_sha256={f.name: sha256(f) for f in files},
                output_folder=str(folder),
                runs=f"{len(files)} (the invented pools as declared, and each with one of the "
                "four rates x 1.01)",
            )
        ],
    )


def margins(science, plants, pools_dir, target):
    plants = Path(plants)
    refused = {}
    for folder in plants.iterdir():
        record = folder / "plant.json"
        if record.exists():
            r = json.loads(record.read_text())
            if r["outcome"].startswith("refused") and r["plant"] in ("ST1", "ST4"):
                refused[r["name"]] = r["outcome"]
    if not control_check(science, plants):
        raise SystemExit("a control departs from its honest run")
    worlds = {}
    for world in inputs()["worlds"]:
        worlds[world] = world_margins(world, science, plants, refused)
        b = worlds[world]
        low = min(v["margin"] for v in b["entries"].values())
        home = min(v["margin"] for v in b["entries"].values() if v["home"])
        print(f"{world}: smallest margin of any entry {low:.3g}, of any home {home:.3g}")
    write_json(
        target,
        dict(
            schema="ensemble-reexpression margins, version 1",
            part=1,
            date="2026-11-25",
            bands="CRITERIA.md section 4.3 with U_c = 0 (the legacy side's own U_l, e_round, "
            "e_close, phi_out's own e_close, and e_store of the candidate's S_c)",
            rule="distance: the largest difference between a planted run and the honest control of "
            "the frozen snapshot at the same captured step, over the entry's entities and compared "
            "times. ratio: distance over the largest magnitude of the readout in the control "
            "(assembly: the smallest over the judged worlds of seed 0). margin: distance over the "
            "band at U_c = 0.",
            worlds=worlds,
            pool_plants=pool_plants(pools_dir),
            refused=refused,
        ),
    )


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "classes":
        classes(*sys.argv[2:4])
    elif action == "identities":
        identities(sys.argv[2])
    elif action == "paths":
        raise SystemExit(paths(*sys.argv[2:5]))
    elif action == "pool-runs":
        pool_runs(*sys.argv[2:4])
    elif action == "margins":
        margins(*sys.argv[2:6])
    else:
        raise SystemExit(__doc__)
