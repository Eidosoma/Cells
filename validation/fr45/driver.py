"""FR-45's driver: one run of one world, in its own process, written as one record in the contract's run shape
(validation/fr45/spec/TABLE.md §4 to §7). The exporter (validation/fr45/exporter.py) forms the table from the
records alone; the driver forms nothing from states that the engine does not hold.

The run: the world built from its `inputs` (validation/fr45/worlds.py), parsed, and stepped in windows of one
step with full recording (`iter_windows(spec, WindowPolicy(1, "full"))`, TABLE §7), so a refusal's step is exact
and every row before it is kept. A plant's patch (validation/fr45/plants/) is applied in the run's own process
before the world is built (TABLE §8.1).

Each key and its source (the build plan's §2.3):
- rows: `n:` from the model's physical amounts, `R:` from site_occupancy.free_sites through the set name map,
  `B:` from bound_sites; `records` the wash's own records at the washed node; `site_heat_pJ` the site operator's
  heat records at each facing compartment; `site_occupied_fraction` the operator's `quantities`, jitted, on the
  row's saved state;
- events: the wash's applied count changing between two rows, its records from the first row after;
- event_map: the wash's event map, NumPy and compiled, on the saved states of its world's map steps (TABLE §6);
- step_report: site_occupancy.step_report on the start (W5's runs), its verdict the run's own outcome of step 1;
- refusal: the mapping below (TABLE §7; its dated addendum, TABLE §14.1, fixes it before any registered run).

The first-run rule: `run` refuses a world whose name does not begin `INVENTED-` unless the call is judged.

Usage (PYTHONPATH at a snapshot, JAX_ENABLE_X64=1, JAX_PLATFORMS=cpu):
  python -B -m validation.fr45.driver run SPEC_JSON RECORD_JSON
SPEC_JSON: {"run", "inputs", "plant" (a module of validation/fr45/plants, or null), "start" (W1eq's start file, or
null), "time_limit_step" (a harness condition for development, or null), "judged" (false)}; an invented world's
job may add "map_at_start" (its event map applied to the start as well, as W7's is).
"""

import argparse
import hashlib
import importlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np

KIND = "fr45 engine run record, version 1"
COMPOSITE, INNER = "cells.model.resolved_pump_composite@1", "cells.model.resolved_pump_tissue@3"
WASH_LAW = "cells.operator.scheduled_compartment_wash@1"
# The run's ledgers and host checks (the checks addendum, TABLE §14.1, fixes the list and its cadence).
CHECKS = ("domain", "local", "outside", "total", "charge", "electrode", "global_charge", "energy",
          "reservoir_work", "electrode_work", "metabolic_work", "site_bound_entity", "site_moiety_entity",
          "dissipation")  # fmt: skip
WASH_CHECKS = ("wash_ions",)
BOOKS = {"site_moiety_entity": "moiety ledger", "energy": "energy ledger", "dissipation": "dissipation check"}
MAP_AT_START = ("W7",)  # Worlds whose event map is applied to the start as well as to the wash row (TABLE §6).
STEP_REPORT = ("W5",)


class TimeLimit(Exception):
    """A harness condition of the driver: the run stopped before a given step (no engine exception)."""


def shape(run_name):
    """The registered shape a run takes, from its name (TABLE §3, §12.1): W1, W1eq, W1p, ..., W7s."""
    name = run_name.removeprefix("INVENTED-").split("~")[0]
    return name.split("-P")[0].split("-dt")[0]


def book(check):
    return BOOKS.get(check, f"host check: {check}")


def saved_steps(inputs, world_shape):
    """{step: time}: the start, each observation time, and W5's horizon (TABLE §5, §5.1)."""
    dt = inputs["dt_s"]
    steps = {0: 0.0}
    for t in inputs["observation_times_s"]:
        steps[int(round(t / dt))] = t
    if world_shape in STEP_REPORT:
        steps[int(round(inputs["horizon_s"] / dt))] = inputs["horizon_s"]
    return steps


def source():
    """Provenance (TABLE §10): the code on PYTHONPATH, its snapshot's record or the checkout's git state."""
    import jax
    import jaxlib
    import scipy

    import cells
    from cells.execution import blas_threads

    root = Path(cells.__file__).resolve().parents[2]
    snap = root / "SNAPSHOT.json"
    if snap.exists():
        data = json.loads(snap.read_text())
        revision, dirty, patch = data.get("git_revision"), bool(data.get("selected_status_porcelain_v1_z")), \
            data.get("patch_sha256")  # fmt: skip
    else:
        git = ["git", "-C", str(root)]
        revision = subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        diff = subprocess.run([*git, "diff", "HEAD"], capture_output=True).stdout
        dirty, patch = bool(diff), hashlib.sha256(diff).hexdigest()
    threads = {lib.get("num_threads") for lib in blas_threads.libraries()}
    return dict(
        engine_revision=revision,
        checkout_dirty=dirty,
        snapshot=str(root),
        snapshot_patch_sha256=patch or hashlib.sha256(b"").hexdigest(),
        python=platform.python_version(),
        numpy=np.__version__,
        scipy=scipy.__version__,
        jax=jax.__version__,
        jaxlib=jaxlib.__version__,
        jax_enable_x64=bool(jax.config.jax_enable_x64),
        jax_platforms=os.environ.get("JAX_PLATFORMS", ""),
        blas_threads=int(next(iter(threads))) if len(threads) == 1 else -1,
        machine=platform.machine(),
        external_modules=[],
    )


class Reader:
    """Reads a saved state into the contract's shapes (TABLE §5), by the world's names."""

    def __init__(self, spec, world, model, p):
        from cells.operators import OPERATORS
        from cells.operators import site_occupancy as so

        self.so, self.model, self.p = so, model, p
        self.spec, self.world = spec, world
        self.declaration = next(d for op, d, _ in _entries(spec) if op.LAW_ID == so.LAW_ID)
        self.ids = list(spec.model.species_ids)
        self.cells = [c.id for c in spec.model.cells]
        self.outside = [c.id for c in spec.model.extracellular]
        self.ligands = list(world.inputs["ligands"])
        self.set_keys = [key for key, _, _ in so.set_axis(self.declaration)]
        self.populations = [pop.id for pop in self.declaration.populations]
        self.facing = sorted(set(world.facing.values()), key=lambda n: (n not in self.outside, n))
        operator = OPERATORS[so.LAW_ID]
        import jax

        self._quantities = jax.jit(lambda state: operator.quantities(state, p, xp=jax.numpy))

    def amounts(self, state):
        cells, outside = self.model.physical_amounts(state, self.p)
        cells, outside = np.asarray(cells), np.asarray(outside)
        out = {}
        for g in self.ligands:
            row = self.ids.index(g)
            for name in self.world.inputs["nodes"]:
                node = name["id"]
                if node in self.outside:
                    out[f"n:{g}@{node}"] = float(outside[row, self.outside.index(node)])
                else:
                    out[f"n:{g}@{node}"] = float(cells[row, self.cells.index(node)])
        free = np.asarray(self.so.free_sites(state, self.p, xp=np))
        for key, value in zip(self.set_keys, free, strict=True):
            out[f"R:{self.world.set_of_engine_key[key]}"] = float(value)
        bound = np.asarray(self.so.bound_sites(state, self.p, xp=np))
        for pop, value in zip(self.populations, bound, strict=True):
            out[f"B:{pop}"] = float(value)
        return out

    def records(self, state):
        node = self.world.washed_node
        if node is None:
            return {}
        k = self.outside.index(node)
        collected, supplied = np.asarray(state.wash_collected_fmol), np.asarray(state.wash_supplied_fmol)
        return {f"{g}@{node}": dict(collected=float(collected[self.ids.index(g), k]),
                                    supplied=float(supplied[self.ids.index(g), k])) for g in self.ligands}  # fmt: skip

    def heat(self, state):
        cell_heat = np.asarray(state.site_dissipated_energy_pJ)
        outside_heat = np.asarray(state.site_outside_dissipated_energy_pJ)
        return {n: float(outside_heat[self.outside.index(n)] if n in self.outside else cell_heat[self.cells.index(n)])
                for n in self.facing}  # fmt: skip

    def fraction(self, state):
        q = np.asarray(self._quantities(state)["site_occupied_fraction"])
        return {pop: float(v) for pop, v in zip(self.populations, q, strict=True)}

    def row(self, step, time_s, state):
        return dict(step=step, time_s=float(time_s), amounts=self.amounts(state), records=self.records(state),
                    site_heat_pJ=self.heat(state), site_occupied_fraction=self.fraction(state))  # fmt: skip

    def capacities(self):
        cap = np.asarray(self.p.site_set_capacity_fmol)
        if cap.shape[0] == 0:  # No shared set: each population its own set, its capacity its own.
            cap = np.asarray(self.p.site_capacity_fmol)
        return {self.world.set_of_engine_key[k]: float(v) for k, v in zip(self.set_keys, cap, strict=True)}


def _entries(spec):
    from cells.definitions import pump_composite_spec as cs

    return cs.entries(spec)


def echo(spec, world, reader):
    """`inputs` (TABLE §4.1): the world as the engine parsed it, by the inputs' names."""
    from cells.operators import site_occupancy as so

    m, inputs = spec.model, world.inputs
    ids = list(m.species_ids)
    registered = {n["id"]: n["registered"] for n in inputs["nodes"]}
    compartments = {**{c.id: ("cell", c) for c in m.cells}, **{c.id: ("node", c) for c in m.extracellular}}
    ions = [s for s in m.species_ids if s not in reader.ligands and s in {i for i, _ in _ion_species()}]
    membranes = list(m.membranes)
    decl = reader.declaration
    counts = {key: entity for key, entity, _ in so.set_axis(decl)}
    sets = []
    for entry in inputs["sets"]:
        key = entry["id"] if entry["shared"] else next(
            p["id"] for p in inputs["populations"] if p["set"] == entry["id"])  # fmt: skip
        entity = counts[key]
        sets.append(dict(id=entry["id"], shared=entry["shared"], owner=entry["owner"], face=entry.get("face"),
                         faces=world.facing[entry["id"]], copies=float(entity.copies),
                         sites_per_copy=int(entity.sites_per_copy),
                         accessible_fraction=float(entity.accessible_fraction)))  # fmt: skip
    set_of = {p["id"]: p["set"] for p in inputs["populations"]}
    populations = [dict(id=p.id, set=set_of[p.id], ligand=p.ligand, k_on=float(p.k_on), k_off=float(p.k_off),
                        initial_occupancy=float(p.initial_occupancy)) for p in decl.populations]  # fmt: skip
    free_amounts = []
    for g in reader.ligands:
        for node in inputs["nodes"]:
            _, c = compartments[node["id"]]
            declared = next((e["declared"] for e in inputs["free_amounts"]
                             if e["ligand"] == g and e["node"] == node["id"]), False)  # fmt: skip
            free_amounts.append(dict(ligand=g, node=node["id"], n_fmol=float(c.initial_amount_fmol[ids.index(g)]),
                                     declared=declared))  # fmt: skip
    wash = None
    if world.washed_node is not None:
        event = next(sched for op, _, sched in _entries(spec) if op.LAW_ID == WASH_LAW).events[0]
        buffer = dict(event.buffer_mM)
        wash = dict(time_s=float(event.time), node=event.node, fraction=float(event.fraction),
                    buffer_mM={g: float(buffer[g]) for g in reader.ligands})  # fmt: skip
    controls = next(sched for op, _, sched in _entries(spec) if op.LAW_ID == so.LAW_ID)
    binding = {c.population: c.changes[0][1] for c in controls if c.route == "binding"}
    multipliers = [dict(of=p.id, name="site_binding_multiplier", value=float(binding.get(p.id, 1.0)))
                   for p in decl.populations]  # fmt: skip
    valence = {s["id"]: s.get("valence", 0) for s in _raw_species(world.raw)}
    T = float(m.temperature_K)
    return dict(
        world=inputs["world"],
        constants=dict(sites_per_fmol=so.SITES_PER_FMOL, temperature_K=T, RT_pJ_per_fmol=float(so.site_rt(T))),
        nodes=[dict(id=n["id"], kind=compartments[n["id"]][0], volume_pL=float(compartments[n["id"]][1].volume_pL),
                    registered=registered[n["id"]]) for n in inputs["nodes"]],  # fmt: skip
        patches=[dict(id=mb.id, inside=mb.inside, outside=mb.outside) for mb in membranes],
        ligands=list(reader.ligands),
        free_amounts=free_amounts,
        sets=sets,
        populations=populations,
        wash=wash,
        permeabilities=[dict(patch=mb.id, ligand=g, value=float(_permeability(mb, g, ids)))
                        for mb in membranes for g in reader.ligands],  # fmt: skip
        ion_permeabilities={mb.id: {i: float(_permeability(mb, i, ids)) for i in ions} for mb in membranes},
        multipliers=multipliers,
        charges={g: int(valence.get(g, 0)) for g in reader.ligands},
        capacitor_components=_components(m),
        host_values=dict(
            areas={mb.id: float(mb.area_m2) for mb in membranes},
            capacitances={mb.id: float(mb.capacitance_F) for mb in membranes},
            ion_amounts={n["id"]: {i: float(compartments[n["id"]][1].initial_amount_fmol[ids.index(i)])
                                   for i in ions} for n in inputs["nodes"]},  # fmt: skip
        ),
        dt_s=float(spec.execution.dt),
        observation_times_s=[float(t) for t in inputs["observation_times_s"]],
        horizon_s=float(spec.experiment.end_time),
    )


def _ion_species():
    from validation.tissue import secreted_species_fixtures as fx

    return fx.ION_SPECIES


def _permeability(membrane, species, ids):
    """A patch's permeability to a species: its declared value, or 0.0 for one it does not declare (the
    species helper declares every ligand membrane-impermeant)."""
    values = tuple(getattr(membrane, "permeability_m_per_s", ()) or ())
    if values and isinstance(values[0], tuple):
        return dict(values).get(species, 0.0)
    return values[ids.index(species)] if len(values) == len(ids) else 0.0


def _raw_species(raw):
    model = raw["model"]
    inner = model.get("inner_model") if isinstance(model.get("inner_model"), dict) else model
    return list(inner.get("species", [])) + [s for op in model.get("operators", []) for s in op.get("species", [])
                                              if isinstance(s, dict) and "valence" in s]  # fmt: skip


def _components(model):
    """The capacitor component holding the bath: every compartment joined to it by patches."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for mb in model.membranes:
        parent[find(mb.inside)] = find(mb.outside)
    members = sorted(x for x in list(parent) if find(x) == find("bath"))
    return [dict(members=members, held_by="bath")]


def _parse_refusal(error):
    """(kind, name) of a refusal at parse: the site operator's names by its REFUSALS, domain or definition."""
    from cells.operators import site_occupancy as so

    text = str(error)
    for name in so.REFUSALS:
        if name in text:
            return ("domain" if name in so.DOMAIN_REFUSALS else "definition"), name
    return "definition", text.split(":")[0][:200]


def run(job, out):
    """Run one job (the module docstring's SPEC_JSON) and write its record to `out`."""
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import ConfigError, parse_spec
    from cells.execution.errors import NumericalError
    from cells.execution.windows import WindowPolicy, iter_windows
    from cells.operators import site_occupancy as so
    from cells.operators import wash_schedule as wash
    from cells.registry.models import get_model
    from validation.fr45 import worlds

    name, inputs = job["run"], job["inputs"]
    if not name.startswith("INVENTED-") and not job.get("judged"):
        raise SystemExit(f"refused: {name} is a registered run; the driver steps one only in judged mode")
    world_shape = shape(name)
    record = dict(kind=KIND, run=name, status="completed", world=inputs["world"], plant=None, dt_s=inputs["dt_s"],
                  steps=0, backend="compiled", driver=dict(window_steps=1), rows=[], capacities={}, free_sites={},
                  events=[], event_map=[], step_report=None, refusal=None, checks=None, operators=[], inputs=None,
                  definition=None, source=source())  # fmt: skip
    plant = None
    if job.get("plant"):
        plant = importlib.import_module(f"validation.fr45.plants.{job['plant']}")
        inputs, changed = plant.declare(inputs)
        plant.apply()
        record["plant"] = dict(id=plant.ID, patch=f"validation/fr45/plants/{job['plant']}.py",
                               change=plant.CHANGE, inputs_changed=list(changed))  # fmt: skip
    start = job.get("start")
    if isinstance(start, str):  # W1eq's start file, read at run time in the run's own process (TABLE §3, item 2).
        start = json.loads(Path(start).read_text())
    if start:
        start = dict(initial_occupancy={p["id"]: p["initial_occupancy"] for p in start["world"]["populations"]},
                     free_amounts={(e["ligand"], e["node"]): e["n"] for e in start["world"]["free_amounts"]})  # fmt: skip
    world = worlds.build(inputs, start=start)

    def refuse(kind, raised, book_, name_, message, step=None, time_s=None):
        record["status"] = "refused"
        record["refusal"] = dict(kind=kind, raised=raised, book=book_, name=name_, message=message, step=step,
                                 time_s=time_s)  # fmt: skip

    try:
        spec = parse_spec(world.raw)
        model = get_model(spec.model)
        state0, p = model.initial_values(spec)
    except ConfigError as error:
        kind, why = _parse_refusal(error)
        refuse(kind, f"{type(error).__module__}.{type(error).__qualname__}", None, why, str(error))
        return _write(record, out)
    reader = Reader(spec, world, model, p)
    record["operators"] = [COMPOSITE, INNER, *(op.LAW_ID for op, _, _ in _entries(spec))]
    record["inputs"] = echo(spec, world, reader)
    record["definition"] = spec.to_dict()
    record["capacities"] = reader.capacities()
    record["free_sites"] = {s: "state" for s in record["capacities"]}
    checks = CHECKS + (WASH_CHECKS if world.washed_node is not None else ())
    record["checks"] = {c: dict(failures=[]) for c in checks}
    saved = saved_steps(inputs, world_shape)
    dt = float(spec.execution.dt)
    map_steps = set()
    if world.washed_node is not None:
        wash_step = int(round(world.inputs["wash"]["time_s"] / dt))
        at_start = job.get("map_at_start", world_shape in MAP_AT_START)  # An invented world may name it.
        map_steps = {wash_step} | ({0} if at_start else set())
    # The start, row 0: the state every window run begins from (TABLE §5: the start, before any step), so a
    # refusal at step 1 keeps it, and the stage condition is read on it.
    from cells.execution.state import initialise

    start_state = initialise(spec).state
    start_state = type(start_state)(*(np.asarray(v) for v in start_state))
    kept, last = {}, (0, 0.0, start_state)  # Saved states for the event map; the last row (step, time, state).
    record["rows"].append(reader.row(0, 0.0, start_state))
    if 0 in map_steps:
        kept[0] = start_state
    limit = job.get("time_limit_step")
    try:
        for window in iter_windows(spec, WindowPolicy(1, "full")):
            history = window.history
            for i, t in enumerate(np.asarray(window.times)):
                step = window.start_step + i
                state = type(history)(*(np.asarray(v)[i] for v in history))
                if last is not None and step == last[0] + 1 and world.washed_node is not None:
                    _event(record, reader, last, (step, t, state), world)
                if step in saved and all(r["step"] != step for r in record["rows"]):
                    record["rows"].append(reader.row(step, t, state))
                if step in map_steps:
                    kept[step] = state
                last = (step, float(t), state)
                record["steps"] = step
            if limit is not None and last[0] + 1 >= limit:
                raise TimeLimit(f"the driver's time limit stops the run before step {limit}")
    except TimeLimit as error:
        refuse("harness", None, None, "driver time limit", str(error), last[0] + 1, last[1])
    except NumericalError as error:
        message = str(error)
        check = next((c for c in checks if message.startswith(model.device_failure_message(c))), None)
        step, t0 = last[0] + 1, last[1]
        if check is not None and check != "domain":
            record["checks"][check]["failures"].append(dict(step=last[0], message=message))
            refuse("check", _qualified(error), book(check), check, message, step, t0)
        else:
            control = _control(spec, t0)
            stage = so.refusal_condition(last[2], control, p, dt) if world_shape else None
            kind = "stage" if stage == so.STAGE_CONDITION else "domain"
            refuse(kind, _qualified(error), None, stage or "solver domain", message, step, t0)
    except ConfigError as error:  # A refusal at binding (e.g. X2 beside sets) before any step.
        kind, why = _parse_refusal(error)
        refuse(kind, _qualified(error), None, why, str(error))
    except Exception as error:  # noqa: BLE001 - the harness: anything the engine did not raise.
        refuse("harness", _qualified(error), None, f"driver: {type(error).__name__}", str(error)[:2000],
               (last[0] + 1) if last else None, last[1] if last else None)  # fmt: skip
    if world_shape in STEP_REPORT:
        record["step_report"] = _step_report(spec, reader, state0, p, dt, record)
    for step in sorted(kept):
        for variant in ("numpy", "compiled"):
            record["event_map"].append(_event_map(spec, reader, world, kept[step], step, variant, wash, p))
    _event_of_refused_step(record, world, map_steps)
    return _write(record, out)


def _event_of_refused_step(record, world, map_steps):
    """A run refused in the step whose start applies the wash holds the event (TABLE §4, Y2) unless the wash
    itself refused: no row follows that step, so its records are the engine's compiled event map's on the wash
    row's saved state, the same compiled map the step applies."""
    refusal = record["refusal"]
    if world.washed_node is None or refusal is None or refusal["step"] is None or record["events"]:
        return
    wash_step = max(map_steps)
    if refusal["step"] != wash_step + 1 or refusal["name"] == "wash_ions":
        return
    entry = next((m for m in record["event_map"] if m["state_step"] == wash_step and m["variant"] == "compiled"), None)
    if entry is None:
        return
    node = world.washed_node
    before, after = entry["before"]["records"], entry["after"]["records"]
    ligands = [key.split("@")[0] for key in after]
    record["events"].append(dict(
        kind="wash", operator=WASH_LAW, node=node, after_step=wash_step, time_s=refusal["time_s"],
        collected={g: after[f"{g}@{node}"]["collected"] - before[f"{g}@{node}"]["collected"] for g in ligands},
        supplied={g: after[f"{g}@{node}"]["supplied"] - before[f"{g}@{node}"]["supplied"] for g in ligands}))  # fmt: skip


def _qualified(error):
    return f"{type(error).__module__}.{type(error).__qualname__}"


def _control(spec, t):
    from cells.definitions import pump_composite_spec as cs

    controls = cs.control_values(spec, [t])
    return type(controls)(*(np.asarray(v[0]) for v in controls))


def _event(record, reader, before, after, world):
    k = reader.outside.index(world.washed_node)
    applied = [int(np.asarray(s.wash_applied)[k]) for s in (before[2], after[2])]
    if applied[1] == applied[0] + 1:
        state = after[2]
        sample, supply = np.asarray(state.wash_last_sample_fmol), np.asarray(state.wash_last_supply_fmol)
        record["events"].append(dict(
            kind="wash", operator=WASH_LAW, node=world.washed_node, after_step=before[0], time_s=before[1],
            collected={g: float(sample[reader.ids.index(g), k]) for g in reader.ligands},
            supplied={g: float(supply[reader.ids.index(g), k]) for g in reader.ligands}))  # fmt: skip


def _event_map(spec, reader, world, state, step, variant, wash, p):
    import jax

    w = world.inputs["wash"]
    control = _control(spec, w["time_s"])
    if variant == "numpy":
        after, _ = wash.apply_events(state, control, p, xp=np)
    else:
        after, _ = jax.jit(lambda s, c: wash.apply_events(s, c, p))(state, control)
        after = type(after)(*(np.asarray(v) for v in after))
    return dict(state_step=step, variant=variant, node=w["node"], fraction=float(control.wash_fraction[
        reader.outside.index(w["node"])]), buffer_mM={g: float(np.asarray(control.wash_buffer_mM)[
        reader.ids.index(g), reader.outside.index(w["node"])]) for g in reader.ligands},
        before=dict(amounts=reader.amounts(state), records=reader.records(state)),
        after=dict(amounts=reader.amounts(after), records=reader.records(after)))  # fmt: skip


def _step_report(spec, reader, state0, p, dt, record):
    from cells.operators import site_occupancy as so

    report = so.step_report(spec, reader.declaration, state0, _control(spec, 0.0), p, dt)
    named = {k: reader.world.set_of_engine_key.get(k, k) for k in reader.set_keys}

    def load(entry):
        ident = named.get(entry["id"], entry["id"]) if entry["kind"] == "L_R" else entry["id"]
        return dict(kind=entry["kind"], id=ident, sums=list(entry["sums"]), per_s=float(entry["per_s"]))

    refused_at_1 = record["refusal"] is not None and record["refusal"]["step"] == 1
    return dict(step=int(report["step"]), h_s=float(report["h_s"]), loads=[load(x) for x in report["loads"]],
                max_load=load(report["max_load"]), h_max_load=float(report["h_max_load"]),
                limit=float(report["limit"]), verdict="refused" if refused_at_1 and
                record["refusal"]["kind"] == "stage" else "admitted")  # fmt: skip


def _write(record, out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(_finite(record), indent=1, allow_nan=False) + "\n"
    out.write_text(text)
    return record


def _finite(value):
    """A non-finite number is written as null (TABLE §1)."""
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _finite(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_finite(v) for v in value]
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("run")
    one.add_argument("job")
    one.add_argument("out")
    args = parser.parse_args(argv)
    run(json.loads(Path(args.job).read_text()), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
