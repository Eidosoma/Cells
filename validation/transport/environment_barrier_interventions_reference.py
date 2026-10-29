"""Independent native-pulse coefficients and complete passive-tissue dynamics.

Static coefficients are recomputed from the preparation request, never taken
from production-derived coefficient maps. A state-owned clock advances through
every adaptive RHS stage. Ordinary membrane/junction controls remain left-held
inside their event segment. No Cells or JAX import or production projection is
used. Artifact cryptographic replay is deliberately the caller's separate
software contract; this oracle checks the recipe and physical correspondence.
"""

import math
from copy import deepcopy
from decimal import Decimal, localcontext

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import surface_dynamics_reference as passive
from validation.transport import environment_barrier_preparation_reference as static

MODEL_ID = "resolved_extracellular_barriers@1"
TIMING_POLICY = "phase_clock_rk_stage_native_logistic@1"
NATIVE_SPECIES = frozenset(("Na", "K", "Cl", "Ca", "M", "P"))
EXTRA_KEYS = frozenset(("barrier_preparation", "intervention", "phase", "timing_policy"))
F, R = passive.F, passive.R
flatten, unpack = passive.flatten, passive.unpack


def _number(value, name, *, nonnegative=False, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} requires a finite number")
    if (nonnegative and value < 0) or (positive and value <= 0):
        raise ValueError(f"Invalid sign for {name}")
    return float(value)


def _same_physical_model(first, second):
    """Independent preparation arithmetic may round a face coefficient by 1 ulp."""
    left, right = deepcopy(first), deepcopy(second)
    if len(left.get("faces", [])) != len(right.get("faces", [])):
        raise ValueError("Prepared face owners differ")
    for a, b in zip(left["faces"], right["faces"], strict=True):
        da, db = a.pop("diffusivity_m2_per_s"), b.pop("diffusivity_m2_per_s")
        if da.keys() != db.keys() or any(
            not math.isclose(da[s], db[s], rel_tol=64 * np.finfo(float).eps, abs_tol=0) for s in da
        ):
            raise ValueError("Prepared face coefficients disagree with the independent recipe")
    if left != right:
        raise ValueError("Physical model differs from the static preparation recipe")


def bind(raw):
    model = raw.get("model", {})
    if model.get("id") != MODEL_ID or not EXTRA_KEYS <= model.keys():
        raise ValueError("Require the complete extracellular-barrier model")
    if model["phase"] not in ("INIT", "SIM") or model["timing_policy"] != TIMING_POLICY:
        raise ValueError("Require INIT/SIM and the stage-clock timing policy")
    artifact = model["barrier_preparation"]
    if not isinstance(artifact, dict) or set(artifact) != {"definition", "provenance"}:
        raise ValueError("Require the complete static preparation pair")
    request = artifact["provenance"]["request"]
    prepared = static.prepare(request)
    _same_physical_model(artifact["definition"]["model"], prepared["definition"]["model"])
    parent = deepcopy(raw)
    for key in EXTRA_KEYS:
        parent["model"].pop(key)
    parent["model"]["id"] = "resolved_tissue@1"
    if parent["model"] != artifact["definition"]["model"]:
        raise ValueError("Physical model must exactly match the embedded prepared model")
    ids = [row["id"] for row in parent["model"]["species"]]
    if not set(ids) <= NATIVE_SPECIES:
        raise ValueError("Native ECM supports only the named Na/K/Cl/Ca/M/P species")
    capacity = parent["execution"].pop("barrier_target_capacity")
    if type(capacity) is not int or not 0 <= capacity <= 65536:
        raise ValueError("Require a bounded integer target-occurrence capacity")
    end = _number(raw["experiment"]["end_time"], "end time", positive=True)
    dt = _number(raw["execution"]["dt"], "dt", positive=True)
    event = model["intervention"]
    sites = request["grid"]["site_ids"]
    if event is not None:
        if not isinstance(event, dict) or set(event) != {
            "name",
            "site_ids",
            "on_s",
            "off_s",
            "change_s",
            "amplitude",
        }:
            raise ValueError("Require one explicit native ECM intervention")
        if not isinstance(event["name"], str) or not event["name"]:
            raise ValueError("Intervention requires a name")
        targets = event["site_ids"]
        if not isinstance(targets, list) or not targets or any(s not in sites for s in targets):
            raise ValueError("Require nonempty ordered known target-site occurrences")
        if len(targets) > capacity:
            raise ValueError("Target capacity must retain duplicate occurrences")
        on, off, change, amplitude = (
            _number(event[k], k) for k in ("on_s", "off_s", "change_s", "amplitude")
        )
        if not 0 <= on < off <= end or change <= 0 or not 0 <= amplitude <= 1:
            raise ValueError("Invalid pulse times, transition width or amplitude")
        if dt > change / 8 * (1 + 16 * np.finfo(float).eps):
            raise ValueError("The declared timestep must resolve the transition width / 8")
    base = passive.bind(parent)
    return {
        **base,
        "parent": base,
        "definition": deepcopy(raw),
        "request": deepcopy(request),
        "static": prepared,
        "phase": model["phase"],
        "event": deepcopy(event),
        "end_time": end,
        "phase_clock_atol_s": 64 * np.finfo(float).eps * max(1.0, end),
        "shapes": base["shapes"] | {"phase_clock_s": (1,)},
    }


def initial(c):
    return np.zeros(sum(math.prod(shape) for shape in c["shapes"].values()))


def _logistic(value):
    if value >= 0:
        return 1 / (1 + (-value).exp())
    exponential = value.exp()
    return exponential / (1 + exponential)


def pulse(time_s, on_s, off_s, change_s):
    """80-digit difference of logistic functions, without a clipped on/off gate."""
    with localcontext() as context:
        context.prec = 80
        t, on, off, change = (Decimal(str(v)) for v in (time_s, on_s, off_s, change_s))
        if not all(v.is_finite() for v in (t, on, off, change)) or change <= 0 or on >= off:
            raise ValueError("Invalid native pulse parameters")
        return float(_logistic(10 * (t - on) / change) - _logistic(10 * (t - off) / change))


def coefficients(c, phase_clock_s):
    time = _number(phase_clock_s, "phase clock", nonnegative=True)
    if time > c["end_time"] + c["phase_clock_atol_s"]:
        raise ValueError("Phase clock is beyond the declared horizon")
    request, prepared = c["request"], c["static"]
    species, sites = request["grid"]["species_ids"], request["grid"]["site_ids"]
    event = c["event"]
    targets = [] if event is None else event["site_ids"]
    with localcontext() as context:
        context.prec = 80
        native = Decimal(0)
        if event is not None and c["phase"] == "SIM":
            t, on, off, change = (
                Decimal(str(v)) for v in (time, event["on_s"], event["off_s"], event["change_s"])
            )
            native = _logistic(10 * (t - on) / change) - _logistic(10 * (t - off) / change)
        effect = native * Decimal(0 if event is None else str(event["amplitude"]))
        base = prepared["coefficients"]["site_base_m2_s"]
        updated, effective, faces = {}, {}, {}
        for sid in species:
            free = Decimal(str(request["free_diffusion_m2_s"][sid]))
            updated[sid] = {site: Decimal(str(base[sid][site])) for site in sites}
            # Each occurrence writes the same baseline interpolation; duplicate
            # target occurrences do not sum effects or compound previous writes.
            for site in targets:
                original = Decimal(str(base[sid][site]))
                updated[sid][site] = original * (1 - effect) + free * effect
            effective[sid] = {
                site: updated[sid][site] * Decimal(str(request["ion_modulators"][sid][site]))
                for site in sites
            }
            faces[sid] = {}
            for name, (a, b) in zip(
                request["grid"]["internal_face_ids"],
                request["grid"]["internal_face_sites"],
                strict=True,
            ):
                left, right = effective[sid][a], effective[sid][b]
                faces[sid][name] = (
                    Decimal(0) if left == 0 or right == 0 else 2 * left * right / (left + right)
                )
        weight = {
            site: Decimal(str(value))
            for site, value in zip(sites, prepared["arrays"]["sodium_weight"], strict=True)
        }
        for site in targets:
            original = Decimal(str(prepared["arrays"]["sodium_weight"][sites.index(site)]))
            weight[site] = original * (1 - effect) + effect
        return {
            "phase_clock_s": time,
            "pulse": float(native),
            "effect": float(effect),
            "target_site_occurrences": list(targets),
            "site_base_m2_s": deepcopy(base),
            "site_updated_m2_s": {
                s: {k: float(v) for k, v in row.items()} for s, row in updated.items()
            },
            "site_effective_m2_s": {
                s: {k: float(v) for k, v in row.items()} for s, row in effective.items()
            },
            "face_m2_s": {s: {k: float(v) for k, v in row.items()} for s, row in faces.items()},
            "sodium_weight": {s: float(v) for s, v in weight.items()},
        }


def _current_parent(c, state, time):
    if np.ndim(state) != 1 or len(state) != sum(math.prod(s) for s in c["shapes"].values()):
        raise ValueError("Require the complete 13-field state")
    if not np.isfinite(state).all():
        raise ValueError("State must be finite")
    fields = unpack(c, state)
    clock = float(fields["phase_clock_s"][0])
    # SciPy's adaptive solver supplies np.float64 times. Keep configuration
    # number validation strict while admitting that runtime float scalar.
    if isinstance(time, np.floating):
        time = float(time)
    actual_time = _number(time, "absolute stage time", nonnegative=True)
    if abs(clock - actual_time) > c["phase_clock_atol_s"]:
        raise ValueError("State-owned phase clock does not match absolute time")
    value = coefficients(c, clock)
    base = dict(c["parent"], layout=deepcopy(c["parent"]["layout"]))
    model = base["raw"]["model"]
    base["layout"]["face_factor"] = [
        [
            value["face_m2_s"][species["id"]][face["id"]] * face["area_m2"] / face["length_m"]
            for face in model["faces"]
        ]
        for species in model["species"]
    ]
    if np.any(c["ai"] + fields["amount_increment"] <= 0) or np.any(
        c["ao"] + fields["extracellular_amount_increment"] <= 0
    ):
        raise ValueError("Physical ion amounts must remain positive")
    return base, fields, value


def evaluate(c, state, time, *, held_control_time=None):
    """Complete slope, instantaneous field, and independent ownership proof."""
    base, fields, value = _current_parent(c, state, time)
    control_time = time if held_control_time is None else held_control_time
    if not 0 <= control_time <= time + c["phase_clock_atol_s"]:
        raise ValueError("Invalid left-held ordinary control time")
    slope, phi, proof = passive.evaluate(base, flatten(base, fields), control_time)
    result = unpack(base, slope)
    ci = (c["ai"] + fields["amount_increment"]) / c["vi"]
    co = (c["ao"] + fields["extracellular_amount_increment"]) / c["vo"]
    n, z = len(c["vi"]), np.asarray(base["layout"]["valence"])
    chemical = (
        1e-3
        * R
        * base["layout"]["temperature"]
        * float(
            np.sum(np.log(ci) * result["amount_increment"])
            + np.sum(np.log(co) * result["extracellular_amount_increment"])
        )
    )
    electric = (
        1e-3
        * F
        * float(
            np.sum(z * result["amount_increment"] * phi[:n])
            + np.sum(z * result["extracellular_amount_increment"] * phi[n:])
        )
    )
    heat = sum(
        float(np.sum(v)) for key, v in result.items() if key.endswith("_dissipated_energy_pJ")
    )
    supplied = float(np.sum(result["reservoir_work_pJ"]) + np.sum(result["electrode_work_pJ"]))
    material = np.sum(result["amount_increment"], axis=1) + np.sum(
        result["extracellular_amount_increment"], axis=1
    )
    result["phase_clock_s"] = np.ones(1)
    return (
        flatten(c, result),
        phi,
        proof
        | {
            "phase_clock_s": value["phase_clock_s"],
            "pulse": value["pulse"],
            "effect": value["effect"],
            "material_rate_balance_fmol_s": material.tolist(),
            "charge_rate_balance_C_s": float(1e-15 * F * np.sum(z[:, 0] * material)),
            "chemical_free_energy_rate_pJ_s": chemical,
            "capacitor_free_energy_rate_pJ_s": electric,
            "dissipation_pJ_s": heat,
            "supplied_work_pJ_s": supplied,
            "physical_energy_balance_pJ_s": chemical + electric + heat - supplied,
            "barrier_parameter_work_pJ_s": 0.0,
            "barrier_energetics_scope": (
                "prescribed diffusivity has no added structural free-energy store"
            ),
        },
    )


def free_energy_change(c, state, time):
    """Independent ideal-ion and capacitor endpoint energy at current coefficients."""
    base, fields, _ = _current_parent(c, state, time)
    phi = passive.electrical.solve(passive.stage(base, flatten(base, fields), time))[0]
    if "initial_phi" not in c:
        zero = initial(c)
        before, values, _ = _current_parent(c, zero, 0.0)
        c["initial_phi"] = passive.electrical.solve(
            passive.stage(before, flatten(before, values), 0.0)
        )[0]
    with localcontext() as context:
        context.prec = 80
        dec = lambda value: Decimal(str(float(value)))  # noqa: E731
        rt = dec(R) * dec(base["layout"]["temperature"]) * Decimal("0.001")
        value = Decimal(0)
        for before, delta, volume in (
            (c["ai"], fields["amount_increment"], c["vi"]),
            (c["ao"], fields["extracellular_amount_increment"], c["vo"]),
        ):
            for s in range(before.shape[0]):
                for owner in range(before.shape[1]):
                    a0, a, v = (
                        dec(before[s, owner]),
                        dec(before[s, owner]) + dec(delta[s, owner]),
                        dec(volume[owner]),
                    )
                    value += rt * (a * ((a / v).ln() - 1) - a0 * ((a0 / v).ln() - 1))
        n = len(c["vi"])
        layout = base["layout"]
        for owner, outside, cap in zip(
            layout["membrane_cell"],
            layout["membrane_outside"],
            layout["membrane_capacitance"],
            strict=True,
        ):
            v = dec(phi[owner] - phi[n + outside])
            v0 = dec(c["initial_phi"][owner] - c["initial_phi"][n + outside])
            value += Decimal("0.5e12") * dec(cap) * (v - v0) * (v + v0)
        return float(value)


class ReferenceIntegrationError(RuntimeError):
    def __init__(self, message, diagnostics):
        super().__init__(message)
        self.diagnostics = diagnostics


def integrate(raw, *, refinement=1, max_step_s=None):
    """Segment ordinary controls while evaluating the smooth pulse at every stage."""
    if type(refinement) is not int or refinement < 1:
        raise ValueError("Require positive integer refinement")
    c = bind(raw)
    if max_step_s is None:
        max_step_s = c["end_time"] / 40
        if c["event"] is not None:
            max_step_s = min(max_step_s, c["event"]["change_s"] / 8)
    step = _number(max_step_s, "reference max step", positive=True) / refinement
    experiment = raw["experiment"]
    events = {0.0, c["end_time"]}
    for name in ("membrane_controls", "junction_controls"):
        events.update(v["time"] for group in experiment[name] for v in group["schedule"])
    if c["event"] is not None:
        events.update((c["event"]["on_s"], c["event"]["off_s"]))
    events = sorted(events)
    times = experiment["observation_times"]
    if (
        not times
        or times[0] != 0
        or times[-1] != c["end_time"]
        or any(b <= a for a, b in zip(times, times[1:], strict=False))
    ):
        raise ValueError("Require ordered observations from zero to the exact horizon")
    state = initial(c)
    saved, evaluations = {0.0: state.copy()}, 0
    atols = flatten(
        c,
        {
            key: np.full(
                shape,
                (1e-18 if key == "phase_clock_s" else 1e-29 if key.endswith("_C") else 2e-14)
                / refinement,
            )
            for key, shape in c["shapes"].items()
        },
    )

    def rhs(time, value, held):
        nonlocal evaluations
        evaluations += 1
        try:
            return evaluate(c, value, time, held_control_time=held)[0]
        except Exception as error:
            raise ReferenceIntegrationError(
                str(error),
                {
                    "time_s": float(time),
                    "held_control_time_s": float(held),
                    "state": [float(v) if np.isfinite(v) else str(v) for v in value],
                    "evaluations": evaluations,
                    "automatic_retry": False,
                },
            ) from error

    for left, right in zip(events, events[1:], strict=False):
        result = solve_ivp(
            lambda t, y, held=left: rhs(t, y, held),
            (left, right),
            state,
            method="DOP853",
            rtol=2e-11 / refinement,
            atol=atols,
            max_step=step,
            dense_output=True,
        )
        if not result.success:
            raise ReferenceIntegrationError(
                result.message,
                {
                    "time_s": float(result.t[-1]),
                    "state": result.y[:, -1].tolist(),
                    "evaluations": evaluations,
                    "automatic_retry": False,
                },
            )
        for time in times:
            if left < time <= right:
                saved[time] = result.y[:, -1].copy() if time == right else result.sol(time)
        state = result.y[:, -1]
    return {
        "times": list(times),
        "state": np.stack([saved[t] for t in times]),
        "potential_V": np.stack([evaluate(c, saved[t], t)[1] for t in times]),
        "evaluations": evaluations,
        "method": "segmented DOP853 with stage-clock Decimal pulse and independent full-node field",
        "event_times": events,
        "refinement": refinement,
        "rtol": 2e-11 / refinement,
        "amount_energy_atol": 2e-14 / refinement,
        "electrode_charge_atol_C": 1e-29 / refinement,
        "phase_clock_atol_s": 1e-18 / refinement,
        "max_step_s": step,
    }
