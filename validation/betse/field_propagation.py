#!/usr/bin/env python3
"""Cells' exterior field carried into the BETSE-order emulator's membranes (cell-ion terms).

The parity tolerance method (PROGRESS.md, P2 attribution, "Method for later rungs")
measures every cell-ion field term by propagation through the reference emulator
(validation/betse/emulator), not by a heuristic or an absolute cutoff. This tool runs
the emulator with its membrane processes seeing a Cells run's own exterior potential phi
(that run's comparison layout, ``diag_extracellular_potential_time``):

  base       no field input: the plain emulator, by the same code path
  boltzmann  each membrane's outside concentrations times exp(-z F (phi_site - <phi>) / RT),
             <phi> the mean over interior grid sites (the Boltzmann response of the
             exterior field, carried dynamically into the cells)
  vpatch     each membrane's voltage shifted by -(phi_site - <phi>_cell), <phi>_cell the
             area-weighted mean over the cell's membranes (Cells' patch voltage against
             the cell's charge voltage)
  both       both at once

Only what the leaks, pumps and channels (and channel gates) see changes
(emulator/spatial.MembraneInputs); junctions, junction gates, the ECM update and the
recorded observables are the emulator's own. phi is held piecewise constant over each
BETSE update: the latest Cells sample at or before the update's start (the first
update uses the first sample). The factors use Cells' F and R. A term is the
difference of two such runs, e.g. base against boltzmann, written by ``budget`` as
difference-budget pairs that validation/betse/protocol_tolerances.py reads
({"budget": FILE, "pairs": [NAME]}).

Landed from the one-off P2 attribution script (parity-rung2-4-20261109-04/
field_attribution.py), generalised: any runner (``default``: default_world_adapter's
emulator; ``network``: network_world_adapter's general-network channels), dt factor,
constants, model differences and SIM start. Validation tooling; no Cells engine model.

    PYTHONPATH=SRC/src:SRC python3 -B validation/betse/field_propagation.py run \\
        --case CASE --protocol P.json --cells-layout CELLS_RUN/layout --mode boltzmann \\
        [--runner default|network] [--dt-factor 10] [--constants betse] \\
        [--sim-start chained] [--model-difference NAME] --out DIR
    ... budget --case CASE [--runner R] --pair NAME BASE OTHER ... --out FILE.json
"""

import argparse
import json
import resource
import sys
import time
from pathlib import Path
from typing import NamedTuple

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    for entry in (ROOT / "src", ROOT):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))

from validation.betse import betse_reference_run as reference_run  # noqa: E402
from validation.betse import default_world_adapter as adapter  # noqa: E402

PHASES = adapter.PHASES
MODES = {"base": (False, False), "boltzmann": (True, False), "vpatch": (False, True)}
MODES["both"] = (True, True)
EXECUTED = (
    "validation/betse/field_propagation.py",
    "validation/betse/network_world_adapter.py",
    "validation/betse/emulator/network.py",
)


class Runner(NamedTuple):
    """One emulator route: world, phase inputs, one update, observables, chained end.

    world(case, *, blind)                        -> world (default_world_adapter keys)
    inputs(world, phase, start, variant)         -> (state, layout, ko_env)
    split(layout) / join(traced, static)         -> layout without / with its static parts
    drive(world, phase, inputs)                  -> per-sample step inputs [steps, ...] (or
                                                    None) from MembraneInputs (or None)
    step(state, layout, dt, drive, variant)      -> (state, valid); drive is this sample's
                                                    slice of drive() (MembraneInputs or None
                                                    for the default and network runners)
    observe(state, layout, variant)              -> (vm, cell_mM, env_mM, v_env, gate_open)
    end(state)                                   -> chained SIM start (phase_start keys)
    """

    world: object
    inputs: object
    split: object
    join: object
    drive: object
    step: object
    observe: object
    end: object
    executed: tuple


def _ones_control(m):
    """Every pump, channel and junction fully available (as the adapters' constant runs)."""
    import jax.numpy as jnp

    from validation.betse.emulator import junction

    return junction.Control(*(jnp.ones(m) for _ in junction.Control._fields))


def _default_runner():
    from validation.betse.emulator import junction, spatial

    def step(state, layout, dt, drive, variant):
        control = _ones_control(layout.junction_block.size)
        new, _, valid = junction.step(
            state, layout, dt, control, variant=variant, membrane_inputs=drive
        )
        return new, valid

    def observe(state, layout, variant):
        t = state.active.tissue
        f = spatial.field(t, layout.active.tissue, variant=variant)
        return (
            f.membrane_voltage_V,
            t.cell_concentration,
            t.outside_concentration,
            f.outside_potential_V.reshape(-1),
            state.junction_open,
        )

    def end(state):
        t = state.active.tissue
        return {
            "cell_mM": np.asarray(t.cell_concentration),
            "membrane_mM": np.asarray(t.membrane_concentration),
            "env_mM": np.asarray(t.outside_concentration),
            "gate_open": np.asarray(state.junction_open),
        }

    return Runner(
        adapter.betse_world,
        adapter.emulator_inputs,
        lambda layout: (layout, None),
        lambda traced, static: traced,
        lambda world, phase, inputs: inputs,
        step,
        observe,
        end,
        adapter.EXECUTED,
    )


def _network_runner():
    from validation.betse import network_world_adapter as net
    from validation.betse.emulator import network, spatial

    def inputs(world, phase, start, variant):
        state, layout, ko, _ = net.network_inputs(world, phase, start, variant)
        return state, layout, ko

    def step(state, layout, dt, drive, variant):
        control = _ones_control(layout.junction.junction_block.size)
        new, _, valid = network.step(
            state, layout, dt, control, variant=variant, membrane_inputs=drive
        )
        return new, valid

    def observe(state, layout, variant):
        t = state.junction.active.tissue
        f = spatial.field(t, layout.junction.active.tissue, variant=variant)
        return (
            f.membrane_voltage_V,
            t.cell_concentration,
            t.outside_concentration,
            f.outside_potential_V.reshape(-1),
            state.junction.junction_open,
        )

    def end(state):
        t = state.junction.active.tissue
        return {
            "cell_mM": np.asarray(t.cell_concentration),
            "membrane_mM": np.asarray(t.membrane_concentration),
            "env_mM": np.asarray(t.outside_concentration),
            "gate_open": np.asarray(state.junction.junction_open),
            "channel_gates": np.asarray(state.gates),
        }

    return Runner(
        net.network_world,
        inputs,
        lambda layout: (layout._replace(kinds=None, ion=None), (layout.kinds, layout.ion)),
        lambda traced, static: traced._replace(kinds=static[0], ion=static[1]),
        lambda world, phase, inputs: inputs,
        step,
        observe,
        end,
        adapter.EXECUTED + net.EXECUTED,
    )


RUNNERS = {"default": _default_runner, "network": _network_runner}


def runner(name):
    if name not in RUNNERS:
        raise adapter.AdapterError(f"unknown runner {name!r}; one of {sorted(RUNNERS)}")
    return RUNNERS[name]()


def interior_mask(world):
    rows, cols = world["grid_shape"]
    k = np.arange(rows * cols)
    return ~((k // cols == 0) | (k % cols == 0) | (k // cols == rows - 1) | (k % cols == cols - 1))


def field_inputs(world, phase, cells_layout, *, boltzmann, vpatch):
    """Per BETSE update of ``phase``: MembraneInputs (scale [U, s, m], shift [U, m]) and stats.

    Built from the Cells layout's diag_extracellular_potential_time; the layout must be of
    the same BETSE geometry. Update u spans [u dt, (u + 1) dt) and takes the latest Cells
    sample at or before u dt (the first sample for the earliest updates).
    """
    from cells.processes.electrochemistry import F, R
    from validation.betse.emulator import spatial

    directory = Path(cells_layout)
    manifest = json.loads((directory / adapter.compare.LAYOUT_MANIFEST).read_text())
    if manifest["betse_geometry_sha256"] != world["geometry_sha256"]:
        raise adapter.AdapterError("the Cells layout was built on a different BETSE geometry")
    times = np.asarray(manifest["phases"][phase]["elapsed_after_update_s"], dtype=np.float64)
    with np.load(directory / f"{phase}_history.npz") as data:
        phi = np.asarray(data["diag_extracellular_potential_time"], dtype=np.float64)
    if phi.shape != (times.size, int(np.prod(world["grid_shape"]))):
        raise adapter.AdapterError("Cells exterior potentials are not [samples, grid sites]")
    dt, updates = world["dt_s"][phase], world["steps"][phase]
    starts = np.arange(updates) * dt
    pick = np.maximum(0, np.searchsorted(times, starts + 1e-12) - 1)
    site, owner, area = world["membrane_site"], world["membrane_cell"], world["membrane_area_m2"]
    z = np.asarray(world["valence"], dtype=np.float64)[None, :, None]
    p = phi[pick]  # [U, sites]
    interior = interior_mask(world)
    relative = p[:, site] - p[:, interior].mean(axis=1, keepdims=True)  # [U, m]
    if boltzmann:
        scale = np.exp(-z * F * relative[:, None, :] / (R * world["temperature_K"]))
    else:
        scale = np.ones((updates, z.size, site.size))
    n = world["cell_volume_m3"].size
    weights = np.bincount(owner, area, minlength=n)
    cell_mean = np.stack([np.bincount(owner, area * row, minlength=n) for row in p[:, site]])
    cell_mean = cell_mean / weights
    shift = -(p[:, site] - cell_mean[:, owner]) if vpatch else np.zeros((updates, site.size))
    stats = {
        "cells_samples": int(times.size),
        "updates": int(updates),
        "first_update_sample": int(pick[0]),
        "max_abs_site_minus_interior_mean_V": float(np.abs(relative).max()),
        "outside_scale_range": [float(scale.min()), float(scale.max())],
        "max_abs_voltage_shift_V": float(np.abs(shift).max()),
    }
    return spatial.MembraneInputs(scale, shift), stats


def driven_phase(route, state, layout, dt, steps, substeps, drive, variant, device):
    """``steps`` samples of ``substeps`` updates of dt each; drive[k] feeds sample k's updates.

    ``drive`` is a pytree of [steps, ...] arrays or None (the plain emulator).
    """
    import jax
    import jax.numpy as jnp

    traced, static = route.split(layout)

    def run(state, traced, dt, drive):
        layout = route.join(traced, static)

        def update(carry, x):
            old, ok = carry
            new, valid = route.step(old, layout, dt, x, variant)
            ok = ok & valid
            return jax.tree.map(lambda a, b: jnp.where(ok, a, b), new, old), ok

        def one(carry, x):
            if substeps == 1:
                new, ok = update(carry, x)
            else:
                new, ok = jax.lax.fori_loop(0, substeps, lambda _, c: update(c, x), carry)
            return (new, ok), (*route.observe(new, layout, variant), ok)

        return jax.lax.scan(one, (state, jnp.asarray(True)), drive, length=steps)

    compiled = jax.jit(run)
    args = jax.device_put((state, traced, jnp.asarray(dt), drive), device)
    started = time.perf_counter()
    (final, ok), history = jax.block_until_ready(compiled(*args))
    wall = time.perf_counter() - started
    history = [np.asarray(v) for v in history]
    accepted = history[-1]
    return {
        "valid": bool(ok),
        "accepted_samples": int(accepted.sum()),
        "first_rejected_sample": None if accepted.all() else int(np.argmin(accepted)) + 1,
        "wall_s_including_compile": wall,
        "vm": history[0],
        "cell_mM": history[1],
        "env_mM": history[2],
        "v_env": history[3],
        "gate_open": history[4],
        "end": route.end(final),
    }


def run_propagation(
    case,
    protocol_path,
    cells_layout,
    out,
    *,
    mode,
    runner_name="default",
    constants="betse",
    device_kind="cpu",
    sim_start="chained",
    dt_factor=1,
    differences=(),
):
    import jax

    jax.config.update("jax_enable_x64", True)
    from validation.betse.emulator import laws

    if mode not in MODES:
        raise adapter.AdapterError(f"unknown mode {mode!r}; one of {sorted(MODES)}")
    boltzmann, vpatch = MODES[mode]
    route = runner(runner_name)
    protocol, protocol_sha = adapter.compare.load_protocol(protocol_path)
    world = route.world(case, blind=False)
    variant = laws.default_world(constants, tuple(differences))
    device = jax.devices(device_kind)[0]
    phases, records, chained = {}, {}, None
    for phase in PHASES:
        start = adapter.phase_start(world, phase, sim_start, chained)
        state, layout, ko = route.inputs(world, phase, start, variant)
        dt, steps = world["dt_s"][phase], world["steps"][phase]
        inputs, stats = None, None
        if mode != "base":
            inputs, stats = field_inputs(
                world, phase, cells_layout, boltzmann=boltzmann, vpatch=vpatch
            )
        drive = route.drive(world, phase, inputs)
        result = driven_phase(
            route, state, layout, dt / dt_factor, steps, dt_factor, drive, variant, device
        )
        chained = result["end"]
        records[phase] = {
            "dt_s": dt / dt_factor,
            "dt_factor": dt_factor,
            "updates": steps * dt_factor,
            "valid": result["valid"],
            "accepted_samples": result["accepted_samples"],
            "first_rejected_sample": result["first_rejected_sample"],
            "wall_s_including_compile": result["wall_s_including_compile"],
            "start": "configured cell/env concentrations" if phase == "init" else sim_start,
            "field_inputs": stats,
            "ko_env_per_m": ko,
        }
        elapsed = [(k + 1) * dt for k in range(steps)]  # BETSE sample k: after k + 1 of its dt
        phases[phase] = adapter.layout_phase(
            world, elapsed, result["vm"], result["cell_mM"], result["env_mM"], result["v_env"]
        )
        if not result["valid"]:
            break
    record = {
        "kind": "cells.field_propagation_run@1",
        "created_utc": reference_run.utc_now(),
        "backend": "emulator",
        "model": "validation/betse/emulator (BETSE-order kernel, not an engine model)",
        "runner": runner_name,
        "mode": mode,
        "boltzmann_outside_scale": boltzmann,
        "patch_voltage_shift": vpatch,
        "cells_layout": None if mode == "base" else str(Path(cells_layout).resolve()),
        "variant": variant._asdict() | {"field_mode": mode},
        "constants": constants,
        "model_differences": list(differences),
        "dt_factor": dt_factor,
        "device": str(device),
        "jax": jax.__version__,
        "sim_start": sim_start,
        "case": world["case"],
        "betse_extract": world["extract"],
        "protocol": {
            "path": str(Path(protocol_path).resolve()),
            "sha256": protocol_sha,
            "id": protocol.get("id"),
        },
        "phases": records,
        "valid": all(r["valid"] for r in records.values()) and len(records) == len(PHASES),
        "max_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    }
    record = adapter.provenance(record, route.executed + EXECUTED)
    out = reference_run.resolve_out(out)
    if record["valid"]:
        adapter.compare.write_layout(
            out,
            phases,
            protocol_sha256=protocol_sha,
            betse_geometry_sha256=world["geometry_sha256"],
            provenance=record,
        )
    else:
        out.mkdir(parents=True, exist_ok=False)
    reference_run.write_json(out / "run.json", adapter.compare.json_safe(record))
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="emulator run whose membranes see a Cells exterior field")
    run.add_argument("--case", required=True)
    run.add_argument("--protocol", required=True)
    run.add_argument("--cells-layout", help="Cells comparison layout (not needed for base)")
    run.add_argument("--mode", choices=sorted(MODES), required=True)
    run.add_argument("--runner", choices=sorted(RUNNERS), default="default")
    run.add_argument("--constants", choices=("betse", "codata"), default="betse")
    run.add_argument("--device", choices=("cpu", "gpu"), default="cpu")
    run.add_argument("--sim-start", choices=("betse", "chained"), default="chained")
    run.add_argument("--dt-factor", type=int, default=1)
    run.add_argument("--model-difference", action="append", default=[])
    run.add_argument("--out", required=True)
    budget = sub.add_parser("budget", help="difference-budget pairs of propagation runs")
    budget.add_argument("--case", required=True, help="BETSE case (inputs only)")
    budget.add_argument("--runner", choices=sorted(RUNNERS), default="default")
    budget.add_argument(
        "--pair", nargs=3, action="append", required=True, metavar=("NAME", "BASE", "OTHER")
    )
    budget.add_argument("--out", required=True, help="fresh JSON file")
    args = parser.parse_args(argv)
    if args.command == "budget":
        route = runner(args.runner)
        world = route.world(args.case, blind=True)
        result = adapter.difference_budget(world, args.pair, route.executed + EXECUTED)
        out = reference_run.resolve_out(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        reference_run.write_json(out, adapter.compare.json_safe(result))
        print(json.dumps({"out": str(out), "pairs": list(result["pairs"])}, indent=2))
        return 0
    if args.mode != "base" and not args.cells_layout:
        parser.error("--cells-layout is required unless --mode base")
    record = run_propagation(
        args.case,
        args.protocol,
        args.cells_layout,
        args.out,
        mode=args.mode,
        runner_name=args.runner,
        constants=args.constants,
        device_kind=args.device,
        sim_start=args.sim_start,
        dt_factor=args.dt_factor,
        differences=tuple(args.model_difference),
    )
    summary = {k: record[k] for k in ("valid", "mode", "runner", "dt_factor", "sim_start")}
    summary["phases"] = {
        p: {k: r[k] for k in ("valid", "wall_s_including_compile", "field_inputs")}
        for p, r in record["phases"].items()
    }
    print(json.dumps(adapter.compare.json_safe(summary), indent=2))
    return 0 if record["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
