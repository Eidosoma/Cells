#!/usr/bin/env python3
"""BETSE's default world with scheduled interventions (parity rung P3), for the emulator and Cells.

``event_world`` reads a plain-BETSE case with ``default_world_adapter.betse_world(events=True)``
and adds its SIM events, from BETSE's own parameters (``global_options``,
``scheduled_options``, ``mem_perms``) and the case's target record
(``inputs/event_targets.json``: tissue profile -> cell indices, written by ``prepare-case``
and checked against the prepared YAML). BETSE fires events in SIM only, at update k's label
t_k = k N dt / (N - 1), and holds the value for that update (emulator/events.py). Mapped
(the correspondence map, parity-p3-interventions-20261110-01/map, accepted by the lead):

* block NaKATP pump (global): Na/K pump availability 1 - pulse(t_k) on every membrane;
* block gap junctions (global, ``random fraction`` 100 only: BETSE targets the first
  fraction of membranes by index, and only 100% blocks both members of every pair);
* change Na / K mem on tissue profiles: additive, Dm = Dm_base + mult pulse(t_k) Dm_default,
  Dm_default the default profile's (``mem_perms``); mult >= 0, modulator function None.
  Change Cl / Ca mem map in the emulator only (Cells has no Cl or Ca leak law).

Everything else (env, temperature, ECM junctions, pressure, external voltage, cutting) is
refused. Backends:

* emulator (``run-emulator``): emulator/events.py, BETSE's order and its event values. One
  process runs INIT once (events never fire there; the cases' INIT inputs must be
  identical) and SIM for each case. ``--event-clock nominal`` evaluates pulse at k dt instead
  of BETSE's label, and ``--event-shift S`` applies update k's value at update k + S: the
  event-timing term and its sensitivity.
* resolved (``run-resolved``): Cells' own resolved_pump_tissue@3, default_world_adapter's
  @2 definition plus, per change-mem event, one leak population per target patch
  (naleak_always_open@1 / kleak_always_open@1, max_permeability mult Dm_default / tm,
  abundance 1) whose channel availability is BETSE's applied pulse; pump and junction
  availabilities are 1 - BETSE's value. Every control changes only at BETSE update
  boundaries, at integer multiples of the Cells dt (BETSE's values, not its nominal clock:
  the timing term is zero by construction). A junction block must be a full step held to
  the end of SIM (BETSE blocks the stored gate, Cells the conductance; they agree only
  then). INIT runs once, SIM per case, as for the emulator; window-end readouts use the
  window-end control.

    VENV_BETSE ... ; python3 validation/betse/event_world_adapter.py prepare-case \\
        --spec SPEC.json --out CASE_DIR          (BETSE config + target record + seed)
    PYTHONPATH=SRC/src:SRC python3 -B validation/betse/event_world_adapter.py run-emulator \\
        --case CASE [--case CASE2 ...] --protocol P.json --out DIR [--dt-factor F]
        [--sim-start chained] [--constants codata] [--model-difference NAME]
        [--event-clock nominal] [--event-shift S]
    ... run-resolved --case CASE [--case ...] [--protocol P.json ...] --dt-init 1e-3
        --dt-sim 1e-4 --field-solver capacitive_reduction_gauged_damped_newton@3 --out DIR
    ... difference-budget --case CASE --pair NAME BASE OTHER ... --out FILE.json

An event's own effect (plain BETSE with the event against plain BETSE without it, the
discrimination numerator) is validation/betse/betse_pair_terms.py.
"""

import argparse
import copy
import json
import math
import resource
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    for entry in (ROOT / "src", ROOT):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))

from validation.betse import betse_reference_run as reference_run  # noqa: E402
from validation.betse import default_world_adapter as adapter  # noqa: E402

PHASES = adapter.PHASES
EXECUTED = (
    "validation/betse/event_world_adapter.py",
    "validation/betse/emulator/events.py",
    "validation/betse/field_propagation.py",
)
TARGETS_FILE = "event_targets.json"
TARGETS_KIND = "cells.betse_event_targets@1"
GLOBAL_MAPPED = {"NaKATP_block": "pump_block", "gj_block": "junction_block"}
MEMBRANE_EVENTS = {"Na_mem": "Na", "K_mem": "K", "Cl_mem": "Cl", "Ca_mem": "Ca"}
RESOLVED_LEAKS = {"Na": "naleak_always_open@1", "K": "kleak_always_open@1"}
RESOLVED_MODEL_ID = "resolved_pump_tissue@3"
CLOCKS = ("betse", "nominal")


class EventError(adapter.AdapterError):
    """The case's events are outside what this adapter maps; nothing is run."""


# ............................................................ case preparation


def disc_cells(centres, count):
    """The ``count`` cells nearest the centroid of all cell centres (ties by index)."""
    centres = np.asarray(centres, dtype=np.float64)
    distance = np.hypot(*(centres - centres.mean(axis=0)).T)
    return sorted(int(i) for i in np.lexsort((np.arange(len(centres)), distance))[:count])


def aligned_time(update, steps, dt):
    """A BETSE event time between labels update - 1 and update (midpoint): a sharp pulse
    edge there takes effect exactly from that update. ``update`` == steps is past the end."""
    if not 0 < update <= steps:
        raise EventError("an aligned event update must lie in 1..steps")
    grid = np.linspace(0, steps * dt, steps)
    if update == steps:
        return float(grid[-1] + 0.5 * (grid[1] - grid[0]))
    return float(0.5 * (grid[update - 1] + grid[update]))


def _block(text, header):
    """The YAML block starting at the line ``header`` (unique) up to the next blank line."""
    start = text.find("\n" + header) + 1
    if start == 0 or text.count("\n" + header) != 1:
        raise EventError(f"YAML block {header!r} not found exactly once")
    end = text.find("\n\n", start)
    return text[start : len(text) if end < 0 else end]


def _set_values(block, values):
    """The block with ``key: value`` lines replaced (comments kept); every key must occur once."""
    lines = block.split("\n")
    for key, value in values.items():
        hits = [i for i, line in enumerate(lines) if line.strip().startswith(key + ":")]
        if len(hits) != 1:
            raise EventError(f"key {key!r} occurs {len(hits)} times in its YAML block")
        line = lines[hits[0]]
        indent = line[: len(line) - len(line.lstrip())]
        rest = line.lstrip()[len(key) + 1 :]
        comment = rest[rest.index("#") :] if "#" in rest else ""
        lines[hits[0]] = f"{indent}{key}: {value}" + (f"  {comment}" if comment else "")
    return "\n".join(lines)


EVENT_HEADERS = {
    "Na_mem": "change Na mem:",
    "K_mem": "change K mem:",
    "Cl_mem": "change Cl mem:",
    "NaKATP_block": "block NaKATP pump:",
    "gj_block": "block gap junctions:",
}
SPOT_TYPE = (
    "          type: image   # Cell population type as any following string:\n"
    '                        # * "all"'
)
SPOT_INDICES = (
    "          image: geo/circle/spot_3.png # Absolute or relative filename of this raster image.\n"
    "          indices: [3, 14, 15, 9, 265]"
)


def case_replacements(text, spec, steps, dt):
    """(old, new) YAML text pairs for ``spec`` and the derived event times (s)."""
    pairs, derived = [], {}
    spot = spec.get("spot_cells")
    if spot is not None:
        pairs.append((SPOT_TYPE, SPOT_TYPE.replace("type: image  ", "type: indices")))
        pairs.append((SPOT_INDICES, SPOT_INDICES.replace("[3, 14, 15, 9, 265]", json.dumps(spot))))
    for name, event in spec["events"].items():
        if name not in EVENT_HEADERS:
            raise EventError(f"event {name!r} is not prepared by this tool")
        on = aligned_time(int(event["on_update"]), steps, dt)
        off_update = event.get("off_update")
        off = (
            float(event["off_after_s"])
            if off_update is None
            else aligned_time(off_update, steps, dt)
        )
        values = {
            "event happens": "True",
            "change start": repr(on),
            "change finish": repr(off),
            "change rate": repr(float(event["change_rate_s"])),
        }
        if name in MEMBRANE_EVENTS:
            values["multiplier"] = repr(float(event["multiplier"]))
            values["apply to"] = json.dumps(list(event["apply_to"]))
        if name == "gj_block":
            values["random fraction"] = str(int(event["random_fraction"]))
        block = _block(text, EVENT_HEADERS[name])
        pairs.append((block, _set_values(block, values)))
        derived[name] = {"change_start_s": on, "change_finish_s": off, **values}
    return pairs, derived


def cmd_prepare_case(args):
    """BETSE config of one P3 case: prepare (exact single-occurrence replacements), the
    target record and the shared seed; the BETSE run itself is betse_reference_run.py run."""
    spec_path = Path(args.spec).resolve()
    spec = json.loads(spec_path.read_text())
    case = reference_run.resolve_out(args.out)
    if case.exists():
        raise SystemExit(f"Refusing existing case directory: {case}")
    base = Path(spec["base_config"])
    text = (base / "sim_config.yaml").read_text()
    sim = _block(text, "sim time settings:")
    steps, dt = int(spec["sim_steps"]), float(spec["sim_dt_s"])
    for needle in (f"time step: {spec['sim_dt_text']}", f"total time: {spec['sim_total_text']}"):
        if needle not in sim:
            raise SystemExit(f"base SIM settings do not contain {needle!r}")
    if not math.isclose(steps * dt, float(spec["sim_total_text"]), rel_tol=1e-12):
        raise SystemExit("sim_steps * sim_dt_s is not the configured SIM total time")
    if spec.get("spot_count"):
        with np.load(Path(spec["geometry"])) as g:
            spec["spot_cells"] = disc_cells(g["cell_centres"], int(spec["spot_count"]))
    pairs, derived = case_replacements(text, spec, steps, dt)
    command = [
        args.betse_python, "-I", str(ROOT / "validation/betse/betse_reference_run.py"), "prepare",
        "--base", str(base), "--out", str(case / "inputs" / "config"),
    ]  # fmt: skip
    for old, new in pairs:
        command += ["--replace", old, new]
    (case / "inputs").mkdir(parents=True)
    done = subprocess.run(command, capture_output=True, text=True)
    (case / "inputs" / "prepare.stdout.log").write_text(done.stdout)
    (case / "inputs" / "prepare.stderr.log").write_text(done.stderr)
    if done.returncode:
        raise SystemExit(f"prepare failed ({done.returncode}); see {case / 'inputs'}")
    seed = Path(spec["seed"])
    target = case / "inputs" / "config" / "INITS" / seed.name
    shutil.copyfile(seed, target)
    target.chmod(stat.S_IMODE(target.stat().st_mode) & ~0o222)
    record = {
        "kind": TARGETS_KIND,
        "created_utc": reference_run.utc_now(),
        "spec": str(spec_path),
        "spec_sha256": reference_run.sha256_file(spec_path),
        "profiles": {} if spec.get("spot_cells") is None else {"Spot": spec["spot_cells"]},
        "selection": spec.get("spot_selection"),
        "picker": "indices (BETSE tissue/picker TissuePickerIndices: the listed cells and all "
        "their membranes)",
        "sim_steps": steps,
        "sim_dt_s": dt,
        "events": derived,
        "seed": {"path": str(seed), "sha256": reference_run.sha256_file(seed)},
        "provenance": reference_run.git_provenance([Path(__file__)]),
    }
    reference_run.write_json(case / "inputs" / TARGETS_FILE, record)
    print(json.dumps({"case": str(case), "events": sorted(derived)}, indent=1))
    return 0


# ............................................................ world and events


def _targets(world):
    directory = Path(world["extract"]).parent / "inputs"
    path = directory / TARGETS_FILE
    if not path.is_file():
        raise EventError(f"no target record {path}")
    record = json.loads(path.read_text())
    if record.get("kind") != TARGETS_KIND:
        raise EventError(f"{path} is not a {TARGETS_KIND}")
    yaml = (directory / "config" / "sim_config.yaml").read_text()
    for name, cells in record["profiles"].items():
        if f"indices: {json.dumps(cells)}" not in yaml or "type: indices" not in yaml:
            raise EventError(f"profile {name}: cell list not found in the prepared YAML")
    return record, str(path)


def parse_events(world, params, profiles):
    """Mapped SIM events [(dict)] of BETSE's parameters; refuses anything unmapped."""
    species = world["species"]
    m = world["membrane_area_m2"].size
    events = []
    for group in ("global_options", "scheduled_options"):
        for name, value in sorted((params.get(group) or {}).items()):
            if value == 0:
                continue
            if name in GLOBAL_MAPPED:
                t_on, t_off, t_change = (float(v) for v in value[:3])
                row = {
                    "name": name,
                    "kind": GLOBAL_MAPPED[name],
                    "t_on_s": t_on,
                    "t_off_s": t_off,
                    "t_change_s": t_change,
                    "membranes": list(range(m)),
                }
                if name == "gj_block":
                    fraction = min(100, max(1, int(value[3])))
                    if fraction != 100:
                        raise EventError("only a 100% gap-junction block is mapped (reciprocal)")
                    row["random_fraction"] = fraction
                events.append(row)
            elif name in MEMBRANE_EVENTS:
                t_on, t_off, t_change, mult = (float(v) for v in value[:4])
                apply_to, function = value[4], value[5]
                ion = MEMBRANE_EVENTS[name]
                if ion not in species:
                    continue  # BETSE skips a change of an absent ion
                if function != "None":
                    raise EventError(f"{name}: modulator function {function!r} is not mapped")
                if not mult >= 0:
                    raise EventError(f"{name}: a negative multiplier (decrease) is not mapped")
                cells = set()
                for profile in apply_to:
                    if profile not in profiles:
                        raise EventError(f"{name}: profile {profile!r} has no target record")
                    cells |= set(profiles[profile])
                owner = world["membrane_cell"]
                events.append(
                    {
                        "name": name,
                        "kind": "membrane",
                        "ion": ion,
                        "species": species.index(ion),
                        "t_on_s": t_on,
                        "t_off_s": t_off,
                        "t_change_s": t_change,
                        "multiplier": mult,
                        "dm_default_m2_s": float(params["mem_perms"][ion]),
                        "profiles": list(apply_to),
                        "cells": sorted(cells),
                        "membranes": [
                            int(j) for j in np.flatnonzero(np.isin(owner, sorted(cells)))
                        ],
                    }
                )
            else:
                raise EventError(f"BETSE event {name!r} is not mapped (engine gap or unused)")
    return events


def event_world(case, *, blind=False):
    """default_world_adapter.betse_world(events=True) plus the case's mapped SIM events.

    A case with no event on (e.g. the no-event reference of the same world) needs no
    target record and maps to no events.
    """
    world = adapter.betse_world(case, blind=blind, events=True)
    directory, manifest = adapter._blind_case(case) if blind else adapter.load_case(case)
    params = {phase: adapter.betse_parameters(manifest, phase) for phase in PHASES}
    groups = ("global_options", "scheduled_options")
    if any(v != 0 for g in groups for v in (params["sim"].get(g) or {}).values()):
        record, path = _targets(world)
        for key in ("sim_steps", "sim_dt_s"):
            actual = world["steps"]["sim"] if key == "sim_steps" else world["dt_s"]["sim"]
            if record[key] != actual:
                raise EventError(f"target record {key} {record[key]} differs from BETSE's {actual}")
    else:
        record, path = {"profiles": {}}, None
    world["events"] = parse_events(world, params["sim"], record["profiles"])
    world["event_targets"] = {"path": path, "profiles": record["profiles"]}
    world["membrane_thickness_m"] = float(params["init"]["tm"])
    with np.load(directory / "init_final.npz") as final:
        world["membrane_dm_base_m2_s"] = np.asarray(final["Dm_cells"], dtype=np.float64)
    return world


def event_values(world, phase, *, clock="betse", shift=0):
    """[updates, events] values BETSE applies at each update of the phase (zeros in INIT).

    ``clock`` "betse" evaluates pulse at BETSE's label of the update, "nominal" at k dt;
    ``shift`` S applies update k's value at update k + S (the first S updates keep 0).
    """
    from validation.betse.emulator import events as ev

    if clock not in CLOCKS:
        raise EventError(f"unknown event clock {clock!r}")
    steps, dt = world["steps"][phase], world["dt_s"][phase]
    values = np.zeros((steps, len(world["events"])))
    if phase != "sim":
        return values
    t = ev.labels(steps, dt) if clock == "betse" else np.arange(steps) * dt
    for e, row in enumerate(world["events"]):
        values[:, e] = ev.pulse(t, row["t_on_s"], row["t_off_s"], row["t_change_s"])
    if shift:
        values = np.concatenate([np.zeros((shift, values.shape[1])), values[:-shift]])
    return values


def emulator_drive(world, phase, inputs=None, *, clock="betse", shift=0):
    """events.Drive [updates, ...] of the phase (BETSE's operation order), plus field inputs."""
    from validation.betse.emulator import events as ev

    values = event_values(world, phase, clock=clock, shift=shift)
    steps, m = values.shape[0], world["membrane_area_m2"].size
    base = world["membrane_dm_base_m2_s"]
    pump, junction = np.ones((steps, m)), np.ones((steps, m))
    scheduled = np.zeros((steps, *base.shape))
    for e, row in enumerate(world["events"]):
        targets = np.asarray(row["membranes"], dtype=np.int64)
        if row["kind"] == "pump_block":
            pump[:] = (1.0 - values[:, e])[:, None]  # sim.NaKATP_block, one scalar
        elif row["kind"] == "junction_block":
            junction[:, targets] = (1.0 - values[:, e])[:, None]
        else:  # Dm_scheduled[ion][targets] = mult * pulse * Dm_default
            scheduled[:, row["species"], targets] = (
                row["multiplier"] * values[:, e] * row["dm_default_m2_s"]
            )[:, None]
    permeability = (scheduled + base[None]) / world["membrane_thickness_m"]
    return ev.Drive(pump, junction, permeability, inputs)


def init_signature(world):
    """What INIT reads: equal signatures let cases share one INIT run."""
    keys = (
        "geometry_sha256", "valence", "cell_volume_m3", "membrane_area_m2", "temperature_K",
        "capacitance_F_m2", "junction_permeability_m_s", "env_diffusivity_m2_s",
        "boundary_concentration_mM", "pump_capacity_fmol_s", "initial_cell_mM",
        "initial_env_mM", "membrane_dm_base_m2_s",
    )  # fmt: skip
    value = {k: np.asarray(world[k]).tolist() if k != "geometry_sha256" else world[k] for k in keys}
    value["init_permeability"] = np.asarray(world["membrane_permeability_m_s"]["init"]).tolist()
    value["dt_steps"] = [world["dt_s"]["init"], world["steps"]["init"]]
    pump = world["calcium_pump"]
    value["calcium_pump"] = (
        None if pump is None else {k: np.asarray(v).tolist() for k, v in pump.items()}
    )
    return json.dumps(value, sort_keys=True)


def _shared_init(worlds):
    signatures = {init_signature(w) for w in worlds}
    if len(signatures) != 1:
        raise EventError("the cases' INIT inputs differ: they cannot share one INIT run")


def _case_name(world):
    return Path(world["extract"]).parent.name


# ............................................................ emulator backend


def _events_runner():
    """field_propagation.Runner for event cases (events.step; INIT drives are constant)."""
    from validation.betse import field_propagation as fp
    from validation.betse.emulator import events as ev

    base = fp.runner("default")

    def step(state, layout, dt, drive, variant):
        new, _, valid = ev.step(state, layout, dt, drive, variant=variant)
        return new, valid

    return base._replace(
        world=event_world,
        drive=lambda world, phase, inputs: emulator_drive(world, phase, inputs),
        step=step,
        executed=base.executed + EXECUTED,
    )


def run_event_emulator(
    cases,
    protocol_path,
    out,
    *,
    constants,
    device_kind,
    sim_start,
    dt_factor=1,
    differences=(),
    clock="betse",
    shift=0,
):
    """INIT once (shared), then SIM of every case; one comparison layout per case."""
    import jax

    jax.config.update("jax_enable_x64", True)
    from validation.betse import field_propagation as fp
    from validation.betse.emulator import laws

    route = _events_runner()
    route = route._replace(
        drive=lambda world, phase, inputs: emulator_drive(
            world, phase, inputs, clock=clock, shift=shift
        )
    )
    protocol, protocol_sha = adapter.compare.load_protocol(protocol_path)
    worlds = [event_world(case) for case in cases]
    _shared_init(worlds)
    variant = laws.default_world(constants, tuple(differences))
    device = jax.devices(device_kind)[0]
    out = reference_run.resolve_out(out)
    out.mkdir(parents=True, exist_ok=False)

    def phase_run(world, phase, start):
        state, layout, ko = route.inputs(world, phase, start, variant)
        dt, steps = world["dt_s"][phase], world["steps"][phase]
        drive = route.drive(world, phase, None)
        result = fp.driven_phase(
            route, state, layout, dt / dt_factor, steps, dt_factor, drive, variant, device
        )
        record = {
            "dt_s": dt / dt_factor,
            "dt_factor": dt_factor,
            "updates": steps * dt_factor,
            "valid": result["valid"],
            "accepted_samples": result["accepted_samples"],
            "first_rejected_sample": result["first_rejected_sample"],
            "wall_s_including_compile": result["wall_s_including_compile"],
            "ko_env_per_m": ko,
            "betse_ko_env_per_m": world["betse_ko_env"][phase],
            "gate_open_range": [float(result["gate_open"].min()), float(result["gate_open"].max())],
        }
        elapsed = [(k + 1) * dt for k in range(steps)]
        layout_phase = adapter.layout_phase(
            world, elapsed, result["vm"], result["cell_mM"], result["env_mM"], result["v_env"]
        )
        return result, record, layout_phase

    init_result, init_record, init_phase = phase_run(
        worlds[0], "init", adapter.phase_start(worlds[0], "init")
    )
    init_record["start"] = "configured cell/env concentrations, gates 1"
    init_record["shared_by"] = [_case_name(w) for w in worlds]
    records = {}
    for world in worlds:
        name = _case_name(world)
        phases, phase_records = {"init": init_phase}, {"init": init_record}
        if init_result["valid"]:
            start = adapter.phase_start(world, "sim", sim_start, init_result["end"])
            _, sim_record, sim_phase = phase_run(world, "sim", start)
            sim_record["start"] = sim_start
            sim_record["event_values"] = _value_summary(world, clock=clock, shift=shift)
            phases["sim"], phase_records["sim"] = sim_phase, sim_record
        record = {
            "kind": "cells.event_world_adapter_run@1",
            "created_utc": reference_run.utc_now(),
            "backend": "emulator",
            "model": "validation/betse/emulator/events.py (BETSE order, not an engine model)",
            "variant": variant._asdict() | {"event_clock": clock, "event_shift": shift},
            "constants": constants,
            "model_differences": list(differences),
            "dt_factor": dt_factor,
            "device": str(device),
            "jax": jax.__version__,
            "sim_start": sim_start,
            "case": world["case"],
            "betse_extract": world["extract"],
            "events": world["events"],
            "event_targets": world["event_targets"]["path"],
            "protocol": {
                "path": str(Path(protocol_path).resolve()),
                "sha256": protocol_sha,
                "id": protocol.get("id"),
            },
            "phases": phase_records,
            "valid": all(r["valid"] for r in phase_records.values())
            and len(phase_records) == len(PHASES),
            "max_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        }
        record = adapter.provenance(record, route.executed)
        target = out / name
        if record["valid"]:
            adapter.compare.write_layout(
                target,
                phases,
                protocol_sha256=protocol_sha,
                betse_geometry_sha256=world["geometry_sha256"],
                provenance=record,
            )
        else:
            target.mkdir()
        reference_run.write_json(target / "run.json", adapter.compare.json_safe(record))
        records[name] = record
    return records


def _value_summary(world, *, clock="betse", shift=0):
    values = event_values(world, "sim", clock=clock, shift=shift)
    rows = []
    for e, row in enumerate(world["events"]):
        v = values[:, e]
        changed = np.flatnonzero(np.diff(v) != 0) + 1
        rows.append(
            {
                "name": row["name"],
                "first_update_nonzero": int(np.argmax(v > 0)) if np.any(v > 0) else None,
                "change_updates": changed[:20].tolist(),
                "values_exactly_0_or_1": bool(np.all((v == 0) | (v == 1))),
                "value_range": [float(v.min()), float(v.max())],
            }
        )
    return rows


# ............................................................ resolved backend (@3)


def _schedule(times, values):
    """Right-continuous schedule [{time, availability}] keeping only changes."""
    rows = []
    for t, v in zip(times, values, strict=True):
        if not rows or rows[-1]["availability"] != float(v):
            rows.append({"time": float(t), "availability": float(v)})
    return rows


def control_times(world, phase, dt):
    """Cells times of BETSE's update boundaries: integer * dt (the engine's grid)."""
    ratio = round(world["dt_s"][phase] / dt)
    if ratio < 1 or not math.isclose(ratio * dt, world["dt_s"][phase], rel_tol=1e-12):
        raise EventError("the Cells dt must divide BETSE's dt")
    return [(k * ratio) * dt for k in range(world["steps"][phase])]


def resolved_event_definition(world, phase, start, *, dt, **kwargs):
    """default_world_adapter's @2 definition as resolved_pump_tissue@3 with the events."""
    if world["calcium_pump"] is None:
        raise EventError("resolved_pump_tissue@3 extends @2: the world needs its Ca-ATPase")
    definition = adapter.resolved_definition(world, phase, start, dt=dt, **kwargs)
    model, experiment = definition["model"], definition["experiment"]
    values = event_values(world, phase)
    times = control_times(world, phase, dt)
    channels, channel_controls = [], []
    pump_values = np.ones(len(times))
    junction_values = None
    for e, row in enumerate(world["events"]):
        v = values[:, e]
        if row["kind"] == "pump_block":
            pump_values = 1.0 - v
        elif row["kind"] == "junction_block":
            on = np.flatnonzero(v > 0)
            if phase == "sim" and (
                not np.all((v == 0) | (v == 1)) or (on.size and not np.all(v[on[0] :] == 1))
            ):
                raise EventError("a junction block must be a full step held to the end of SIM")
            junction_values = 1.0 - v
        else:
            if row["ion"] not in RESOLVED_LEAKS:
                raise EventError(f"{row['name']}: Cells has no {row['ion']} leak law (engine gap)")
            if phase != "sim":
                continue  # BETSE fires no event in INIT: INIT is the same for every case
            schedule = _schedule(times, v)
            for j in row["membranes"]:
                cid = f"evt-{row['name']}-{j}"
                channels.append(
                    {
                        "id": cid,
                        "membrane_id": f"mem-{j}",
                        "kinetic_law": RESOLVED_LEAKS[row["ion"]],
                        "max_permeability_m_per_s": row["multiplier"]
                        * row["dm_default_m2_s"]
                        / world["membrane_thickness_m"],
                        "abundance": 1.0,
                        "initial_gate": [],
                        "permeant_ions": [{"species_id": row["ion"], "relative_permeability": 1.0}],
                    }
                )
                channel_controls.append({"channel_id": cid, "schedule": copy.deepcopy(schedule)})
    if phase == "sim":
        pumps = _schedule(times, pump_values)
        for group in experiment["pump_controls"]:
            group["schedule"] = copy.deepcopy(pumps)
        if junction_values is not None:
            junctions = _schedule(times, junction_values)
            for group in experiment["junction_controls"]:
                group["schedule"] = copy.deepcopy(junctions)
    model["id"] = RESOLVED_MODEL_ID
    model["channels"] = channels
    experiment["channel_controls"] = channel_controls
    definition["execution"]["channel_capacity"] = len(channels)
    return definition


def _window_sink(observed, newton, spec, model):
    """default_world_adapter._window_sink with each window's readouts at its end control."""
    from cells.core.schedule import control_values
    from cells.processes.electrochemistry import CHARGE_PER_FMOL

    def sink(window):
        for k in adapter.RESOLVED_OBSERVED:
            observed[k].append(np.asarray(getattr(window.observations, k)))
        state = type(window.final.state)(*(np.asarray(v) for v in window.final.state))
        layout = type(window.final.layout)(*(np.asarray(v) for v in window.final.layout))
        controls = control_values(spec, [float(window.final.time)])
        control = type(controls)(*(np.asarray(v[0]) for v in controls))
        w = model.readouts(state, control, layout, xp=np)
        with np.errstate(all="ignore"):
            ledgers = model.balances(state, layout)
        newton.append(
            {
                "time_s": float(window.final.time),
                "iterations": int(w.field.iterations),
                "converged": bool(w.field.converged),
                "current_normalized": float(w.field.current_normalized),
                "ledgers_max_abs": {
                    k: float(np.max(np.abs(v), initial=0.0)) for k, v in ledgers.items()
                },
                "supplied_charge_C": float(
                    np.sum(np.abs(layout.valence * state.reservoir_supplied)) * CHARGE_PER_FMOL
                ),
            }
        )

    return sink


def _resolved_phase(world, phase, start, out, *, dt, device_kind, solver, field_solver, window):
    """One resolved phase: (record, layout phase or None, final checkpoint or None)."""
    from cells.core.specs import parse_spec
    from cells.core.windows import WindowPolicy, run_windowed
    from cells.models.registry import get_model

    definition = resolved_event_definition(
        world, phase, start, dt=dt, backend=device_kind, solver=solver, field_solver=field_solver
    )
    reference_run.write_json(out / f"{phase}_definition.json", definition)
    record = {"dt_s": dt, "solver": solver, "field_solver": field_solver}
    observed, newton = {k: [] for k in adapter.RESOLVED_OBSERVED}, []
    try:
        spec = parse_spec(definition)
        sink = _window_sink(observed, newton, spec, get_model(spec.model))
        started = time.perf_counter()
        result = run_windowed(spec, WindowPolicy(window), sink=sink)
        record["wall_s"] = time.perf_counter() - started
    except Exception as error:  # keep the evidence of a failed integration
        record["failure"] = {
            "type": type(error).__name__,
            "message": str(error)[:2000],
            "windows_completed": len(newton),
            "last_completed_time_s": newton[-1]["time_s"] if newton else 0.0,
            "window_ends": newton,
        }
        if newton:
            partial = {k: np.concatenate(v) for k, v in observed.items()}
            np.savez_compressed(out / f"{phase}_partial_observations.npz", **partial)
            record["failure"]["checks_before_failure"] = adapter._resolved_checks(
                definition, partial, newton
            )
        return record, None, None, definition
    obs = {k: np.concatenate(v) for k, v in observed.items()}
    record |= {
        "steps": int(result.final.step_index - result.start_step),
        "execute_ms_per_step": 1e3
        * result.timings.get("window_execute_seconds", float("nan"))
        / max(1, result.final.step_index - result.start_step),
        "timings": result.timings,
        "resources": result.resources,
        "diagnostics": result.diagnostics,
        **adapter._resolved_checks(definition, obs, newton),
        "channel_populations": len(definition["model"]["channels"]),
    }
    layout_phase = adapter.resolved_layout_phase(world, definition, obs)
    record["patch_exterior"] = adapter.patch_exterior_check(world, layout_phase)
    return record, layout_phase, result.final, definition


def run_resolved_events(
    cases,
    out,
    *,
    device_kind,
    dt_init=1e-3,
    dt_sim=1e-4,
    solver=adapter.RESOLVED_SOLVER,
    field_solver=adapter.RESOLVED_FIELD_SOLVER,
    window_steps=250,
    protocol_paths=None,
):
    """Blind resolved_pump_tissue@3: INIT once (shared), SIM per case from its end.

    Reads BETSE inputs only (``event_world(blind=True)``). With ``protocol_paths`` (one per
    case, judged run) each protocol must match its case and the run.
    """
    import jax

    jax.config.update("jax_enable_x64", True)
    worlds = [event_world(case, blind=True) for case in cases]
    _shared_init(worlds)
    model_id = lambda world: RESOLVED_MODEL_ID  # noqa: E731
    protocols = [None] * len(worlds) if protocol_paths is None else list(protocol_paths)
    if len(protocols) != len(worlds):
        raise EventError("give one protocol per case")
    judged = [
        None
        if path is None
        else adapter.judged_protocol(
            path,
            world,
            device_kind=device_kind,
            dt_init=dt_init,
            dt_sim=dt_sim,
            solver=solver,
            model_id=model_id,
            field_solver=field_solver,
        )
        for world, path in zip(worlds, protocols, strict=True)
    ]
    out = reference_run.resolve_out(out)
    out.mkdir(parents=True, exist_ok=False)
    device = jax.devices(device_kind)[0]
    options = dict(device_kind=device_kind, solver=solver, field_solver=field_solver)
    init_dir = out / "init"
    init_dir.mkdir()
    init_record, init_phase, init_final, init_definition = _resolved_phase(
        worlds[0], "init", adapter.phase_start(worlds[0], "init"), init_dir, dt=dt_init,
        window=window_steps, **options,
    )  # fmt: skip
    init_record["start"] = "configured"
    init_record["shared_by"] = [_case_name(w) for w in worlds]
    reference_run.write_json(init_dir / "init_record.json", adapter.compare.json_safe(init_record))
    runs = {}
    for world, path, verdict in zip(worlds, protocols, judged, strict=True):
        name = _case_name(world)
        target = out / name
        target.mkdir()
        records, phases = {"init": init_record}, {"init": init_phase}
        if init_final is not None:
            start = adapter.resolved_handoff(init_definition, init_final)
            sim_record, sim_phase, _, _ = _resolved_phase(
                world, "sim", start, target, dt=dt_sim, window=window_steps, **options
            )
            sim_record["start"] = "own INIT end (shared INIT run)"
            records["sim"] = sim_record
            if sim_phase is not None:
                phases["sim"] = sim_phase
        protocol, sha = (None, None) if verdict is None else verdict
        run = {
            "kind": "cells.event_world_adapter_run@1",
            "created_utc": reference_run.utc_now(),
            "backend": "resolved",
            "model": RESOLVED_MODEL_ID,
            "blind": (
                "BETSE inputs only (manifest, geometry.npz, init_final parameter arrays, the "
                "case's target record); no BETSE history or end state read; no Cells-vs-BETSE "
                "difference computed"
            ),
            "device": str(device),
            "jax": jax.__version__,
            "sim_start": "chained",
            "case": world["case"],
            "betse_extract": world["extract"],
            "events": world["events"],
            "event_targets": world["event_targets"]["path"],
            "shared_init": str(init_dir),
            "phases": records,
            "valid": len(phases) == len(PHASES),
            "max_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            "protocol": None
            if protocol is None
            else {"path": str(Path(path).resolve()), "sha256": sha, "id": protocol.get("id")},
        }
        run = adapter.provenance(run, adapter.EXECUTED + EXECUTED)
        if run["valid"]:
            adapter.compare.write_layout(
                target / "layout",
                phases,
                protocol_sha256=sha,  # None: blind integration run, not judgeable
                betse_geometry_sha256=world["geometry_sha256"],
                provenance=run,
            )
        reference_run.write_json(target / "run.json", adapter.compare.json_safe(run))
        runs[name] = run
    return runs


# ............................................................ terms and command line


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare-case", help="BETSE config, target record and seed of a case")
    prep.add_argument("--spec", required=True)
    prep.add_argument("--out", required=True, help="fresh case directory")
    prep.add_argument(
        "--betse-python", default="/mnt/workspaces/Cells/venv-betse/bin/python",
        help="Python with ruamel.yaml for betse_reference_run.py prepare",
    )  # fmt: skip
    emu = sub.add_parser("run-emulator", help="event emulator: INIT once, SIM per case")
    emu.add_argument("--case", action="append", required=True)
    emu.add_argument("--protocol", required=True)
    emu.add_argument("--constants", choices=("betse", "codata"), default="betse")
    emu.add_argument("--device", choices=("cpu", "gpu"), default="cpu")
    emu.add_argument("--sim-start", choices=("betse", "chained"), default="betse")
    emu.add_argument("--dt-factor", type=int, default=1)
    emu.add_argument("--model-difference", action="append", default=[])
    emu.add_argument("--event-clock", choices=CLOCKS, default="betse")
    emu.add_argument("--event-shift", type=int, default=0)
    emu.add_argument("--out", required=True)
    res = sub.add_parser("run-resolved", help="blind or judged @3 runs: INIT once, SIM per case")
    res.add_argument("--case", action="append", required=True)
    res.add_argument("--protocol", action="append", help="one per case (judged run)")
    res.add_argument("--device", choices=("cpu", "gpu"), default="cpu")
    res.add_argument("--dt-init", type=float, default=1e-3)
    res.add_argument("--dt-sim", type=float, default=1e-4)
    res.add_argument("--window-steps", type=int, default=250)
    res.add_argument(
        "--field-solver", choices=adapter.RESOLVED_FIELD_SOLVERS,
        default=adapter.RESOLVED_FIELD_SOLVER,
    )  # fmt: skip
    res.add_argument("--out", required=True)
    budget = sub.add_parser("difference-budget", help="default_world_adapter's, events on")
    budget.add_argument("--case", required=True)
    budget.add_argument(
        "--pair", nargs=3, action="append", required=True, metavar=("NAME", "BASE", "OTHER")
    )
    budget.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare-case":
        return cmd_prepare_case(args)
    if args.command == "run-emulator":
        records = run_event_emulator(
            args.case,
            args.protocol,
            args.out,
            constants=args.constants,
            device_kind=args.device,
            sim_start=args.sim_start,
            dt_factor=args.dt_factor,
            differences=tuple(args.model_difference),
            clock=args.event_clock,
            shift=args.event_shift,
        )
        print(json.dumps({k: r["valid"] for k, r in records.items()}, indent=1))
        return 0 if all(r["valid"] for r in records.values()) else 1
    if args.command == "run-resolved":
        runs = run_resolved_events(
            args.case,
            args.out,
            device_kind=args.device,
            dt_init=args.dt_init,
            dt_sim=args.dt_sim,
            field_solver=args.field_solver,
            window_steps=args.window_steps,
            protocol_paths=args.protocol,
        )
        print(json.dumps({k: r["valid"] for k, r in runs.items()}, indent=1))
        return 0 if all(r["valid"] for r in runs.values()) else 1
    out = reference_run.resolve_out(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    world = event_world(args.case, blind=True)
    result = adapter.difference_budget(world, args.pair, adapter.EXECUTED + EXECUTED)
    reference_run.write_json(out, adapter.compare.json_safe(result))
    print(json.dumps({"out": str(out)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
