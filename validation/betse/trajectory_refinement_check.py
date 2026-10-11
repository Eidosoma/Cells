"""Refinement panel aggregation; reuse frozen saved-state/physics arithmetic unchanged."""

import alignment as a
import contact as c
import trajectory_context as ctx
import trajectory_failure as prior
import trajectory_refinement_context as refined
from trajectory_check import Checks, cells_record, difference, native_record


def overlap(registered, output):
    """The repeated 25 us native and eight Cells runs must reproduce prior raw arrays."""
    protocol = registered["protocol"]
    native = c.read(output / "betse.json")
    local = c.read(output / "cells.json")
    old_native, old_local = (
        c.read(prior.SESSION / "betse.json"),
        c.read(prior.SESSION / "cells.json"),
    )
    native_count = 0
    for case in protocol["cases"]:
        for profile in protocol["native_constant_profiles"]:
            identifier = ctx.key(case["id"], profile, protocol["native_steps_s"][0])
            for mode in ("observed", "unobserved"):
                path = f"native/{identifier}/{mode}/result.json"
                c.require(
                    native["results"][identifier][mode] == path, "Noncanonical native result path"
                )
                record = c.read(output / path)
                old = c.read(prior.SESSION / old_native["results"][identifier][mode])
                for field in ("ordinary", "final", "trace"):
                    c.require(record[field] == old[field], "Repeated native trajectory changed")
                native_count += 1
    for identifier, path in local["results"].items():
        c.require(path == f"cells/{identifier}/result.json", "Noncanonical Cells result path")
        record = c.read(output / path)
        old = c.read(prior.SESSION / old_local["results"][identifier])
        for field in (
            "definition",
            "times",
            "history",
            "observations",
            "diagnostics",
            "final_step_index",
        ):
            c.require(record[field] == old[field], "Repeated Cells trajectory changed")
    return {
        "native_runs_byte_equal": native_count,
        "cells_runs_byte_equal": len(local["results"]),
        "timings_compared": False,
    }


# The aggregation below follows the frozen v1 comparator. Only registration/protocol
# identity and the additional old/new overlap gate differ; all arithmetic and limits
# are provided by the unchanged trajectory_check.py helpers and registered protocol.


def audit_data(registered, output):
    refined.validate_registration(registered)
    p = registered["protocol"]
    c.require(
        p == c.read(refined.PROTOCOL) and registered["base_protocol"] == c.read(a.PROTOCOL),
        "Protocol differs",
    )
    c.require(registered["geometry"] == ctx.native_geometry(), "Geometry source differs")
    c.require(
        registered["settings"] == c.read(ctx.evidence.SESSION / "betse.json")["settings"],
        "Registered mechanisms differ",
    )
    c.require(
        registered["cells_runtime"] == c.read(ctx.PRESERVATION)["runtime"],
        "Registered runtime differs",
    )
    native, local = c.read(output / "betse.json"), c.read(output / "cells.json")
    a.provenance(registered, native, local)
    c.require(
        native["engine"] == "actual_betse_full_init_loop"
        and local["engine"] == "unchanged_cells_checked_rk4_runner",
        "Not actual full engines",
    )
    c.require(
        native["trajectory_run"] is local["trajectory_run"] is True
        and local["device"] == "cpu"
        and local["x64_enabled"] is True
        and local["jit_disabled"] is False,
        "Execution context differs",
    )
    for record in (native, local):
        c.require(
            record["registration_sha256"] == c.sha(output / "registration.json"),
            "Worker inputs differ",
        )
        c.require(
            not any(w["category"] in p["forbidden_warning_categories"] for w in record["warnings"]),
            "Numerical runtime warning",
        )
    expected_native = {
        ctx.key(case["id"], profile, dt)
        for case in p["cases"]
        for profile in p["native_constant_profiles"]
        for dt in p["native_steps_s"]
    }
    c.require(
        set(native["results"]) == expected_native
        and set(local["results"]) == set(registered["cells_definitions"]),
        "Trajectory coverage differs",
    )
    for identifier, pair in native["results"].items():
        c.require(
            pair
            == {
                mode: f"native/{identifier}/{mode}/result.json"
                for mode in ("observed", "unobserved")
            },
            "Noncanonical native result paths",
        )
    c.require(
        all(
            path == f"cells/{identifier}/result.json"
            for identifier, path in local["results"].items()
        ),
        "Noncanonical Cells result paths",
    )
    checks, native_values, cells_values, refinements = Checks(), {}, {}, {}
    for case in p["cases"]:
        for profile in p["native_constant_profiles"]:
            for dt in p["native_steps_s"]:
                identifier = ctx.key(case["id"], profile, dt)
                pair = native["results"][identifier]
                c.require(
                    set(pair) == {"observed", "unobserved"}, "Noninterference partner missing"
                )
                records = {mode: c.read(output / path) for mode, path in pair.items()}
                for mode, record in records.items():
                    c.require(
                        record["mode"] == mode and record["id"] == identifier,
                        "Native partner identity differs",
                    )
                    c.require(
                        record["native_yaml_sha256"]
                        == c.sha((output / pair[mode]).parent / "native.yaml"),
                        "Native input YAML changed",
                    )
                c.require(
                    records["observed"]["ordinary"] == records["unobserved"]["ordinary"]
                    and records["observed"]["final"] == records["unobserved"]["final"]
                    and records["unobserved"]["trace"] is None,
                    "Observer noninterference failed",
                )
                for field in (
                    "dt_s",
                    "constants",
                    "geometry",
                    "settings",
                    "rho_channel",
                    "species",
                    "valence",
                    "permeability_m_per_s",
                    "configured_steps",
                    "native_pickle_present",
                ):
                    c.require(
                        records["observed"][field] == records["unobserved"][field],
                        "Noninterference partner parameters differ",
                    )
                native_values[identifier] = native_record(
                    registered, records["observed"], case, profile, dt, checks
                )
            keys = [ctx.key(case["id"], profile, dt) for dt in p["native_steps_s"]]
            # Coarse-to-middle is a contraction witness, not a selected-step acceptance.
            coarse = difference(
                "native_coarse/" + keys[0],
                native_values[keys[0]],
                native_values[keys[1]],
                {k: 1e100 for k in p["trajectory_tolerances"]},
                Checks(),
            )
            fine = difference(
                "native_refinement/" + keys[1],
                native_values[keys[1]],
                native_values[keys[2]],
                p["trajectory_tolerances"],
                checks,
            )
            for unit in fine:
                floor = p["instantaneous_tolerances"][
                    "amount_fmol" if unit == "transfer_fmol" else unit
                ]
                c.require(
                    fine[unit] <= p["refinement"]["native_contraction_max"] * coarse[unit] + floor,
                    "Native refinement does not contract above roundoff",
                )
            refinements[case["id"] + "/" + profile] = {
                "coarse_to_middle": coarse,
                "middle_to_fine": fine,
            }
        for backend in p["cells_backends"]:
            for dt in p["cells_steps_s"]:
                identifier = ctx.key(case["id"], backend, dt)
                record = c.read(output / local["results"][identifier])
                cells_values[identifier] = cells_record(
                    registered, record, case, backend, dt, checks
                )
            keys = [ctx.key(case["id"], backend, dt) for dt in p["cells_steps_s"]]
            refinements[case["id"] + "/" + backend] = difference(
                "cells_refinement/" + keys[0],
                cells_values[keys[0]],
                cells_values[keys[1]],
                p["instantaneous_tolerances"],
                checks,
            )
            target = native_values[
                ctx.key(case["id"], "matched_constants", p["native_steps_s"][-1])
            ]
            refinements[case["id"] + "/cross/" + backend] = difference(
                "cross/" + keys[-1],
                cells_values[keys[-1]],
                target,
                p["trajectory_tolerances"],
                checks,
            )
        for dt in p["cells_steps_s"]:
            keys = [ctx.key(case["id"], backend, dt) for backend in p["cells_backends"]]
            difference(
                "backend/" + keys[0],
                cells_values[keys[0]],
                cells_values[keys[1]],
                p["instantaneous_tolerances"],
                checks,
            )
    return {
        "prior_overlap": overlap(registered, output),
        "status": "pass" if checks.failed_count == 0 else "failed",
        "comparisons": checks.count,
        "failed_comparisons": checks.failed_count,
        "maximum_normalized_error": checks.maximum,
        "worst": checks.worst,
        "first_failures": checks.failures,
        "refinements_and_cross_differences": refinements,
        "native_observed_runs": len(native_values),
        "native_unobserved_runs": len(native_values),
        "cells_runs": len(cells_values),
        "native_steps_observed": len(p["cases"])
        * len(p["native_constant_profiles"])
        * sum(round(p["duration_s"] / dt) for dt in p["native_steps_s"]),
        "trajectory_run": True,
        "biological_validation": False,
    }
