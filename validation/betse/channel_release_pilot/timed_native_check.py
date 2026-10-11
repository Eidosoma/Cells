"""D105 version of D093 loop checks with explicit interval availability.

Original algebra/budgets retained; D103 exact source-order remixing checks replace
only the incorrect blocked bath identity. No fabricated single-update receipts.
"""

import math
from decimal import localcontext

import feedback_compare as old
import paired_native_check as fixture
import review_check as input_check
import review_math as remix
import timed_context as ctx

c, io = ctx.c, ctx.io
t, oldcheck, ind = old.oldcheck.t, old.oldcheck.oldcheck, old.oldcheck.ind
expected_order = old.oldcheck.expected_order


class Ledger(io.Ledger):
    def __init__(self, tolerances, failure_path=None):
        super().__init__(tolerances, tolerances["relative"], failure_path)
        self.remix_records, self.original_guard_rejections = [], []

    def add(self, name, a, b, unit):
        if "/zero_flux_mean/" in name:
            c.require(abs(a - b) <= 2e-12 + self.relative * abs(b), "Local remix material budget")
        self.compare(name, a, b, unit)


def stage_checks(ledger, prefix, value, initial, g, p, base):
    n, m = g["cell_count"], g["membrane_count"]
    stage = value["physical"]
    for field in ("inside_mM", "outside_mM", "at_membrane_mM"):
        oldcheck.shape_finite(stage[field], [6, n if field == "inside_mM" else m], field)
    for name in (
        "ordinary_density_mol_per_m2_s",
        "junction_density_mol_per_m2_s",
        "extra_rho_cells_C_per_m3",
        "extra_rho_env_C_per_m3",
        "boundary_voltage_V",
    ):
        oldcheck.require_zero(stage[name], name)
    vi = [v / 1e-15 for v in g["cell_volumes_m3"]]
    vo = g["effective_bath_volume_m3"] / 1e-15
    for s in range(6):
        outside = t.uniform_bath(stage["outside_mM"][s])
        c.require(
            outside > 0 and all(v > 0 for v in stage["inside_mM"][s]), "Nonpositive chemistry"
        )
        ledger.compare(
            prefix + f"/membrane/{s}",
            stage["at_membrane_mM"][s],
            [stage["inside_mM"][s][owner] for owner in g["membrane_owners"]],
            "concentration_mM",
        )
        residual = math.fsum(
            [
                (v - b) * volume
                for v, b, volume in zip(
                    stage["inside_mM"][s], initial["inside_mM"][s], vi, strict=True
                )
            ]
            + [(outside - t.uniform_bath(initial["outside_mM"][s])) * vo]
        )
        ledger.compare(prefix + f"/conservation/{s}", residual, 0, "amount_fmol")
        if s != 1:
            c.require(
                stage["inside_mM"][s] == initial["inside_mM"][s]
                and stage["outside_mM"][s] == initial["outside_mM"][s],
                "Inactive species changed",
            )
    voltage = t.uniform_faces(stage["voltage_V"], g["membrane_owners"], n)
    c.require(all(-0.12 <= v <= 0.06 for v in voltage), "Voltage outside kinetic domain")
    if value["channel"] is not None:
        ch = value["channel"]
        c.require(ch["modulator"] == 1 or ch["modulator"] == [1.0] * m, "Nonconstant modulation")
        for key in ("m", "h"):
            gate = t.uniform_faces(value["channel"][key], g["membrane_owners"], n)
            c.require(all(0 <= q <= 1 for q in gate), "Gate outside unit domain")
        product = [m0 * h0 for m0, h0 in zip(ch["m"], ch["h"], strict=True)]
        ledger.compare(prefix + "/derived_product", ch["derived_m_times_h"], product, "gate")
        if ch["P"] is not None:
            ledger.compare(prefix + "/native_P", ch["P"], product, "gate")


def pre_channel_voltage(values):
    # FULL evaluates six zero-permeability ordinary ion fluxes before the
    # channel boundary. The pinned electroflux adds its 1e-25 V nonce in place
    # on each call, even at zero flux. Reproduce operation order, not 6*nonce.
    result = list(values)
    for _ in range(6):
        result = [value + 1e-25 for value in result]
    return result


def observed(r, variant, row, ledger):
    p, phy, trace = r["protocol"], r["transport_protocol"], row["trace"]
    g = row["geometry"]
    n, m, dt, f = g["cell_count"], g["membrane_count"], p["dt_s"], phy["constants"]["F"]
    c.require(
        trace["status"] == "complete_observation_not_qualification"
        and trace["hook_restored"] is True
        and trace["pending"] is None,
        "Incomplete observed trace",
    )
    c.require(
        all(v == 1 for v in trace["calls"].values())
        and len(trace["calls"]) == 7
        and trace["gate_initializations"] == int(variant["channel"]),
        "Repeated/missing native setup",
    )
    c.require(len(trace["steps"]) == len(trace["labels_s"]) == p["steps"], "Missing step")
    c.require(trace["sampled_indices"] == list(range(1, p["steps"])), "Native sampling changed")
    c.require(
        trace["storage"]
        == [{"index": i, "raw_label_s": trace["labels_s"][i]} for i in trace["sampled_indices"]],
        "Stored clock changed",
    )
    for i, label in enumerate(trace["labels_s"]):
        c.require(
            math.isclose(
                label, i * p["duration_s"] / (p["steps"] - 1), rel_tol=1e-15, abs_tol=1e-20
            ),
            "Native linspace labels changed",
        )
    c.require(
        trace["initial"]["channel"] == row["fixture"]["after"]["channel"],
        "Fixture was reset/advanced before loop",
    )
    initial = trace["initial"]["physical"]
    for region in ("inside_mM", "outside_mM"):
        c.require(initial[region] == row["core_initial"][region], "Pre-loop inventory changed")
    previous, accumulated = trace["initial"], [0.0] * n
    vi = [v / 1e-15 for v in g["cell_volumes_m3"]]
    vo = g["effective_bath_volume_m3"] / 1e-15
    for i, step in enumerate(trace["steps"]):
        prefix = row["condition"] + f"/step/{i}"
        u = row["timed_input"]["intervals"][i]["availability"]
        c.require(
            step["index"] == i
            and step["raw_label_s"] == trace["labels_s"][i]
            and step["before_elapsed_s"] == i * dt
            and step["after_elapsed_s"] == (i + 1) * dt,
            "Wrong elapsed/label clock mapping",
        )
        c.require(step["order"] == expected_order(variant), "Wrong gate/transfer/voltage ordering")
        c.require(
            set(step)
            == {"index", "raw_label_s", "before_elapsed_s", "after_elapsed_s", "before", "order"}
            | set(step["order"]),
            "Unrecorded/extra boundary",
        )
        b, final = step["before"]["physical"], step["after_voltage"]["physical"]
        for region in ("inside_mM", "outside_mM"):
            c.require(b[region] == previous["physical"][region], "Unowned inter-step transfer")
        c.require(step["before"]["channel"] == previous["channel"], "Inter-step gate reset")
        c.require(
            b["voltage_V"] == pre_channel_voltage(previous["physical"]["voltage_V"]),
            "Pre-channel native voltage nonce differs",
        )
        ledger.compare(
            prefix + "/read_previous_voltage",
            b["voltage_V"],
            previous["physical"]["voltage_V"],
            "voltage_V",
        )
        density = [0.0] * m
        if variant["network"]:
            oldcheck.require_zero(
                step["after_clear"]["network_current"], "uncleared network current"
            )
        if variant["channel"]:
            cb, ca = step["before_gate"]["channel"], step["after_gate"]["channel"]
            c.require(
                step["before_channel"]["physical"] == step["before_gate"]["physical"]
                and step["before_channel"]["network_current"]
                == step["before_gate"]["network_current"]
                and {k: v for k, v in step["before_channel"]["channel"].items() if k != "modulator"}
                == {k: v for k, v in cb.items() if k != "modulator"},
                "Hidden pre-gate mutation",
            )
            for region in ("inside_mM", "outside_mM", "voltage_V"):
                c.require(
                    step["after_gate"]["physical"][region]
                    == step["before_gate"]["physical"][region],
                    "Gate-only boundary already transferred ions",
                )
            c.require(
                step["after_channel"]["channel"]["m"] == ca["m"]
                and step["after_channel"]["channel"]["h"] == ca["h"],
                "Double gate update",
            )
            for face, owner in enumerate(g["membrane_owners"]):
                v = step["before_gate"]["physical"]["voltage_V"][face]
                with localcontext() as dec:
                    dec.prec = 80
                    targets, tau = ind.kinetics(v)
                    expected = ind.native_step([cb["m"][face], cb["h"][face]], targets, tau, dt)
                    ledger.compare(
                        prefix + f"/gates/{face}",
                        [ca["m"][face], ca["h"][face]],
                        list(map(float, expected)),
                        "gate",
                    )
                    opened = ind.d(ca["m"][face]) * ind.d(ca["h"][face])
                    permeability = ind.d(phy["max_permeability_m_per_s"]) * opened * ind.d(u)
                    density[face] = float(
                        ind.inward_density(
                            v,
                            b["inside_mM"][1][owner],
                            t.uniform_bath(b["outside_mM"][1]),
                            permeability,
                            phy,
                        )
                    )
                ledger.compare(prefix + f"/open/{face}", ca["P"][face], float(opened), "gate")
                ledger.compare(
                    prefix + f"/diffusivity/{face}",
                    step["after_channel"]["channel"]["DChan_m2_per_s"][face],
                    float(permeability) * phy["thickness_m"],
                    "diffusivity_m2_per_s",
                )
            ledger.compare(
                prefix + "/density",
                step["after_channel"]["channel"]["density_mol_per_m2_s"],
                density,
                "density_mol_per_m2_s",
            )
            density = step["after_channel"]["channel"]["density_mol_per_m2_s"]
            c.require(
                ca["m"] != cb["m"] and ca["h"] != cb["h"],
                "Gates did not advance, including under block",
            )
            c.require(
                step["after_channel"]["physical"]["extra_current_density_A_per_m2"]
                == b["extra_current_density_A_per_m2"],
                "Premature current export",
            )
        flux = [v * 1e15 for v in t.cell_sums(density, g)]
        current = [-f * value for value in density]
        for name in ["before", *step["order"]]:
            c.require(
                (step[name]["channel"] is not None) == variant["channel"],
                "Changed channel inventory",
            )
            stage_checks(
                ledger, prefix + "/" + name, step[name], initial, g, phy, r["base_protocol"]
            )
            s = step[name]["physical"]
            after_transfer = name in (
                "after_channel",
                "before_network",
                "after_network",
                "before_ordinary",
                "after_ordinary",
                "after_voltage",
            )
            expected_ci = [
                old + (dt * q / volume if after_transfer else 0)
                for old, q, volume in zip(b["inside_mM"][1], flux, vi, strict=True)
            ]
            expected_co = t.uniform_bath(b["outside_mM"][1]) - (
                dt * math.fsum(flux) / vo if after_transfer else 0
            )
            ledger.compare(
                prefix + f"/{name}/K_inside", s["inside_mM"][1], expected_ci, "concentration_mM"
            )
            ledger.compare(
                prefix + f"/{name}/K_outside",
                t.uniform_bath(s["outside_mM"][1]),
                expected_co,
                "concentration_mM",
            )
            if name in ("after_network", "before_ordinary", "after_ordinary", "after_voltage"):
                ledger.compare(
                    prefix + f"/{name}/current",
                    s["extra_current_density_A_per_m2"],
                    current,
                    "current_density_A_per_m2",
                )
            if name in ("after_channel", "before_network", "after_network"):
                ledger.compare(
                    prefix + f"/{name}/network_current",
                    step[name]["network_current"],
                    current,
                    "current_density_A_per_m2",
                )
        ledger.compare(
            prefix + "/Jmem", final["Jmem_A_per_m2"], current, "current_density_A_per_m2"
        )
        average = [
            q / area for q, area in zip(t.cell_sums(current, g), g["cell_areas_m2"], strict=True)
        ]
        smoothed = [
            a * j + b0 * average[owner]
            for a, b0, j, owner in zip(
                row["smooth_weight_mem"],
                row["smooth_weight_other"],
                current,
                g["membrane_owners"],
                strict=True,
            )
        ]
        ledger.compare(prefix + "/Jn", final["Jn_A_per_m2"], smoothed, "current_density_A_per_m2")
        ledger.compare(
            prefix + "/I_mem",
            final["I_mem_A"],
            [-j * a for j, a in zip(smoothed, g["membrane_areas_m2"], strict=True)],
            "current_A",
        )
        accumulated = [a + dt * q for a, q in zip(accumulated, flux, strict=True)]
        ledger.compare(
            prefix + "/accumulated_transfer",
            [
                (a - b0) * volume
                for a, b0, volume in zip(
                    final["inside_mM"][1], initial["inside_mM"][1], vi, strict=True
                )
            ],
            accumulated,
            "amount_fmol",
        )
        ledger.compare(
            prefix + "/charge_voltage",
            t.uniform_faces(final["voltage_V"], g["membrane_owners"], n),
            [
                v0 + q * f * 1e-15 / (a * g["specific_capacitance_F_per_m2"])
                for v0, q, a in zip(
                    t.uniform_faces(initial["voltage_V"], g["membrane_owners"], n),
                    accumulated,
                    g["cell_areas_m2"],
                    strict=True,
                )
            ],
            "voltage_V",
        )
        remix.check_zero_flux_boundaries(
            prefix,
            {
                name: step[name]
                for name in (
                    "before",
                    "after_channel",
                    "after_network",
                    "after_ordinary",
                    "after_voltage",
                )
            },
            g,
            phy["max_permeability_m_per_s"] * phy["thickness_m"] * u,
            ledger,
        )
        if not u:
            oldcheck.require_zero(density, "blocked density")
            c.require(
                final["inside_mM"] == b["inside_mM"]
                and final["voltage_V"] == previous["physical"]["voltage_V"],
                "Blocked inventories changed",
            )
        else:
            c.require(all(q < 0 for q in flux), "Missing active outward K transfer")
        previous = step["after_voltage"]
    c.require(row["final"] == previous, "Final export differs from last completed step")
    c.require(
        row["histories"]["time"]["values"]
        == [trace["labels_s"][i] for i in trace["sampled_indices"]],
        "Native stored time values differ",
    )
    for name, field in (
        ("cc_time", "inside_mM"),
        ("cc_env_time", "outside_mM"),
        ("vm_time", "voltage_V"),
        ("I_mem_time", "I_mem_A"),
        ("rho_cells_time", "rho_C_per_m3"),
    ):
        c.require(
            row["histories"][name]["values"]
            == [
                trace["steps"][i]["after_voltage"]["physical"][field]
                for i in trace["sampled_indices"]
            ],
            "Native history/observer disagreement",
        )
    return {
        "id": variant["id"],
        "observed_steps": len(trace["steps"]),
        "accumulated_inward_K_fmol": accumulated,
        "maximum_voltage_change_V": max(
            abs(v - v0)
            for v, v0 in zip(previous["physical"]["voltage_V"], initial["voltage_V"], strict=True)
        ),
    }


def input_checks(view, row):
    schedule = view["schedules"][row["condition"]]
    table = ctx.intervals(schedule, view["protocol"]["duration_s"], row["dt_s"])
    timed = row["timed_input"]
    c.require(
        timed["schedule"] == schedule
        and timed["completed_updates"] == len(table)
        and timed["builtin_tissue_event"] is False
        and timed["native_clock_modified"] is False,
        "Timed input scope/clock",
    )
    maximum = (
        view["preparation_registration"]["transport_protocol"]["max_permeability_m_per_s"]
        * view["preparation_registration"]["transport_protocol"]["thickness_m"]
    )
    c.require(
        len(timed["intervals"]) == len(table) and len(timed["applications"]) == len(schedule),
        "Input coverage",
    )
    for i, (actual, expected) in enumerate(zip(timed["intervals"], table, strict=True)):
        c.require(
            {k: actual[k] for k in expected} == expected
            and actual["maxDm_m2_per_s"] == maximum * expected["availability"]
            and math.isclose(
                actual["raw_label_s"],
                i * view["protocol"]["duration_s"] / (len(table) - 1),
                rel_tol=1e-15,
                abs_tol=1e-20,
            ),
            "Native elapsed versus raw label/input differs",
        )
    previous = maximum
    for receipt, control in zip(timed["applications"], schedule, strict=True):
        index = round(control["time"] / row["dt_s"])
        c.require(
            receipt["index"] == receipt["completed_updates"] == index
            and receipt["elapsed_s"] == control["time"]
            and receipt["availability"] == control["availability"]
            and receipt["baseline_maxDm_m2_per_s"] == maximum
            and receipt["previous_maxDm_m2_per_s"] == previous
            and receipt["applied_maxDm_m2_per_s"] == maximum * control["availability"]
            and receipt["before"] == receipt["after"]
            and receipt["numeric_inventory"] == receipt["numeric_inventory_after"],
            "Input altered state or used wrong boundary",
        )
        input_check.inventory_link(receipt["numeric_inventory"], receipt["before"])
        remix.moving_ions(receipt["numeric_inventory"])
        if row["trace"] is not None:
            source = (
                row["trace"]["initial"] if index == 0 else row["trace"]["steps"][index]["before"]
            )
            c.require(
                receipt["before"] == source, "Input state differs from observed elapsed boundary"
            )
        previous = receipt["applied_maxDm_m2_per_s"]


def points(view, row, variant, ledger, side=None):
    schedule = view["schedules"][row["condition"]]
    probes = row["fresh_probes"] if side is None else [entry[side] for entry in row["side_probes"]]
    output = []
    for probe in probes:
        t0 = probe["elapsed_s"]
        one = view | {"protocol": view["protocol"] | {"common_times_s": [t0]}}
        observed_row = row | {"fresh_probes": [probe]}
        u = ctx.availability(schedule, t0, "right" if side is None else side)
        output.extend(
            old.native_points(
                one,
                observed_row,
                variant
                | {
                    "id": row["condition"] + ("/samples" if side is None else "/switch_" + side),
                    "permeability_fraction": u,
                },
                ledger,
            )
        )
    return output


def check(r, output, aggregate):
    expected = {
        h + "/" + ctx.key(v, s)
        for h in r["plan"]["histories"]
        for v in r["plan"]["conditions"]
        for s in r["plan"]["native_steps_s"]
    }
    c.require(
        set(aggregate["records"]) == expected and aggregate["native_runs"] == 2 * len(expected),
        "Timed native coverage",
    )
    original = c.read(ctx.feedback.audit.preparation.audit.CAPTURE / "betse.json")
    results, counts, failures = {}, 0, 0
    for history, view in r["views"].items():
        points_by_key, sides, summaries, saved = {}, {}, {}, {}
        variant = next(
            v
            for v in view["preparation_registration"]["transport_protocol"]["variants"]
            if v["id"] == "active_channel"
        )
        for condition in r["plan"]["conditions"]:
            for step in r["plan"]["native_steps_s"]:
                key = ctx.key(condition, step)
                paths = aggregate["records"][history + "/" + key]
                a, b = (io.read_compressed(output / paths[m]) for m in ("observed", "unobserved"))
                registration = ctx.feedback.loop_registration(view, step)
                for row in (a, b):
                    c.require(row["condition"] == condition, "Native condition")
                    fixture.preparation(registration, variant, row, original)
                    old.native_saved_state_contract(
                        row, registration["transport_protocol"]["constants"]
                    )
                    input_checks(view, row)
                excluded = {"mode", "trace", "fresh_probes", "side_probes"}
                c.require(
                    {k: v for k, v in a.items() if k not in excluded}
                    == {k: v for k, v in b.items() if k not in excluded}
                    and b["trace"] is b["fresh_probes"] is b["side_probes"] is None,
                    "Native observer changed state",
                )
                tolerances = registration["transport_protocol"]["tolerances"].copy()
                tolerances["amount_fmol"] = old.accumulation_tolerance(view, a["steps"])
                ledger = Ledger(
                    tolerances, output / history / "native" / key / "boundary-failures.jsonl"
                )
                observed(registration, variant, a, ledger)
                points_by_key[key] = points(view, a, variant, ledger)
                c.require(
                    [s["time_s"] for s in a["side_probes"]]
                    == [r["plan"]["block_time_s"], r["plan"]["release_time_s"]],
                    "Native side probe clocks",
                )
                sides[key] = {
                    side: points(view, a, variant, ledger, side) for side in ("left", "right")
                }
                summaries[key] = ledger.summary() | {
                    "remixing": remix.summary(ledger.remix_records),
                    "remix_records": ledger.remix_records,
                    "original_guard_rejections": ledger.original_guard_rejections,
                }
                failures += ledger.failed
                counts += ledger.count
                saved[key] = a
        for step in r["plan"]["native_steps_s"]:
            baseline, no_op = (saved[ctx.key(v, step)] for v in ("baseline", "no_op"))
            c.require(
                baseline["final"] == no_op["final"]
                and baseline["histories"] == no_op["histories"]
                and baseline["trace"] == no_op["trace"],
                "No-op schedule changed native trajectory",
            )
        results[history] = {
            "status": "pass" if all(v["status"] == "pass" for v in summaries.values()) else "fail",
            "points": points_by_key,
            "sides": sides,
            "boundary_checks": summaries,
        }
    return {
        "status": "pass" if failures == 0 else "fail",
        "by_history": results,
        "comparisons": counts,
        "failed_comparisons": failures,
        "observer_pairs": len(expected),
    }
