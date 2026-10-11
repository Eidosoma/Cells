"""SPEC-008 bounded arithmetic/accounting checks; no time integration or production edit."""

import argparse
import copy
import hashlib
import json
import math
import platform
import sys
from dataclasses import asdict, fields, replace
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_voltage_gated_channel import Checks  # noqa: E402
from tests import reference_finite_extracellular as ref  # noqa: E402
from tests import reference_multispecies as ion  # noqa: E402
from tests import reference_physical_ionic_graph as graph  # noqa: E402

PROTOCOL = ROOT / "configs/reference/finite_extracellular_v1.json"
PROTOCOL_SHA = "5169c84abd14fe9d9963bd55bd6bb5b2614c8541031d1378367eba81b37b1e2a"
SPEC_SHA = "f8e3a4798c0d9fa7ba7c82478aaede0c15a3bc8abadccceca3ae9d369ce34af1"
RELEASE = ROOT / "runs/core-008-2026-09-10/release-audit.json"
RELEASE_SHA = "e03a211726888d3962825db544bba6742aa09603031d68ebbbc4745542393f08"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inherited_definition(case):
    old = ion.load_json(ROOT / "configs/reference/physical_ionic_graph_v1.json")
    return copy.deepcopy(
        next(c["definition"] for c in old["cases"] if c["id"] == case["source_case"])
    )


def definition(case):
    old = inherited_definition(case)
    return {
        "schema": ref.SCHEMA,
        "species": old["species"],
        "temperature_K": old["bath"]["temperature_K"],
        "extracellular": copy.deepcopy(case["extracellular"]),
        "cells": old["cells"],
        "junctions": old["junctions"],
    }


def d(value):
    """Exact binary64 input values, with independent exact SI defining constants."""
    return Decimal(value) if type(value) is int else Decimal.from_float(float(value))


F = Decimal("6.02214076e23") * Decimal("1.602176634e-19")
R = Decimal("6.02214076e23") * Decimal("1.380649e-23")
A = Decimal("1e-15")


def decimal_flux(z, ci, co, v, rt, area, permeability):
    x = z * F * v / rt
    numerator = co - ci if x == 0 else x * (co - ci * x.exp()) / (x.exp() - 1)
    return area * permeability / A * numerator


def decimal_rates(world, state, control):
    """Direct exponential interfaces, literal incidence and full-system energy."""
    rt = R * d(world.temperature_K)
    v = [
        d(m.initial_voltage_V)
        + A
        * F
        / (d(m.area_m2) * d(m.specific_capacitance_F_per_m2))
        * sum(
            z * (d(n) - d(n0))
            for z, n, n0 in zip(world.valence, row, c.initial_amount_fmol, strict=True)
        )
        for c, m, row in zip(world.cells, world.membranes, state.amount, strict=True)
    ]
    ci = [
        [d(n) / d(c.volume_pL) for n in row]
        for c, row in zip(world.cells, state.amount, strict=True)
    ]
    co = [d(n) / d(world.extracellular.volume_pL) for n in state.extracellular_amount]
    leak, cycle, local, dissipation, mus, supplied = [], [], [], [], [], []
    gates, hf = [None] * len(world.channels), [Decimal(0)] * len(world.channels)
    for i, m in enumerate(world.membranes):
        mu = [
            rt * (x / y).ln() + z * F * v[i]
            for z, x, y in zip(world.valence, ci[i], co, strict=True)
        ]
        passive = [
            decimal_flux(z, x, y, v[i], rt, d(m.area_m2), d(p) * d(u))
            for z, x, y, p, u in zip(
                world.valence, ci[i], co, m.permeability_m_per_s, control.leak[i], strict=True
            )
        ]
        p = m.pump
        nu = (0,) * len(co) if p is None else p.stoichiometry
        g = (
            Decimal(0)
            if p is None
            else d(p.drive_J_per_mol) + sum(x * y for x, y in zip(nu, mu, strict=True))
        )
        exponential = (-g / rt).exp()
        r = (
            Decimal(0)
            if p is None
            else d(p.capacity_fmol_per_s)
            * d(control.pump[i])
            * (exponential - 1)
            / (exponential + 1)
        )
        row = [j + x * r for j, x in zip(passive, nu, strict=True)]
        hpower = Decimal(0)
        for k, ch in enumerate(world.channels):
            if ch.membrane_id != m.id:
                continue
            mv = 1000 * v[i]
            targets = (
                1 / (1 + (-(mv + 6) / Decimal("6.4")).exp()),
                1 / (1 + ((mv + Decimal("25.3")) / Decimal("3.5")).exp()),
            )
            taus = (
                (Decimal("8.33") - Decimal("0.1163") * mv) / 1000,
                (1620 - Decimal("15.5") * mv) / 1000,
            )
            gates[k] = tuple(
                (t - d(q)) / tau
                for t, q, tau in zip(targets, state.membrane_gate[k], taus, strict=True)
            )
            s = world.species_ids.index(ch.species_id)
            effective = (
                d(ch.max_permeability_m_per_s)
                * d(ch.abundance)
                * d(control.channel[k])
                * d(state.membrane_gate[k][0])
                * d(state.membrane_gate[k][1])
            )
            hf[k] = decimal_flux(
                world.valence[s], ci[i][s], co[s], v[i], rt, d(m.area_m2), effective
            )
            row[s] += hf[k]
            hpower = -A * hf[k] * mu[s]
        leak.append(tuple(passive))
        cycle.append(r)
        local.append(row)
        mus.append(tuple(mu))
        dissipation.append(
            -A * (sum(x * y for x, y in zip(passive, mu, strict=True)) + r * g) + hpower
        )
        supplied.append(Decimal(0) if p is None else -A * d(p.drive_J_per_mol) * r)
    dn = copy.deepcopy(local)
    outside = tuple(-sum(row[s] for row in local) for s in range(len(co)))
    edges, eg, de = [], [], []
    for k, e in enumerate(world.junctions):
        src, dst = world.cell_ids.index(e.from_cell), world.cell_ids.index(e.to_cell)
        dv = v[src] - v[dst]
        flow = tuple(
            decimal_flux(
                z,
                ci[dst][s],
                ci[src][s],
                -dv,
                rt,
                d(e.area_m2),
                d(p) * d(control.junction[k]) * (d(r) + (1 - d(r)) * d(state.junction_gate[k])),
            )
            for s, (z, p, r) in enumerate(
                zip(world.valence, e.permeability_m_per_s, e.residual_fraction, strict=True)
            )
        )
        mu = tuple(
            rt * (ci[dst][s] / ci[src][s]).ln() - z * F * dv for s, z in enumerate(world.valence)
        )
        for s, j in enumerate(flow):
            dn[src][s] -= j
            dn[dst][s] += j
        target = 1 / (
            1
            + (d(e.sensitivity_per_V) * (-dv - d(e.half_voltage_V))).exp()
            + (d(e.sensitivity_per_V) * (dv - d(e.half_voltage_V))).exp()
        )
        edges.append(flow)
        eg.append((target - d(state.junction_gate[k])) / d(e.tau_s))
        de.append(-A * sum(j * u for j, u in zip(flow, mu, strict=True)))
    dv = tuple(
        A
        * F
        / (d(m.area_m2) * d(m.specific_capacitance_F_per_m2))
        * sum(z * j for z, j in zip(world.valence, row, strict=True))
        for m, row in zip(world.membranes, dn, strict=True)
    )
    chemical = (
        A
        * rt
        * sum(
            c.ln() * j
            for row, slope in zip((*ci, co), (*dn, outside), strict=True)
            for c, j in zip(row, slope, strict=True)
        )
    )
    electric = sum(
        d(m.area_m2) * d(m.specific_capacitance_F_per_m2) * x * y
        for m, x, y in zip(world.membranes, v, dv, strict=True)
    )

    def cast(values):
        return tuple(float(x) for x in values)

    def matrix(values):
        return tuple(cast(row) for row in values)

    rate = ref.State(
        matrix(dn),
        matrix(leak),
        cast(cycle),
        cast(x * Decimal("1e12") for x in dissipation),
        matrix(gates),
        cast(hf),
        cast(eg),
        matrix(edges),
        cast(x * Decimal("1e12") for x in de),
        cast(outside),
    )
    return ref.Instantaneous(
        rate,
        cast(v),
        cast(dv),
        cast(co),
        matrix(local),
        matrix(mus),
        cast(dissipation),
        cast(de),
        float(sum(supplied)),
        float(chemical + electric),
    )


def decimal_energy(world, state, displacement=Decimal(0), slope=None):
    rows = (*state.amount, state.extracellular_amount)
    rates = None if slope is None else (*slope.amount, slope.extracellular_amount)
    chemical = Decimal(0)
    for i, (c, row) in enumerate(zip((*world.cells, world.extracellular), rows, strict=True)):
        for s, n in enumerate(row):
            value = d(n) if rates is None else d(n) + displacement * d(rates[i][s])
            chemical += value * ((value / d(c.volume_pL)).ln() - 1)
    electric = Decimal(0)
    for i, (c, m, row) in enumerate(zip(world.cells, world.membranes, state.amount, strict=True)):
        delta_charge = sum(
            z * (d(n) - d(n0) + (Decimal(0) if rates is None else displacement * d(rates[i][s])))
            for s, (z, n, n0) in enumerate(
                zip(world.valence, row, c.initial_amount_fmol, strict=True)
            )
        )
        capacitance = d(m.area_m2) * d(m.specific_capacitance_F_per_m2)
        v = d(m.initial_voltage_V) + A * F / capacitance * delta_charge
        electric += capacitance * v * v / 2
    return A * R * d(world.temperature_K) * chemical + electric


def manufactured_history(world, scale):
    """Declared algebraic transfers, not an Euler step or simulated history."""
    state = ref.initial_state(world)
    leak = tuple(
        tuple(scale * (i + 1) * (s + 1) for s in range(len(world.species_ids)))
        for i in range(len(world.cells))
    )
    cycles = tuple(
        0.0 if m.pump is None else -scale * (i + 1) for i, m in enumerate(world.membranes)
    )
    channels = tuple(-scale * (k + 1) for k in range(len(world.channels)))
    edges = tuple(
        tuple(scale * (k + 1) * (s + 1) for s in range(len(world.species_ids)))
        for k in range(len(world.junctions))
    )
    local = [
        [
            leak[i][s] + (0.0 if m.pump is None else m.pump.stoichiometry[s] * cycles[i])
            for s in range(len(world.species_ids))
        ]
        for i, m in enumerate(world.membranes)
    ]
    for k, i in enumerate(world.channel_cells):
        local[i][world.species_ids.index(world.channels[k].species_id)] += channels[k]
    amounts = [
        [n + local[i][s] for s, n in enumerate(c.initial_amount_fmol)]
        for i, c in enumerate(world.cells)
    ]
    for k, (src, dst) in enumerate(world.endpoints):
        for s, j in enumerate(edges[k]):
            amounts[src][s] -= j
            amounts[dst][s] += j
    outside = tuple(
        n - math.fsum(row[s] for row in local)
        for s, n in enumerate(world.extracellular.initial_amount_fmol)
    )
    return replace(
        state,
        amount=tuple(tuple(row) for row in amounts),
        extracellular_amount=outside,
        leak_transferred=leak,
        pump_cycles=cycles,
        channel_transferred=channels,
        junction_transferred=edges,
    )


def coordinates(world, result):
    out = {}
    for field in fields(ref.State):
        name, values = field.name, getattr(result.rate, field.name)
        if name in ("amount", "leak_transferred"):
            for i, row in enumerate(values):
                for s, x in zip(world.species_ids, row, strict=True):
                    out[f"{name}/{world.cell_ids[i]}/{s}"] = (x, "flux_fmol_per_s")
        elif name == "extracellular_amount":
            for s, x in zip(world.species_ids, values, strict=True):
                out[f"{name}/{s}"] = (x, "flux_fmol_per_s")
        elif name == "junction_transferred":
            for edge, row in zip(world.junctions, values, strict=True):
                for s, x in zip(world.species_ids, row, strict=True):
                    out[f"{name}/{edge.id}/{s}"] = (x, "flux_fmol_per_s")
        elif name == "membrane_gate":
            for ch, row in zip(world.channels, values, strict=True):
                for gate, x in zip(("m", "h"), row, strict=True):
                    out[f"{name}/{ch.id}/{gate}"] = (x, "rate_per_s")
        else:
            owners = (
                world.junctions
                if name.startswith("junction_")
                else world.channels
                if name == "channel_transferred"
                else world.membranes
            )
            for owner, x in zip(owners, values, strict=True):
                if "dissipated" in name:
                    out[f"{name}/{owner.id}"] = (x * 1e-12, "power_W")
                else:
                    out[f"{name}/{owner.id}"] = (
                        x,
                        "rate_per_s" if name == "junction_gate" else "flux_fmol_per_s",
                    )
    for field, tolerance in (("voltage_V", "voltage_V"), ("voltage_rate_V_per_s", "rate_per_s")):
        for cell, x in zip(world.cells, getattr(result, field), strict=True):
            out[f"{field}/{cell.id}"] = (x, tolerance)
    for s, x in zip(world.species_ids, result.extracellular_concentration_mM, strict=True):
        out[f"outside_concentration/{s}"] = (x, "concentration_mM")
    for field in ("supplied_power_W", "stored_energy_rate_W"):
        out[field] = (getattr(result, field), "power_W")
    return out


def compare(checks, group, label, actual, expected, reverse=False):
    checks.require(group, label + "/keys", actual.keys() == expected.keys())
    for name, (x, tolerance) in actual.items():
        y = expected[name][0]
        if reverse and name.startswith("junction_transferred/"):
            y = -y
        checks.close(group, label + "/" + name, x, y, tolerance)


def composition_checks(panel, checks):
    assemblies = []
    for case in panel["cases"]:
        raw = definition(case)
        w = ref.resolve(raw)
        initial, enabled = ref.initial_state(w), graph.enabled(w)
        old = graph.resolve(inherited_definition(case))
        baseline = ref.evaluate(w)
        old_result = graph.evaluate(old)
        for f in fields(graph.State):

            def flat(value):
                return [x for row in value for x in (row if isinstance(row, tuple) else (row,))]

            for j, (x, y) in enumerate(
                zip(
                    flat(getattr(baseline.rate, f.name)),
                    flat(getattr(old_result.rate, f.name)),
                    strict=True,
                )
            ):
                tol = (
                    "power_W"
                    if "dissipated" in f.name
                    else "rate_per_s"
                    if "gate" in f.name
                    else "flux_fmol_per_s"
                )
                scale = 1e-12 if "dissipated" in f.name else 1
                checks.close(
                    "maintained_initial_reduction",
                    f"{case['id']}/{f.name}/{j}",
                    x * scale,
                    y * scale,
                    tol,
                )
        controls = [
            (
                str(u),
                graph.Control(
                    tuple(tuple(u for _ in row) for row in enabled.leak),
                    (u,) * len(w.cells),
                    (u,) * len(w.channels),
                    (u,) * len(w.junctions),
                ),
            )
            for u in panel["probes"]["availability"]
        ]
        controls += [
            ("internal_only", replace(controls[0][1], junction=enabled.junction)),
            ("membrane_only", replace(enabled, junction=(0.0,) * len(w.junctions))),
        ]
        controls += [
            (
                f"blocked_membrane_{i}",
                replace(
                    enabled,
                    leak=tuple(
                        (0.0,) * len(w.species_ids) if j == i else row
                        for j, row in enumerate(enabled.leak)
                    ),
                    pump=tuple(0.0 if j == i else u for j, u in enumerate(enabled.pump)),
                    channel=tuple(
                        0.0 if owner == i else u
                        for owner, u in zip(w.channel_cells, enabled.channel, strict=True)
                    ),
                ),
            )
            for i in range(len(w.cells))
        ]
        for label, control in controls:
            for gate in panel["probes"]["gate_states"]:
                state = replace(
                    initial,
                    membrane_gate=((gate, gate),) * len(w.channels),
                    junction_gate=(gate,) * len(w.junctions),
                )
                r = ref.evaluate(w, state, control)
                oracle = decimal_rates(w, state, control)
                key = f"{case['id']}/{label}/{gate}"
                compare(
                    checks, "decimal_complete_rates", key, coordinates(w, r), coordinates(w, oracle)
                )
                for s in range(len(w.species_ids)):
                    checks.close(
                        "closed_species_rate",
                        key + f"/{s}",
                        math.fsum(
                            (r.rate.extracellular_amount[s], *(row[s] for row in r.rate.amount))
                        ),
                        0.0,
                        "flux_fmol_per_s",
                    )
                    checks.require(
                        "outside_owns_only_membranes",
                        key + f"/{s}",
                        r.rate.extracellular_amount[s]
                        == -math.fsum(row[s] for row in r.membrane_rate_fmol_per_s),
                    )
                charged = ion.CHARGE_PER_FMOL * math.fsum(
                    z * j for z, j in zip(w.valence, r.rate.extracellular_amount, strict=True)
                )
                checks.close(
                    "opposite_capacitor_current",
                    key,
                    charged
                    + math.fsum(
                        m.capacitance_F * dv
                        for m, dv in zip(w.membranes, r.voltage_rate_V_per_s, strict=True)
                    ),
                    0.0,
                    "current_A",
                )
                dissipated = math.fsum((*r.membrane_dissipation_W, *r.junction_dissipation_W))
                checks.close(
                    "closed_energy_power",
                    key,
                    r.stored_energy_rate_W,
                    r.supplied_power_W - dissipated,
                    "power_W",
                )
                checks.require(
                    "nonnegative_dissipation",
                    key,
                    all(
                        x >= -panel["tolerances"]["negative_dissipation_W"]
                        for x in (*r.membrane_dissipation_W, *r.junction_dissipation_W)
                    ),
                )
                membranes_blocked = all(u == 0 for row in control.leak for u in row) and all(
                    u == 0 for u in (*control.pump, *control.channel)
                )
                if membranes_blocked:
                    checks.require(
                        "blocked_outside_exact_zero",
                        key,
                        all(x == 0.0 for x in r.rate.extracellular_amount),
                    )
                if membranes_blocked and all(u == 0 for u in control.junction):
                    on = ref.evaluate(w, state, enabled)
                    checks.require(
                        "blocked_gates_keep_relaxing",
                        key,
                        r.rate.membrane_gate == on.rate.membrane_gate
                        and r.rate.junction_gate == on.rate.junction_gate,
                    )
        state = manufactured_history(w, panel["probes"]["ledger_scale_fmol"])
        residual = ref.ledger_residuals(w, state)
        for name in ("inside_material_fmol", "outside_material_fmol", "global_material_fmol"):
            values = residual[name]
            flat = [x for row in values for x in (row if isinstance(row, tuple) else (row,))]
            for j, x in enumerate(flat):
                checks.close(
                    "manufactured_material", f"{case['id']}/{name}/{j}", x, 0, "material_fmol"
                )
        for name in ("countercharge_increment_C", "absolute_countercharge_C"):
            checks.close(
                "manufactured_countercharge", f"{case['id']}/{name}", residual[name], 0, "charge_C"
            )
        energy = float(decimal_energy(w, state) - decimal_energy(w, initial))
        checks.close(
            "finite_energy_difference",
            case["id"],
            ref.energy_change_J(w, state),
            energy,
            "energy_J",
        )
        nonzero = replace(
            state,
            membrane_dissipated_energy_pJ=(1e-6,) * len(w.cells),
            junction_dissipated_energy_pJ=(2e-6,) * len(w.junctions),
        )
        work = 1e-15 * math.fsum(
            m.pump.drive_J_per_mol * p
            for m, p in zip(w.membranes, state.pump_cycles, strict=True)
            if m.pump is not None
        )
        expected_residual = energy + 1e-12 * (len(w.cells) * 1e-6 + len(w.junctions) * 2e-6) + work
        checks.close(
            "finite_energy_history_formula",
            case["id"],
            ref.ledger_residuals(w, nonzero)["energy_residual_J"],
            expected_residual,
            "energy_J",
        )
        shifted = ref.evaluate(w, state)
        compare(
            checks,
            "nonzero_state_decimal_rates",
            case["id"],
            coordinates(w, shifted),
            coordinates(w, decimal_rates(w, state, enabled)),
        )
        epsilon = d(panel["probes"]["directional_probe_s"])
        derivative = float(
            (
                decimal_energy(w, state, epsilon, shifted.rate)
                - decimal_energy(w, state, -epsilon, shifted.rate)
            )
            / (2 * epsilon)
        )
        checks.close(
            "energy_directional_derivative",
            case["id"],
            shifted.stored_energy_rate_W,
            derivative,
            "power_W",
        )
        for mode in ("cell_order", "species_order", "edge_order", "edge_orientation"):
            permuted = copy.deepcopy(raw)
            if mode == "cell_order":
                permuted["cells"].reverse()
            elif mode == "species_order":
                permuted["species"].reverse()
            elif mode == "edge_order":
                permuted["junctions"].reverse()
            else:
                for e in permuted["junctions"]:
                    e["from_cell"], e["to_cell"] = e["to_cell"], e["from_cell"]
            other = ref.resolve(permuted)
            compare(
                checks,
                mode,
                case["id"],
                coordinates(other, ref.evaluate(other)),
                coordinates(w, baseline),
                mode == "edge_orientation",
            )
        assemblies.append(
            {
                "id": case["id"],
                "definition": raw,
                "initial": asdict(baseline),
                "manufactured_residuals": residual,
                "initial_countercharge_C": w.initial_countercharge_C,
            }
        )
    return assemblies


def volume_limit(panel, checks):
    results = []
    transfer = panel["probes"]["volume_limit_transfer_fmol"]
    by_id = {c["id"]: c for c in panel["cases"]}
    for name in panel["probes"]["volume_limit_cases"]:
        case = by_id[name]
        w = ref.resolve(definition(case))
        initial = ref.initial_state(w)
        row = list(initial.amount[0])
        out = list(initial.extracellular_amount)
        row[0] += transfer
        out[0] -= transfer
        state = replace(
            initial,
            amount=(tuple(row),),
            extracellular_amount=tuple(out),
            leak_transferred=((transfer, 0.0, 0.0),),
        )
        r = ref.evaluate(w, state)
        old = graph.resolve(inherited_definition(case))
        old_state = graph.State(**{f.name: getattr(state, f.name) for f in fields(graph.State)})
        clamped = graph.evaluate(old, old_state)
        co0 = initial.extracellular_amount[0] / w.extracellular.volume_pL
        observed = r.extracellular_concentration_mM[0] - co0
        checks.close(
            "inverse_volume_response",
            name,
            observed,
            -transfer / w.extracellular.volume_pL,
            "concentration_mM",
        )
        error = max(
            abs(x - y)
            for row1, row2 in zip(r.rate.amount, clamped.rate.amount, strict=True)
            for x, y in zip(row1, row2, strict=True)
        )
        results.append(
            {
                "id": name,
                "volume_pL": w.extracellular.volume_pL,
                "concentration_change_mM": observed,
                "maximum_intracellular_rate_difference_fmol_per_s": error,
            }
        )
    for a, b in zip(results[:-1], results[1:], strict=True):
        checks.require(
            "maintained_limit_monotone_probe",
            b["id"],
            0
            < b["maximum_intracellular_rate_difference_fmol_per_s"]
            < a["maximum_intracellular_rate_difference_fmol_per_s"],
        )
    return results


def verify():
    if sha(PROTOCOL) != PROTOCOL_SHA or sha(ROOT / "docs/FINITE_EXTRACELLULAR_SPEC.md") != SPEC_SHA:
        raise ValueError("Frozen SPEC-008 inputs changed; version any scientific revision")
    if sha(RELEASE) != RELEASE_SHA:
        raise ValueError("Accepted production release changed")
    panel = ion.load_json(PROTOCOL)
    for name, value in panel["inherited_sources_sha256"].items():
        if sha(ROOT / name) != value:
            raise ValueError(f"Inherited source changed: {name}")
    release = ion.load_json(RELEASE)
    production = {
        str(p.relative_to(ROOT / "src/cells")): sha(p)
        for p in sorted((ROOT / "src/cells").rglob("*.py"))
    }
    if production != release["source_hashes"]:
        raise ValueError("SPEC-008 must leave production unchanged")
    for name, value in release["implementation_files_sha256"].items():
        if sha(ROOT / name) != value:
            raise ValueError(f"Accepted implementation dependency changed: {name}")
    checks = Checks(panel["tolerances"])
    with localcontext() as context:
        context.prec = panel["probes"]["decimal_precision"]
        assemblies = composition_checks(panel, checks)
        limit = volume_limit(panel, checks)
    sources = set(panel["inherited_sources_sha256"]) | {
        "configs/reference/finite_extracellular_v1.json",
        "docs/FINITE_EXTRACELLULAR_SPEC.md",
        "tests/reference_finite_extracellular.py",
        "scripts/check_finite_extracellular.py",
        "tests/unit/test_finite_extracellular_reference.py",
        "pyproject.toml",
        "requirements-lock.txt",
        "requirements-reference.txt",
    }
    return {
        "status": "fail" if checks.failures else "pass",
        "scope": panel["scope"],
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "protocol_sha256": PROTOCOL_SHA,
        "spec_sha256": SPEC_SHA,
        "production_release_sha256": RELEASE_SHA,
        "production_version": "0.13.0",
        "production_source_sha256": production,
        "source_sha256": {n: sha(ROOT / n) for n in sorted(sources)},
        "checks": sum(g["checks"] for g in checks.groups.values()),
        "checks_failed": len(checks.failures),
        "groups": checks.groups,
        "failures": checks.failures,
        "tolerances": panel["tolerances"],
        "assemblies": assemblies,
        "volume_limit": limit,
        "coupled_trajectory_qualification": "not_performed",
        "method_selection": "not_performed",
        "production_change": False,
        "independent_ode_solver_run": False,
        "gpu_qualification": "not_performed",
        "biological_acceptance": "not_assessable",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New receipt; refuse to overwrite evidence")
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        raise FileExistsError("Choose a new receipt path")
    result = verify()
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is not None:
        with args.output.open("x") as handle:
            handle.write(payload)
    print(payload, end="")
    return int(result["status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
