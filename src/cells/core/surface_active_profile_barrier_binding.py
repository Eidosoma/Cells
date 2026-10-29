"""Coefficient capabilities for the two native schedules, never physical state."""

from types import SimpleNamespace

import numpy as np

from cells.core import surface_barrier_interventions_binding as barriers
from cells.core import surface_profile_interventions_spec as membranes
from cells.core.specs import ConfigError
from cells.processes import betse_tissue_profiles as native


def views(spec):
    m = spec.model
    provenance = m.coupled_preparation["provenance"]
    values = vars(m) | dict(
        profile_preparation=provenance["profile_preparation"],
        interventions=m.membrane_interventions,
        barrier_preparation=provenance["barrier_preparation"],
        intervention=m.barrier_intervention,
    )
    return SimpleNamespace(
        model=SimpleNamespace(**values), execution=spec.execution, experiment=spec.experiment
    )


def native_parameters(spec, parent):
    declarations = views(spec)
    m = declarations.model
    view, _, events, dynamic, baseline, coefficient = membranes.bindings(m, spec.execution)
    count = spec.execution.membrane_capacity
    index, thickness = np.zeros(count, dtype=np.int64), np.ones(count)
    for i, row in enumerate(m.membranes):
        index[i] = view.layout.membrane_ids.index(row.id)
        thickness[i] = view.thickness_m[row.id]
    values = {"intervention_" + key: value for key, value in events.kernel._asdict().items()}
    values.update(
        intervention_dynamic_factor=dynamic,
        native_baseline_m2_s=baseline,
        native_event_coefficient_m2_s=coefficient,
        membrane_native_index=index,
        membrane_thickness_m=thickness,
        species_native_index=np.asarray([native.IONS.index(s) for s in m.species_ids]),
        species_native_supported=np.asarray([s in native.IONS for s in m.species_ids]),
        profile_sim=np.asarray(m.phase == "SIM"),
    )
    return values | barriers.native_parameters(declarations, parent)


def check_ramp_steps(spec, steps):
    if spec.model.phase != "SIM":
        return
    events = (
        *spec.model.membrane_interventions,
        *((spec.model.barrier_intervention,) if spec.model.barrier_intervention else ()),
    )
    if not events:
        return
    ceiling = min(event.change_s / 8 for event in events)
    if spec.execution.dt > ceiling * (1 + 16 * np.finfo(float).eps):
        raise ConfigError("Combined nominal dt must resolve both transition times/8")
    allowance = max(2 * np.spacing(spec.experiment.end_time), 16 * np.finfo(float).eps * ceiling)
    if np.max(steps, initial=0) > ceiling + allowance:
        raise ConfigError("Combined RK4 steps must resolve both transition times/8")
