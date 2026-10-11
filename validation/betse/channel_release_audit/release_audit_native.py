"""D106 independent timed native identities, source-order operations and input clocks."""

import hashlib
import math
import struct
from decimal import localcontext
from fractions import Fraction

import feedback_audit_math as am
import release_audit_math as control

ind, require = am.ind, am.require


def array_contract(row):
    shapes = {
        "inside_mM": [6, 7],
        "outside_mM": [6, 30],
        "at_membrane_mM": [6, 30],
        "ordinary_density_mol_per_m2_s": [6, 30],
        "junction_density_mol_per_m2_s": [6, 30],
        "rho_C_per_m3": [7],
        "extra_rho_cells_C_per_m3": [7],
        "boundary_voltage_V": [100],
    }
    shapes |= {
        k: [30]
        for k in (
            "voltage_V",
            "extra_rho_env_C_per_m3",
            "extra_current_density_A_per_m2",
            "Jmem_A_per_m2",
            "Jn_A_per_m2",
            "I_mem_A",
        )
    }
    channel_fields = {
        "m": "m",
        "h": "h",
        "P": "P",
        "DChan": "DChan_m2_per_s",
        "chan_flux": "density_mol_per_m2_s",
    }
    if row["final"]["channel"] is not None:
        shapes |= {"channel/" + k: [30] for k in channel_fields}
    require(set(row["final_arrays"]) == set(shapes), "Native final array membership")
    for name, shape in shapes.items():
        record = row["final_arrays"][name]
        ind.array_bytes(record, shape)
        expected = (
            row["final"]["channel"][channel_fields[name.split("/")[1]]]
            if name.startswith("channel/")
            else row["final"]["physical"][name]
        )
        require(record["values"] == expected, "Native final raw/bytes link")
    history_shapes = {
        "time": [],
        "cc_time": [6, 7],
        "cc_env_time": [6, 30],
        "vm_time": [30],
        "I_mem_time": [30],
        "rho_cells_time": [7],
        "rate_NaKATP_time": [30],
        "gjopen_time": [30],
        "dd_time": [6, 30],
    }
    require(set(row["histories"]) == set(history_shapes), "Native history coverage")
    for name, shape in history_shapes.items():
        ind.array_bytes(row["histories"][name], [row["steps"] - 1, *shape])
    for name, value in (("rate_NaKATP_time", 0), ("gjopen_time", 1), ("dd_time", 0)):
        require(
            all(v == value for v in am.flat(row["histories"][name]["values"])),
            "Inactive native history",
        )
    return len(shapes) + len(history_shapes)


def accumulated_atol(r, row):
    g, state = row["geometry"], row["trace"]["initial"]["physical"]
    vi, vo = [v / 1e-15 for v in g["cell_volumes_m3"]], g["effective_bath_volume_m3"] / 1e-15
    largest = max(
        math.fsum([c * v for c, v in zip(inside, vi, strict=True)] + [ind.uniform(outside) * vo])
        for inside, outside in zip(state["inside_mM"], state["outside_mM"], strict=True)
    )
    policy = r["protocol"]["native_conservation"]
    return (
        policy["base_atol_fmol"]
        + policy["roundoff_multiplier"] * (2.0**-52) * row["steps"] * largest
    )


def steps(r, row, accounting=None):
    """Yield one complete independently reconstructed metric map at a time."""
    physics, protocol = r["preparation_registration"]["transport_protocol"], r["protocol"]
    constants, variant, dt = physics["constants"], row["id"], row["dt_s"]
    g, trace = row["geometry"], row["trace"]
    count = round(protocol["duration_s"] / dt)
    require(row["steps"] == count and len(trace["steps"]) == count, "Native step extent")
    require(
        trace["calls"]
        == dict.fromkeys(
            (
                "run_sim_core",
                "init_dynamics",
                "clear_storage",
                "initial_update_V",
                "loop",
                "loop_return",
                "run_return",
            ),
            1,
        ),
        "Native lifecycle calls",
    )
    enabled, active = variant in ind.VARIANTS[2:], variant == "active_channel"
    require(
        trace["gate_initializations"] == int(enabled)
        and trace["pending"] is None
        and trace["hook_restored"] is True,
        "Native lifecycle completion",
    )
    require(trace["status"] == "complete_observation_not_qualification", "Native trace status")
    require(trace["sampled_indices"] == list(range(1, count)), "Native storage indices")
    ind.near(
        trace["labels_s"],
        [i * protocol["duration_s"] / (count - 1) for i in range(count)],
        1e-20,
        1e-15,
    )
    require(
        trace["storage"]
        == [{"index": i, "raw_label_s": trace["labels_s"][i]} for i in range(1, count)],
        "Native label/storage clock",
    )
    initial = trace["initial"]["physical"]
    ind.direct_charge(initial, g, constants)
    previous, accumulated = trace["initial"], [0.0] * 7
    vi, vo = [v / 1e-15 for v in g["cell_volumes_m3"]], g["effective_bath_volume_m3"] / 1e-15
    for i, step in enumerate(trace["steps"]):
        prefix = row["condition"] + f"/step/{i}"
        active = control.availability(
            r["schedules"][row["condition"]], float(Fraction(str(dt)) * i)
        )
        metrics = ind.Metrics()
        require(
            (step["index"], step["before_elapsed_s"], step["after_elapsed_s"], step["raw_label_s"])
            == (i, i * dt, (i + 1) * dt, trace["labels_s"][i]),
            "Native elapsed clock",
        )
        require(step["order"] == ind.order_for(variant), "Native stage order")
        require(
            set(step)
            == {"index", "raw_label_s", "before_elapsed_s", "after_elapsed_s", "before", "order"}
            | set(step["order"]),
            "Native boundary membership",
        )
        b, final = step["before"]["physical"], step["after_voltage"]["physical"]
        require(step["before"]["channel"] == previous["channel"], "Native interstep gate reset")
        require(
            all(b[k] == previous["physical"][k] for k in ("inside_mM", "outside_mM")),
            "Native interstep transfer",
        )
        metrics.add(
            prefix + "/read_previous_voltage",
            b["voltage_V"],
            previous["physical"]["voltage_V"],
            "voltage_V",
        )
        require(
            b["voltage_V"] == control.nonce_voltage(previous["physical"]["voltage_V"]),
            "Independent pre-channel nonce",
        )
        density = [0.0] * 30
        if variant != "network_off":
            require(
                all(v == 0 for v in step["after_clear"]["network_current"]),
                "Native current not cleared",
            )
        if enabled:
            before, after = step["before_gate"]["channel"], step["after_gate"]["channel"]
            for face, owner in enumerate(g["membrane_owners"]):
                v = step["before_gate"]["physical"]["voltage_V"][face]
                metrics.add(
                    prefix + f"/gates/{face}",
                    [after["m"][face], after["h"][face]],
                    ind.gate_values(v, [before["m"][face], before["h"][face]], dt),
                    "gate",
                )
                with localcontext() as context:
                    context.prec = 80
                    opening = ind.decimal(after["m"][face]) * ind.decimal(after["h"][face])
                    permeability = (
                        opening * ind.decimal(physics["max_permeability_m_per_s"]) * int(active)
                    )
                    expected = float(
                        ind.inward_density(
                            v,
                            b["inside_mM"][1][owner],
                            ind.uniform(b["outside_mM"][1]),
                            permeability,
                            constants,
                            physics["temperature_K"],
                        )
                    )
                metrics.add(prefix + f"/open/{face}", after["P"][face], float(opening), "gate")
                metrics.add(
                    prefix + f"/diffusivity/{face}",
                    step["after_channel"]["channel"]["DChan_m2_per_s"][face],
                    float(permeability) * physics["thickness_m"],
                    "diffusivity_m2_per_s",
                )
                density[face] = expected
            metrics.add(
                prefix + "/density",
                step["after_channel"]["channel"]["density_mol_per_m2_s"],
                density,
                "density_mol_per_m2_s",
            )
            density = step["after_channel"]["channel"]["density_mol_per_m2_s"]
        flow = [v * 1e15 for v in ind.integrate_faces(density, g)]
        current = [-constants["F"] * v for v in density]
        for name in ["before", *step["order"]]:
            snapshot = step[name]
            require((snapshot["channel"] is not None) == enabled, "Native channel inventory")
            ind.stage_metrics(metrics, prefix + "/" + name, snapshot, initial, g)
            transferred = name in (
                "after_channel",
                "before_network",
                "after_network",
                "before_ordinary",
                "after_ordinary",
                "after_voltage",
            )
            expected_ci = [
                old + (dt * rate / volume if transferred else 0)
                for old, rate, volume in zip(b["inside_mM"][1], flow, vi, strict=True)
            ]
            expected_co = ind.uniform(b["outside_mM"][1]) - (
                dt * math.fsum(flow) / vo if transferred else 0
            )
            metrics.add(
                prefix + f"/{name}/K_inside",
                snapshot["physical"]["inside_mM"][1],
                expected_ci,
                "concentration_mM",
            )
            metrics.add(
                prefix + f"/{name}/K_outside",
                ind.uniform(snapshot["physical"]["outside_mM"][1]),
                expected_co,
                "concentration_mM",
            )
            if name in ("after_network", "before_ordinary", "after_ordinary", "after_voltage"):
                metrics.add(
                    prefix + f"/{name}/current",
                    snapshot["physical"]["extra_current_density_A_per_m2"],
                    current,
                    "current_density_A_per_m2",
                )
            if name in ("after_channel", "before_network", "after_network"):
                metrics.add(
                    prefix + f"/{name}/network_current",
                    snapshot["network_current"],
                    current,
                    "current_density_A_per_m2",
                )
        metrics.add(prefix + "/Jmem", final["Jmem_A_per_m2"], current, "current_density_A_per_m2")
        average = [
            v / a for v, a in zip(ind.integrate_faces(current, g), g["cell_areas_m2"], strict=True)
        ]
        smooth = [
            w * v + other * average[o]
            for w, v, other, o in zip(
                row["smooth_weight_mem"],
                current,
                row["smooth_weight_other"],
                g["membrane_owners"],
                strict=True,
            )
        ]
        metrics.add(prefix + "/Jn", final["Jn_A_per_m2"], smooth, "current_density_A_per_m2")
        metrics.add(
            prefix + "/I_mem",
            final["I_mem_A"],
            [-v * a for v, a in zip(smooth, g["membrane_areas_m2"], strict=True)],
            "current_A",
        )
        accumulated = [a + dt * v for a, v in zip(accumulated, flow, strict=True)]
        measured = [
            (a - b0) * v
            for a, b0, v in zip(final["inside_mM"][1], initial["inside_mM"][1], vi, strict=True)
        ]
        metrics.add(prefix + "/accumulated_transfer", measured, accumulated, "amount_fmol")
        voltage = [
            v0 + q * constants["F"] * 1e-15 / (a * g["specific_capacitance_F_per_m2"])
            for v0, q, a in zip(
                ind.owner_values(initial["voltage_V"], g),
                accumulated,
                g["cell_areas_m2"],
                strict=True,
            )
        ]
        metrics.add(
            prefix + "/charge_voltage",
            ind.owner_values(final["voltage_V"], g),
            voltage,
            "voltage_V",
        )
        ind.direct_charge(final, g, constants)
        require(
            all(v < 0 for v in flow) if active else all(v == 0 for v in flow), "Native control flow"
        )
        independent_means(prefix, step, g, active, metrics, accounting)
        if not active:
            require(
                final["inside_mM"] == b["inside_mM"]
                and final["voltage_V"] == previous["physical"]["voltage_V"],
                "Independent blocked completed state",
            )
        previous = step["after_voltage"]
        yield prefix, metrics.values
    require(row["final"] == previous, "Native last completed state")
    for name, field in (
        ("cc_time", "inside_mM"),
        ("cc_env_time", "outside_mM"),
        ("vm_time", "voltage_V"),
        ("I_mem_time", "I_mem_A"),
        ("rho_cells_time", "rho_C_per_m3"),
    ):
        require(
            row["histories"][name]["values"]
            == [trace["steps"][i]["after_voltage"]["physical"][field] for i in range(1, count)],
            "Native sampled-state history",
        )
    require(row["histories"]["time"]["values"] == trace["labels_s"][1:], "Native history clock")


def probes(r, row, side=None):
    g, trace, points = row["geometry"], row["trace"], []
    physics = r["preparation_registration"]["transport_protocol"]
    metrics = ind.Metrics()
    vi, vo = [v / 1e-15 for v in g["cell_volumes_m3"]], g["effective_bath_volume_m3"] / 1e-15
    initial = trace["initial"]["physical"]
    selected = (
        row["fresh_probes"] if side is None else [point[side] for point in row["side_probes"]]
    )
    times = (
        r["protocol"]["common_times_s"]
        if side is None
        else [r["protocol"]["duration_s"] / 4, r["protocol"]["duration_s"] / 2]
    )
    for time_s, probe in zip(times, selected, strict=True):
        u = control.availability(r["schedules"][row["condition"]], time_s, side or "right")
        index = round(time_s / row["dt_s"])
        saved = trace["initial"] if index == 0 else trace["steps"][index - 1]["after_voltage"]
        state, channel = saved["physical"], saved["channel"]
        prefix = (
            row["condition"]
            + ("/samples" if side is None else "/switch_" + side)
            + f"/dt_{row['dt_s']:.8g}/fresh/{index}"
        )
        gates = (
            [[0.0] * 7, [0.0] * 7]
            if channel is None
            else [ind.owner_values(channel[k], g) for k in ("m", "h")]
        )
        permeability = (
            [0.0] * 30
            if channel is None
            else [
                m * h * physics["max_permeability_m_per_s"] * u
                for m, h in zip(channel["m"], channel["h"], strict=True)
            ]
        )
        inputs = probe["inputs_before"]
        require(
            probe["source"] == "betse.science.sim_toolbox.electroflux"
            and probe["evaluation"] == "post_hoc_copied_completed_state_not_interval_current"
            and probe["elapsed_s"] == time_s,
            "Native fresh-probe identity",
        )
        require(
            inputs["voltage_V"] == state["voltage_V"]
            and inputs["outside_K_mM"] == state["outside_mM"][1]
            and inputs["inside_K_mM"] == [state["inside_mM"][1][i] for i in g["membrane_owners"]],
            "Probe used stale state",
        )
        require(
            inputs["valence"] == probe["valence_after"] == [1.0] * 30
            and probe["voltage_after_V"] == [v + 1e-25 for v in inputs["voltage_V"]],
            "Probe mutation contract",
        )
        metrics.add(
            prefix + "/permeability",
            inputs["permeability_m_per_s"],
            permeability,
            "permeability_m_per_s",
        )
        density = [
            float(ind.inward_density(v, ci, co, p, physics["constants"], physics["temperature_K"]))
            for v, ci, co, p in zip(
                inputs["voltage_V"],
                inputs["inside_K_mM"],
                inputs["outside_K_mM"],
                permeability,
                strict=True,
            )
        ]
        metrics.add(
            prefix + "/density",
            probe["inward_density_mol_per_m2_s"],
            density,
            "density_mol_per_m2_s",
        )
        flow = [v * 1e15 for v in ind.integrate_faces(probe["inward_density_mol_per_m2_s"], g)]
        points.append(
            {
                "gate": gates,
                "voltage_V": ind.owner_values(state["voltage_V"], g),
                "cell_K_fmol": [a * v for a, v in zip(state["inside_mM"][1], vi, strict=True)],
                "bath_K_fmol": ind.uniform(state["outside_mM"][1]) * vo,
                "transfer_fmol": [
                    (a - b) * v
                    for a, b, v in zip(
                        state["inside_mM"][1], initial["inside_mM"][1], vi, strict=True
                    )
                ],
                "flux_fmol_per_s": flow,
                "permeability_m_per_s": ind.owner_values(inputs["permeability_m_per_s"], g),
                "inward_current_A": [physics["constants"]["F"] * 1e-15 * v for v in flow],
            }
        )
    return metrics.values, points


def independent_means(prefix, step, geometry, active, metrics, accounting=None):
    regions = ("inside_mM", "outside_mM", "at_membrane_mM")
    before = step["before"]["physical"]
    channel, network, ordinary, final = (
        step[n]["physical"]
        for n in ("after_channel", "after_network", "after_ordinary", "after_voltage")
    )
    if accounting is not None:
        for label, state in (("after_network", network), ("after_ordinary", ordinary)):
            changed = [field for field in regions if state[field] != channel[field]]
            if changed:
                accounting["diagnostics"].append(
                    {
                        "id": prefix + "/" + label,
                        "original_guard": "no_duplicate_exact_identity",
                        "changed_fields": changed,
                    }
                )
        if not active:
            changed = [field for field in (*regions, "voltage_V") if final[field] != before[field]]
            if changed:
                accounting["diagnostics"].append(
                    {
                        "id": prefix + "/blocked_final",
                        "original_guard": "blocked_exact_identity",
                        "changed_fields": changed,
                    }
                )
    require(all(channel[k] == network[k] for k in regions), "Independent empty network transfer")
    require(
        all(network[k] == ordinary[k] for k in ("inside_mM", "at_membrane_mM")),
        "Independent ordinary material transfer",
    )
    require(all(ordinary[k] == final[k] for k in regions), "Independent voltage material transfer")
    rows = [
        ("after_ordinary", s, network["outside_mM"][s], ordinary["outside_mM"][s]) for s in range(6)
    ]
    if not active:
        require(
            all(channel[k] == before[k] for k in ("inside_mM", "at_membrane_mM")),
            "Independent blocked channel transfer",
        )
        require(
            all(channel["outside_mM"][s] == before["outside_mM"][s] for s in range(6) if s != 1),
            "Independent blocked other-ion transfer",
        )
        rows.append(("blocked_after_channel", 1, before["outside_mM"][1], channel["outside_mM"][1]))
    for stage, species, first, last in rows:
        initial, actual = ind.uniform(first), ind.uniform(last)
        expected_mean = control.ordered_mean(first)
        require(last == [expected_mean] * 30, "Independent source-order mean mismatch")
        change = Fraction.from_float(actual) - Fraction.from_float(initial)
        amount = float(change * Fraction.from_float(geometry["effective_bath_volume_m3"]) * 10**15)
        require(abs(amount) <= 2e-12, "Independent local remix budget")
        require(
            abs(change) <= Fraction(30, 2**53 - 30) * abs(Fraction.from_float(initial)),
            "Independent uniform mean arithmetic bound",
        )
        if accounting is not None:
            accounting["means"].append(
                {
                    "id": f"{prefix}/zero_flux_mean/{stage}/{species}",
                    "stage": stage,
                    "species": species,
                    "input_concentration_mM": initial,
                    "output_concentration_mM": actual,
                    "source_order_mean_mM": expected_mean,
                    "ideal_uniform_mean_mM": initial,
                    "roundoff_concentration_mM": float(change),
                    "roundoff_amount_fmol": amount,
                    "roundoff_ulps": float(abs(change)) / math.ulp(initial),
                    "source_order_exact": True,
                }
            )
        metrics.add(
            f"{prefix}/zero_flux_mean/{stage}/{species}/material_roundoff",
            amount,
            0.0,
            "amount_fmol",
        )


def inventory(guard, snapshot):
    require(
        guard["excluded_input"] == "channel/maxDm" and "channel/maxDm" not in guard["numeric"],
        "Input exclusion changed",
    )
    # Independently bind numeric bytes to the captured physical and gate fields.
    names = {
        "cc_cells": "inside_mM",
        "cc_env": "outside_mM",
        "cc_at_mem": "at_membrane_mM",
        "vm": "voltage_V",
        "rho_cells": "rho_C_per_m3",
        "extra_rho_cells": "extra_rho_cells_C_per_m3",
        "extra_rho_env": "extra_rho_env_C_per_m3",
        "extra_J_mem": "extra_current_density_A_per_m2",
        "fluxes_mem": "ordinary_density_mol_per_m2_s",
        "fluxes_gj": "junction_density_mol_per_m2_s",
        "Jmem": "Jmem_A_per_m2",
        "Jn": "Jn_A_per_m2",
        "I_mem": "I_mem_A",
        "Phi_b": "boundary_voltage_V",
    }
    values = {"sim/" + name: snapshot["physical"][field] for name, field in names.items()}
    values |= {
        "gates/" + name: snapshot["channel"][field]
        for name, field in (
            ("m", "m"),
            ("h", "h"),
            ("P", "P"),
            ("DChan", "DChan_m2_per_s"),
            ("chan_flux", "density_mol_per_m2_s"),
        )
    }
    for name, value in values.items():
        if value is None:
            continue
        shape, level = [], value
        while isinstance(level, list):
            shape.append(len(level))
            level = level[0] if level else 0.0
        raw = b"".join(struct.pack("<d", v) for v in am.flat(value))
        require(
            guard["numeric"][name]
            == {
                "kind": "array",
                "dtype": "<f8",
                "shape": shape,
                "bytes_sha256": hashlib.sha256(raw).hexdigest(),
            },
            "Independent numeric inventory link: " + name,
        )
    require(
        any(name.startswith("geometry/") for name in guard["numeric"]),
        "Missing geometry input guard",
    )
    require(
        guard["opaque_metadata"]["sim/movingIons"] == {"type": "list", "length": 6},
        "Moving-ion guard",
    )
    moving = {k: v for k, v in guard["numeric"].items() if k.startswith("sim/movingIons/")}
    require(
        moving == {f"sim/movingIons/{i}": {"kind": "int", "value": i} for i in range(6)},
        "Nonce/ordinary species extent",
    )


def inputs(r, row):
    schedule = r["schedules"][row["condition"]]
    timed, dt = row["timed_input"], Fraction(str(row["dt_s"]))
    duration = Fraction(str(r["protocol"]["duration_s"]))
    count = int(duration / dt)
    require(
        count * dt == duration and row["steps"] == count and timed["completed_updates"] == count,
        "Independent native interval extent",
    )
    require(
        timed["schedule"] == schedule
        and timed["native_clock_modified"] is False
        and timed["builtin_tissue_event"] is False
        and timed["parameter"] == "maxDm = immutable_baseline * availability",
        "Independent native input scope",
    )
    physics = r["preparation_registration"]["transport_protocol"]
    maximum = physics["max_permeability_m_per_s"] * physics["thickness_m"]
    require(
        len(timed["intervals"]) == count and len(timed["applications"]) == len(schedule),
        "Independent native input coverage",
    )
    for i, entry in enumerate(timed["intervals"]):
        start, end = float(i * dt), float((i + 1) * dt)
        u = control.availability(schedule, start)
        require(
            entry["index"] == i
            and entry["start_s"] == start
            and entry["end_s"] == end
            and entry["availability"] == u
            and entry["maxDm_m2_per_s"] == maximum * u,
            "Independent held input",
        )
        require(
            math.isclose(
                entry["raw_label_s"],
                i * float(duration) / (count - 1),
                rel_tol=1e-15,
                abs_tol=1e-20,
            ),
            "Independent raw/elapsed clock",
        )
    previous = maximum
    for point, item in zip(schedule, timed["applications"], strict=True):
        index = Fraction(str(point["time"])) / dt
        require(index.denominator == 1, "Independent off-grid input")
        require(
            item["index"] == item["completed_updates"] == int(index)
            and item["elapsed_s"] == point["time"]
            and item["availability"] == point["availability"],
            "Independent applied input time",
        )
        require(
            item["baseline_maxDm_m2_per_s"] == maximum
            and item["previous_maxDm_m2_per_s"] == previous
            and item["applied_maxDm_m2_per_s"] == maximum * point["availability"],
            "Independent absolute restoration",
        )
        require(
            item["before"] == item["after"]
            and item["numeric_inventory"] == item["numeric_inventory_after"],
            "Independent input state mutation",
        )
        inventory(item["numeric_inventory"], item["before"])
        if row["trace"] is not None:
            expected = (
                row["trace"]["initial"]
                if index == 0
                else row["trace"]["steps"][int(index)]["before"]
            )
            require(item["before"] == expected, "Independent input/observation boundary")
        previous = item["applied_maxDm_m2_per_s"]


class Case:
    def __init__(self, r, row, partner):
        exclude = {"mode", "trace", "fresh_probes", "side_probes"}
        require(
            {k: v for k, v in row.items() if k not in exclude}
            == {k: v for k, v in partner.items() if k not in exclude},
            "Native observer changed exports",
        )
        require(
            partner["trace"] is None
            and partner["fresh_probes"] is None
            and partner["side_probes"] is None,
            "Unobserved output has observer data",
        )
        inputs(r, row)
        inputs(r, partner)
        ind.geometry_contract(row["geometry"])
        self.arrays = array_contract(row) + array_contract(partner)
        ind.direct_charge(
            partner["final"]["physical"],
            row["geometry"],
            r["preparation_registration"]["transport_protocol"]["constants"],
        )
        self.charge_snapshots = row["steps"] + 2
        self.accounting = {"means": [], "diagnostics": []}
        self.sequence = steps(r, row, self.accounting)
        self.pending, self.current = {}, None
        self.fresh, self.points = probes(r, row)
        self.sides = {}
        for side in ("left", "right"):
            metrics, self.sides[side] = probes(r, row, side)
            require(not self.fresh.keys() & metrics.keys(), "Duplicate side probe identity")
            self.fresh.update(metrics)

    def resolve(self, name):
        if "/fresh/" in name:
            if self.current is not None:
                require(not self.pending, "Native step identities omitted")
                require(next(self.sequence, None) is None, "Native steps omitted")
                self.current = None
            require(name in self.fresh, "Unknown/duplicate fresh-probe identity")
            return self.fresh.pop(name)
        group = "/".join(name.split("/")[:3])
        if group != self.current:
            require(not self.pending, "Native boundary identities omitted")
            self.current, self.pending = next(self.sequence)
            require(group == self.current, "Native comparison order/coverage")
        require(name in self.pending, "Unknown/duplicate native identity")
        return self.pending.pop(name)

    def finish(self):
        require(
            not self.pending and not self.fresh and next(self.sequence, None) is None,
            "Native independent coverage incomplete",
        )
