"""FR-1's planted controls, each in its own process (the lead's ruling of 17 November 2026).

C13 and K3 of fr1-closed-compartment-v1 (validation/tissue/compartment_acceptance_protocol.json).
The generator's C13_controls and K3_planted parts run this module as a subprocess, one plant per
process, so no plant can reach a judged world; each writes one JSON bundle with the plant's
identity and size, its rows and the engine's verdict on them.

* **move** (C13, a misbooked move): C3's first-order loading under ARS at 1 ms, recorded at every
  step to MOVE_AT_S; there the compartment's S is raised by MOVE_RELATIVE of the route's booked
  move, its accumulator unchanged. The rows before it are the unplanted run's; the planted row is
  the edited checkpoint, which the engine validates on resuming (cells.core.runner:
  validate_checkpoint runs the model's row checks on it).
* **work** (C13, a misbooked work): C10's RK4 world (first-order loading at 0.1 ms) to WORK_AT_S;
  there the route's booked work is scaled by 1 + WORK_RELATIVE.
* **route** and **anchor** (K3): W+ with milestone 1's planted controls, a K route of 1e-13 m/s on
  the bounding patch and a 1e-17 C compartment anchor, admitted through milestone 1's test-only
  bypass of refusals 4 and 5 (the declaration's refuse_ion_routes and refuse_charge_anchor
  replaced in this process only); S1 and S2 at every row.

Usage: python -m validation.tissue.compartment_acceptance_plants PLANT OUT_JSON
"""

import copy
import dataclasses
import json
import sys
import time
from pathlib import Path

import numpy as np

from validation.tissue import compartment_acceptance_fixtures as af
from validation.tissue import compartment_fixtures as cf
from validation.tissue import secreted_species_fixtures as fx

MOVE_AT_S, MOVE_END_S, MOVE_RELATIVE = 0.1, 0.2, 1e-6
# The work's plant: 2e-3 of the booked work at 0.3 s. The lead accepted 1e-4 on an estimate of the
# booked work (about 2.6e-3 pJ) that the first development run measured at 2.1e-4 pJ, a margin of
# 1.06 over RK4's absolute 2e-8 pJ; 2e-3 gives about 21, above the ruling's 10.
WORK_AT_S, WORK_END_S, WORK_RELATIVE = 0.3, 0.4, 2e-3
K3_END_S = 0.02
PLANTS = ("move", "work", "route", "anchor")


def _prefix(raw, at):
    """The world run to `at`, recorded at every step: (result, its records)."""
    from cells.core.runner import run
    from cells.core.specs import parse_spec
    from validation.tissue import compartment_acceptance_qualification as generator

    head = copy.deepcopy(raw)
    dt = head["execution"]["dt"]
    head["experiment"]["end_time"] = at
    head["experiment"]["observation_times"] = fx.grid_times(at, dt, dt)
    result = run(parse_spec(head))
    return result, generator.records_of(result, head)


def _row_ratios(model, spec, state, steps):
    """Every ledger's |balance| over its bound at one row (the records' ratio_LEDGER)."""
    from cells.models.surface_pump import ENERGY_RTOL
    from validation.tissue import compartment_acceptance_qualification as generator

    _, p = model.initial_values(spec)
    x = spec.execution
    balances = model.balances(state, p)
    magnitudes = model.magnitudes(state, p)
    _, bounds = model.ledger_limits(state, p, np.asarray(x.material_balance_atol_fmol),
                                    ENERGY_RTOL[x.solver], steps=steps, magnitudes=magnitudes)
    names = list(model.LEDGERS)
    return {name: generator._ratio(balances[name], bounds[k])
            for k, name in enumerate(names) if name in balances}


def _planted(raw, at, edit, identity):
    """The unplanted rows to `at`, the edited checkpoint's ratios, and the engine's verdict on
    resuming from it."""
    from cells.core.errors import NumericalError
    from cells.core.runner import run
    from cells.core.specs import ConfigError, parse_spec
    from cells.models.registry import get_model

    spec = parse_spec(raw)
    model = get_model(spec.model)
    result, records = _prefix(raw, at)
    state = model.STATE_TYPE(*(np.asarray(v).copy() for v in result.final.state))
    state, size = edit(spec, model, state)
    planted = dataclasses.replace(result.final, state=state)
    ratios = _row_ratios(model, spec, state, result.final.step_index)
    verdict = dict(refused=False, message=None)
    try:
        run(spec, planted)
    except (NumericalError, ConfigError) as error:
        verdict = dict(refused=True, message=str(error), kind=type(error).__name__)
    prefix_max = {k[len("ratio_"):]: max(v) for k, v in records["series"].items()
                  if k.startswith("ratio_")}
    return dict(plant=dict(identity, **size), prefix_rows=len(records["record_s"]),
                prefix_max_ratio=prefix_max, planted_row_s=float(result.final.time),
                planted_step=int(result.final.step_index), planted_ratios=ratios,
                engine=verdict)


def move():
    raw = af.first_order_loading(end=MOVE_END_S)
    species, node = fx.SPECIES, af.NODE

    def edit(spec, model, state):
        s = list(spec.model.species_ids).index(species)
        o = [c.id for c in spec.model.extracellular].index(node)
        booked = float(np.asarray(state.exchange_moved_fmol)[0])
        extra = MOVE_RELATIVE * booked
        increment = np.asarray(state.extracellular_amount_increment).copy()
        increment[s, o] += extra
        return state._replace(extracellular_amount_increment=increment), dict(
            booked_move_fmol=booked, absolute_fmol=extra)

    return _planted(raw, MOVE_AT_S, edit, dict(
        kind="move", world="C3's first-order loading, ARS at 1 ms", field=(
            "extracellular_amount_increment[S, ecs_0] (the route's accumulator unchanged)"),
        relative=MOVE_RELATIVE, at_s=MOVE_AT_S, expected_ledger="outside"))


def work():
    raw = af.first_order_loading(dt=af.RK4_DT, solver=af.RK4, end=WORK_END_S)

    def edit(spec, model, state):
        work_ = np.asarray(state.exchange_work_pJ).copy()
        booked = float(work_[0])
        work_[0] = booked * (1.0 + WORK_RELATIVE)
        return state._replace(exchange_work_pJ=work_), dict(
            booked_work_pJ=booked, absolute_pJ=booked * WORK_RELATIVE)

    return _planted(raw, WORK_AT_S, edit, dict(
        kind="work", world="C10's RK4 world: first-order loading at 0.1 ms",
        field="exchange_work_pJ[load]", relative=WORK_RELATIVE, at_s=WORK_AT_S,
        expected_ledger="energy"))


def _silence_rows(spec, observations):
    """S1 and S2 at every row (compartment_fixtures.silence's definitions, row by row)."""
    from cells.models.registry import get_model
    from cells.numerics import surface_field as field

    model = get_model(spec.model)
    state, _ = model.initial_values(spec)
    ions = [i for i, z in enumerate(spec.model.valence) if z != 0]
    j = [c.id for c in spec.model.extracellular].index(cf.NODE)
    k = [p.id for p in spec.model.membranes].index(cf.PATCH)
    initial = np.asarray(state.extracellular_amount_increment)[ions, j]
    rows = np.asarray(observations.extracellular_amount_increment)[:, ions, j]
    s1 = [bool(r.tobytes() == initial.tobytes()) for r in rows]
    c_b = spec.model.membranes[k].capacitance_F
    v = np.asarray(observations.membrane_voltage_V)[:, k]
    allowance = field.CHARGE_ATOL_C + field.CHARGE_RTOL * np.abs(c_b * v)
    s2 = (np.abs(v) / (allowance / c_b)).tolist()
    return s1, s2


def _k3(planted):
    from cells.core.runner import run
    from cells.core.specs import parse_spec
    from cells.models.operators import compartments as comp

    comp.refuse_ion_routes = lambda *a: None  # Milestone 1's bypass, in this process only.
    comp.refuse_charge_anchor = lambda *a: None
    every = fx.grid_times(K3_END_S, 1e-3, 1e-3)
    kwargs = dict(planted_route=cf.PLANTED_ROUTE) if planted == "route" else dict(
        planted_anchor=cf.PLANTED_ANCHOR_C)
    spec = parse_spec(cf.live_compartment(end=K3_END_S, dt=1e-3, observation_times=every,
                                          **kwargs))
    result = run(spec)
    s1, s2 = _silence_rows(spec, result.observations)
    return dict(plant=dict(kind=planted, **{k: float(v) for k, v in kwargs.items()},
                           bypass="refusals 4 and 5 replaced in this process (milestone 1's)"),
                record_s=[float(t) for t in result.observations.times], s1_rows=s1, s2_rows=s2)


def main(argv):
    if len(argv) != 2 or argv[0] not in PLANTS:
        raise SystemExit(__doc__)
    started = time.perf_counter()
    out = {"move": move, "work": work}.get(argv[0], lambda: _k3(argv[0]))()
    out["wall_s"] = time.perf_counter() - started
    Path(argv[1]).write_text(json.dumps(out, indent=1, allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
