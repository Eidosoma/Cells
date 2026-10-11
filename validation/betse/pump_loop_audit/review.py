"""Independent raw-law, ownership, chronology and observer audit; no ODE reruns."""

import argparse
import math
import signal
import time
import traceback
import zipfile
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from pathlib import Path

import evidence as e

Z = (1, 1, -1, 2, -1, -1)
SPECIES = ["Na", "K", "Cl", "Ca", "P", "M"]
F, R = 96485.33212331001, 8.31446261815324


def pump_density(inputs, parameters, alpha):
    """Chemical-potential affinity and separate saturation factors, 70 digits."""
    with localcontext() as context:
        context.prec = 70
        d = Decimal
        p = {k: d(v) for k, v in parameters.items()}
        rt = d(R) * d(inputs["T"])
        drive = p["deltaGATP"] + rt * (p["cADP"] * p["cPi"] / (1000 * p["cATP"])).ln()
        results = []
        for ci, co, ki, ko, v in zip(
            *(inputs[k] for k in ("cNai", "cNao", "cKi", "cKo", "Vm")), strict=True
        ):
            ci, co, ki, ko, v = map(d, (ci, co, ki, ko, v))
            e.require(min(ci, co, ki, ko) > 0, "Pump pool depleted")
            affinity = drive + 3 * rt * (co / ci).ln() + 2 * rt * (ki / ko).ln() - d(F) * v
            e.require(abs(affinity / rt) <= 80, "Pump domain")
            saturation = 1 / (
                (1 + (p["KmNK_Na"] / ci) ** 3)
                * (1 + (p["KmNK_K"] / ko) ** 2)
                * (1 + p["KmNK_ATP"] / p["cATP"])
            )
            cycles = d(alpha) * d(inputs["block"]) * saturation * (1 - (affinity / rt).exp())
            e.require(-cycles * affinity >= 0, "Negative pump dissipation")
            results.append([float(-3 * cycles), float(2 * cycles), float(3 * cycles)])
        return [list(v) for v in zip(*results, strict=True)]


def passive_density(inputs):
    with localcontext() as context:
        context.prec = 70
        d = Decimal
        rt = d(R) * d(inputs["T"])
        result = []
        for co, ci, diff, length, z, v in zip(
            *(inputs[k] for k in ("cA", "cB", "Dc", "d", "zc", "vBA")), strict=True
        ):
            co, ci, diff, length, z, v = map(d, (co, ci, diff, length, z, v))
            e.require(min(co, ci, length) > 0 and diff >= 0, "Passive physical domain")
            # The source's explicit nonce is a compatibility detail, not our production law.
            x = (z + d("1e-25")) * (v + d("1e-25")) * d(F) / rt
            e.require(abs(x) <= 50, "Passive voltage domain")
            h = (x / 2).exp()
            factor = co - ci if x == 0 else x * (co / h - ci * h) / (h - 1 / h)
            result.append(float(diff / length * d(inputs["rho"]) * factor))
        return result


def physical(record, g, initial, ledger, *, electrical):
    p = record["physical"]
    n, m = g["cell_count"], g["membrane_count"]
    for name in (
        "inside_mM",
        "outside_mM",
        "at_membrane_mM",
        "ordinary_density_mol_per_m2_s",
        "junction_density_mol_per_m2_s",
    ):
        e.shape(p[name], [6, n if name == "inside_mM" else m])
    e.require(
        all(v > 0 for name in ("inside_mM", "outside_mM") for v in e.flat(p[name])),
        "Nonpositive chemistry",
    )
    for name in (
        "junction_density_mol_per_m2_s",
        "extra_current_density_A_per_m2",
        "extra_rho_cells_C_per_m3",
        "extra_rho_env_C_per_m3",
        "boundary_voltage_V",
    ):
        e.require(all(v == 0 for v in e.flat(p[name])), "Undeclared source: " + name)
    for s in range(6):
        e.require(
            all(v == p["outside_mM"][s][0] for v in p["outside_mM"][s]), "Bath not well mixed"
        )
        ledger.compare(
            "membrane_cell_concentration_mM",
            p["at_membrane_mM"][s],
            [p["inside_mM"][s][i] for i in g["membrane_owners"]],
            2e-12,
        )
        residual = math.fsum(
            [
                (p["outside_mM"][s][0] - initial["outside_mM"][s][0])
                * g["effective_bath_volume_m3"]
                * 1e15,
                *(
                    (p["inside_mM"][s][i] - initial["inside_mM"][s][i])
                    * g["cell_volumes_m3"][i]
                    * 1e15
                    for i in range(n)
                ),
            ]
        )
        ledger.compare("global_material_fmol", residual, 0.0, 2e-12, 0.0)
    if electrical:
        with localcontext() as context:
            context.prec = 70
            d = Decimal
            rho = [
                float(d(F) * sum(d(Z[s]) * d(p["inside_mM"][s][i]) for s in range(6)))
                for i in range(n)
            ]
        ledger.compare("charge_density_C_m3", p["rho_C_per_m3"], rho, 2e-8)
        v = [
            rho[i]
            * g["cell_volumes_m3"][i]
            / g["cell_areas_m2"][i]
            / g["specific_capacitance_F_per_m2"]
            for i in g["membrane_owners"]
        ]
        ledger.compare("voltage_V", p["voltage_V"], v, 2e-10)
        current_density = [
            -F * math.fsum(Z[s] * p["ordinary_density_mol_per_m2_s"][s][j] for s in range(6))
            for j in range(m)
        ]
        ledger.compare(
            "unsmoothed_current_density_A_m2", p["Jmem_A_per_m2"], current_density, 2e-13
        )
        ledger.compare(
            "face_current_A",
            p["I_mem_A"],
            [-j * a for j, a in zip(p["Jn_A_per_m2"], g["membrane_areas_m2"], strict=True)],
            2e-20,
        )
        for i in range(n):
            faces = [j for j, owner in enumerate(g["membrane_owners"]) if owner == i]
            ledger.compare(
                "cell_current_A",
                math.fsum(p["I_mem_A"][j] for j in faces),
                -math.fsum(current_density[j] * g["membrane_areas_m2"][j] for j in faces),
                2e-20,
            )


def review_row(plan, variant, row, ledger):
    g, trace, meta, settings = row["geometry"], row["trace"], row["metadata"], row["settings"]
    e.require(
        g["cell_count"] == 7
        and g["membrane_count"] == 30
        and row["phase"] == "INIT"
        and row["dt_s"] == plan["dt_s"]
        and row["steps"] == 8,
        "Native scope",
    )
    e.require(
        meta["species"] == SPECIES
        and meta["valence"] == list(Z)
        and row["moving_ions"] == list(range(6))
        and row["sodium_index"] == 0
        and row["potassium_index"] == 1,
        "Species axes",
    )
    e.require(
        meta["channel"] is meta["network_inventory"] is None
        and meta["rho_channel"] == 1
        and meta["sim_temperature_K"] == 298.15,
        "Other mechanism",
    )
    e.require(
        settings["solver"] == "FULL"
        and settings["constants"] == plan["constants"] == dict(F=F, R=R)
        and settings["cluster_open"] == variant["cluster_open"]
        and settings["substances_affect_charge"] is True
        and settings["temperature_K"] == 298.15
        and settings["thickness_m"] == 7.5e-9
        and settings["pump_parameters"] == plan["pump_parameters"],
        "Settings changed",
    )
    e.require(
        all(
            settings[k] == 0
            for k in (
                "Ca_dyn",
                "alpha_Ca",
                "cell_polarizability",
                "channel_noise_level",
                "deform_osmo",
                "deformation",
                "dynamic_noise",
                "fluid_flow",
                "gj_surface",
                "grn_enabled",
                "is_ecm",
                "molecules_enabled",
                "v_sensitive_gj",
            )
        ),
        "Undeclared mechanism",
    )
    alpha = plan["alpha_mol_per_m2_s"] if variant["pump"] else 0.0
    e.require(settings["alpha_NaK"] == alpha, "Pump capacity")
    e.require(
        g["effective_bath_volume_m3"] == 30 * g["configured_bath_volume_m3"], "Wrong effective bath"
    )
    for i in range(7):
        area = math.fsum(
            a for a, o in zip(g["membrane_areas_m2"], g["membrane_owners"], strict=True) if o == i
        )
        ledger.compare("area_m2", area, g["cell_areas_m2"][i], 1e-24, 2e-14)
        ledger.compare(
            "volume_area_m", g["diviterm_m"][i], g["cell_volumes_m3"][i] / area, 1e-19, 2e-14
        )
    diffusivity = [
        [permeability * 7.5e-9 if variant["leak"] else 0.0] * 30
        for permeability in plan["permeability_m_per_s"]
    ]
    e.require(meta["ordinary_diffusivity_m2_per_s"] == diffusivity, "Declared passive law changed")
    f = row["fixture"]
    e.require(
        f["applications"] == 1
        and row["fixture_hook"] == dict(calls=1, returns=1)
        and row["hook_restored"],
        "Fixture lifecycle",
    )
    e.require(
        f["declared"] == dict(rho_pump=variant["rho_pump"], cluster_open=variant["cluster_open"])
        and f["before"]["physical"] == f["after"]["physical"]
        and f["before"]["rho_pump"] == 1
        and f["after"]["rho_pump"] == variant["rho_pump"],
        "Fixture state mutation",
    )
    for stage in ("before", "after"):
        e.require(
            f[stage]["channel"] is None and all(v == 0 for v in f[stage]["network_current"]),
            "Fixture network mutation",
        )
    for record in (*row["final_arrays"].values(), *row["histories"].values()):
        e.array(record)
    for name, record in row["final_arrays"].items():
        e.require(record["values"] == row["final"]["physical"][name], "Final array export")
    if trace is None:
        return None
    e.require(
        len(trace["steps"]) == len(trace["raw_steps"]) == len(trace["labels_s"]) == 8
        and trace["pending"] is None
        and trace["inflight_calls"] == 0
        and trace["gate_initializations"] == 0
        and trace["hook_restored"]
        and all(v == 1 for v in trace["calls"].values()),
        "Trace lifecycle",
    )
    e.require(
        trace["sampled_indices"] == list(range(1, 8))
        and trace["labels_s"][0] == 0
        and trace["labels_s"][-1] == plan["duration_s"],
        "Native label/sampling coverage",
    )
    ledger.compare(
        "raw_labels_s",
        trace["labels_s"],
        [i * plan["duration_s"] / 7 for i in range(8)],
        1e-18,
        0.0,
    )
    initial = trace["initial"]["physical"]
    e.require(
        initial["inside_mM"] == f["after"]["physical"]["inside_mM"]
        and initial["outside_mM"] == f["after"]["physical"]["outside_mM"],
        "Initialization changed chemistry",
    )
    physical(trace["initial"], g, initial, ledger, electrical=True)
    total_cycles = 0.0
    for index, (step, raw) in enumerate(zip(trace["steps"], trace["raw_steps"], strict=True)):
        e.require(
            step["index"] == raw["index"] == index
            and step["raw_label_s"] == trace["labels_s"][index]
            and step["before_elapsed_s"] == index * plan["dt_s"]
            and step["after_elapsed_s"] == (index + 1) * plan["dt_s"],
            "Step chronology",
        )
        e.require(
            step["order"] == ["before_ordinary", "after_ordinary", "after_voltage"]
            and step["before"] == step["before_ordinary"],
            "Step boundary order",
        )
        previous = trace["initial"] if index == 0 else trace["steps"][index - 1]["after_voltage"]
        start = raw["before"]
        for name in ("inside_mM", "outside_mM", "at_membrane_mM", "voltage_V"):
            e.require(
                start["physical"][name] == previous["physical"][name], "Disconnected native step"
            )
        e.require(
            start["rho_pump"] == variant["rho_pump"] and start["pump_block"] == 1.0,
            "Pump control changed",
        )
        before, after, end = (
            step[k] for k in ("before_ordinary", "after_ordinary", "after_voltage")
        )
        for name in ("inside_mM", "outside_mM", "at_membrane_mM"):
            e.require(
                start["physical"][name] == before["physical"][name], "Hidden concentration update"
            )
            e.require(
                after["physical"][name] == end["physical"][name], "Voltage update changed chemistry"
            )
        passive = [call for call in raw["calls"] if call["function"] == "electroflux"]
        pumps = [call for call in raw["calls"] if call["function"] == "pumpNaKATP"]
        e.require(
            [v["species_index"] for v in passive] == list(range(6))
            and len(pumps) == int(variant["pump"])
            and len(raw["calls"]) == 6 + len(pumps),
            "Raw call coverage",
        )
        density = [[0.0] * 30 for _ in range(6)]
        cycles = [0.0] * 30
        if pumps:
            e.require(raw["calls"][0] is pumps[0], "Pump/passive ordering")
            args = pumps[0]["inputs"]
            e.require(args["T"] == 298.15 and args["block"] == 1.0, "Pump temperature/block")
            for key, field, s in (
                ("cNai", "at_membrane_mM", 0),
                ("cNao", "outside_mM", 0),
                ("cKi", "at_membrane_mM", 1),
                ("cKo", "outside_mM", 1),
            ):
                e.require(args[key] == start["physical"][field][s], "Wrong live pump pool")
            e.require(args["Vm"] == start["physical"]["voltage_V"], "Wrong live pump voltage")
            expected = pump_density(args, settings["pump_parameters"], alpha)
            ledger.compare("raw_pump_density", pumps[0]["returned"], expected, 2e-18)
            e.require(
                before["reported_NaK_rate"] == pumps[0]["returned"][2],
                "Pump diagnostic mislabeled/transformed",
            )
            for j in range(30):
                factor = (
                    variant["rho_pump"]
                    if variant["cluster_open"] or j not in g["boundary_faces"]
                    else 0.0
                )
                density[0][j], density[1][j] = factor * expected[0][j], factor * expected[1][j]
                cycles[j] = -density[0][j] / 3
        else:
            e.require(all(v == 0 for v in before["reported_NaK_rate"]), "Disabled pump owns rate")
        for s, call in enumerate(passive):
            args = call["inputs"]
            e.require(
                args["T"] == 298.15
                and args["rho"] == 1.0
                and args["Dc"] == diffusivity[s]
                and args["d"] == [7.5e-9] * 30
                and args["zc"] == [Z[s]] * 30
                and args["cA"] == start["physical"]["outside_mM"][s]
                and args["cB"] == start["physical"]["at_membrane_mM"][s],
                "Wrong live passive inputs",
            )
            ledger.compare(
                "nonce_voltage_V", args["vBA"], start["physical"]["voltage_V"], 1e-22, 0.0
            )
            expected = passive_density(args)
            ledger.compare("raw_passive_density", call["returned"], expected, 2e-18)
            for j in range(30):
                if variant["cluster_open"] or j not in g["boundary_faces"]:
                    density[s][j] += expected[j]
        ledger.compare(
            "applied_density", before["physical"]["ordinary_density_mol_per_m2_s"], density, 2e-18
        )
        for s in range(6):
            transfer = [
                value * area * plan["dt_s"]
                for value, area in zip(density[s], g["membrane_areas_m2"], strict=True)
            ]
            predicted = [
                before["physical"]["inside_mM"][s][i]
                + math.fsum(
                    v for v, o in zip(transfer, g["membrane_owners"], strict=True) if o == i
                )
                / g["cell_volumes_m3"][i]
                for i in range(7)
            ]
            outside = [
                v - math.fsum(transfer) / g["effective_bath_volume_m3"]
                for v in before["physical"]["outside_mM"][s]
            ]
            ledger.compare("inside_update_mM", after["physical"]["inside_mM"][s], predicted, 2e-12)
            ledger.compare("outside_update_mM", after["physical"]["outside_mM"][s], outside, 2e-12)
        for point in (before, after):
            physical(point, g, initial, ledger, electrical=False)
        physical(end, g, initial, ledger, electrical=True)
        total_cycles += (
            math.fsum(v * a for v, a in zip(cycles, g["membrane_areas_m2"], strict=True))
            * plan["dt_s"]
            * 1e15
        )
    e.require(row["final"] == trace["steps"][-1]["after_voltage"], "Final disconnected from trace")
    for hist, field in (
        ("cc_time", "inside_mM"),
        ("cc_env_time", "outside_mM"),
        ("vm_time", "voltage_V"),
        ("I_mem_time", "I_mem_A"),
        ("rho_cells_time", "rho_C_per_m3"),
    ):
        e.require(
            row["histories"][hist]["values"]
            == [
                trace["steps"][i]["after_voltage"]["physical"][field]
                for i in trace["sampled_indices"]
            ],
            "Native history alignment: " + hist,
        )
    e.require(
        row["histories"]["rate_NaKATP_time"]["values"]
        == [
            trace["steps"][i]["after_voltage"]["reported_NaK_rate"]
            for i in trace["sampled_indices"]
        ],
        "Rate history alignment",
    )
    e.require(
        row["histories"]["time"]["values"]
        == [trace["labels_s"][i] for i in trace["sampled_indices"]]
        and trace["storage"]
        == [dict(index=i, raw_label_s=trace["labels_s"][i]) for i in trace["sampled_indices"]],
        "Storage chronology",
    )
    return dict(actual_signed_cycles_fmol=total_cycles, observed_steps=8, physical_records=25)


def audit():
    r = e.authenticate()
    packet = e.read(e.CAPTURE / "betse.json")
    rows, plan = packet["rows"], r["protocol"]
    e.require(
        packet["installed_python_sha256"]
        == {
            k: v
            for k, v in r["upstream"]["files_sha256"].items()
            if k.startswith("betse/") and k.endswith(".py")
        },
        "Native installed code",
    )
    e.require(
        set(rows)
        == {v["id"] + "/" + mode for v in plan["variants"] for mode in ("observed", "unobserved")},
        "Native row set",
    )
    ledger = e.Ledger()
    summaries = {}
    for variant in plan["variants"]:
        pair = []
        for mode in ("observed", "unobserved"):
            row = rows[variant["id"] + "/" + mode]
            e.require(
                row == e.read(e.CAPTURE / "native" / variant["id"] / mode / "result.json"),
                "Aggregate/individual mismatch",
            )
            e.require(
                row["id"] == variant["id"]
                and row["mode"] == mode
                and (row["trace"] is None) == (mode == "unobserved"),
                "Row identity",
            )
            e.require(
                {k: row["geometry"][k] for k in r["expected_geometry"]} == r["expected_geometry"],
                "Captured geometry differs",
            )
            result = review_row(plan, variant, row, ledger)
            if result is not None:
                summaries[variant["id"]] = result
            pair.append(row)
        for key in set(pair[0]) - {"mode", "trace"}:
            e.require(pair[0][key] == pair[1][key], "Observation changed native output: " + key)
    notices = (e.CAPTURE / "native.stderr.log").read_text().splitlines()
    e.require(
        len(notices) == 24
        and all(
            line == "[pump_job.py] Ignoring cutting event, as cut profiles are disabled."
            for line in notices
        ),
        "Unexpected native stderr",
    )
    return dict(
        status="native_pump_lifecycle_independently_closed",
        comparisons=ledger.count,
        maxima=ledger.maxima,
        native_runs=12,
        observed_steps=48,
        observer_pairs=6,
        physical_records=150,
        variants=summaries,
        known_disabled_cut_notices=len(notices),
        native_pickles_hashed_not_executed=True,
        coupled_trajectory_qualified=False,
        energy_convergence_qualified=False,
        biology_validated=False,
        gpu_tested=False,
    )


def execute(output, tests):
    e.require(
        output.is_relative_to(e.ROOT / "runs")
        and output != e.ROOT / "runs"
        and not output.exists(),
        "Fresh review output required",
    )
    receipt = e.software(tests, 20)
    output.mkdir(parents=True)
    start = time.monotonic()

    def deadline(_sig, _frame):
        raise TimeoutError("Saved-number audit exceeded 45 seconds")

    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, 45)
    try:
        inputs = {str(p.relative_to(e.ROOT)): e.sha(p) for p in Path(__file__).parent.glob("*.py")}
        e.write(
            output / "registration.json",
            dict(
                schema="cells.native_pump_lifecycle_review@1",
                capture=str(e.CAPTURE.relative_to(e.ROOT)),
                capture_completion_sha256=e.COMPLETION_SHA,
                source_sha256=inputs,
                tests=receipt,
                registered_utc=datetime.now(UTC).isoformat(),
                precision_digits=70,
                timeout_seconds=45,
                forbidden_imports=list(e.FORBIDDEN),
            ),
        )
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in inputs:
                archive.write(e.ROOT / name, arcname=name)
        with e.model_fence():
            result = audit()
            e.authenticate()
        e.require(all(e.sha(e.ROOT / n) == h for n, h in inputs.items()), "Review source changed")
        e.write(output / "review.json", result)
        e.write(
            output / "completion.json",
            dict(
                status=result["status"],
                elapsed_seconds=time.monotonic() - start,
                finished_utc=datetime.now(UTC).isoformat(),
                files_sha256={p.name: e.sha(p) for p in output.iterdir() if p.is_file()},
                comparisons=result["comparisons"],
                native_runs=12,
                observed_steps=48,
                observer_pairs=6,
                biology_validated=False,
                coupled_trajectory_qualified=False,
                production_changed=False,
                automatic_followup=False,
            ),
        )
        print(
            dict(
                status=result["status"],
                comparisons=result["comparisons"],
                elapsed_seconds=time.monotonic() - start,
                completion_sha256=e.sha(output / "completion.json"),
            )
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        e.write(
            output / "failure.json",
            dict(status="review_failed_not_closed", traceback=traceback.format_exc()),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--tests", type=Path, required=True)
    args = parser.parse_args()
    execute(args.output.resolve(), args.tests.resolve())
