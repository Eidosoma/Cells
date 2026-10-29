"""Independent passive excision, absolute-time continuation and cut diagnostics.

No Cells/JAX imports. Geometry is rebuilt from retained raw owners and the
independent full-node electrical equations are solved again. The cut energy
remainder is reported, never assigned to an invented mechanical work ledger.
"""

import math
from copy import deepcopy
from numbers import Real

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import surface_dynamics_reference as dynamics
from validation.tissue import surface_field_reference as electrical

F, R = dynamics.F, dynamics.R
MODEL_ID = "resolved_tissue_excision@1"
flatten, unpack = dynamics.flatten, dynamics.unpack


def physical_definition(raw):
    result = deepcopy(raw)
    if result["model"]["id"] == MODEL_ID:
        result["model"] = deepcopy(result["model"]["tissue"])
    if result["model"]["id"] != "resolved_tissue@1":
        raise ValueError("Excision reference supports only passive resolved tissue")
    return result


def origin_time(raw):
    return (
        raw["model"]["excision"]["source"]["checkpoint"]["time"]
        if raw["model"]["id"] == MODEL_ID
        else 0.0
    )


def bind(raw):
    physical = physical_definition(raw)
    return dict(dynamics.bind(physical), definition=deepcopy(raw), origin_time=origin_time(raw))


initial = dynamics.initial


class ExcisionError(ValueError):
    def __init__(self, message, archive, audit):
        super().__init__(message)
        self.archive = archive
        self.audit = audit


def _state(c, state):
    if isinstance(state, dict):
        if set(state) != set(c["shapes"]):
            raise ValueError("Archive requires all twelve named source state fields")
        value = flatten(c, state)
    else:
        value = np.asarray(state)
    if value.shape != initial(c).shape or not np.isfinite(value).all():
        raise ValueError("Require complete finite passive state")
    return value.copy()


def event_times(raw):
    e = raw["experiment"]
    return sorted(
        {
            0.0,
            e["end_time"],
            *(
                v["time"]
                for kind in ("membrane", "junction")
                for row in e[kind + "_controls"]
                for v in row["schedule"]
            ),
        }
    )


def evaluate(c, state, time):
    value = _state(c, state)
    stage = dynamics.stage(c, value, time)
    if np.any(stage["ci"] <= 0) or np.any(stage["co"] <= 0):
        raise ValueError("Passive excision requires strictly positive retained concentrations")
    try:
        return dynamics.evaluate(c, value, time)
    except (AssertionError, np.linalg.LinAlgError) as error:
        raise ValueError("Retained capacitor/charge/current field is incompatible") from error


def snapshot(c, state, time):
    state = _state(c, state)
    d = unpack(c, state)
    _, phi, proof = evaluate(c, state, time)
    stage = dynamics.stage(c, state, time)
    matrix, *_ = electrical.topology(stage)
    p, m = c["layout"], c["raw"]["model"]
    n = len(c["vi"])
    inside = c["ai"] + d["amount_increment"]
    outside = c["ao"] + d["extracellular_amount_increment"]
    chemical_inside = (
        0.001 * R * p["temperature"] * np.sum(inside * (np.log(inside / c["vi"]) - 1), axis=0)
    )
    chemical_outside = (
        0.001 * R * p["temperature"] * np.sum(outside * (np.log(outside / c["vo"]) - 1), axis=0)
    )
    cap_energy = []
    for k, patch in enumerate(m["membranes"]):
        i, o = p["membrane_cell"][k], n + p["membrane_outside"][k]
        cap_energy.append(0.5e12 * patch["capacitance_F"] * (phi[i] - phi[o]) ** 2)
    charge = np.r_[stage["cell_charge_C"], stage["outside_charge_C"]]
    cap_charge = matrix @ phi
    electrode = np.where(p["reservoir"], (cap_charge - charge)[n:], 0.0)
    return dict(
        time_s=float(time),
        cell_ids=[v["id"] for v in m["cells"]],
        outside_ids=[v["id"] for v in m["extracellular"]],
        species_ids=[v["id"] for v in m["species"]],
        inside_amount_fmol=inside,
        outside_amount_fmol=outside,
        inside_charge_C=np.asarray(stage["cell_charge_C"]),
        outside_charge_C=np.asarray(stage["outside_charge_C"]),
        potential_V=phi,
        capacitor_node_charge_C=cap_charge,
        electrode_charge_C=electrode,
        chemical_inside_pJ=chemical_inside,
        chemical_outside_pJ=chemical_outside,
        membrane_energy_pJ=np.asarray(cap_energy),
        chemical_energy_pJ=float(chemical_inside.sum() + chemical_outside.sum()),
        capacitor_energy_pJ=float(math.fsum(cap_energy)),
        stored_energy_pJ=float(
            chemical_inside.sum() + chemical_outside.sum() + math.fsum(cap_energy)
        ),
        field_proof=proof,
    )


def excise(raw, state, removed_cell_ids, time_s, *, step_index=None, event_index=None):
    c = bind(raw)
    if (
        not isinstance(time_s, Real)
        or isinstance(time_s, bool)
        or not np.isfinite(time_s)
        or not c["origin_time"] <= time_s <= raw["experiment"]["end_time"]
    ):
        raise ValueError("Cut requires a finite accepted absolute time")
    dt = raw["execution"]["dt"]
    if time_s != round(time_s / dt) * dt and time_s not in event_times(raw):
        raise ValueError("Cut time is not an original nominal-grid point or declared event")
    names = [v["id"] for v in c["raw"]["model"]["cells"]]
    removed = list(removed_cell_ids)
    if len(set(removed)) != len(removed) or not set(removed) <= set(names):
        raise ValueError("Require distinct currently owned cell IDs")
    flat = _state(c, state)
    before = snapshot(c, flat, time_s)
    archived = deepcopy(state) if isinstance(state, dict) else unpack(c, flat)
    archived = {name: np.asarray(value).copy().tolist() for name, value in archived.items()}
    archive = dict(
        definition=deepcopy(raw),
        checkpoint=dict(
            time=float(time_s), step_index=step_index, event_index=event_index, state=archived
        ),
    )
    if not removed:
        return dict(
            raw=deepcopy(raw),
            context=c,
            state=flat,
            start_time=float(time_s),
            archive=archive,
            audit=dict(
                no_op=True,
                terminal=False,
                removed_cell_ids=[],
                before=before,
                after=before,
                unresolved_cut_energy_pJ=0.0,
            ),
        )
    m = c["raw"]["model"]
    removed_indices = [names.index(name) for name in removed]
    keep = [i for i, name in enumerate(names) if name not in removed]
    removed_patches = [i for i, p in enumerate(m["membranes"]) if p["inside"] in removed]
    removed_chemical = float(before["chemical_inside_pJ"][removed_indices].sum())
    removed_capacitor = float(before["membrane_energy_pJ"][removed_patches].sum())
    audit = dict(
        no_op=False,
        terminal=not keep,
        removed_cell_ids=removed,
        removed_amount_fmol=before["inside_amount_fmol"][:, removed_indices].sum(axis=1),
        removed_charge_C=float(before["inside_charge_C"][removed_indices].sum()),
        removed_fixed_charge_equivalent_fmol=math.fsum(
            m["cells"][i]["fixed_charge_equivalent_fmol"] for i in removed_indices
        ),
        removed_chemical_energy_pJ=removed_chemical,
        removed_owned_capacitor_energy_pJ=removed_capacitor,
        removed_membrane_ids=[m["membranes"][i]["id"] for i in removed_patches],
        before=before,
        mechanical_work_model=False,
        source_native_tissue_equivalence=False,
    )
    if not keep:
        audit.update(
            after=None,
            electrode_charge_impulse_C=None,
            maintained_boundary_work_pJ=None,
            unresolved_cut_energy_pJ=None,
            reason="Terminal archive; no runnable retained tissue",
        )
        return dict(
            raw=None,
            context=None,
            state=None,
            start_time=float(time_s),
            archive=archive,
            audit=audit,
        )
    after_raw = physical_definition(raw)
    post, e = after_raw["model"], after_raw["experiment"]
    post["cells"] = [deepcopy(m["cells"][i]) for i in keep]
    for row, i in zip(post["cells"], keep, strict=True):
        row["initial_amount_fmol"] = dict(
            zip(before["species_ids"], before["inside_amount_fmol"][:, i].tolist(), strict=True)
        )
        row["initial_charge_C"] = float(before["inside_charge_C"][i])
    for i, row in enumerate(post["extracellular"]):
        row["initial_amount_fmol"] = dict(
            zip(before["species_ids"], before["outside_amount_fmol"][:, i].tolist(), strict=True)
        )
        row["initial_charge_C"] = float(before["outside_charge_C"][i])
    post["membranes"] = [v for v in post["membranes"] if v["inside"] not in removed]
    post["junctions"] = [
        v for v in post["junctions"] if v["sender"] not in removed and v["receiver"] not in removed
    ]
    for kind in ("membrane", "junction"):
        retained = {v["id"] for v in post[kind + "s"]}
        e[kind + "_controls"] = [v for v in e[kind + "_controls"] if v[kind + "_id"] in retained]
    # Preserve future discontinuity boundaries even when their only original
    # physical owner was removed. No-op insertions do not alter survivor rates.
    retained_events = set(event_times(after_raw))
    missing = sorted(t for t in event_times(raw) if t >= time_s and t not in retained_events)
    if not e["membrane_controls"]:
        raise ValueError("Retained tissue has no membrane available for clock/field continuation")
    anchor = e["membrane_controls"][0]["schedule"]
    for time in missing:
        level = next(v["availability"] for v in reversed(anchor) if v["time"] <= time)
        anchor.append(dict(time=time, availability=level))
        anchor.sort(key=lambda v: v["time"])
    e["observation_times"] = sorted(
        {float(time_s), *(t for t in e["observation_times"] if t >= time_s)}
    )
    post_context = bind(after_raw)
    post_context["origin_time"] = float(time_s)
    local = initial(post_context)
    try:
        after = snapshot(post_context, local, time_s)
    except ValueError as error:
        raise ExcisionError(
            str(error),
            archive,
            audit
            | dict(
                rejected=True,
                after=None,
                candidate_definition=after_raw,
                reason="Retained field is incompatible; no charge or concentration repair",
            ),
        ) from error
    impulse = after["electrode_charge_C"] - before["electrode_charge_C"]
    work = 1e12 * math.fsum(
        v["boundary_potential_V"] * q for v, q in zip(post["extracellular"], impulse, strict=True)
    )
    remainder = (
        after["stored_energy_pJ"]
        - before["stored_energy_pJ"]
        + removed_chemical
        + removed_capacitor
        - work
    )
    audit.update(
        after=after,
        preserved_noop_clock_times=missing,
        electrode_charge_impulse_C=impulse,
        maintained_boundary_work_pJ=float(work),
        chemical_energy_jump_pJ=after["chemical_energy_pJ"] - before["chemical_energy_pJ"],
        capacitor_energy_jump_pJ=after["capacitor_energy_pJ"] - before["capacitor_energy_pJ"],
        unresolved_cut_energy_pJ=float(remainder),
    )
    return dict(
        raw=after_raw,
        context=post_context,
        state=local,
        start_time=float(time_s),
        archive=archive,
        audit=audit,
    )


class ReferenceIntegrationError(RuntimeError):
    def __init__(self, message, diagnostics):
        super().__init__(message)
        self.diagnostics = diagnostics


def integrate(
    raw,
    *,
    state=None,
    start_time=None,
    end_time=None,
    observation_times=None,
    refinement=1,
    max_step_s=1e-4,
    first_step_s=1e-7,
):
    c = bind(raw)
    start = c["origin_time"] if start_time is None else float(start_time)
    end = raw["experiment"]["end_time"] if end_time is None else float(end_time)
    if (
        type(refinement) is not int
        or refinement < 1
        or not np.isfinite(max_step_s)
        or max_step_s <= 0
        or not np.isfinite(first_step_s)
        or first_step_s <= 0
        or not np.isfinite(start)
        or not np.isfinite(end)
        or start < c["origin_time"]
        or end < start
    ):
        raise ValueError("Invalid absolute reference integration interval or refinement")
    times = (
        sorted(
            {start, end, *(t for t in raw["experiment"]["observation_times"] if start <= t <= end)}
        )
        if observation_times is None
        else list(observation_times)
    )
    if (
        not times
        or times[0] != start
        or times[-1] != end
        or any(b <= a for a, b in zip(times[:-1], times[1:], strict=True))
    ):
        raise ValueError("Observations must cover the ordered absolute integration interval")
    current = initial(c) if state is None else _state(c, state)
    saved = {start: current.copy()}
    evaluations = 0
    events = sorted({start, end, *(t for t in event_times(raw) if start < t < end)})
    atol = flatten(
        c,
        {
            k: np.full(shape, (1e-29 if k.endswith("_C") else 2e-14) / refinement)
            for k, shape in c["shapes"].items()
        },
    )

    def rhs(t, y, held):
        nonlocal evaluations
        evaluations += 1
        try:
            return evaluate(c, y, held)[0]
        except Exception as error:
            raise ReferenceIntegrationError(
                str(error),
                dict(
                    time_s=float(t),
                    held_control_time_s=float(held),
                    state=y.tolist(),
                    evaluations=evaluations,
                    automatic_retry=False,
                ),
            ) from error

    for left, right in zip(events[:-1], events[1:], strict=True):
        solved = solve_ivp(
            lambda t, y, held=left: rhs(t, y, held),
            (left, right),
            current,
            method="DOP853",
            rtol=2e-11 / refinement,
            atol=atol,
            max_step=max_step_s / refinement,
            # Zero local ledgers otherwise let solve_ivp propose a large first
            # trial before seeing this fixture's microsecond electrical mode.
            # Only the starting trial is bounded; subsequent steps adapt to
            # unchanged physical rates and error tolerances.
            first_step=min(first_step_s / refinement, max_step_s / refinement, right - left),
            dense_output=True,
        )
        if not solved.success:
            raise ReferenceIntegrationError(
                solved.message, dict(time_s=float(solved.t[-1]), state=solved.y[:, -1].tolist())
            )
        for t in times:
            if left < t <= right:
                saved[t] = solved.y[:, -1].copy() if t == right else solved.sol(t)
        current = solved.y[:, -1].copy()
    return dict(
        times=times,
        state=np.stack([saved[t] for t in times]),
        potential_V=np.stack([evaluate(c, saved[t], t)[1] for t in times]),
        evaluations=evaluations,
        event_times=events,
        start_time=start,
        end_time=end,
        refinement=refinement,
        max_step_s=max_step_s / refinement,
        first_step_s=first_step_s / refinement,
        rtol=2e-11 / refinement,
        amount_energy_atol=2e-14 / refinement,
        electrode_charge_atol_C=1e-29 / refinement,
        method="Independent full-node roots and DOP853, absolute-time event segmentation",
    )
