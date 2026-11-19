"""The general closure on @3's world (kinds/proton_buffer.py's general layout, rapid_binding@1;
docs/CORE_SEAMS_DESIGN.md §5 and §19 as amended on 18 November 2026).

In an admitted general world nothing changes a held total: every mover of a closure row is refused
at the definition unless its law reads rapid_binding@1, and no built-in law does yet. So the moving
cases here run a test-namespace law whose reads name it, in a scoped registry. World-level power
for a real mover waits for one.
- The read: on B4's buffered cell re-expressed for the general closure, the free h equals version
  1's within the residual criterion, and the potentials are the same bits.
- The split through the engine (phase 1, CORE_SEAMS §19) is in test_rapid_binding_world_run.py
  (one ligand) and test_rapid_binding_world_two_ligands.py (H and Mg on one binder), split out for
  the tiers; their helpers stay here.
- The world-level split check against the core-seams references: a cell holding a registered
  state's totals (S1, and S3 with H and Mg on nuc4) books S_c plus @3's ideal terms on its rows
  equal to the references' E_c.
- Release steps inside amendment C5's registered scope are admitted: S4's pi2_PO4 (H -1), S7's
  mgx_MgmH (H -1, Mg +1), each at a state with every total positive, with the split check
  passing there too. Outside the scope they are refused, naming what C5 does not cover: a count
  below -1, a release in another ligand, or two release steps on one binder.
- P1's case (CORE_SEAMS §17), at an outside node under the general closure: after a draw of ten
  times the free amount, today's predictor form (the read's free amount less the draw) is
  negative, while the stage read at the predicted stored totals is valid with a positive free
  amount, until the draw passes the stored floor; past it the read, the model's domain check and
  the closure's term (NaN, so the ledger refuses) each refuse the state.
- The current injection carried by H+ into a general closure's cell is refused at the definition.
- The run view of a general world, from its definition: the ligand set and the reader's check.
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
from cells.execution.state import initialise
from cells.kinds import proton_buffer
from cells.laws.electrochemistry import R
from cells.records import run_view
from cells.registry import kind_registry
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


@pytest.mark.parametrize(
    "system, k",
    [("S1", 0), ("S1", 11), ("S3", 0), ("S3", 5), ("S4", 0), ("S7", 1), ("S7", 2), ("S7", 3)],
)  # S4's pi2_PO4 and S7's mgx_MgmH: release steps inside C5's scope, at states with totals > 0.
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


@pytest.mark.parametrize("system, k", [("S4", 0), ("S7", 1)])
def test_release_steps_inside_c5s_scope_are_admitted_and_outside_it_refused(system, k):
    """Amendment C5 and the lead's ruling (19 November 2026): a release step inside C5's
    registered scope is admitted, here S4's pi2_PO4 (single-sign) and S7's mgx_MgmH (mixed), at
    a state with every total positive. Planted: pi2 given a form with H -2, a count below -1,
    which C5 does not cover, is refused naming it."""
    raw, _ = reference_cell(system, k)
    parse_spec(raw)
    if system == "S4":
        pi2 = next(e for e in raw["model"]["species"] if e["id"] == "pi2")
        pi2["forms"].append(dict(id="pi2_PO4m", counts={"H": -2}, standard_mu_RT=60.0))
        with pytest.raises(ConfigError, match=r"pi2_PO4m has a count below -1.*Amendment C5"):
            parse_spec(raw)


def test_the_release_scope_names_what_c5_does_not_cover():
    """The scope at the unit level: S7's mgx and S4's pi2 lie inside it; a release step in Mg, and
    a binder with two release steps (whose mixed-sign form is also reached by two paths), lie
    outside it."""
    def forms(*items):
        return (("X", (), 0.0), *((fid, tuple(counts.items()), 0.0) for fid, counts in items))

    mgx = forms(("X_H", {"H": 1}), ("X_Mg", {"Mg": 1}), ("X_MgmH", {"H": -1, "Mg": 1}))
    pi2 = forms(("X_H", {"H": 1}), ("X_PO4", {"H": -1}), ("X_Mg", {"Mg": 1}))
    assert proton_buffer._release_scope_error(mgx, "H") is None
    assert proton_buffer._release_scope_error(pi2, "H") is None
    released_mg = forms(("X_mMg", {"Mg": -1}), ("X_H", {"H": 1}))
    assert "releases Mg, not the proton row" in proton_buffer._release_scope_error(released_mg, "H")
    two = forms(("X_mH", {"H": -1}), ("X_Mg", {"Mg": 1}), ("X_MgmH", {"H": -1, "Mg": 1}))
    assert "2 release steps" in proton_buffer._release_scope_error(two, "H")
    assert proton_buffer._release_scope_error(mgx, None) is not None  # No proton row: none admitted.


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
    impl, state, p, _ = host(spec)
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
        # Past the floor the solve fails: numpy's warnings there are silenced, its outputs checked.
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            read_p, ok_p = proton_buffer.stage_read(predicted, p, xp=np)
            valid = impl.domain_valid(predicted, p, p.active, xp=np)
            term = proton_buffer.ledger_terms(predicted, p, xp=np)["stored_pJ"][lumen]
        assert today < 0
        assert bool(ok_p) is admitted and bool(valid) is admitted
        assert bool(np.isfinite(term)) is admitted  # S_c is NaN past it, so the ledger refuses.
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


def test_the_run_view_states_the_ligand_set_from_the_definition():
    """The run view of a general world (D154), prepared from its definition with no run: the
    binding_ligand set lists the ligand rows in order, each carrying its species, its role named,
    and the view passes the reader's check (every closure field declares its axes, unit and layer,
    or prepare refuses). Planted: the set's roles left empty, as at 2d2d9d20, are refused."""
    spec = parse_spec(reference_cell("S3", 0)[0])
    plan = run_view.prepare(spec, run_view.Request(), layout=initialise(spec).layout)
    view = plan.view({}, "write_run")
    run_view.validate(view)
    ligands = {s["id"]: s for s in view["sets"]}["binding_ligand"]
    assert ligands["ids"] == ["H", "Mg"] and ligands["carries"] == [["H"], ["Mg"]]
    assert set(ligands["roles"]) == {"ligand"}

    def empty_roles(spec, declaration):
        sets = proton_buffer.view_sets(spec, declaration)
        return {key: {**entry, "roles": {}} for key, entry in sets.items()}

    planted = replace(proton_buffer.PROTON_BUFFER, view_sets=empty_roles)
    with kind_registry.scope(kind_fixtures.registry(planted)):
        spec = parse_spec(reference_cell("S3", 0)[0])
        with pytest.raises(run_view.ViewRefused, match="the roles of set binding_ligand name"):
            run_view.prepare(spec, run_view.Request(), layout=initialise(spec).layout)
