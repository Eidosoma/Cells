"""The invented pools run alone, by the frozen snapshot's own pool code: their paths and arrays.

    PYTHONPATH=SNAPSHOT/src:SNAPSHOT pool_paths.py run OUT.npz [--rate NAME --factor 1.01]
    PYTHONPATH=SNAPSHOT/src:SNAPSHOT pool_paths.py all DIR   the pools as declared and, for
                                                             PW-pool, with each rate x 1.01
    pool_paths.py look OUT.npz                               every path, in short
    pool_paths.py near OUT.npz    the distance of every event from every grid point and stage
                                  middle of its steps

`run` makes every pool of inputs_rehearsal.json (world, seed index, cell) with its events recorded
and saves, for each, the final 19 arrays and the committed events: time, mask and bonds after the
event, and the availability after it (1 if the bond mask has at least as many set bits as the
occupied mask, SPEC section 3.2). `--rate` multiplies one rate (a PW-pool plant). Nothing is read
but the inputs file.
"""

import argparse
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RATES = ("k_on_M_inv_s", "k_close_s_inv", "k_off_s_inv", "k_fragment_dissolve_s_inv")


def definition(entry, seed_index, rate=None, factor=1.0):
    p = dict(entry["pool"])
    p = {k: p[k] for k in p if k not in ("model", "topology", "initial_bond_indices")}
    if rate is not None:
        p[rate] = p[rate] * factor
    p.update(
        seed=entry["seeds"][seed_index],
        recording="events",
        event_chunk_size=128,
        max_output_bytes=8 * 1024**3 // 2,
        max_wall_seconds=3600.0,
    )
    return p


def run_pool(raw):
    """(final PoolState, events) with events a list of per-world lists of (time, mask, bonds)."""
    from cells.assembly_pool import engine
    from cells.assembly_pool.spec import parse_spec

    spec = parse_spec(raw)
    events = [[] for _ in range(spec.worlds)]

    def callback(_, host, trace):
        when, mask, bonds, _, event = (np.asarray(v) for v in trace)
        for i in range(when.shape[0]):
            for w in range(when.shape[1]):
                if event[i, w] >= 0:
                    events[w].append((float(when[i, w]), int(mask[i, w]), int(bonds[i, w])))

    state, report = engine.run(spec, callback=callback)
    return spec, state, events, report


def availability(mask, bonds):
    return 1 if bonds.bit_count() >= mask.bit_count() else 0


def all_pools(inputs):
    for world, w in inputs["worlds"].items():
        for cell, entry in (w.get("pools") or {}).items():
            for s in range(len(entry["seeds"])):
                yield world, cell, s, entry


def run(path, rate, factor):
    inputs = json.loads((HERE / "inputs_rehearsal.json").read_text())
    saved, log = {}, []
    for world, cell, s, entry in all_pools(inputs):
        spec, state, events, report = run_pool(definition(entry, s, rate, factor))
        key = f"{world}/{cell}/s{s}"
        for name, value in state._asdict().items():
            saved[f"{key}/final/{name}"] = np.asarray(value)
        for k, rows in enumerate(events):
            saved[f"{key}/path/{k}"] = np.array(
                [(t, availability(m, b)) for t, m, b in rows], dtype=np.float64
            ).reshape(-1, 2)
        n = sum(len(e) for e in events)
        log.append((key, n, int(np.asarray(state.event_count).sum())))
    np.savez_compressed(path, **saved)
    for row in log:
        print(*row)


def look(path):
    d = np.load(path)
    worlds = sorted({k.rsplit("/path/", 1)[0] for k in d if "/path/" in k})
    for key in worlds:
        print(key)
        for k in sorted((int(x.rsplit("/", 1)[1]) for x in d if x.startswith(key + "/path/"))):
            p = d[f"{key}/path/{k}"]
            flips = sum(1 for i in range(len(p)) if p[i, 1] != (p[i - 1, 1] if i else 1.0))
            print(
                "  world",
                k,
                "events",
                len(p),
                "changes",
                flips,
                [f"{t:.5f}:{int(a)}" for t, a in p[:8]],
            )


def run_all(folder):
    """The pools as declared, then one rate x 1.01 at a time."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    run(folder / "pools.npz", None, 1.0)
    for rate in RATES:
        run(folder / f"pools-{rate}.npz", rate, 1.01)


def near(path):
    """The smallest distance of an event from a grid point or a stage middle, as a share of a step,
    over every step of the world's judged families, the retry step and half of it (SPEC 3.2)."""
    from make_inputs import WORLDS

    d = np.load(path)
    for world in ("inv_cell", "inv_base"):
        h3 = WORLDS[world]["candidate"][2]
        steps = [*WORLDS[world]["candidate"], h3 / 2, h3 / 4]
        best = (1.0, None)
        for key in d.files:
            if not key.startswith(world + "/") or "/path/" not in key:
                continue
            for t in d[key][:, 0]:
                for h in steps:
                    for kind, x in (("grid", t / h), ("stage middle", t / h - 0.5)):
                        r = abs(x - round(x))
                        if r < best[0]:
                            best = (r, f"{key} at {t!r} s beside a {kind} of {h!r} s")
        print(f"{world}: the closest event is {best[0]:.3e} of a step away, {best[1]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "all", "look", "near"))
    parser.add_argument("path")
    parser.add_argument("--rate", choices=RATES)
    parser.add_argument("--factor", type=float, default=1.0)
    a = parser.parse_args()
    if a.action == "run":
        run(a.path, a.rate, a.factor)
    elif a.action == "all":
        run_all(a.path)
    elif a.action == "near":
        near(a.path)
    else:
        look(a.path)
