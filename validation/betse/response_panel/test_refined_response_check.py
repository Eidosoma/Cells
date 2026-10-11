"""Fine-grid decoder/corruption tests use saved or explicitly synthetic data, no ODE."""

import copy
import hashlib
import json
import struct
import subprocess

import pytest
import refined_response_cells_check as local
import refined_response_check as check
import refined_response_context as ctx
import refined_response_native as native
from test_refined_response import plan as plan
from test_refined_response import prior as prior
from test_refined_response import registered as registered
from test_refined_response import saved as saved

c = ctx.c


def array(values, shape):
    return {
        "dtype": "<f8",
        "shape": shape,
        "values": copy.deepcopy(values),
        "bytes_sha256": hashlib.sha256(
            b"".join(struct.pack("<d", v) for v in check.numbers(values))
        ).hexdigest(),
    }


@pytest.mark.parametrize("h", [12.5e-6, 6.25e-6])
@pytest.mark.parametrize("condition", ["baseline", "zero_amplitude", "static_blocked"])
def test_all_retained_fine_native_steps_checked(registered, saved, h, condition):
    view = ctx.panel_view(registered, h)
    row = next(r for r in view["native_rows"] if r["condition"] == condition)
    checks = check.Checks()
    result = check.native_record(view, saved[ctx.prior.key(row)]["observed"], row, checks)
    assert checks.failed_count == 0, checks.failures
    assert checks.count == 266 + 364 * ctx.count(h)
    assert len(result) == ctx.count(h) + 1
    assert all(len(r["flux_fmol_per_s"]) == 21 and len(r["current_A"]) == 7 for r in result[:-1])
    assert len(check.intervals(result)) == ctx.count(h)
    assert result[-1]["current_A"] == result[-1]["flux_fmol_per_s"] == []
    assert len(check.common_grid(result)) == 41


@pytest.mark.parametrize("h", [12.5e-6, 6.25e-6])
def test_synthetic_fine_pulse_with_baseline_transport_rejected(registered, saved, prior, h):
    view = ctx.panel_view(registered, h)
    row = next(r for r in view["native_rows"] if r["condition"] == "suppression_recovery")
    packet = copy.deepcopy(saved[f"{h:.8f}/baseline"]["observed"])
    packet["result"]["row"] = row
    packet["metadata"] = ctx.prepared(row)["metadata"]
    packet["result"]["final_metadata"] = packet["metadata"] | {
        "pickles_present": {"seed": True, "init": False, "sim": True}
    }
    events = c.read(ctx.DISPATCH / ctx.prior.key(row) / "dispatch.json")["events"]
    for event, dispatched in zip(packet["events"]["events"], events, strict=True):
        for name in native.VARIABLE:
            event["before"]["arrays"][name] = copy.deepcopy(dispatched["before"]["arrays"][name])
            for boundary in ("after", "before_update"):
                event[boundary]["arrays"][name] = copy.deepcopy(dispatched["after"]["arrays"][name])
    last = events[-1]["after"]["arrays"]
    packet["result"]["final_state"]["arrays"].update(
        {k: copy.deepcopy(last[k]) for k in native.VARIABLE}
    )
    numerical = packet["result"]["numerical"]
    numerical["final"]["Dm_cells"] = copy.deepcopy(last["Dm_cells"])
    numerical["permeability_m_per_s"] = [
        [v / 7.5e-9 for v in a] for a in last["Dm_cells"]["values"]
    ]
    numerical["ordinary"]["dd_time"] = array(
        [e["after"]["arrays"]["Dm_cells"]["values"] for e in events[1:]], [ctx.count(h) - 1, 6, 30]
    )
    assert native.check_row(row, "observed", packet, prior, registered["plan"], ctx.prepared(row))[
        "observed_steps"
    ] == ctx.count(h)
    checks = check.Checks()
    check.native_record(view, packet, row, checks)
    assert checks.failed_count > 0 and any("GHK" in r["id"] for r in checks.failures)


@pytest.mark.parametrize("h", [12.5e-6, 6.25e-6])
@pytest.mark.parametrize(
    "corruption", ["event_count", "late_clock", "late_control", "late_nonce", "final_Dm", "dtype"]
)
def test_late_native_linkage_corruption_rejected(registered, saved, prior, h, corruption):
    row = next(
        r for r in registered["native_rows"] if (r["dt_s"], r["condition"]) == (h, "baseline")
    )
    packet = copy.deepcopy(saved[ctx.prior.key(row)]["observed"])
    event = packet["events"]["events"][-1]
    if corruption == "event_count":
        packet["events"]["events"].pop()
    elif corruption == "late_clock":
        event["raw_label_s"] -= h
    elif corruption == "late_control":
        a = event["after"]["arrays"]["Dm_scheduled"]
        a["values"][0][0] = 1.0
        event["after"]["arrays"]["Dm_scheduled"] = array(a["values"], a["shape"])
    elif corruption == "late_nonce":
        a = event["before_update"]["arrays"]["vm"]
        a["values"][0] += 1.0
        event["before_update"]["arrays"]["vm"] = array(a["values"], a["shape"])
    elif corruption == "final_Dm":
        a = packet["result"]["final_state"]["arrays"]["Dm_cells"]
        a["values"][0][0] *= 0.5
        packet["result"]["final_state"]["arrays"]["Dm_cells"] = array(a["values"], a["shape"])
    else:
        event["after"]["arrays"]["cc_cells"]["dtype"] = "<f4"
    with pytest.raises(ValueError):
        native.check_row(
            row,
            "observed",
            packet,
            prior,
            registered["plan"],
            ctx.prepared(row),
            c.read(ctx.overlap_path(row, "observed")),
        )


@pytest.fixture(scope="module")
def blocked(registered):
    """Repeat a constant blocked solution on new grids in memory, not a solver run."""
    baseline = c.read(
        ctx.legacy.evidence.SESSION / "cells/blocked/jax_eager/0.00005000/result.json"
    )
    results = {}
    for row in registered["cells_rows"]:
        if row["condition"] != "static_blocked":
            continue
        h, factor = row["hold_step_s"], row["subdivision"]
        n, count = ctx.count(h) * factor, ctx.count(h)
        record = copy.deepcopy(baseline) | {
            "id": row["id"],
            "definition": registered["cells_definitions"][row["id"]],
            "final_step_index": n,
        }
        record["times"] = array([k * (h / factor) for k in range(n)] + [0.001], [n + 1])
        for group, length in (("history", n + 1), ("observations", count + 1)):
            for name, original in baseline[group].items():
                record[group][name] = array(
                    [original["values"][0] for _ in range(length)], [length, *original["shape"][1:]]
                )
        record["observations"]["times"] = array(
            registered["common_times_s"][f"{h:.8f}"], [count + 1]
        )
        results[row["id"]] = record
    return results


@pytest.mark.parametrize("h", [12.5e-6, 6.25e-6])
@pytest.mark.parametrize("backend", ["jax_eager", "jax_jit"])
@pytest.mark.parametrize("factor", [1, 2, 4])
def test_synthetic_blocked_solution_every_accepted_and_observed_point(
    registered, blocked, h, backend, factor
):
    view = ctx.panel_view(registered, h)
    row = next(
        r
        for r in view["cells_rows"]
        if r["id"] == ctx.identifier(h, "static_blocked", backend, factor)
    )
    checks = check.Checks()
    result = local.cells_record(view, blocked[row["id"]], row, checks)
    assert checks.failed_count == 0
    assert checks.count == 24 * (ctx.count(h) * factor + 1) + 86 * (ctx.count(h) + 1)
    assert all(v == 0 for point in result for a in point.values() for v in a)


@pytest.mark.parametrize("h", [12.5e-6, 6.25e-6])
@pytest.mark.parametrize(
    "corruption",
    [
        "clock",
        "definition",
        "shape",
        "bytes",
        "final_step",
        "late_padding",
        "late_flux",
        "terminal_control",
        "terminal_current",
        "missing_readout",
        "diagnostic",
    ],
)
def test_rehashed_fine_cells_corruptions_rejected(registered, blocked, h, corruption):
    view = ctx.panel_view(registered, h)
    row = next(
        r
        for r in view["cells_rows"]
        if r["id"] == ctx.identifier(h, "static_blocked", "jax_eager", 4)
    )
    record = copy.deepcopy(blocked[row["id"]])
    if corruption == "definition":
        record["definition"]["execution"]["dt"] *= 2
    elif corruption == "final_step":
        record["final_step_index"] -= 1
    elif corruption == "missing_readout":
        record["observations"].pop("membrane_current_A")
    elif corruption == "shape":
        record["observations"]["voltage_V"]["shape"][0] = 41
    elif corruption == "bytes":
        record["times"]["bytes_sha256"] = "0" * 64
    elif corruption == "diagnostic":
        record["diagnostics"]["max_balance_error_fmol"] = -1
    elif corruption == "clock":
        a = record["times"]
        a["values"][-2] += 1e-8
        record["times"] = array(a["values"], a["shape"])
    else:
        group, name, indices = {
            "late_padding": ("history", "amount_increment", [-2, 0, 7]),
            "late_flux": ("observations", "leak_flux_fmol_per_s", [-2, 0, 0]),
            "terminal_control": ("observations", "leak_multiplier", [-1, 0, 0]),
            "terminal_current": ("observations", "membrane_current_A", [-1, 0]),
        }[corruption]
        a = record[group][name]
        cursor = a["values"]
        for i in indices[:-1]:
            cursor = cursor[i]
        cursor[indices[-1]] = 1
        record[group][name] = array(a["values"], a["shape"])
    checks = check.Checks()
    try:
        local.cells_record(view, record, row, checks)
    except ValueError:
        return
    assert checks.failed_count > 0


@pytest.fixture(scope="module")
def coarse():
    registered = c.read(ctx.COARSE / "registration.json")
    result = check.read_panel(ctx.COARSE, registered, registered, coarse=True)
    return registered, result


def test_generalized_checker_reproduces_all_original_coarse_surfaces(coarse):
    r, (natives, cells, laws, _, _, _) = coarse
    original = c.read(ctx.COARSE / "comparison.json")
    scopes = check.compare_panel(r, natives, cells, 6.25e-6)
    total = check.combine([laws, *scopes.values()])
    assert total["comparisons"] == original["comparisons"] == 345576
    assert total["failed_comparisons"] == original["failed_comparisons"] == 150
    assert total["maximum_normalized_error"] == original["maximum_normalized_error"]
    assert laws["comparisons"] == 198264 and laws["failed_comparisons"] == 0
    assert laws["first_failures"] == []
    for name, scope in scopes.items():
        old = original["comparisons_by_scope"][name.split("/", 1)[1]]
        assert {k: scope[k] for k in old} == old


def test_coarse_arithmetic_is_exact_software_overlap(coarse):
    r, (natives, cells, _, _, _, _) = coarse
    for row in r["native_rows"]:
        packet = native.links.read_packet(
            ctx.COARSE / "native" / row["condition"] / "observed", "observed"
        )
        assert natives[row["condition"]] == check.legacy.native_record(
            r, packet, row, check.Checks()
        )
    for row in r["cells_rows"]:
        record = c.read(ctx.COARSE / "cells" / row["id"] / "result.json")
        assert cells[row["id"]] == check.legacy.local.cells_record(r, record, row, check.Checks())


def zero_canonical(count):
    return [
        {
            k: [0.0] * size if k not in ("current_A", "flux_fmol_per_s") or j < count else []
            for k, size in (
                ("voltage_V", 7),
                ("amount_fmol", 24),
                ("transfer_fmol", 21),
                ("flux_fmol_per_s", 21),
                ("current_A", 7),
            )
        }
        for j in range(count + 1)
    ]


def test_complete_scope_counts_required_selection_and_unhidden_rejection(registered):
    panels, scopes, laws = {}, {}, {}
    for h in (25e-6, 12.5e-6, 6.25e-6):
        view = (
            c.read(ctx.COARSE / "registration.json")
            if h == 25e-6
            else ctx.panel_view(registered, h)
        )
        canonical = zero_canonical(ctx.count(h))
        natives = {cond: copy.deepcopy(canonical) for cond in registered["plan"]["conditions"]}
        cells = {r["id"]: copy.deepcopy(canonical) for r in view["cells_rows"]}
        if h != 6.25e-6:
            natives["baseline"][-1]["amount_fmol"][22] = 1.0  # deliberate coarse-only mismatch
        panels[h] = view, natives, cells
        current = check.compare_panel(view, natives, cells, 6.25e-6)
        assert all(
            s["required"] == ("/cross_engine/" not in key or h == 6.25e-6)
            for key, s in current.items()
        )
        scopes |= current
        laws[f"{h:.8f}"] = check.summary(check.Checks()) | {
            "comparisons": 4864 * ctx.count(h) + 3704
        }
    scopes |= check.across_holds(registered, panels)
    result = check.verdict(laws, scopes)
    assert len(scopes) == 132 and result["comparisons"] == 2494936
    assert result["required_gates"]["comparisons"] == 2298936
    assert result["required_gates"]["failed_comparisons"] == 0
    assert result["failed_comparisons"] > 0
    assert (
        result["status"] == "finest_held_response_gates_pass_with_coarse_rejections_pending_audit"
    )
    assert not result["trajectory_qualified"] and not result["forcing_convergence_qualified"]
    assert all(not s["required"] for k, s in scopes.items() if k.startswith("across_hold/"))
    selected = next(v for v in scopes.values() if v["required"])
    selected["failed_comparisons"] = 1
    assert check.verdict(laws, scopes)["status"] == "failed_not_qualified"


def test_summary_and_aggregate_never_alias_mutable_failures():
    checks = check.Checks()
    checks.compare("good", 0, 0, "x", {"x": 1, "relative": 0})
    first = check.summary(checks)
    aggregate = check.combine([first])
    checks.compare("bad", 2, 0, "x", {"x": 1, "relative": 0})
    checks.worst["actual"] = 99
    assert first["failed_comparisons"] == aggregate["failed_comparisons"] == 0
    assert first["first_failures"] == aggregate["first_failures"] == []
    first["worst"]["actual"] = -99
    assert aggregate["worst"]["actual"] == 0


def test_terminal_hold_differs_from_analytic_endpoint_at_both_fine_grids():
    law = c.read(ctx.held.law.PLAN)
    for h in (12.5e-6, 6.25e-6):
        schedule = ctx.held.held_schedule(c.read(ctx.held.PLAN), "suppression_recovery", h)
        assert schedule[-1]["time"] == (ctx.count(h) - 1) * h
        assert schedule[-1]["multipliers"]["Na"] != ctx.held.law.decimal_availability(
            0.001, law["candidate_pulse"]
        )


def test_checker_imports_and_subprocess_fence_without_models():
    code = """
import sys
sys.path.insert(0, "validation/betse/response_panel")
import refined_response_check as check
assert not any(n.split(".")[0] in check.fence.FORBIDDEN for n in sys.modules)
sys.meta_path.insert(0, check.fence.ImportFence())
for name in check.fence.FORBIDDEN:
    try:
        __import__(name)
    except RuntimeError as error:
        assert "Offline audit forbids" in str(error)
    else:
        raise AssertionError(name)
print("fence_pass")
"""
    result = subprocess.run(
        [str(c.CELLS_PYTHON), "-B", "-c", code],
        cwd=c.ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    assert result.stdout.strip() == "fence_pass"


def test_registered_definitions_parse_without_integrating(registered):
    code = """
import json, sys
from cells.core.specs import parse_spec
for definition in json.load(sys.stdin).values():
    parse_spec(definition)
print("48_declared_definitions_parse_no_integration")
"""
    result = subprocess.run(
        [str(c.CELLS_PYTHON), "-B", "-c", code],
        cwd=c.ROOT,
        input=json.dumps(registered["cells_definitions"]),
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    assert result.stdout.strip() == "48_declared_definitions_parse_no_integration"
