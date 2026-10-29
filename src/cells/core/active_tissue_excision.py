"""Remove active tissue owners while preserving intrinsic physiological state.

The nineteen-field source is archived completely. Chemical/charge anchors are
rebased to actual survivors; seventeen local ledgers restart, and surviving
channel/junction gates retain their values. Maintained pump fuel is a boundary
condition, not a finite ATP pool or a removed material inventory.
"""

import math
from bisect import bisect_right
from copy import deepcopy

import numpy as np

from cells.core.grid import EventGrid
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, _fields, parse_spec
from cells.core.state import Checkpoint
from cells.core.surface_active_excision_spec import (
    MODEL_ID,
    POLICIES,
    SurfaceActiveExcisionModel,
    base_spec,
)
from cells.core.surface_kinetic_spec import SurfaceHCNExtraModel
from cells.core.tissue_excision import ExcisionResult, _chemical_terms, topology
from cells.models import surface_hcn_extra as active
from cells.models import surface_tissue as passive
from cells.models.registry import get_model
from cells.processes import betse_tissue_cut as removal
from cells.processes.electrochemistry import CHARGE_PER_FMOL

GATES = ("channel_gate", "junction_gate")


def ordinary(spec):
    if type(spec.model) is SurfaceHCNExtraModel:
        return spec
    if type(spec.model) is SurfaceActiveExcisionModel:
        return base_spec(spec)
    raise ConfigError("Active excision requires resolved_tissue@12 or its excision epoch")


def _point_check(spec, point):
    ordinary(spec)
    implementation = get_model(spec.model)
    initial, layout = implementation.initial_values(spec)
    start = getattr(spec.model, "epoch_start_time", 0.0)
    if (
        type(point) is not Checkpoint
        or isinstance(point.time, bool)
        or not isinstance(point.time, (int, float))
        or not math.isfinite(point.time)
        or not start <= point.time <= spec.experiment.end_time
        or type(point.step_index) is not int
        or type(point.event_index) is not int
        or EventGrid(spec).exact_index(point.time) != point.step_index
        or event_index(spec, point.time) != point.event_index
        or type(point.state) is not implementation.STATE_TYPE
        or type(point.layout) is not implementation.LAYOUT_TYPE
    ):
        raise ConfigError("Invalid complete active excision checkpoint or absolute clock")
    for value, template in zip(point.state, initial, strict=True):
        if np.asarray(value).shape != template.shape or np.asarray(value).dtype != template.dtype:
            raise ConfigError("Active excision source state shape or precision disagrees")
    if any(
        np.asarray(a).dtype != b.dtype or not np.array_equal(a, b)
        for a, b in zip(point.layout, layout, strict=True)
    ):
        raise ConfigError("Active excision source layout does not match its definition")
    if point.time == start and any(
        not np.array_equal(a, b) for a, b in zip(point.state, initial, strict=True)
    ):
        raise ConfigError("Active excision source initial state does not match its epoch")
    # Removal is a host boundary and also accepts checkpoints still on a device.
    # NumPy dispatching take() to a JAX array has incompatible mode semantics.
    state = type(point.state)(*(np.asarray(v) for v in point.state))
    implementation.check_values(state, spec)
    table = control_values(spec, [point.time])
    control = type(table)(*(v[0] for v in table))
    if not implementation.control_domain_valid(state, control, layout, layout.active, xp=np):
        raise ConfigError("Active excision source actual-control field is invalid")


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
    _fields(source, {"definition", "checkpoint"}, "active excision source")
    spec = parse_spec(source["definition"])
    ordinary(spec)
    cp = _fields(
        source["checkpoint"],
        {"time", "step_index", "event_index", "state", "layout"},
        "source checkpoint",
    )
    model = get_model(spec.model)
    initial, template = model.initial_values(spec)
    _fields(cp["state"], set(initial._fields), "complete nineteen-field source state")
    _fields(cp["layout"], set(template._fields), "complete source layout")

    def array(raw, target):
        value = np.asarray(raw)
        if value.size:
            allowed = (
                "fiu" if target.dtype.kind == "f" else "iu" if target.dtype.kind in "iu" else "b"
            )
            if value.dtype.kind not in allowed:
                raise ConfigError("Active source array numeric type disagrees")
        converted = value.astype(target.dtype)
        if target.dtype.kind in "iu" and not np.array_equal(value, converted):
            raise ConfigError("Active source integer layout exceeds its declared precision")
        if converted.size == target.size == 0:
            converted = converted.reshape(target.shape)
        return converted

    try:
        state = model.STATE_TYPE(*(array(cp["state"][k], v) for k, v in initial._asdict().items()))
        layout = model.LAYOUT_TYPE(
            *(array(cp["layout"][k], v) for k, v in template._asdict().items())
        )
    except (TypeError, ValueError, OverflowError) as error:
        raise ConfigError("Require numeric complete active source arrays") from error
    point = Checkpoint(state, layout, cp["time"], cp["step_index"], cp["event_index"])
    _point_check(spec, point)
    return spec, point


def physical(spec, point):
    p = type(point.layout)(*(np.asarray(v) for v in point.layout))
    y = type(point.state)(*(np.asarray(v) for v in point.state))
    n, o = len(spec.model.cells), len(spec.model.extracellular)
    inside, outside = passive.physical_amounts(y, p)
    charge = passive.charge_increment(y, p, xp=np)
    table = control_values(spec, [point.time])
    control = type(table)(*(v[0] for v in table))
    field = get_model(spec.model).field_values(y, control, p, xp=np)
    if not field.converged:
        raise ConfigError("Active excision field did not converge")
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
    _point_check(spec, point)
    m, before = spec.model, physical(spec, point)
    fields = dict(
        cell_amount_fmol=removal.OwnedField(
            before["amount"], "cell", kind="quantity", units="fmol", nonnegative=True
        ),
        extracellular_amount_fmol=removal.OwnedField(
            before["outside_amount"], "environment", kind="quantity", units="fmol", nonnegative=True
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
        membrane_capacitor_energy_pJ=removal.OwnedField(
            0.5e12 * np.asarray([v.capacitance_F for v in m.membranes]) * before["voltage"] ** 2,
            "membrane",
            kind="quantity",
            units="pJ",
            nonnegative=True,
        ),
    )
    try:
        result = removal.apply_cut(topology(spec), removed_ids, fields)
    except (TypeError, ValueError) as error:
        raise ConfigError("Invalid active cell removal: " + str(error)) from error
    plan = result.plan
    if not plan.after.cell_ids:
        return None, result, before
    raw = ordinary(spec).to_dict()["model"]
    for key, ids in (
        ("cells", plan.after.cell_ids),
        ("membranes", plan.after.membrane_ids),
        ("junctions", plan.after.edge_ids),
    ):
        raw[key] = [v for v in raw[key] if v["id"] in ids]
    for key, amount, charge in (
        (
            "cells",
            before["amount"][:, plan.new_to_old["cell"]],
            before["charge"][plan.new_to_old["cell"]],
        ),
        ("extracellular", before["outside_amount"], before["outside_charge"]),
    ):
        for i, row in enumerate(raw[key]):
            row["initial_amount_fmol"] = dict(
                zip(m.species_ids, amount[:, i].tolist(), strict=True)
            )
            row["initial_charge_C"] = float(charge[i])
    channels = []
    for i, row in enumerate(raw["channels"]):
        if row["membrane_id"] in plan.after.membrane_ids:
            row["initial_gate"] = np.asarray(point.state.channel_gate)[
                : len(row["initial_gate"]), i
            ].tolist()
            channels.append(row)
    raw["channels"] = channels
    indices = {v.id: i for i, v in enumerate(m.junctions)}
    for row in raw["junctions"]:
        row["gate"]["initial_gate"] = float(point.state.junction_gate[indices[row["id"]]])
    return raw, result, before


def experiment(spec, tissue, time):
    e = deepcopy(ordinary(spec).to_dict()["experiment"])
    owners = {
        kind: {v["id"] for v in tissue[kind + "s"]} for kind in ("membrane", "junction", "channel")
    }
    owners["pump"] = {v["pump"]["id"] for v in tissue["membranes"] if v["pump"] is not None}
    for kind, ids in owners.items():
        e[kind + "_controls"] = [v for v in e[kind + "_controls"] if v[kind + "_id"] in ids]
    carrier = e["membrane_controls"][0]["schedule"]
    clocks = [v["time"] for v in carrier]
    times = sorted({time, *(v.time for v in spec.experiment.changes), *clocks})
    e["membrane_controls"][0]["schedule"] = [
        dict(time=t, availability=carrier[bisect_right(clocks, t) - 1]["availability"])
        for t in times
    ]
    e["observation_times"] = sorted({time, *(t for t in e["observation_times"] if t >= time)})
    return e


def histories(spec, point, plan):
    channel_kept = np.asarray(
        [i for i, v in enumerate(spec.model.channels) if v.membrane_id in plan.after.membrane_ids],
        dtype=np.int64,
    )
    channel_removed = np.asarray(
        [
            i
            for i, v in enumerate(spec.model.channels)
            if v.membrane_id not in plan.after.membrane_ids
        ],
        dtype=np.int64,
    )
    indices = {
        "cell_slot": (plan.new_to_old["cell"], plan.removed["cell"]),
        "extracellular_slot": (plan.new_to_old["environment"], plan.removed["environment"]),
        "membrane_slot": (plan.new_to_old["membrane"], plan.removed["membrane"]),
        "edge_slot": (plan.new_to_old["edge"], plan.removed["edge"]),
        "face_slot": (np.arange(len(spec.model.faces)), np.empty(0, dtype=np.int64)),
        "channel_slot": (channel_kept, channel_removed),
    }
    kept, removed = {}, {}
    for key, axes in active.STATE_AXES.items():
        a, b = indices[axes[-1]]
        value = np.asarray(getattr(point.state, key))
        kept[key], removed[key] = (
            np.take(value, a, axis=-1).tolist(),
            np.take(value, b, axis=-1).tolist(),
        )
    return kept, removed, channel_kept, channel_removed


def transition_report(spec, point, result, before, after_spec=None, after_point=None):
    plan, m = result.plan, spec.model
    removed, kept = plan.removed["cell"], plan.new_to_old["cell"]
    archived, removed_history, channel_kept, channel_removed = histories(spec, point, plan)
    cell_energy = _chemical_terms(before["amount"], [v.volume_pL for v in m.cells], m.temperature_K)
    outside_energy = _chemical_terms(
        before["outside_amount"], [v.volume_pL for v in m.extracellular], m.temperature_K
    )
    ionic, cap = result.fields["cell_amount_fmol"], result.fields["membrane_capacitor_energy_pJ"]
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
        removed_channel_ids=[m.channels[i].id for i in channel_removed],
        retained_channel_ids=[m.channels[i].id for i in channel_kept],
        removed_pump_ids=[
            v.pump.id
            for v in m.membranes
            if v.pump is not None and v.id not in plan.after.membrane_ids
        ],
        retained_pump_ids=[
            v.pump.id for v in m.membranes if v.pump is not None and v.id in plan.after.membrane_ids
        ],
        removed_junction_ids=list(result.removed_owner_ids["edge"]),
        retained_junction_ids=list(plan.after.edge_ids),
        physical_policy=(
            "Excise owned material and capacitors; no lysis release or charge projection"
        ),
        junction_policy="Abstract cell edges, no physical contact-face or wound exposure claim",
        history_policy=POLICIES["state_policy"],
        gate_policy="Exact surviving channel/junction state; no voltage-based reinitialization",
        pump_fuel_policy="Maintained chemical reservoirs, no finite ATP or protein inventory",
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
        removed_chemical_energy_pJ=math.fsum(cell_energy[:, removed].ravel()),
        before_chemical_energy_pJ=math.fsum([*cell_energy.ravel(), *outside_energy.ravel()]),
        before_capacitor_energy_pJ=float(cap.previous_total),
        archived_retained_state=archived,
        archived_removed_state=removed_history,
        local_ledger_fields=[k for k in active.STATE_AXES if k not in GATES],
        energy_claim=(
            "Chemical/capacitor/held-electrode diagnostics only; "
            "no gate or mechanical cutting-energy law"
        ),
    )
    if after_spec is None:
        report["continuation"] = "Terminal archive; no zero-cell active solver"
        return report
    after = physical(after_spec, after_point)
    for actual, expected in (
        (after["amount"], before["amount"][:, kept]),
        (after["outside_amount"], before["outside_amount"]),
        (after["charge"], before["charge"][kept]),
        (after["outside_charge"], before["outside_charge"]),
        (
            np.asarray(after_point.state.channel_gate)[:, : len(channel_kept)],
            np.asarray(point.state.channel_gate)[:, channel_kept],
        ),
        (
            np.asarray(after_point.state.junction_gate)[: len(plan.after.edge_ids)],
            np.asarray(point.state.junction_gate)[plan.new_to_old["edge"]],
        ),
    ):
        if not np.array_equal(actual, expected):
            raise ConfigError(
                "Active removal changed surviving material, charge or intrinsic gate state"
            )
    if plan.changed and any(
        np.any(getattr(after_point.state, k)) for k in active.STATE_AXES if k not in GATES
    ):
        raise ConfigError("Active excision local ledgers must start at zero")
    old_v, new_v = before["voltage"][plan.new_to_old["membrane"]], after["voltage"]
    capacitance = np.asarray([v.capacitance_F for v in after_spec.model.membranes])
    jump = math.fsum(0.5e12 * capacitance * (new_v - old_v) * (new_v + old_v))
    impulse = after["electrode"] - before["electrode"]
    work = 1e12 * float(
        np.dot(np.asarray([v.boundary_potential_V for v in m.extracellular]), impulse)
    )
    report.update(
        after_chemical_energy_pJ=math.fsum(
            [*cell_energy[:, kept].ravel(), *outside_energy.ravel()]
        ),
        after_capacitor_energy_pJ=math.fsum(0.5e12 * capacitance * new_v**2),
        retained_capacitor_energy_jump_pJ=jump,
        electrode_charge_impulse_C=impulse.tolist(),
        held_boundary_work_impulse_pJ=work,
        unresolved_cut_energy_pJ=jump - work,
        unresolved_energy_interpretation=(
            "Declared potential reference; diagnostic remainder, not predicted cutting work"
        ),
        postcut_voltage_V=new_v.tolist(),
        exterior_amount_fmol=after["outside_amount"].tolist(),
        solver_rebuilt=True,
        surviving_gates_preserved=True,
    )
    return report


def excise(spec, checkpoint, removed_cell_ids):
    spec = parse_spec(spec.to_dict())
    source = capture_source(spec, checkpoint)
    tissue, result, before = derive_tissue(spec, checkpoint, removed_cell_ids)
    if not result.plan.changed:
        report = transition_report(spec, checkpoint, result, before, spec, checkpoint)
        report["history_policy"] = "Unchanged complete source, gates, ledgers and clock"
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
        experiment=experiment(spec, tissue, checkpoint.time),
        execution=ordinary(spec).to_dict()["execution"],
    )
    after = parse_spec(raw)
    state, layout = get_model(after.model).initial_values(after)
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
