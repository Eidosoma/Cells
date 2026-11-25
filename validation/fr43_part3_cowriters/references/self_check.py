"""Read the written reference files as C0 reads them, and test them against separate code.

    python -I self_check.py [--out DIR] [--fast]

It imports nothing of the writer.  Its parts, per world of the invented and of the registered set:

0. the draws again, by a vectorised Threefry;
1. layout and C0 (CRITERIA 4.2) on the files alone, every derived number formed again from the published
   ones (counts, scales, accuracies, identities, start, running check, used differences, orders,
   estimates, tolerances, pairs, margins, the Lie order);
2. a third solution of the exact process, honest and planted, by SciPy's DOP853 in doubles with its own
   root finding, the affinities taken from the laws' logarithms;
3. the split model again at the two coarsest rungs (and the Lie plant at its coarsest) in plain doubles,
   the reactions' half-step by extrapolated Runge-Kutta steps and the gene unit's by SSPRK(3,3) in its
   convex form;
4. the invented set's own rules (SPEC 8): names, runs, no shared number, the refused and the stopped run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

HERE = Path(__file__).resolve().parent
SPEC = HERE.parent / "spec"
U = 2.0**-53
COPY = 1e15 / 6.02214076e23
PROBLEMS = []
COUNTS = {"checks": 0}


def expect(condition, what):
    COUNTS["checks"] += 1
    if not condition:
        PROBLEMS.append(what)


def close(a, b, relative, what):
    COUNTS["checks"] += 1
    if not abs(a - b) <= relative * max(abs(a), abs(b)):
        PROBLEMS.append(f"{what}: {a!r} against {b!r}")


# ------------------------------------------------------------------------------------ part 0: the draws


def threefry(key, block):
    """Threefry-2x32 with 20 rounds on arrays of 32-bit words."""
    rotations = (13, 15, 26, 6, 17, 29, 16, 24)
    schedule = (key[0], key[1], key[0] ^ key[1] ^ np.uint32(0x1BD11BDA))
    x, y = block[0] + schedule[0], block[1] + schedule[1]
    for turn in range(20):
        by = np.uint32(rotations[turn % 8])
        x = x + y
        y = ((y << by) | (y >> (np.uint32(32) - by))) ^ x
        if turn % 4 == 3:
            step = turn // 4 + 1
            x = x + schedule[step % 3]
            y = y + schedule[(step + 1) % 3] + np.uint32(step)
    return x, y


def draws_again(seed, site, pairs):
    """The pairs of LAWS section 6, vectorised over the counter: the hex strings of u1 and of u2."""
    with np.errstate(over="ignore"):
        zero = np.zeros(pairs, dtype=np.uint32)

        def word(number):
            return np.full(pairs, number, dtype=np.uint32)

        key = (zero, word(seed))
        for data in (word(site & 0xFFFFFFFF), word(site >> 32), word(1), np.arange(pairs, dtype=np.uint32), zero):
            key = threefry(key, (zero, data))
        out = []
        for element in (0, 1):
            high, low = threefry(key, (zero, word(element)))
            whole = (high.astype(np.uint64) << np.uint64(32)) | low.astype(np.uint64)
            u = ((whole & np.uint64(2**52 - 1)).astype(np.float64) + 0.5) * 2.0**-52
            out.append([float(v).hex() for v in u])
        return out


def part_zero(label, inputs, drawn):
    for name, block in inputs["worlds"].items():
        copies = drawn["worlds"][name]["copies"]
        expect([c["seed"] for c in copies] == block["seeds"], f"{label} {name}: the draws' seeds")
        for c in copies:
            again = draws_again(c["seed"], c["site_index"], inputs["draws"]["pairs_per_copy"])
            expect(again == [c["u1"], c["u2"]], f"{label} {name} c{c['copy']}: the draws")


# --------------------------------------------------------------------------- part 1: the files alone


def identity_text(world_name, world):
    """READOUTS section 4, written out from its text."""
    if world["kind"] == "reactions":
        return {
            "S cell": [("n_S_c", 1, "t"), ("n_S_c", -1, "0"), ("xi_1", -1, "t"), ("xi_2", 1, "t"), ("moved", 1, "t")],
            "S node": [("n_S_o", 1, "t"), ("n_S_o", -1, "0"), ("moved", -1, "t")],
            "X": [("n_X", 1, "t"), ("n_X", -1, "0"), ("xi_1", 1, "t")],
            "Y": [("n_Y", 1, "t"), ("n_Y", -1, "0"), ("xi_2", 1, "t")],
            "W": [("n_W", 1, "t"), ("n_W", -1, "0"), ("xi_2", -1, "t")],
            "S moiety": [(n, s, w) for w, s in (("t", 1), ("0", -1)) for n in ("n_X", "n_S_c", "n_S_o", "n_W")],
            "Y moiety": [(n, s, w) for w, s in (("t", 1), ("0", -1)) for n in ("n_Y", "n_W")],
        }
    length = world["gene"]["residues"]
    r = length / world["gene"]["stages"]
    return {
        "R cell": [("n_R_c", 1, "t"), ("n_R_c", -1, "0"), ("made", -1, "t"), ("lost", 1, "t"), ("moved", 1, "t")],
        "R node": [("n_R_o", 1, "t"), ("n_R_o", -1, "0"), ("moved", -1, "t")],
        "N": [("n_N", 1, "t"), ("n_N", -1, "0"), ("exits", r, "t")],
        "Pi": [("n_Pi", 1, "t"), ("n_Pi", -1, "0"), ("exits", -2 * r, "t")],
        "M": [("n_M", 1, "t"), ("n_M", -1, "0"), ("lost", -length, "t")],
        "machines": [("free", 1, "t"), ("engaged", 1, "t"), ("free", -1, "0"), ("engaged", -1, "0")],
        "engaged": [("engaged", 1, "t"), ("inits", -1, "t"), ("made", 1, "t")],
        "transit": [("transit", 1, "t"), ("exits", -r, "t"), ("made", length, "t")],
        "nucleoside": [
            (n, s * k, w)
            for w, s in (("t", 1), ("0", -1))
            for n, k in (("n_N", 1), ("n_M", 1), ("n_R_c", length), ("n_R_o", length), ("transit", 1))
        ],
    }


SERIES = {
    "reactions": ["n_S_c", "n_S_o", "n_X", "n_Y", "n_W", "xi_1", "xi_2", "moved"],
    "gene": ["n_R_c", "n_R_o", "n_N", "n_M", "n_Pi", "free", "engaged", "transit", "inits", "exits", "made", "lost",
             "moved"],
}


class Files:
    """One world's reference object beside its inputs."""

    def __init__(self, label, inputs, name, ref):
        self.label, self.inputs, self.name, self.ref = label, inputs, name, ref
        self.block = inputs["worlds"][name]
        self.end = self.block["end_s"]
        self.rungs = self.block["rungs_s"]
        self.judged = inputs["judged"][name]
        self.families = [f for f in inputs["families"] if f["world"] == name]
        self.plants = [p for p in inputs["plants"] if p["world"] == name]
        self.copies = ref["copies"]
        self.K = [c["events"]["K"] for c in self.copies]

    def say(self, text):
        return f"{self.label} {self.name}: {text}"

    def accuracy(self, readout):
        if readout == "t_events":
            return max(c["events"]["accuracy_s"] for c in self.copies)
        return max(max(c["series"][readout]["accuracy"][1:]) for c in self.copies)

    def e_round(self, readout, steps):
        return (4 if readout == "t_events" else 16) * (steps + 1) * U * self.ref["scales"][readout]

    def honest(self, readout, copies=None):
        copies = copies or self.copies
        if readout == "t_events":
            return [c["events"]["time_s"][:k] for c, k in zip(copies, self.K, strict=True)]
        return [c["series"][readout]["value"][1:] for c in copies]

    def families_of(self, plant):
        if plant["families"] == "both":
            return [f["id"] for f in self.families]
        return plant["families"]


def finite(value, path, files):
    if isinstance(value, dict):
        for key, inner in value.items():
            finite(inner, f"{path}.{key}", files)
    elif isinstance(value, list):
        for i, inner in enumerate(value):
            finite(inner, f"{path}[{i}]", files)
    elif isinstance(value, float):
        expect(math.isfinite(value), files.say(f"{path} is not finite"))


def rms(a, b):
    pairs = [(x, y) for left, right in zip(a, b, strict=True) for x, y in zip(left, right, strict=True)]
    return math.sqrt(sum((x - y) ** 2 for x, y in pairs) / len(pairs))


def slope(x, y):
    x, y = np.log(x), np.log(y)
    return float(np.sum((x - x.mean()) * (y - y.mean())) / np.sum((x - x.mean()) ** 2))


def part_one(files, digest):
    ref, inputs, name = files.ref, files.inputs, files.name
    for key in ("kind", "world", "inputs_sha256", "copies", "scales", "classes", "planted", "sizing", "plants",
                "draws_check", "reported", "provenance"):
        expect(key in ref, files.say(f"the key {key} is missing"))
    finite(ref, "", files)
    expect(ref["kind"] == "fr43 part 3 co-writers reference, version 2", files.say("kind"))
    expect(ref["world"] == name and ref["inputs_sha256"] == digest, files.say("world or inputs_sha256"))
    expect(ref["draws_check"]["identical"] is True, files.say("draws_check"))
    expect(
        ref["draws_check"]["entries"] == 2 * inputs["draws"]["pairs_per_copy"] * len(files.copies),
        files.say("draws_check entries"),
    )
    wanted = {item["readout"]: "S" for item in files.judged["S"]} or {"t_events": "R"}
    expect(ref["classes"] == wanted, files.say("classes"))
    expect([c["seed"] for c in files.copies] == files.block["seeds"], files.say("seeds"))
    for key, text in identity_text(name, files.block).items():
        given = sorted((n, float(k), w) for n, k, w in inputs["identities"][name][key])
        expect(given == sorted((n, float(k), w) for n, k, w in text), files.say(f"identity {key} in the inputs"))
    copies_and_scales(files)
    sizing(files)
    margins(files)
    for c in files.copies:
        expect(len(c["checks"]) > 0, files.say("no checks"))
        for check in c["checks"]:
            expect(check["passes"] is True and check["residual"] <= check["bound"],
                   files.say(f"c{c['copy']} check {check['name']}"))


def copies_and_scales(files):
    ref, inputs, block = files.ref, files.inputs, files.block
    samples, end = block["samples_s"], files.end
    names = SERIES[block["kind"]]
    expect(set(ref["scales"]) == {"t_events", *names}, files.say("scales' names"))
    expect(all(s > 0 for s in ref["scales"].values()), files.say("a scale is not positive"))
    cut = end - inputs["guard_steps"] * files.rungs[0]
    limit = (1e-15 if "t_events" in files.judged["R"] else 1e-11) * end
    for c in files.copies:
        events = c["events"]
        times = events["time_s"]
        expect(c["samples_s"] == samples, files.say("samples"))
        expect(events["K_all"] == len(times) == len(events["channel"]) == len(events["counts_after"]), files.say("K_all"))
        expect(events["K"] == sum(1 for t in times if t <= cut), files.say("K"))
        expect(all(b > a for a, b in zip(times, times[1:], strict=False)) and times[-1] <= end, files.say("times"))
        for k, (channel, counts) in enumerate(zip(events["channel"], events["counts_after"], strict=True)):
            expect((channel, counts) == (("assemble", [0, 1]) if k % 2 == 0 else ("dissolve", [2, 0])),
                   files.say(f"event {k}"))
        expect(min(abs(t - cut) for t in times) > 1e-9 * end, files.say("an event at the guard"))
        expect(events["K_all"] < inputs["draws"]["pairs_per_copy"], files.say("draws"))
        expect(0 < events["accuracy_s"] <= limit, files.say("the events' accuracy"))
        expect(events["K"] >= inputs["minimum_events"][files.name]["per_copy"], files.say("minimum events"))
        series = c["series"]
        expect(set(series) == set(names), files.say("the series' names"))
        for n in names:
            expect(len(series[n]["value"]) == len(series[n]["accuracy"]) == len(samples), files.say(f"{n} length"))
            expect(max(series[n]["accuracy"]) <= 1e-11 * ref["scales"][n], files.say(f"{n} accuracy"))
        value = {n: series[n]["value"] for n in names}
        for n, declared in inputs["start"][files.name].items():
            declared = block["gene"]["machines_copies"] * COPY if isinstance(declared, str) else declared
            expect(abs(value[n][0] - declared) <= 4 * U * abs(declared), files.say(f"start {n}"))
        for key, terms in inputs["identities"][files.name].items():
            least = min(abs(k) * ref["scales"][n] for n, k, _ in terms)
            for i in range(len(samples)):
                total = math.fsum(k * value[n][i if w == "t" else 0] for n, k, w in terms)
                expect(abs(total) <= 1e-11 * least, files.say(f"identity {key} at {samples[i]}"))
    expect(sum(files.K) >= inputs["minimum_events"][files.name]["total"], files.say("minimum events in all"))

    def largest(n, *books):
        return max(
            abs(c["series"][n]["value"][i])
            + (abs(c["series"][n]["value"][0]) if books else 0.0)
            + sum(abs(c["series"][b]["value"][i]) for b in books)
            for c in files.copies
            for i in range(len(samples))
        )

    if block["kind"] == "reactions":
        special = {"n_S_c": ("xi_1", "xi_2", "moved"), "n_S_o": ("moved",)}
    else:
        special = {"n_R_c": ("made", "lost", "moved"), "n_R_o": ("moved",)}
    for n in names:
        close(ref["scales"][n], largest(n, *special.get(n, ())), 1e-14, files.say(f"scale {n}"))
    expect(ref["scales"]["t_events"] == end, files.say("scale t_events"))
    if "running" in files.judged:
        running = files.judged["running"]
        for c in files.copies:
            last = {n: c["series"][n]["value"][-1] for n in names}
            first = {n: c["series"][n]["value"][0] for n in names}
            for book, key in (("xi_1", "X"), ("xi_2", "Y"), ("moved", "S node")):
                size = sum(abs(k) * abs((last if w == "t" else first)[n]) for n, k, w in inputs["identities"][files.name][key])
                for h in files.rungs:
                    bound = 16 * (end / h + 1) * U * size
                    expect(abs(last[book]) > running["multiple"] * bound, files.say(f"running check {book} h={h}"))


def one_statistic(files, got, rungs, entry, label):
    readout, p = entry["readout"], entry["p"]
    steps = [files.end / h for h in rungs]
    bounds = [files.e_round(readout, s) for s in steps]
    expect(len(got["d"]) == len(rungs) - 1, files.say(f"{label} d"))
    used = 0
    for j, d in enumerate(got["d"]):
        if not d > 10 * (bounds[j] + bounds[j + 1]):
            break
        used = j + 1
    expect(got["used"] == used, files.say(f"{label} used"))
    estimate = max(got["d"][-1] / (2**p - 1), got["d"][-2] / (2**p * (2**p - 1)))
    close(got["est"], estimate, 1e-12, files.say(f"{label} est"))
    close(got["tau"], 3 * estimate + files.accuracy(readout) + bounds[-1], 1e-12, files.say(f"{label} tau"))
    if used >= 3:
        close(got["q"], slope(rungs[:used], got["d"][:used]), 1e-9, files.say(f"{label} q"))
    else:
        expect(got["q"] is None, files.say(f"{label} q is not null"))
    return used


def sizing(files):
    got = files.ref["sizing"]
    for family in files.families:
        for entry in files.judged["S"]:
            readout = entry["readout"]
            label = f"sizing {family['id']} {readout}"
            here = got[family["id"]][readout]
            used = one_statistic(files, here, files.rungs, entry, label)
            one_statistic(files, here["retry"], files.rungs[1:] + [files.block["retry_rung_s"]], entry, label + " retry")
            if readout in files.judged["at_rounding"]:
                expect(used < 3, files.say(f"{label}: named and resolved"))
            else:
                expect(used >= 3 and abs(here["q"] - entry["p"]) <= 0.4, files.say(f"{label}: order {here['q']}"))
            expect(here["E"] <= here["tau"], files.say(f"{label}: E above tau"))
    for kind, rows in [("pair", {"pair": got["pair"]}), ("rungs", got["rungs"])]:
        for row in rows.values():
            for readout, entry in row.items():
                close(entry["threshold"], 10 * files.e_round(readout, files.end / files.rungs[0]), 1e-12,
                      files.say(f"{kind} {readout} threshold"))
                close(entry["ratio"], entry["rms"] / entry["threshold"], 1e-12, files.say(f"{kind} {readout} ratio"))
                expect(entry["ratio"] >= 10, files.say(f"{kind} {readout}: {entry['ratio']}"))
    expect(set(got["pair"]) == set(files.judged["orders_differ"]), files.say("pair's readouts"))
    differ = files.judged.get("rungs_differ", [])
    expect(set(got["rungs"]) == ({f["id"] for f in files.families} if differ else set()), files.say("rungs' families"))
    for rows in got["rungs"].values():
        expect(set(rows) == set(differ), files.say("rungs' readouts"))
    for mutant in got["mutant"].values():
        close(mutant["q"], slope(files.rungs[-3:], mutant["E"]), 1e-9, files.say("mutant q"))
        expect(abs(mutant["q"] - 1) <= 0.25, files.say(f"P3's order {mutant['q']}"))


def margins(files):
    ref = files.ref
    listed = {(m["plant"], m["family"], m["check"]): m for m in ref["plants"]}
    expected = set()
    for plant in files.plants:
        families = [None] if plant["kind"] == "record" else files.families_of(plant)
        for family in families:
            for check_class, check in plant["must_fail"]:
                expected.add((plant["id"], family, check))
                entry = listed.get((plant["id"], family, check))
                if entry is None:
                    expect(False, files.say(f"plant {plant['id']} {family} {check} is missing"))
                    continue
                label = files.say(f"plant {plant['id']} {family} {check}")
                expect(entry["no_margin"] is bool(plant.get("no_margin")), label + " no_margin")
                if entry["no_margin"]:
                    k = files.K[0]
                    expect(entry["distance"] == k - k // 2, label + " distance")
                    continue
                close(entry["margin"], entry["distance"] / entry["expected_tolerance"], 1e-12, label + " margin")
                expect(entry["margin"] >= 10 * (1 - 1e-9), label + f" margin {entry['margin']}")
                distance, tolerance = margin_again(files, plant, family, check_class, check)
                close(entry["distance"], distance, 1e-9, label + " distance")
                close(entry["expected_tolerance"], tolerance, 1e-12, label + " tolerance")
    expect(set(listed) == expected, files.say("the plants listed"))


def margin_again(files, plant, family, check_class, check):
    ref, honest = files.ref, files.copies
    if plant["kind"] == "record":
        return record_again(files, plant, check)
    if plant["kind"] == "engine":
        return max(ref["sizing"]["mutant"][family]["E"]), ref["sizing"][family][check]["tau"]
    if plant["id"].startswith("P4"):
        tolerance = ref["sizing"][family][check]["tau"]
        close(ref["planted"][plant["id"]][family]["shift_s"], 10 * tolerance, 1e-12, files.say("P4's shift"))
        return 10 * tolerance, tolerance
    planted = ref["planted"][plant["id"]][family]
    if check == "t_events":
        pairs = []
        for c, other, k in zip(honest, planted, files.K, strict=True):
            k = min(k, other["events"]["K_all"])
            pairs.append((c["events"]["time_s"][:k], other["events"]["time_s"][:k]))
        if check_class == "R":
            far = max(abs(x - y) for a, b in pairs for x, y in zip(a, b, strict=True))
            return far, files.e_round(check, files.end / files.rungs[0]) + files.accuracy(check)
        distance = rms([a for a, _ in pairs], [b for _, b in pairs])
    else:
        distance = rms(files.honest(check), files.honest(check, planted))
    return distance, ref["sizing"][family][check]["tau"]


def record_again(files, plant, check):
    value = {n: list(s["value"]) for n, s in files.copies[0]["series"].items()}
    edited = {n: list(v) for n, v in value.items()}
    if plant["id"].startswith("P6"):
        book = "xi_2" if plant["id"] == "P6" else "lost"
        edited[book] = [v * (1 + 1e-3) for v in value[book]]
    elif plant["id"] in ("P7", "P7-W6", "P13", "P15"):
        for n in {"P7": ["n_S_o"], "P7-W6": ["n_R_o"], "P13": ["n_Pi"], "P15": ["n_N", "n_M"]}[plant["id"]]:
            edited[n] = [value[n][0]] * len(value[n])
    else:
        n = check.split(" ", 1)[1]
        return abs(value[n][0] * 1.01 - value[n][0]), 4 * U * abs(value[n][0])
    best = (0.0, 1.0)
    for i, t in enumerate(files.block["samples_s"]):
        if t == 0.0:
            continue
        terms = files.inputs["identities"][files.name][check.split(" ", 1)[1]]
        pick = [i if w == "t" else 0 for _, _, w in terms]
        size = sum(abs(k * value[n][j]) for (n, k, _), j in zip(terms, pick, strict=True))
        apart = abs(math.fsum(k * (edited[n][j] - value[n][j]) for (n, k, _), j in zip(terms, pick, strict=True)))
        bound = 16 * (t / files.rungs[0] + 1) * U * size
        if apart / bound > best[0] / best[1]:
            best = (apart, bound)
    return best


# ------------------------------------------------------------------- part 2: the exact process, again


class Law:
    """The laws of one world from their text, in doubles: the state's rates with the hazard last."""

    def __init__(self, block, dropped=()):
        self.block, self.dropped = block, dropped
        channels = {c["id"]: c for c in block["population"]["channels"]}
        self.k_assemble = channels["assemble"]["rate_constant"]
        self.read = channels["assemble"]["read"]
        self.k_dissolve = channels["dissolve"]["rate_constant"]
        self.g = block["population"]["transfer"]["conductance_pL_per_s"]["active"]
        self.cell, self.node = block["cell_pL"], block["node_pL"]
        rows = block["rows_fmol"]
        if block["kind"] == "reactions":
            self.k1, self.k2 = (r["rate_constant"] for r in block["reactions"])
            self.start = [rows["S_cell"], rows["S_node"], rows["X"], rows["Y"], rows["W"], 0.0, 0.0, 0.0, 0.0]
            self.names = SERIES["reactions"]
        else:
            gene = block["gene"]
            self.gene, self.m, self.L = gene, gene["stages"], gene["residues"]
            self.r = self.L / self.m
            self.kappa = gene["speed_per_s"] / self.r
            self.c_t = gene["template_copies"] * COPY / self.cell
            self.mu_res = gene["mu_RT"]["R"] / self.L
            self.start = (
                [rows["R_cell"], rows["R_node"], rows["N"], rows["M"], rows["Pi"], gene["machines_copies"] * COPY]
                + [0.0] * self.m + [0.0] * 6
            )

    def affinities(self, n, pi, m, r):
        mu, unit = self.gene["mu_RT"], self.cell * self.gene["c0_mM"]
        x = self.mu_res + 2 * (mu["Pi"] + math.log(pi / unit)) - (mu["N"] + math.log(n / unit))
        y = (mu["M"] + math.log(m / unit)) - self.mu_res - math.log(r / unit) / self.L
        return x, y

    def rates(self, active, y):
        cell, node = y[0] / self.cell, y[1] / self.node
        flow = self.g * (cell - node) if active else 0.0
        if active:
            total = self.k_dissolve
        elif self.read is None:
            total = 2 * self.k_assemble
        else:
            total = 2 * self.k_assemble * (cell if self.read["at"] == "cell" else node)
        if self.block["kind"] == "reactions":
            one = self.k1 * y[2]
            two = self.k2 * self.cell * cell * (y[3] / self.cell)
            return [one - two - flow, flow, -one, -two, two, one, two, flow, total]
        gene, m = self.gene, self.m
        r_c, n, mono, pi, free, chain = y[0], y[2], y[3], y[4], y[5], y[6 : 6 + m]
        x, a = self.affinities(n, pi, mono, r_c)
        c_n = n / self.cell
        phi = c_n / (gene["saturation_mM"]["N"] + c_n) * (1.0 if "e^x" in self.dropped else -math.expm1(x))
        begun = gene["initiation_per_mM_s"] * self.c_t * free
        flux = [self.kappa * phi * c for c in chain]
        exits = math.fsum(flux)
        lost = gene["degradation"]["rate_per_s"] * r_c * (1.0 if "e^y" in self.dropped else -math.expm1(a))
        links = [begun, *flux]
        return (
            [flux[-1] - lost - flow, flow, -self.r * exits, self.L * lost, 2 * self.r * exits, flux[-1] - begun]
            + [links[j] - links[j + 1] for j in range(m)]
            + [begun, exits, flux[-1], lost, flow, total]
        )

    def tolerances(self):
        if self.block["kind"] == "reactions":
            return [1e-13] * 8 + [1e-13]
        rows = self.block["rows_fmol"]
        chain, machines = rows["N"] / self.L, self.start[5]
        return (
            [1e-13 * chain] * 2 + [1e-13 * rows["N"]] * 3 + [1e-13 * machines] * (self.m + 1) + [1e-13 * chain] * 5 + [1e-13]
        )

    def readouts(self, y):
        if self.block["kind"] == "reactions":
            return dict(zip(self.names, y[:8], strict=True))
        m = self.m
        chain = y[6 : 6 + m]
        inits, exits, made, lost, moved = y[6 + m : 11 + m]
        return {
            "n_R_c": y[0], "n_R_o": y[1], "n_N": y[2], "n_M": y[3], "n_Pi": y[4], "free": y[5],
            "engaged": math.fsum(chain), "transit": self.r * math.fsum(j * c for j, c in enumerate(chain)),
            "inits": inits, "exits": exits, "made": made, "lost": lost, "moved": moved,
        }


def planted_law(block, plant):
    """The law with one reference plant's change (LAWS section 9)."""
    changed = json.loads(json.dumps(block))
    name, dropped = plant["id"], ()
    channel = changed["population"]["channels"][0]
    if name == "P1":
        changed["reactions"][0]["rate_constant"] *= 1.01
    elif name == "P2":
        changed["gene"]["initiation_per_mM_s"] *= 1.01
    elif name == "P5":
        channel["rate_constant"] *= 1.01
    elif name == "P9":
        channel["read"]["at"] = "node"
    elif name == "P10":
        for reaction in changed["reactions"]:
            reaction["rate_constant"] = 0.0
    elif name == "P10-W6":
        changed["gene"]["initiation_per_mM_s"] = 0.0
    else:
        dropped = {"P11": ("e^x",), "P12": ("e^y",)}[name]
    return Law(changed, dropped)


def third_solution(law, thresholds, end, samples):
    """DOP853 from event to event; the hazard's threshold is its terminal event."""
    tolerances = law.tolerances()
    y, t, active = list(law.start), 0.0, False
    times, rows, following = [], [law.readouts(y)], 1
    while t < end:
        need = thresholds[len(times)]

        def fires(_, v, need=need):
            return v[-1] - need

        fires.terminal, fires.direction = True, 1
        found = solve_ivp(
            lambda _, v, active=active: law.rates(active, v), (t, end), y, method="DOP853", rtol=1e-12,
            atol=tolerances, events=fires, dense_output=True,
        )
        stop = found.t[-1]
        while following < len(samples) and samples[following] <= stop:
            rows.append(law.readouts(list(found.sol(samples[following]))))
            following += 1
        y, t = [float(v) for v in found.y[:, -1]], float(stop)
        if found.status != 1:
            break
        times.append(t)
        y[-1] = 0.0
        active = not active
    return times, rows


def threefry_thresholds(drawn, name, c):
    return [-math.log(float.fromhex(u)) for u in drawn["worlds"][name]["copies"][c]["u1"]]


def part_two(files, drawn, worst):
    """The third solution's distance from the published ones, over T and over each readout's scale."""
    samples = files.block["samples_s"]
    sets = [("", Law(files.block), files.copies)]
    for plant in files.plants:
        series = [s for s in files.ref["planted"].get(plant["id"], {}).values() if isinstance(s, list)]
        if series:
            expect(all(s == series[0] for s in series), files.say(f"{plant['id']}: its families differ"))
            sets.append((plant["id"] + " ", planted_law(files.block, plant), series[0]))
    cut = files.end - files.inputs["guard_steps"] * files.rungs[0]
    for label, law, copies in sets:
        for c, copy in enumerate(copies):
            times, rows = third_solution(law, threefry_thresholds(drawn, files.name, c), files.end, samples)
            events = copy["events"]
            expect(len(times) == events["K_all"], files.say(f"{label}c{c}: the third solution's number of events"))
            expect(events["K"] == sum(1 for t in events["time_s"] if t <= cut), files.say(f"{label}c{c}: K"))
            far = max((abs(a - b) for a, b in zip(times, events["time_s"], strict=False)), default=0.0) / files.end
            worst[f"{label}t_events / T"] = max(worst.get(f"{label}t_events / T", 0.0), far)
            for n, s in copy["series"].items():
                far = max(abs(a - row[n]) for a, row in zip(s["value"], rows, strict=True)) / files.ref["scales"][n]
                worst[f"{label}{n} / scale"] = max(worst.get(f"{label}{n} / scale", 0.0), far)


# ------------------------------------------------------------------------- part 3: the split, again


class SiteAgain:
    def __init__(self, law, thresholds, cell, node):
        self.law, self.thresholds, self.cell, self.node = law, thresholds, cell, node
        self.moved, self.hazard, self.active, self.times = 0.0, 0.0, False, []

    def advance(self, start, tau):
        law, t, stop = self.law, 0.0, tau
        while True:
            if self.active:
                total = law.k_dissolve
            else:
                total = 2 * law.k_assemble * (1.0 if law.read is None else self.cell / law.cell)
            need = self.thresholds[len(self.times)] - self.hazard
            wait = need / total
            step = min(wait, stop - t)
            if self.active:
                # dn_c/dt = -g (n_c/V_c - n_o/V_o) with n_c + n_o fixed
                rate = law.g * (1 / law.cell + 1 / law.node)
                apart = self.cell / law.cell - self.node / law.node
                flow = apart * law.g * -math.expm1(-rate * step) / rate
                self.cell, self.node, self.moved = self.cell - flow, self.node + flow, self.moved + flow
            if wait > stop - t:
                self.hazard += total * step
                return
            t += step
            self.times.append(start + t)
            self.hazard, self.active = 0.0, not self.active


def reactions_flow(law, state, tau, pieces=1):
    """W5's B by classical RK4 with a Richardson step: the state is S, X, Y, W, xi_1, xi_2."""

    def f(v):
        one = law.k1 * v[1]
        two = law.k2 * v[0] * v[2] / law.cell
        return np.array([one - two, -one, -two, two, one, two])

    def rk4(v, h):
        a = f(v)
        b = f(v + h / 2 * a)
        c = f(v + h / 2 * b)
        d = f(v + h * c)
        return v + h / 6 * (a + 2 * b + 2 * c + d)

    v = np.array(state)
    h = tau / pieces
    for _ in range(pieces):
        whole, half = rk4(v, h), rk4(rk4(v, h / 2), h / 2)
        v = half + (half - whole) / 15
    return list(v)


def gene_flow(law, state, tau):
    """W6's B: one SSPRK(3,3) step in Shu and Osher's convex form; the state is the law's without R_node."""

    def f(v):
        full = law.rates(False, [v[0], 0.0, *v[1:], 0.0, 0.0])
        return np.array([full[0], *full[2 : len(v) + 1]])

    u = np.array(state)
    one = u + tau * f(u)
    two = 0.75 * u + 0.25 * (one + tau * f(one))
    return list(u / 3 + 2 / 3 * (two + tau * f(two)))


def split_again(files, thresholds, first, h, lie=False):
    law = Law(files.block)
    tau, steps = h / 2, round(files.end / h)
    start = law.start
    site = SiteAgain(law, thresholds, start[0], start[1])
    gene = files.block["kind"] == "gene"
    # the co-writer's state without the cell's shared row, which the site holds
    state = list(start[2 : -2]) if gene else [start[2], start[3], start[4], 0.0, 0.0]
    forward = [first != "population", first == "population"]
    marks = [round(t / h) for t in files.block["samples_s"][1:]]
    rows = []
    for step in range(steps):
        halves = 0
        for cowriter in forward + (forward if lie else forward[::-1]):
            if cowriter:
                flow = gene_flow if gene else reactions_flow
                after = flow(law, [site.cell, *state], tau)
                site.cell, state = after[0], after[1:]
            else:
                site.advance(step * h + halves * tau, tau)
                halves += 1
        if step + 1 in marks:
            if gene:
                full = law.readouts([site.cell, site.node, *state, site.moved, 0.0])
            else:
                x, other, w, e1, e2 = state
                full = {"n_S_c": site.cell, "n_S_o": site.node, "n_X": x, "n_Y": other, "n_W": w, "xi_1": e1,
                        "xi_2": e2, "moved": site.moved}
            rows.append(full)
    return site.times, rows


def part_three(files, drawn, worst):
    """The first difference d_1 of every S readout and the pair at h_1, from plain doubles."""
    rungs = files.rungs[:2]
    firsts = [f["first"] for f in files.families]
    runs = {}
    for first in firsts:
        for h in rungs:
            runs[first, h] = [
                split_again(files, threefry_thresholds(drawn, files.name, c), first, h) for c in range(len(files.copies))
            ]

    def series(first, h, readout):
        if readout == "t_events":
            return [run[0][:k] for run, k in zip(runs[first, h], files.K, strict=True)]
        return [[row[readout] for row in run[1]] for run in runs[first, h]]

    for family in files.families:
        for entry in files.judged["S"]:
            readout = entry["readout"]
            if readout in files.judged["at_rounding"]:
                continue
            again = rms(series(family["first"], rungs[1], readout), series(family["first"], rungs[0], readout))
            given = files.ref["sizing"][family["id"]][readout]["d"][0]
            worst[f"d_1 {readout}"] = max(worst.get(f"d_1 {readout}", 0.0), abs(again / given - 1))
        for readout, got in files.ref["sizing"]["rungs"].get(family["id"], {}).items():
            again = rms(series(family["first"], rungs[1], readout), series(family["first"], rungs[0], readout))
            worst[f"rungs {readout}"] = max(worst.get(f"rungs {readout}", 0.0), abs(again / got["rms"] - 1))
    for readout, got in files.ref["sizing"]["pair"].items():
        again = rms(series(firsts[0], rungs[0], readout), series(firsts[1], rungs[0], readout))
        worst[f"pair {readout}"] = max(worst.get(f"pair {readout}", 0.0), abs(again / got["rms"] - 1))
    for family_id, got in files.ref["sizing"]["mutant"].items():
        first = next(f["first"] for f in files.families if f["id"] == family_id)
        h = files.rungs[-3]
        again = rms(
            [
                split_again(files, threefry_thresholds(drawn, files.name, c), first, h, lie=True)[0][:k]
                for c, k in enumerate(files.K)
            ],
            files.honest("t_events"),
        )
        worst["mutant E"] = abs(again / got["E"][0] - 1)


# ------------------------------------------------------------------- part 4: the invented set's rules


def walk_numbers(value, path=()):
    """Every number of a nested value with its path of keys."""
    if isinstance(value, dict):
        for key, inner in value.items():
            yield from walk_numbers(inner, (*path, key))
    elif isinstance(value, list):
        for inner in value:
            yield from walk_numbers(inner, path)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield path, float(value)


KIND_OF_KEY = {
    "cell_pL": "volume", "node_pL": "volume", "end_s": "horizon", "rows_fmol": "amount", "rate_constant": "rate",
    "speed_per_s": "rate", "initiation_per_mM_s": "rate", "rate_per_s": "rate", "conductance_pL_per_s": "conductance",
    "seeds": "seed", "rungs_s": "rung", "retry_rung_s": "rung", "step_s": "rung", "samples_s": "time",
    "time_s": "time", "template_copies": "count", "machines_copies": "count", "saturation_mM": "concentration",
    "mu_RT": "potential", "residues": "chain", "stages": "chain",
}


def kinds_of(inputs):
    out = {}
    blocks = {"worlds": inputs["worlds"], "runs": inputs["runs"], "restart": inputs["restart"]}
    for path, number in walk_numbers(blocks):
        for key in path:
            if key in KIND_OF_KEY and number != 0.0:
                out.setdefault(KIND_OF_KEY[key], set()).add(number)
    return out


def part_four(invented, registered, drawn):
    left, right = kinds_of(invented), kinds_of(registered)
    expect(set(left) == set(right), "the invented set's kinds of numbers")
    for kind in sorted(left):
        expect(not left[kind] & right[kind], f"the invented set shares a {kind}: {sorted(left[kind] & right[kind])}")
    expect(set(invented) == set(registered), "the invented inputs' top-level keys")
    for name, world in invented["worlds"].items():
        expect(set(world) == set(registered["worlds"][name]), f"the invented world {name}'s keys")
        for t in world["samples_s"]:
            expect((t / world["rungs_s"][0]).is_integer(), f"{name}: the sample {t} is off the grid")
        expect((invented["restart"].get(name, {"time_s": 0.0})["time_s"] / world["rungs_s"][0]).is_integer(), name)
    for source, label in ((invented, "invented"), (registered, "registered")):
        names = [run["name"] for run in source["runs"]]
        expect(len(set(names)) == len(names), f"{label}: a run is listed twice")
        for run in source["runs"] + source["retry"].get("runs", []):
            stem = f"{run['world']} {run['first']}-first h={run['step_s']!r} c{run['copy']}"
            expect(run["name"].startswith(stem), f"{label}: the name {run['name']}")
            suffix = run["name"][len(stem):]
            expect((suffix, run["role"]) in {("", "judged"), (" restart", "support"), (" lie", "plant"),
                                             (" refused", "support"), (" stopped", "support"), (" retry", "judged")},
                   f"{label}: the run {run['name']}")
        for family in source["families"]:
            for h in family["rungs_s"]:
                for c in range(source["copies"]):
                    expect(f"{family['id']} h={h!r} c{c}" in names, f"{label}: a judged run of {family['id']} is missing")
    for entry in invented["placement"]:
        rung = invented["worlds"][entry["world"]]["rungs_s"][0]
        expect(entry["dt_a0_max_at_the_coarsest_step"] == entry["largest_propensity_per_s"] * rung <= 0.25,
               f"the placement of {entry['world']}")
    by_variant = {run["variant"]: run for run in invented["runs"] if run["variant"] in ("refused", "stopped")}
    refused = by_variant["refused"]
    exact = next(e for e in invented["placement"] if e["world"] == refused["world"])
    expect(exact["largest_propensity_per_s"] * refused["step_s"] > 1, "the refused run keeps the placement")
    stopped = by_variant["stopped"]
    block = json.loads(json.dumps(invented["worlds"][stopped["world"]]))
    ((path, number),) = stopped["change"].items()
    outer, inner = path.split(".")
    expect(inner in block[outer], "the stopped run's change names a declared row")
    block[outer][inner] = number
    law = Law(block)
    _, rows = third_solution(law, threefry_thresholds(drawn, stopped["world"], 0), block["end_s"], block["samples_s"])
    x = [law.affinities(row["n_N"], row["n_Pi"], row["n_M"], row["n_R_c"])[0] for row in rows]
    expect(x[0] < -1.1 and x[-1] > -0.9, f"the stopped run's x goes from {x[0]} to {x[-1]}")
    return x


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=HERE / "out")
    parser.add_argument("--fast", action="store_true", help="part 1 and part 4 alone")
    parser.add_argument("--invented-only", action="store_true")
    arguments = parser.parse_args()
    registered_bytes = (SPEC / "inputs.json").read_bytes()
    registered = json.loads(registered_bytes)
    invented_bytes = (arguments.out / "inputs_invented.json").read_bytes()
    invented = json.loads(invented_bytes)
    drawn = {
        "invented": json.loads((arguments.out / "draws_invented.json").read_bytes()),
        "registered": json.loads((SPEC / "draws.json").read_bytes()),
    }
    references = json.loads((arguments.out / "reference_invented.json").read_bytes())
    sets = [("invented", invented, hashlib.sha256(invented_bytes).hexdigest(), references)]
    if not arguments.invented_only:
        own = {n: json.loads((arguments.out / f"reference_{n}.json").read_bytes()) for n in registered["worlds"]}
        sets.append(("registered", registered, hashlib.sha256(registered_bytes).hexdigest(), own))
    x = part_four(invented, registered, drawn["invented"])
    print(f"stopped run: x at the samples from {x[0]:.4f} to {x[-1]:.4f}")
    for label, inputs, digest, refs in sets:
        part_zero(label, inputs, drawn[label])
        expect(set(refs) == set(inputs["worlds"]), f"{label}: the worlds")
        for name, ref in refs.items():
            files = Files(label, inputs, name, ref)
            part_one(files, digest)
            if arguments.fast:
                continue
            exact, split = {}, {}
            part_two(files, drawn[label], exact)
            part_three(files, drawn[label], split)
            print(f"{label} {name}: third solution, worst {max(exact.values()):.2e} "
                  f"({max(exact, key=exact.get)}); split again, worst relative {max(split.values()):.2e} "
                  f"({max(split, key=split.get)})")
            expect(max(exact.values()) <= 1e-9, f"{label} {name}: the third solution departs: {exact}")
            expect(max(split.values()) <= 1e-3, f"{label} {name}: the split again departs: {split}")
    print(f"{COUNTS['checks']} checks, {len(PROBLEMS)} problems")
    for problem in PROBLEMS:
        print("PROBLEM", problem)
    sys.exit(1 if PROBLEMS else 0)


if __name__ == "__main__":
    main()
