"""Reference-only R1-S0: reuse frozen equations/settings, inspect a longer horizon."""

import contextlib
import importlib
import importlib.abc
import math
import sys

import relax_context as ctx

c = ctx.c


@contextlib.contextmanager
def model_fence():
    def blocked(name):
        return any(name == n or name.startswith(n + ".") for n in ctx.FORBIDDEN_REFERENCE)

    c.need(not any(blocked(n) for n in sys.modules), "Simulator already imported by reference")

    class Fence(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path, target=None):
            if blocked(fullname):
                raise ImportError("Forbidden in reference-only scoping: " + fullname)
            return None

    guard = Fence()
    sys.meta_path.insert(0, guard)
    try:
        yield
    finally:
        sys.meta_path.remove(guard)
        c.need(not any(blocked(n) for n in sys.modules), "Reference imported a simulator")


def implementation():
    sys.path.insert(0, str(ctx.HERE.parent / "pump_matched_pilot"))
    return importlib.import_module("pilot_reference")


def solve_to_disk(case, setting, plan, directory, write, solver):
    """Validate the serialized evidence, normalizing runtime scalar subclasses."""
    directory.mkdir(parents=True, exist_ok=False)
    path = directory / "result.json"
    write(path, solver.integrate(case, setting, plan))
    return c.read(path, None)


def fields(record, setting, duration, samples):
    c.need(
        record["setting"] == setting
        and len(record["times_s"]) == samples
        and len(record["states"]) == len(record["voltage_V"]) == samples,
        "Reference sample/setting coverage",
    )
    times = record["times_s"]
    c.need(
        times[0] == 0.0
        and times[-1] == duration
        and all(a < b for a, b in zip(times, times[1:], strict=False)),
        "Reference sample clock",
    )
    accepted = record["accepted_times_s"]
    c.need(
        len(accepted) == len(record["accepted_states"]) == len(record["accounting"])
        and len(accepted) >= 2
        and accepted[0] == 0.0
        and accepted[-1] == duration
        and all(a < b for a, b in zip(accepted, accepted[1:], strict=False)),
        "Accepted reference clock",
    )
    for group, width in (
        (record["states"], 59),
        (record["accepted_states"], 59),
        (record["voltage_V"], 7),
    ):
        c.need(
            all(
                len(row) == width and all(type(v) is float and math.isfinite(v) for v in row)
                for row in group
            ),
            "Reference state extent/finiteness",
        )


def summary(case, record, plan, equations):
    """Check all saved dense samples and accepted endpoints; no interval enclosure claim."""
    limits = plan["accounting"]
    lower_concentration = math.inf
    max_x = max_affinity = max_voltage = 0.0
    max_material = max_charge = max_energy = 0.0
    minimum_dissipation = math.inf
    checked = 0
    rt = equations.R * case["temperature_K"]
    for states, linked in (
        (record["states"], None),
        (record["accepted_states"], record["accounting"]),
    ):
        for index, state in enumerate(states):
            inside, outside, volts = equations.read_state(case, state)
            rates = equations.rhs(case, state, (1.0, 1.0))
            c.need(
                len(rates) == 59 and all(math.isfinite(v) for v in rates), "Reference finite rates"
            )
            balance = equations.accounting(case, state)
            if linked is not None:
                c.exact.Exact().match(balance, linked[index], "Accepted accounting link")
            c.need(
                balance["material_residual_fmol"] <= limits["cells_material_fmol"]
                and balance["charge_residual_C"] <= limits["cells_charge_C"]
                and balance["energy_residual_pJ"] <= limits["cells_energy_pJ"],
                "Reference sampled accounting",
            )
            max_material = max(max_material, balance["material_residual_fmol"])
            max_charge = max(max_charge, balance["charge_residual_C"])
            max_energy = max(max_energy, balance["energy_residual_pJ"])
            lower_concentration = min(
                lower_concentration, *(v for row in inside + [outside] for v in row)
            )
            minimum_dissipation = min(minimum_dissipation, *rates[52:])
            for i, v in enumerate(volts):
                max_voltage = max(max_voltage, abs(v))
                mu = [
                    rt * math.log(inside[i][s] / outside[s]) + case["valence"][s] * equations.F * v
                    for s in range(3)
                ]
                affinity = equations.chemistry(case, i) + math.fsum(
                    z * x for z, x in zip(case["pump_stoichiometry"], mu, strict=True)
                )
                max_affinity = max(max_affinity, abs(affinity / rt))
                max_x = max(max_x, *(abs(z * equations.F * v / rt) for z in case["valence"]))
            checked += 1
    c.need(
        lower_concentration > 0
        and max_x <= 50
        and max_affinity <= 80
        and minimum_dissipation >= -1e-14,
        "Reference sampled physical domain",
    )
    terminal = record["states"][-1]
    inside, outside, volts = equations.read_state(case, terminal)
    rates = equations.rhs(case, terminal, (1.0, 1.0))
    voltage_rates = [
        equations.F
        * 1e-15
        * math.fsum(case["valence"][s] * rates[3 * i + s] for s in range(3))
        / (case["area_m2"][i] * case["specific_capacitance_F_m2"][i])
        for i in range(7)
    ]
    return dict(
        checked_states_including_repeated_endpoints=checked,
        min_concentration_mM=lower_concentration,
        max_abs_voltage_V=max_voltage,
        max_abs_zFV_over_RT=max_x,
        max_abs_pump_affinity_over_RT=max_affinity,
        min_dissipation_rate_pJ_per_s=minimum_dissipation,
        max_material_residual_fmol=max_material,
        max_charge_residual_C=max_charge,
        max_energy_residual_pJ=max_energy,
        endpoint=dict(
            inside_mM=inside,
            outside_mM=outside,
            voltage_V=volts,
            net_inside_amount_rates_fmol_s=[rates[3 * i : 3 * i + 3] for i in range(7)],
            net_outside_amount_rates_fmol_s=rates[21:24],
            voltage_rates_V_s=voltage_rates,
        ),
        continuous_between_sample_domain_enclosure=False,
        steady_state_tested=False,
        biology_validated=False,
    )


def overlap(actual, original, plan, ledger_type):
    reference = plan["reference"]
    count = len(original["times_s"])
    c.need(
        count == 161 and actual["times_s"][:count] == original["times_s"], "Physical prefix clock"
    )
    ledger = ledger_type()
    for name, start, stop, limit in (
        ("amount", 0, 52, "agreement_amount_fmol"),
        ("energy", 52, 59, "agreement_energy_pJ"),
    ):
        ledger.compare(
            "prefix_" + name,
            [y[start:stop] for y in actual["states"][:count]],
            [y[start:stop] for y in original["states"]],
            reference[limit],
        )
    ledger.compare(
        "prefix_voltage",
        actual["voltage_V"][:count],
        original["voltage_V"],
        reference["agreement_voltage_V"],
    )
    return dict(
        compared_samples=count,
        comparisons=ledger.comparisons,
        maxima=ledger.maxima,
        adaptive_prefix_bitwise_required=False,
    )


def record_gate(scope, plan, records):
    labels = sorted(
        f"{v}/{s['id']}" for v in scope["variants"] for s in plan["reference"]["solves"]
    )
    c.need(
        sorted(records) == labels and len(records) == scope["reference_solves"],
        "Reference matrix coverage",
    )
    for label in labels:
        setting = next(s for s in plan["reference"]["solves"] if label.endswith("/" + s["id"]))
        row = records[label]
        fields(row, setting, scope["duration_s"], scope["reference_samples_per_solve"])
        c.need(
            row["times_s"] == [i * plan["reference"]["sample_dt_s"] for i in range(1600)] + [0.01],
            "Reference exact sampling grid",
        )
        c.need(
            row["stats"]["rhs_calls"] <= scope["reference_rhs_calls_per_solve"]
            and len(row["accepted_times_s"]) - 1 <= scope["reference_accepted_steps_per_solve"],
            "Reference per-solve work caps",
        )


def run(registration, output, write, budget):
    with model_fence():
        reference = implementation()
        c.need(ctx.runtime() == registration["runtime"], "Worker runtime changed")
        scope, plan, cases = registration["scope"], registration["protocol"], registration["cases"]
        originals = c.read(c.LEGACY / "reference.json", None)["records"]
        records, results = {}, {}
        for case in cases.values():
            for setting in plan["reference"]["solves"]:
                label = case["id"] + "/" + setting["id"]
                print("Reference " + label, flush=True)
                directory = c.child(output, "reference/" + label)
                row = solve_to_disk(case, setting, plan, directory, write, reference)
                budget(output)
                fields(row, setting, scope["duration_s"], scope["reference_samples_per_solve"])
                metrics = summary(case, row, plan, reference.equations)
                prefix = overlap(row, originals[label], plan, reference.Ledger)
                results[label] = dict(
                    path=str((directory / "result.json").relative_to(output)),
                    sha256=c.sha(directory / "result.json"),
                    metrics=metrics,
                    prefix=prefix,
                    stats=row["stats"],
                )
                records[label] = row
                budget(output)
        record_gate(scope, plan, records)
        agreement = reference.gate(plan, records)
        c.need(agreement["status"] == "independent_reference_gate_pass", "Reference agreement gate")
        return dict(
            status="reference_10ms_scope_pass_pending_independent_review",
            records=results,
            reference_solves=len(records),
            agreement=agreement,
            prefix_comparisons=sum(v["prefix"]["comparisons"] for v in results.values()),
            sampled_states_checked=sum(
                v["metrics"]["checked_states_including_repeated_endpoints"]
                for v in results.values()
            ),
            total_reference_rhs_calls=sum(v["stats"]["rhs_calls"] for v in results.values()),
            native_runs=0,
            cells_runs=0,
            native_ladder_qualified=False,
            matched_10ms_qualified=False,
            steady_state_qualified=False,
            biology_validated=False,
            production_changed=False,
            automatic_followup=False,
        )
