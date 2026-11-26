"""The population axis against seam A's code-blind references (validation/core_seams/references,
with amendments 1 and A2; CORE_SEAMS_DESIGN §19; the kinds owner's design statement 1, §4, §5).

Through the documented interface only (REFERENCES_USAGE.md). The engine's laws are built from the
registered inputs (reference_inputs.json: states, edges, rate expressions and constants), never
from their values. Each registered host state is set into a world and probed (transporter.probe),
and the probe is compared with api.cycle_state's record at FLOORS floors, above the references'
ten (their rule for a tolerance with power):
- ΔG/RT, absolute, (terms + 8) eps; J, absolute, (J+ + J-)(terms + 8) eps per mode, carried through
  the rows, the held supply, heat, work, the stored standard part, the charge and current, and
  the guard's total (a near-equilibrium J needs the absolute floor);
- S, J+ and J-, a diagram's Pi+-, share and J- by the diagram, its edges' rates and one-way
  fluxes per carrier, its occupancies, and the slopes (dJ/dV, the conductance's magnitude, the
  material slopes): relative, (terms + 8) eps; where the reference is 0 the floor is 0, so
  equality is exact (amendment F4);
- the engine's stated bands (amendment A2): api.engine_wegscheider_band's B, B_psi, N, T, R0, B_W
  and verdict equal forms.wegscheider's for every cycle of every registered and planted diagram;
  api.engine_guard's G and A agree with the probe's guard and allowance, and its verdict is the
  engine's wherever G is not within its floor of A;
- Wegscheider at the definition: every registered law is admitted, and every planted diagram law
  is refused (Q7's basis plants at registration, the others at the definition) with a reason
  about its cycles, as the references' verdicts say. The two constant plants on the converting
  pump d1 are refused first by seam E's check of the kind's standard free energies, which the
  species registry runs ahead of the kind's own checks, beyond the band the law's form gives
  (the binding owner's item 5), so each names that check; no other plant is refused by it;
- the parse: each registered mode's charge sum and charge moved N to P (n_q) are the references'
  (values.seam_a.parse), and the charge plant (mode_species_unbalanced) is refused.
Not here: the planted negative S (the lead's substitution, test_cycle_kind.py's planted factored
evaluation); the moiety plant (mode_moiety_unbalanced), since the species registry declares no
moieties yet (seam E's), so the kind cannot check them; and the base-forms plants, whose rows are
seam C's binder forms, out of this pass's scope (Q4).
"""

import json
import math
import re
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.kinds import transporter
from cells.laws.cycles import forms
from cells.laws.cycles.forms import CycleForm, Diagram, Edge, FluxTerm, Rate
from cells.laws.electrochemistry import CHARGE_PER_FMOL, F, R
from cells.models import surface_pump_v3
from cells.registry import kind_registry
from cells.registry import laws as law_registry
from validation import id_table
from validation.core_seams.references import api
from validation.tissue import pump_water_fixtures as water_fixtures

EPS = np.finfo(float).eps
FLOORS = 16  # Above the references' ten floors; their plants' margins lie far above it.
HERE = Path(api.__file__).parent
INPUTS = id_table.load(HERE / "reference_inputs.json")
VALUES = json.loads((HERE / "designs" / "core_seams_reference_values.json").read_text())
A = INPUTS["seam_a"]
REGISTRY = A["registry"]
C0 = REGISTRY["standard_concentration_mM"]
VERSION_1 = {  # Each factored law's role and its K's parameter name.
    "cells.cycle.proton_atp_mass_action_positive@1": ("proton", "K_H_mM"),
    "cells.cycle.atp_driven_transporter_mass_action_positive@1": ("role", "K_Y_mM"),
}
FUEL = ("ATP", "ADP", "Pi")
SKIPPED = {"planted_negative_S_n1": "the lead's substitution (a planted evaluation)"}
LAWS = [law for law in A["laws"] if law["id"] not in SKIPPED]
OTHER_END = {"a": "b", "b": "a"}


def engine_id(law):
    name = "ref_" + re.sub(r"[^a-z0-9_]", "_", law["id"].lower())
    return "seamtest.cycle.ref_law@1".replace("ref_law", name)


def law_rows(law):
    """The (species, end) rows a reference law touches, in first-appearance order."""
    rows = []

    def add(species, end):
        if (species, end) not in rows:
            rows.append((species, end))

    if law["kind"] == "diagram":
        for edge in law["edges"]:
            for side in ("fwd", "bwd"):
                for species, end, _ in edge[side]["orders"]:
                    add(species, end)
        for cycle in law["cycles"]:
            for species, end, _ in cycle["nu"]:
                add(species, end)
    else:
        for mode in law["modes"]:
            for species, end, _ in mode["nu"]:
                add(species, end)
            for term in mode.get("flux_terms", ()):
                for species, end, _ in term["cycle_nu"]:
                    add(species, end)
    return rows


def counts(rows, nu):
    by_row = {(s, e): n for s, e, n in nu}
    return tuple(int(by_row.get(row, 0)) for row in rows)


def roles_of(rows):
    species = list(dict.fromkeys(s for s, _ in rows))
    return tuple((s, REGISTRY["species"][s]["valence"]) for s in species)


def engine_form(law):
    """The engine's CycleForm of a diagram or net-flow reference law, from its inputs."""
    rows = law_rows(law)
    if law["kind"] == "diagram":
        edges = tuple(
            Edge(
                e["id"],
                int(e["from"]),
                int(e["to"]),
                Rate(e["fwd"]["k0_per_s"], tuple(tuple(o) for o in e["fwd"]["orders"]), e["fwd"].get("zeta", 0.0)),
                Rate(e["bwd"]["k0_per_s"], tuple(tuple(o) for o in e["bwd"]["orders"]), e["bwd"].get("zeta", 0.0)),
            )
            for e in law["edges"]
        )
        cycles = tuple((c["id"], tuple((eid, int(s)) for eid, s in c["edges"])) for c in law["cycles"])
        return CycleForm(
            kinetics="diagram",
            roles=roles_of(rows),
            rows=tuple(rows),
            modes=tuple((c["id"], counts(rows, c["nu"])) for c in law["cycles"]),
            diagram=Diagram(tuple(law["states"]), edges, cycles, law["rate_scale_per_s"], C0),
        )
    return CycleForm(
        kinetics="net_flow",
        roles=roles_of(rows),
        rows=tuple(rows),
        modes=tuple((m["id"], counts(rows, m["nu"])) for m in law["modes"]),
        flux_terms=tuple(
            tuple(
                FluxTerm(t["capacity_fmol_per_s"], counts(rows, t["cycle_nu"]), t.get("shift_psi", 0.0))
                for t in m["flux_terms"]
            )
            for m in law["modes"]
        ),
    )


def engine_law(law):
    """A test-only CycleLaw in the `seamtest` namespace, never shipped; None for a factored law,
    which runs on its built-in law."""
    if law["kind"] == "factored":
        return None
    return law_registry.CycleLaw(
        engine_id(law),
        (),
        (),
        None,
        None,
        cycle=engine_form(law),
        host=transporter.KIND_ID,
        provenance="calibrated",
        source="seam A's registered inputs (validation/core_seams/references), test-only",
    )


def registered(laws):
    """(laws the engine's registry admits, {law ID: its refusal}) of the given CycleLaws."""
    admitted, refused = [], {}
    for law in laws:
        try:
            law_registry.BUILTIN.extended(law)
        except (ConfigError, ValueError) as error:
            refused[law.law_id] = str(error)
        else:
            admitted.append(law)
    return admitted, refused


BUILT, REFUSED = registered([x for x in (engine_law(law) for law in LAWS) if x is not None])


def scopes(*extra):
    registry = kind_registry.KindRegistry()
    registry.register(transporter.TRANSPORTER)
    return kind_registry.scope(registry), law_registry.scope(law_registry.BUILTIN.extended(*BUILT, *extra))


def world(law, population, state, law_id=None):
    """A heredity cell (end a, its cell) and its bath (end b) at the references' volumes and
    registry, every registered species at the state's concentrations, and the population in the
    general form."""
    raw = water_fixtures.heredity_cell("D", end_time=0.002)
    m = raw["model"]
    m["standard_concentration_mM"] = C0
    m["temperature_K"] = REGISTRY["temperature_K"]
    cell, bath = m["cells"][0], m["extracellular"][0]
    cell["volume_pL"], bath["volume_pL"] = A["volumes_pL"]["a"], A["volumes_pL"]["b"]
    for sid, entry in REGISTRY["species"].items():
        known = next((s for s in m["species"] if s["id"] == sid), None)
        if known is None:
            known = dict(id=sid, valence=entry["valence"])
            m["species"].append(known)
        assert known["valence"] == entry["valence"], sid
        known["standard_mu_RT"] = entry["mu0_RT"]
        for node, end in ((cell, "a"), (bath, "b")):
            amount = node["volume_pL"] * state["c_mM"][end].get(sid, 1e-3)
            before = node["initial_amount_fmol"].get(sid, 0.0)
            node["initial_amount_fmol"][sid] = amount
            node["fixed_charge_equivalent_fmol"] -= entry["valence"] * (amount - before)
        for patch in m["membranes"]:
            patch["permeability_m_per_s"][sid] = 0.0
        raw["execution"]["material_balance_atol_fmol"][sid] = 1e-15
    n_end = population["orientation"]["N"]
    law_end = {n_end: "N", OTHER_END[n_end]: "P"}
    held = [(s, law_end[e]) for s, e in population.get("held_rows", [])]
    entry = dict(
        id="population_0",
        host="membrane_0",
        orientation={"N": n_end},
        capacity_fmol_s=population["capacity_fmol_per_s"],
    )
    if law["kind"] == "factored":
        role, k_name = VERSION_1[law["law_id"]]
        moved = next(s for s, _, _ in law["modes"][0]["nu"] if s not in FUEL)
        params = dict(
            stoichiometry=law["parameters"]["n"],
            km_role_mM=law["parameters"][k_name],
            km_atp_mM=law["parameters"]["K_ATP_mM"],
        )
        if role == "proton":
            params |= dict(ph_ref=7.0, ph_band=30.0)  # A domain band every registered state is inside.
        entry |= dict(
            law=law["law_id"],
            roles={role: moved, **{f: f for f in FUEL}},
            parameters=params,
            held_rows=[[role if s == moved else s, e] for s, e in held],
        )
    else:
        entry |= dict(
            law=law_id or engine_id(law),
            roles={s: s for s, _ in roles_of(law_rows(law))},
            parameters={},
            held_rows=[[s, e] for s, e in held],
        )
    m[transporter.MODEL_KEY] = [entry]
    return raw


def prepared(law, *extra, law_id=None):
    """(spec, initial state, layout, control) of the law's world, parsed at its first state."""
    population = A["populations"][law["id"]]
    kinds, laws = scopes(*extra)
    with kinds, laws:
        spec = parse_spec(world(law, population, A["states"][law["id"]][0], law_id))
        structure = surface_pump_v3.structure(spec.model)
        s0, p = surface_pump_v3.initial_values(spec, structure=structure)
        controls = control_values(spec, [0.0])
        control = type(controls)(*(v[0] for v in controls))
        control = control._replace(cycle_availability=np.array([population["availability"]]))
    return spec, s0, p, control


def probed(ready, state):
    """The probe at one registered host state: its concentrations as the amounts at end a (the
    cell) and end b (the bath), its potentials given directly."""
    spec, s0, p, control = ready
    ids = list(spec.model.species_ids)
    cell, outside = np.array(s0.amount_increment), np.array(s0.extracellular_amount_increment)
    for sid in REGISTRY["species"]:
        row = ids.index(sid)
        cell[row, 0] = A["volumes_pL"]["a"] * state["c_mM"]["a"].get(sid, 1e-3) - p.amount_reference[row, 0]
        outside[row, 0] = (
            A["volumes_pL"]["b"] * state["c_mM"]["b"].get(sid, 1e-3) - p.extracellular_amount_reference[row, 0]
        )
    s = s0._replace(amount_increment=cell, extracellular_amount_increment=outside)
    potentials = np.zeros(p.active.size + p.outside_active.size)
    potentials[0] = state["phi_V"]["a"]
    potentials[p.active.size] = state["phi_V"]["b"]
    kinds, laws = scopes()
    with kinds, laws:
        return transporter.probe(s, potentials, control, p, xp=np)


class Mismatches(list):
    def close(self, where, engine, reference, floor):
        engine, reference = float(engine), float(reference)
        if not abs(engine - reference) <= FLOORS * floor:
            self.append(f"{where}: engine {engine!r}, reference {reference!r}, floor {floor!r}")


def reference_modes(law):
    """The reference's mode IDs in the engine's mode order: a diagram's cycles, a law's modes."""
    return [c["id"] for c in law["cycles"]] if law["kind"] == "diagram" else [m["id"] for m in law["modes"]]


def compare_state(law, k, state, ready, out):
    spec, _, p, _ = ready
    population = A["populations"][law["id"]]
    rec = api.cycle_state(law, population, REGISTRY, state, A["volumes_pL"])
    pr = probed(ready, state)
    kinds, laws = scopes()
    with kinds, laws:
        form = transporter.cycle_form(dict(spec.model.kinds)[transporter.KIND_ID][0].law)
    ids = list(spec.model.species_ids)
    n_end = population["orientation"]["N"]
    rt = R * spec.model.temperature_K
    where = f"{law['id']}[{k}, {state.get('tag')}]"
    mode_ids = reference_modes(law)
    assert len(mode_ids) == len(form.modes), where
    zeta_sum = sum(abs(e[s].get("zeta", 0.0)) for e in law.get("edges", ()) for s in ("fwd", "bwd"))
    floor_j, rel = {}, {}
    for m, mode in enumerate(mode_ids):
        r = rec["modes"][mode]
        rel[mode] = (r["dG_RT_terms_abs"] + 8) * EPS
        floor_j[mode] = r["J_scale"] * rel[mode]
        out.close(f"{where} {mode} dG_RT", pr.modes.x[m, 0], r["dG_RT"], rel[mode])
        out.close(f"{where} {mode} J", pr.modes.j[m, 0], r["J"], floor_j[mode])
        pairs = [] if law["kind"] == "net_flow" else [("s", "S"), ("j_plus", "J_plus"), ("j_minus", "J_minus")]
        if law["kind"] == "diagram":
            pairs += [("pi_plus", "Pi_plus"), ("pi_minus", "Pi_minus"), ("share", "sigma_share"),
                      ("j_minus_diagram", "J_minus_diagram")]  # fmt: skip
        for name, key in pairs:
            out.close(f"{where} {mode} {key}", getattr(pr.modes, name)[m, 0], r[key], rel[mode] * abs(r[key]))
        if "slopes" in rec:  # A slope's terms: J's scale times its voltage exponents (F/RT units).
            ref_slope = rec["slopes"]["dJ_dV"][mode]
            exponents = abs(p.cycle_charge_moved[m, 0]) + zeta_sum
            slope_floor = rel[mode] * (abs(ref_slope) + r["J_scale"] * F / rt * exponents)
            out.close(f"{where} {mode} dJ_dV", pr.modes.d_j_d_v[m, 0], ref_slope, slope_floor)
    worst = max(rel.values())
    # The rows and the held supply, by species and host end.
    rows, held = {}, {}
    for kk in range(p.cycle_row_species.shape[0]):
        if not p.cycle_row_present[kk, 0]:
            continue
        end = n_end if p.cycle_row_at_n[kk, 0] else OTHER_END[n_end]
        key = f"{ids[p.cycle_row_species[kk, 0]]}@{end}"
        floor = sum(abs(p.cycle_nu[m, kk, 0]) * floor_j[mode] for m, mode in enumerate(mode_ids))
        (held if p.cycle_row_held[kk, 0] else rows)[key] = (kk, floor)
    assert set(rows) == set(rec["rows_fmol_per_s"]), (where, sorted(rows), sorted(rec["rows_fmol_per_s"]))
    assert set(held) == set(rec["held_supply_fmol_per_s"]), where
    for key, (kk, floor) in rows.items():
        out.close(f"{where} row {key}", pr.rows.rate[kk, 0], rec["rows_fmol_per_s"][key], floor)
        if "slopes" not in rec:
            continue
        material = rec["slopes"]["material"][key]
        amount = A["volumes_pL"][key.split("@")[1]] * state["c_mM"][key.split("@")[1]][key.split("@")[0]]
        for name, ref_key in (("self_slope", "row_self_slope_per_s"), ("max_mode_slope", "max_mode_slope_per_s")):
            value = material[ref_key]
            scale = sum(abs(p.cycle_nu[m, kk, 0]) * rec["modes"][mode]["J_scale"] for m, mode in enumerate(mode_ids))
            out.close(
                f"{where} row {key} {ref_key}", getattr(pr.rows, name)[kk, 0], value,
                worst * (abs(value) + scale / amount),
            )  # fmt: skip
    for key, (kk, floor) in held.items():
        out.close(f"{where} held {key}", pr.rows.held_supply[kk, 0], rec["held_supply_fmol_per_s"][key], floor)
    # Heat, work, the stored part, the charge, the current and the guard's total. A product's
    # floor carries both factors' floors: |dJ| (|x| + dx) + |J| dx per mode, with dx ΔG/RT's
    # absolute floor; for work, x is the held rows' drive, which X (the probe's x_terms) bounds.
    xs = [abs(float(pr.modes.x[m, 0])) for m in range(len(mode_ids))]
    js = [abs(float(pr.modes.j[m, 0])) for m in range(len(mode_ids))]
    bound_x = [float(pr.modes.x_terms[m, 0]) for m in range(len(mode_ids))]
    g_floor = sum(floor_j[mode] * (x + rel[mode]) + j * rel[mode] for mode, x, j in zip(mode_ids, xs, js))
    w_floor = sum(floor_j[mode] * (b + rel[mode]) + j * rel[mode] for mode, b, j in zip(mode_ids, bound_x, js))
    out.close(f"{where} heat", pr.populations.heat_pJ_s[0], rec["heat_pJ_per_s"], 1e-3 * rt * g_floor)
    out.close(f"{where} work", pr.populations.work_pJ_s[0], rec["work_pJ_per_s"], 1e-3 * rt * w_floor)
    out.close(
        f"{where} guard total", 1e-3 * rt * pr.populations.guard[0], rec["guard_total_pJ_per_s"],
        1e-3 * rt * g_floor,
    )  # fmt: skip
    stored = 1e-3 * rt * sum(
        floor_j[mode] * abs(p.cycle_moved_standard_RT[m, 0]) + abs(js[m]) * rel[mode] * abs(p.cycle_moved_standard_RT[m, 0])
        for m, mode in enumerate(mode_ids)
    )
    out.close(f"{where} stored", pr.populations.stored_pJ_s[0], rec["stored_standard_pJ_per_s"], stored)
    charge = sum(abs(p.cycle_charge_moved[m, 0]) * floor_j[mode] for m, mode in enumerate(mode_ids))
    out.close(f"{where} charge a to b", pr.populations.charge_a_to_b_fmol_s[0], rec["charge_a_to_b_fmol_per_s"], charge)
    out.close(
        f"{where} current a to b", pr.populations.current_a_to_b_pA[0], rec["current_a_to_b_pA"],
        1e12 * CHARGE_PER_FMOL * charge,
    )  # fmt: skip
    if "slopes" in rec:  # The engine's conductance is |dI/dV|; its terms as dJ/dV's, in pS.
        conductance = abs(rec["slopes"]["conductance_pS"])
        terms = sum(
            abs(p.cycle_charge_moved[m, 0]) * rec["modes"][mode]["J_scale"] * (abs(p.cycle_charge_moved[m, 0]) + zeta_sum)
            for m, mode in enumerate(mode_ids)
        ) * 1e12 * CHARGE_PER_FMOL * F / rt
        out.close(f"{where} conductance", pr.populations.conductance_pS[0], conductance, worst * (conductance + terms))
    if law["kind"] == "diagram":
        for e, edge in enumerate(law["edges"]):
            r = rec["edges"][edge["id"]]
            for name, key in (("alpha_fwd", "alpha_fwd_per_s"), ("alpha_bwd", "alpha_bwd_per_s"),
                              ("oneway_fwd", "oneway_fwd_per_carrier_per_s"),
                              ("oneway_bwd", "oneway_bwd_per_carrier_per_s")):  # fmt: skip
                out.close(f"{where} edge {edge['id']} {key}", getattr(pr.edges, name)[e, 0], r[key], worst * abs(r[key]))
            net_floor = rec["carrier_scale_fmol"] * (
                abs(r["oneway_fwd_per_carrier_per_s"]) + abs(r["oneway_bwd_per_carrier_per_s"])
            ) * worst
            out.close(f"{where} edge {edge['id']} net", pr.edges.net_fmol_s[e, 0], r["net_fmol_per_s"], net_floor)
        for i, value in enumerate(rec["occupancy"]):
            out.close(f"{where} occupancy {law['states'][i]}", pr.occupancy[i, 0], value, worst * abs(value))
    # The guard as stated (amendment A2): G and A, and the verdict where G is not at A.
    guard = api.engine_guard(law, population, REGISTRY, state)
    out.close(f"{where} guard G", pr.populations.guard[0], guard["G_RT_fmol_per_s"], g_floor)
    a_ref = guard["A_RT_fmol_per_s"]
    out.close(f"{where} guard A", pr.populations.allowance[0], a_ref, 64 * EPS * abs(a_ref))
    if abs(guard["G_RT_fmol_per_s"] - a_ref) > FLOORS * g_floor + 64 * EPS * abs(a_ref):
        fires = bool(pr.populations.guard[0] > pr.populations.allowance[0])
        if fires != bool(guard["fires"]):
            out.append(f"{where} guard verdict: engine fires {fires}, reference fires {guard['fires']}")


@pytest.mark.parametrize("law", LAWS, ids=[law["id"] for law in LAWS])
def test_the_engine_matches_the_references_at_every_registered_state(law):
    assert engine_id(law) not in REFUSED, REFUSED.get(engine_id(law))
    ready = prepared(law)
    out = Mismatches()
    for k, state in enumerate(A["states"][law["id"]]):
        compare_state(law, k, state, ready, out)
    assert not out, "\n".join(out[:20]) + (f"\n... {len(out)} in all" if len(out) > 20 else "")


def wegscheider_records(law, form):
    """The engine's forms.wegscheider and the references' engine band, per cycle."""
    z = {role: REGISTRY["species"][role]["valence"] for role in form.role_names}
    mu = {role: REGISTRY["species"][role]["mu0_RT"] for role in form.role_names}
    for m, cycle in enumerate(law["cycles"]):
        yield cycle, forms.wegscheider(form, m, z, mu, C0), api.engine_wegscheider_band(law, cycle, REGISTRY)


def test_the_engines_wegscheider_band_is_the_one_the_references_evaluate():
    """Amendment A2: for every cycle of every registered and planted diagram, the engine's parse
    decision (B exactly, B_psi exactly, N, T and B_W to rounding, R0 to its 50 digits' rounding,
    and the verdict) is the references' evaluation of the stated band."""
    out = []
    diagrams = [law for law in LAWS if law["kind"] == "diagram"]
    planted = [dict(law, kind="diagram") for law in A["planted_laws"]]
    for law in (*diagrams, *planted):
        try:
            form = engine_form(law)
        except Exception as error:  # A plant the form cannot even hold is refused there.
            out.append(f"{law['id']}: the engine's form could not be built: {error}")
            continue
        if form.errors():  # A basis plant (Q7) or a structural one: refused before any band.
            continue
        for cycle, mine, ref in wegscheider_records(law, form):
            where = f"{law['id']} {cycle['id']}"
            b = {f"{role}@{end}": int(v) for role, end, v in mine.coefficients if v != 0}
            if b != {key: v for key, v in ref["B"].items() if v != 0}:
                out.append(f"{where} B: engine {b}, reference {ref['B']}")
            if mine.psi != Fraction(ref["B_psi"]):
                out.append(f"{where} B_psi: engine {mine.psi}, reference {ref['B_psi']}")
            if mine.constants != ref["N"]:
                out.append(f"{where} N: engine {mine.constants}, reference {ref['N']}")
            if not math.isclose(float(mine.terms), ref["T"], rel_tol=4 * EPS):
                out.append(f"{where} T: engine {float(mine.terms)!r}, reference {ref['T']!r}")
            if not math.isclose(float(mine.band), ref["B_W"], rel_tol=4 * EPS):
                out.append(f"{where} B_W: engine {float(mine.band)!r}, reference {ref['B_W']!r}")
            r0 = float(mine.constant)
            if not abs(r0 - ref["R0"]) <= 2 * math.ulp(ref["R0"]) + 1e-40:
                out.append(f"{where} R0: engine {r0!r}, reference {ref['R0']!r}")
            if not math.isclose(float(mine.psi_band), ref["B_psi_band"], rel_tol=4 * EPS, abs_tol=0.0):
                out.append(f"{where} B_psi band: engine {float(mine.psi_band)!r}, reference {ref['B_psi_band']!r}")
            if mine.admitted != ref["admitted"]:
                out.append(f"{where} admitted: engine {mine.admitted}, reference {ref['admitted']}")
    assert not out, "\n".join(out[:20])


# The plants refused first by seam E's check of the kind's standard free energies (the binding
# owner's item 5, a recorded exception in this file at the lead's ruling of 19 November 2026): the
# constant plants on d1, the one converting pump, whose dG°/RT entry the species registry checks
# ahead of the kind's own Wegscheider check. Every other plant is refused by the kind, or at
# registration.
BY_E = {"d1_pump__k_1pct", "d1_pump__k_1e-6"}
E_REFUSAL = r"standard_free_energies, entry .* beyond its law's form's band"


def test_registered_laws_are_admitted_and_planted_ones_refused_as_the_references_say():
    """Wegscheider at the definition (statement 1, §5.1; Q7): every registered law parses, and
    every planted diagram law is refused, at registration (its form's errors: a basis plant or a
    structural one) or at the definition (the constant or the charge's), with a reason about its
    cycles; the references' verdicts agree. The constant plants on the converting pump d1 are
    refused first by seam E's check, beyond the band their law's form gives (BY_E), and no other
    plant is."""
    assert BY_E <= {planted["id"] for planted in A["planted_laws"]}  # No stale name passes unseen.
    verdicts = VALUES["seam_a"]["wegscheider"]
    for law in LAWS:
        if engine_id(law) in REFUSED:  # Refused at registration: its own test reports it.
            continue
        prepared(law)  # Parses: admitted.
        if law["id"] in verdicts:
            assert verdicts[law["id"]]["verdict"] != "refused", law["id"]
    for planted in A["planted_laws"]:
        base = next(law for law in LAWS if law["id"] == A["plant_states"][planted["id"]])
        plant = dict(planted, kind="diagram")
        with pytest.raises((ConfigError, ValueError)) as refused:
            built = engine_law(plant)  # A form the registry refuses raises at registration.
            prepared(dict(plant, id=base["id"]), built, law_id=built.law_id)
        message = str(refused.value)
        if planted["id"] in BY_E:
            assert re.search(E_REFUSAL, message), (planted["id"], message[:200])
        else:
            assert re.search(r"Wegscheider|cycle|charge", message), (planted["id"], message[:200])
            assert "standard_free_energies" not in message, (planted["id"], message[:200])
        if planted["id"] in verdicts:
            assert verdicts[planted["id"]]["verdict"] != "admitted", planted["id"]


def test_each_registered_modes_charge_is_the_references_and_the_charge_plant_is_refused():
    parse = VALUES["seam_a"]["parse"]
    for law in LAWS:
        if engine_id(law) in REFUSED:  # Refused at registration: its own test reports it.
            continue
        spec = prepared(law)[0]
        kinds, laws = scopes()
        with kinds, laws:
            checks = transporter.cycle_checks(spec)
        for check, mode in zip(checks, reference_modes(law), strict=True):
            ref = parse[law["id"]][mode]
            assert check.charge_sum == ref["charge_sum"], (law["id"], mode)
            assert check.charge_moved == ref["n_q"], (law["id"], mode)
            assert ref["admitted"] and check.admitted, (law["id"], mode)
    # The charge plant (one X+ leaves N and two arrive at P), as a net-flow mode on a registered
    # population with N = a and no held rows.
    plant = next(p for p in A["parse_plants"] if p["id"] == "mode_species_unbalanced")
    record = parse[plant["id"]]
    assert not (record["admitted"] if "admitted" in record else any(v["admitted"] for v in record.values()))
    host = next(law for law in LAWS if law["kind"] == "net_flow")
    assert A["populations"][host["id"]]["orientation"]["N"] == "a" and "held_rows" not in A["populations"][host["id"]]
    mode = dict(id="planted", nu=plant["nu"], flux_terms=[dict(capacity_fmol_per_s=1.0, cycle_nu=plant["nu"])])
    planted = dict(id=plant["id"], kind="net_flow", modes=[mode])
    built = engine_law(planted)
    with pytest.raises(ConfigError, match="conserves charge"):
        prepared(dict(planted, id=host["id"]), built, law_id=built.law_id)
