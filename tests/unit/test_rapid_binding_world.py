"""The general closure on @3's world (kinds/proton_buffer.py's general layout, rapid_binding@1;
docs/CORE_SEAMS_DESIGN.md §5 and §19 as amended on 18 November 2026).

In an admitted general world nothing changes a held total: every mover of a closure row is refused
at the definition unless its law reads rapid_binding@1, and no built-in law does yet. So the moving
cases here run a test-namespace law whose reads name it, in a scoped registry. World-level power
for a real mover waits for one.
- The read: on B4's buffered cell re-expressed for the general closure, the free h equals version
  1's within the residual criterion, and the potentials are the same bits.
- The split (phase 1, CORE_SEAMS §19): protons carried out of the general closure's cell close
  every ledger, the energy ledger with the closure's term S_c beside @3's ideal terms. Without the
  term it fails.
- The world-level split check against the core-seams references: a cell holding a registered
  state's totals (S1, and S3 with H and Mg on nuc4) books S_c plus @3's ideal terms on its rows
  equal to the references' E_c.
- P1's case (CORE_SEAMS §17), at an outside node under the general closure: after a draw of ten
  times the free amount, today's predictor form (the read's free amount less the draw) is
  negative, while the stage read at the predicted stored totals is valid with a positive free
  amount, until the draw passes the stored floor.
- The current injection carried by H+ into a general closure's cell is refused at the definition.
Each test carries its planted error.
"""

import copy
import json
import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.kinds import proton_buffer
from cells.laws.electrochemistry import R
from cells.registry import kind_registry, laws
from cells.registry.laws import CycleLaw
from tests import kind_fixtures
from tests.unit.test_proton_buffer_kind import buffered_world, host
from validation.compartment_ph_engine import definitions as fr
from validation.tissue import pump_water_fixtures as water_fixtures

EPS = np.finfo(float).eps
REFS = Path(__file__).resolve().parents[2] / "validation" / "core_seams" / "references"
READS_LAW = "tests.binding_reading_carrier@1"


def general(raw, *, kon=1e7):
    """raw (a world with version 1's read) re-expressed for the general closure: B's two-form
    spelling as one form holding one more H, and the read rapid_binding@1 on H at the same nodes."""
    raw = copy.deepcopy(raw)
    m = raw["model"]
    b = next(e for e in m["species"] if e["id"] == "B")
    b["forms"] = [dict(id="HB", counts={"H": 1}, standard_mu_RT=b.pop("protonated_standard_mu_RT"))]
    read = m[proton_buffer.MODEL_KEY][0]
    m[proton_buffer.MODEL_KEY] = [
        dict(read_id="rapid_binding@1", ligand_rows=["H"],
             binders={node: list(rows) for node, rows in read["buffers"].items()},
             k_on_per_mM_s={"B": {"H": kon}})
    ]  # fmt: skip
    return raw


def amounts(state, p):
    return np.concatenate(
        (p.amount_reference + state.amount_increment,
         p.extracellular_amount_reference + state.extracellular_amount_increment), axis=1,
    )  # fmt: skip


def test_the_general_read_gives_version_1s_free_h_within_the_criterion():
    v1 = parse_spec(buffered_world())
    g = parse_spec(general(buffered_world()))
    impl1, state1, p1, control1 = host(v1)
    impl2, state2, p2, control2 = host(g)
    read1, ok1 = proton_buffer.stage_read(state1, p1, xp=np)
    read2, ok2 = proton_buffer.stage_read(state2, p2, xp=np)
    assert ok1 and ok2
    h = list(v1.model.species_ids).index("H")
    free1, free2 = amounts(read1, p1)[h], amounts(read2, p2)[h]
    assert abs(free2[0] / free1[0] - 1) <= 1e-12  # The buffered cell: the criterion's scale.
    assert np.array_equal(free1[1:], free2[1:])  # Unbuffered nodes are read as stored.
    b = list(v1.model.species_ids).index("B")
    assert amounts(read2, p2)[b, 0] < amounts(state2, p2)[b, 0]  # The free base form only.
    first = impl1.readouts(state1, control1, p1, xp=np).field.potential_V
    second = impl2.readouts(state2, control2, p2, xp=np).field.potential_V
    assert np.array_equal(np.asarray(first), np.asarray(second))  # Charge from the totals only.
    # Planted: a read at another binder potential (its form 1% stronger) moves free h beyond it.
    raw = general(buffered_world())
    form = next(e for e in raw["model"]["species"] if e["id"] == "B")["forms"][0]
    form["standard_mu_RT"] -= math.log(1.01)
    _, s3, p3, _ = host(parse_spec(raw))
    read3, _ = proton_buffer.stage_read(s3, p3, xp=np)
    assert abs(amounts(read3, p3)[h, 0] / free1[0] - 1) > 1e-6


def reads_law():
    """A test-namespace cycle law whose reads name rapid_binding@1, held by a scoped law registry,
    for the planted carrier's moves (never shipped)."""
    return CycleLaw(
        READS_LAW, (("carried", 1),), (), lambda *a, **k: None, lambda *a, **k: True,
        reads=("rapid_binding@1",), host=kind_fixtures.CARRIER_ID,
    )  # fmt: skip


def reading_carrier():
    """kind_fixtures' planted charged carrier, its moves naming READS_LAW."""
    base = kind_fixtures.carrier()
    moved = base.moved_rows
    return replace(base, moved_rows=lambda d: tuple((*row, READS_LAW) for row in moved(d)))


def carried(*, ledger=True, rate=1e-3, carrier=reading_carrier):
    kind = proton_buffer.PROTON_BUFFER
    if not ledger:
        kind = replace(kind, ledger_terms=None)
    kinds = kind_fixtures.registry(carrier(), kind)
    raw = general(buffered_world(quiet=True))
    return kinds, kind_fixtures.declare_carrier(raw, species="H", rate=rate)


def test_carried_protons_close_every_ledger_with_the_general_term_and_fail_without_it():
    registry = laws.active().extended(reads_law())
    kinds, raw = carried()
    with kind_registry.scope(kinds), laws.scope(registry):
        spec = parse_spec(raw)
        result = run(spec)  # Every row's host checks: the energy ledger with the stored term.
    final = result.final.state
    ids = list(spec.model.species_ids)
    h, b = ids.index("H"), ids.index("B")
    moved = 1e-3 * spec.experiment.end_time
    assert float(final.carrier_transferred[h, 0]) == pytest.approx(moved, rel=1e-12)
    assert float(final.amount_increment[h, 0]) == pytest.approx(-moved, rel=1e-12)  # H's total.
    assert float(final.amount_increment[b, 0]) == 0.0  # The binder's total never moves.
    assert result.diagnostics["max_energy_balance_relative"] < 1e-3
    lag = np.asarray(final.binding_max_lag_pX)
    assert 0.0 < float(lag[0]) <= 1e-3 and float(lag[1]) == 0.0  # The closure's cell; the bath.
    # Planted: without the closure's term, the energy ledger fails.
    kinds, raw = carried(ledger=False)
    with kind_registry.scope(kinds), laws.scope(registry):
        with pytest.raises(NumericalError, match="accounting failed: energy"):
            run(parse_spec(raw))
    # And the carrier whose law reads only the stored row is refused at the definition.
    kinds, raw = carried(carrier=kind_fixtures.carrier)
    with kind_registry.scope(kinds), pytest.raises(ConfigError, match="lack rapid_binding@1"):
        parse_spec(raw)


def reference_cell(system, k):
    """The heredity cell D holding a registered state's totals of a references system, scaled to
    the cell's volume (the same concentrations), under the general closure; elsewhere each added
    row at a trace, its charge in each node's anchor. Returns (raw, the reference's volume)."""
    inputs = json.loads((REFS / "reference_inputs.json").read_text())["seam_c"]
    registry = inputs["registry"]
    s = inputs["systems"][system]
    state = inputs["manufactured_states"][system][k]
    raw = copy.deepcopy(water_fixtures.heredity_cell("D", end_time=0.004))
    m = raw["model"]
    v_ref = s["volume_pL"]
    for ligand in s["ligands"]:
        entry = dict(id=ligand, valence=registry["species"][ligand]["valence"],
                     standard_mu_RT=registry["species"][ligand]["mu0_RT"])
        if ligand not in [e["id"] for e in m["species"]]:
            m["species"].append(entry)
    for binder in s["binders"]:
        forms = registry["binders"][binder]["forms"]
        m["species"].append(dict(
            id=binder, valence=registry["binders"][binder]["base_valence"],
            standard_mu_RT=forms[0]["mu0_RT"],
            forms=[dict(id=f["id"], counts=f["counts"], standard_mu_RT=f["mu0_RT"]) for f in forms[1:]],
        ))  # fmt: skip
    m["standard_concentration_mM"] = registry["standard_concentration_mM"]
    z = {e["id"]: e["valence"] for e in m["species"]}
    added = [*s["ligands"], *s["binders"]]
    totals = {**state["totals"]["ligands_fmol"], **state["totals"]["binders_fmol"]}
    for node in (*m["cells"], *m["extracellular"]):
        volume = node["volume_pL"]
        values = {r: (totals[r] / v_ref if node is m["cells"][0] else 1e-6) * volume for r in added}
        node["initial_amount_fmol"] |= values
        node["fixed_charge_equivalent_fmol"] -= math.fsum(z[r] * values[r] for r in added)
    for patch in m["membranes"]:
        patch["permeability_m_per_s"] |= dict.fromkeys(added, 0.0)
    raw["execution"]["material_balance_atol_fmol"] |= dict.fromkeys(added, 1e-10)
    for group in ("membrane_controls", "channel_controls", "pump_controls"):
        for entry in raw["experiment"][group]:
            entry["schedule"] = [dict(time=0.0, availability=0.0)]
    m[proton_buffer.MODEL_KEY] = [
        dict(read_id="rapid_binding@1", ligand_rows=list(s["ligands"]),
             binders={m["cells"][0]["id"]: list(s["binders"])},
             k_on_per_mM_s={b: dict.fromkeys(sorted({l for f in registry["binders"][b]["forms"]
                                                      for l in f.get("counts", {})}), 1e7)
                            for b in s["binders"]})
    ]  # fmt: skip
    return raw, v_ref


@pytest.mark.parametrize("system, k", [("S1", 0), ("S1", 11), ("S3", 0), ("S3", 5)])
def test_phase_1s_split_books_the_references_E_c_at_world_level(system, k):
    """The kind's start term S_c (binding_initial_pJ) plus @3's ideal terms RT n (ln(n/V) - 1) on
    the closure's rows at the cell equals the references' E_c at the same concentrations (E_c
    scales with the volume), within 16 eps of the references' terms, scaled. Planted: S_c alone,
    @3's ideal terms masked, misses it by their sum."""
    raw, v_ref = reference_cell(system, k)
    spec = parse_spec(raw)
    _, state, p, _ = host(spec)
    cell = spec.model.cells[0]
    rows = np.asarray(p.binding_rows)
    n = np.asarray(cell.initial_amount_fmol)[rows]
    rt = 1e-3 * R * spec.model.temperature_K
    ideal = rt * np.sum(n * (np.log(n / cell.volume_pL) - 1.0))
    s_c = float(p.binding_initial_pJ[0])
    scale = v_ref / cell.volume_pL
    values = json.loads((REFS / "designs" / "core_seams_reference_values.json").read_text())
    term = values["seam_c"]["systems"][system]["states"][k]["booked_term"]
    floor = 16 * EPS * term["terms_abs_pJ"]
    assert abs((s_c + ideal) * scale - term["E_c_pJ"]) <= floor, (s_c, ideal, term["E_c_pJ"])
    assert abs(s_c * scale - term["E_c_pJ"]) > floor


def lumen_general():
    """FR-4's development world under the general closure at the cell and the lumen (an outside
    node), with no mover of their rows: its pump and leak removed."""
    raw = fr.development_world(fr.fr4_world())
    m = raw["model"]
    for row in ("B_c", "B_L"):
        entry = next(e for e in m["species"] if e["id"] == row)
        entry["forms"] = [dict(id="H" + row, counts={"H": 1},
                               standard_mu_RT=entry.pop("protonated_standard_mu_RT"))]
    m["stage_reads"] = [dict(read_id="rapid_binding@1", ligand_rows=["H"],
                             binders={fr.CELL: ["B_c"], fr.LUMEN: ["B_L"]},
                             k_on_per_mM_s={"B_c": {"H": 1e7}, "B_L": {"H": 1e7}})]
    m.pop("transporters")
    m.pop("passive_routes")
    return raw


def test_p1s_predictor_reads_the_free_amount_at_the_predicted_totals():
    """P1 (CORE_SEAMS §17; §19 as amended: the general layout only). At the lumen, after a draw D
    of protons from its stored total: today's predictor form, the read's free amount less D, is
    negative from D = n_free on; the stage read at the predicted stored totals is valid, with a
    positive free amount, while D stays below the stored total less its floor (0 here), and
    invalid past it."""
    spec = parse_spec(lumen_general())
    _, state, p, _ = host(spec)
    h = list(spec.model.species_ids).index("H")
    lumen = len(spec.model.cells) + [n.id for n in spec.model.extracellular].index(fr.LUMEN)
    read, ok = proton_buffer.stage_read(state, p, xp=np)
    assert ok
    n_free = float(amounts(read, p)[h, lumen])
    stored = float(amounts(state, p)[h, lumen])
    for draw, admitted in ((10 * n_free, True), (0.5 * stored, True), (1.01 * stored, False)):
        increment = np.array(state.extracellular_amount_increment)
        increment[h, lumen - len(spec.model.cells)] -= draw
        predicted = state._replace(extracellular_amount_increment=increment)
        today = n_free - draw
        with np.errstate(over="ignore", invalid="ignore"):  # Past the floor the solve fails.
            read_p, ok_p = proton_buffer.stage_read(predicted, p, xp=np)
        assert today < 0
        assert bool(ok_p) is admitted
        if admitted:
            assert float(amounts(read_p, p)[h, lumen]) > 0


def test_an_h_carried_injection_into_a_general_closure_cell_is_refused():
    raw = cs.frozen_definition(lumen_general())
    raw["model"].setdefault("operators", []).append(
        dict(law="electrode_current_injection@1",
             electrodes=[dict(cell_id=fr.CELL, carriers={"H": 1.0})])
    )  # fmt: skip
    raw["experiment"]["injection_controls"] = [
        dict(cell_id=fr.CELL, schedule=[dict(time=0.0, current_A=2e-12)])
    ]
    with pytest.raises(ConfigError, match=r"species H is held by the stage read .* names or moves"):
        parse_spec(raw)
    k_carried = copy.deepcopy(raw)
    k_carried["model"]["operators"][-1]["electrodes"][0]["carriers"] = {"K": 1.0}
    parse_spec(k_carried)  # The control.
