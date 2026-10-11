"""Saved full-loop boundary checks; no calls into either simulator."""

import math
from decimal import localcontext

import loop_context as ctx

c, t, oldcheck, ind = ctx.c, ctx.t, ctx.check, ctx.audit.independent


def expected_order(variant):
    order = []
    if variant["network"]:
        order += ["after_clear"]
        if variant["channel"]:
            order += ["before_channel", "before_gate", "after_gate", "after_channel"]
        order += ["before_network", "after_network"]
    return order + ["before_ordinary", "after_ordinary", "after_voltage"]


def preparation(r, variant, row, reference):
    p, fixture = r["protocol"], row["fixture"]
    v = variant["id"]
    ref = reference["rows"][v + "/prescribed_mh_a"]
    prep = reference["preparations"][v]
    c.require(
        row["id"] == v and row["mode"] in p["modes"] and row["phase"] == "INIT",
        "Wrong lifecycle row",
    )
    c.require(
        row["settings"] == prep["settings"]
        and row["geometry"] == prep["geometry"]
        and row["source_constants"] == prep["source_constants"],
        "Changed physical preparation",
    )
    c.require(row["core_initial"] == ref["core_initial"], "Changed core initialization")
    c.require(
        fixture["applications"] == 1
        and fixture["declared_gate"] == p["initial_gate"]
        and row["fixture_hook"] == {"calls": 1, "returns": 1}
        and row["hook_restored"] is True,
        "Incomplete/repeated fixture or profiling hook",
    )
    meta = fixture["metadata"]
    c.require(
        meta["channel"] == ref["metadata"]
        and all(
            meta[k] == ref[k]
            for k in (
                "species",
                "valence",
                "sim_temperature_K",
                "rho_channel",
                "ordinary_diffusivity_m2_per_s",
                "network_inventory",
            )
        ),
        "Changed actual channel/network",
    )
    c.require(
        fixture["before"]["physical"] == fixture["after"]["physical"]
        and fixture["before"]["network_current"] == fixture["after"]["network_current"],
        "Fixture changed physical state",
    )
    c.require(
        fixture["before"]["channel"] == ref["initialized_channel"]
        and fixture["after"]["channel"] == ref["channel_before"],
        "Changed gate fixture",
    )
    for stage in ("before", "after"):
        for region in ("inside_mM", "outside_mM"):
            c.require(
                fixture[stage]["physical"][region] == row["core_initial"][region],
                "Initialization changed ionic inventories",
            )
    c.require(row["steps"] == p["steps"] and row["dt_s"] == p["dt_s"], "Wrong step settings")
    for group in ("final_arrays", "histories"):
        for record in row[group].values():
            ctx.validate_array_record(record)
    for key, value in row["final"]["physical"].items():
        c.require(row["final_arrays"][key]["values"] == value, "Final arrays/raw state disagree")
    if row["trace"] is not None:
        c.require(
            row["trace"]["initial"]["physical"] == ref["before"],
            "Full-loop initial voltage/current/inventory differs from qualified preparation",
        )


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
        prefix = variant["id"] + f"/step/{i}"
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
                    permeability = (
                        ind.d(phy["max_permeability_m_per_s"])
                        * opened
                        * ind.d(variant["permeability_fraction"])
                    )
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
        if not variant["permeability_fraction"]:
            oldcheck.require_zero(density, "blocked density")
            c.require(
                final["inside_mM"] == initial["inside_mM"]
                and final["outside_mM"] == initial["outside_mM"],
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


def evaluate(r, native):
    reference = c.read(ctx.audit.CAPTURE / "betse.json")
    rows = native["rows"]
    c.require(
        set(rows)
        == {v + "/" + mode for v in r["protocol"]["variants"] for mode in r["protocol"]["modes"]},
        "Incomplete paired coverage",
    )
    ledger, summaries = oldcheck.Ledger(r["transport_protocol"]), []
    for variant in r["transport_protocol"]["variants"]:
        a, b = (rows[variant["id"] + "/" + mode] for mode in r["protocol"]["modes"])
        for row in (a, b):
            preparation(r, variant, row, reference)
        c.require(b["trace"] is None, "Unobserved counterpart has a step observer")
        excluded = {"mode", "trace"}
        c.require(
            {k: v for k, v in a.items() if k not in excluded}
            == {k: v for k, v in b.items() if k not in excluded},
            "Observer changed exported state/history",
        )
        summaries.append(observed(r, variant, a, ledger))
    off, empty, blocked = (
        rows[name + "/observed"] for name in ("network_off", "empty_network", "blocked_channel")
    )
    c.require(
        off["final"]["physical"] == empty["final"]["physical"] == blocked["final"]["physical"],
        "Inactive network controls differ physically",
    )
    c.require(
        len({row["id"] for row in ledger.rows}) == len(ledger.rows), "Duplicate comparison ID"
    )
    failed = [v for v in ledger.rows if not v["passed"]]
    return {
        "status": "pass" if not failed else "fail",
        "comparison_count": len(ledger.rows),
        "failed_comparisons": len(failed),
        "comparisons": ledger.rows,
        "summaries": summaries,
        "observer_pairs_checked": 4,
        "observed_steps": sum(v["observed_steps"] for v in summaries),
        "coupled_trajectory_qualified": False,
    }
