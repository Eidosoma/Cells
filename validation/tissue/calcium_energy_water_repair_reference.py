"""Independent live-volume finite-fuel/calcium/water with prescribed Na/K injury.

The five damage/lesion ledgers extend the frozen 43-field reference. Injury
changes owned chemical ions and capacitor charge; it has no direct ATP cost,
volume displacement, gating reset or structural free energy in this model.
"""

import math
from copy import deepcopy
from numbers import Real

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import calcium_energy_water_reference as parent
from validation.tissue import morris_lecar_repair_reference as clock_reference

MODEL_ID = "resolved_calcium_energy_water_repair@1"
LAW_ID = "prescribed_patch_injury_resealing@1"
F, R = parent.F, parent.R
flatten, unpack = parent.flatten, parent.unpack
analytic_clock = clock_reference.clock
ROUND_ATOL = 4096 * np.finfo(np.float64).eps
EXTRA_FIELDS = (
    "damage",
    "damage_opened",
    "damage_closed",
    "injury_transferred",
    "injury_dissipated_energy_pJ",
)


def bounded(value, low, high):
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
        or not np.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError("Invalid prescribed injury scalar")
    return float(value)


def ordered(rows, key, names):
    if not isinstance(rows, list):
        raise ValueError("Explicit injury rows must be lists")
    if any(not isinstance(row, dict) or key not in row for row in rows):
        raise ValueError("Injury rows require explicit physical identities")
    indexed = {row[key]: row for row in rows}
    if len(indexed) != len(rows) or set(indexed) != set(names):
        raise ValueError("Injury rows must cover distinct physical membrane identities")
    return [indexed[name] for name in names]


def bind(raw):
    m = raw["model"]
    if m["id"] != MODEL_ID:
        raise ValueError("Require " + MODEL_ID)
    expected = {
        "id",
        "ionic",
        "stores",
        "plasma_transport",
        "calcium_channels",
        "ip3_release",
        "energy_pools",
        "regeneration_ports",
        "chemical_osmotic_coupling",
        "energy_osmotic_coupling",
        "water_compartments",
        "water_membranes",
        "injury_patches",
    }
    if set(m) != expected:
        raise ValueError(
            "Prescribed repair does not admit hidden structural energy or other model fields"
        )
    projected = deepcopy(raw)
    patches = projected["model"].pop("injury_patches")
    controls = projected["experiment"].pop("injury_controls")
    projected["model"]["id"] = parent.MODEL_ID
    base = parent.bind(projected)
    ion = m["ionic"]
    mids = [v["id"] for v in ion["membranes"]]
    ids = [v["id"] for v in ion["species"]]
    na = m["plasma_transport"]["sodium_species"]
    if "K" not in ids or any(v["valence"] != 1 for v in ion["species"] if v["id"] in (na, "K")):
        raise ValueError("Prescribed injury requires owned Na(+1) and K(+1)")
    parsed = []
    for patch in ordered(patches, "membrane_id", mids):
        if (
            set(patch)
            != {
                "membrane_id",
                "law",
                "initial_damage",
                "injury_rate_per_s",
                "resealing_rate_per_s",
                "permeability_m_per_s",
            }
            or patch["law"] != LAW_ID
        ):
            raise ValueError("Require the explicit prescribed patch injury/resealing law")
        row = deepcopy(patch)
        row["initial_damage"] = bounded(row["initial_damage"], 0, 1)
        for key in ("injury_rate_per_s", "resealing_rate_per_s"):
            row[key] = bounded(row[key], 0, 1e5)
        if set(row["permeability_m_per_s"]) != set(ids):
            raise ValueError("Injury permeability must explicitly cover all ionic species")
        for species, value in row["permeability_m_per_s"].items():
            row["permeability_m_per_s"][species] = bounded(value, 0, 1e-5)
            if species not in (na, "K") and value != 0:
                raise ValueError("Prescribed injury transports Na/K only")
        parsed.append(row)
    schedules = []
    for row in ordered(controls, "membrane_id", mids):
        if (
            set(row) != {"membrane_id", "schedule"}
            or not isinstance(row["schedule"], list)
            or not row["schedule"]
        ):
            raise ValueError("Require a nonempty explicit injury control schedule")
        previous = -1.0
        for change in row["schedule"]:
            if set(change) != {"time", "injury", "resealing"}:
                raise ValueError("Unknown injury control fields")
            time = bounded(change["time"], 0, raw["experiment"]["end_time"])
            if time <= previous or (previous < 0 and time != 0):
                raise ValueError("Injury controls must increase strictly from time zero")
            for key in ("injury", "resealing"):
                bounded(change[key], 0, 1)
            previous = time
        schedules.append(deepcopy(row["schedule"]))
    permeability = np.array([[row["permeability_m_per_s"][name] for row in parsed] for name in ids])
    nm, ns = len(mids), len(ids)
    return dict(
        base,
        raw=deepcopy(raw),
        parent=base,
        injury=parsed,
        injury_controls=schedules,
        injury_permeability=permeability,
        initial_damage=np.array([v["initial_damage"] for v in parsed]),
        shapes=base["shapes"]
        | dict(
            damage=(nm,),
            damage_opened=(nm,),
            damage_closed=(nm,),
            injury_transferred=(ns, nm),
            injury_dissipated_energy_pJ=(ns, nm),
        ),
    )


def initial(c):
    d = unpack(c["parent"], parent.initial(c["parent"]))
    d.update({key: np.zeros(c["shapes"][key]) for key in EXTRA_FIELDS})
    d["damage"] = c["initial_damage"].copy()
    return flatten(c, d)


def damage_valid(c, d):
    damage = d["damage"]
    if np.any(damage < 0) or np.any(damage > 1):
        raise ValueError("Damage must remain within [0,1]")
    for key in ("damage_opened", "damage_closed", "injury_dissipated_energy_pJ"):
        if np.any(d[key] < -ROUND_ATOL):
            raise ValueError("Injury integrals and heat cannot be negative")
    if np.any(
        np.abs(damage - c["initial_damage"] - d["damage_opened"] + d["damage_closed"]) > ROUND_ATOL
    ):
        raise ValueError("Damage/opened/closed ledger is inconsistent")
    support = c["injury_permeability"] > 0
    for key in ("injury_transferred", "injury_dissipated_energy_pJ"):
        if np.any(d[key][~support] != 0):
            raise ValueError(
                "Unsupported injury species/routes cannot own historical transfer or heat"
            )


def evaluate(c, state, time, *, channel_levels=None):
    if (
        np.ndim(state) != 1
        or np.size(state) != sum(math.prod(shape) for shape in c["shapes"].values())
        or not np.isfinite(state).all()
    ):
        raise ValueError("Require the complete finite flat 48-field injury state")
    d = unpack(c, state)
    damage_valid(c, d)
    slope, phi, proof = parent.evaluate(
        c["parent"], flatten(c["parent"], d), time, channel_levels=channel_levels
    )
    result = unpack(c["parent"], slope)
    result.update({key: np.zeros(c["shapes"][key]) for key in EXTRA_FIELDS})
    volume = parent.volumes(c["parent"], d)
    p = c["layout"]
    ions = c["raw"]["model"]["ionic"]["species"]
    rt = R * c["temperature"]
    chemical, electric, heat_total = 0.0, 0.0, 0.0
    for j, patch in enumerate(c["injury"]):
        control = next(row for row in reversed(c["injury_controls"][j]) if row["time"] <= time)
        opened = patch["injury_rate_per_s"] * control["injury"] * (1 - d["damage"][j])
        closed = patch["resealing_rate_per_s"] * control["resealing"] * d["damage"][j]
        result["damage"][j], result["damage_opened"][j], result["damage_closed"][j] = (
            opened - closed,
            opened,
            closed,
        )
        i, o = p["membrane_cell"][j], p["membrane_outside"][j]
        store = c["stores"][i]
        vm = phi[i] - phi[len(c["vi"]) + o]
        for s, ion in enumerate(ions):
            permeability = patch["permeability_m_per_s"][ion["id"]]
            if permeability == 0:
                continue
            chemical_index = store.ids.index(ion["id"])
            ci = (store.n0 + d["chemical_amount_increment"][i])[chemical_index, store.cy] / volume[
                i
            ]
            co = (c["ao"][s, o] + d["extracellular_amount_increment"][s, o]) / volume[
                len(c["vi"]) + o
            ]
            x = ion["valence"] * F * vm / rt
            flux = (
                p["membrane_area"][j]
                * permeability
                * d["damage"][j]
                / 1e-15
                * (ci - co if x == 0 else x * (ci - co * math.exp(-x)) / -math.expm1(-x))
            )
            heat = 1e-3 * flux * (rt * math.log(ci / co) + ion["valence"] * F * vm)
            result["amount_increment"][s, i] -= flux
            result["extracellular_amount_increment"][s, o] += flux
            result["chemical_amount_increment"][i, chemical_index, store.cy] -= flux
            result["injury_transferred"][s, j] = flux
            result["injury_dissipated_energy_pJ"][s, j] = heat
            chemical -= 1e-3 * flux * rt * math.log(ci / co)
            electric -= 1e-3 * flux * ion["valence"] * F * vm
            heat_total += heat
    return (
        flatten(c, result),
        phi,
        proof
        | dict(
            injury_energy_balance_pJ_s=chemical + electric + heat_total,
            physical_energy_balance_pJ_s=proof["physical_energy_balance_pJ_s"]
            + chemical
            + electric
            + heat_total,
            physical_free_energy_rate_pJ_s=proof["physical_free_energy_rate_pJ_s"] - heat_total,
            injury_chemical_power_pJ_s=chemical,
            injury_capacitor_power_pJ_s=electric,
            injury_dissipation_pJ_s=heat_total,
            structural_repair_energy="not modelled",
            direct_structural_atp_demand_fmol_s=0.0,
        ),
    )


def free_energy_change(c, state, time=0.0):
    return parent.free_energy_change(c["parent"], flatten(c["parent"], unpack(c, state)), time)


ReferenceIntegrationError = parent.ReferenceIntegrationError


def integrate(raw, *, refinement=1, max_step_s=0.625e-6, channel_segments=None):
    if (
        type(refinement) is not int
        or refinement < 1
        or not parent.energy._number(max_step_s, positive=True)
    ):
        raise ValueError("Require positive finite refinement and step cap")
    c, e = bind(raw), raw["experiment"]
    segments = channel_segments or [(0.0, None)]
    if (
        segments[0][0] != 0
        or any(not parent.energy._number(t) or t > e["end_time"] for t, _ in segments)
        or any(b[0] <= a[0] for a, b in zip(segments, segments[1:], strict=False))
    ):
        raise ValueError("Require assembly-owner controls increasing from zero")
    events = {0.0, e["end_time"], *(t for t, _ in segments)}
    for name, groups in e.items():
        if name.endswith("_controls"):
            events.update(
                row["time"]
                for group in groups
                for row in group.get("schedule", group.get("controls", []))
            )
    y = initial(c)
    saved, evaluations = {0.0: y.copy()}, 0
    atols = flatten(
        c,
        {
            key: np.full(shape, (1e-29 if key.endswith("_C") else 2e-14) / refinement)
            for key, shape in c["shapes"].items()
        },
    )

    def rhs(t, state, held, levels):
        nonlocal evaluations
        evaluations += 1
        try:
            return evaluate(c, state, held, channel_levels=levels)[0]
        except Exception as error:
            raise ReferenceIntegrationError(
                str(error),
                dict(
                    time_s=float(t),
                    held_control_time_s=float(held),
                    state=[float(v) if np.isfinite(v) else str(v) for v in state],
                    evaluations=evaluations,
                    automatic_retry=False,
                ),
            ) from error

    for left, right in zip(sorted(events), sorted(events)[1:], strict=False):
        levels = next(value for start, value in reversed(segments) if start <= left)
        solved = solve_ivp(
            lambda t, state, held=left, opened=levels: rhs(t, state, held, opened),
            (left, right),
            y,
            method="DOP853",
            rtol=2e-11 / refinement,
            atol=atols,
            max_step=max_step_s / refinement,
            dense_output=True,
        )
        if not solved.success:
            raise ReferenceIntegrationError(
                solved.message,
                dict(
                    time_s=float(solved.t[-1]),
                    state=solved.y[:, -1].tolist(),
                    evaluations=evaluations,
                    automatic_retry=False,
                ),
            )
        for t in e["observation_times"]:
            if left < t <= right:
                saved[t] = solved.y[:, -1].copy() if t == right else solved.sol(t)
        y = solved.y[:, -1]
    return dict(
        times=e["observation_times"],
        state=np.stack([saved[t] for t in e["observation_times"]]),
        evaluations=evaluations,
        potential_V=np.stack(
            [
                evaluate(
                    c,
                    saved[t],
                    t,
                    channel_levels=next(value for start, value in reversed(segments) if start <= t),
                )[1]
                for t in e["observation_times"]
            ]
        ),
        method="segmented DOP853; independent joint43 +selective Na/K prescribed injury",
        refinement=refinement,
        rtol=2e-11 / refinement,
        amount_volume_damage_energy_atol=2e-14 / refinement,
        electrode_charge_atol_C=1e-29 / refinement,
        max_step_s=max_step_s / refinement,
        event_times=sorted(events),
    )
