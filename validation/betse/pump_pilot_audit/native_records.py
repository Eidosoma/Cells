"""Independent live-law, lifecycle and conservation review of saved native rows."""

import math
from decimal import Decimal as D
from decimal import localcontext

import audit_evidence as context
import review as lifecycle

e = context.e


def identity(row, baseline, dt, duration, mode):
    dynamic = {"dt_s", "steps", "mode", "trace", "histories", "final", "final_arrays"}
    e.require(set(row) == set(baseline), "Native row membership")
    context.same_record(
        {k: v for k, v in row.items() if k not in dynamic},
        {k: v for k, v in baseline.items() if k not in dynamic},
        "Native preparation/settings changed",
    )
    e.require(
        row["mode"] == mode
        and row["dt_s"] == dt
        and row["steps"] == round(duration / dt)
        and (row["trace"] is None) == (mode == "unobserved"),
        "Native row clock/mode",
    )
    for record in (*row["histories"].values(), *row["final_arrays"].values()):
        e.array(record)
    for key, record in row["final_arrays"].items():
        e.require(
            context.diagnostic.bitwise_equal(record["values"], row["final"]["physical"][key]),
            "Native final array link",
        )


def exact_pair(row, quiet):
    context.same_record(
        {k: v for k, v in row.items() if k not in ("mode", "trace")},
        {k: v for k, v in quiet.items() if k not in ("mode", "trace")},
        "Observer interference",
    )


def material_budget(plan, inventory, completed):
    p = plan["accounting"]
    return (
        p["native_base_material_fmol"]
        + p["native_roundoff_multiplier"] * math.ulp(1.0) * completed * inventory
    )


class PhysicalLedger:
    """Apply the already-registered cumulative policy, never to live rate checks."""

    def __init__(self, ledger, budget):
        self.ledger, self.budget = ledger, budget

    def compare(self, name, actual, expected, atol, rtol=2e-11):
        if name == "global_material_fmol":
            atol, rtol = self.budget, 0.0
        self.ledger.compare(name, actual, expected, atol, rtol)


def live_laws(raw, before, row, variant, ledger):
    g, physical = row["geometry"], raw["before"]["physical"]
    calls = raw["calls"]
    pumps = [v for v in calls if v["function"] == "pumpNaKATP"]
    passive = [v for v in calls if v["function"] == "electroflux"]
    e.require(
        len(pumps) == int(variant["pump"])
        and [v["species_index"] for v in passive] == list(range(6))
        and len(calls) == 6 + len(pumps),
        "Live source call coverage",
    )
    density = [[0.0] * 30 for _ in range(6)]
    if pumps:
        e.require(calls[0] is pumps[0], "Pump order")
        args = pumps[0]["inputs"]
        for name, field, species in (
            ("cNai", "at_membrane_mM", 0),
            ("cNao", "outside_mM", 0),
            ("cKi", "at_membrane_mM", 1),
            ("cKo", "outside_mM", 1),
        ):
            e.require(args[name] == physical[field][species], "Live pump pool")
        e.require(
            args["Vm"] == physical["voltage_V"]
            and args["T"] == row["settings"]["temperature_K"]
            and args["block"] == 1.0,
            "Live pump voltage/control",
        )
        expected = lifecycle.pump_density(
            args, row["settings"]["pump_parameters"], row["settings"]["alpha_NaK"]
        )
        ledger.compare("raw_pump_density", pumps[0]["returned"], expected, 2e-18)
        e.require(
            before["reported_NaK_rate"] == pumps[0]["returned"][2], "Pump diagnostic identity"
        )
        for j in range(30):
            if variant["cluster_open"] or j not in g["boundary_faces"]:
                density[0][j], density[1][j] = (
                    variant["rho_pump"] * expected[s][j] for s in range(2)
                )
    else:
        e.require(all(v == 0 for v in before["reported_NaK_rate"]), "Inactive pump diagnostic")
    for s, call in enumerate(passive):
        args = call["inputs"]
        e.require(
            args["T"] == row["settings"]["temperature_K"]
            and args["rho"] == 1.0
            and args["Dc"] == row["metadata"]["ordinary_diffusivity_m2_per_s"][s]
            and args["d"] == [row["settings"]["thickness_m"]] * 30
            and args["zc"] == [lifecycle.Z[s]] * 30
            and args["cA"] == physical["outside_mM"][s]
            and args["cB"] == physical["at_membrane_mM"][s],
            "Live passive inputs",
        )
        ledger.compare("nonce_voltage_V", args["vBA"], physical["voltage_V"], 1e-22, 0.0)
        expected = lifecycle.passive_density(args)
        ledger.compare("raw_passive_density", call["returned"], expected, 2e-18)
        for j in range(30):
            if variant["cluster_open"] or j not in g["boundary_faces"]:
                density[s][j] += expected[j]
    ledger.compare(
        "independent_applied_density",
        before["physical"]["ordinary_density_mol_per_m2_s"],
        density,
        2e-18,
    )


def inspect(row, baseline, plan, variant, ledger, *, progress=None):
    trace, g = row["trace"], row["geometry"]
    count, dt = row["steps"], row["dt_s"]
    e.require(
        len(trace["steps"]) == len(trace["raw_steps"]) == len(trace["labels_s"]) == count
        and trace["pending"] is None
        and trace["inflight_calls"] == trace["gate_initializations"] == 0
        and trace["hook_restored"] is True
        and trace["status"] == baseline["trace"]["status"]
        and trace["calls"] == baseline["trace"]["calls"],
        "Native lifecycle",
    )
    e.require(trace["sampled_indices"] == list(range(1, count)), "Native sample coverage")
    history_fields = (
        ("cc_time", "inside_mM"),
        ("cc_env_time", "outside_mM"),
        ("vm_time", "voltage_V"),
        ("I_mem_time", "I_mem_A"),
        ("rho_cells_time", "rho_C_per_m3"),
        ("rate_NaKATP_time", None),
    )
    for hist, _ in history_fields:
        e.require(len(row["histories"][hist]["values"]) == count - 1, "Native history extent")
    ledger.compare(
        "raw_labels_s",
        trace["labels_s"],
        [i * plan["duration_s"] / (count - 1) for i in range(count)],
        1e-18,
        0.0,
    )
    initial = trace["initial"]["physical"]
    context.same_record(initial, baseline["trace"]["initial"]["physical"], "Native initial state")
    inventory = max(
        math.fsum(
            [initial["outside_mM"][s][0] * g["effective_bath_volume_m3"] * 1e15]
            + [
                v * c * 1e15
                for v, c in zip(g["cell_volumes_m3"], initial["inside_mM"][s], strict=True)
            ]
        )
        for s in range(6)
    )
    lifecycle.physical(
        trace["initial"],
        g,
        initial,
        PhysicalLedger(ledger, material_budget(plan, inventory, 0)),
        electrical=True,
    )
    cumulative = [[D(0)] * 3 for _ in range(7)]
    with localcontext() as dc:
        dc.prec = 70
        for index, (step, raw) in enumerate(zip(trace["steps"], trace["raw_steps"], strict=True)):
            e.require(
                step["index"] == raw["index"] == index
                and step["raw_label_s"] == trace["labels_s"][index]
                and step["order"] == ["before_ordinary", "after_ordinary", "after_voltage"]
                and step["before"] == step["before_ordinary"],
                "Native chronology",
            )
            before, after, end = (
                step[k] for k in ("before_ordinary", "after_ordinary", "after_voltage")
            )
            live_laws(raw, before, row, variant, ledger)
            budget = material_budget(plan, inventory, index + 1)
            for record in (before, after):
                lifecycle.physical(
                    record, g, initial, PhysicalLedger(ledger, budget), electrical=False
                )
            lifecycle.physical(end, g, initial, PhysicalLedger(ledger, budget), electrical=True)
            for face, owner in enumerate(g["membrane_owners"]):
                for species in range(3):
                    cumulative[owner][species] += (
                        D(before["physical"]["ordinary_density_mol_per_m2_s"][species][face])
                        * D(g["membrane_areas_m2"][face])
                        * D(dt)
                        * D("1e15")
                    )
            material = []
            global_amount = []
            for s in range(3):
                inside = [
                    (D(end["physical"]["inside_mM"][s][i]) - D(initial["inside_mM"][s][i]))
                    * D(g["cell_volumes_m3"][i])
                    * D("1e15")
                    for i in range(7)
                ]
                outside = (
                    (D(end["physical"]["outside_mM"][s][0]) - D(initial["outside_mM"][s][0]))
                    * D(g["effective_bath_volume_m3"])
                    * D("1e15")
                )
                material.extend(inside[i] - cumulative[i][s] for i in range(7))
                material.append(outside + sum(cumulative[i][s] for i in range(7)))
                global_amount.append(outside + sum(inside))
            ledger.compare(
                "cumulative_transfer_fmol", list(map(float, material)), [0.0] * 24, budget, 0.0
            )
            charge = (
                D(lifecycle.F)
                * D("1e-15")
                * sum(D(z) * v for z, v in zip((1, 1, -1), global_amount, strict=True))
            )
            ledger.compare(
                "global_charge_C", float(charge), 0.0, lifecycle.F * 1e-15 * 3 * budget, 0.0
            )
            # Compare every stored sample while its corresponding step is live.
            # The same canonical-value equality formerly compared six full lists,
            # forcing six complete trace decodes when steps are streamed.
            if index:
                for hist, field in history_fields:
                    context.same_record(
                        row["histories"][hist]["values"][index - 1],
                        end["physical"][field] if field else end["reported_NaK_rate"],
                        "Native history: " + hist,
                    )
            if progress is not None and ((index + 1) % 1000 == 0 or index + 1 == count):
                progress("physics_steps", completed=index + 1, total=count)
    context.same_record(row["final"], trace["steps"][-1]["after_voltage"], "Native final link")
    e.require(
        row["histories"]["time"]["values"] == trace["labels_s"][1:]
        and trace["storage"]
        == [dict(index=i, raw_label_s=trace["labels_s"][i]) for i in range(1, count)],
        "Native stored clock",
    )
    return dict(steps=count, physical_records=1 + 3 * count)
