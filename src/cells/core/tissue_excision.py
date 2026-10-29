"""Conservative cell removal with full source provenance and absolute clocks.

This first adapter supports passive resolved tissue. Post-cut reference amounts
are the actual surviving amounts; new local ledgers start at the cut, while all
old ledgers remain in the immutable source record. Field solvability is checked
without silently neutralizing nodes or projecting charge.
"""

import math
from bisect import bisect_right
from copy import deepcopy
from dataclasses import dataclass

import numpy as np

from cells.core.grid import EventGrid
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, _fields, parse_spec
from cells.core.state import Checkpoint
from cells.core.surface_excision_spec import MODEL_ID, POLICIES, SurfaceExcisionModel, base_spec
from cells.core.surface_tissue_spec import SurfaceTissueModel
from cells.models import surface_tissue as passive
from cells.models.registry import get_model
from cells.processes import betse_tissue_cut as removal
from cells.processes.electrochemistry import CHARGE_PER_FMOL, R


@dataclass(frozen=True)
class ExcisionResult:
    source_spec: object
    source_checkpoint: Checkpoint
    spec: object | None
    checkpoint: Checkpoint | None
    report: dict


def ordinary(spec):
    if type(spec.model) is SurfaceTissueModel:
        return spec
    if type(spec.model) is SurfaceExcisionModel:
        return base_spec(spec)
    raise ConfigError(
        "Excision supports passive resolved tissue; other owners need explicit adapters"
    )


def _point_check(spec, point):
    ordinary(spec)
    implementation = get_model(spec.model)
    state0, layout = implementation.initial_values(spec)
    start = getattr(spec.model, "epoch_start_time", 0.0)
    if (
        isinstance(point.time, bool)
        or not isinstance(point.time, (int, float))
        or not math.isfinite(point.time)
        or point.time < start
        or point.time > spec.experiment.end_time
        or type(point.step_index) is not int
        or type(point.event_index) is not int
        or EventGrid(spec).exact_index(point.time) != point.step_index
        or event_index(spec, point.time) != point.event_index
        or type(point.state) is not implementation.STATE_TYPE
        or type(point.layout) is not implementation.LAYOUT_TYPE
    ):
        raise ConfigError("Invalid complete excision source checkpoint or absolute clock")
    for value, template in zip(point.state, state0, strict=True):
        if np.asarray(value).shape != template.shape or np.asarray(value).dtype != template.dtype:
            raise ConfigError("Excision source state shape or precision disagrees")
    if any(
        np.asarray(a).dtype != b.dtype or not np.array_equal(a, b)
        for a, b in zip(point.layout, layout, strict=True)
    ):
        raise ConfigError("Excision source layout does not match its definition")
    if point.time == start and any(
        not np.array_equal(a, b) for a, b in zip(point.state, state0, strict=True)
    ):
        raise ConfigError("Excision source initial state does not match its epoch")
    implementation.check_values(point.state, spec)
    table = control_values(spec, [point.time])
    u = type(table)(*(v[0] for v in table))
    if not implementation.control_domain_valid(point.state, u, layout, layout.active, xp=np):
        raise ConfigError("Excision source has an invalid actual-control field")


def capture_source(spec, point):
    _point_check(spec, point)
    return dict(
        definition=spec.to_dict(),
        checkpoint=dict(
            time=point.time,
            step_index=point.step_index,
            event_index=point.event_index,
            state={k: np.asarray(v).tolist() for k, v in point.state._asdict().items()},
            layout={k: np.asarray(v).tolist() for k, v in point.layout._asdict().items()},
        ),
    )


def decode_source(source):
    _fields(source, {"definition", "checkpoint"}, "excision source")
    spec = parse_spec(source["definition"])
    ordinary(spec)
    cp = _fields(
        source["checkpoint"],
        {"time", "step_index", "event_index", "state", "layout"},
        "source checkpoint",
    )
    model = get_model(spec.model)
    _fields(cp["state"], set(model.STATE_TYPE._fields), "complete source state")
    initial, template = model.initial_values(spec)
    _fields(cp["layout"], set(template._fields), "complete source layout")

    def array(raw, v):
        value = np.asarray(raw)
        if value.size:
            allowed = "fiu" if v.dtype.kind == "f" else "iu" if v.dtype.kind in "iu" else "b"
            if value.dtype.kind not in allowed:
                raise ConfigError("Excision source array numeric type disagrees")
        value = value.astype(v.dtype)
        if value.size == v.size == 0:
            # JSON cannot retain trailing dimensions behind a zero-length axis.
            value = value.reshape(v.shape)
        return value

    try:
        state = model.STATE_TYPE(*(array(cp["state"][k], v) for k, v in initial._asdict().items()))
        layout = model.LAYOUT_TYPE(
            *(array(cp["layout"][k], v) for k, v in template._asdict().items())
        )
    except (ValueError, TypeError) as error:
        raise ConfigError("Require numeric complete source arrays") from error
    point = Checkpoint(state, layout, cp["time"], cp["step_index"], cp["event_index"])
    _point_check(spec, point)
    return spec, point


def topology(spec):
    m = spec.model
    cells, outside = [v.id for v in m.cells], [v.id for v in m.extracellular]
    return removal.validate_topology(
        removal.Topology(
            tuple(cells),
            tuple(v.id for v in m.membranes),
            tuple(v.id for v in m.junctions),
            tuple(outside),
            np.array([cells.index(v.inside) for v in m.membranes], dtype=np.int64),
            np.array([outside.index(v.outside) for v in m.membranes], dtype=np.int64),
            np.array(
                [[cells.index(v.sender), cells.index(v.receiver)] for v in m.junctions],
                dtype=np.int64,
            ).reshape(-1, 2),
            np.full((len(m.junctions), 2), -1, dtype=np.int64),
            np.zeros(len(m.junctions), dtype=bool),
        )
    )


def _physical(spec, point):
    p, y = point.layout, point.state
    n, o = len(spec.model.cells), len(spec.model.extracellular)
    inside, outside = passive.physical_amounts(y, p)
    charge = passive.charge_increment(y, p, xp=np)
    table = control_values(spec, [point.time])
    u = type(table)(*(v[0] for v in table))
    field = passive.field_values(y, u, p, xp=np)
    if not field.converged:
        raise ConfigError("Excision field did not converge")
    return dict(
        amount=inside[:, :n],
        outside_amount=outside[:, :o],
        charge=(p.initial_cell_charge_C + charge[: len(p.active)])[:n],
        outside_charge=(p.initial_outside_charge_C + charge[len(p.active) :])[:o],
        voltage=field.rates.membrane_voltage_V[: len(spec.model.membranes)],
        electrode=field.electrode_charge_C[:o],
        potential=field.potential_V,
    )


def derive_tissue(spec, point, removed_ids):
    """Return surviving ordinary model data and an explicit owner-based remap."""
    _point_check(spec, point)
    raw = ordinary(spec).to_dict()["model"]
    try:
        plan = removal.plan_cut(topology(spec), removed_ids)
    except (ValueError, TypeError) as error:
        raise ConfigError("Invalid cell removal: " + str(error)) from error
    physical = _physical(spec, point)
    m = spec.model
    fields = dict(
        cell_amount_fmol=removal.OwnedField(
            physical["amount"], "cell", kind="quantity", units="fmol", nonnegative=True
        ),
        extracellular_amount_fmol=removal.OwnedField(
            physical["outside_amount"],
            "environment",
            kind="quantity",
            units="fmol",
            nonnegative=True,
        ),
        cell_volume_pL=removal.OwnedField(
            np.asarray([v.volume_pL for v in m.cells]),
            "cell",
            kind="quantity",
            units="pL",
            nonnegative=True,
        ),
        cell_fixed_charge_C=removal.OwnedField(
            CHARGE_PER_FMOL * np.asarray([v.fixed_charge_equivalent_fmol for v in m.cells]),
            "cell",
            kind="quantity",
            units="C",
        ),
        cell_net_charge_C=removal.OwnedField(physical["charge"], "cell", kind="state"),
        membrane_capacitor_energy_pJ=removal.OwnedField(
            0.5e12 * np.asarray([v.capacitance_F for v in m.membranes]) * physical["voltage"] ** 2,
            "membrane",
            kind="quantity",
            units="pJ",
            nonnegative=True,
        ),
    )
    domains = {
        "cell_slot": "cell",
        "extracellular_slot": "environment",
        "membrane_slot": "membrane",
        "edge_slot": "edge",
    }
    for key, axes in passive.STATE_AXES.items():
        domain = domains.get(axes[-1])
        count = len(getattr(plan.before, domain + "_ids")) if domain else len(m.faces)
        fields["history_" + key] = removal.OwnedField(
            np.asarray(getattr(point.state, key))[..., :count],
            domain or "global",
            axis=-1 if domain else None,
            kind="state",
        )
    result = removal.apply_cut(plan.before, removed_ids, fields)
    if not plan.after.cell_ids:
        return None, result, physical
    for key, ids in (
        ("cells", plan.after.cell_ids),
        ("membranes", plan.after.membrane_ids),
        ("junctions", plan.after.edge_ids),
    ):
        raw[key] = [v for v in raw[key] if v["id"] in ids]
    for key, amount, charge in (
        (
            "cells",
            physical["amount"][:, plan.new_to_old["cell"]],
            physical["charge"][plan.new_to_old["cell"]],
        ),
        ("extracellular", physical["outside_amount"], physical["outside_charge"]),
    ):
        for i, row in enumerate(raw[key]):
            row["initial_amount_fmol"] = dict(
                zip(m.species_ids, amount[:, i].tolist(), strict=True)
            )
            row["initial_charge_C"] = float(charge[i])
    return raw, result, physical


def _experiment(spec, tissue, time):
    e = deepcopy(ordinary(spec).to_dict()["experiment"])
    for kind in ("membrane", "junction"):
        ids = {v["id"] for v in tissue[kind + "s"]}
        e[kind + "_controls"] = [v for v in e[kind + "_controls"] if v[kind + "_id"] in ids]
    # Retain every source control boundary, including removed-route-only edges.
    carrier = e["membrane_controls"][0]["schedule"]
    clocks = [v["time"] for v in carrier]
    times = sorted({time, *(v.time for v in spec.experiment.changes), *clocks})
    e["membrane_controls"][0]["schedule"] = [
        dict(time=t, availability=carrier[bisect_right(clocks, t) - 1]["availability"])
        for t in times
    ]
    e["observation_times"] = sorted({time, *(t for t in e["observation_times"] if t >= time)})
    return e


def _chemical_terms(amount, volume, temperature):
    return 1e-3 * R * temperature * amount * (np.log(amount / np.asarray(volume)) - 1)


def transition_report(spec, point, result, before, after_spec=None, after_point=None):
    plan, m = result.plan, spec.model
    removed, kept = plan.removed["cell"], plan.new_to_old["cell"]
    ionic = result.fields["cell_amount_fmol"]
    cell_terms = _chemical_terms(before["amount"], [v.volume_pL for v in m.cells], m.temperature_K)
    outer_terms = _chemical_terms(
        before["outside_amount"], [v.volume_pL for v in m.extracellular], m.temperature_K
    )
    cap = result.fields["membrane_capacitor_energy_pJ"]
    report = dict(
        law=removal.LAW_ID,
        changed=plan.changed,
        terminal=not bool(plan.after.cell_ids),
        time_s=point.time,
        before_layout_identity=plan.before_identity,
        after_layout_identity=plan.after_identity,
        removed_cell_ids=list(result.removed_owner_ids["cell"]),
        retained_cell_ids=list(plan.after.cell_ids),
        species_ids=list(m.species_ids),
        physical_policy=(
            "Excise cell-owned material and capacitors; "
            "no release into exterior or hidden charge correction"
        ),
        junction_policy=(
            "Abstract junction endpoints; "
            "this model declares no physical contact faces or wound exposure"
        ),
        history_policy=POLICIES["state_policy"],
        source_clock=dict(
            time=point.time, step_index=point.step_index, event_index=point.event_index
        ),
        removed_amount_fmol=ionic.removed_quantity.tolist(),
        retained_amount_fmol=ionic.retained.tolist(),
        material_residual_fmol=np.asarray(ionic.balance_residual).tolist(),
        removed_net_charge_C=before["charge"][removed].tolist(),
        removed_fixed_charge_C=result.fields["cell_fixed_charge_C"].removed_quantity.tolist(),
        removed_volume_pL=result.fields["cell_volume_pL"].removed_quantity.tolist(),
        removed_capacitor_energy_pJ=cap.removed_quantity.tolist(),
        removed_chemical_energy_pJ=math.fsum(cell_terms[:, removed].ravel()),
        before_chemical_energy_pJ=math.fsum([*cell_terms.ravel(), *outer_terms.ravel()]),
        before_capacitor_energy_pJ=float(cap.previous_total),
        archived_retained_history={
            k.removeprefix("history_"): v.retained.tolist()
            for k, v in result.fields.items()
            if k.startswith("history_")
        },
        archived_removed_history={
            k.removeprefix("history_"): v.removed_values.tolist()
            for k, v in result.fields.items()
            if k.startswith("history_")
        },
        energy_claim=(
            "Transition diagnostics only; "
            "no mechanical cutting-work law or full native tissue trajectory equivalence"
        ),
    )
    if after_spec is None:
        report["continuation"] = "terminal archive; no zero-cell electrical solver is implied"
        return report
    after = _physical(after_spec, after_point)
    for actual, expected in (
        (after["amount"], before["amount"][:, kept]),
        (after["outside_amount"], before["outside_amount"]),
        (after["charge"], before["charge"][kept]),
        (after["outside_charge"], before["outside_charge"]),
    ):
        if not np.array_equal(actual, expected):
            raise ConfigError("Excision changed surviving physical material or charge")
    old_v = before["voltage"][plan.new_to_old["membrane"]]
    new_v = after["voltage"]
    cap_values = np.asarray([v.capacitance_F for v in after_spec.model.membranes])
    cap_jump = math.fsum(0.5e12 * cap_values * (new_v - old_v) * (new_v + old_v))
    impulse = after["electrode"] - before["electrode"]
    boundary = np.asarray([v.boundary_potential_V for v in m.extracellular])
    work = 1e12 * float(np.dot(boundary, impulse))
    report.update(
        after_chemical_energy_pJ=math.fsum([*cell_terms[:, kept].ravel(), *outer_terms.ravel()]),
        after_capacitor_energy_pJ=math.fsum(0.5e12 * cap_values * new_v**2),
        retained_capacitor_energy_jump_pJ=cap_jump,
        electrode_charge_impulse_C=impulse.tolist(),
        held_boundary_work_impulse_pJ=work,
        unresolved_cut_energy_pJ=cap_jump - work,
        unresolved_energy_interpretation=(
            "Remainder after removed-owned energy and clamp work; diagnostic in the declared "
            "potential reference, not fitted or predicted cut work"
        ),
        postcut_voltage_V=new_v.tolist(),
        exterior_amount_fmol=after["outside_amount"].tolist(),
        solver_rebuilt=True,
    )
    return report


def excise(spec, checkpoint, removed_cell_ids):
    """Create a validated continuation or a terminal archive; inputs are untouched."""
    spec = parse_spec(spec.to_dict())
    source = capture_source(spec, checkpoint)
    tissue, result, before = derive_tissue(spec, checkpoint, removed_cell_ids)
    if not result.plan.changed:
        report = transition_report(spec, checkpoint, result, before, spec, checkpoint)
        report["history_policy"] = "unchanged source identity, clock and all ledgers"
        return ExcisionResult(spec, checkpoint, spec, checkpoint, report)
    if tissue is None:
        return ExcisionResult(
            spec, checkpoint, None, None, transition_report(spec, checkpoint, result, before)
        )
    raw = dict(
        schema_version=1,
        model=dict(
            id=MODEL_ID,
            tissue=tissue,
            excision=dict(POLICIES, source=source, removed_cell_ids=list(removed_cell_ids)),
        ),
        experiment=_experiment(spec, tissue, checkpoint.time),
        execution=ordinary(spec).to_dict()["execution"],
    )
    after = parse_spec(raw)
    implementation = get_model(after.model)
    state, layout = implementation.initial_values(after)
    point = Checkpoint(
        state,
        layout,
        checkpoint.time,
        EventGrid(after).exact_index(checkpoint.time),
        event_index(after, checkpoint.time),
    )
    _point_check(after, point)
    report = transition_report(spec, checkpoint, result, before, after, point)
    return ExcisionResult(spec, checkpoint, after, point, report)
