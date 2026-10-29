"""Independent active excision: actual owners, retained gates, new local histories.

The frozen kinetic oracle supplies all ionic/gate/pump equations. The frozen
passive excision oracle supplies owner removal and chemical/capacitor diagnostics.
Its instantaneous field view incorporates the actual intrinsic junction gates;
channel and pump currents are internal to capacitor components. No Cells/JAX
imports, geometry projection from production, or invented gate energy is used.
"""

from copy import deepcopy
from numbers import Real

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import surface_excision_reference as passive
from validation.tissue import surface_kinetic_reference as kinetic

MODEL_ID = "resolved_tissue_active_excision@1"
BASE_ID = "resolved_tissue@12"
CONTROL_FAMILIES = ("membrane", "junction", "channel", "pump")
GATES = ("channel_gate", "junction_gate")
F, R = kinetic.F, kinetic.R
flatten, unpack, initial = kinetic.flatten, kinetic.unpack, kinetic.initial
ExcisionError = passive.ExcisionError
ReferenceIntegrationError = passive.ReferenceIntegrationError


def physical_definition(raw):
    result = deepcopy(raw)
    if result["model"]["id"] == MODEL_ID:
        result["model"] = deepcopy(result["model"]["tissue"])
    if result["model"]["id"] != BASE_ID:
        raise ValueError("Active excision requires the complete resolved_tissue@12 parent")
    return result


def bind(raw):
    start = (
        raw["model"]["excision"]["source"]["checkpoint"]["time"]
        if raw["model"]["id"] == MODEL_ID
        else 0.0
    )
    return dict(kinetic.bind(physical_definition(raw)), definition=deepcopy(raw), origin_time=start)


def event_times(raw):
    e = raw["experiment"]
    return sorted(
        {
            0.0,
            e["end_time"],
            *(
                v["time"]
                for kind in CONTROL_FAMILIES
                for row in e[kind + "_controls"]
                for v in row["schedule"]
            ),
        }
    )


def _state(c, state):
    if isinstance(state, dict):
        if set(state) != set(c["shapes"]):
            raise ValueError("Active cut archives require all nineteen named fields")
        value = flatten(c, state)
    else:
        value = np.asarray(state)
    if value.shape != initial(c).shape or not np.isfinite(value).all():
        raise ValueError("Require a complete finite nineteen-field state")
    return value.copy()


def evaluate(c, state, time):
    value = _state(c, state)
    gates = unpack(c, value)["junction_gate"]
    minima = np.asarray(
        [row["gate"]["minimum_open_fraction"] for row in c["raw"]["model"]["junctions"]]
    )
    if np.any(gates < minima) or np.any(gates > 1):
        raise ValueError("Intrinsic junction memory lies outside its declared domain")
    try:
        return kinetic.evaluate(c, value, time)
    except (AssertionError, np.linalg.LinAlgError) as error:
        raise ValueError(
            "Active retained field or charge/current rates are incompatible"
        ) from error


def _retain_clocks(raw, clocks):
    carrier = raw["experiment"]["membrane_controls"][0]["schedule"]
    present = {row["time"] for row in carrier}
    for time in sorted(set(clocks) - present):
        held = next(row["availability"] for row in reversed(carrier) if row["time"] <= time)
        carrier.append(dict(time=time, availability=held))
        carrier.sort(key=lambda row: row["time"])


def _passive_view(c, state):
    """Current physical field/energy view, not a replacement active trajectory."""
    values = unpack(c, state)
    raw = deepcopy(c["raw"])
    m = raw["model"]
    m["id"] = "resolved_tissue@1"
    m.pop("channels")
    for row in m["membranes"]:
        row.pop("pump")
    for j, row in enumerate(m["junctions"]):
        row.pop("gate")
        row["permeability_m_per_s"] = {
            name: p * values["junction_gate"][j] for name, p in row["permeability_m_per_s"].items()
        }
    for kind in ("channel", "pump"):
        raw["experiment"].pop(kind + "_controls")
    raw["execution"].pop("channel_capacity")
    _retain_clocks(raw, event_times(c["raw"]))
    context = passive.bind(raw)
    return raw, context, passive.flatten(context, values)


def snapshot(c, state, time):
    value = _state(c, state)
    evaluate(c, value, time)
    _, context, physical = _passive_view(c, value)
    return passive.snapshot(context, physical, time)


def _json_values(value):
    if isinstance(value, dict):
        return {k: _json_values(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_values(v) for v in value]
    return value.tolist() if hasattr(value, "tolist") else value


def excise(
    raw, state, removed_cell_ids, time_s, *, step_index=None, event_index=None, source_layout=None
):
    c = bind(raw)
    if (
        not isinstance(time_s, Real)
        or isinstance(time_s, bool)
        or not np.isfinite(time_s)
        or not c["origin_time"] <= time_s <= raw["experiment"]["end_time"]
    ):
        raise ValueError("Cut requires an accepted absolute time within this epoch")
    value = _state(c, state)
    evaluate(c, value, time_s)
    values = unpack(c, value)
    archive = dict(
        definition=deepcopy(raw),
        checkpoint=dict(
            time=float(time_s),
            step_index=step_index,
            event_index=event_index,
            state=_json_values(deepcopy(state) if isinstance(state, dict) else values),
            layout=_json_values(deepcopy(c["layout"] if source_layout is None else source_layout)),
        ),
    )
    view, _, physical = _passive_view(c, value)
    try:
        result = passive.excise(
            view, physical, removed_cell_ids, time_s, step_index=step_index, event_index=event_index
        )
    except ExcisionError as error:
        raise ExcisionError(str(error), archive, error.audit) from error
    result["archive"] = archive
    result["audit"].update(
        source_state_fields=19,
        preserved_gate_fields=list(GATES),
        gate_energy_store=False,
        finite_atp_store=False,
        maintained_atp_work_internal=False,
    )
    if result["audit"]["no_op"]:
        result.update(raw=deepcopy(raw), context=c, state=value)
        return result
    if result["audit"]["terminal"]:
        return result
    after = physical_definition(raw)
    before_m, after_m = c["raw"]["model"], after["model"]
    removed = set(result["audit"]["removed_cell_ids"])
    for name in ("cells", "extracellular"):
        after_m[name] = deepcopy(result["raw"]["model"][name])
    after_m["membranes"] = [p for p in after_m["membranes"] if p["inside"] not in removed]
    membranes = {p["id"] for p in after_m["membranes"]}
    after_m["channels"] = [p for p in after_m["channels"] if p["membrane_id"] in membranes]
    after_m["junctions"] = [
        p
        for p in after_m["junctions"]
        if p["sender"] not in removed and p["receiver"] not in removed
    ]
    old_channels = {p["id"]: j for j, p in enumerate(before_m["channels"])}
    old_junctions = {p["id"]: j for j, p in enumerate(before_m["junctions"])}
    for p in after_m["channels"]:
        p["initial_gate"] = values["channel_gate"][
            : len(p["initial_gate"]), old_channels[p["id"]]
        ].tolist()
    for p in after_m["junctions"]:
        p["gate"]["initial_gate"] = float(values["junction_gate"][old_junctions[p["id"]]])
    for kind in CONTROL_FAMILIES:
        rows = (
            after_m[kind + "s"]
            if kind != "pump"
            else [p["pump"] for p in after_m["membranes"] if p["pump"] is not None]
        )
        names = {p["id"] for p in rows}
        after["experiment"][kind + "_controls"] = [
            p for p in after["experiment"][kind + "_controls"] if p[kind + "_id"] in names
        ]
    retained_events = set(event_times(after))
    _retain_clocks(after, {*event_times(raw), time_s})
    after["experiment"]["observation_times"] = sorted(
        {float(time_s), *(t for t in raw["experiment"]["observation_times"] if t >= time_s)}
    )
    context = bind(after)
    context["origin_time"] = float(time_s)
    local = initial(context)
    evaluate(context, local, time_s)
    result.update(raw=after, context=context, state=local)
    result["audit"].update(
        preserved_noop_clock_times=sorted(set(event_times(raw)) - retained_events),
        removed_channel_ids=[
            p["id"] for p in before_m["channels"] if p["membrane_id"] not in membranes
        ],
        removed_pump_ids=[
            p["pump"]["id"]
            for p in before_m["membranes"]
            if p["id"] not in membranes and p["pump"] is not None
        ],
    )
    return result


def integrate(
    raw,
    *,
    state=None,
    start_time=None,
    end_time=None,
    observation_times=None,
    refinement=1,
    max_step_s=5e-6,
    first_step_s=1e-7,
):
    c = bind(raw)
    start = c["origin_time"] if start_time is None else float(start_time)
    end = raw["experiment"]["end_time"] if end_time is None else float(end_time)
    if (
        type(refinement) is not int
        or refinement < 1
        or not np.isfinite([start, end, max_step_s, first_step_s]).all()
        or start < c["origin_time"]
        or end < start
        or min(max_step_s, first_step_s) <= 0
    ):
        raise ValueError("Invalid active reference interval, step or refinement")
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
        raise ValueError("Observations must cover the ordered absolute interval")
    current = initial(c) if state is None else _state(c, state)
    saved, evaluations = {start: current.copy()}, 0
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
            first_step=min(first_step_s / refinement, max_step_s / refinement, right - left),
            dense_output=True,
        )
        if not solved.success:
            raise ReferenceIntegrationError(
                solved.message, dict(time_s=float(solved.t[-1]), state=solved.y[:, -1].tolist())
            )
        for time in times:
            if left < time <= right:
                saved[time] = solved.y[:, -1].copy() if time == right else solved.sol(time)
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
        rtol=2e-11 / refinement,
        amount_energy_gate_atol=2e-14 / refinement,
        electrode_charge_atol_C=1e-29 / refinement,
        max_step_s=max_step_s / refinement,
        first_step_s=first_step_s / refinement,
        method=(
            "Independent nineteen-field DOP853, full-node field roots "
            "and four absolute control clocks"
        ),
    )
