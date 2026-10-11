"""Independent full-grid surfaces using D082's saved-array readers and fsum reconstruction."""

import copy
import importlib
import math
from collections import Counter

import refined_audit_context as ctx

c = ctx.c
base = importlib.import_module("response_audit")
HOLDS = (0.000025, 0.0000125, 0.00000625)
WIDTHS = {
    "voltage_V": 7,
    "amount_fmol": 24,
    "transfer_fmol": 21,
    "flux_fmol_per_s": 21,
    "current_A": 7,
}


def cells_path(r, row, coarse=False):
    if coarse:
        return ctx.prior.prior.COARSE / "cells" / row["id"] / "result.json"
    name = "cells/" + row["id"] + "/result.json"
    if row["id"] in r["reused_cells"]:
        entry = r["reused_cells"][row["id"]]
        path = ctx.prior.FAILED / name
        c.require(entry["path"] == name and entry["sha256"] == c.sha(path), "Reused source differs")
        return path
    c.require(row in r["new_cells_rows"], "Unregistered new Cells source")
    return ctx.SESSION / name


def load_panels(r):
    panels = {}
    for h in HOLDS:
        if h == HOLDS[0]:
            view = c.read(ctx.prior.prior.COARSE / "registration.json")
        else:
            view = r | {
                "plan": r["plan"] | {"hold_step_s": h},
                "native_rows": [v for v in r["native_rows"] if v["dt_s"] == h],
                "cells_rows": [v for v in r["cells_rows"] if v["hold_step_s"] == h],
                "common_times_s": r["common_times_s"][f"{h:.8f}"],
            }
        c.require(len(view["common_times_s"]) == round(0.001 / h) + 1, "Wrong independent grid")
        natives, cells = {}, {}
        for row in view["native_rows"]:
            condition = row["condition"]
            prefix = (
                ctx.prior.prior.COARSE / "native" / condition
                if h == HOLDS[0]
                else ctx.prior.FAILED / "native" / f"{h:.8f}" / condition
            )
            numerical = c.read(prefix / "observed/result.json")["numerical"]
            natives[condition] = base.native_surface(view, numerical)
        for row in view["cells_rows"]:
            key = (row["condition"], row["backend"], row["subdivision"])
            c.require(key not in cells, "Duplicated independent Cells identity")
            cells[key] = base.cells_surface(view, c.read(cells_path(r, row, h == HOLDS[0])))
        c.require(len(natives) == 4 and len(cells) == 24, "Incomplete independent panel")
        panels[h] = natives, cells
    return panels


def compare(label, left, right, limits, required):
    c.require(len(left) == len(right) and len(left) in (41, 81, 161), "Independent grid differs")
    last, checks = len(left) - 1, base.AuditChecks()
    maxima, interval_max = dict.fromkeys(WIDTHS, 0.0), 0.0
    limits = limits | {"transfer_fmol": limits.get("transfer_fmol", limits["amount_fmol"])}
    for j, (a, b) in enumerate(zip(left, right, strict=True)):
        c.require(set(a) == set(b) == set(WIDTHS), "Independent surface fields differ")
        for unit, width in WIDTHS.items():
            expected = 0 if j == last and unit in ("flux_fmol_per_s", "current_A") else width
            c.require(
                len(a[unit]) == len(b[unit]) == expected, "Independent owner/endpoint axes differ"
            )
            for i, (x, y) in enumerate(zip(a[unit], b[unit], strict=True)):
                checks.compare(f"{label}/{j}/{unit}/{i}", x, y, unit, limits)
                maxima[unit] = max(maxima[unit], abs(x - y))
    for j in range(last):
        for i in range(21):
            a = left[j + 1]["transfer_fmol"][i] - left[j]["transfer_fmol"][i]
            b = right[j + 1]["transfer_fmol"][i] - right[j]["transfer_fmol"][i]
            checks.compare(
                f"{label}/intervals/{j}/transfer_fmol/{i}", a, b, "transfer_fmol", limits
            )
            interval_max = max(interval_max, abs(a - b))
    c.require(checks.count == 101 * last + 52, "Incomplete independent scalar coverage")
    result = base.immutable_summary(checks) | {
        "required": required,
        "status": "pass" if checks.failed_count == 0 else "rejected",
        "maximum_absolute_errors": maxima,
        "maximum_interval_transfer_error_fmol": interval_max,
    }
    return result, [copy.deepcopy(f) | {"scope": label} for f in checks.failures]


def common(surface):
    c.require(len(surface) in (41, 81, 161), "Unregistered independent projection")
    # Select exact saved boundaries; no interpolation or new endpoint rate.
    return [surface[i * ((len(surface) - 1) // 40)] for i in range(41)]


def rebuild(r, panels):
    scopes, failures = {}, []
    conditions = r["plan"]["conditions"]

    def add(label, a, b, limits, required, metadata):
        c.require(label not in scopes, "Duplicated independent comparison scope")
        result, failed = compare(label, a, b, limits, required)
        scopes[label] = result | metadata
        failures.extend(failed)

    for h in HOLDS:
        native, cells = panels[h]
        for condition in conditions:
            for backend in ("jax_eager", "jax_jit"):
                for a, b in ((1, 2), (2, 4)):
                    add(
                        f"{h:.8f}/fixed_input_solver/{condition}/{backend}/{a}-{b}",
                        cells[condition, backend, a],
                        cells[condition, backend, b],
                        r["criteria"]["instantaneous_tolerances"],
                        True,
                        {"hold_step_s": h},
                    )
                add(
                    f"{h:.8f}/cross_engine/{condition}/{backend}",
                    native[condition],
                    cells[condition, backend, 4],
                    r["criteria"]["trajectory_tolerances"],
                    h == HOLDS[-1],
                    {"hold_step_s": h},
                )
            for factor in (1, 2, 4):
                add(
                    f"{h:.8f}/backend/{condition}/{factor}",
                    cells[condition, "jax_eager", factor],
                    cells[condition, "jax_jit", factor],
                    r["criteria"]["instantaneous_tolerances"],
                    True,
                    {"hold_step_s": h},
                )
    for a, b in zip(HOLDS[:-1], HOLDS[1:], strict=True):
        for condition in conditions:
            for engine in ("native", "jax_eager", "jax_jit"):

                def select(h, condition=condition, engine=engine):
                    native, cells = panels[h]
                    return common(
                        native[condition] if engine == "native" else cells[condition, engine, 4]
                    )

                add(
                    f"across_hold/{a:.8f}-{b:.8f}/{condition}/{engine}",
                    select(a),
                    select(b),
                    r["criteria"]["trajectory_tolerances"],
                    False,
                    {
                        "interpretation": "joint_native_integration_and_forcing_resampling"
                        if engine == "native"
                        else "finely_integrated_Cells_input_hold_sensitivity",
                        "native_convergence_qualified": False,
                        "forcing_convergence_qualified": False,
                    },
                )
    c.require(len(scopes) == 132, "Incomplete independent scopes")
    return scopes, failures


def combine(values):
    c.require(bool(values), "No independent summaries")
    worst = max(values, key=lambda v: v["maximum_normalized_error"])
    return copy.deepcopy(
        {
            "comparisons": sum(v["comparisons"] for v in values),
            "failed_comparisons": sum(v["failed_comparisons"] for v in values),
            "maximum_normalized_error": worst["maximum_normalized_error"],
            "worst": worst["worst"],
            "first_failures": [f for v in values for f in v["first_failures"]][:100],
        }
    )


def compare_one(name, actual, expected):
    for key in (
        "comparisons",
        "failed_comparisons",
        "required",
        "status",
        "hold_step_s",
        "interpretation",
        "native_convergence_qualified",
        "forcing_convergence_qualified",
    ):
        c.require(
            actual.get(key) == expected.get(key), "Independent scope verdict differs: " + name
        )
    left, right = actual["first_failures"], expected["first_failures"]
    c.require(
        [v["id"] for v in left] == [v["id"] for v in right], "Independent failure identities differ"
    )
    pairs = [(a[k], b[k]) for a, b in zip(left, right, strict=True) for k in ("actual", "expected")]
    pairs += [
        (actual["maximum_absolute_errors"][u], expected["maximum_absolute_errors"][u])
        for u in WIDTHS
    ]
    pairs.append(
        (
            actual["maximum_interval_transfer_error_fmol"],
            expected["maximum_interval_transfer_error_fmol"],
        )
    )
    # D082's reconstruction-only allowance for fsum versus sequential sums.
    # Pass/fail normalization always uses the original physical criteria.
    c.require(
        all(math.isclose(a, b, rel_tol=2e-11, abs_tol=2e-20) for a, b in pairs),
        "Independent reconstructed values differ beyond summation roundoff",
    )


def compare_rebuild(original, scopes):
    saved = original["comparisons_by_scope"]
    c.require(set(scopes) == set(saved), "Independent scope coverage differs")
    for name, actual in scopes.items():
        compare_one(name, actual, saved[name])
    surface = combine(list(scopes.values()))
    required = combine([v for v in scopes.values() if v["required"]])
    c.require(
        surface["comparisons"] == 1121904
        and surface["failed_comparisons"] == 4173
        and required["comparisons"] == 925904
        and required["failed_comparisons"] == 0,
        "Independent full surface/gate coverage differs",
    )
    return surface, required


def classify(failures, scopes):
    c.require(
        len(failures) == len({v["id"] for v in failures}) == 4173,
        "Incomplete or duplicated full failure ledger",
    )
    rows = []
    for failure in failures:
        scope = failure["scope"]
        c.require(
            scope in scopes and scopes[scope]["required"] is False,
            "Required gate in failure ledger",
        )
        parts = scope.split("/")
        across = parts[0] == "across_hold"
        c.require(across or parts[1] == "cross_engine", "Unexpected diagnostic failure family")
        family = "across_hold" if across else "cross_engine/" + parts[0]
        suffix = failure["id"][len(scope) + 1 :].split("/")
        interval = suffix[0] == "intervals"
        j, unit, i = suffix[1:] if interval else suffix
        step = 0.000025 if across else float(parts[0])
        count = round(0.001 / step)
        c.require(
            failure["id"].startswith(scope + "/")
            and unit in WIDTHS
            and 0 <= int(i) < WIDTHS[unit]
            and 0 <= int(j) <= count
            and (not interval or unit == "transfer_fmol" and int(j) < count)
            and (unit not in ("current_A", "flux_fmol_per_s") or int(j) < count)
            and math.isfinite(failure["normalized_error"])
            and failure["normalized_error"] > 1,
            "Invalid diagnostic failure coordinate/value",
        )
        rows.append(
            failure
            | {
                "family": family,
                "condition": parts[2],
                "engine": parts[3],
                "time_s": int(j) * step,
                "interval_end_s": (int(j) + 1) * step if interval else None,
                "quantity": unit,
                "column": int(i),
                "required": False,
            }
        )
    families = dict(Counter(v["family"] for v in rows))
    c.require(
        families
        == {"cross_engine/0.00002500": 150, "cross_engine/0.00001250": 40, "across_hold": 3983},
        "Diagnostic failure classification differs",
    )
    return {
        "all_failures": rows,
        "by_family": families,
        "by_quantity": dict(Counter(v["quantity"] for v in rows)),
        "all_required_gates_pass": True,
        "forcing_convergence_qualified": False,
        "native_convergence_qualified": False,
    }
