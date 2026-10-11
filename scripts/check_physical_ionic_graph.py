"""SPEC-007 bounded instantaneous checks; no graph integration or production edits."""

import argparse
import copy
import hashlib
import itertools
import json
import math
import platform
import sys
from dataclasses import asdict, replace
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_voltage_gated_channel import Checks  # noqa: E402
from tests import reference_bioelectric_pair as pair  # noqa: E402
from tests import reference_multispecies as ionic  # noqa: E402
from tests import reference_physical_ionic_graph as ref  # noqa: E402
from tests import reference_voltage_gated_channel as channel  # noqa: E402

PROTOCOL = ROOT / "configs/reference/physical_ionic_graph_v1.json"
FROZEN_PROTOCOL_SHA256 = "6b6e5431e475e6467428f78d99a1b8756c71cac160498b393aff16d7e17dfc7f"
SPEC_SHA256 = "04feb84040e18af82e12ca21894e38051ef7bec9f0da214379856274ff54e91f"
RELEASE = ROOT / "runs/core-007-2026-09-10/release-audit.json"
RELEASE_SHA256 = "2a08a2487aafd13cb1e604063e9ff3b68bd5a75cc7c09fe4dea480f952b05085"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decimal_transfer(z, ca, cb, dv, temperature, area, permeability, gate, residual, control):
    """Direct high-precision numerator, not the composed Bernoulli implementation."""

    def d(x):
        return Decimal(str(x))

    f = Decimal("6.02214076e23") * Decimal("1.602176634e-19")
    r = Decimal("6.02214076e23") * Decimal("1.380649e-23")
    x = z * f * d(dv) / (r * d(temperature))
    drive = d(ca) - d(cb) if x == 0 else x * (d(ca) * x.exp() - d(cb)) / (x.exp() - 1)
    return (
        d(area)
        * d(permeability)
        * d(control)
        * (d(residual) + (1 - d(residual)) * d(gate))
        * drive
        / Decimal("1e-15")
    )


def transport_checks(panel, checks):
    probes = panel["probes"]
    common = (298.15, probes["area_m2"], probes["permeability_m_per_s"])
    ca, residual = probes["source_concentration_mM"], probes["residual_fraction"]
    grid = itertools.product(
        probes["valences"],
        probes["concentration_ratios"],
        probes["voltage_differences_V"],
        probes["gate_states"],
        probes["controls"],
    )
    for z, ratio, dv, gate, control in grid:
        cb = ca * ratio
        args = (z, ca, cb, dv, *common, gate, residual, control)
        flow = ref.transfer(*args)
        expected = float(decimal_transfer(*args))
        label = f"{z}/{ratio}/{dv}/{gate}/{control}"
        checks.close("decimal_edge_flux", label, flow, expected, "flux_fmol_per_s")
        reverse = ref.transfer(z, cb, ca, -dv, *common, gate, residual, control)
        checks.close("edge_reversal", label, reverse, -flow, "flux_fmol_per_s")
        mu = ionic.R * common[0] * math.log(cb / ca) - z * ionic.F * dv
        checks.require(
            "passive_direction",
            label,
            -ionic.MOL_PER_FMOL * flow * mu >= -panel["tolerances"]["negative_dissipation_W"],
        )
        if control == 0:
            checks.require("disabled_edge_exact_zero", label, flow == 0.0)
        if dv == 0:
            expected = (
                common[1]
                * common[2]
                / ionic.MOL_PER_FMOL
                * control
                * (residual + (1 - residual) * gate)
                * (ca - cb)
            )
            checks.close("zero_voltage_diffusion", label, flow, expected, "flux_fmol_per_s")
    for z, ratio in itertools.product(probes["valences"], probes["concentration_ratios"]):
        cb = ca * ratio
        dv = ionic.R * common[0] * math.log(ratio) / (z * ionic.F)
        checks.close(
            "individual_nernst_balance",
            f"{z}/{ratio}",
            ref.transfer(z, ca, cb, dv, *common, 0.25, residual, 1.0),
            0.0,
            "flux_fmol_per_s",
        )
    edge = ref.resolve(
        next(c["definition"] for c in panel["cases"] if c["id"] == "pair_mono")
    ).junctions[0]
    for dv, gate in itertools.product(probes["voltage_differences_V"], probes["gate_states"]):
        d = Decimal(str(dv))
        a = Decimal(str(edge.sensitivity_per_V))
        v = Decimal(str(edge.half_voltage_V))
        target = 1 / (1 + (a * (-d - v)).exp() + (a * (d - v)).exp())
        label = f"{dv}/{gate}"
        checks.close("junction_gate_decimal", label, edge.target(dv), float(target), "gate")
        checks.close(
            "junction_gate_decimal",
            label + "/rate",
            edge.gate_rate(dv, gate),
            float((target - Decimal(str(gate))) / Decimal(str(edge.tau_s))),
            "rate_per_s",
        )
        checks.require("junction_gate_symmetry", label, edge.target(dv) == edge.target(-dv))
        checks.require(
            "junction_gate_inward",
            label,
            (gate != 0 or edge.gate_rate(dv, gate) >= 0)
            and (gate != 1 or edge.gate_rate(dv, gate) <= 0),
        )


def local_reference(graph, state, control):
    """Independent local calls for reduction checks, without graph contributions."""
    by_cell = {i: k for k, i in enumerate(graph.channel_cells)}
    rates, powers = [], []
    for i, p in enumerate(graph.cells):
        if i in by_cell:
            k = by_cell[i]
            r = channel.evaluate(
                graph.channels[k],
                state.amount[i],
                channel.Gate(*state.membrane_gate[k]),
                leak_control=control.leak[i],
                pump_control=control.pump[i],
                availability=control.channel[k],
            )
            rates.append(r.amount_rate_fmol_per_s)
            powers.append(r.stored_ionic_capacitor_energy_rate_W)
        else:
            r = ionic.evaluate(
                p, state.amount[i], leak_control=control.leak[i], pump_control=control.pump[i]
            )
            rates.append(r.amount_rate_fmol_per_s)
            powers.append(r.stored_energy_rate_W)
    return tuple(rates), tuple(powers)


def coordinates(graph, result):
    """ID-labelled rate/readout map, deliberately distinct from reference storage."""
    data = {}
    for field in ("amount", "leak_transferred"):
        for cell, row in zip(graph.cell_ids, getattr(result.rate, field), strict=True):
            for species, value in zip(graph.species_ids, row, strict=True):
                data[f"{field}/{cell}/{species}"] = (value, "flux_fmol_per_s")
    for field, tol in (
        ("pump_cycles", "flux_fmol_per_s"),
        ("membrane_dissipated_energy_pJ", "energy_pJ"),
    ):
        for cell, value in zip(graph.cell_ids, getattr(result.rate, field), strict=True):
            data[f"{field}/{cell}"] = (value, tol)
    for k, c in enumerate(graph.channels):
        for g, value in zip(("m", "h"), result.rate.membrane_gate[k], strict=True):
            data[f"membrane_gate/{c.channel.id}/{g}"] = (value, "rate_per_s")
        data[f"channel_transferred/{c.channel.id}"] = (
            result.rate.channel_transferred[k],
            "flux_fmol_per_s",
        )
    for k, e in enumerate(graph.junctions):
        for species, value in zip(
            graph.species_ids, result.rate.junction_transferred[k], strict=True
        ):
            data[f"junction_transferred/{e.id}/{species}"] = (value, "flux_fmol_per_s")
        data[f"junction_gate/{e.id}"] = (result.rate.junction_gate[k], "rate_per_s")
        data[f"junction_dissipated_energy_pJ/{e.id}"] = (
            result.rate.junction_dissipated_energy_pJ[k],
            "energy_pJ",
        )
        data[f"junction_current/{e.id}"] = (result.junction_current_A[k], "current_A")
    for cell, value, rate in zip(
        graph.cell_ids, result.voltage_V, result.voltage_rate_V_per_s, strict=True
    ):
        data[f"voltage/{cell}"] = (value, "charge_V")
        data[f"voltage_rate/{cell}"] = (rate, "voltage_rate_V_per_s")
    data["energy_rate"] = (result.stored_energy_rate_W, "power_W")
    return data


def compare_maps(checks, group, label, actual, expected, *, reverse=False):
    checks.require(group, label + "/coordinate_identity", set(actual) == set(expected))
    for key, (value, tol) in actual.items():
        wanted = expected[key][0]
        if reverse and key.startswith(("junction_transferred/", "junction_current/")):
            wanted = -wanted
        checks.close(group, label + "/" + key, value, wanted, tol)


def manufactured_history(graph, scale):
    """Algebraic nonzero ledgers, not the output of any numerical time step."""
    state = ref.initial_state(graph)
    leak = tuple(
        tuple(scale * (s + 1) * (-1 if i % 2 else 1) for s in range(len(graph.species_ids)))
        for i in range(len(graph.cells))
    )
    pump = tuple(
        scale * (i + 1) if p.pump_id is not None else 0.0 for i, p in enumerate(graph.cells)
    )
    channels = tuple(-scale * (k + 1) for k in range(len(graph.channels)))
    edges = tuple(
        tuple(scale * (k + 1) * (s + 1) for s in range(len(graph.species_ids)))
        for k in range(len(graph.junctions))
    )
    values = [
        [n + leak[i][s] + p.stoichiometry[s] * pump[i] for s, n in enumerate(p.initial_amount_fmol)]
        for i, p in enumerate(graph.cells)
    ]
    for k, c in enumerate(graph.channels):
        values[graph.cell_ids.index(c.assembly.cell_id)][c.species_index] += channels[k]
    for i, cell in enumerate(graph.cell_ids):
        for s in range(len(graph.species_ids)):
            values[i][s] += math.fsum(
                (int(e.to_cell == cell) - int(e.from_cell == cell)) * edges[k][s]
                for k, e in enumerate(graph.junctions)
            )
    return replace(
        state,
        amount=tuple(tuple(row) for row in values),
        leak_transferred=leak,
        pump_cycles=pump,
        channel_transferred=channels,
        junction_transferred=edges,
    )


def composition_checks(panel, checks):
    results = []
    for case in panel["cases"]:
        name, definition = case["id"], case["definition"]
        graph = ref.resolve(definition)
        state = ref.initial_state(graph)
        on = ref.enabled(graph)
        isolated = replace(on, junction=(0.0,) * len(graph.junctions))
        internal = replace(
            on,
            leak=tuple(tuple(0.0 for _ in row) for row in on.leak),
            pump=(0.0,) * len(graph.cells),
            channel=(0.0,) * len(graph.channels),
        )
        off = replace(internal, junction=isolated.junction)
        variants = [("all", on), ("local", isolated), ("internal", internal), ("off", off)]
        variants.extend(
            (
                f"blocked_edge_{k}",
                replace(
                    on, junction=tuple(0.0 if i == k else 1.0 for i in range(len(graph.junctions)))
                ),
            )
            for k in range(len(graph.junctions))
        )
        nominal = ref.evaluate(graph, state, on)
        for label, control in variants:
            label = name + "/" + label
            result = ref.evaluate(graph, state, control)
            local, local_power = local_reference(graph, state, control)
            for i, cell in enumerate(graph.cell_ids):
                for s, species in enumerate(graph.species_ids):
                    incidence = math.fsum(
                        (int(e.to_cell == cell) - int(e.from_cell == cell))
                        * result.rate.junction_transferred[k][s]
                        for k, e in enumerate(graph.junctions)
                    )
                    checks.close(
                        "incidence_composition",
                        label + f"/{cell}/{species}",
                        result.rate.amount[i][s],
                        local[i][s] + incidence,
                        "flux_fmol_per_s",
                    )
                    checks.require(
                        "bath_excludes_internal",
                        label + f"/{cell}/{species}",
                        result.bath_rate_fmol_per_s[i][s] == -local[i][s],
                    )
            for s, species in enumerate(graph.species_ids):
                residual = math.fsum(row[s] for row in result.rate.amount) + math.fsum(
                    row[s] for row in result.bath_rate_fmol_per_s
                )
                checks.close(
                    "global_species_balance",
                    label + "/" + species,
                    residual,
                    0.0,
                    "flux_fmol_per_s",
                )
            weighted = math.fsum(
                p.capacitance_F * dv
                for p, dv in zip(graph.cells, result.voltage_rate_V_per_s, strict=True)
            )
            external = ionic.CHARGE_PER_FMOL * math.fsum(
                z * row[s] for row in local for s, z in enumerate(graph.valence)
            )
            checks.close("capacitance_weighted_charge", label, weighted, external, "current_A")
            checks.close(
                "graph_power_balance",
                label,
                result.stored_energy_rate_W,
                result.supplied_power_W
                - math.fsum((*result.membrane_dissipation_W, *result.junction_dissipation_W)),
                "power_W",
            )
            checks.close(
                "local_plus_edge_power",
                label,
                result.stored_energy_rate_W,
                math.fsum(local_power) - math.fsum(result.junction_dissipation_W),
                "power_W",
            )
            checks.require(
                "gate_control_separation",
                label,
                result.rate.membrane_gate == nominal.rate.membrane_gate
                and result.rate.junction_gate == nominal.rate.junction_gate,
            )
            for k, (edge, (a, b)) in enumerate(zip(graph.junctions, graph.endpoints, strict=True)):
                dv = result.voltage_V[a] - result.voltage_V[b]
                powers = []
                for s, z in enumerate(graph.valence):
                    ca, cb = (
                        state.amount[a][s] / graph.cells[a].volume_pL,
                        state.amount[b][s] / graph.cells[b].volume_pL,
                    )
                    expected = float(
                        decimal_transfer(
                            z,
                            ca,
                            cb,
                            dv,
                            graph.cells[0].temperature_K,
                            edge.area_m2,
                            edge.permeability_m_per_s[s],
                            state.junction_gate[k],
                            edge.residual_fraction[s],
                            control.junction[k],
                        )
                    )
                    checks.close(
                        "assembled_decimal_edge",
                        label + f"/{edge.id}/{s}",
                        result.rate.junction_transferred[k][s],
                        expected,
                        "flux_fmol_per_s",
                    )
                    mu = (
                        ionic.R * graph.cells[0].temperature_K * math.log(cb / ca)
                        - z * ionic.F * dv
                    )
                    powers.append(-ionic.MOL_PER_FMOL * expected * mu)
                checks.close(
                    "edge_owned_dissipation",
                    label + "/" + edge.id,
                    result.junction_dissipation_W[k],
                    math.fsum(powers),
                    "power_W",
                )
                checks.require(
                    "edge_owned_dissipation",
                    label + "/nonnegative/" + edge.id,
                    result.junction_dissipation_W[k]
                    >= -panel["tolerances"]["negative_dissipation_W"],
                )
                if control.junction[k] == 0:
                    checks.require(
                        "blocked_edge_no_transfer",
                        label + "/" + edge.id,
                        all(v == 0.0 for v in result.rate.junction_transferred[k])
                        and result.junction_dissipation_W[k] == 0.0,
                    )
            if not graph.junctions or all(u == 0 for u in control.junction):
                checks.require("disconnected_local_reduction", label, result.rate.amount == local)
        expected = coordinates(graph, nominal)
        for order in itertools.permutations(definition["cells"]):
            raw = copy.deepcopy(definition)
            raw["cells"] = list(order)
            permuted = ref.resolve(raw)
            compare_maps(
                checks,
                "cell_permutation",
                name,
                coordinates(permuted, ref.evaluate(permuted)),
                expected,
            )
        for order in itertools.permutations(definition["species"]):
            raw = copy.deepcopy(definition)
            raw["species"] = list(order)
            permuted = ref.resolve(raw)
            compare_maps(
                checks,
                "species_permutation",
                name,
                coordinates(permuted, ref.evaluate(permuted)),
                expected,
            )
        reversed_edges = copy.deepcopy(definition)
        reversed_edges["junctions"].reverse()
        permuted = ref.resolve(reversed_edges)
        compare_maps(
            checks,
            "edge_permutation",
            name,
            coordinates(permuted, ref.evaluate(permuted)),
            expected,
        )
        for edge in reversed_edges["junctions"]:
            edge["from_cell"], edge["to_cell"] = edge["to_cell"], edge["from_cell"]
        reversed_graph = ref.resolve(reversed_edges)
        compare_maps(
            checks,
            "graph_orientation",
            name,
            coordinates(reversed_graph, ref.evaluate(reversed_graph)),
            expected,
            reverse=True,
        )
        history = manufactured_history(graph, panel["probes"]["ledger_scale_fmol"])
        balance = ref.ledger_residuals(graph, history)
        for row in balance["material_fmol"]:
            for value in row:
                checks.close("nonzero_history_material", name, value, 0.0, "material_fmol")
        for value in balance["charge_V"]:
            checks.close("nonzero_history_charge", name, value, 0.0, "charge_V")
        for value in balance["global_material_fmol"]:
            checks.close("nonzero_history_global", name, value, 0.0, "material_fmol")
        forgotten = replace(
            history,
            leak_transferred=state.leak_transferred,
            pump_cycles=state.pump_cycles,
            channel_transferred=state.channel_transferred,
            junction_transferred=state.junction_transferred,
        )
        checks.require(
            "history_cannot_be_reset",
            name,
            max(
                abs(v)
                for row in ref.ledger_residuals(graph, forgotten)["material_fmol"]
                for v in row
            )
            > panel["tolerances"]["material_fmol"],
        )
        unchanged = ref.evaluate(graph, replace(history, amount=state.amount))
        checks.require("history_not_extra_material", name, unchanged.rate == nominal.rate)
        results.append(
            {
                "id": name,
                "cell_count": len(graph.cells),
                "channel_count": len(graph.channels),
                "junction_count": len(graph.junctions),
                "nominal": asdict(nominal),
                "manufactured_history_residuals": balance,
            }
        )
    return results


def structural_witnesses(panel, checks):
    cases = {c["id"]: c["definition"] for c in panel["cases"]}
    graph = ref.resolve(cases["pair_mono"])
    control = ref.enabled(graph)
    internal = replace(
        control,
        leak=tuple((0.0,) * len(graph.species_ids) for _ in graph.cells),
        pump=(0.0,) * len(graph.cells),
        channel=(0.0,) * len(graph.channels),
    )
    result = ref.evaluate(graph, control=internal)
    unweighted = math.fsum(result.voltage_rate_V_per_s)
    checks.require("unequal_capacitance_not_voltage_sum", "pair", abs(unweighted) > 1e-8)
    # The star recipient has exactly one local membrane, regardless of degree.
    star = ref.resolve(cases["star_mono"])
    state = ref.initial_state(star)
    on = ref.enabled(star)
    complete = ref.evaluate(star)
    local, _ = local_reference(star, state, on)
    recipient = star.cell_ids.index("cell_2")
    checks.require(
        "shared_recipient_not_duplicated",
        "nonzero membrane witness",
        any(abs(v) > 1e-8 for v in local[recipient]),
    )
    checks.require(
        "shared_recipient_not_duplicated",
        "complete RHS differs from two whole recipients",
        any(
            abs(
                complete.rate.amount[recipient][s]
                - (
                    2 * local[recipient][s]
                    + sum(row[s] for row in complete.rate.junction_transferred)
                )
            )
            > 1e-8
            for s in range(len(star.species_ids))
        ),
    )
    cycle = ref.resolve(cases["cycle_mono"])
    initial = ref.initial_state(cycle)
    circulation = replace(
        initial,
        junction_transferred=tuple(
            tuple(
                panel["probes"]["ledger_scale_fmol"] * (s + 1)
                for s in range(len(cycle.species_ids))
            )
            for _ in cycle.junctions
        ),
    )
    residual = ref.ledger_residuals(cycle, circulation)
    checks.require(
        "cycle_history_witness",
        "zero node increment with nonzero edge history",
        circulation != initial
        and all(value == 0.0 for row in residual["internal_transfer_fmol"] for value in row)
        and all(value == 0.0 for row in residual["material_fmol"] for value in row),
    )
    checks.require(
        "cycle_history_witness",
        "same future derivative, distinct recorded history",
        ref.evaluate(cycle, circulation) == ref.evaluate(cycle, initial),
    )
    return {
        "unequal_pair_unweighted_voltage_rate_V_per_s": unweighted,
        "star_recipient_local_rate_fmol_per_s": local[recipient],
        "cycle_history": "algebraic circulation only; no trajectory or memory claim",
    }


def old_pair_reduction(panel, checks):
    raw = copy.deepcopy(next(c["definition"] for c in panel["cases"] if c["id"] == "pair_mono"))
    for c in raw["cells"]:
        c["channel"] = None
    graph = ref.resolve(raw)
    old_cells = tuple(
        pair.cell.Parameters(
            volume_pL=p.volume_pL,
            area_m2=p.area_m2,
            specific_capacitance_F_per_m2=p.specific_capacitance_F_per_m2,
            temperature_K=p.temperature_K,
            initial_mM=tuple(n / p.volume_pL for n in p.initial_amount_fmol),
            bath_mM=p.bath_mM,
            permeability_m_per_s=p.permeability_m_per_s,
            initial_voltage_V=p.initial_voltage_V,
            pump_capacity_fmol_per_s=p.capacity_fmol_per_s,
            atp_free_energy_J_per_mol=p.drive_J_per_mol,
        )
        for p in graph.cells
    )
    edge = graph.junctions[0]
    old = pair.Parameters(
        old_cells,
        pair.Junction(
            area_m2=edge.area_m2,
            permeability_m_per_s=edge.permeability_m_per_s,
            residual=edge.residual_fraction,
            sensitivity_per_V=edge.sensitivity_per_V,
            half_voltage_V=edge.half_voltage_V,
            tau_s=edge.tau_s,
            initial_gate=edge.initial_gate,
        ),
    )
    for u, gate in itertools.product(panel["probes"]["controls"], panel["probes"]["gate_states"]):
        state = replace(ref.initial_state(graph), junction_gate=(gate,))
        result = ref.evaluate(graph, state, replace(ref.enabled(graph), junction=(u,)))
        leak, cycles, flow, slope, dissipation = pair.rates(
            old, old.initial_amount, old.initial_voltage, gate, pair.Control(contact=u)
        )
        label = f"{u}/{gate}"
        for i in range(2):
            checks.close(
                "old_hyperbolic_pair_reduction",
                label + "/pump",
                result.rate.pump_cycles[i],
                float(cycles[i]),
                "flux_fmol_per_s",
            )
            for s in range(len(graph.valence)):
                expected = float(
                    leak[s, i] + pair.NU[s] * cycles[i] + (-1 if i == 0 else 1) * flow[s]
                )
                checks.close(
                    "old_hyperbolic_pair_reduction",
                    label + f"/{i}/{s}",
                    result.rate.amount[i][s],
                    expected,
                    "flux_fmol_per_s",
                )
        for actual, expected in zip(result.rate.junction_transferred[0], flow, strict=True):
            checks.close(
                "old_hyperbolic_pair_reduction",
                label + "/edge",
                actual,
                float(expected),
                "flux_fmol_per_s",
            )
        checks.close(
            "old_hyperbolic_pair_reduction",
            label + "/gate",
            result.rate.junction_gate[0],
            float(slope),
            "rate_per_s",
        )
        checks.close(
            "old_hyperbolic_pair_reduction",
            label + "/power",
            math.fsum((*result.membrane_dissipation_W, *result.junction_dissipation_W)),
            float(sum(dissipation)) * 1e-12,
            "power_W",
        )


def verify():
    if (
        sha(PROTOCOL) != FROZEN_PROTOCOL_SHA256
        or sha(ROOT / "docs/PHYSICAL_IONIC_GRAPH_SPEC.md") != SPEC_SHA256
    ):
        raise ValueError(
            "Frozen SPEC-007 inputs changed; preserve evidence and version any revision"
        )
    if sha(RELEASE) != RELEASE_SHA256:
        raise ValueError("Accepted production release identity changed")
    panel = ionic.load_json(PROTOCOL)
    for name, value in panel["inherited_sources_sha256"].items():
        if sha(ROOT / name) != value:
            raise ValueError(f"Inherited scientific source changed: {name}")
    release = json.loads(RELEASE.read_text())
    production = {
        str(p.relative_to(ROOT / "src/cells")): sha(p)
        for p in sorted((ROOT / "src/cells").rglob("*.py"))
    }
    if production != release["source_hashes"]:
        raise ValueError("SPEC-007 must leave production unchanged")
    for name, value in release["implementation_files_sha256"].items():
        if sha(ROOT / name) != value:
            raise ValueError(f"Accepted implementation dependency changed: {name}")
    checks = Checks(panel["tolerances"])
    with localcontext() as context:
        context.prec = panel["probes"]["decimal_precision"]
        transport_checks(panel, checks)
        assemblies = composition_checks(panel, checks)
        witnesses = structural_witnesses(panel, checks)
        old_pair_reduction(panel, checks)
    sources = set(panel["inherited_sources_sha256"]) | {
        "configs/reference/physical_ionic_graph_v1.json",
        "docs/PHYSICAL_IONIC_GRAPH_SPEC.md",
        "tests/reference_physical_ionic_graph.py",
        "scripts/check_physical_ionic_graph.py",
        "tests/unit/test_physical_ionic_graph_reference.py",
        "scripts/check_voltage_gated_channel.py",
        "tests/reference_bioelectric.py",
        "pyproject.toml",
        "requirements-lock.txt",
        "requirements-reference.txt",
    }
    return {
        "status": "fail" if checks.failures else "pass",
        "scope": panel["scope"],
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "protocol_sha256": FROZEN_PROTOCOL_SHA256,
        "spec_sha256": SPEC_SHA256,
        "production_release_sha256": RELEASE_SHA256,
        "production_version": "0.12.0",
        "source_sha256": {s: sha(ROOT / s) for s in sorted(sources)},
        "production_source_sha256": production,
        "checks": sum(g["checks"] for g in checks.groups.values()),
        "checks_failed": len(checks.failures),
        "groups": checks.groups,
        "failures": checks.failures,
        "tolerances": panel["tolerances"],
        "assemblies": assemblies,
        "witnesses": witnesses,
        "coupled_trajectory_qualification": "not_performed",
        "method_selection": "not_performed",
        "production_change": False,
        "gpu_qualification": "not_performed",
        "biological_acceptance": "not_assessable",
        "independent_ode_solver_run": False,
        "native_betse_execution": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, help="New receipt path; never overwrite earlier evidence"
    )
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
