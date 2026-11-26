"""The general closure on @3's world (kinds/proton_buffer.py's general layout, cells.binding.rapid_binding@1;
docs/CORE_SEAMS_DESIGN.md §5 and §19 as amended on 18 November 2026).

In an admitted general world nothing changes a held total: every mover of a closure row is refused
at the definition unless its law reads cells.binding.rapid_binding@1, and no built-in law does yet. So the moving
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
- §5.2's admission at a closure row, its charge half beside the kept read: the reading carrier
  (its role_species bound, its law in base forms) is admitted. A kind with no role_species, a
  law with no base forms, a role bound to a form, and a role bound to another species are each
  refused.
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
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.state import initialise
from cells.kinds import proton_buffer
from cells.laws.electrochemistry import CHARGE_PER_FMOL, R
from cells.records import run_view
from cells.registry import kind_registry, laws
from cells.registry.laws import CycleLaw
from tests import kind_fixtures
from tests.unit.test_proton_buffer_kind import buffered_world, host
from validation.compartment_ph_engine import definitions as fr
from validation.tissue import pump_water_fixtures as water_fixtures

EPS = np.finfo(float).eps
REFS = Path(__file__).resolve().parents[2] / "validation" / "core_seams" / "references"
READS_LAW = "tests.cycle.binding_reading_carrier@1"


def general(raw, *, kon=1e7):
    """raw (a world with version 1's read) re-expressed for the general closure: B's two-form
    spelling as one form holding one more H, and the read cells.binding.rapid_binding@1 on H at the same nodes."""
    raw = copy.deepcopy(raw)
    m = raw["model"]
    b = next(e for e in m["species"] if e["id"] == "B")
    b["forms"] = [dict(id="HB", counts={"H": 1}, standard_mu_RT=b.pop("protonated_standard_mu_RT"))]
    read = m[proton_buffer.MODEL_KEY][0]
    m[proton_buffer.MODEL_KEY] = [
        dict(read_id="cells.binding.rapid_binding@1", ligand_rows=["H"], proton_row="H",
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
    # K3b's derivative from the read: version 1's layout gives None; the general one, at the
    # buffered cell, the one site's closed forms on the species axis, with H = h + T_B f (1 - f)
    # and f the bound fraction: d ln h / d n_H = 1 / (V H), d ln h / d n_B = d ln c_base / d n_H
    # = -f / (V H) and d ln c_base / d n_B = (1 / T_B + f^2 / H) / V.
    assert proton_buffer.free_log_sensitivity(read1, p1, xp=np) is None
    d, held = proton_buffer.free_log_sensitivity(read2, p2, xp=np)
    volume = float(p2.volume[0])
    total_b = amounts(state2, p2)[b, 0] / volume
    bound = 1 - amounts(read2, p2)[b, 0] / amounts(state2, p2)[b, 0]
    slope = free2[0] / volume + total_b * bound * (1 - bound)
    closed = {
        (h, h): 1 / (volume * slope),
        (h, b): -bound / (volume * slope),
        (b, h): -bound / (volume * slope),
        (b, b): (1 / total_b + bound**2 / slope) / volume,
    }
    assert all(abs(d[i, k, 0] / value - 1) <= 1e-9 for (i, k), value in closed.items())
    assert bool(held[h, 0]) and bool(held[b, 0]) and np.count_nonzero(held) == 2
    assert np.count_nonzero(d) == 4  # Nothing off the closure's rows or nodes.
    # Under jit, as the kinds' material term calls it: the same block.
    import jax
    import jax.numpy as jnp

    compiled = jax.jit(lambda r, q: proton_buffer.free_log_sensitivity(r, q, xp=jnp))
    d_jit, held_jit = compiled(read2, p2)
    assert np.allclose(np.asarray(d_jit), d, rtol=1e-12, atol=0.0)
    assert np.array_equal(np.asarray(held_jit), held)
    # Planted: a read at another binder potential (its form 1% stronger) moves free h beyond it.
    raw = general(buffered_world())
    form = next(e for e in raw["model"]["species"] if e["id"] == "B")["forms"][0]
    form["standard_mu_RT"] -= math.log(1.01)
    _, s3, p3, _ = host(parse_spec(raw))
    read3, _ = proton_buffer.stage_read(s3, p3, xp=np)
    assert abs(amounts(read3, p3)[h, 0] / free1[0] - 1) > 1e-6


def reads_law(*, forms="base"):
    """A test-namespace cycle law whose reads name cells.binding.rapid_binding@1, held by a scoped law registry,
    for the planted carrier's moves (never shipped). It declares its moves in base forms (§5.2's
    admission), unless `forms` says otherwise."""
    return CycleLaw(
        READS_LAW, (("carried", 1),), (), lambda *a, **k: None, lambda *a, **k: True,
        reads=("cells.binding.rapid_binding@1",), host=kind_fixtures.CARRIER_ID, forms=forms,
    )  # fmt: skip


def reading_carrier(*, role=None, hook=True):
    """kind_fixtures' planted charged carrier, its moves naming READS_LAW. Its role_species binds
    the law's role "carried" to the carried species, or to `role` (a plant), at its patch's inside
    and outside (§5.2's admission; the lead's ruling (iii)). With hook False it declares none."""
    from cells.modules import EntityBinding

    base = kind_fixtures.carrier()
    moved = base.moved_rows

    def role_species(declaration):
        species, _, inside, outside, _ = declaration
        ends = {"inside": inside, "outside": outside}
        return (EntityBinding(READS_LAW, {"carried": role or species}, ends, {}),)

    return replace(base, moved_rows=lambda d: tuple((*row, READS_LAW) for row in moved(d)),
                   role_species=role_species if hook else None)  # fmt: skip


def binder_world():
    """FR-4's world under the general closure with B_c held at both its nodes (the lumen's binders
    gain it), and the planted carrier moving B_c, a binder row with its form HB_c, across the
    bounding patch between them: a kind's move of a closure's binder row at the closure's own
    nodes (the kinds owner's K1)."""
    from tests.unit.test_rapid_binding_parse import general_world

    def edit(m):
        (read,) = m["stage_reads"]
        read["binders"][fr.LUMEN] = sorted([*read["binders"][fr.LUMEN], "B_c"])

    raw = general_world(edit=edit)
    return kind_fixtures.declare_carrier(raw, species="B_c", rate=1e-3, membrane="bounding_0")


def carried(*, ledger=True, rate=1e-3, carrier=reading_carrier):
    kind = proton_buffer.PROTON_BUFFER
    if not ledger:
        kind = replace(kind, ledger_terms=None)
    kinds = kind_fixtures.registry(carrier(), kind)
    raw = general(buffered_world(quiet=True))
    return kinds, kind_fixtures.declare_carrier(raw, species="H", rate=rate)


@pytest.mark.parametrize(
    "variant, message",
    [
        ("no hook", r"declares no role_species"),
        ("no base forms", r"declares no base forms"),
        ("a form as a row", r"moves the forms \['HB'\] as rows"),
        ("another species", r"which its entities' resolved rows do not hold"),
        ("a binder row without base forms",
         r"species B_c has forms \(HB_c beside its base\): .* moves its cell rows, and no law "
         "declares how it moves the forms"),
    ],
)  # fmt: skip
def test_section_5_2s_admission_refuses_each_planted_mover(variant, message):
    """§5.2's admission at a closure row, its charge half, with the read kept beside it (the lead,
    19 November 2026). The reading carrier moving H out of the general closure's cell is admitted
    (the control). Planted, each refused at the definition: a kind that declares no role_species,
    a law that declares no base forms, the role bound to a form (HB), and the role bound to another
    species than the one its moved_rows names. A binder row with forms (the kinds owner's K1,
    check_two_form_rows deferring to this admission): the carrier moving B_c at the closure's own
    nodes under a base-form law is admitted (that variant's control), and under a law without base
    forms the two-form rule still refuses it."""
    unformed = variant in ("no base forms", "a binder row without base forms")
    law = reads_law(forms=None if unformed else "base")
    carrier = {"no hook": lambda: reading_carrier(hook=False),
               "a form as a row": lambda: reading_carrier(role="HB"),
               "another species": lambda: reading_carrier(role="K")}.get(variant, reading_carrier)
    if variant == "a binder row without base forms":
        raw = binder_world()
    else:
        raw = kind_fixtures.declare_carrier(
            general(buffered_world(quiet=True)), species="H", rate=1e-3
        )
    registry = laws.active().extended(reads_law())
    with kind_registry.scope(kind_fixtures.registry(reading_carrier(), proton_buffer.PROTON_BUFFER)):
        with laws.scope(registry):
            parse_spec(raw)  # The control.
    planted = laws.active().extended(law)
    with kind_registry.scope(kind_fixtures.registry(carrier(), proton_buffer.PROTON_BUFFER)):
        with laws.scope(planted), pytest.raises(ConfigError, match=message):
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
        dict(read_id="cells.binding.rapid_binding@1", ligand_rows=list(s["ligands"]),
             **({"proton_row": "H"} if "H" in s["ligands"] else {}),
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


def with_sodium(raw, *, only):
    """raw (a reference cell) with the heredity cell's Na as a ligand row: its @3 movers removed
    (patch permeability, NaV, the Na/K pump) and H's potential given it. only: Na takes H's place
    (every count, row, rate and amount) and no proton row is declared; else nuc4 binds Na too."""
    m, e = raw["model"], raw["experiment"]
    species = {entry["id"]: entry for entry in m["species"]}
    species["Na"]["standard_mu_RT"] = species["H"]["standard_mu_RT"]
    for patch in m["membranes"]:
        patch["permeability_m_per_s"]["Na"], patch["pump"] = 0.0, None
    m["channels"] = [c for c in m["channels"] if c["id"] != "nav_0"]
    e["channel_controls"] = [c for c in e["channel_controls"] if c["channel_id"] != "nav_0"]
    e["pump_controls"] = []
    read = m[proton_buffer.MODEL_KEY][0]
    if not only:
        species["nuc4"]["forms"].append(dict(id="nuc4_Na", counts={"Na": 1}, standard_mu_RT=10.0))
        read["ligand_rows"].append("Na")
        read["k_on_per_mM_s"]["nuc4"]["Na"] = 1e7
        return raw

    def na(rows):
        return {"Na" if row == "H" else row: value for row, value in rows.items()}

    m["species"].remove(species["H"])
    for entry in m["species"]:
        for form in entry.get("forms", ()):
            form["counts"] = na(form["counts"])
    for node in (*m["cells"], *m["extracellular"]):
        amounts = node["initial_amount_fmol"]
        node["fixed_charge_equivalent_fmol"] += amounts["Na"]  # The node's Na, replaced.
        amounts["Na"] = amounts.pop("H")
    for patch in m["membranes"]:
        patch["permeability_m_per_s"].pop("H")
    raw["execution"]["material_balance_atol_fmol"].pop("H")
    del read["proton_row"]
    read["ligand_rows"] = ["Na" if row == "H" else row for row in read["ligand_rows"]]
    read["k_on_per_mM_s"] = {b: na(rates) for b, rates in read["k_on_per_mM_s"].items()}
    return raw


@pytest.mark.parametrize(
    "system, k, sodium",
    [("S4", 0, None), ("S7", 1, None), ("S4", 0, "only"), ("S4", 0, "beside H")],
    ids=["S4-0", "S7-1", "S4-0-sodium only", "S4-0-sodium beside H"],  # The first two: today's IDs.
)
def test_release_steps_inside_c5s_scope_are_admitted_and_outside_it_refused(system, k, sodium):
    """Amendment C5 and the lead's ruling (19 November 2026): a release step inside C5's
    registered scope is admitted, here S4's pi2_PO4 (single-sign) and S7's mgx_MgmH (mixed), at
    a state with every total positive. Planted: pi2 given a form with H -2, a count below -1,
    which C5 does not cover, is refused naming it. The proton is the declared proton_row, never
    the one ligand of valence +1 (the third review's finding 1), through the parser: with Na in
    H's place and no proton row, pi2's Na release is refused (the inference admitted it); with Na
    declared beside H, pi2's H release is admitted (the inference, left with none, refused it)."""
    raw, _ = reference_cell(system, k)
    if sodium is not None:
        with_sodium(raw, only=sodium == "only")
    if sodium == "only":
        with pytest.raises(ConfigError, match=r"pi2_PO4 \+ Na <-> pi2 releases Na, not the proton"):
            parse_spec(raw)
        return
    parse_spec(raw)
    if system == "S4" and sodium is None:
        pi2 = next(e for e in raw["model"]["species"] if e["id"] == "pi2")
        pi2["forms"].append(dict(id="pi2_PO4m", counts={"H": -2}, standard_mu_RT=60.0))
        with pytest.raises(ConfigError, match=r"pi2_PO4m has a count below -1.*Amendment C5"):
            parse_spec(raw)


def test_a_stage_reaching_a_signed_held_total_is_refused_by_the_reads_guard(monkeypatch):
    """The read's precondition by construction (positive_held_totals; host only, one parse, about
    2 s). S4's state 0 with its cell's H total set negative, at minus half pi2's total: pi2's
    release form (H -1) keeps the joint margin at half pi2's total, positive, so the margin admits
    the state, and the guard refuses it on the total's own sign. Planted, the guard lifted: the read
    admits a stage at a non-positive held total, unrefused."""
    raw, _ = reference_cell("S4", 0)
    spec = parse_spec(raw)
    _, state, p, _ = host(spec)
    ids = list(spec.model.species_ids)
    h, pi2 = ids.index("H"), ids.index("pi2")
    held = amounts(state, p)
    target = -0.5 * held[pi2, 0]  # fmol in the cell
    signed = state._replace(amount_increment=state.amount_increment.copy())
    signed.amount_increment[h, 0] = target - p.amount_reference[h, 0]
    assert amounts(signed, p)[h, 0] < 0
    assert bool(proton_buffer.stage_read(state, p, xp=np)[1])
    assert not bool(proton_buffer.stage_read(signed, p, xp=np)[1])
    monkeypatch.setattr(
        proton_buffer,
        "positive_held_totals",
        lambda total_l, held, *, xp: xp.ones(total_l.shape[1], bool),
    )
    with np.errstate(all="ignore"):
        assert bool(proton_buffer.stage_read(signed, p, xp=np)[1])  # Unrefused without the guard.


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
    m["stage_reads"] = [dict(read_id="cells.binding.rapid_binding@1", ligand_rows=["H"], proton_row="H",
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
        dict(law="cells.operator.electrode_current_injection@1",
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


# ----------------------------------------------------------------- the forms face (MT-1b's item 1)
# cells.route.logmean_electrodiffusion_forms@1 (laws/routes/logmean_electrodiffusion_forms.py), slice 1: its own
# entity set in @3, statically absent unless declared, every row moving as itself. Host steps only
# (numpy), so no row here compiles a world.
FORMS = "cells.route.logmean_electrodiffusion_forms@1"


def face_world(law, *, floating=False, solver=None):
    """FR-4's development world without its kinds, with one face lumen -> bath declaring `law`
    and carrying Na, K and Cl: today's face, or the forms law with its rows as themselves (the
    degenerate case). With floating, the plasma patch is removed and the cell's charge anchored
    against the lumen's: the cell and the lumen are one capacitor component with no capacitor to
    the held bath, so the face is its only return path (the build plan's item 0), on the floor
    field solver, where that offset's Kirchhoff residual reaches its rounding floor."""
    raw = fr.development_world(fr.fr4_world())
    m, x = raw["model"], raw["execution"]
    for key in ("stage_reads", "transporters", "passive_routes"):
        m.pop(key)
    diffusivity = dict.fromkeys((s["id"] for s in m["species"]), 0.0)
    diffusivity.update(Na=0.5e-9, K=1.0e-9, Cl=1.5e-9)
    m["faces"] = [dict(id="face_0", sender=fr.LUMEN, receiver=fr.BATH, area_m2=1e-12,
                       length_m=1e-6, diffusivity_m2_per_s=diffusivity, law=law)]  # fmt: skip
    x["face_capacity"] = int(law != FORMS)  # A forms face takes no slot of today's faces.
    if solver is not None:
        x["solver"] = solver
    if floating:
        m["membranes"] = [p for p in m["membranes"] if p["outside"] != fr.BATH]
        kept = {p["id"] for p in m["membranes"]}
        e = raw["experiment"]
        e["membrane_controls"] = [c for c in e["membrane_controls"] if c["membrane_id"] in kept]
        x["membrane_capacity"] = len(kept)
        x["field_solver"] = "cells.solver.capacitive_reduction_gauged_damped_newton@3"
        cell = m["cells"][0]
        lumen = next(n for n in m["extracellular"] if n["id"] == fr.LUMEN)
        z = {s["id"]: s["valence"] for s in m["species"]}
        cell["initial_charge_C"] = -lumen["initial_charge_C"]
        ionic = math.fsum(z[s] * a for s, a in cell["initial_amount_fmol"].items())
        cell["fixed_charge_equivalent_fmol"] = cell["initial_charge_C"] / CHARGE_PER_FMOL - ionic
    return raw


def host_steps(raw, steps):
    """(spec, impl, the states of `steps` host IMEX steps from the start, each one accepted)."""
    spec = parse_spec(raw)
    impl, state, p, control = host(spec)
    states = [state]
    for _ in range(steps):
        state, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
        assert bool(valid)
        states.append(state)
    return spec, impl, states


@pytest.mark.parametrize("floating", [False, True], ids=["held", "floating"])
def test_a_forms_face_of_rows_as_themselves_steps_as_todays_face(floating):
    """The degenerate-equivalence row (the build plan's item 1): a forms face whose rows are their
    own forms steps as today's face, every state field bitwise over three host steps, its movers'
    transfers and heat beside today's face's; its ledgers close (check_values). Floating: the face
    is the only return path of the cell and lumen's component, whose offset the forms face's
    current balance fixes. Compiled, the same pair matched bitwise where the programs matched, and
    otherwise at rounding (the slice's evidence). Planted: the forms face at twice its factor
    differs."""
    _, _, today = host_steps(face_world("cells.route.logmean_electrodiffusion@1", floating=floating), 3)
    spec, impl, forms = host_steps(face_world(FORMS, floating=floating), 3)
    paired = {"face_transferred": "forms_face_transferred",
              "face_dissipated_energy_pJ": "forms_face_dissipated_energy_pJ"}  # fmt: skip
    for a, b in zip(today, forms, strict=True):
        for name in type(a)._fields:
            assert np.array_equal(getattr(a, name), getattr(b, paired.get(name, name))), name
    assert np.any(forms[-1].forms_face_transferred != 0)
    assert forms[-1].forms_face_dissipated_energy_pJ[0] > 0
    history = impl.STATE_TYPE(*(np.stack(v) for v in zip(*forms, strict=True)))
    impl.check_values(history, spec, steps=np.arange(len(forms)))  # Every ledger closes.
    raw = face_world(FORMS, floating=floating)
    raw["model"]["faces"][0]["area_m2"] *= 2  # Planted.
    _, _, planted = host_steps(raw, 1)
    assert not np.array_equal(planted[1].extracellular_amount_increment,
                              today[1].extracellular_amount_increment)  # fmt: skip


def test_the_forms_entity_set_is_absent_unless_declared_and_binds_its_return_path():
    """Static absence: a world without forms faces has today's structure field, types and fields
    (no forms field anywhere), and its definition writes no forms face; a forms world's types gain
    their fields and its definition round-trips. The return path (the build plan's item 0, @3's
    condition): field.bind refuses the floating cell and lumen without the forms face's return path
    and admits them inside its context, which @3's initial_values enters and leaves; the whole
    definition parses, and without its face it is refused."""
    from cells.definitions import surface_pump_v3_spec as tissue3
    from cells.models import surface_pump_v3 as inner
    from cells.models import surface_tissue as tissue
    from cells.numerics import surface_field

    spec = parse_spec(face_world("cells.route.logmean_electrodiffusion@1"))
    impl, state, p, _ = host(spec)
    assert impl.structure.forms_faces == () and impl.STATE_TYPE is inner.STATE_TYPE
    assert not any(k.startswith("forms_face") for k in (*type(state)._fields, *type(p)._fields))
    assert "forms" not in json.dumps(tissue3.to_dict(spec))
    forms = parse_spec(face_world(FORMS, floating=True))
    impl, state, p, _ = host(forms)
    assert impl.structure.forms_faces == ("face_0",) and forms.model.faces == ()
    assert set(inner.FORMS_STATE_AXES) <= set(type(state)._fields)
    assert set(inner.FORMS_LAYOUT_FIELDS) <= set(type(p)._fields)
    assert parse_spec(tissue3.to_dict(forms)) == forms
    base = tissue3.projection(forms)
    with pytest.raises(ValueError, match="require an outside return path"):
        tissue.initial_values(base)
    assert surface_field._RETURN_PATHS.get() == ()  # Never left set.
    with surface_field.return_paths([(1, 0)]):  # The lumen (1) to the bath (0).
        tissue.initial_values(base)
    raw = face_world(FORMS, floating=True)
    raw["model"]["faces"] = []
    with pytest.raises(ConfigError, match="require an outside return path"):
        parse_spec(raw)


@pytest.mark.parametrize(
    "case, message",
    [
        ("rk4", "runs on the plain IMEX tableaux"),
        ("N2", "runs on the plain IMEX tableaux"),
        ("projective", "runs on the fine engine in version 1"),
        ("no structure", "through its structure's implementation"),
        ("composite", "runs in @3 alone in version 1"),
        ("stationary", "the structural laws read neither"),
        ("run view", "No view declarations for cells.route.logmean_electrodiffusion_forms@1"),
        ("exact booking", "books today's faces' neutral rows"),
        ("closure", "beside another stage read"),
        ("labels", "is moved by a forms face"),
    ],
)
def test_version_1_refuses_a_forms_face_where_its_paths_are_not_built(case, message):
    """Each path version 1 does not build for a forms face refuses it, naming why: RK4 and N2
    (the plain IMEX tableaux only), the projective mode, a caller without @3's structure, the
    composite's adapter, the stationary analysis, the run view, the faces' exact booking, and a
    world with another stage read than the general closure's (version 1's cells.kind.rapid_proton_buffer@1
    here), and FR-42's labels on a row a forms face moves (label_errors, and the step itself), while
    a row it does not move gives no such reason. The control: the same forms world parses and
    steps (test_a_forms_face_of_rows_as_themselves_steps_as_todays_face)."""
    from cells.analysis import stationary
    from cells.models import pump_composite_adapter as adapter
    from cells.models import surface_pump_v3 as inner

    if case in ("rk4", "N2", "exact booking", "closure"):
        raw = face_world(FORMS, solver={"rk4": "rk4", "N2": "cells.solver.imex_ars222_implicit_conductances@1"}
                         .get(case))  # fmt: skip
        if case == "exact booking":
            raw["model"]["heat_bookings"] = {"faces": "cells.heat.exact_free_energy_heat@1"}
        if case == "closure":
            raw["model"]["stage_reads"] = fr.fr4_world()["model"]["stage_reads"]
        with pytest.raises(ConfigError, match=message):
            parse_spec(raw)
        return
    spec = parse_spec(face_world(FORMS))
    impl, state, p, control = host(spec)
    if case == "labels":
        ids = list(spec.model.species_ids)
        reasons = inner.label_errors(p, [ids.index("K")], structure=impl.structure,
                                     model=spec.model)  # fmt: skip
        assert any(message in r for r in reasons), reasons
        unmoved = inner.label_errors(p, [ids.index("ATP")], structure=impl.structure,
                                     model=spec.model)  # fmt: skip
        assert not any(message in r for r in unmoved)
        with pytest.raises(ConfigError, match="have no one-way term"):
            impl.imex_step(state, spec.execution.dt, control, p, xp=np, labels=[ids.index("K")])
        return
    with pytest.raises((ConfigError, ValueError, run_view.ViewRefused), match=message):
        if case == "projective":
            inner.check_steps(replace(spec, projective=object()), [spec.execution.dt], None)
        elif case == "no structure":
            inner.initial_values(spec)
        elif case == "composite":
            adapter.for_structure(impl.structure)
        elif case == "stationary":
            stationary._components(p, None, [0])
        else:
            run_view.prepare(spec, run_view.Request(), layout=p)


def forms_world(*, law=FORMS, carry=("B_L", "H", "K", "Na", "Cl"), receiver_holds=True,
                stronger=0.0, protons=1.0):  # fmt: skip
    """lumen_general's world (the general closure at the cell and the lumen, no movers) with a
    second finite outside node, lumen_1, holding B_L under the closure too, at 80% of the lumen's
    B_L, K and Cl and neutral on its own (it has no capacitor), joined to the lumen by a face of
    `law` carrying `carry`. The face is lumen_1's only path, so its potential is set by zero net
    face current (G5's condition), on the floor field solver. receiver_holds False: lumen_1's
    closure holds no B_L (a one-ended binder). stronger: HB_L's standard potential lowered by this
    many RT. protons: lumen_1's H total as a fraction of the lumen's. The lumen's protons are almost
    all bound (HB_L is about 6% of B_L there), so with equal H totals HB_L hardly differs between
    the nodes; protons below 1 gives the bound form a gradient comparable to the base's."""
    raw = lumen_general()
    m, x = raw["model"], raw["execution"]
    if stronger:
        b_l = next(e for e in m["species"] if e["id"] == "B_L")
        b_l["forms"][0]["standard_mu_RT"] -= stronger
    lumen = next(n for n in m["extracellular"] if n["id"] == fr.LUMEN)
    other = copy.deepcopy(lumen)
    other["id"] = "lumen_1"
    z = {s["id"]: s["valence"] for s in m["species"]}
    other["initial_amount_fmol"] = {
        s: a * (0.8 if s in ("B_L", "K", "Cl") else protons if s == "H" else 1.0)
        for s, a in lumen["initial_amount_fmol"].items()
    }
    other["initial_charge_C"] = 0.0
    other["fixed_charge_equivalent_fmol"] = -math.fsum(
        z[s] * a for s, a in other["initial_amount_fmol"].items()
    )
    m["extracellular"].append(other)
    if receiver_holds:
        m["stage_reads"][0]["binders"]["lumen_1"] = ["B_L"]
    diffusivity = dict.fromkeys((s["id"] for s in m["species"]), 0.0)
    diffusivity.update(dict.fromkeys(carry, 1e-9))
    m["faces"] = [dict(id="face_0", sender=fr.LUMEN, receiver="lumen_1", area_m2=1e-12,
                       length_m=1e-6, diffusivity_m2_per_s=diffusivity, law=law)]  # fmt: skip
    x["extracellular_capacity"] = len(m["extracellular"])
    x["face_capacity"] = int(law != FORMS)
    x["field_solver"] = "cells.solver.capacitive_reduction_gauged_damped_newton@3"
    return raw


def test_the_forms_kernel_sums_to_the_totals_difference_and_rests_at_equal_forms():
    """The face note's §2 at the kernel (numerics/surface_transport.forms_face_transport): at zero
    potential difference a binder's forms' fluxes sum to (D A/L) (c_total,s - c_total,r), since
    logmean(a, b) ln(a/b) = a - b per form, within rounding; equal forms at both ends give zero flux
    and zero heat, exactly. Planted: one form's valence drives a flux at a potential difference."""
    from cells.laws.electrochemistry import MOL_PER_FMOL
    from cells.numerics import surface_transport as surface

    faces = surface.FormsFaces(
        np.array([True]), np.array([0]), np.array([1]), np.full((3, 1), 2e-15),
        np.array([[-2.0], [-1.0], [0.0]]), np.eye(3),
    )  # fmt: skip
    left, right = np.array([[3.0], [0.2], [1e-3]]), np.array([[1.0], [0.5], [2e-3]])
    rates = surface.forms_face_transport(left, right, np.zeros(1), 298.15, faces, xp=np)
    total = 2e-15 * float(np.sum(left - right)) / MOL_PER_FMOL
    assert bool(rates.valid)
    assert abs(float(np.sum(rates.flux_fmol_s)) - total) <= 16 * EPS * float(
        np.sum(np.abs(rates.flux_fmol_s))
    )
    rest = surface.forms_face_transport(left, left, np.zeros(1), 298.15, faces, xp=np)
    assert not np.any(rest.flux_fmol_s) and not np.any(rest.dissipation_pJ_s)
    moved = surface.forms_face_transport(left, left, np.full(1, 1e-3), 298.15, faces, xp=np)
    assert np.count_nonzero(moved.flux_fmol_s) == 2  # The neutral form stays at rest (planted).


def test_a_forms_face_moves_a_binder_as_its_forms_and_every_ledger_closes():
    """The face note's §5 rows on a forms face between two closure nodes, four host steps, lumen_1
    at half the lumen's H total so that the bound form has a gradient:
    - B_L moves as its forms (B_L, HB_L) at the closure's free forms, HB_L carrying its proton (the
      H row's transfer is its free H's and HB_L's, the bound share above a thousandfold); the rows
      H, K, Na and Cl as themselves (free H at both ends);
    - every ledger closes (check_values: the material ledgers with the bound H carried, the energy
      ledger with the closure's S_c and the movers' heat), and each step's heat is non-negative;
    - lumen_1, whose only path is the face, sits where the face's net current is zero (G5's
      condition), to the field's rounding.
    Planted: the forms moved without their ligands (HB_L's proton left out of its stoichiometry)
    are refused at the definition."""
    from cells.laws.routes import logmean_electrodiffusion_forms as forms_law
    from cells.models import surface_pump_v3 as inner

    spec, impl, states = host_steps(forms_world(protons=0.5), 4)
    p = impl.initial_values(spec)[1]
    network = (np.asarray(p.binding_rows), np.asarray(p.binding_counts),
               np.asarray(p.binding_present), 1)  # fmt: skip
    names = forms_law.movers(spec.model, network, inner.forms_of_binders(spec.model)).names
    assert names[-2:] == ("B_L:B_L", "B_L:HB_L") and list(p.forms_face_form_movers) == [9, 10]
    moved = states[-1].forms_face_transferred[:, 0]
    assert moved[5] == 0 and moved[10] > 1e-2 * moved[9] > 0  # B_L as its forms, HB_L carried.
    rows = inner.forms_row_transfers(states[-1], p, xp=np)[:, 0]
    h = list(spec.model.species_ids).index("H")
    assert abs(rows[h] - (moved[3] + moved[10])) <= 4 * EPS * abs(moved[10])
    assert moved[10] > 1e3 * abs(moved[3])  # The bound form carries the protons, not the free H.
    heat = [s.forms_face_dissipated_energy_pJ[0] for s in states]
    assert all(b >= a for a, b in zip(heat, heat[1:], strict=False)) and heat[-1] > 0
    history = impl.STATE_TYPE(*(np.stack(v) for v in zip(*states, strict=True)))
    impl.check_values(history, spec, steps=np.arange(len(states)))  # Every ledger closes.
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    values = impl.readouts(states[-1], control, p, xp=np)
    read = proton_buffer.stage_read(states[-1], p, xp=np)[0]
    forms, _ = inner.forms_rates(read, np.asarray(values.field.potential_V), p, xp=np)
    terms = float(np.sum(np.abs(p.forms_face_valence * forms.flux_fmol_s)))
    assert abs(float(forms.current_A[0])) <= 1e-9 * CHARGE_PER_FMOL * terms  # G5: no net current.
    real = forms_law.movers

    def unligated(model, network=None, forms=None):
        table = real(model, network, forms)
        stoichiometry = np.array(table.stoichiometry)
        stoichiometry[np.asarray(table.binder) >= 0, list(model.species_ids).index("H")] = 0.0
        return table._replace(stoichiometry=stoichiometry)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(forms_law, "movers", unligated)
        with pytest.raises(ConfigError, match="HB_L changes its rows' charge"):
            parse_spec(forms_world())


@pytest.mark.parametrize(
    "case, message",
    [
        ("forms law", None),
        ("today's law at a ligand row", r"species H at lumen_0 is held by the closure .* face_0"),
        ("today's law at a binder row", r"species B_L has forms .* face face_0 moves its outside"),
        ("one end held", "holds at lumen_0 and not at lumen_1"),
        ("binder held at neither end", "species B_c has .* moves its outside rows"),
    ],
)
def test_the_forms_law_is_admitted_at_closure_rows_where_todays_face_is_refused(case, message):
    """§4's admission: at the general closure's rows the forms law is admitted (it moves each form
    and free ligand at the closure's read) and today's face law refused (it reads stored totals);
    a binder the closure holds at one end only is refused (version 1: its forms have no
    concentration there), and a multi-form row the closure holds at neither end stays inert, as
    the registry rules for every mover."""
    raw = {
        "forms law": lambda: forms_world(),
        "today's law at a ligand row": lambda: forms_world(
            law="cells.route.logmean_electrodiffusion@1", carry=("H", "K")
        ),
        "today's law at a binder row": lambda: forms_world(law="cells.route.logmean_electrodiffusion@1"),
        "one end held": lambda: forms_world(receiver_holds=False),
        "binder held at neither end": lambda: forms_world(carry=("B_c", "K")),
    }[case]()
    if message is None:
        parse_spec(raw)
        return
    with pytest.raises(ConfigError, match=message):
        parse_spec(raw)


# ------------------------------------------- the leak reading the closure (MT-1b's item 3)

LEAK_V1, LEAK_V2 = "cells.route.proton_constant_field_leak@1", "cells.route.proton_constant_field_leak@2"


def leak_general(law=LEAK_V2):
    """lumen_general's world with FR-4's leak back on the bounding patch, between the cell and the
    lumen, each a node of the general closure, under `law`."""
    raw = lumen_general()
    raw["model"]["passive_routes"] = [
        dict(id="proton_leak_0", patch=fr.BOUNDING, law=law, permeability_m_per_s=6e-7)
    ]
    return raw


def test_the_leak_at_version_2_reads_the_general_closures_free_h_and_closes_every_ledger():
    """MT-1b's face plan, item 3 (MITOCHONDRIA_DESIGN §7): at the general closure's nodes @2 is
    admitted (its declared read is the closure's, its row the closure's ligand H, crossing a
    patch) and @1 refused (it declares no read). @2's flux is the constant-field flux of the
    closure's free h at both ends, from the closure's own read: planted, the stored totals give
    another. Four host steps keep every ledger closing with the closure's S_c (host side)."""
    from cells.kinds import passive_routes
    from cells.laws.electrochemistry import ghk_leak

    with pytest.raises(ConfigError, match=r"cells.route.proton_constant_field_leak@1, whose reads \[\] lack"):
        parse_spec(leak_general(LEAK_V1))
    spec = parse_spec(leak_general())
    impl, state, p, control = host(spec)
    read = proton_buffer.stage_read(state, p, xp=np)[0]
    potentials = np.asarray(impl.readouts(state, control, p, xp=np).field.potential_V)
    flux = passive_routes._flux(read, potentials, control, p, xp=np).flux
    h = list(spec.model.species_ids).index("H")
    inside, outside = int(p.passive_inside[0]), int(p.passive_outside[0])
    volume = np.concatenate((p.volume, p.extracellular_volume))

    def ends(s):
        cells = p.amount_reference + s.amount_increment
        nodes = p.extracellular_amount_reference + s.extracellular_amount_increment
        amounts = np.concatenate((cells, nodes), axis=1)[h]
        return amounts[inside] / volume[inside], amounts[outside] / volume[outside]

    voltage = potentials[inside] - potentials[outside]
    opening = control.membrane[int(p.passive_membrane[0])]
    args = (voltage, 1, p.temperature, p.passive_area[0], 6e-7, opening)
    free = ghk_leak(*ends(read), *args, xp=np)
    assert flux[h, 0] == pytest.approx(float(free), rel=1e-14, abs=0) and flux[h, 0] != 0
    assert abs(float(ghk_leak(*ends(state), *args, xp=np)) - flux[h, 0]) > 1e-3 * abs(flux[h, 0])
    states = [state]
    for _ in range(4):
        state, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
        assert bool(valid)
        states.append(state)
    history = impl.STATE_TYPE(*(np.stack(v) for v in zip(*states, strict=True)))
    impl.check_values(history, spec, steps=np.arange(len(states)))  # Every ledger, S_c's too.


def test_the_leak_at_version_2_is_version_1_without_a_closure_and_refused_at_b4s_nodes():
    """With no closure @2 is @1, bit for bit over three host steps (one mask, one kernel, the same
    read), on the passive routes' closed pair with an H row; at B4's buffered nodes, whose free h
    @1 reads, @2 is refused (host side, parses and steps only)."""
    from tests.unit import test_passive_routes_kind as pr

    runs = []
    for law in (LEAK_V1, LEAK_V2):
        raw = pr.charged_pair(species="H", valence=1, voltage_fmol=-5.18e-5)
        raw["model"]["passive_routes"][-1]["law"] = law
        spec = parse_spec(raw)
        impl, state, p, control = host(spec)
        for _ in range(3):
            state, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
            assert bool(valid)
        runs.append(state)
    pairs = zip(*runs, strict=True)
    assert all(np.asarray(a).tobytes() == np.asarray(b).tobytes() for a, b in pairs)
    raw = fr.development_world(fr.fr4_world())
    raw["model"]["passive_routes"][0]["law"] = LEAK_V2
    with pytest.raises(ConfigError, match=r"is a buffered node of B4's version-1 closure"):
        parse_spec(raw)


def test_a_route_reading_the_closure_moves_a_ligand_across_two_ends_and_the_face_is_pinned():
    """The route-law branch of the closure's admission (species_registry._route_mover_errors)
    refuses a route law whose row is no ligand of the closure (a binder's row holds its forms') and
    one on a host without two ends; the forms face's names in the registry are the forms law
    module's own (the face review's tidy-up)."""
    from types import SimpleNamespace

    from cells.laws.routes import logmean_electrodiffusion_forms as forms_law
    from cells.registry import species_registry

    closure = SimpleNamespace(ligands=("H",))
    assert species_registry._route_mover_errors(closure, LEAK_V2, "H") == ()
    refused = species_registry._route_mover_errors(closure, LEAK_V2, "B_c")
    assert "no ligand of the closure" in refused[0]
    face = laws.RouteLaw(
        "tests.route.face_route@1", ("face",), "a planted route on a face",
        host="cells.kind.passive_routes@1", reads=("cells.binding.rapid_binding@1",),
    )  # fmt: skip
    with laws.scope(laws.BUILTIN.extended(face)):
        refused = species_registry._route_mover_errors(closure, face.law_id, "H")
        assert "are not two-ended" in refused[0]
    assert species_registry.FORMS_FACE_LAW == forms_law.LAW_ID
    assert species_registry.FORMS_FACE_READ == forms_law.CLOSURE_READ_ID
