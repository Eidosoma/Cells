"""Independent neutral cotransport on finite-energy compliant compartments.

No Cells/JAX imports or production projections. Positive route cycles carry
declared stoichiometric ions outside-to-inside. Current amounts and volumes
drive both cotransport and the existing water/finite-energy reference.
"""

from copy import deepcopy
from numbers import Real

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import cotransport_material_coordinates as material
from validation.tissue import surface_energy_water_reference as water_energy
from validation.transport import cotransport_reference as transport

F, R = water_energy.F, water_energy.R
flatten, unpack = water_energy.flatten, water_energy.unpack
MODEL_ID = "resolved_cotransport_water@1"
CONTROL_KINDS = (*water_energy.CONTROL_KINDS, "cotransport")
EXTRA_FIELDS = (
    "cotransport_cycles_fmol",
    "cotransport_transferred_fmol",
    "cotransport_dissipated_energy_pJ",
)


def bind(raw):
    if raw["model"]["id"] != MODEL_ID:
        raise ValueError("Require resolved_cotransport_water@1")
    projected = deepcopy(raw)
    projected["model"]["id"] = water_energy.MODEL_ID
    routes = projected["model"].pop("cotransporters")
    schedules = projected["experiment"].pop("cotransport_controls")
    projected["execution"].pop("cotransport_capacity")
    base = water_energy.bind(projected)
    m = raw["model"]
    species = [row["id"] for row in m["species"]]
    cells = [row["id"] for row in m["cells"]]
    outside = [row["id"] for row in m["extracellular"]]
    patches = {row["id"]: row for row in m["membranes"]}
    names = set()
    nu = np.zeros((len(species), len(routes)), dtype=np.int64)
    inside, exterior = [], []
    for j, route in enumerate(routes):
        name, capacity = route["id"], route["capacity_fmol_per_s"]
        if (
            not isinstance(name, str)
            or not name
            or name in names
            or route["membrane_id"] not in patches
            or isinstance(capacity, bool)
            or not isinstance(capacity, Real)
            or not np.isfinite(capacity)
            or capacity < 0
        ):
            raise ValueError(
                "Cotransport requires unique IDs, declared membranes and finite capacity"
            )
        names.add(name)
        if route["law"] == "kcc_reversible_tanh@1":
            roles = {"potassium": (1, 1), "chloride": (-1, 1)}
        elif route["law"] == "nkcc_reversible_tanh@1":
            roles = {"sodium": (1, 1), "potassium": (1, 1), "chloride": (-1, 2)}
        else:
            raise ValueError("Unsupported manufactured cotransport law")
        refs = route["roles"]
        if set(refs) != set(roles) or len(set(refs.values())) != len(refs):
            raise ValueError("Cotransport roles must be distinct and explicit")
        for role, (valence, coefficient) in roles.items():
            i = species.index(refs[role])
            if m["species"][i]["valence"] != valence:
                raise ValueError("Cotransport role has the wrong actual species valence")
            nu[i, j] = coefficient
        patch = patches[route["membrane_id"]]
        inside.append(cells.index(patch["inside"]))
        exterior.append(len(cells) + outside.index(patch["outside"]))
    controls = {}
    for group in schedules:
        name, rows = group["cotransport_id"], group["schedule"]
        if name in controls or not rows:
            raise ValueError("Duplicate or empty cotransport schedule")
        times = np.asarray([row["time"] for row in rows])
        levels = np.asarray([row["availability"] for row in rows])
        if (
            not np.isfinite(times).all()
            or times[0] != 0
            or np.any(np.diff(times) <= 0)
            or times[-1] > raw["experiment"]["end_time"]
            or not np.isfinite(levels).all()
            or np.any((levels < 0) | (levels > 1))
        ):
            raise ValueError("Invalid right-continuous cotransport schedule")
        controls[name] = deepcopy(rows)
    if set(controls) != names:
        raise ValueError("Cotransport controls must exactly match route owners")
    return dict(
        base,
        raw=deepcopy(raw),
        water_energy=base,
        cotransport_nu=nu,
        cotransport_inside=inside,
        cotransport_outside=exterior,
        cotransport_controls=[controls[row["id"]] for row in routes],
        shapes=base["shapes"]
        | dict(
            cotransport_cycles_fmol=(len(routes),),
            cotransport_transferred_fmol=(len(species), len(routes)),
            cotransport_dissipated_energy_pJ=(len(routes),),
        ),
    )


def initial(c):
    d = unpack(c["water_energy"], water_energy.initial(c["water_energy"]))
    d.update({name: np.zeros(c["shapes"][name]) for name in EXTRA_FIELDS})
    return flatten(c, d)


def evaluate(c, state, time, *, charge_equivalent_increment_fmol=None):
    if not np.isfinite(state).all():
        raise ValueError("Complete cotransport/water reference state must be finite")
    d = unpack(c, state)
    slope, phi, proof = water_energy.evaluate(
        c["water_energy"],
        flatten(c["water_energy"], d),
        time,
        charge_equivalent_increment_fmol=charge_equivalent_increment_fmol,
    )
    result = unpack(c["water_energy"], slope)
    amount = np.c_[c["ai"] + d["amount_increment"], c["ao"] + d["extracellular_amount_increment"]]
    volume = np.r_[
        c["vi"] + d["volume_increment_pL"],
        c["vo"] + d["extracellular_volume_increment_pL"],
    ]
    concentration = amount / volume
    routes = c["raw"]["model"]["cotransporters"]
    cycles, affinity, heat = (np.zeros(len(routes)) for _ in range(3))
    moved = np.zeros((amount.shape[0], len(routes)))
    temperature = c["raw"]["model"]["temperature_K"]
    for j, route in enumerate(routes):
        i, o = c["cotransport_inside"][j], c["cotransport_outside"][j]
        level = next(
            row["availability"]
            for row in reversed(c["cotransport_controls"][j])
            if row["time"] <= time
        )
        values = transport.cycle(
            concentration[:, i].tolist(),
            concentration[:, o].tolist(),
            c["cotransport_nu"][:, j].tolist(),
            route["capacity_fmol_per_s"],
            level,
            temperature,
        )
        cycles[j] = values["cycle_fmol_s"]
        affinity[j] = values["affinity_J_mol"]
        heat[j] = values["dissipated_power_pJ_s"]
        moved[:, j] = values["transported_fmol_s"]
    exchanged = np.asarray(
        transport.exchange(
            cycles.tolist(),
            c["cotransport_inside"],
            c["cotransport_outside"],
            c["cotransport_nu"].tolist(),
            amount.shape[-1],
        )
    )
    n = len(c["vi"])
    result["amount_increment"] += exchanged[:, :n]
    result["extracellular_amount_increment"] += exchanged[:, n:]
    result.update(
        cotransport_cycles_fmol=cycles,
        cotransport_transferred_fmol=moved,
        cotransport_dissipated_energy_pJ=heat,
    )
    chemical = 1e-3 * R * temperature * np.sum(np.log(concentration) * exchanged)
    valence = np.asarray([row["valence"] for row in c["raw"]["model"]["species"]])
    return (
        flatten(c, result),
        phi,
        proof
        | dict(
            physical_energy_balance_pJ_s=float(
                proof["physical_energy_balance_pJ_s"] + chemical + heat.sum()
            ),
            ionic_chemical_power_pJ_s=float(proof["ionic_chemical_power_pJ_s"] + chemical),
            ionic_dissipation_pJ_s=float(proof["ionic_dissipation_pJ_s"] + heat.sum()),
            cotransport_chemical_power_pJ_s=float(chemical),
            cotransport_dissipation_pJ_s=float(heat.sum()),
            cotransport_affinity_J_mol=affinity.tolist(),
            cotransport_cycle_fmol_s=cycles.tolist(),
            cotransport_route_charge_C_s=(
                1e-15 * F * (valence @ c["cotransport_nu"]) * cycles
            ).tolist(),
            cotransport_charge_rate_C_s=(1e-15 * F * (valence @ exchanged)).tolist(),
        ),
    )


class ReferenceIntegrationError(RuntimeError):
    """Failed stage/solver evidence, retained for the calling run's failure artifact."""

    def __init__(self, message, diagnostics):
        super().__init__(message)
        self.diagnostics = diagnostics


def integrate(
    raw,
    *,
    max_step_s,
    refinement=1,
    method="DOP853",
    segment_coordinates="global",
    tolerance_scale=1.0,
    material_coordinates="full",
):
    """Adaptively integrate all 31 fields, with explicitly bounded physical steps.

    Each control interval uses its left endpoint's right-continuous controls,
    including RHS evaluations at the right endpoint. States are continuous at
    an event; observation potentials use the controls active at that event.

    ``max_step_s`` is a case-specific accuracy cap, not an inherited channel
    timestep. Refinement divides both this cap and all error tolerances. The
    caller must choose a scientifically adequate duration and compare refined
    trajectories. Evaluation extrema include rejected trial stages, not just
    observations. No stage is clipped, projected or retried after domain failure.
    An explicit ``tolerance_scale`` in (0, 1] tightens solver tolerances without
    changing the step cap or startup rule. The default preserves the original
    values. Requests below DOP853's binary64 relative-tolerance floor are refused
    rather than silently relaxed by SciPy. This setting never changes the
    separate state, reference-stability or conservation acceptance budgets.

    Only DOP853 is currently qualified here. Naive Radau/BDF numerical Jacobians
    perturb ionic amounts off the closed capacitor-component charge manifold;
    stiff support needs independently validated conservative coordinates first.

    The opt-in ``local_delta`` coordinates integrate each control interval from
    local time zero and zero change from its independently computed parent.
    Original material/energy anchors are retained in every RHS evaluation.
    Startup uses one eighth of the smallest pool-inventory/rate timescale,
    bounded by interval/1000 and the maximum step, then divided by refinement.
    Solver relative tolerances act on segment changes in this mode; numerical
    tolerance values and the separate full-state comparison budgets do not
    change. No production parent or production refinement grid is used.

    ``transport_ledgers`` drops only the redundant bulk-ion solver coordinates
    for a sealed single-pair, channel/junction/face-free case. The full state is
    reconstructed from signed transport at every evaluation and observation;
    electrical charge uses the electrogenic ledgers and original charge anchors.
    Fuel, water and heat/work coordinates remain integrated unchanged. The
    original bulk RHS must agree with the coordinate derivative within its
    arithmetic roundoff bound. This is not a projection of a legacy trajectory.
    """
    if type(refinement) is not int or refinement < 1:
        raise ValueError("Refinement must be a positive integer")
    if (
        isinstance(tolerance_scale, bool)
        or not isinstance(tolerance_scale, Real)
        or not np.isfinite(tolerance_scale)
        or not 0 < tolerance_scale <= 1
    ):
        raise ValueError("Tolerance scale must be a finite tightening multiplier in (0, 1]")
    rtol = (2e-11 / refinement) * tolerance_scale
    amount_atol = (2e-14 / refinement) * tolerance_scale
    charge_atol = (1e-29 / refinement) * tolerance_scale
    if rtol < 100 * np.finfo(float).eps or min(amount_atol, charge_atol) <= 0:
        raise ValueError("Requested reference tolerances fall below the binary64 solver floor")
    if (
        isinstance(max_step_s, bool)
        or not isinstance(max_step_s, Real)
        or not np.isfinite(max_step_s)
        or max_step_s <= 0
    ):
        raise ValueError("max_step_s must be an explicit finite positive physical step cap")
    if method != "DOP853":
        raise ValueError("Only DOP853 is validated; implicit solvers need conservative coordinates")
    if segment_coordinates not in ("global", "local_delta"):
        raise ValueError("Reference coordinates must be global or local_delta")
    if material_coordinates not in ("full", "transport_ledgers"):
        raise ValueError("Material coordinates must be full or transport_ledgers")
    c, experiment = bind(raw), raw["experiment"]
    codec = material.bind(c) if material_coordinates == "transport_ledgers" else None
    end = experiment["end_time"]
    times = np.asarray(experiment["observation_times"], dtype=float)
    if (
        not np.isfinite(end)
        or end <= 0
        or times.ndim != 1
        or times.size == 0
        or not np.isfinite(times).all()
        or np.any(np.diff(times) <= 0)
        or np.any((times < 0) | (times > end))
    ):
        raise ValueError("Require positive finite duration and ordered observations inside it")
    events = sorted(
        {
            0.0,
            end,
            *(
                row["time"]
                for kind in CONTROL_KINDS
                for group in experiment[kind + "_controls"]
                for row in group["schedule"]
            ),
        }
    )
    if not np.isfinite(events).all() or events[0] != 0 or events[-1] != end:
        raise ValueError("All seven control clocks must lie within the integration interval")
    start = initial(c)
    state = start.copy() if codec is None else codec.pack(start)
    saved, segments = {0.0: state.copy()}, []
    state_min, state_max = start.copy(), start.copy()
    evaluations = 0
    atols = flatten(
        c,
        {
            name: np.full(shape, charge_atol if name.endswith("_C") else amount_atol)
            for name, shape in c["shapes"].items()
        },
    )
    if codec is not None:
        atols = atols[codec.integrated_indices]
    coordinate_details = dict(
        material_coordinates=material_coordinates,
        integrated_scalar_count=int(state.size),
        complete_scalar_count=int(start.size),
        derived_fields=[] if codec is None else list(material.BULK_FIELDS),
        field_charge_source="bulk_increments"
        if codec is None
        else "electrogenic_transport_ledgers",
    )

    def complete(value):
        return value if codec is None else codec.unpack(value)

    def evaluate_coordinates(value, held_time):
        if codec is None:
            return evaluate(c, value, held_time)
        return evaluate(
            c,
            complete(value),
            held_time,
            charge_equivalent_increment_fmol=codec.charge_increment_fmol(value),
        )

    def failure(message, time, held_time, value, phase, *, local_time=None):
        # JSON-safe even when a failed trial itself contains a NaN or infinity.
        def finite_values(array):
            return [float(v) if np.isfinite(v) else str(v) for v in array]

        try:
            full_state = finite_values(complete(value))
        except ValueError:
            # Preserve the attempted coordinates if a nonfinite or overflowing
            # trial cannot be reconstructed; never invent a replacement state.
            full_state = None
        return ReferenceIntegrationError(
            message,
            dict(
                phase=phase,
                time_s=float(time),
                held_control_time_s=float(held_time),
                local_time_s=None if local_time is None else float(local_time),
                state=full_state,
                attempted_solver_state=finite_values(value),
                initial_state=start.tolist(),
                evaluation_state_minimum=finite_values(state_min),
                evaluation_state_maximum=finite_values(state_max),
                evaluations=evaluations,
                completed_segments=deepcopy(segments),
                event_times=events,
                method=method,
                segment_coordinates=segment_coordinates,
                max_step_s=float(max_step_s / refinement),
                refinement=refinement,
                tolerance_scale=float(tolerance_scale),
                rtol=rtol,
                amount_volume_energy_atol=amount_atol,
                electrode_charge_atol_C=charge_atol,
                automatic_retry=False,
                **coordinate_details,
            ),
        )

    def rhs(time, value, held_time, *, local_time=None):
        nonlocal evaluations
        evaluations += 1
        slope = None
        try:
            full_state = complete(value)
            np.minimum(state_min, full_state, out=state_min)
            np.maximum(state_max, full_state, out=state_max)
            slope = evaluate_coordinates(value, held_time)[0]
            if not np.isfinite(slope).all():
                raise ValueError("Nonfinite independent reference derivative")
            return slope if codec is None else codec.pack_derivative(slope)
        except Exception as error:
            retained = failure(
                f"Reference RHS failed at t={time!r}: {error}",
                time,
                held_time,
                value,
                "rhs",
                local_time=local_time,
            )
            if codec is not None and slope is not None:
                retained.diagnostics["attempted_full_derivative"] = [
                    float(v) if np.isfinite(v) else str(v) for v in slope
                ]
                try:
                    report = codec.derivative_consistency(slope)
                    retained.diagnostics["material_derivative_consistency"] = {
                        key: val.tolist() if isinstance(val, np.ndarray) else val
                        for key, val in report.items()
                    }
                except ValueError as diagnostic_error:
                    retained.diagnostics["material_derivative_diagnostic_error"] = str(
                        diagnostic_error
                    )
            raise retained from error

    for left, right in zip(events, events[1:], strict=False):
        options = {}
        origin = state.copy()
        local = segment_coordinates == "local_delta"
        if local:
            # This state came from this reference's own preceding integration,
            # including when running a tighter reference from the original start.
            slope = rhs(left, origin, left, local_time=0.0)
            amounts = (
                c["water_energy"]["energy_initial"]
                + unpack(c, complete(origin))["energy_amount_increment_fmol"]
            )
            rates = unpack(c, complete(slope))["energy_amount_increment_fmol"]
            if not np.isfinite(amounts).all() or np.any(amounts <= 0):
                raise failure("Nonpositive startup pool", left, left, origin, "startup")
            moving = np.abs(rates) > 0
            first = min(max_step_s, (right - left) / 1000)
            if np.any(moving):
                first = min(first, float(np.min(amounts[moving] / np.abs(rates[moving]))) / 8)
            first /= refinement
            if not np.isfinite(first) or first <= 0:
                raise failure("Unrepresentable startup step", left, left, origin, "startup")
            options["first_step"] = first
        solution = solve_ivp(
            (
                (lambda t, y, held=left, base=origin: rhs(held + t, base + y, held, local_time=t))
                if local
                else (lambda t, y, held=left: rhs(t, y, held))
            ),
            (0.0, right - left) if local else (left, right),
            np.zeros_like(origin) if local else state,
            method=method,
            rtol=rtol,
            atol=atols,
            max_step=max_step_s / refinement,
            dense_output=True,
            **options,
        )
        if not solution.success:
            raise failure(
                solution.message,
                left + solution.t[-1] if local else solution.t[-1],
                left,
                origin + solution.y[:, -1] if local else solution.y[:, -1],
                "solver",
                local_time=solution.t[-1] if local else None,
            )
        steps = np.diff(solution.t)
        segments.append(
            dict(
                left_s=float(left),
                right_s=float(right),
                held_control_time_s=float(left),
                evaluations=int(solution.nfev) + int(local),
                accepted_steps=int(steps.size),
                minimum_accepted_step_s=float(steps.min()),
                maximum_accepted_step_s=float(steps.max()),
                **(
                    dict(
                        segment_coordinates=segment_coordinates,
                        first_step_s=first,
                        startup_pool_amount_fmol=amounts.tolist(),
                        startup_pool_rate_fmol_s=rates.tolist(),
                        startup_evaluations=1,
                    )
                    if local
                    else {}
                ),
            )
        )
        for time in times[(times > left) & (times <= right)]:
            # Preserve the actual accepted endpoint, not its interpolated value.
            value = (
                solution.y[:, -1].copy()
                if time == right
                else solution.sol(time - left if local else time)
            )
            saved[time] = origin + value if local else value
        state = origin + solution.y[:, -1] if local else solution.y[:, -1].copy()
    potentials = []
    for time in times:
        try:
            potentials.append(evaluate_coordinates(saved[time], time)[1])
        except Exception as error:
            raise failure(
                f"Reference observation failed at t={time!r}: {error}",
                time,
                time,
                saved[time],
                "observation",
            ) from error
    return dict(
        times=times.tolist(),
        state=np.stack([complete(saved[time]) for time in times]),
        potential_V=np.stack(potentials),
        initial_state=start,
        final_state=complete(state),
        evaluation_state_minimum=state_min,
        evaluation_state_maximum=state_max,
        evaluations=evaluations,
        observation_evaluations=len(times),
        accepted_steps=sum(segment["accepted_steps"] for segment in segments),
        segments=segments,
        refinement=refinement,
        method="DOP853; full-node ion kinetics, finite pools, Decimal water and cotransport",
        rtol=rtol,
        amount_volume_energy_atol=amount_atol,
        electrode_charge_atol_C=charge_atol,
        tolerance_scale=float(tolerance_scale),
        max_step_s=float(max_step_s / refinement),
        event_times=events,
        segment_coordinates=segment_coordinates,
        relative_tolerance_applies_to=(
            "segment_delta" if segment_coordinates == "local_delta" else "global_state"
        ),
        **coordinate_details,
    )
