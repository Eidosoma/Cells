"""The engine's plants (the sheet's §5.4 and §5.2; G4): each an exact edit of a world or of the
operator's motion, run as engine_run.py runs a world and compared with G2's unplanted references
(compare.py), to show which judged item it fails. Development, not judged.

Edits of the definition:
- A1-1, a wrong stage count: m_tx = 6;
- A1-2, a wrong speed: v_tx = 40;
- A1-5, u squared on transcription's initiation: the regulator's coupling declared twice, so its
  factor multiplies the rate twice (B1′ multiplies its routes' factors in declared order).

Edits of the motion, made in the running process only, never in src (validation's planted failures,
each replacing one module function of cells.operator.templated_polymerisation@1 before the world is compiled):
- A1-3, a dropped fuel term: translation's stage exits move no ATP, ADP or Pi; its laws, phi_tl and
  x_tl, are unchanged;
- A1-4 and A1-M-2, a machine not returned: a release returns no machine to the pool (A1's
  transcription; every A1-M world's chain);
- A1-6, a wrong amino-acid entry: each translation stage exit draws 49 amino acids, not 50;
- A1-M-1, initiation reads the total machines: J_I = lambda M_q, at T = 5.

Each plant runs in its own process (a compiled program is cached per process, so an unplanted one
must never be reused), and writes engine_run.py's record, or the engine's refusal, into
`<out>/<plant>/`.

Run: PYTHONPATH=src:. JAX_ENABLE_X64=1 python -m validation.gene_regulation.plants --plant NAME
[--dt S] --out DIR, or --plant all to run each in a child process.
"""

import argparse
import copy
import json
import subprocess
import sys
import traceback
from pathlib import Path

import numpy as np

from cells.operators import templated_polymerisation as tp
from validation.gene_regulation import engine_run, worlds

FUEL = ("ATP", "ADP", "Pi")
COUPLING_LAWS = (
    "cells.operator.species_regulated_availability@1",
    "cells.operator.species_regulated_availability@2",
)


def _block(raw):
    (block,) = [o for o in raw["model"]["operators"] if o["law"] == worlds.POLYMERISATION]
    return block


def _chain(raw, route):
    (chain,) = [c for c in _block(raw)["chains"] if c["id"] == route]
    return chain


_ROWS = [None]  # The operator's listed rows, in order, set by plant() before the compile.


def _motion(edit):
    """Replace tp.changes by one that moves rows by an edited copy of the layout's motion."""
    original = tp.changes

    def planted(j_init, j_stage, j_deg, j_tr, p, *, xp):
        return original(j_init, j_stage, j_deg, j_tr, edit(p), xp=xp)

    tp.changes = planted


def _not_returned(routes):
    """Replace tp.changes by one whose releases return no machine on the chains `routes`."""
    original = tp.changes

    def planted(j_init, j_stage, j_deg, j_tr, p, *, xp):
        dn, d_free, d_complexes, produced, consumed = original(
            j_init, j_stage, j_deg, j_tr, p, xp=xp
        )
        released = xp.sum(xp.where(p.poly_chain_last, j_stage, 0.0), axis=1)
        mask = xp.asarray([1.0 if c in routes else 0.0 for c in _CHAINS[0]])
        return dn, d_free - (mask * released) @ p.poly_chain_pool, d_complexes, produced, consumed

    tp.changes = planted


_CHAINS = [()]


def _total_machines():
    """Replace tp.fluxes by one whose initiation reads the pool's total machines."""
    original = tp.fluxes

    def planted(n, free, complexes, controls, p, volume, *, xp):
        return original(n, p.poly_pool_total_fmol + 0 * free, complexes, controls, p, volume, xp=xp)

    tp.fluxes = planted


def _column(p, field, chain, rows, factor):
    """p with `field`[chain, row] multiplied by `factor` for each listed row."""
    value = np.array(getattr(p, field), copy=True) if not hasattr(
        getattr(p, field), "at") else getattr(p, field)  # fmt: skip
    listed = _ROWS[0]
    for row in rows:
        k = listed.index(row)
        if hasattr(value, "at"):
            value = value.at[chain, k].multiply(factor)
        else:
            value[chain, k] *= factor
    return p._replace(**{field: value})


def plant(name, dt=0.5):
    """(world name, raw definition) of a plant, with its process-local edit applied."""
    if name == "A1-1":
        raw = worlds.world("A1", dt=dt)
        _chain(raw, "tx")["stages"] = 6
        return "A1", raw
    if name == "A1-2":
        raw = worlds.world("A1", dt=dt)
        _chain(raw, "tx")["speed_per_s"] = 40.0
        return "A1", raw
    if name == "A1-5":
        raw = worlds.world("A1", dt=dt)
        (coupling,) = [o for o in raw["model"]["operators"] if o["law"] in COUPLING_LAWS]
        twice = copy.deepcopy(coupling["couplings"][0])
        twice["id"] = f"{twice['id']}_twice"
        coupling["couplings"].append(twice)
        raw["experiment"]["coupling_controls"].append(
            dict(coupling_id=twice["id"], schedule=[dict(time=0.0, enabled=1)])
        )
        return "A1", raw
    world = {"A1-3": "A1", "A1-4": "A1", "A1-6": "A1", "A1-M-1": "pol T=5"}.get(name)
    if name.startswith("A1-M-2 "):
        world = name.removeprefix("A1-M-2 ")
    if world is None:
        raise ValueError(f"unknown plant {name!r}")
    raw = worlds.world(world, dt=dt)
    block = _block(raw)
    _ROWS[0] = [s["id"] for s in block["species"]]
    _CHAINS[0] = tuple(c["id"] for c in block["chains"])
    tl = _CHAINS[0].index("tl") if "tl" in _CHAINS[0] else None
    if name == "A1-3":
        _motion(lambda p: _column(_column(p, "poly_chain_draws", tl, ["ATP"], 0.0),
                                  "poly_chain_releases", tl, ["ADP", "Pi"], 0.0))  # fmt: skip
    elif name == "A1-4":
        _not_returned(("tx",))
    elif name == "A1-6":
        _motion(lambda p: _column(p, "poly_chain_draws", tl, ["A"], 49.0 / 50.0))
    elif name == "A1-M-1":
        _total_machines()
    else:
        _not_returned(_CHAINS[0])
    return world, raw


def names():
    return ["A1-1", "A1-2", "A1-3", "A1-4", "A1-5", "A1-6", "A1-M-1"] + [
        f"A1-M-2 {w}" for w in worlds.names() if w != "A1"
    ]


def run_one(name, dt, out):
    """One plant in this process: engine_run.py's record, or the refusal, each with the source's
    identity (engine_run.provenance: untracked source is frozen into the plant's folder)."""
    folder = out / engine_run.slug(name)
    folder.mkdir(parents=True, exist_ok=False)
    source, patch = engine_run.provenance(folder)
    if patch is not None:
        (folder / "checkout.patch").write_text(patch)
    world, raw = plant(name, dt)
    symbols = worlds.test_instance()
    try:
        from cells.definitions.specs import parse_spec

        spec = parse_spec(raw)
        states = engine_run.collect(spec)
        times, values, checks = engine_run.readouts(spec, states)
        record = dict(
            kind="cells.gene_regulation.engine_run@1",
            plant=name,
            world=world,
            cell=checks["exported_cell"],
            set="test instance",
            symbols_RT={k: str(v) for k, v in symbols.items()},
            dt_s=dt,
            t=times,
            readouts=values,
            checks=checks,
            refused=None,
        )
    except Exception as error:  # A refusal is the plant's outcome, recorded whole.
        record = dict(plant=name, world=world, refused=f"{type(error).__name__}: {error}",
                      traceback=traceback.format_exc()[-4000:])  # fmt: skip
    record.update(engine_run.late_sources(folder, source))
    (folder / "plant.json").write_text(json.dumps(record, indent=1, default=float) + "\n")
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plant", required=True)
    parser.add_argument("--dt", type=float, default=0.5)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    if args.plant != "all":
        record = run_one(args.plant, args.dt, out)
        print(json.dumps({"plant": args.plant, "refused": record["refused"]}), flush=True)
        return 0
    out.mkdir(parents=True, exist_ok=False)
    source, patch = engine_run.provenance(out)
    if patch is not None:
        (out / "checkout.patch").write_text(patch)
    (out / "run_record.json").write_text(json.dumps(dict(source, dt_s=args.dt), indent=1) + "\n")
    for name in names():
        subprocess.run([sys.executable, "-m", "validation.gene_regulation.plants", "--plant", name,
                        "--dt", str(args.dt), "--out", str(out)], check=False)  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
