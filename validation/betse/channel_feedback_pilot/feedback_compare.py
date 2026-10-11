"""Native boundary accounting, full Cells histories, refinement and pilot contact."""

import math

import feedback_context as ctx
import feedback_io as io
import feedback_reference as ref
import feedback_reference_check as refcheck

c = ctx.c
oldcheck = ctx.audit.checker
ind = ctx.audit.independent
ready = ctx.audit.readiness


def accumulation_tolerance(r, steps):
    s = c.read(ctx.audit.CAPTURE / "betse.json")["rows"]["network_off/observed"]["trace"][
        "initial"
    ]["physical"]
    g, p = r["geometry"], r["protocol"]["native_conservation"]
    vi = [v / 1e-15 for v in g["cell_volumes_m3"]]
    vo = g["effective_bath_volume_m3"] / 1e-15
    total = max(
        math.fsum([a * v for a, v in zip(row, vi, strict=True)] + [ind.uniform(outside) * vo])
        for row, outside in zip(s["inside_mM"], s["outside_mM"], strict=True)
    )
    return p["base_atol_fmol"] + p["roundoff_multiplier"] * math.ulp(1.0) * steps * total


def zero(value):
    c.require(all(v == 0 for v in refcheck.flat(value)), "Nonzero inactive state/transport")


def native_points(r, row, variant, ledger):
    points = []
    g, trace = row["geometry"], row["trace"]
    initial = trace["initial"]["physical"]
    vi = [v / 1e-15 for v in g["cell_volumes_m3"]]
    vo = g["effective_bath_volume_m3"] / 1e-15
    transport = r["preparation_registration"]["transport_protocol"]
    constants = transport["constants"]
    f = constants["F"]
    for time_s, probe in zip(r["protocol"]["common_times_s"], row["fresh_probes"], strict=True):
        index = round(time_s / row["dt_s"])
        saved = trace["initial"] if index == 0 else trace["steps"][index - 1]["after_voltage"]
        physical, ch = saved["physical"], saved["channel"]
        q = [
            (now - old) * volume
            for now, old, volume in zip(
                physical["inside_mM"][1], initial["inside_mM"][1], vi, strict=True
            )
        ]
        gates = (
            [[0.0] * 7, [0.0] * 7]
            if ch is None
            else [ind.owner_values(ch[k], g) for k in ("m", "h")]
        )
        c.require(
            probe["elapsed_s"] == time_s
            and probe["evaluation"] == "post_hoc_copied_completed_state_not_interval_current",
            "Fresh native probe time/meaning differs",
        )
        inputs = probe["inputs_before"]
        c.require(
            inputs["voltage_V"] == physical["voltage_V"]
            and inputs["outside_K_mM"] == physical["outside_mM"][1]
            and inputs["inside_K_mM"]
            == [physical["inside_mM"][1][o] for o in g["membrane_owners"]],
            "Fresh probe is not copied completed state",
        )
        c.require(
            inputs["valence"] == probe["valence_after"] == [1.0] * 30, "Fresh probe valence differs"
        )
        c.require(
            probe["voltage_after_V"] == [v + 1e-25 for v in inputs["voltage_V"]],
            "Native probe mutation differs",
        )
        permeability = (
            [0.0] * 30
            if ch is None
            else [
                m * h * transport["max_permeability_m_per_s"] * variant["permeability_fraction"]
                for m, h in zip(ch["m"], ch["h"], strict=True)
            ]
        )
        label = ctx.key(variant["id"], row["dt_s"]) + f"/fresh/{index}"
        ledger.compare(
            label + "/permeability",
            inputs["permeability_m_per_s"],
            permeability,
            "permeability_m_per_s",
        )
        density = [
            float(ind.inward_density(v, ci, co, p, constants, 298.15))
            for v, ci, co, p in zip(
                inputs["voltage_V"],
                inputs["inside_K_mM"],
                inputs["outside_K_mM"],
                permeability,
                strict=True,
            )
        ]
        ledger.compare(
            label + "/density",
            probe["inward_density_mol_per_m2_s"],
            density,
            "density_mol_per_m2_s",
        )
        flow = [v * 1e15 for v in ind.integrate_faces(probe["inward_density_mol_per_m2_s"], g)]
        points.append(
            {
                "gate": gates,
                "voltage_V": ind.owner_values(physical["voltage_V"], g),
                "cell_K_fmol": [a * v for a, v in zip(physical["inside_mM"][1], vi, strict=True)],
                "bath_K_fmol": ind.uniform(physical["outside_mM"][1]) * vo,
                "transfer_fmol": q,
                "flux_fmol_per_s": flow,
                "permeability_m_per_s": ind.owner_values(inputs["permeability_m_per_s"], g),
                "inward_current_A": [f * 1e-15 * v for v in flow],
            }
        )
    return points


def native_saved_state_contract(row, constants):
    fields = {
        "m": "m",
        "h": "h",
        "P": "P",
        "DChan": "DChan_m2_per_s",
        "chan_flux": "density_mol_per_m2_s",
    }
    expected = set(row["final"]["physical"])
    if row["final"]["channel"] is not None:
        expected |= {"channel/" + name for name in fields}
        for name, field in fields.items():
            c.require(
                row["final_arrays"]["channel/" + name]["values"] == row["final"]["channel"][field],
                "Final channel array/raw state disagree",
            )
    c.require(set(row["final_arrays"]) == expected, "Final array membership differs")
    if row["trace"] is None:
        ind.direct_charge(row["final"]["physical"], row["geometry"], constants)
        return 1
    snapshots = [row["trace"]["initial"]] + [
        step["after_voltage"] for step in row["trace"]["steps"]
    ]
    for snapshot in snapshots:
        ind.direct_charge(snapshot["physical"], row["geometry"], constants)
    return len(snapshots)


def native_checks(r, output, aggregate):
    expected = {
        ctx.key(v, h) for v in r["protocol"]["variants"] for h in r["protocol"]["native_steps_s"]
    }
    c.require(
        set(aggregate["records"]) == expected and aggregate["native_runs"] == 24,
        "Native trajectory coverage differs",
    )
    original = c.read(ctx.audit.preparation.audit.CAPTURE / "betse.json")
    points, summaries, inactive_final = {}, {}, {}
    total_failed = charge_snapshots = 0
    for variant in r["preparation_registration"]["transport_protocol"]["variants"]:
        for step in r["protocol"]["native_steps_s"]:
            key = ctx.key(variant["id"], step)
            paths = aggregate["records"][key]
            c.require(set(paths) == {"observed", "unobserved"}, "Missing observer counterpart")
            a, b = (io.read_compressed(output / paths[mode]) for mode in ("observed", "unobserved"))
            registration = ctx.loop_registration(r, step)
            for row in (a, b):
                oldcheck.preparation(registration, variant, row, original)
                charge_snapshots += native_saved_state_contract(
                    row, registration["transport_protocol"]["constants"]
                )
            exclude = {"mode", "trace", "fresh_probes"}
            c.require(
                {k: v for k, v in a.items() if k not in exclude}
                == {k: v for k, v in b.items() if k not in exclude}
                and b["trace"] is None
                and b["fresh_probes"] is None,
                "Native observer changed outputs",
            )
            tolerances = registration["transport_protocol"]["tolerances"].copy()
            tolerances["amount_fmol"] = accumulation_tolerance(r, a["steps"])
            ledger = io.Ledger(
                tolerances,
                tolerances["relative"],
                output / "native" / key / "boundary-failures.jsonl",
            )
            summary = oldcheck.observed(registration, variant, a, ledger)
            points[key] = native_points(r, a, variant, ledger)
            summaries[key] = ledger.summary() | {
                "accumulation_atol_fmol": tolerances["amount_fmol"],
                "observed": summary,
            }
            total_failed += ledger.failed
            if variant["id"] != "active_channel":
                if step in inactive_final:
                    c.require(
                        a["final"]["physical"] == inactive_final[step],
                        "Inactive native controls differ physically",
                    )
                else:
                    inactive_final[step] = a["final"]["physical"]
    return {
        "status": "pass" if not total_failed else "fail",
        "failed_comparisons": total_failed,
        "boundary_checks": summaries,
        "points": points,
        "observer_pairs": 12,
        "direct_charge_snapshots_checked": charge_snapshots,
    }


def unpack_arrays(record):
    ctx.audit.preparation.validate_array_record(record["times"])
    for group in ("history", "observations"):
        for value in record[group].values():
            ctx.audit.preparation.validate_array_record(value)
    return (
        record["times"]["values"],
        {k: v["values"] for k, v in record["history"].items()},
        {k: v["values"] for k, v in record["observations"].items()},
    )


def cells_tolerances(r):
    return r["preparation_registration"]["transport_protocol"]["tolerances"] | {
        "state": 2e-12,
        "energy": 1e-9,
    }


def cells_points_and_checks(r, record, ledger):
    key = record["id"]
    definition = r["cells_definitions"][key]
    c.require(record["definition"] == definition, "Cells data definition differs")
    c.require(
        record["runtime"] == r["preparation_registration"]["cells_runtime"],
        "Cells trajectory runtime differs",
    )
    times, history, observations = unpack_arrays(record)
    dt, duration = definition["execution"]["dt"], definition["experiment"]["end_time"]
    count = round(duration / dt)
    c.require(
        record["start_step"] == 0
        and record["final_step_index"] == count
        and times == [i * dt for i in range(count)] + [duration],
        "Cells accepted grid differs",
    )
    c.require(set(history) == set(ready.STATE_SHAPES), "Cells full-state coverage differs")
    variant = key.split("/")[0]
    p, enabled = (
        r["reference_parameters"][variant],
        variant in ("blocked_channel", "active_channel"),
    )
    expected = ready.expected_initial(enabled)
    for name, shape in ready.STATE_SHAPES.items():
        c.require(
            record["history"][name]["shape"] == [len(times), *shape]
            and history[name][0] == expected[name],
            "Cells initial/full-state shape differs",
        )
    for j in range(len(times)):
        state = {name: values[j] for name, values in history.items()}
        for name in (
            "leak_transferred",
            "pump_cycles",
            "junction_gate",
            "junction_transferred",
            "junction_dissipated_energy_pJ",
        ):
            zero(state[name])
        zero(
            [
                state["amount_increment"][0],
                state["amount_increment"][2],
                state["extracellular_amount_increment"][0],
                state["extracellular_amount_increment"][2],
            ]
        )
        zero([v[7:] for v in state["amount_increment"]])
        zero([v[1:] for v in state["extracellular_amount_increment"]])
        zero([v[7:] for v in state["gate"]])
        zero(state["channel_transferred"][7:])
        zero(state["dissipated_energy_pJ"][7:])
        q, m, h, energy = (
            state["amount_increment"][1][:7],
            state["gate"][0][:7],
            state["gate"][1][:7],
            state["dissipated_energy_pJ"][:7],
        )
        packed = q + (m + h if enabled else []) + energy
        ref.readout(p, packed)  # Independent positivity/kinetic-domain check; no time step.
        ledger.compare(key + f"/transfer/{j}", state["channel_transferred"][:7], q, "state")
        ledger.compare(
            key + f"/bath/{j}",
            state["extracellular_amount_increment"][1][0],
            -math.fsum(q),
            "state",
        )
        ledger.compare(
            key + f"/energy/{j}",
            math.fsum(energy),
            refcheck.thermodynamic_dissipation(p, q),
            "energy",
        )
        c.require(all(v >= -1e-12 for v in energy), "Negative Cells dissipation")
        if variant != "active_channel":
            zero(q + energy + state["extracellular_amount_increment"][1])
        if not enabled:
            zero(state["gate"])
    diagnostics = record["diagnostics"]
    limits = {
        "max_balance_error_fmol": 1e-10,
        "max_extracellular_balance_error_fmol": 1e-10,
        "max_global_balance_error_fmol": 1e-10,
        "max_charge_balance_error_V": 1e-8,
        "max_countercharge_error_C": 1e-20,
        "max_energy_balance_error_pJ": 1e-6,
    }
    c.require(
        set(diagnostics) == set(limits)
        and all(0 <= diagnostics[k] <= limit for k, limit in limits.items()),
        "Production invariant diagnostics rejected",
    )
    c.require(
        observations["times"] == r["protocol"]["common_times_s"], "Cells observation clock differs"
    )
    points = []
    for j, time_s in enumerate(observations["times"]):
        index = round(time_s / dt)
        for name in ready.STATE_SHAPES:
            ledger.compare(
                key + f"/sample/{j}/{name}",
                observations[name][j],
                history[name][index],
                "gate" if name == "gate" else "state",
            )
        points.append(
            {
                "gate": [v[:7] for v in observations["gate"][j]],
                "voltage_V": observations["voltage_V"][j][:7],
                "cell_K_fmol": observations["amount"][j][1][:7],
                "bath_K_fmol": observations["extracellular_amount"][j][1][0],
                "transfer_fmol": observations["channel_transferred"][j][:7],
                "flux_fmol_per_s": observations["channel_flux_fmol_per_s"][j][:7],
                "permeability_m_per_s": observations["channel_effective_permeability_m_per_s"][j][
                    :7
                ],
                "inward_current_A": observations["membrane_current_A"][j][:7],
                "energy_pJ": observations["dissipated_energy_pJ"][j][:7],
            }
        )
        q = history["amount_increment"][index][1][:7]
        packed = (
            q
            + (history["gate"][index][0][:7] + history["gate"][index][1][:7] if enabled else [])
            + history["dissipated_energy_pJ"][index][:7]
        )
        own_state = ref.readout(p, packed)
        units = {
            "gate": "gate",
            "voltage_V": "voltage_V",
            "cell_K_fmol": "amount_fmol",
            "bath_K_fmol": "amount_fmol",
            "transfer_fmol": "amount_fmol",
            "flux_fmol_per_s": "flux_fmol_per_s",
            "permeability_m_per_s": "permeability_m_per_s",
            "inward_current_A": "current_A",
            "energy_pJ": "energy_pJ",
        }
        for field, unit in units.items():
            ledger.compare(
                key + f"/constitutive/{j}/" + field, points[-1][field], own_state[field], unit
            )
    return points


def compare_histories(name, left, right, absolute, relative, failure_path, start=0):
    ledger = io.Ledger(absolute, relative, failure_path)
    ta, ha, oa = unpack_arrays(left)
    tb, hb, ob = unpack_arrays(right)
    c.require(ta[start:] == tb and set(ha) == set(hb), "Restart/backend accepted history differs")
    for field in ha:
        ledger.compare(
            name + "/history/" + field,
            ha[field][start:],
            hb[field],
            "gate" if field == "gate" else "state",
        )
    c.require(set(oa) == set(ob), "Restart/backend observations differ")
    selected = [i for i, time_s in enumerate(oa["times"]) if time_s >= tb[0]]
    for field in oa:
        ledger.compare(
            name + "/observations/" + field,
            [oa[field][i] for i in selected],
            ob[field],
            "gate" if field == "gate" else "state",
        )
    return ledger.summary()


def cells_checks(r, output, aggregate):
    c.require(
        set(aggregate["records"]) == set(r["cells_definitions"])
        and aggregate["cells_trajectories"] == 16,
        "Cells trajectory coverage differs",
    )
    ledger = io.Ledger(
        cells_tolerances(r),
        2e-11,
        output / "cells-state-failures.jsonl",
    )
    points, records = {}, {}
    for key, path in aggregate["records"].items():
        record = io.read_compressed(output / path)
        points[key] = cells_points_and_checks(r, record, ledger)
        records[key] = record
    restarts, backends = {}, {}
    expected_resumes = {
        ctx.key(v, r["protocol"]["restart_step_s"], "jax_jit") for v in r["protocol"]["variants"]
    }
    c.require(
        set(aggregate["resumed"]) == expected_resumes and aggregate["resumed_segments"] == 4,
        "Restart coverage differs",
    )
    for key, path in aggregate["resumed"].items():
        resumed = io.read_compressed(output / path)
        start = round(r["protocol"]["restart_time_s"] / r["protocol"]["restart_step_s"])
        c.require(
            resumed["definition"] == records[key]["definition"]
            and resumed["runtime"] == records[key]["runtime"]
            and resumed["start_step"] == start
            and resumed["final_step_index"] == records[key]["final_step_index"],
            "Restart metadata differs",
        )
        restarts[key] = compare_histories(
            key,
            records[key],
            resumed,
            r["protocol"]["restart_absolute"],
            2e-11,
            output / "cells" / key / "restart-failures.jsonl",
            start,
        )
    for variant in r["protocol"]["variants"]:
        eager, compiled = (
            records[ctx.key(variant, r["protocol"]["cells_eager_step_s"], backend)]
            for backend in ("jax_eager", "jax_jit")
        )
        backends[variant] = compare_histories(
            variant,
            compiled,
            eager,
            r["protocol"]["backend_absolute"],
            2e-11,
            output / f"backend-{variant}-failures.jsonl",
        )
    failures = ledger.failed + sum(
        v["failed_comparisons"] for v in (*restarts.values(), *backends.values())
    )
    return {
        "status": "pass" if not failures else "fail",
        "failed_comparisons": failures,
        "state_checks": ledger.summary(),
        "restarts": restarts,
        "backends": backends,
        "points": points,
    }


def compare_points(name, left, right, protocol, output, energy=True, multiplier=1):
    fields = set(protocol["trajectory_absolute"]) - {"interval_transfer_fmol"}
    if not energy:
        fields.remove("energy_pJ")
    ledger = io.Ledger(
        {k: v * multiplier for k, v in protocol["trajectory_absolute"].items()},
        protocol["comparison_relative"],
        output / "trajectory-failures.jsonl",
    )
    errors = dict.fromkeys(fields | {"interval_transfer_fmol"}, 0.0)
    previous_a = previous_b = None
    for i, (a, b) in enumerate(zip(left, right, strict=True)):
        a, b = ({k: v for k, v in point.items() if k in fields} for point in (a, b))
        c.require(set(a) == set(b) == fields, "Trajectory readout scope differs")
        for field, x, y in refcheck.point_pairs(a, b, previous_a, previous_b):
            ledger.compare(name + f"/observation/{i}/" + field, x, y, field)
            errors[field] = max(
                errors[field],
                max(abs(u - v) for u, v in zip(refcheck.flat(x), refcheck.flat(y), strict=True)),
            )
        previous_a, previous_b = a, b
    return ledger.summary() | {"maximum_absolute_errors": errors}


def refinement(errors, self_changes, reference_error, protocol):
    result = {}
    policy = protocol["refinement"]
    for field in policy["required_fields"]:
        floor = max(
            protocol["trajectory_absolute"][field] * policy["roundoff_fraction_of_budget"],
            policy["reference_error_floor_multiplier"] * reference_error[field],
        )
        values = [error[field] for error in errors]
        own = [value[field] for value in self_changes]
        pairs = [(values[0], values[1]), (values[1], values[2]), (own[0], own[1])]
        passed = all(b <= floor or b <= policy["required_error_ratio_max"] * a for a, b in pairs)
        result[field] = {
            "errors_to_reference": values,
            "own_refinement_differences": own,
            "floor": floor,
            "classification": "reference_or_roundoff_limited"
            if max(values + own) <= floor
            else "resolved_refinement",
            "passed": passed,
        }
    return {
        "status": "pass" if all(v["passed"] for v in result.values()) else "fail",
        "fields": result,
    }


def dynamic_checks(r, output, reference, native, cells):
    protocol = r["protocol"]
    comparisons, refinements, cross = {}, {}, {}
    required_failures = 0
    coarse_diagnostic_failures = 0
    for variant in protocol["variants"]:
        oracle = reference["reference_solutions"][variant]
        primary = [
            oracle["readouts"][round(t / protocol["reference"]["sample_dt_s"])]
            for t in protocol["common_times_s"]
        ]
        for engine, steps, points, backend in (
            ("native", protocol["native_steps_s"], native["points"], None),
            ("cells", protocol["cells_steps_s"], cells["points"], "jax_jit"),
        ):
            previous = None
            errors, changes = [], []
            for j, step in enumerate(steps):
                key = ctx.key(variant, step, backend)
                name = engine + "/" + key
                result = compare_points(
                    name, points[key], primary, protocol, output, energy=engine == "cells"
                )
                result["required"] = j == len(steps) - 1
                comparisons[name] = result
                errors.append(result["maximum_absolute_errors"])
                if result["required"]:
                    required_failures += result["failed_comparisons"]
                else:
                    coarse_diagnostic_failures += result["failed_comparisons"]
                if previous is not None:
                    difference = compare_points(
                        name + "/own_refinement",
                        previous,
                        points[key],
                        protocol,
                        output,
                        energy=engine == "cells",
                    )
                    changes.append(difference["maximum_absolute_errors"])
                previous = points[key]
            refinements[engine + "/" + variant] = refinement(
                errors, changes, reference["measured_reference_disagreement"][variant], protocol
            )
        a = native["points"][ctx.key(variant, protocol["native_steps_s"][-1])]
        b = cells["points"][ctx.key(variant, protocol["cells_steps_s"][-1], "jax_jit")]
        cross[variant] = compare_points(
            "cross_engine/" + variant,
            a,
            b,
            protocol,
            output,
            energy=False,
            multiplier=protocol["cross_engine_budget_multiplier"],
        )
        required_failures += cross[variant]["failed_comparisons"]
    bad_refinements = sum(v["status"] != "pass" for v in refinements.values())
    return {
        "status": "pass" if required_failures == bad_refinements == 0 else "fail",
        "required_failed_comparisons": required_failures,
        "failed_refinement_groups": bad_refinements,
        "coarse_diagnostic_failures": coarse_diagnostic_failures,
        "comparisons": comparisons,
        "refinements": refinements,
        "cross_engine": cross,
    }


def check(r, output, reference, native_aggregate, cells_aggregate):
    native = native_checks(r, output, native_aggregate)
    io.write_compressed(output / "native-accounting.json.gz", native)
    cells = cells_checks(r, output, cells_aggregate)
    io.write_compressed(output / "cells-accounting.json.gz", cells)
    dynamic = dynamic_checks(r, output, reference, native, cells)
    io.write(output / "trajectory-comparison.json", dynamic)
    return {
        "status": "capture_pass_pending_audit"
        if all(v["status"] == "pass" for v in (reference, native, cells, dynamic))
        else "capture_failed_not_qualified",
        "native_boundary_comparisons": sum(
            v["comparisons"] for v in native["boundary_checks"].values()
        ),
        "native_boundary_failures": native["failed_comparisons"],
        "cells_accounting_failures": cells["failed_comparisons"],
        "required_trajectory_failures": dynamic["required_failed_comparisons"],
        "coarse_diagnostic_failures": dynamic["coarse_diagnostic_failures"],
        "failed_refinement_groups": dynamic["failed_refinement_groups"],
        "reference_convergence_checked": reference["reference_convergence_checked"],
        "observer_pairs": native["observer_pairs"],
        "native_direct_charge_snapshots": native["direct_charge_snapshots_checked"],
        "restart_pairs": len(cells["restarts"]),
        "backend_pairs": len(cells["backends"]),
        "coupled_trajectory_qualified": False,
        "independent_audit_complete": False,
        "biology_validated": False,
        "gpu_tested": False,
    }
