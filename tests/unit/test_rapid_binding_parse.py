"""The general closure's parse and admission, before its solve (seam C; kinds/proton_buffer.py,
cells.binding.rapid_binding@1, and registry/species_registry.py's check_closure_rows; docs/CORE_SEAMS_DESIGN.md
§5 and §19 as amended on 18 November 2026: the general parse comes before the references'
amendments, with no closure solve and no number from it).

The world is FR-4's development world re-expressed for the general closure: its two buffers
written as forms (one form holding one more H each), and the read declared as cells.binding.rapid_binding@1 on
the ligand H at the cell and the lumen.
- The declaration parses, writes back canonically, keeps version 1's entries and types apart, and
  names its closure rows; an admitted world parses (its solve is stage 1's kernel). Each stage row
  names its read's law as a third item (P1's selector): cells.binding.rapid_binding@1 for the general closure,
  cells.kind.rapid_proton_buffer@1 (not a registered law: today's predictor) for version 1.
- At a closure row, @3's own routes and pumps are refused, and so is a kind's move whose law's
  reads lack cells.binding.rapid_binding@1: FR-4's proton pump (its reads name version 1's read) and its proton
  leak (a route law declares no reads). Planted control: the pump's reads with cells.binding.rapid_binding@1
  admit it. An operator that names a held species is refused; one that names another species is
  admitted.
- Each malformed or inadmissible declaration is refused with its reason.
Each test carries its planted error (D187).
"""

import copy
from types import SimpleNamespace

import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.kinds import proton_buffer
from cells.laws.pumps import calcium_atpase
from cells.registry import species_registry as registry
from validation.compartment_ph_engine import definitions as fr

KIND = proton_buffer.KIND_ID


def general_entry(**overrides):
    entry = dict(
        read_id="cells.binding.rapid_binding@1",
        ligand_rows=["H"],
        proton_row="H",
        binders={fr.CELL: ["B_c"], fr.LUMEN: ["B_L"]},
        k_on_per_mM_s={"B_c": {"H": 1e7}, "B_L": {"H": 1e7}},
    )
    return entry | overrides


def respell(species, row, forms):
    """Row's registry entry with its version-1 two-form key replaced by forms (base unchanged)."""
    entry = next(e for e in species if e["id"] == row)
    entry.pop("protonated_standard_mu_RT", None)
    entry["forms"] = forms


def general_world(*, pump=False, leak=False, entry=None, edit=None):
    """FR-4's development world with the general closure; FR-4's pump and leak only on request."""
    raw = fr.development_world(fr.fr4_world())
    m = raw["model"]
    for row in ("B_c", "B_L"):
        mu = next(e for e in m["species"] if e["id"] == row)["protonated_standard_mu_RT"]
        respell(m["species"], row, [dict(id="H" + row, counts={"H": 1}, standard_mu_RT=mu)])
    m["stage_reads"] = [general_entry() if entry is None else entry]
    if not pump:
        m.pop("transporters")
    if not leak:
        m.pop("passive_routes")
    if edit is not None:
        edit(m)
    return raw


def refused(raw, match):
    with pytest.raises(ConfigError, match=match):
        parse_spec(raw)


def test_the_general_declaration_parses_writes_back_and_is_admitted():
    v1 = parse_spec(fr.development_world(fr.fr4_world()))  # Version 1's world, as registered.
    declaration = proton_buffer._parse_general(general_entry(), v1.model)
    assert declaration == proton_buffer.GeneralDeclaration(
        ("H",),
        ((fr.CELL, ("B_c",)), (fr.LUMEN, ("B_L",))),
        (("B_L", (("H", 1e7),)), ("B_c", (("H", 1e7),))),
        "H",
    )
    assert proton_buffer.to_dict(declaration) == [general_entry()]
    unsorted = general_entry(binders={fr.LUMEN: ["B_L"], fr.CELL: ["B_c"]})
    assert proton_buffer._parse_general(unsorted, v1.model) == declaration  # Canonical.
    assert declaration.closure_rows == (
        ("H", fr.CELL), ("B_c", fr.CELL), ("H", fr.LUMEN), ("B_L", fr.LUMEN),
    )  # fmt: skip
    # P1's selector (the binding owner's ruling (a)): each stage row names its read's law.
    assert proton_buffer.stage_rows(declaration) == tuple(
        (*row, "cells.binding.rapid_binding@1") for row in declaration.closure_rows
    )
    # Version 1's declaration keeps its type and entry; the general one has its own.
    v1_declaration = dict(v1.model.kinds)[KIND]
    assert type(v1_declaration) is proton_buffer.Declaration
    # Version 1's rows name cells.kind.rapid_proton_buffer@1, which is not a registered law: today's form.
    assert {row[2] for row in proton_buffer.stage_rows(v1_declaration)} == {"cells.kind.rapid_proton_buffer@1"}
    assert all(len(row) == 3 for row in proton_buffer.stage_rows(v1_declaration))
    assert proton_buffer.structure_entry(v1_declaration) == (2,)
    assert proton_buffer.structure_entry(declaration) == proton_buffer.GeneralEntry(1, 2)
    parse_spec(general_world())  # The admitted world parses.


def test_a_kind_move_at_a_closure_row_needs_the_closures_read(monkeypatch):
    """FR-4's proton pump moves H at both closure nodes, and its law's reads name version 1's read
    only: refused, naming the law. Given cells.binding.rapid_binding@1 in its reads (planted), the move gets past
    the read and meets §5.2's admission next, which refuses it for the first of its conditions the
    transporter does not meet. Which one follows the transporter's own state (since 3a882746 it
    declares role_species, and its law declares no base forms), so only the admission is asserted;
    each condition is pinned by test_rapid_binding_world.py's planted movers. The proton leak, a
    route law, declares no reads."""
    refused(
        general_world(pump=True),
        r"species H at cell_0 is held by the closure cells.binding.rapid_binding@1: cells.kind.transporter@1 moves "
        r"it under .*cells.cycle.proton_atp_mass_action_positive@1, whose reads \['cells.kind.rapid_proton_buffer@1'\] "
        r"lack cells.binding.rapid_binding@1",
    )
    reads = registry._law_reads
    monkeypatch.setattr(
        registry, "_law_reads", lambda law: (*reads(law), "cells.binding.rapid_binding@1")
    )
    refused(
        general_world(pump=True),
        r"§5.2's admission refuses cells.kind.transporter@1's move under "
        r".*cells.cycle.proton_atp_mass_action_positive@1: ",
    )
    monkeypatch.undo()
    refused(general_world(leak=True), r"cells.kind.passive_routes@1 moves it under .*, whose reads \[\]")


def test_a_held_total_at_or_below_zero_is_refused_before_any_logarithm():
    """Phase 1 (CORE_SEAMS §19 as amended): @3 books its per-row ideal terms on held rows, whose
    logarithms need a positive total, so a held total at or below zero is refused at the
    definition, before any state is built or any logarithm taken: today by @2's own amount check
    ("amount must be finite and positive"), which runs ahead of the registry's background check
    (either refusal passes). The control is the declared world; the plants put the lumen's H total
    at zero and below it. (A total that crosses zero within a run is the solve's, item 3.)"""

    def lumen_h(value):
        def edit(m):
            node = next(n for n in m["extracellular"] if n["id"] == fr.LUMEN)
            node["initial_amount_fmol"]["H"] = value

        return edit

    parse_spec(general_world())
    for value in (0.0, -1e-3):  # Either the registry's refusal or @2's own, both at parse.
        refused(
            general_world(edit=lumen_h(value)),
            rf"species H: {fr.LUMEN} holds {value:g} fmol\. A row absent|amount must be finite "
            "and positive",
        )


def _bounding_h_route(m):
    patch = next(p for p in m["membranes"] if p["id"] == fr.BOUNDING)
    patch["permeability_m_per_s"]["H"] = 1e-9


def test_at3s_own_routes_and_pumps_are_refused_at_a_closure_row(monkeypatch):
    refused(
        general_world(edit=_bounding_h_route),
        rf"species H at cell_0 is held by the closure cells.binding.rapid_binding@1: the membrane {fr.BOUNDING} "
        "moves it in the step",
    )
    from cells.models import surface_pump_v3

    join = surface_pump_v3.moved_rows

    def with_pump(model):  # Planted: @3's calcium pump on the bounding patch, its role H.
        rows = dict(join(model))
        rows["H"] = (*rows.get("H", ()), ("pump", calcium_atpase.LAW_ID, (fr.BOUNDING,)))
        return rows

    parse_spec(general_world())  # The control: nothing of @3's moves H there.
    monkeypatch.setattr(surface_pump_v3, "moved_rows", with_pump)
    refused(general_world(), rf"the pump {fr.BOUNDING} moves it in the step")


class _Model:
    """A parsed model with its kinds replaced (attributes otherwise the parsed model's)."""

    def __init__(self, model, kinds):
        self._model, self.kinds = model, kinds

    def __getattr__(self, name):
        return getattr(self._model, name)


def test_an_operator_naming_a_held_species_is_refused(monkeypatch):
    """check_stage_read_rows (which holds every stage read's rows, the general closure's too) on
    version 1's parsed world, without its pump and leak, with the general declaration in its
    kinds. A composite's operators reach the registry's check; here a planted operator stands in
    for one, and the inner model is the parsed one. Planted: an operator naming H, held at both
    nodes; the control names Na, which no closure holds."""
    raw = fr.development_world(fr.fr4_world())
    for key in ("transporters", "passive_routes"):
        raw["model"].pop(key)
    v1 = parse_spec(raw)
    declaration = proton_buffer._parse_general(general_entry(), v1.model)
    inner = _Model(v1.model, ((KIND, declaration),))
    spec = SimpleNamespace(model=SimpleNamespace(operators=()), experiment=v1.experiment)
    monkeypatch.setattr(registry, "_inner_model", lambda _: inner)

    def operator(species):
        item = SimpleNamespace(id=species, catalogue=None, evidence=None)
        return SimpleNamespace(
            LAW_ID="cells.operator.planted_reaction@1", PROCESS=False, species_identities=lambda _: (item,)
        )

    monkeypatch.setattr(registry, "_entries", lambda _: ((operator("Na"), None),))
    registry.check_stage_read_rows(spec)
    monkeypatch.setattr(registry, "_entries", lambda _: ((operator("H"), None),))
    with pytest.raises(
        ConfigError,
        match=r"species H is held by the stage read of cells.kind.rapid_proton_buffer@1 at cell_0: "
        "cells.operator.planted_reaction@1 names or moves it",
    ):
        registry.check_stage_read_rows(spec)


def _species(m, row):
    return next(e for e in m["species"] if e["id"] == row)


def _ligand_na(m):
    _species(m, "Na")["standard_mu_RT"] = 0.0


def _two_h_only(m):  # B_L's one form holds two H: not reachable from the base by unit steps.
    form = _species(m, "B_L")["forms"][0]
    form.update(id="H2B_L", counts={"H": 2})


def _binds_na(m):  # B_c's forms bind Na too.
    _ligand_na(m)
    _species(m, "B_c")["forms"].append(dict(id="NaB_c", counts={"Na": 1}, standard_mu_RT=-2.0))


def _version_1_spelling(m):
    entry = _species(m, "B_c")
    entry["protonated_standard_mu_RT"] = entry.pop("forms")[0]["standard_mu_RT"]


GENERAL = general_entry()
REFUSALS = {
    "fields": (dict(GENERAL, proton="H"), None, "a read declares exactly"),
    "proton row": (general_entry(proton_row="B_c"), None, "proton_row 'B_c' is not a declared"),
    "unknown ligand": (general_entry(ligand_rows=["X"]), None, "distinct species rows"),
    "repeated ligand": (general_entry(ligand_rows=["H", "H"]), None, "distinct species rows"),
    "unknown node": (
        general_entry(binders={"nowhere": ["B_c"]}, k_on_per_mM_s={"B_c": {"H": 1e7}}),
        None,
        "unknown node 'nowhere'",
    ),
    "held bath": (
        general_entry(binders={fr.BATH: ["B_c"]}, k_on_per_mM_s={"B_c": {"H": 1e7}}),
        None,
        f"node {fr.BATH} is a held bath",
    ),
    "a ligand as binder": (
        general_entry(
            binders={fr.CELL: ["H"]}, k_on_per_mM_s={"H": {"H": 1e7}}
        ),
        None,
        "'H' is not a binder row",
    ),
    "k_on rows": (general_entry(k_on_per_mM_s={"B_c": {"H": 1e7}}), None, "names each binder"),
    "k_on value": (
        general_entry(k_on_per_mM_s={"B_c": {"H": 0.0}, "B_L": {"H": 1e7}}),
        None,
        "must be a finite positive number|positive",
    ),
    "k_on ligand": (
        general_entry(k_on_per_mM_s={"B_c": {"Na": 1e7}, "B_L": {"H": 1e7}}),
        None,
        "names 'Na', no declared ligand row",
    ),
    "ligand without potential": (
        general_entry(ligand_rows=["H", "K"]),
        None,
        "ligand row K declares no standard_mu_RT",
    ),
    "version 1's spelling": (GENERAL, _version_1_spelling, "binder row B_c declares no forms"),
    "unit steps": (GENERAL, _two_h_only, "not reachable from its base by unit steps"),
    "a form's ligand undeclared": (GENERAL, _binds_na, r"forms bind \['Na'\], which the closure"),
    "k_on per binding": (
        general_entry(ligand_rows=["H", "Na"]),
        _binds_na,
        r"k_on of B_c names \['H'\], but its forms bind \['H', 'Na'\]",
    ),
    "an unbound ligand": (
        general_entry(ligand_rows=["H", "Na"]),
        _ligand_na,
        r"ligand rows \['Na'\] are bound by no declared binder",
    ),
}


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_each_inadmissible_general_declaration_is_refused(case):
    entry, edit, message = REFUSALS[case]
    parse_spec(general_world())  # The control: the declared world is admitted.
    refused(general_world(entry=copy.deepcopy(entry), edit=edit), message)


def test_version_1s_bound_kind_keeps_todays_fields_and_the_general_entry_has_its_own():
    """declared_fields (§7.4 (n) 5): version 1's entry binds today's fields, names and order
    (written out here, so any change to them fails), and a GeneralEntry binds the general
    closure's. Only version 1's own entry selects version 1's layout."""
    from cells.registry import kind_registry

    kind = kind_registry.active().lookup(KIND)
    v1 = kind_registry.bound(kind, (2,))
    assert v1.state_axes == (
        ("proton_buffer_max_lag_pH", ("node",)),
        ("proton_buffer_min_pH", ("node",)),
        ("proton_buffer_max_pH", ("node",)),
    )
    assert v1.layout_fields == (
        "proton_buffer_rows", "proton_buffer_member", "proton_buffer_k_mM", "proton_buffer_k_on",
        "proton_buffer_mu_RT", "proton_buffer_proton_mu_RT", "proton_buffer_c0_mM",
        "proton_buffer_initial_pJ",
    )  # fmt: skip
    assert v1.control_fields == () and v1.readout_columns == ("free_proton_mM", "pH")
    general = kind_registry.bound(kind, proton_buffer.GeneralEntry(2, 3))
    assert general.state_axes == proton_buffer.GENERAL_STATE_AXES
    assert general.layout_fields == proton_buffer.GENERAL_LAYOUT_FIELDS
    assert general.readout_columns == proton_buffer.GENERAL_COLUMNS
    assert not set(general.layout_fields) & set(v1.layout_fields)
