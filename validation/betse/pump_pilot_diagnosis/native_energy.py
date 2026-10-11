"""Independent saved-flux accounting; no simulator, reference or producer imports.

Use total applied ion transfer and potassium pump return, rather than the
producer's passive-plus-sodium decomposition. The convex energy remainder is a
diagnostic, never a correction to the saved dissipation or acceptance budget.
"""

from decimal import Decimal as D
from decimal import localcontext

F, R = D(96485.33212331001), D(8.31446261815324)
Z, NU = (1, 1, -1), (-3, 2, 0)


def same(values):
    if not values or any(v != values[0] for v in values):
        raise ValueError("Nonuniform membrane or bath")
    return values[0]


def volts(physical, geometry):
    return [
        D(
            same(
                [
                    v
                    for v, owner in zip(
                        physical["voltage_V"], geometry["membrane_owners"], strict=True
                    )
                    if owner == i
                ]
            )
        )
        for i in range(geometry["cell_count"])
    ]


def chemical_change(old, new, volume, rt):
    """Return energy change and its nonnegative first-order Taylor remainder."""
    if min(old, new, volume, rt) <= 0:
        raise ValueError("Nonpositive energy domain")
    dn = (new - old) * volume
    remainder = rt * volume * (new * (new / old).ln() - (new - old)) / 1000
    return rt * dn * old.ln() / 1000 + remainder, remainder


def capacitor_change(old, new, capacitance):
    dv = new - old
    return capacitance * dv * (new + old) * D("5e11"), capacitance * dv * dv * D("5e11")


def reconstruct(row, variant, times, ledger, *, progress=None):
    with localcontext() as context:
        context.prec = 70
        return _reconstruct(row, variant, times, ledger, progress=progress)


def _reconstruct(row, variant, times, ledger, *, progress=None):
    g, trace = row["geometry"], row["trace"]
    n, dt = g["cell_count"], D(row["dt_s"])
    if n != 7 or g["membrane_count"] != 30 or len(trace["steps"]) != row["steps"]:
        raise ValueError("Native scope")
    initial = trace["initial"]["physical"]
    vi = [D(v) * D("1e15") for v in g["cell_volumes_m3"]]
    vo = D(g["effective_bath_volume_m3"]) * D("1e15")
    cap = [D(a) * D(g["specific_capacitance_F_per_m2"]) for a in g["cell_areas_m2"]]
    rt = R * D(row["settings"]["temperature_K"])
    p = {k: D(v) for k, v in row["settings"]["pump_parameters"].items()}
    drive = p["deltaGATP"] + rt * (p["cADP"] * p["cPi"] / (1000 * p["cATP"])).ln()
    leaks, cycles, dissipated = [[D(0)] * 3 for _ in range(n)], [D(0)] * n, [D(0)] * n
    energy_delta, convex_chemical, convex_capacitor = D(0), D(0), D(0)
    worst_defect, worst_remainder, max_transfer = D(0), D(0), 0.0
    records, energy_records = [], []
    previous = initial
    for index, (step, raw) in enumerate(zip(trace["steps"], trace["raw_steps"], strict=True)):
        old, new = raw["before"]["physical"], step["after_voltage"]["physical"]
        for field in ("inside_mM", "outside_mM", "voltage_V", "at_membrane_mM"):
            if old[field] != previous[field]:
                raise ValueError("Disconnected native history")
        if (
            step["index"] != index
            or raw["index"] != index
            or step["before_elapsed_s"] != index * row["dt_s"]
            or step["after_elapsed_s"] != (index + 1) * row["dt_s"]
            or raw["before"]["rho_pump"] != variant["rho_pump"]
            or raw["before"]["pump_block"] != 1.0
        ):
            raise ValueError("Clock/control mismatch")
        before = step["before_ordinary"]["physical"]
        for field in ("inside_mM", "outside_mM", "at_membrane_mM"):
            if (
                old[field] != before[field]
                or new[field] != step["after_ordinary"]["physical"][field]
            ):
                raise ValueError("Hidden concentration update")
        applied = before["ordinary_density_mol_per_m2_s"]
        pump = [call for call in raw["calls"] if call["function"] == "pumpNaKATP"]
        passive = [call for call in raw["calls"] if call["function"] == "electroflux"]
        if (
            len(pump) != int(variant["pump"])
            or [c["species_index"] for c in passive] != list(range(6))
            or len(raw["calls"]) != 6 + len(pump)
        ):
            raise ValueError("Raw source coverage")
        transfer, cycle_step = [[D(0)] * 3 for _ in range(n)], [D(0)] * n
        for j, (owner, area) in enumerate(
            zip(g["membrane_owners"], g["membrane_areas_m2"], strict=True)
        ):
            active = variant["cluster_open"] or j not in g["boundary_faces"]
            density = D(0)
            if pump:
                density = (
                    D(pump[0]["returned"][1][j]) / 2 * D(variant["rho_pump"]) if active else D(0)
                )
                ledger.compare(
                    "pump_stoichiometry_density",
                    pump[0]["returned"][0][j],
                    float(-D(3) * D(pump[0]["returned"][1][j]) / 2),
                    2e-18,
                )
            factor = D(area) * dt * D("1e15")
            cycle_step[owner] += density * factor
            for s in range(6):
                expected = (D(passive[s]["returned"][j]) if active else D(0)) + (
                    D(NU[s]) * density if s < 3 else D(0)
                )
                ledger.compare("applied_density", applied[s][j], float(expected), 2e-18)
                if s < 3:
                    transfer[owner][s] += D(applied[s][j]) * factor
                elif (
                    applied[s][j] != 0
                    or new["inside_mM"][s] != initial["inside_mM"][s]
                    or new["outside_mM"][s] != initial["outside_mM"][s]
                ):
                    raise ValueError("Immobile species moved")
        old_v, new_v = volts(old, g), volts(new, g)
        for i in range(n):
            transport_work = D(0)
            for s in range(3):
                ci, co = D(old["inside_mM"][s][i]), D(same(old["outside_mM"][s]))
                mu = rt * (ci / co).ln() + Z[s] * F * old_v[i]
                transport_work += mu * transfer[i][s]
                leaks[i][s] += transfer[i][s] - NU[s] * cycle_step[i]
                actual = (D(new["inside_mM"][s][i]) - ci) * vi[i]
                max_transfer = max(max_transfer, abs(float(actual - transfer[i][s])))
                ledger.compare(
                    "single_inside_transfer_fmol", float(actual), float(transfer[i][s]), 2e-12
                )
            diss = -(transport_work + drive * cycle_step[i]) / 1000
            if diss < D("-1e-20"):
                raise ValueError("Negative dissipation")
            dissipated[i] += diss
            cycles[i] += cycle_step[i]
            change, gap = capacitor_change(old_v[i], new_v[i], cap[i])
            energy_delta += change
            convex_capacitor += gap
        for i in range(n + 1):
            for s in range(3):
                a = D(old["inside_mM"][s][i]) if i < n else D(same(old["outside_mM"][s]))
                b = D(new["inside_mM"][s][i]) if i < n else D(same(new["outside_mM"][s]))
                change, gap = chemical_change(a, b, vi[i] if i < n else vo, rt)
                energy_delta += change
                convex_chemical += gap
                if i == n:
                    actual = (b - a) * vo
                    predicted = -sum(v[s] for v in transfer)
                    max_transfer = max(max_transfer, abs(float(actual - predicted)))
                    ledger.compare(
                        "single_bath_transfer_fmol", float(actual), float(predicted), 2e-12
                    )
        work = -drive * sum(cycles) / 1000
        defect = energy_delta + sum(dissipated) - work
        gap = convex_chemical + convex_capacitor
        worst_defect = max(worst_defect, abs(defect))
        worst_remainder = max(worst_remainder, abs(defect - gap))
        t = step["after_elapsed_s"]
        energy_records.append(
            dict(
                time_s=t,
                defect_pJ=float(defect),
                convex_chemical_pJ=float(convex_chemical),
                convex_capacitor_pJ=float(convex_capacitor),
                residual_after_convex_pJ=float(defect - gap),
            )
        )
        if any(abs(t - wanted) < 1e-15 for wanted in times):
            q = [
                (D(new["inside_mM"][s][i]) - D(initial["inside_mM"][s][i])) * vi[i]
                for i in range(n)
                for s in range(3)
            ]
            q += [
                (D(same(new["outside_mM"][s])) - D(same(initial["outside_mM"][s]))) * vo
                for s in range(3)
            ]
            state = q + [x for row_ in leaks for x in row_] + cycles + dissipated
            records.append(
                dict(time_s=t, state=list(map(float, state)), voltage_V=list(map(float, new_v)))
            )
        previous = new
        if progress is not None and ((index + 1) % 1000 == 0 or index + 1 == row["steps"]):
            progress("energy_steps", completed=index + 1, total=row["steps"])
    records.insert(
        0, dict(time_s=0.0, state=[0.0] * 59, voltage_V=list(map(float, volts(initial, g))))
    )
    if len(records) != len(times) or row["final"]["physical"] != previous:
        raise ValueError("Native sample/final coverage")
    return dict(
        times_s=[v["time_s"] for v in records],
        states=[v["state"] for v in records],
        voltage_V=[v["voltage_V"] for v in records],
        energy=dict(
            max_defect_pJ=float(worst_defect),
            max_unexplained_pJ=float(worst_remainder),
            max_single_transfer_roundoff_fmol=max_transfer,
            final=energy_records[-1],
            history=energy_records,
        ),
        steps=row["steps"],
    )
