"""Independent saved-number acceptance; never call a model or producer checker."""

import audit_evidence as context
import native_energy
import native_records

e, d = context.e, context.diagnostic


def key(identifier, dt):
    return identifier + "/dt_" + format(dt, ".8g")


def all_pass(result):
    e.require(
        result["failed_comparisons"] == 0 and not result["failed_groups"],
        "Independent numerical rejection",
    )
    e.require(
        len(result["refinements"]) == 36
        and all(v["passed"] for v in result["refinements"].values()),
        "Independent refinement rejection",
    )
    e.require(
        result["native_observed_steps"] == 6720
        and result["observer_pairs"] == 18
        and result["physical_records"] == 20178
        and len(result["exact_overlap_records"]) == 12,
        "Independent coverage",
    )


def notice_check(directory):
    notices = (directory / "betse.stderr.log").read_text().splitlines()
    e.require(
        len(notices) == 72
        and all(
            v == "[refinement_job.py] Ignoring cutting event, as cut profiles are disabled."
            for v in notices
        ),
        "Unexpected native stderr",
    )
    for name in ("runner.stderr.log", "reuse.stderr.log", "comparison.stderr.log"):
        e.require((directory / name).read_bytes() == b"", "Unexpected stderr: " + name)
    return len(notices)


def audit(r, sources, output):
    plan, trajectory = r["protocol"], r["protocol"]["trajectory"]
    capture = context.CAPTURE
    packet = e.read(capture / "betse.json")
    e.require(
        packet["installed_python_sha256"]
        == {
            k: v
            for k, v in r["native_preparation"]["upstream"]["files_sha256"].items()
            if k.startswith("betse/") and k.endswith(".py")
        },
        "Native installed source identity",
    )
    native = packet["records"]
    variants = r["native_preparation"]["protocol"]["variants"]
    e.require(
        set(native)
        == {
            key(v["id"], dt) + "/" + mode
            for v in variants
            for dt in plan["native_steps_s"]
            for mode in ("observed", "unobserved")
        },
        "Native record membership",
    )
    previous = e.read(d.CAPTURE / "betse.json")["records"]
    baseline = e.read(e.CAPTURE / "betse.json")["rows"]
    reference = e.read(capture / "reference.json")["records"]
    # This frozen reader decodes the original NPZ/checkpoint archives. Every file
    # in the new packet is already required to be a byte-identical copy of them.
    cells = d.cells_records(e.read(capture / "cells.json"), sources)
    constraints, grids, refinements, energy, overlap = {}, {}, {}, {}, {}
    e.require(
        set(reference)
        == {v["id"] + "/" + p["id"] for v in variants for p in plan["reference"]["solves"]},
        "Reference membership",
    )
    e.require(
        set(cells)
        == {key(v["id"], dt) + "/jax_jit" for v in variants for dt in plan["cells_steps_s"]}
        | {key(v["id"], plan["cells_eager_step_s"]) + "/jax_eager" for v in variants},
        "Cells membership",
    )
    for name, record in reference.items():
        context.same_record(
            record,
            e.read(context.child(capture, "reference/" + name + "/result.json")),
            "Reference aggregate/individual link",
        )
        primary = reference[name.split("/")[0] + "/" + plan["reference"]["primary"]]
        e.require(record["times_s"] == primary["times_s"], "Reference grid")
        e.shape(record["states"], [161, 59])
        e.shape(record["voltage_V"], [161, 7])
        limits = plan["reference"]
        checks = d.state_checks(
            record,
            primary,
            (
                limits["agreement_amount_fmol"],
                limits["agreement_energy_pJ"],
                limits["agreement_voltage_V"],
                0.0,
            ),
        )
        constraints.update({"reference/" + name + "/" + k: v for k, v in checks.items()})
    ledger = e.Ledger()
    updates, physical_records = 0, 0
    for variant in variants:
        ident = variant["id"]
        primary = d.sample(
            reference[ident + "/" + plan["reference"]["primary"]], plan["common_times_s"]
        )
        ladders = {"native": [], "cells": []}
        for dt in plan["native_steps_s"]:
            label = key(ident, dt)
            row, quiet = (
                e.read(context.child(capture, native[label + "/" + mode]))
                for mode in ("observed", "unobserved")
            )
            for mode, value in (("observed", row), ("unobserved", quiet)):
                native_records.identity(
                    value, baseline[ident + "/" + mode], dt, plan["duration_s"], mode
                )
                if dt == r["amendment"]["overlap_step_s"]:
                    overlap[label + "/" + mode] = context.same_record(
                        value,
                        e.read(context.child(d.CAPTURE, previous[label + "/" + mode])),
                        "Exact repeated native record",
                    )
            native_records.exact_pair(row, quiet)
            scope = native_records.inspect(
                row, baseline[ident + "/observed"], plan, variant, ledger
            )
            updates += scope["steps"]
            physical_records += scope["physical_records"]
            all_times = [i * dt for i in range(row["steps"] + 1)]
            reconstructed = native_energy.reconstruct(row, variant, all_times, ledger)
            saved = e.read(context.child(capture, "comparison_rows/" + label + "/result.json"))
            e.require(
                saved["points"]["times_s"] == reconstructed["times_s"],
                "Producer reconstruction clock link",
            )
            # Strict roundoff-only cross-check of every reconstructed coordinate;
            # these are not replacements for the registered scientific limits.
            ledger.compare(
                "producer_state_link",
                saved["points"]["states"],
                reconstructed["states"],
                2e-12,
                0.0,
            )
            ledger.compare(
                "producer_voltage_link",
                saved["points"]["voltage_V"],
                reconstructed["voltage_V"],
                2e-12,
                0.0,
            )
            points = d.sample(reconstructed, plan["common_times_s"])
            energy[label] = reconstructed["energy"]
            checks = d.state_checks(
                points,
                primary,
                (
                    trajectory["native_amount_fmol"],
                    trajectory["native_energy_pJ"],
                    trajectory["native_voltage_V"],
                    trajectory["relative"],
                ),
            )
            ladders["native"].append(checks)
            grids["native/" + label] = checks
            if dt == plan["native_steps_s"][-1]:
                finest = points
                constraints.update({ident + "/native_finest/" + k: v for k, v in checks.items()})
                constraints[ident + "/native_energy_balance"] = d.discrepancy(
                    reconstructed["energy"]["max_defect_pJ"],
                    0.0,
                    plan["accounting"]["native_finest_energy_pJ"],
                )
            directory = output / "native_rows" / label
            directory.mkdir(parents=True)
            e.write(
                directory / "review.json",
                dict(scope=scope, points=reconstructed, reference_checks=checks),
            )
            print("independently reviewed: " + label, flush=True)
        for dt in plan["cells_steps_s"]:
            label = key(ident, dt) + "/jax_jit"
            row = cells[label]
            e.require(row["times_s"] == plan["common_times_s"], "Cells observation grid")
            checks = d.state_checks(
                row,
                primary,
                (
                    trajectory["cells_state_atol"],
                    trajectory["cells_state_atol"],
                    trajectory["cells_voltage_V"],
                    trajectory["cells_state_rtol"],
                ),
            )
            checks["voltage"] = d.discrepancy(
                row["voltage_V"], primary["voltage_V"], trajectory["cells_voltage_V"]
            )
            constraints.update({label + "/reference/" + k: v for k, v in checks.items()})
            grids["cells/" + label] = checks
            ladders["cells"].append(checks)
            if dt == plan["cells_steps_s"][-1]:
                factor = trajectory["cross_engine_budget_multiplier"]
                checks = d.state_checks(
                    finest,
                    row,
                    (
                        factor * trajectory["native_amount_fmol"],
                        factor * trajectory["native_energy_pJ"],
                        factor * trajectory["native_voltage_V"],
                        trajectory["relative"],
                    ),
                )
                constraints.update({ident + "/cross_engine/" + k: v for k, v in checks.items()})
        for engine, values in ladders.items():
            for name, unit in (("amount", "fmol"), ("energy", "pJ"), ("voltage", "V")):
                refinements[ident + "/" + engine + "/" + name] = d.refinement(
                    [v[name]["max_error"] for v in values],
                    plan["refinement"][f"floor_{name}_{unit}"],
                    plan["refinement"]["contraction_max"],
                )
        label = key(ident, plan["cells_eager_step_s"])
        eager, jit = cells[label + "/jax_eager"], cells[label + "/jax_jit"]
        constraints[ident + "/backends/state"] = d.discrepancy(
            eager["states"], jit["states"], 2e-12, 2e-11
        )
        constraints[ident + "/backends/voltage"] = d.discrepancy(
            eager["voltage_V"], jit["voltage_V"], 2e-10, 2e-11
        )
    for label, record in cells.items():
        for names, budget in (
            (
                (
                    "max_balance_error_fmol",
                    "max_extracellular_balance_error_fmol",
                    "max_global_balance_error_fmol",
                ),
                "cells_material_fmol",
            ),
            (("max_countercharge_error_C",), "cells_charge_C"),
            (("max_energy_balance_error_pJ",), "cells_energy_pJ"),
        ):
            constraints[label + "/saved_diagnostics/" + budget] = d.discrepancy(
                [record["diagnostics"][k] for k in names],
                [0.0] * len(names),
                plan["accounting"][budget],
            )
    producer = e.read(capture / "comparison.json")
    e.require(
        producer["comparisons"] == 616806
        and producer["failed_comparisons"] == 0
        and not producer["failed_groups"]
        and not producer["first_failure_examples"],
        "Unexpected producer verdict",
    )
    context.same_record(overlap, producer["exact_overlap_records"], "Producer overlap links")
    e.require(set(refinements) == set(producer["refinement"]), "Producer refinement membership")
    for name, values in refinements.items():
        p = producer["refinement"][name]
        e.require(
            values["passed"] == p["passed"] and values["floor"] == p["floor"],
            "Producer refinement decision",
        )
        ledger.compare("producer_refinement_errors", p["errors"], values["errors"], 2e-12, 0.0)
    result = dict(
        status="refined_pump_pilot_independent_review_recorded",
        comparisons=sum(v["comparisons"] for v in constraints.values()),
        failed_comparisons=sum(len(v["failures"]) for v in constraints.values()),
        failed_groups={k: v for k, v in constraints.items() if v["failures"]},
        constraints=constraints,
        reference_error_ladders=grids,
        refinements=refinements,
        native_energy=energy,
        exact_overlap_records=overlap,
        native_law_transfer_conservation_link_comparisons=ledger.count,
        native_law_transfer_conservation_link_maxima=ledger.maxima,
        native_observed_steps=updates,
        physical_records=physical_records,
        observer_pairs=18,
        decoded_cells_trajectories=24,
        full_state_restart_suffixes=6,
        complete_checkpoint_links=6,
        known_disabled_cut_notices=notice_check(capture),
        energy_accounting_independently_reconstructed_for=(
            "native only; Cells diagnostics remain source-bound saved reports, "
            "with the separate D114 family review preserved"
        ),
        native_pickles_hashed_not_executed=True,
        model_or_reference_rerun=False,
        production_changed=False,
        tolerance_changed=False,
        biology_validated=False,
        gpu_tested=False,
        automatic_followup=False,
    )
    # Preserve numerical rejection evidence before the controller applies all_pass.
    e.write(output / "review.json", result)
    return result
