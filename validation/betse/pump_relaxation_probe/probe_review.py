"""Focused saved-reference review: independent arithmetic, no integration."""

import math
import sys

import relax_context as ctx

sys.path.insert(0, str(ctx.HERE.parent / "pump_coupled_audit"))
import coupled_audit as physics  # noqa: E402

c, e = ctx.c, ctx.c.e


def compare_states(ledger, name, actual, expected, limits):
    for field, lo, hi, key in (
        ("amount", 0, 52, "agreement_amount_fmol"),
        ("energy", 52, 59, "agreement_energy_pJ"),
    ):
        ledger.compare(
            name + "/" + field,
            [v[lo:hi] for v in actual["states"]],
            [v[lo:hi] for v in expected["states"]],
            limits[key],
            0.0,
        )
    ledger.compare(
        name + "/voltage",
        actual["voltage_V"],
        expected["voltage_V"],
        limits["agreement_voltage_V"],
        0.0,
    )


def domain(case, state, constants):
    """Reconstruct concentrations, charge and affinity directly from saved amounts."""
    e.shape(state, [59])
    f, rt = constants["F"], constants["R"] * case["temperature_K"]
    inside = [
        [
            case["initial_inside_mM"][i][s] + state[3 * i + s] / case["volume_pL"][i]
            for s in range(3)
        ]
        for i in range(7)
    ]
    outside = [
        case["initial_outside_mM"][s] + state[21 + s] / case["outside_volume_pL"] for s in range(3)
    ]
    minimum = min(v for row in inside + [outside] for v in row)
    c.need(minimum > 0 and min(state[52:]) >= -1e-14, "Reference physical domain")
    volts = []
    for i in range(7):
        v = case["initial_voltage_V"][i] + f * 1e-15 * math.fsum(
            case["valence"][s] * state[3 * i + s] for s in range(3)
        ) / (case["area_m2"][i] * case["specific_capacitance_F_m2"][i])
        mu = [
            rt * math.log(inside[i][s] / outside[s]) + case["valence"][s] * f * v for s in range(3)
        ]
        drive = case["delta_g0_J_mol"][i] + rt * math.log(
            case["adp_mM"][i] * case["pi_mM"][i] / (1000 * case["atp_mM"][i])
        )
        c.need(
            max(abs(z * f * v / rt) for z in case["valence"]) <= 50
            and abs(
                (
                    drive
                    + math.fsum(
                        nu * m for nu, m in zip(case["pump_stoichiometry"], mu, strict=True)
                    )
                )
                / rt
            )
            <= 80,
            "Reference voltage/affinity domain",
        )
        volts.append(v)
    return volts


def row_checks(case, row, setting, plan, constants, ledger):
    times = [i * plan["reference"]["sample_dt_s"] for i in range(1600)] + [0.01]
    c.need(row["setting"] == setting and row["times_s"] == times, "Reference grid/settings")
    e.shape(row["states"], [1601, 59])
    e.shape(row["voltage_V"], [1601, 7])
    accepted = row["accepted_times_s"]
    e.shape(accepted, [len(accepted)])
    c.need(
        2 <= len(accepted) <= 4097
        and accepted[0] == 0.0
        and accepted[-1] == 0.01
        and all(a < b for a, b in zip(accepted[:-1], accepted[1:], strict=True))
        and 0 < row["stats"]["rhs_calls"] <= 30000,
        "Reference accepted clock/work",
    )
    e.shape(row["accepted_states"], [len(accepted), 59])
    c.need(len(row["accounting"]) == len(accepted), "Reference accounting coverage")
    c.need(row["states"][0] == row["accepted_states"][0] == [0.0] * 59, "Reference initial state")
    ledger.compare(
        "sample/accepted endpoint", row["states"][-1], row["accepted_states"][-1], 1e-14, 0.0
    )
    for y, v in zip(row["states"], row["voltage_V"], strict=True):
        ledger.compare("charge/voltage", v, domain(case, y, constants), 1e-9, 0.0)
    for y in row["accepted_states"]:
        domain(case, y, constants)
    # Reuse the qualified, independently written 60-digit extensive-energy check.
    # Check every accepted endpoint plus the 41 common observation states, not
    # every interpolated dense state. Repeated states share a deterministic cache.
    observations = [i * 40 for i in range(41)]
    high_precision = [row["states"][i] for i in observations] + row["accepted_states"]
    cache, maxima = (
        {},
        dict(material_residual_fmol=0.0, charge_residual_C=0.0, energy_residual_pJ=0.0),
    )
    for y in high_precision:
        key = tuple(y)
        if key not in cache:
            cache[key] = physics.physical(case, y, constants)
        values = cache[key]
        for name, limit in (
            ("material_residual_fmol", "cells_material_fmol"),
            ("charge_residual_C", "cells_charge_C"),
            ("energy_residual_pJ", "cells_energy_pJ"),
        ):
            ledger.compare(name, values[name], 0.0, plan["accounting"][limit], 0.0)
            maxima[name] = max(maxima[name], values[name])
    return dict(
        domain_states=1601 + len(accepted),
        independent_accounting_states=len(high_precision),
        maxima=maxima,
        endpoint_voltage_V=row["voltage_V"][-1],
    )


def run(registration, summary, directory):
    with e.model_fence(), physics.model_fence():
        plan, cases = registration["protocol"], registration["cases"]
        constants = ctx.inherited()["native_preparation"]["protocol"]["constants"]
        originals = c.read(c.LEGACY / "reference.json", None)["records"]
        labels = {case + "/" + s["id"] for case in cases for s in plan["reference"]["solves"]}
        c.need(set(summary["records"]) == labels and len(labels) == 18, "Reference coverage")
        ledger, rows = e.Ledger(), {}
        for case_id, case in cases.items():
            primary_key = case_id + "/" + plan["reference"]["primary"]
            primary = c.read(c.child(directory, summary["records"][primary_key]["path"]), None)
            for setting in plan["reference"]["solves"]:
                label = case_id + "/" + setting["id"]
                link = summary["records"][label]
                path = c.child(directory, link["path"])
                c.need(
                    link["path"] == "reference/" + label + "/result.json"
                    and c.sha(path) == link["sha256"],
                    "Reference row link",
                )
                row = c.read(path, None)
                rows[label] = row_checks(case, row, setting, plan, constants, ledger)
                compare_states(ledger, "solver", row, primary, plan["reference"])
                c.need(row["times_s"][:161] == originals[label]["times_s"], "Prefix clock")
                compare_states(
                    ledger,
                    "prefix",
                    {k: row[k][:161] for k in ("states", "voltage_V")},
                    originals[label],
                    plan["reference"],
                )
                print("Saved reference reviewed: " + label, flush=True)
        return dict(
            status="focused_reference_review_pass",
            records=rows,
            reference_solves=18,
            comparisons=ledger.count,
            maxima=ledger.maxima,
            independent_accounting_states=sum(
                v["independent_accounting_states"] for v in rows.values()
            ),
            domain_states=sum(v["domain_states"] for v in rows.values()),
            dense_energy_independently_checked_only_at_common_observations=True,
            endpoint_rates_independently_reviewed=False,
            new_integrations=0,
            biology_validated=False,
            steady_state_qualified=False,
        )
