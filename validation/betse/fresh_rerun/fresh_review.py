"""Fresh saved-evidence review using the established independent arithmetic."""

from itertools import islice
from types import SimpleNamespace

import common as u


def modules():
    u.module_path("pump_relaxation_audit")
    import native_read
    import saved_review

    u.module_path("pump_relaxation_clock")
    import clock_labels

    return saved_review, native_read, clock_labels


def prefix(full, short, exact, *, duration_s=0.001, progress=None):
    match = exact.Exact()
    count = short["steps"]
    u.need(
        short["dt_s"] == full["dt_s"] and count == round(duration_s / full["dt_s"]), "Prefix clock"
    )
    match.match(full["trace"]["initial"], short["trace"]["initial"], "Prefix initial state")
    for field in ("steps", "raw_steps"):
        for index, (a, b) in enumerate(
            zip(islice(full["trace"][field], count), short["trace"][field], strict=True), 1
        ):
            excluded = {"raw_label_s"} if field == "steps" else set()
            match.match(
                {k: v for k, v in a.items() if k not in excluded},
                {k: v for k, v in b.items() if k not in excluded},
                "Physical prefix " + field,
            )
            if progress is not None and (index % 1000 == 0 or index == count):
                progress("prefix_steps", field=field, completed=index, total=count)
    for name in full["histories"]:
        if name != "time":
            match.match(
                full["histories"][name]["values"][: count - 1],
                short["histories"][name]["values"],
                "Physical history prefix " + name,
            )
    match.match(
        full["trace"]["steps"][count - 1]["after_voltage"], short["final"], "Prefix endpoint"
    )
    return dict(steps=count, exact_scalars=match.scalars, raw_display_labels_excluded=True)


def native(output, campaign, preparation, plan, name, index):
    saved, reader, clocks = modules()
    e = saved.e
    dt = u.RANGES[name][index]
    directory = campaign / "native" / name / str(index) / "capture"
    u.authenticate_stage(directory.parent)
    u.authenticate_stage(campaign / "reference")
    baseline = preparation["rows"][name + "/observed"]
    variant = next(
        v for v in preparation["native_preparation"]["protocol"]["variants"] if v["id"] == name
    )
    with e.model_fence():
        row, format_check = reader.read(directory / "stream")
        saved.native_records.identity(row, baseline, dt, plan["duration_s"], "observed")
        ledger = e.Ledger()
        physical = clocks.inspect(
            saved.native_records, saved.c.exact.Exact, row, baseline, plan, variant, ledger
        )
        points = saved.native_energy.reconstruct(row, variant, plan["common_times_s"], ledger)
        target = saved.d.sample(
            u.read(
                campaign
                / "reference/reference"
                / name
                / plan["reference"]["primary"]
                / "result.json"
            ),
            plan["common_times_s"],
        )
        checks = saved.state_checks(points, target, plan)
        energy = saved.d.discrepancy(
            points["energy"]["max_defect_pJ"], 0.0, plan["accounting"]["native_finest_energy_pJ"]
        )
        pair = overlap = None
        if index == 2:
            u.authenticate_stage(campaign / "native" / name / "quiet")
            u.authenticate_stage(campaign / "native" / name / "prefix")
            pair = reader.pair(
                directory / "stream", campaign / "native" / name / "quiet/capture/stream"
            )
            short, _ = reader.read(campaign / "native" / name / "prefix/capture/stream")
            overlap = prefix(row, short, saved.c.exact)
    result = dict(
        case=name,
        dt_s=dt,
        updates=row["steps"],
        reference_checks=checks,
        finest_energy_check=energy,
        physical=physical,
        format_check=format_check,
        common_points={k: points[k] for k in ("states", "times_s", "voltage_V")},
        energy=points["energy"],
        observer_pair=pair,
        physical_prefix=overlap,
        independent_comparisons=ledger.count,
        independent_maxima=ledger.maxima,
        decimal_digits=70,
        native_every_update_accounting=True,
    )
    u.write(output / "result.json", result)
    return {k: result[k] for k in ("case", "dt_s", "updates", "independent_comparisons")}


def conclude(output, campaign, preparation, plan):
    saved, _, _ = modules()
    e, d = saved.e, saved.d
    u.authenticate_stage(campaign / "cpu")
    u.authenticate_stage(campaign / "reference")
    for name in u.VARIANTS:
        for i in range(3):
            u.authenticate_stage(campaign / "review" / name / str(i))
    source = u.ROOT / "validation/betse/pump_relaxation_audit/saved_review.py"
    adapted = u.private("_fresh_saved_cells_review", source)
    diagnostic = u.private(
        "_fresh_saved_arrays", u.ROOT / "validation/betse/pump_pilot_diagnosis/diagnose.py"
    )
    diagnostic.CAPTURE = campaign / "cpu"

    def path(name):
        u.need(name in ("matched", "reference"), "Unexpected historical packet request")
        return campaign / ("cpu" if name == "matched" else "reference")

    adapted.ctx = SimpleNamespace(
        **(
            vars(adapted.ctx)
            | dict(
                path=path,
                cells_reader=lambda: diagnostic,
                PACKETS={"matched": (None, u.sha(campaign / "cpu/registration.json"))},
            )
        )
    )
    reference_preparation = dict(protocol=plan, cases=preparation["cases"])
    with e.model_fence():
        cells_result, records = adapted.cells((reference_preparation, preparation))
        constraints, refinements, native_rows = {}, {}, {}
        for name in u.VARIANTS:
            rows = [u.read(campaign / "review" / name / str(i) / "result.json") for i in range(3)]
            u.need([r["dt_s"] for r in rows] == u.RANGES[name], "Native range membership")
            native_rows[name] = rows
            constraints.update(
                {name + "/native/" + k: v for k, v in rows[-1]["reference_checks"].items()}
            )
            constraints[name + "/native/energy_closure"] = rows[-1]["finest_energy_check"]
            cell_rows = [
                cells_result["rows"][adapted.d_key(name, h)] for h in plan["cells_steps_s"]
            ]
            constraints.update({name + "/cells/" + k: v for k, v in cell_rows[-1].items()})
            finest = records[adapted.d_key(name, plan["cells_steps_s"][-1])]
            constraints.update(
                {
                    name + "/cross/" + k: v
                    for k, v in saved.state_checks(
                        rows[-1]["common_points"], finest, plan, cross=True
                    ).items()
                }
            )
            for engine, errors in (
                ("native", [r["reference_checks"] for r in rows]),
                ("cells", cell_rows),
            ):
                for field, unit in (("amount", "fmol"), ("energy", "pJ"), ("voltage", "V")):
                    refinements[name + "/" + engine + "/" + field] = d.refinement(
                        [r[field]["max_error"] for r in errors],
                        plan["refinement"][f"floor_{field}_{unit}"],
                        plan["refinement"]["contraction_max"],
                    )
        failed_constraints = [k for k, v in constraints.items() if v["failures"]]
        failed_refinement = [k for k, v in refinements.items() if not v["passed"]]
    result = dict(
        status="fresh_10ms_numerical_review_pass"
        if not failed_constraints and not failed_refinement
        else "fresh_10ms_numerical_review_failed",
        constraints=constraints,
        refinement=refinements,
        failed_constraints=failed_constraints,
        failed_refinement=failed_refinement,
        cells=cells_result,
        native_rows=18,
        native_updates=sum(r["updates"] for rows in native_rows.values() for r in rows),
        finest_observer_pairs=6,
        physical_prefixes=6,
        prior_qualification_inherited=False,
        historical_artifacts_recovered=False,
        biological_validation=False,
        steady_state_qualified=False,
        full_betse_parity=False,
        production_changed=False,
        scientific_tolerances_changed=False,
        automatic_followup=False,
    )
    u.write(output / "comparison.json", result)
    u.need(
        not failed_constraints and not failed_refinement,
        "Fresh numerical criteria failed; retained comparison.json",
    )
    return result
