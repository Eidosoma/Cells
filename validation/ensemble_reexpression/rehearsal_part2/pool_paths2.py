"""The two invented pools of the clusters run alone, by the frozen snapshot's own pool code.

    PYTHONPATH=SNAPSHOT/src:SNAPSHOT pool_paths2.py run OUT.npz    every pool of every seed index
    pool_paths2.py look OUT.npz                                    every path, in short
    pool_paths2.py near OUT.npz    the distance of every event from every grid point and stage
                                   middle of the clusters' four steps

The four clusters hold the same two pools (as the registered ones hold base's), so a pool is named
once, under `inv_pools`. The reader of the definition, the event recorder and the availability are
Part 1's (`../rehearsal/pool_paths.py`).
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "rehearsal"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_inputs as first  # noqa: E402
import make_inputs2 as m  # noqa: E402
from pool_paths import availability, definition, run_pool  # noqa: E402


def entries():
    pools = next(iter(m.CLUSTERS.values()))["pools"]
    for cell, e in pools.items():
        block = dict(pool=first.pool_block(dict(pools=pools), cell), seeds=e["seeds"])
        for s in range(m.SEEDS):
            yield cell, s, block


def run(path):
    saved = {}
    for cell, s, block in entries():
        _, state, events, _ = run_pool(definition(block, s))
        key = f"{m.PATHS_UNDER}/{cell}/s{s}"
        for name, value in state._asdict().items():
            saved[f"{key}/final/{name}"] = np.asarray(value)
        for k, rows in enumerate(events):
            saved[f"{key}/path/{k}"] = np.array(
                [(t, availability(a, b)) for t, a, b in rows], dtype=np.float64
            ).reshape(-1, 2)
        print(key, [len(e) for e in events], int(np.asarray(state.event_count).sum()))
    np.savez_compressed(path, **saved)


def paths(npz):
    d = np.load(npz)
    return {k: d[k] for k in sorted(d.files) if "/path/" in k}


def look(npz):
    for key, p in paths(npz).items():
        flips = sum(1 for i in range(len(p)) if p[i, 1] != (p[i - 1, 1] if i else 1.0))
        print(key, "events", len(p), "changes", flips, [f"{t:.6f}:{int(a)}" for t, a in p[:6]])


def near(npz):
    """The smallest distance of an event from a grid point or a step's middle, as a share of a
    step, over the four steps of the clusters (PART2.md section 4.1)."""
    best = (1.0, None)
    steps = {h for c in m.CLUSTERS.values() for h in (*m.WORLDS[c["child"]]["candidate"],
                                                      m.retry_step(c["child"]))}  # fmt: skip
    for key, p in paths(npz).items():
        for t in p[:, 0]:
            for h in sorted(steps):
                for kind, x in (("grid point", t / h), ("step's middle", t / h - 0.5)):
                    r = abs(x - round(x))
                    if r < best[0]:
                        best = (r, f"{key} at {t!r} s beside a {kind} of {h!r} s")
    print(f"steps {sorted(steps)}: the closest event is {best[0]:.3e} of a step away, {best[1]}")


if __name__ == "__main__":
    dict(run=run, look=look, near=near)[sys.argv[1]](sys.argv[2])
