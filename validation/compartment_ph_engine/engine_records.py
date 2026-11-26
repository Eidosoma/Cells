"""The engine's records of FR-4's (and later FR-5's) worlds, for the qualification generator.

validation/tissue/compartment_ph_qualification.engine_run calls `run(definition)`: it parses the
development world (definitions.development_world: the declared world without FR-1's compartment
operator, the lead's ruling of 15 November 2026), runs it on the windowed runner
(cells.execution.windows.run_windowed, every accepted row checked on the host, the CPU backend in
float64), and keeps one row per record from each window's observations (ENGINE_READOUTS):
- `record_s` and `series`: the closure's pH at the cytosol and the lumen (B4's readout), the
  bounding patch's voltage, the H and K rows at both nodes, the pump's cumulative cycles, the
  maintenance's work, every law's heat, the stored free energy's change, the energy residual and
  the integrated flows the engine's ledger allowance uses, the pump's and the leak's cumulative
  proton transfers (cytosol to lumen positive) and each route's heat;
- `amounts_fmol`: every row at every node and record, from which the judge computes the material
  check and its allowance;
- `stage`: B4's running extrema at the last record (gap 7): the largest lag estimate over every
  buffered node and stage, and the cytosol's smallest and largest pH; the count of envelope
  refusals, 0 for a run that completes (B4's stage check refuses the step at the first stage
  beyond the budget);
- `ledgers`: the charge ledger's residual and its tolerance at the record of their largest ratio.
A refusal (at the definition or in the run) is recorded with its message: a refusal is a verdict.
A refusal at the definition is attributed to the envelope (`refusal_reason`, K3's catch: the lead's
ruling) when the same development world is admitted with B4's stage check alone removed.

`run(..., path="vector")` runs the same world as the one world of a cells.execution.vector_windows
window instead: every accepted row is checked on the device (the model's device_checks, with the
kinds' check hooks), and the observed rows reach Records through `one_world`, since a vector
window's observations are keyed by world ID. The records are the same fields; `path` names which.

The energy identity, from the engine's own ledger (surface_pump_v3.balances with the kinds' terms):
residual = stored change + heat - work, with heat every *_dissipated_energy_pJ field and work every
*_work_pJ field (reservoir, electrode and the maintenance's), so stored change = residual - heat +
work. The flows are ledger_limits' (every heat and work field's magnitude).
"""

from contextlib import nullcontext

import numpy as np

from validation.compartment_ph_engine import definitions as defs

WINDOW_STEPS = 1000  # One record per window at 1 ms.
FR4_ROWS = ("H", "K")
MOVED = {  # Route ID -> (series, species): its cumulative transfer, cytosol to lumen positive.
    "proton_leak_0": ("moved_H_leak", "H"),
    "proton_pore_0": ("moved_H_pore", "H"),
    "cargo_transfer_0": ("moved_X_transfer", "X"),
    "cargo_pore_0": ("moved_X_pore", "X"),
}
PATHS = ("host", "vector")  # Where every accepted row is checked: run()'s `path`.
WORLDS = ("development", "declared")  # run()'s `world`: without or with FR-1's operator.
VECTOR_WORLD_ID = 1  # The one world of a vector-window run.
VECTOR_LIMIT = 2**53 - 1  # Its batch's padded-step and working-byte limits: one world, no cap.


class Records:
    """A run_windowed sink: one row of readouts per record."""

    def __init__(self, spec, model):
        from cells.models import surface_pump_v3

        self.spec, self.model, self.v3 = spec, model, surface_pump_v3
        # The inner structure: @3's own, or the composite's inner model's (the declared world).
        inner = getattr(model, "inner", model)
        self.structure = getattr(model, "structure", None) or inner.structure
        m = spec.model
        self.ids = list(m.species_ids)
        self.cells = [c.id for c in m.cells]
        self.outside = [o.id for o in m.extracellular]
        self.bounding = [p.id for p in m.membranes].index(defs.BOUNDING)
        kinds = dict(m.kinds)
        routes = kinds.get("cells.kind.passive_routes@1", ())
        self.routes = [r.id for r in routes]  # The parsed (sorted) order: the route axis.
        damages = [d.patch for d in kinds.get("cells.kind.patch_damage@1", ())]
        self.damage = defs.BOUNDING if defs.BOUNDING in damages else None
        conditions = [c.id for c in kinds.get("cells.kind.ph_condition@1", ())]
        self.condition = conditions.index(defs.CONDITION) if defs.CONDITION in conditions else None
        _, self.p = model.initial_values(spec)
        from cells.registry import kind_registry

        self.pump = kind_registry.active().lookup("cells.kind.transporter@1")  # Planted or not.
        self.tol = np.asarray(spec.execution.material_balance_atol_fmol)
        self.rtol = surface_pump_v3.ENERGY_RTOL[spec.execution.solver]
        self.dt = spec.execution.dt
        names = model.STATE_TYPE._fields
        self.heat_fields = [f for f in names if f.endswith("_dissipated_energy_pJ")]
        self.work_fields = [f for f in names if f.endswith("_work_pJ")]
        self.record_s, self.series, self.amounts = [], {}, {}
        self.charge = (0.0, None, None)  # (ratio, residual, tolerance)
        self.last = None

    def amount(self, obs, j, species, node):
        row = self.ids.index(species)
        if node in self.cells:
            return float(obs.amount[j, row, self.cells.index(node)])
        return float(obs.extracellular_amount[j, row, self.outside.index(node)])

    def __call__(self, window):
        obs = window.observations
        for j in range(len(obs.times)):
            self.add(obs, j)

    def add(self, obs, j):
        from cells.models import surface_pump as first

        fields = self.model.STATE_TYPE._fields
        state = self.model.STATE_TYPE(*(np.asarray(getattr(obs, f))[j] for f in fields))
        v3, p, b = self.v3, self.p, self.bounding
        row = dict(
            pH_c=float(obs.pH[j, self.cells.index(defs.CELL)]),
            pH_L=float(obs.pH[j, len(self.cells) + self.outside.index(defs.LUMEN)]),
            V_b=float(obs.membrane_voltage_V[j, b]),
            cycles=float(state.transporter_cycles[b]),
            work_pJ=float(state.transporter_metabolic_work_pJ[b]),
            moved_H_pump=float(  # The kind's own cumulative H transfer into the lumen.
                self.pump.ledger_terms(state, p, xp=np)["outside"][
                    self.ids.index("H"), self.outside.index(defs.LUMEN)
                ]
            ),
            heat_pump_pJ=float(state.transporter_dissipated_energy_pJ[b]),
            heat_bounding_0_K_pJ=float(state.membrane_dissipated_energy_pJ[b]),
        )
        for species in FR4_ROWS:
            for node, key in ((defs.CELL, "c"), (defs.LUMEN, "L")):
                name = f"Heq_{key}" if species == "H" else f"{species}_{key}"
                row[name] = self.amount(obs, j, species, node)
        for k, route in enumerate(self.routes):  # Every passive route's transfer, and its heat.
            if route in MOVED:
                name, species = MOVED[route]  # c to L positive: the routes are inward-positive.
                row[name] = -float(state.passive_transferred[self.ids.index(species), k])
            row[f"heat_{route}_pJ"] = float(state.passive_dissipated_energy_pJ[k])
        if "X" in self.ids:  # FR-5: the cargo, the damage and the condition.
            for node, key in ((defs.CELL, "c"), (defs.LUMEN, "L")):
                row[f"X_{key}"] = self.amount(obs, j, "X", node)
        if self.damage is not None:
            row["d"] = float(state.patch_damage[b])
        if self.condition is not None:
            row["f"] = float(np.asarray(obs.ph_condition_factor)[j, self.condition])
        ledgers = v3.balances(state, p, structure=self.structure)
        heat = sum(float(np.sum(getattr(state, f))) for f in self.heat_fields)
        work = sum(float(np.sum(getattr(state, f))) for f in self.work_fields)
        residual = float(ledgers["energy"])
        steps = int(round(float(obs.times[j]) / self.dt))
        magnitudes = v3.channel_magnitudes(state, p, structure=self.structure)
        flows, bounds = first.ledger_limits(
            state, p, self.tol, self.rtol, steps=steps, magnitudes=magnitudes
        )
        row.update(
            heat_pJ=heat,
            stored_change_pJ=residual - heat + work,
            energy_residual_pJ=residual,
            energy_flows_pJ=float(flows),
        )
        charge = np.abs(np.asarray(ledgers["charge"]))
        tolerance = np.asarray(bounds[first.LEDGERS.index("charge")]) * np.ones_like(charge)
        k = int(np.argmax(charge / tolerance))
        if charge[k] / tolerance[k] >= self.charge[0]:
            self.charge = (float(charge[k] / tolerance[k]), float(charge[k]), float(tolerance[k]))
        self.record_s.append(float(obs.times[j]))
        for name, value in row.items():
            self.series.setdefault(name, []).append(value)
        for node in self.cells + self.outside:
            for species in self.ids:
                self.amounts.setdefault(node, {}).setdefault(species, []).append(
                    self.amount(obs, j, species, node)
                )
        self.last = state

    def stage(self, completed):
        """B4's running extrema at the last record, and the envelope refusals (gap 7)."""
        if self.last is None:
            return dict(
                envelope_max_lag_ph=None,
                envelope_stages_beyond=None,
                cytosol_pH_min=None,
                cytosol_pH_max=None,
            )
        cell = self.cells.index(defs.CELL)
        return dict(
            envelope_max_lag_ph=float(np.max(self.last.proton_buffer_max_lag_pH)),
            envelope_stages_beyond=0 if completed else None,
            cytosol_pH_min=float(self.last.proton_buffer_min_pH[cell]),
            cytosol_pH_max=float(self.last.proton_buffer_max_pH[cell]),
        )

    def record(self, completed):
        return dict(
            record_s=self.record_s,
            series=self.series,
            amounts_fmol=self.amounts,
            stage=self.stage(completed),
            ledgers=dict(charge_residual_C=self.charge[1], charge_tolerance_C=self.charge[2]),
        )

    def start(self):
        """FR-5's start (§13.2) from the last record: (nodes, readouts) for
        definitions.start_extract. Each node's FR-4 rows (fmol) and its charge (C), the engine's
        own (surface_pump_v3.node_charge of the last state: cells, then outside nodes), and the
        last record's pH_c, pH_L and V_b."""
        charges = np.asarray(self.v3.node_charge(self.last, self.p, xp=np))
        nodes = {}
        for k, node in enumerate(self.cells + self.outside):
            index = k if k < len(self.cells) else self.p.active.size + k - len(self.cells)
            nodes[node] = dict(
                amounts_fmol={s: self.amounts[node][s][-1] for s, _ in defs.SPECIES},
                charge_C=float(charges[index]),
            )
        readouts = dict(pH_c=self.series["pH_c"][-1], pH_L=self.series["pH_L"][-1],
                        V_b_V=self.series["V_b"][-1])
        return nodes, readouts


def envelope_reason(definition):
    """ "envelope" when the development world, refused at the definition, is admitted with B4's
    stage check alone removed (every other built-in kind as registered), else None."""
    import dataclasses

    from cells.definitions.specs import ConfigError, parse_spec
    from cells.kinds import proton_buffer
    from cells.registry import kind_registry

    registry = kind_registry.KindRegistry()
    for kind in kind_registry.active().model_keys().values():
        if kind is proton_buffer.PROTON_BUFFER:
            kind = dataclasses.replace(kind, stage_check=None)
        registry.register(kind)
    with kind_registry.scope(registry):
        try:
            parse_spec(defs.development_world(definition))
        except ConfigError:
            return None
    return "envelope"


class OneWorld:
    """One world's view of a vector window, as the windowed runner's sink receives a window: a
    vector window's observations are keyed by world ID."""

    __slots__ = ("observations",)

    def __init__(self, observations):
        self.observations = observations


def one_world(sink, world_id=VECTOR_WORLD_ID):
    """A vector-window sink that passes `world_id`'s observations, when the round has any, to a
    windowed-runner sink (Records)."""

    def consume(window):
        found = window.observations.get(world_id)
        if found is not None:
            sink(OneWorld(found))

    return consume


def _run_vector(spec, sink, window_steps):
    """The one world through cells.execution.vector_windows (every accepted row checked on the device:
    the model's device_checks, the kinds' check hooks included): (steps, diagnostics, timings,
    resources, final checkpoint), the windowed runner's result fields."""  # noqa: E501
    from cells.execution.batch import BatchSpec, WorldSpec
    from cells.execution.vector_windows import run_vector_windowed
    from cells.execution.windows import WindowPolicy

    batch = BatchSpec((WorldSpec(VECTOR_WORLD_ID, spec),), 1, VECTOR_LIMIT, VECTOR_LIMIT)
    result = run_vector_windowed(
        batch, WindowPolicy(window_steps, "observations"), sink=one_world(sink)
    )
    world = result.worlds[VECTOR_WORLD_ID]
    steps = int(world.final.step_index - world.start_step)
    return (steps, dict(world.diagnostics), dict(result.timings), dict(result.resources),
            world.final)


def run(definition, *, registry=None, window_steps=WINDOW_STEPS, path="host",
        world="development", checkpoint_dir=None):
    """The engine part's record of `definition`'s development world (module docstring). With
    `registry` the build runs inside kind_registry.scope(registry) (a planted control's). `path`
    is "host" (cells.execution.windows.run_windowed: every accepted row checked on the host) or
    "vector" (one world in a cells.execution.vector_windows window: every accepted row checked on the
    device, the observations through `one_world`); the records are the same fields. `world` is
    "development" (definitions.development_world: without FR-1's compartment operator) or
    "declared" (definitions.declared_world: the composite with it, which must give the same
    records bitwise, docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.1). With `checkpoint_dir` (FR-5's
    start part) a run that completes also writes the engine's snapshot of its final state there
    (cells.records.io.write_snapshot) and returns FR-5's start under `start_nodes` and `start_readouts`
    (Records.start, from its last record: the run ends on a record), for
    definitions.start_extract."""  # noqa: E501
    from cells.definitions.specs import ConfigError, parse_spec
    from cells.execution.errors import NumericalError
    from cells.execution.windows import WindowPolicy, run_windowed
    from cells.registry import kind_registry
    from cells.registry.models import get_model

    if world not in WORLDS:
        raise ValueError(f"world is one of {WORLDS}, not {world!r}")
    build = defs.development_world if world == "development" else defs.declared_world
    if path not in PATHS:
        raise ValueError(f"path is one of {PATHS}, not {path!r}")
    out = dict(
        admitted=False,
        completed=False,
        refusal=None,
        refusal_reason=None,
        steps=0,
        record_s=[],
        series={},
        amounts_fmol={},
        stage={},
        ledgers={},
        path=path,
        world=world,
    )
    with kind_registry.scope(registry) if registry is not None else nullcontext():
        try:
            spec = parse_spec(build(definition))
        except ConfigError as error:
            out["refusal"] = f"definition: {error}"
            if registry is None:
                out["refusal_reason"] = envelope_reason(definition)
            return out
        out["admitted"] = True
        model = get_model(spec.model)
        sink = Records(spec, model)
        try:
            if path == "vector":
                steps, diagnostics, timings, resources, final = _run_vector(
                    spec, sink, window_steps
                )
            else:
                result = run_windowed(spec, WindowPolicy(window_steps, "observations"), sink=sink)
                steps = int(result.final.step_index - result.start_step)
                diagnostics, timings = dict(result.diagnostics), dict(result.timings)
                resources, final = dict(result.resources), result.final
        except (ConfigError, NumericalError) as error:
            out["refusal"] = f"run: {error}"
            out.update(sink.record(completed=False))
            out["steps"] = int(round(sink.record_s[-1] / spec.execution.dt)) if sink.record_s else 0
            return out
        if checkpoint_dir is not None:  # FR-5's start: the snapshot, then the start's parts.
            from cells.records.io import write_snapshot

            if sink.record_s[-1] != final.time:
                raise ValueError("FR-5's start needs a record at the run's end")
            write_snapshot(checkpoint_dir, spec, final)
            out["start_nodes"], out["start_readouts"] = sink.start()
    out.update(sink.record(completed=True))
    out.update(
        completed=True,
        steps=steps,
        diagnostics=diagnostics,
        timings=timings,
        resources={k: v for k, v in resources.items() if np.isscalar(v)},
    )
    return out
