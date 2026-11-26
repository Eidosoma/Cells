"""The reference-side files of Part 2's rehearsal, formed from the legacy runs alone.

    reference2.py classes SCIENCE F          legacy_rehearsal_part2.json: the legacy side's classes
                                             and its pins
    reference2.py identities SCIENCE         the sums, moieties, balances and capacitors of PART2.md
                                             sections 6.2 and 9 on every legacy run at h/4, against
                                             a rounding count (a check of this reader's signs)
    reference2.py paths POOLS SCIENCE F      reference_paths_rehearsal_part2.json, and the pools
                                             against the coupled runs
    reference2.py margins SCIENCE PLANTS F   margins_rehearsal_part2.json

SCIENCE is the capture's output folder (`runs/`, `MANIFEST.json`), PLANTS the plant driver's, POOLS
the pool runs' npz file. Standard library and numpy; no engine, no builder's and no judge's code.
"""

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "rehearsal"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import legacy_arrays2 as la  # noqa: E402
import make_inputs2 as m  # noqa: E402
import reference as first  # noqa: E402
import rules  # noqa: E402

HERE = Path(__file__).resolve().parent
write_json, ratio4 = first.write_json, first.ratio4


def inputs():
    return json.loads((HERE / "inputs_rehearsal_part2.json").read_text())


# ------------------------------------------------------------------ classes


def world_classes(world, science, data):
    """The legacy side's own classes of one world, in legacy_part2.json's layout."""
    scales = data["worlds"][world]["scales"]
    w = m.WORLDS[la.child_of(world)]
    steps, *_ = la.steps_of(world)
    rows, largest_of = {}, {}
    for family in la.families(world):
        diffs = la.differences(la.load(science, world, family))
        for e, (d2, d1, _, largest) in diffs.items():
            rows.setdefault(e, []).append((d2, d1, largest))
            largest_of[e] = max(largest_of.get(e, 0.0), largest)
    zero, out = [], {}
    for e, values in rows.items():
        if e not in scales:
            zero.append(e)
            if largest_of[e] != 0.0:
                raise SystemExit(f"{world} {e} has no scale and is not zero")
            continue
        theta = rules.legacy_threshold(steps, scales[e])
        if len(values) == 1:
            d2, d1, largest = values[0]
            out[e] = dict(
                **{"class": rules.order_class(d2, d1, theta)},
                observed_order=None if d1 == 0 or d2 == 0 else la.sig(math.log2(d2 / d1)),
                d2=la.sig(d2), d1=la.sig(d1), threshold=la.sig(theta), largest=la.sig(largest),
            )  # fmt: skip
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
    missing = set(scales) - set(out)
    if missing:
        raise SystemExit(f"{world}: no captured entry for {sorted(missing)}")
    block = dict(
        captured_steps_s=[w["legacy"] / k for k in (1, 2, 4)],
        captured_step_counts=[rules.grid_steps(w["end"], w["legacy"] / k) for k in (1, 2, 4)],
    )
    if world in m.CLUSTERS:
        block["families"] = f"{m.SEEDS} seeds x world IDs 0 to {m.IDS - 1}"
    block["entries"] = {e: out[e] for e in scales if e in out}
    block["zero_entries"] = sorted(zero)
    return block


def classes(science, target):
    data = inputs()
    worlds = {w: world_classes(w, science, data) for w in data["worlds"]}
    write_json(
        target,
        dict(
            schema="ensemble-reexpression legacy side, version 1",
            part=2,
            captures=first.capture_block(science),
            threshold_rule="10 x 8 x 2^-52 x (S + 1) x s, S the steps of the finest captured run, "
            "s inputs_rehearsal_part2.json's scale",
            worlds=worlds,
        ),
    )
    counts, odd = {}, []
    for w, b in worlds.items():
        mine = {}
        for e, v in b["entries"].items():
            for c, n in ({v["class"]: 1} if "class" in v else v["classes"]).items():
                counts[c] = counts.get(c, 0) + n
                mine[c] = mine.get(c, 0) + n
                fault = c == "resolved outside its window" or (
                    c == "mixed" and "class" in v and v["d1"] > v["threshold"]
                )
                if fault or c == "mixed":
                    odd.append((w, e, c, v))
        print(f"{w}: {mine}, zero {b['zero_entries']}")
    print("classes over all entries:", counts)
    for row in odd:
        print("  ", *row)


# ------------------------------------------------------------------ identities, PART2.md 6.2 and 9


def identities(science):
    worst = {}
    data = inputs()["worlds"]
    for world in data:
        for family in la.families(world):
            e = la.load(science, world, family, steps=("h4",))[0]
            for name, value in checks(world, e, data).items():
                if value > worst.get(name, (0.0,))[0]:
                    worst[name] = (value, f"{world} {family or ''}")
    for k, v in sorted(worst.items()):
        print(f"{k}: largest |difference| over its rounding count {v[0]:.2e} ({v[1]})")


def checks(world, e, data):
    """{identity: max |difference| / bound} on a run's entries. The bound is the rounding count of
    the entry's own scale at the legacy run's steps (READOUTS section 5's form)."""
    child = la.child_of(world)
    w, o = m.WORLDS[child], la.order(world)
    scales = data[world]["scales"]
    steps, *_ = la.steps_of(world)
    out = {}
    cells = range(len(o["cells"]))

    def put(name, value, scale):
        bound = rules.e_round(steps, scale)
        out[name] = max(out.get(name, 0.0), float(np.max(np.abs(value), initial=0.0)) / bound)

    def get(name):
        return e.get(name, 0.0)

    def col(name, j):
        v = e.get(name)
        return 0.0 if v is None else v[:, j]

    # One membrane a cell, in the cells' order; one K channel, one calcium channel a membrane.
    for j in cells:
        for x in o["species"]:
            total = col(f"leak_{x}", j)
            if x == "Na":
                total = total - 3 * col("pump", j) + 3 * col("exchanger", j)
            if x == "K":
                total = total + col("channel_K", j) + 2 * col("pump", j)
            if x == "Ca":
                total = total - col("ca_pump", j) - col("exchanger", j) + col("ca_channel", j)
            for k, g in enumerate(w["junctions"].values()):
                sign = (g["b"] == o["cells"][j]) * 1.0 - (g["a"] == o["cells"][j]) * 1.0
                total = total + sign * col(f"junction_{x}", k)
            if f"exchange_{x}" in e:
                put(f"exchange_{x}", e[f"exchange_{x}"][:, j] - total, scales[f"exchange_{x}"])
        # The cytosol's and the store's rows: what crossed, and what the reactions made.
        for c in o["chemical"]:
            for part, name in (("cytosol", f"cyt_{c}"), ("er", f"store_{c}")):
                total = 0.0
                if part == "cytosol" and c in o["species"]:
                    total = total + e[f"exchange_{c}"][:, j]
                sign = -1.0 if part == "cytosol" else 1.0
                if c == "Ca":
                    total = total + sign * (
                        col("store_leak_Ca", j) + col("store_pump", j) + col("store_release", j)
                    )
                if c == "K":
                    total = total + sign * col("store_leak_K", j)
                for r, (where, a, b) in m.reactions(w).items():
                    if where == part:
                        n = b.get(c, 0) - a.get(c, 0)
                        total = total + n * col(f"extent_{r}", j)
                value = e[name][:, j] - total
                if name in scales:
                    put("row balance " + part, value, scales[name])
                elif np.any(value):
                    out[f"{name} not zero"] = math.inf
        # The moieties.
        for part, name in (("cytosol", "cyt"), ("er", "store")):
            total = col(f"{name}_B", j) + col(f"{name}_CaB", j) + col(f"{name}_Ca2B", j)
            put("moiety B " + part, total, scales[f"{name}_B"])
        total = sum(
            col(f"{p}_Ca", j) + col(f"{p}_CaB", j) + 2 * col(f"{p}_Ca2B", j)
            for p in ("cyt", "store")
        )
        put("calcium's total", total - e["exchange_Ca"][:, j], scales["cyt_Ca"])
        if w["kind"] == "ip3":
            put("moiety IP3", col("cyt_IP3", j) + col("cyt_IP3_bound", j), scales["cyt_IP3"])
        # The regions and the closed world.
    for x in o["species"]:
        total = e[f"n_out_{x}"].sum(1) + e[f"exchange_{x}"].sum(1)
        put(f"closed world {x}", total, scales[f"n_out_{x}"] + scales[f"exchange_{x}"])
        for k, r in enumerate(o["regions"]):
            total = 0.0
            if r == "bath":
                for j in cells:
                    total = total - col(f"leak_{x}", j)
                    if x == "Na":
                        total = total + 3 * col("pump", j) - 3 * col("exchanger", j)
                    if x == "K":
                        total = total - col("channel_K", j) - 2 * col("pump", j)
                    if x == "Ca":
                        total = total + col("ca_pump", j) + col("exchanger", j)
                        total = total - col("ca_channel", j)
            for i, f in enumerate(w["faces"].values()):
                total = total + ((f["b"] == r) * 1.0 - (f["a"] == r) * 1.0) * col(f"face_{x}", i)
            put(f"region balance {x}", e[f"n_out_{x}"][:, k] - total, scales[f"n_out_{x}"])
    if world == child:  # The capacitors, at the potential times that are compared rows.
        times, pots = la.compared(w), list(w["potentials"])
        row = la.rows_at(np.array(times), [t for t in pots if np.any(np.abs(np.array(times) - t)
                                                                     <= 1e-12)])  # fmt: skip
        at = [i for i, t in enumerate(pots) if np.any(np.abs(np.array(times) - t) <= 1e-12)]
        for j, c in enumerate(o["cells"]):
            cell, s = w["cells"][c], w["stores"][c]
            moved = sum(m.SPECIES[x] * e[f"exchange_{x}"][row, j] for x in o["species"])
            v = cell["voltage"] + rules.F * rules.FMOL / cell["cap"] * moved
            put("capacitor", e["voltage"][at, j] - v, scales["voltage"])
            cap = rules.capacitance(s["area"], s["release"]["specific"])
            moved = sum(z * e[f"store_{x}"][row, j] for x, z in m.rows(w).items())
            v = rules.F * rules.FMOL / cap * moved
            put("store capacitor", e["store_voltage"][at, j] - v, scales["store_voltage"])
    return out


# ------------------------------------------------------------------ the pools


def coupled_pool(science, world, step, seed):
    folder = la.run_folder(science, world, step, seed)
    with np.load(folder / "checkpoint" / "state.npz", allow_pickle=False) as arrays:
        return {k[len("pool_") :]: arrays[k] for k in arrays.files if k.startswith("pool_")}


def paths(pools_npz, science, target):
    pools = first.pool_set(pools_npz)
    cells = list(next(iter(m.CLUSTERS.values()))["pools"])
    end = m.SHARED["end"]
    worlds, events, compared, ok = {}, 0, 0, True
    for (key, cell, seed), (by_world, finals) in sorted(pools.items()):
        block = worlds.setdefault(key, {}).setdefault(f"s{seed}", {})
        block[cell] = {
            str(k): [[float(t), int(a)] for t, a in by_world[k]] for k in sorted(by_world)
        }
        events += sum(len(v) for v in by_world.values())
        index = cells.index(cell)
        for world in m.CLUSTERS:  # Every cluster, at h, h/2 and h/4, holds the pools alone.
            for step in la.STEPS:
                coupled = coupled_pool(science, world, step, seed)
                for name, value in finals.items():
                    c = coupled[name][:, index]
                    compared += 1
                    if c.dtype != value.dtype or c.tobytes() != value.tobytes():
                        ok = False
                        print("DIFFERS", world, cell, seed, step, name)
            folder = la.run_folder(science, world, "h4", seed)
            with np.load(folder / "checkpoint" / "state.npz", allow_pickle=False) as arrays:
                exposure, segments = arrays["availability_exposure_s"], arrays["segments"]
            ratio = first.exposure_check(by_world, end, exposure[:, index], segments)
            ok &= ratio <= 1.0
            print(
                f"{world} {cell} s{seed}: {sum(len(v) for v in by_world.values())} events, "
                f"exposure ratio {ratio:.2f} of its bound"
            )
    write_json(
        target,
        dict(
            schema="ensemble-reexpression reference paths, version 1",
            made_by="the frozen snapshot's own pool code, run alone on the invented pools",
            entry="one [time_s, availability after the event] per committed event, in order; "
            "availability 1 before the first",
            read_by="the four clusters, which hold the same two pools (the profile's `paths`)",
            events=events,
            worlds=worlds,
        ),
    )
    print(f"{events} events; {compared} arrays against the coupled runs', all equal: {ok}")
    return 0 if ok else 1


# ------------------------------------------------------------------ margins, PART2.md section 7

# {mechanism: {home entry: its plants}} (sections 7.1 and 7.4). The voltage's plant is the one that
# moves it most.
HOMES = {
    "leak permeability": {f"leak_{x}": ("leak",) for x in ("Na", "K", "Cl")},
    "channel permeability": {"channel_K": ("channel",), "channel_K_summary": ("channel",)},
    "channel kinetics": {"gate_m": ("kinetics",), "gate_h": ("kinetics",)},
    "Na/K pump": {"pump": ("pump",)},
    "junction permeability": {f"junction_{x}": ("junction",) for x in ("Na", "K", "Cl")},
    "junction gate": {"junction_gate": ("jgate",)},
    "faces": {f"face_{x}": ("face",) for x in ("Na", "K", "Cl")},
    "electrical closure": {"voltage": None, "phi_out": ("faceK",)},
    "plasma Ca leak": {"leak_Ca": ("leakCa",)},
    "Ca junction route": {"junction_Ca": ("junctionCa",)},
    "Ca faces": {"face_Ca": ("faceCa",)},
    "store Ca leak": {"store_leak_Ca": ("storeleakCa",)},
    "store K leak": {"store_voltage": ("storeleakK",)},
    "store pump": {"store_pump": ("storepump",)},
    "release permeability": {"store_release": ("release",)},
    "release's calcium factor": {"store_release": ("activation", "inhibition")},
    "cytosolic buffer, first site": {"extent_bind_0_first": ("bind0a",)},
    "cytosolic buffer, second site": {"extent_bind_0_second": ("bind0b",)},
    "store buffer, first site": {"extent_bind_1_first": ("bind1a",)},
    "store buffer, second site": {"extent_bind_1_second": ("bind1b",)},
    "store capacitor": {"store_K": ("storecap",)},
    "plasma calcium pump": {"ca_pump": ("pmca",)},
    "exchanger": {"exchanger": ("ncx", "ncxkm")},
    "Ca channel permeability": {"ca_channel": ("cav",)},
    "Ca channel kinetics": {"ca_gate_m": ("cavkinetics",), "ca_gate_h": ("cavkinetics",)},
    "IP3 factor": {"store_release": ("ip3activation",)},
    "IP3 binding": {"extent_ip3_binding": ("ip3binding",)},
}
FIRST_HOMES = {
    "store K leak": ("store_leak_K", "storeleakK"),
    "store capacitor": ("store_voltage", "storecap"),
}
NOT_IN_CLUSTERS = "store capacitor"
WHY_NOT = (
    "a cluster's captures hold one end state and not the early rows where the capacitor shows; it "
    "is tested in the four children alone (the lead's ruling of 25 November, as registered)"
)
FIRST_HOME_WHY = "the first declared home, replaced as registered; not tested there"
NAMED = {  # PART2.md section 7.3: each structural plant's named entries, and its world.
    "SC1 release calcium factor left out": (("store_release", "store_Ca"), "inv_spatial"),
    "SC3b store voltage sign reversed in the calcium routes": (
        ("store_leak_Ca", "store_release"), "inv_spatial",
    ),
    "SC4 store pump direction reversed": (("store_pump", "store_Ca"), "inv_spatial"),
    "SC5 calcium valence one in the store leak and release": (
        ("store_leak_Ca", "store_release"), "inv_spatial",
    ),
    "SC6 first buffer second order in calcium": (("extent_bind_0_first", "cyt_Ca"), "inv_spatial"),
    "SC13 the store pump's standard free energy left at the mM one": (
        ("heat_store_pump",), "inv_spatial",
    ),
    "SC7 exchanger sodium terms squared": (("exchanger",), "inv_plasma"),
    "SC8 plasma calcium pump reversed": (("ca_pump", "cyt_Ca"), "inv_plasma"),
    "SC12 the plasma pump's standard free energy left at the mM one": (
        ("heat_ca_pump",), "inv_plasma",
    ),
    "SC9 calcium channel inactivation left out": (("ca_channel",), "inv_gated"),
    "SC10 calcium channel m not squared": (("ca_channel",), "inv_gated"),
    "SC2 IP3 factor left out": (("store_release",), "inv_ip3"),
}  # fmt: skip
CLUSTER_NAMED = {
    "SC11 availability on the calcium channel too, seed 1": ("ca_channel",),
    "SC14 availability on the other cell's channel": ("channel_K", "channel_K_summary"),
}


class Bands:
    """The bands of one world at U_c = 0 and at the widest that an unresolved triple gives."""

    def __init__(self, block, steps_l, steps_c, steps_retry, honest):
        self.block, self.S_l, self.S_c, self.S_r = block, steps_l, steps_c, steps_retry
        self.honest = honest  # {entry: (d2, d1, U_l, largest)}

    def closure(self, e):
        for part in ("closure_terms_V", "closure_terms"):
            if e in self.block[part]:
                return self.block[part][e]
        return self.block["closure_share"] * self.block["scales"][e]

    def rounding(self, e, steps):
        return rules.e_round(steps, self.block["scales"][e]) + rules.e_store(
            steps, self.block["amount_refs"].get(e, 0.0)
        )

    def band(self, e, steps, u_c=0.0):
        return (
            2 * (self.honest[e][2] + u_c)
            + self.rounding(e, steps)
            + rules.e_round(self.S_l, self.block["scales"][e])
            + self.closure(e)
        )

    def of(self, e):
        widest = 10 * self.rounding(e, self.S_r) / 3  # U_c = theta/3 (section 7.4).
        return (
            self.band(e, self.S_c),
            self.band(e, self.S_r),
            self.band(e, self.S_r, widest),
        )


def most(a, b=None):
    return float(np.max(np.abs(a if b is None else a - b), initial=0.0))


def entry_block(e, measured, home_plants, bands):
    """One entry of margins_part2.json's layout. `measured` is {plant: (distance, largest)}."""
    ratio = {p: (d / big if big else 0.0) for p, (d, big) in measured.items()}
    band, retry, widest = bands.of(e)
    best = max(ratio, key=ratio.get)
    homes = [p for p in home_plants if p in measured]
    use = max(homes, key=lambda p: ratio[p]) if homes else best
    distance, largest = measured[use]
    out = dict(
        home=bool(homes),
        ratio=ratio4(ratio[use]),
        ratio_from=use,
        margin=ratio4(distance / band),
        band_at_U_c_0=ratio4(band),
        largest=ratio4(largest),
        home_plants={
            p: dict(ratio=ratio4(ratio[p]), margin=ratio4(measured[p][0] / band))
            for p in sorted(homes)
        },
    )
    if homes and best not in homes:
        out.update(
            best_ratio=ratio4(ratio[best]), best_from=best,
            best_margin=ratio4(measured[best][0] / band),
        )  # fmt: skip
    out.update(
        band_at_retry_U_c_0=ratio4(retry),
        margin_at_retry=ratio4(distance / retry),
        margin_at_retry_widest_unresolved=ratio4(distance / widest),
    )
    return out


def homes_of(entries, runs, measure):
    """{entry: its home plants} and {mechanism: {entry: plants}} over the plants that ran."""
    by_entry, by_mechanism = {}, {}
    for mechanism, table in HOMES.items():
        for e, plants in table.items():
            if e not in entries:
                continue
            if plants is None:
                plants = (max(runs, key=lambda p: measure(p, e)),)
            have = [p for p in plants if p in runs]
            if have:
                by_entry.setdefault(e, []).extend(have)
                by_mechanism.setdefault(mechanism, {})[e] = have
    return by_entry, by_mechanism


def mechanisms_of(by_mechanism, entries):
    return {
        mechanism: {e: {p: entries[e]["home_plants"][p] for p in plants} for e, plants in v.items()}
        for mechanism, v in by_mechanism.items()
    }


class Child:
    """A child's honest runs, its control and its planted runs at the captured h."""

    def __init__(self, world, science, plants, data):
        self.world, self.root, self.block = world, Path(plants), data["worlds"][world]
        self.names = [e for e in self.block["scales"]]
        self.honest = la.differences(la.load(science, world))
        self.steps = la.steps_of(world)
        self.bands = Bands(self.block, *self.steps, self.honest)
        self.control = self.run(f"control {world} h")
        self.runs = {}
        for folder in sorted(self.root.glob(f"P-* {world}")):
            record = json.loads((folder / "plant.json").read_text())
            if record["outcome"] != "completed":
                raise SystemExit(f"{folder.name}: {record['outcome']}")
            self.runs[record["plant"]] = self.run(folder.name)

    def run(self, name):
        return la.entries_of_windows(self.world, la.windows(self.root / name / "run"))

    def measure(self, plant, e):
        return most(self.runs[plant][e], self.control[e]), most(self.control[e])

    def margins(self):
        def ratio(p, e):
            d, big = self.measure(p, e)
            return d / big if big else 0.0

        by_entry, by_mechanism = homes_of(self.names, self.runs, ratio)
        entries = {
            e: entry_block(
                e, {p: self.measure(p, e) for p in self.runs}, by_entry.get(e, ()), self.bands
            )
            for e in self.names
        }
        out = dict(S_c=self.steps[1], S_l=self.steps[0], S_c_retry=self.steps[2], entries=entries,
                   plants_run=sorted(f"P-{p}" for p in self.runs), structural=self.structural(),
                   mechanisms=mechanisms_of(by_mechanism, entries))  # fmt: skip
        out["first_homes_not_tested_there"] = {
            mechanism: self.first_home(e, p) for mechanism, (e, p) in FIRST_HOMES.items()
        }
        return out

    def first_home(self, e, plant):
        d, big = self.measure(plant, e)
        return dict(entry=e, plant=plant, ratio=ratio4(d / big if big else 0.0),
                    margin=ratio4(d / self.bands.of(e)[0]), why=FIRST_HOME_WHY)  # fmt: skip

    def structural(self):
        out = {}
        for name, (named, where) in NAMED.items():
            if where != self.world:
                continue
            record = json.loads((self.root / name / "plant.json").read_text())
            if record["outcome"] != "completed":
                raise SystemExit(f"{name}: {record['outcome']}")
            run = self.run(name)
            block = dict(named=list(named), run=name)
            for e in named:
                d = most(run[e], self.control[e])
                band, _, widest = self.bands.of(e)
                block[e] = dict(distance=ratio4(d), margin=ratio4(d / band),
                                margin_at_retry_widest_unresolved=ratio4(d / widest))  # fmt: skip
            out[name] = block
        return out

    # ------------------------------------------------------------ at the end, for a cluster

    def at_end(self, cluster):
        """The entries of the cluster, from the child's planted runs at its end (the potentials and
        the `_summary` entries at the summary times)."""
        w = m.WORLDS[self.world]
        times = np.array(la.compared(w))
        end = la.rows_at(times, [w["end"]])
        summaries = m.CLUSTERS[cluster]["summaries"]
        at = la.rows_at(times, summaries)
        pot = la.rows_at(np.array(w["potentials"]), summaries)

        def pick(run):
            out = {}
            for e in self.cluster_names(cluster):
                base = e.removesuffix("_summary")
                rows = at if base != e else pot if base in ("voltage", "store_voltage") else end
                out[e] = run[base][rows]
            return out

        return pick(self.control), {p: pick(v) for p, v in self.runs.items()}

    def cluster_names(self, cluster):
        return list(self.data_cluster["scales"])

    def cluster_margins(self, cluster, cluster_block):
        self.data_cluster = cluster_block
        control, runs = self.at_end(cluster)
        honest = {
            e: self.honest[e.removesuffix("_summary")] for e in cluster_block["scales"]
        }  # fmt: skip
        bands = Bands(cluster_block, *self.steps, honest)

        def measure(p, e):
            return most(runs[p][e], control[e]), most(control[e])

        def ratio(p, e):
            d, big = measure(p, e)
            return d / big if big else 0.0

        names = list(cluster_block["scales"])
        by_entry, by_mechanism = homes_of(names, runs, ratio)
        entries = {
            e: entry_block(e, {p: measure(p, e) for p in runs}, by_entry.get(e, ()), bands)
            for e in names
        }
        for v in entries.values():
            v["cluster_ratio"] = ratio4(v["ratio"] / 2)
            v["cluster_home_plants"] = {
                p: ratio4(q["ratio"] / 2) for p, q in v["home_plants"].items()
            }
        tested = {k: v for k, v in by_mechanism.items() if k != NOT_IN_CLUSTERS}
        e, plant = "store_K", "storecap"
        return dict(
            cluster_entries_at_the_end=entries,
            cluster_mechanisms_at_the_end=mechanisms_of(tested, entries),
            cluster_not_tested={
                NOT_IN_CLUSTERS: dict(
                    why=WHY_NOT, entry=e, plant=plant,
                    ratio_halved=entries[e]["cluster_home_plants"][plant],
                    margin_at_the_end=entries[e]["home_plants"][plant]["margin"],
                )
            },
        )  # fmt: skip


def cluster_structural(science, plants, data):
    """SC11 and SC14 on inv_cluster_gated, seed index 1, world by world."""
    world, out = "inv_cluster_gated", {}
    block = data["worlds"][world]
    for name, named in CLUSTER_NAMED.items():
        seed = 1
        control = la.assembly(Path(plants) / f"control {world} s{seed} h" / "run", world)
        planted = la.assembly(Path(plants) / name / "run", world)
        out[name] = dict(seed=seed)
        for e in named:
            rows = []
            for k in range(m.IDS):
                honest = la.differences(la.load(science, world, (seed, k)))
                bands = Bands(block, *la.steps_of(world), honest)
                a = la.entries_of_assembly(world, control, k)[e]
                b = la.entries_of_assembly(world, planted, k)[e]
                d, big = most(b, a), most(a)
                rows.append(dict(distance=ratio4(d), relative=ratio4(d / big),
                                 margin=ratio4(d / bands.of(e)[0])))  # fmt: skip
            out[name][e] = dict(per_world=rows)
    return out


def control_check(science, plants):
    """Every control of the plant driver equals its honest run at h, bit for bit."""
    ok, counts = True, {}
    for folder in sorted(Path(plants).glob("control *")):
        record = json.loads((folder / "plant.json").read_text())
        honest = la.run_folder(science, record["world"], "h", record["seed"])
        a, b = first.all_arrays(honest), first.all_arrays(folder / "run")
        same = a.keys() == b.keys() and all(
            x.dtype == b[k].dtype and x.shape == b[k].shape and x.tobytes() == b[k].tobytes()
            for k, x in a.items()
        )
        ok &= same
        counts[folder.name] = len(a)
        print(f"{folder.name}: {len(a)} arrays {'equal bit for bit' if same else 'DIFFER'}")
    return ok, counts


def margins(science, plants, target):
    plants, data = Path(plants), inputs()
    ok, counts = control_check(science, plants)
    if not ok:
        raise SystemExit("a control departs from its honest run")
    refused = {}
    for folder in sorted(plants.iterdir()):
        record = folder / "plant.json"
        if record.exists():
            r = json.loads(record.read_text())
            if r["outcome"] != "completed":
                refused[r["name"]] = r["outcome"]
    children_of = {v["child"]: k for k, v in m.CLUSTERS.items()}
    worlds = {}
    for world in m.WORLDS:
        child = Child(world, science, plants, data)
        worlds[world] = child.margins()
        if world in children_of:
            cluster = children_of[world]
            worlds[world] |= child.cluster_margins(cluster, data["worlds"][cluster])
        report(world, worlds[world])
    clusters = cluster_structural(science, plants, data)
    ip3 = m.RESTART[0]
    release = worlds[ip3]["entries"]["store_release"]["home_plants"]["release"]
    planted = Child(ip3, science, plants, data)
    sc14 = clusters["SC14 availability on the other cell's channel"]
    ep4 = {e: sc14[e]["per_world"][0] for e in CLUSTER_NAMED["SC14 availability on the other "
                                                              "cell's channel"]}  # fmt: skip
    engine = {}
    for variant in ("inv_EP3", "EP3"):
        engine[variant] = dict(
            run=next(r["name"] for r in data["runs"] if r["variant"] == variant),
            named=["store_release"],
            registered_distance_is=f"P-release {ip3}'s planted run against its control, at the "
            "captured h",
            store_release=dict(distance=ratio4(planted.measure("release", "store_release")[0]),
                               **release),
        )  # fmt: skip
    for variant in ("inv_EP4", "EP4"):
        engine[variant] = dict(
            run=next(r["name"] for r in data["runs"] if r["variant"] == variant),
            named=list(ep4),
            registered_distance_is="SC14's planted run against its control, seed index 1, world 0",
            **ep4,
        )
    write_json(
        target,
        dict(
            schema="ensemble-reexpression margins, version 1", part=2, date="2026-11-25",
            bands="CRITERIA.md section 4.3 with U_c = 0 (the legacy side's own U_l, e_round, "
            "e_close = closure_terms_V or closure_terms where an entry has one, else closure_share "
            "x s; and e_store of the candidate's S_c; PART2.md section 8. The retry's: S_c of half "
            "the family's last step)",
            rule="distance: the largest difference between a planted run and the honest control of "
            "the frozen snapshot at the same captured step, over the entry's entities and compared "
            "times. ratio: distance over the largest magnitude of the readout in the control. "
            "margin: distance over the band at U_c = 0.",
            worlds=worlds, refused=refused, cluster_gated_calcium=clusters,
            control_seed_1_arrays_equal=counts["control inv_cluster_gated s1 h"],
            engine_plants=engine,
        ),
    )  # fmt: skip
    print("refused:", refused)
    for name, v in clusters.items():
        print(name, {k: x["per_world"] for k, x in v.items() if k != "seed"})


def report(world, b):
    """What is tested: a mechanism is, when one of its plants has a margin of 10 at a home."""
    for label, entries, mechanisms in (
        ("", b["entries"], b["mechanisms"]),
        (" at the end", b.get("cluster_entries_at_the_end"),
         b.get("cluster_mechanisms_at_the_end")),
    ):  # fmt: skip
        if entries is None:
            continue
        half = 2 if label else 1
        worst = min(
            (p["margin"] / half, mech, e)
            for mech, v in mechanisms.items()
            for e, plants in v.items()
            for p in [max(plants.values(), key=lambda q: q["margin"])]
        )
        untested = [
            mech
            for mech, v in mechanisms.items()
            if all(p["margin"] / half < 10 for plants in v.values() for p in plants.values())
        ]
        homes = [
            (e, p, round(q["margin"] / half, 1))
            for e, v in entries.items()
            for p, q in v["home_plants"].items()
            if q["margin"] / half < 10
        ]
        print(f"{world}{label}: smallest home {worst}, untested {untested}, home plants below 10 "
              f"{homes}")  # fmt: skip


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "classes":
        classes(*sys.argv[2:4])
    elif action == "identities":
        identities(sys.argv[2])
    elif action == "paths":
        raise SystemExit(paths(*sys.argv[2:5]))
    elif action == "margins":
        margins(*sys.argv[2:5])
    else:
        raise SystemExit(__doc__)
