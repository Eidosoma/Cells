"""FR-3's planted controls, each in its own process, by checkpoint edits (the lead's ruling).

Q5's controls of fr3-site-occupancy-v1 (validation/tissue/site_occupancy_acceptance_protocol.json).
The generator's Q5_material_plants and Q5_energy_plants parts run this module as a subprocess, one
plant per process, so no plant can reach a judged world. No engine code is patched: each plant
runs a registered world to PLANT_AT_S, recorded at every step, edits the checkpoint's state at that
row, and records the edited row's terms and the engine's verdict on resuming from it (the runner's
validate_checkpoint runs the model's row checks on the checkpoint). Each writes one JSON bundle
with the plant's identity and size, the unplanted rows, the planted row and the verdict.

* **move** (q5_passive_from_zero, passive): the facing node's free ligand raised by
  MATERIAL_RELATIVE of the population's net bound amount, its accumulator unchanged: @3's
  outside ledger;
* **bound** (the same world): B raised by MATERIAL_RELATIVE of B, R unchanged: the operator's own
  ledgers (the bound and moiety identities);
* **work** (q1_eps_1e-1, mixed): the population's booked work x (1 + WORK_RELATIVE), the
  references' registered energy control;
* **heat_sign** (q5_passive_from_zero): the facing node's heat negated;
* **site_free_energy** (q5_passive_from_zero): the facing node's heat set to H + dG_site, the heat
  a booking without the site term books (-dG_node), with dG_site = G_site(t) - G_site(0) from
  Appendix A.3's form, computed here from the checkpoint's B and R (the lead's ruling 4).
The judge detects the energy plants by the guard of record on the edited row (the lead's ruling
3); the engine's own verdict is recorded beside it.

Usage: python -m validation.tissue.site_occupancy_acceptance_plants PLANT OUT_JSON
"""

import dataclasses
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

from validation.tissue import site_occupancy_acceptance_fixtures as af

PLANT_AT_S = 1.0
RESUME_STEPS = 10  # The resumed run's horizon after the planted row (its verdict).
MATERIAL_RELATIVE = 1e-6
WORK_RELATIVE = 1e-6  # The references' registered control: the work x (1 + 1e-6).
PASSIVE, MIXED = "q5_passive_from_zero", "q1_eps_1e-1"
PLANTS = ("move", "bound", "work", "heat_sign", "site_free_energy")
N_A, K_B = 6.02214076e23, 1.380649e-23  # SI 2019, exact.


def every_step(raw, end):
    """The world to `end` (its schedule changes before it), recorded at every step."""
    from validation.tissue import site_occupancy_acceptance_qualification as generator

    head = generator._head(raw, end)
    dt = head["execution"]["dt"]
    head["experiment"]["observation_times"] = [k * dt for k in range(round(end / dt) + 1)]
    return head


def site_free_energy_pJ(bound, free, capacity, k_d_mM, temperature_K):
    """Appendix A.3's G_site = B (dG0 + RT ln(B/S)) + RT R ln(R/S), dG0 = RT ln(K_d / 1 mM),
    0 ln 0 = 0, RT = 1e-3 R T pJ/fmol with R = N_A k_B (exact)."""
    rt = 1e-3 * N_A * K_B * temperature_K

    def xlnx(x):
        return 0.0 if x == 0.0 else x * math.log(x / capacity)

    return bound * rt * math.log(k_d_mM) + rt * (xlnx(bound) + xlnx(free))


def _planted(world_id, edit, identity):
    """The unplanted rows to PLANT_AT_S, the edited row's terms, and the engine's verdict on
    resuming from the edited checkpoint."""
    from cells.core.errors import NumericalError
    from cells.core.runner import run
    from cells.core.specs import ConfigError, parse_spec
    from cells.models.registry import get_model
    from validation.tissue import site_occupancy_acceptance_qualification as generator

    raw = af.registered_world(world_id)
    head = every_step(raw, PLANT_AT_S)
    result = run(parse_spec(head))
    records = generator.records_of(result, head)
    spec = result.spec
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    state = model.STATE_TYPE(*(np.asarray(v).copy() for v in result.final.state))
    state, size = edit(spec, p, state)
    planted = dataclasses.replace(result.final, state=state)
    steps = int(result.final.step_index)
    populations = generator.declared_populations(head)
    row = generator.series_of_state(model, spec, p, state, steps, populations)
    dt = spec.execution.dt
    resume = every_step(raw, PLANT_AT_S + RESUME_STEPS * dt)
    verdict = dict(refused=False, message=None, kind=None)
    try:
        run(parse_spec(resume), planted)
    except (NumericalError, ConfigError) as error:
        verdict = dict(refused=True, message=str(error), kind=type(error).__name__)
    return dict(plant=dict(identity, world=world_id, at_s=PLANT_AT_S, **size),
                prefix=records, planted=dict(record_ms=generator.ms(float(result.final.time)),
                                             step=steps, series=row),
                engine=verdict)


def _indices(spec, population="r0"):
    """(the ligand's row, the facing node's outside index, the population's index)."""
    m = spec.model
    s = list(m.species_ids).index(af.LIGAND)
    o = [c.id for c in m.extracellular].index("ecs_0")
    return s, o, 0 if population == "r0" else None


def move():
    def edit(spec, p, state):
        s, o, k = _indices(spec)
        booked = float(np.asarray(state.site_bound_net_fmol)[k])
        extra = MATERIAL_RELATIVE * booked
        increment = np.asarray(state.extracellular_amount_increment).copy()
        increment[s, o] += extra
        return state._replace(extracellular_amount_increment=increment), dict(
            booked_net_fmol=booked, absolute_fmol=extra)

    return _planted(PASSIVE, edit, dict(
        kind="move", field="extracellular_amount_increment[S, ecs_0] (net binding's accumulator "
        "unchanged)", relative=MATERIAL_RELATIVE, checks=["ledger:outside"],
        passing=["local"]))


def bound():
    def edit(spec, p, state):
        _, _, k = _indices(spec)
        b = float(np.asarray(p.site_bound_anchor_fmol)[k]
                  + np.asarray(state.site_bound_increment_fmol)[k])
        extra = MATERIAL_RELATIVE * b
        increment = np.asarray(state.site_bound_increment_fmol).copy()
        increment[k] += extra
        return state._replace(site_bound_increment_fmol=increment), dict(
            bound_fmol=b, absolute_fmol=extra)

    return _planted(PASSIVE, edit, dict(
        kind="bound", field="site_bound_increment_fmol[r0] (R unchanged)",
        relative=MATERIAL_RELATIVE, checks=["ledger:site_bound_entity"],
        passing=["local", "outside", "total"]))


def work():
    def edit(spec, p, state):
        _, _, k = _indices(spec)
        values = np.asarray(state.site_work_pJ).copy()
        booked = float(values[k])
        values[k] = booked * (1.0 + WORK_RELATIVE)
        return state._replace(site_work_pJ=values), dict(
            booked_work_pJ=booked, absolute_pJ=booked * WORK_RELATIVE)

    return _planted(MIXED, edit, dict(
        kind="work", field="site_work_pJ[r0]", relative=WORK_RELATIVE, checks=["closure"],
        passing=["local", "outside", "total", "site_bound_entity", "site_moiety_entity"]))


def _heat_edit(new_heat):
    def edit(spec, p, state):
        _, o, _ = _indices(spec)
        values = np.asarray(state.site_outside_dissipated_energy_pJ).copy()
        booked = float(values[o])
        values[o], size = new_heat(spec, p, state, booked)
        return state._replace(site_outside_dissipated_energy_pJ=values), dict(
            booked_heat_pJ=booked, planted_heat_pJ=float(values[o]), **size)
    return edit


def heat_sign():
    edit = _heat_edit(lambda spec, p, state, h: (-h, dict(absolute_pJ=2.0 * abs(h))))
    return _planted(PASSIVE, edit, dict(
        kind="heat_sign", field="site_outside_dissipated_energy_pJ[ecs_0], negated",
        checks=["closure", "dissipation"],
        passing=["local", "outside", "total", "site_bound_entity", "site_moiety_entity"]))


def site_free_energy():
    def new_heat(spec, p, state, h):
        capacity = float(np.asarray(p.site_capacity_fmol)[0])
        b0 = float(np.asarray(p.site_bound_anchor_fmol)[0])
        r0 = float(np.asarray(p.site_free_anchor_fmol)[0])
        b = b0 + float(np.asarray(state.site_bound_increment_fmol)[0])
        r = r0 + float(np.asarray(state.site_free_increment_fmol)[0])
        pop = af.registered(PASSIVE)["populations"][0]
        k_d = pop["dissociation_rate_per_s"] / pop["association_rate_per_mM_per_s"]
        t = float(spec.model.temperature_K)
        dg = (site_free_energy_pJ(b, r, capacity, k_d, t)
              - site_free_energy_pJ(b0, r0, capacity, k_d, t))
        return h + dg, dict(dG_site_pJ=dg, absolute_pJ=abs(dg))

    return _planted(PASSIVE, _heat_edit(new_heat), dict(
        kind="site_free_energy", field="site_outside_dissipated_energy_pJ[ecs_0] = H + dG_site "
        "(the heat a booking without the site term books)", checks=["closure", "dissipation"],
        passing=["local", "outside", "total", "site_bound_entity", "site_moiety_entity"]))


def main(argv):
    if len(argv) != 2 or argv[0] not in PLANTS:
        raise SystemExit(__doc__)
    started = time.perf_counter()
    out = dict(move=move, bound=bound, work=work, heat_sign=heat_sign,
               site_free_energy=site_free_energy)[argv[0]]()
    out["wall_s"] = time.perf_counter() - started
    from validation.tissue import site_occupancy_acceptance_qualification as generator

    Path(argv[1]).write_text(json.dumps(generator.plain(out), indent=1, allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
