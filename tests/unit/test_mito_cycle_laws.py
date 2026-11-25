"""The mitochondria's cycle laws on cells.transporter@1, the kinds owner's law modules
(docs/MITOCHONDRIA_LAWS_APPENDIX.md at tag mito-laws-appendix-2026-11-20b, D236). The first head:
complexes I, III and IV, the synthase, the nucleotide exchange, the phosphate carrier and the
K+/H+ exchange. The second: the matrix's NADH supply on a held pair and the intermembrane
space's adenylate kinase, with the world on beard2005@2 (AMP2-).

Each claim with its plant (D187):
- registration: the seven laws register in the built-in registry, each a monomial form hosted by
  the kind, reading rapid_binding@1 in base forms, with the kind's material term; the supply too, on
  held fuel only and with no step term, and its pair is held together. Planted: a world that moves
  the pair, or holds one of it, is refused;
- the seven laws' own material rates are the host-P world's material rule: the fastest, complex I,
  returns along its own change at the rule's reading, by differences through the closures' read.
  Planted: without them the rule reads over a hundredfold too low;
- a host-P world (FR-4's lumen under the general closure as the IMS, its cell as the matrix, with
  beard2005@2's rows at 298.15 K) admits every population, at the closures' rows too, the kinase
  at P, and two steps close every ledger. The cited constants' seam-E entries are §9's, the
  kinase's -ln K_base unrounded; the supply cites none, and its held-row work is its pair's
  upkeep, its heat plus the work it delivers. The synthase's rate-only constant emits none and
  never moves its x. Planted: the synthase's constant as a CitedConstant is refused by the
  registry's check, and a RateConstant as a factor's K by the form;
- the comparison harness's adapter (validation/mitochondria/component_comparison, the lane's)
  evaluates each law as the kind does: log S, x and J at the world's start agree. The harness
  assembles x itself, from potential_set_values; the kind's own world-level x is this world's,
  so this tie, not the harness, covers it;
- a handful of registered rows, each law's center row of the component references (tag
  mito-components-registration-2026-11-20), have x, S, J and J- in band. Planted: complex I with
  -4u for +4u misses; the supply's pair held at r, without 10^-0.10, moves x by -0.10 ln 10; and
  the kinase without its prefactor has S too small by exactly (1 + [Mg2+]_P/K_MgATP).
The full comparison, every registered row with both plants, is the harness's run: landing
evidence, outside the suite (the lead's ruling 4).

Its cost (D224): 10.4 s for the five tests, measured at f671fc2d on the timed lane. The world
test parses one numpy world and steps it twice, uncompiled; the others parse it or read rows. Its
material part, added since, is four evaluations more."""

import contextlib
import copy
import dataclasses
import math

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.kinds import proton_buffer, transporter
from cells.laws.cycles import forms
from cells.laws.electrochemistry import R
from cells.registry import laws as law_registry
from cells.registry import species_registry
from cells.registry.kind_registry import qualified
from cells.registry.models import get_model
from tests.unit import test_cycle_kind as ck
from tests.unit import test_transporter_kind as tk
from validation.mitochondria import component_comparison as cc

T_K = 298.15  # The appendix's temperature (D236).
LAWS = {  # population ID: (law, roles, parameters)
    "c1": ("nadh_ubiquinone_proton_cycle@1",
           dict(NADH="NADH", Q="Q", NAD="NAD", QH2="QH2", H="H"), {}),
    "c3": ("ubiquinol_cytochrome_c_proton_cycle@1",
           dict(QH2="QH2", Q="Q", c_ox="cytc_ox", c_red="cytc_red", H="H", Pi="Pi"),
           dict(k_Pi3=0.19172, k_Pi4=25.310)),
    "c4": ("cytochrome_c_oxygen_proton_cycle@1",
           dict(O2="O2", c_red="cytc_red", c_ox="cytc_ox", H="H"), dict(k_O2=1.20e-4)),
    "f1": ("proton_coupled_atp_synthesis_cycle@1", dict(ADP="ADP", Pi="Pi", ATP="ATP", H="H"),
           dict(K_MgADP=347.0e-6, K_MgATP=24.0e-6)),
    "ant": ("electrogenic_nucleotide_exchange@1", dict(ATP="ATP", ADP="ADP"),
            dict(theta_P=0.35, k_mADP=3.5e-6)),
    "pic": ("phosphate_proton_symport@1", dict(Pi="Pi", H="H"), dict(k_PiHt=0.45082)),
    "khe": ("potassium_proton_exchange@1", dict(K="K", H="H"), {}),
}  # fmt: skip
SUPPLY = {  # The second head's: the matrix's NADH supply, its pair held (§6).
    "dh": ("held_reductant_supply@1",
           dict(S_red="S_red", NAD="NAD", S_ox="S_ox", NADH="NADH", H="H", Pi="Pi"),
           dict(r=4.5807, k_Pi1=0.13413, k_Pi2=0.67668)),
}  # fmt: skip
KINASE = {  # The second head's: the intermembrane space's adenylate kinase, every row at P (§7).
    "ak": ("adenylate_kinase@1", dict(ADP="ADP", ATP="ATP", AMP="AMP", Mg="Mg"),
           dict(K_MgATP=24.0e-6)),
}  # fmt: skip
ALL = {**LAWS, **SUPPLY, **KINASE}
HELD = {"dh": [["S_red", "N"], ["S_ox", "N"]]}  # population ID: its held rows
SET = "beard2005@2"  # @1 and AMP2-, whose potential the kinase's K_base fixes (D236).
MM = dict(K=140.0, Mg=1.0, O2=0.026, NAD=1.5, NADH=1.5, Q=0.7, QH2=0.7, cytc_ox=1.3, cytc_red=1.4,
          ADP=1.0, ATP=2.0, Pi=5.0, S_ox=1.0, AMP=0.1)  # fmt: skip
MM["S_red"] = 10**-0.10 * SUPPLY["dh"][2]["r"] * MM["S_ox"]  # The declared ratio (§6).


def host_p_world(laws=None):
    """FR-4's development world under the general closure (the binding owner's lumen_general): its
    cell is the matrix (N) and its lumen, a finite outside node bounded by the cell, the IMS (P),
    each under the closure (H and Mg; ADP, ATP, Pi and the node's buffer). beard2005@2's rows
    replace FR-4's neutral fuel, at 298.15 K. One population of each law sits on the bounding patch
    at a capacity small enough that the arbitrary state's fluxes keep every step bound; the supply
    holds its pair, at the declared ratio."""
    from tests.unit.test_rapid_binding_world import fr, lumen_general

    raw = lumen_general()
    m = raw["model"]
    m["temperature_K"] = T_K
    for sid in ("ATP", "ADP", "Pi"):  # FR-4's neutral fuel, which nothing moves here.
        m["species"] = [e for e in m["species"] if e["id"] != sid]
        for node in (*m["cells"], *m["extracellular"]):
            node["initial_amount_fmol"].pop(sid)
        for patch in m["membranes"]:
            patch["permeability_m_per_s"].pop(sid, None)
        raw["execution"]["material_balance_atol_fmol"].pop(sid, None)
    present = {e["id"] for e in m["species"]}
    nodes = [n["id"] for n in (*m["cells"], *m["extracellular"])]
    rows = dict(species_registry.POTENTIAL_SETS[SET].rows)
    for row, z in rows.items():
        if row not in present:
            ck.add_species(raw, row, z, 0.0, dict.fromkeys(nodes, MM[row]))
    for e in m["species"]:
        if e["id"] in rows:
            e.pop("standard_mu_RT", None)
    raw = species_registry.with_potential_set(raw, SET)
    m = raw["model"]
    (read,) = m["stage_reads"]
    read["ligand_rows"] = ["H", "Mg"]
    read["binders"] = {fr.CELL: ["ADP", "ATP", "B_c", "Pi"], fr.LUMEN: ["ADP", "ATP", "B_L", "Pi"]}
    read["k_on_per_mM_s"] = {"ADP": {"Mg": 1e5}, "ATP": {"Mg": 1e5}, "Pi": {"H": 1e7},
                             "B_c": {"H": 1e7}, "B_L": {"H": 1e7}}  # fmt: skip
    m[transporter.MODEL_KEY] = [
        dict(id=pid, host="bounding_0", law=qualified(law), orientation={"N": "a"},
             capacity_fmol_s=1e-15, roles=roles, parameters=parameters,
             held_rows=HELD.get(pid, []))
        for pid, (law, roles, parameters) in (laws or ALL).items()
    ]  # fmt: skip
    return raw


@contextlib.contextmanager
def mito_scoped(*extra_laws):
    """The transporter and the binding closure's kind, the built-in laws and any extra ones."""
    laws = law_registry.BUILTIN.extended(*extra_laws) if extra_laws else law_registry.BUILTIN
    with tk.scoped(*tk.CHARGED_KINDS), law_registry.scope(laws):
        yield


def start(raw):
    """(spec, impl, state, p, control) at the start, inside the caller's scope."""
    spec = parse_spec(copy.deepcopy(raw))
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    return spec, impl, state, p, control


def evaluation(impl, state, p, control):
    read, ok = proton_buffer.stage_read(state, p, xp=np)
    assert bool(ok)
    volts = np.asarray(impl.readouts(state, control, p, xp=np).field.potential_V)
    return read, volts, transporter._evaluate(read, volts, control, p, xp=np)


def free_molar(spec, p, read):
    """{name: free concentration in M} of a stage read at the matrix (N) and the lumen (P), named
    as the harness names its inputs (cc.SET_INPUT)."""
    ids = list(spec.model.species_ids)
    lumen = [x.id for x in spec.model.extracellular].index("lumen_0")
    amounts = {
        "N": (p.amount_reference + read.amount_increment)[:, 0] / p.volume[0],
        "P": (p.extracellular_amount_reference + read.extracellular_amount_increment)[:, lumen]
        / p.extracellular_volume[lumen],
    }
    return {f"{cc.SET_INPUT.get(s, s)}_{end}": float(amounts[end][ids.index(s)]) / 1000.0
            for end in ("N", "P") for s in ids}  # fmt: skip


def test_the_seven_laws_register_as_monomial_forms_of_the_kind_in_base_forms():
    for law, _, _ in LAWS.values():
        found = law_registry.active().lookup(qualified(law))
        assert found.host == transporter.KIND_ID and found.cycle.kinetics == "monomial", law
        assert found.reads == ("rapid_binding@1",) and found.forms == "base", law
        assert ck.step_terms(found) == ["material_term"], law


def test_the_supply_runs_on_its_held_pair_only():
    """The supply registers as the others do, on held fuel only, its pair its fuel roles. Planted:
    a host-P world that moves the pair, or holds one of it, is refused at the parse."""
    (law, _, _) = SUPPLY["dh"]
    found = law_registry.active().lookup(qualified(law))
    assert found.host == transporter.KIND_ID and found.cycle.kinetics == "monomial"
    assert found.reads == ("rapid_binding@1",) and found.forms == "base"
    assert found.fuel_kinds == (transporter.HELD,)
    assert found.cycle.fuel_roles == ("S_red", "S_ox")
    for held, match in (([], "runs on held fuel"), ([["S_red", "N"]], "held together")):
        raw = host_p_world()
        (entry,) = [e for e in raw["model"][transporter.MODEL_KEY] if e["id"] == "dh"]
        entry["held_rows"] = held
        with mito_scoped(), pytest.raises(ConfigError, match=match):
            start(raw)


def own_response(state, p, control, volts, row_node, j):
    """[rows] the rate (1/s) at which each row that population j moves returns along j's own change:
    the kind's rates differenced over stored totals moved by its counts, the closures' read inside,
    at fixed potentials. Where j is the fastest, each is its block's one rate."""
    n, moved = p.active.size, p.cycle_row_present[:, j] & ~p.cycle_row_held[:, j]
    rows = [(*row, nu) for row, nu in zip(
        zip(p.cycle_row_species[moved, j], row_node[moved, j], strict=True),
        np.sum(p.cycle_nu[:, moved, j], axis=0), strict=True) if nu]  # fmt: skip
    ends = []
    for h in (1e-9, -1e-9):
        inc = [state.amount_increment.copy(), state.extracellular_amount_increment.copy()]
        for s, node, nu in rows:
            inc[int(node >= n)][s, node - n * int(node >= n)] += h * nu
        totals = dict(amount_increment=inc[0], extracellular_amount_increment=inc[1])
        read, ok = proton_buffer.stage_read(state._replace(**totals), p, xp=np)
        assert bool(ok)
        k = transporter.rates(read, volts, control, p, xp=np)
        ends.append(np.concatenate((k.cell, k.outside), axis=1))
    slope = (ends[0] - ends[1]) / 2e-9
    return np.array([-slope[s, node] / nu for s, node, nu in rows])


def test_a_host_p_world_admits_every_law_and_books_its_entries_and_steps():
    """Every population parses at the closures' rows, two steps close every ledger, and the cited
    constants' entries are §9's x° at 298.15 K. The synthase emits none, and its x does not move
    with its RateConstant (40 for 36.03 kJ/mol: S moves by exactly that). The supply cites none,
    and its held-row work is its pair's upkeep, its heat plus the work it delivers. The material
    rule's reading, the largest row sum of the seven laws' own rates through the closures'
    derivative, is the rate at which the fastest of them, complex I, returns along its own change,
    to 1%. Planted: the rule without those rates (the neutral rows' and K3b's slopes) reads over a
    hundredfold too low; the synthase's constant as a CitedConstant, refused by the registry's
    check; a RateConstant as a factor's K, refused."""
    with mito_scoped():
        spec, impl, state, p, control = start(host_p_world())
        states = [state]
        for _ in range(2):
            state, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
            assert bool(valid)
            states.append(state)
        history = impl.STATE_TYPE(*(np.stack(v) for v in zip(*states, strict=True)))
        impl.check_values(history, spec, steps=np.arange(len(states)))  # Every ledger closes.
        read, volts, e1 = evaluation(impl, states[0], p, control)
        rates = transporter._population_rates(read, volts, control, p, xp=np)
        assert list(p.cycle_material) == [pid in LAWS for pid in ALL]
        off = p._replace(cycle_material=np.zeros_like(p.cycle_material))
        rule, without = (
            max(transporter.material_term(read, volts, control, q, xp=np)) for q in (p, off)
        )
        back = own_response(states[0], p, control, volts, e1.row_node, list(ALL).index("c1"))
    assert back == pytest.approx(rule, rel=1e-2, abs=0) and without < 1e-2 * rule
    # The supply's books (§6), each side from the registry's potentials and the read: its held-row
    # work is the pair's upkeep, -J (mu_S_ox - mu_S_red), and equals its heat plus the work
    # delivered to the NAD pool, J (mu_NADH + mu_H - mu_NAD) (one node, so no charge term).
    free = free_molar(spec, p, read)
    mu0 = species_registry.potential_set_values(
        SET, temperature_K=T_K, standard_concentration_mM=species_registry.SET_C0_MM
    )
    mu = {row: mu0[row] + math.log(free[f"{cc.SET_INPUT.get(row, row)}_N"]) for row in mu0
          if f"{cc.SET_INPUT.get(row, row)}_N" in free}  # fmt: skip
    dh = list(ALL).index("dh")
    pj = float(e1.j[0, dh]) * 1e-3 * R * T_K  # pJ/s per unit of mu/RT
    upkeep = -pj * (mu["S_ox"] - mu["S_red"])
    delivered = pj * (mu["NADH"] + mu["H"] - mu["NAD"])
    work = float(rates.derivatives["cycle_metabolic_work_pJ"][dh])
    heat = float(rates.derivatives["cycle_dissipated_energy_pJ"][dh])
    assert pj != 0.0 and work == pytest.approx(upkeep, rel=1e-9, abs=0.0)  # pJ/s near 1e-15
    assert work == pytest.approx(heat + delivered, rel=1e-9, abs=0.0)
    entries = transporter.standard_free_energies(dict(spec.model.kinds)[transporter.KIND_ID])
    x0 = {e.law_id: e.dG_kJ_mol * 1000 / (R * T_K) + e.dG_RT_offset for e in entries}
    expected = {"c1": -44.1016, "c3": 19.1137, "c4": -163.6593, "ak": 0.9443}  # §9's entries
    assert sorted(x0) == sorted(qualified(ALL[pid][0]) for pid in expected)
    for pid, value in expected.items():
        assert round(x0[qualified(ALL[pid][0])], 4) == value, pid
    # The synthase's rate-only constant: x is the registry's, whatever the constant.
    base = law_registry.active().lookup(qualified(LAWS["f1"][0]))
    rate = base.cycle.monomial.rates[0]
    shifted = dataclasses.replace(
        base,
        law_id="seamtest.synthase_shifted@1",
        cycle=base.cycle._replace(monomial=base.cycle.monomial._replace(
            rates=(rate._replace(log_k=rate.log_k._replace(dg_kj_mol=40.0)),))),
    )  # fmt: skip
    laws = dict(ALL, f1=("seamtest.synthase_shifted@1",) + LAWS["f1"][1:])
    raw = host_p_world(laws)
    with mito_scoped(shifted):
        _, impl2, state2, p2, control2 = start(raw)
        _, _, e2 = evaluation(impl2, state2, p2, control2)
    f1 = list(ALL).index("f1")
    assert e1.x[0, f1] == e2.x[0, f1]  # Bit for bit: the constant never enters x.
    assert e1.log_s[0, f1] - e2.log_s[0, f1] == pytest.approx(
        (40.0 - 36.03) * 1000 / (R * T_K), rel=1e-9
    )
    cited = dataclasses.replace(
        shifted,
        law_id="seamtest.synthase_cited@1",
        cycle=base.cycle._replace(monomial=base.cycle.monomial._replace(
            rates=(rate._replace(log_k=forms.CitedConstant(*rate.log_k)),))),
    )  # fmt: skip
    for entry in raw["model"][transporter.MODEL_KEY]:
        entry["law"] = entry["law"].replace("synthase_shifted", "synthase_cited")
    with mito_scoped(cited), pytest.raises(ConfigError, match="synthase_cited"):
        start(raw)  # Planted: the constant as a CitedConstant, its entry the registry's to refuse.
    term = forms.MonomialTerm(forms.RateConstant(36.03), ((forms.Reference("H", "N"), 1.0),))
    planted = base.cycle._replace(monomial=base.cycle.monomial._replace(
        rates=(rate._replace(factors=(forms.MonomialFactor(1.0, (term,)),)),)))  # fmt: skip
    assert any("a mode's log k only" in r for r in forms.monomial_errors(planted))


def test_the_harness_adapter_evaluates_each_law_as_the_kind_does():
    """At the host-P world's start, the comparison harness's MonomialAdapter (forms' public
    pipeline, x from the named set) gives each population's log S, x and J per unit capacity as
    the kind's own evaluation does, from the same free concentrations and potentials."""
    with mito_scoped():
        spec, impl, state, p, control = start(host_p_world())
        read, volts, e = evaluation(impl, state, p, control)
    n = len(spec.model.cells)
    lumen = [x.id for x in spec.model.extracellular].index("lumen_0")
    free = free_molar(spec, p, read)
    values = {"dpsi_mV": 1000.0 * float(volts[n + lumen] - volts[0])}
    inputs = dict(
        constants=dict(T_K=str(T_K), F_RT_per_mV=str(96485.33212331001 / (R * T_K) / 1000.0)),
        parameters=dict(with_pi_control=dict(unit="1")),
    )
    for j, (pid, (law, roles, parameters)) in enumerate(ALL.items()):
        spec_j = cc.EngineSpec(
            qualified(law), capacity="unit", parameters=tuple(parameters.items()),
            roles=tuple(roles.items()), potential_set=SET,
        )  # fmt: skip
        found = law_registry.active().lookup(qualified(law))
        got = cc.MonomialAdapter(found.cycle, spec_j, inputs).evaluate(values, free)
        k = float(p.cycle_capacity_fmol_s[j])
        assert got["x"] == pytest.approx(float(e.x[0, j]), abs=1e-9), pid
        assert math.log(got["S"]) == pytest.approx(float(e.log_s[0, j]), abs=1e-9), pid
        assert got["J"] == pytest.approx(float(e.j[0, j]) / k, rel=1e-9, abs=1e-300), pid


def _rows():
    import json
    from pathlib import Path

    return json.loads(Path(__file__).with_name("mito_component_center_rows.json").read_text())


def test_a_handful_of_registered_rows_are_in_band_and_a_reversed_voltage_term_is_not():
    """Each built law's center row of the registered component references: the harness's engine
    adapter gives x, S, J and J- within the row's band. Planted: complex I with zeta -4 for +4."""
    data = _rows()
    inputs = data["inputs"]
    for key, row in data["rows"].items():
        adapter, reason = cc.engine_adapter(key, inputs)
        assert adapter is not None, (key, reason)
        free = cc.free_coordinates(row["inputs"], inputs)
        got = adapter.evaluate(row["inputs"], free)
        for q in ("x", "S", "J", "J_minus"):
            assert abs(got[q] - float(row["ref"][q])) <= row["band"][q], (key, q)
    key = "complex_I"
    adapter, _ = cc.engine_adapter(key, inputs)
    rate = adapter.form.monomial.rates[0]
    adapter.form = adapter.form._replace(monomial=adapter.form.monomial._replace(
        rates=(rate._replace(zeta=-4.0),)))  # fmt: skip
    row = data["rows"][key]
    got = adapter.evaluate(row["inputs"], cc.free_coordinates(row["inputs"], inputs))
    assert abs(got["J"] - float(row["ref"]["J"])) > 3 * row["band"]["J"]
    key = "nadh_supply"  # Planted: the pair held at r, without 10^-0.10 (§6's control).
    adapter, _ = cc.engine_adapter(key, inputs)
    row = data["rows"][key]
    planted = dict(row["inputs"], S_red_N=cc.parameter(inputs, "r") * row["inputs"]["S_ox_N"])
    got = adapter.evaluate(planted, cc.free_coordinates(planted, inputs))
    assert got["x"] - float(row["ref"]["x"]) == pytest.approx(-0.10 * math.log(10), rel=1e-9)
    key = "adenylate_kinase"  # Planted: without its prefactor (§7's control), the only factor.
    adapter, _ = cc.engine_adapter(key, inputs)
    row = data["rows"][key]
    free = cc.free_coordinates(row["inputs"], inputs)
    got = adapter.evaluate(row["inputs"], free, plant="dropped_factor")
    factor = 1.0 + free["Mg_P"] / cc.parameter(inputs, "K_MgATP")
    assert float(row["ref"]["S"]) / got["S"] == pytest.approx(factor, rel=1e-9)
