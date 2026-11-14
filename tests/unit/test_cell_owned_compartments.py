"""Tier-1 smoke test of cell_owned_compartments@1 and the contract's declarations (FR-1, D169).

docs/CLOSED_COMPARTMENT_DESIGN.md §1.4 to §1.6 and §4, in NumPy (no compile), on the silence world W
(validation/tissue/compartment_fixtures.loaded_compartment):
* the contract (§1.6, option (b), the lead's ruling): a DECLARATION_ONLY operator is admitted only
  when nothing of it reaches the step; each excluded declaration and each overridden step method is
  refused with its reason. The part-less operator with nothing at all (the contract test's
  `Nothing`) stays refused. A part-less owner whose every owned field is an accepted write is
  admitted, and one with an owned field nothing writes is refused. Every registered operator is
  admitted, as before;
* the declaration parses and round-trips, its refusals 1 to 7 fire with their reasons, and the
  summary carries the identity block. A label or reference changes no binding;
* the composite's structure check refuses the providers and closers of what the declaration reads
  as declared, in either order, and admits the operators of its list; the list fails closed.
"""

import copy
from types import SimpleNamespace

import pytest

from cells.core import pump_composite_spec as cs
from cells.core.specs import ConfigError, parse_spec
from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.models.operators import OPERATORS
from cells.models.operators import compartments as comp
from cells.models.operators.contract import (
    DECLARATION_EXCLUDES,
    STEP_METHODS,
    Operator,
    check_declarations,
    declaration_errors,
)
from cells.models.registry import get_model
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from validation.tissue import compartment_fixtures as cfx
from validation.tissue import secreted_species_fixtures as fx

LAW = cfx.LAW
END = 0.004


def w(**kwargs):
    return cfx.loaded_compartment(end=END, **kwargs)


def declared(raw, compartments):
    out = copy.deepcopy(raw)
    out["model"]["operators"][-1]["compartments"] = compartments
    return out


def node(raw, name):
    return next(c for c in raw["model"]["extracellular"] if c["id"] == name)


def patch(raw, name):
    return next(p for p in raw["model"]["membranes"] if p["id"] == name)


def two_cells(*, contacts, faces=(), junctions=()):
    """Two cells on the bath; cell_0's compartment ecs_0, a finite node ecs_1 beside cell_1."""
    raw = fx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=(("ecs_0", 1.0), ("ecs_1", 1.0)),
        contacts=contacts,
        faces=faces,
        junctions=junctions,
        end=0.01,
        concentrations_mM=dict(cell_0=1e-3, cell_1=1e-3, ecs_0=1e-6, ecs_1=5e-4),
    )
    return raw


# ------------------------------------------------------------------ the contract


class Minimal(Operator):
    LAW_ID = "minimal_declaration@1"
    DECLARATION_ONLY = True


def test_the_declaration_is_admitted_and_contributes_nothing():
    op = OPERATORS[LAW]
    assert type(op).DECLARATION_ONLY and declaration_errors(type(op)) == []
    assert check_declarations(type(op)) is type(op)
    assert check_declarations(Minimal) is Minimal
    for other in OPERATORS.values():  # Every registered operator, as before.
        assert check_declarations(type(other)) is type(other)


def test_the_operator_with_nothing_at_all_stays_refused():
    class Nothing(Operator):
        LAW_ID = "nothing@1"

    with pytest.raises(ValueError, match="contributes at least one part"):
        check_declarations(Nothing)


TRUTHY = {bool: True, str: "x", type(None): "x"}


@pytest.mark.parametrize("attribute, what", DECLARATION_EXCLUDES)
def test_a_declaration_that_declares_anything_of_the_step_is_refused(attribute, what):
    default = getattr(Operator, attribute)
    if isinstance(default, (bool, str, type(None))):
        value = TRUTHY[type(default)]
    elif hasattr(default, "keys"):
        value = {"x_fmol": ("x",)}
    else:
        value = ("x",)
    marked = type("Marked", (Minimal,), {attribute: value})
    with pytest.raises(ValueError, match=rf"a declaration contributes nothing.*\({attribute}\)"):
        check_declarations(marked)


@pytest.mark.parametrize("method", STEP_METHODS)
def test_a_declaration_that_overrides_a_step_method_is_refused(method):
    marked = type("Marked", (Minimal,), {method: lambda self, *a, **k: None})
    with pytest.raises(ValueError, match=f"overrides the step method {method}"):
        check_declarations(marked)


def test_a_part_less_owner_of_accepted_writes_only_is_admitted():
    class Owner(Operator):
        LAW_ID = "accepted_owner@1"
        STATE_AXES = {"held_fmol": ["cell_slot"]}
        LEDGERS = ("held",)
        LEDGER_DIAGNOSTICS = ("held_error_fmol",)
        ACCEPTS_WRITES = {"held_fmol": ("held",)}

    class Stranded(Owner):
        LAW_ID = "stranded_owner@1"
        STATE_AXES = {"held_fmol": ["cell_slot"], "stuck_fmol": ["cell_slot"]}

    assert check_declarations(Owner) is Owner
    with pytest.raises(ValueError, match="contributes at least one part"):
        check_declarations(Stranded)


# ------------------------------------------------------------------ the declaration


def test_the_declaration_parses_round_trips_and_names_its_compartments():
    spec = parse_spec(w())
    assert [d.law for d in spec.model.operators] == ["scheduled_species_exchange@1", LAW]
    declaration = spec.model.operators[-1]
    assert declaration.compartments == (
        comp.Compartment("ecs_0", "contact_0", "cell_0", "lysosome pool", None),
    )
    assert parse_spec(cs.to_dict(spec)) == spec
    op = OPERATORS[LAW]
    summary = op.summary(spec, declaration, (), None)
    assert summary["compartments"] == [
        dict(
            id="ecs_0",
            node_column=1,
            patch="contact_0",
            patch_column=1,
            owner="cell_0",
            owner_carrier="cell_0",
            label="lysosome pool",
            reference=None,
        )
    ]
    model = get_model(spec.model)
    assert (
        model.STATE_TYPE._fields
        == get_model(parse_spec(w(declared=False)).model).STATE_TYPE._fields
    )


def test_a_label_or_a_reference_changes_no_binding():
    plain = cfx.bindings(w())
    for label, reference in (("secretory granules", None), (None, "GO:0005764")):
        other = cfx.bindings(declared(w(), [cfx.compartment(label=label, reference=reference)]))
        assert cfx.same_bindings(plain, other) == []


def closed_world(gauge):
    raw = w()
    node(raw, "bath")["reservoir"] = False
    raw["model"]["closure"]["gauge_reference"] = gauge
    return raw


def faced_world():
    raw = fx.world(
        cells=(("cell_0", 1.0),),
        nodes=(("ecs_0", 1.0),),
        contacts=(("contact_0", "cell_0", "ecs_0"),),
        faces=(("face_0", "ecs_0", "bath", 1e-10, 1e-5),),
        end=END,
        concentrations_mM=dict(cell_0=1e-3, ecs_0=1e-6),
    )
    return cfx.with_compartments(raw, [cfx.compartment()])


def shared_node():
    raw = two_cells(contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_0")))
    return cfx.with_compartments(raw, [cfx.compartment()])


def misowned():
    raw = two_cells(contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_1")))
    return cfx.with_compartments(raw, [cfx.compartment(owner="cell_1")])


def permeable():
    raw = w()
    patch(raw, "contact_0")["permeability_m_per_s"]["K"] = 1e-9
    return raw


def charged():
    raw = w()
    lumen = node(raw, "ecs_0")
    lumen["fixed_charge_equivalent_fmol"] += 1e-8
    valence = {s["id"]: s["valence"] for s in raw["model"]["species"]}
    net = lumen["fixed_charge_equivalent_fmol"] + sum(
        valence[s] * n for s, n in lumen["initial_amount_fmol"].items()
    )
    lumen["initial_charge_C"] = CHARGE_PER_FMOL * net
    return raw


REFUSALS = {
    "an undeclared node": (
        lambda: declared(w(), [cfx.compartment(node="nowhere")]),
        "is not a declared outside node",
    ),
    "a held bath": (
        lambda: declared(w(), [cfx.compartment(node="bath", patch="wall_cell_0")]),
        "is a held bath",
    ),
    "the gauge": (lambda: closed_world("ecs_0"), "is the gauge"),
    "a node named by a face": (faced_world, "is named by the face 'face_0'"),
    "an undeclared patch": (
        lambda: declared(w(), [cfx.compartment(patch="nope")]),
        "is not declared",
    ),
    "a patch that does not face the node": (
        lambda: declared(w(), [cfx.compartment(patch="wall_cell_0")]),
        "is bounded by exactly one patch",
    ),
    "a node faced by two patches": (shared_node, "is bounded by exactly one patch"),
    "an owner that is not a cell": (
        lambda: declared(w(), [cfx.compartment(owner="bath")]),
        "is not a cell",
    ),
    "a patch on another cell": (misowned, "not on its declared owner 'cell_1'"),
    "two compartments on one node": (
        lambda: declared(w(), [cfx.compartment(), cfx.compartment(label="again")]),
        "one compartment per node",
    ),
    "an ion route on the bounding patch": (permeable, "carries an ion route"),
    "a charge anchor": (charged, "nonzero charge anchor"),
    "no held bath in the owner's component": (lambda: closed_world("bath"), "with no held bath"),
    "an empty label": (
        lambda: declared(w(), [cfx.compartment(label=" ")]),
        "null or a non-empty string",
    ),
    "a numeric reference": (
        lambda: declared(w(), [cfx.compartment(reference=5)]),
        "null or a non-empty string",
    ),
}


@pytest.mark.parametrize("name", sorted(REFUSALS))
def test_definition_refusals(name):
    build, message = REFUSALS[name]
    with pytest.raises(ConfigError, match=message):
        parse_spec(build())


def replaced(events):
    raw = two_cells(
        contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_1")),
        faces=(("face_1", "ecs_1", "bath", 1e-10, 1e-5),),
        junctions=(("junction_0", "cell_0", "cell_1"),),
    )
    template = fx.template(raw, "cell_1", "T", s_mM=1e-3)
    raw = fx.with_replacement(raw, [template], events)
    return cfx.with_compartments(raw, [cfx.compartment()])


def test_replacement_composes_away_from_owners_and_never_on_or_from_one():
    parse_spec(replaced([(0.005, "cell_1", "T", "c1_new")]))
    with pytest.raises(ConfigError, match="schedules an event on 'cell_0'"):
        parse_spec(replaced([(0.005, "cell_0", "T", "c0_new")]))
    with pytest.raises(ConfigError, match="names 'cell_0', which owns a compartment, as a donor"):
        parse_spec(replaced([(0.005, "cell_1", None, "c1_new", "cell_0")]))


def test_the_admitted_list_fails_closed(monkeypatch):
    class Newcomer(Operator):
        LAW_ID = "a_future_operator@1"
        EVENT = True

    monkeypatch.setitem(OPERATORS, Newcomer.LAW_ID, Newcomer())
    spec = parse_spec(w())
    model = SimpleNamespace(operators=(*spec.model.operators, SimpleNamespace(law=Newcomer.LAW_ID)))
    experiment = SimpleNamespace(operators=(*spec.experiment.operators, SimpleNamespace(data=())))
    fake = SimpleNamespace(model=model, experiment=experiment)
    with pytest.raises(ConfigError, match="a_future_operator@1 is not on its admitted list"):
        comp.check_definition(fake, spec.model.operators[-1])
    assert set(comp.ADMITTED) <= set(OPERATORS)


# ------------------------------------------------------------------ the structure check

STATE, WATER = "membrane_entity_state@1", "ideal_osmosis_linear_compliance_water@1"
STRUCTURE_REFUSED = {
    "water": ((WATER,), WATER),
    "membrane state": ((STATE,), STATE),
    "insertion@1": ((STATE, "scheduled_membrane_insertion@1"), "scheduled_membrane_insertion@1"),
    "insertion@2": ((STATE, "scheduled_membrane_insertion@2"), "scheduled_membrane_insertion@2"),
    "the partition": ((STATE, "isopotential_partition@1"), "isopotential_partition@1"),
    "lumen@1": (
        (STATE, "scheduled_membrane_insertion@1", "restricted_cleft_lumen@1"),
        "restricted_cleft_lumen@1",
    ),
    "lumen@2": (
        (STATE, "scheduled_membrane_insertion@2", "restricted_cleft_lumen@2"),
        "restricted_cleft_lumen@2",
    ),
    "replacement@2, over water": ((WATER, "scheduled_cell_replacement@2"), WATER),
    "the symport, over water": ((WATER, "k_anion_symport_mass_action@1"), WATER),
}
STRUCTURE_ADMITTED = (
    ("scheduled_species_exchange@1",),
    ("scheduled_species_turnover@1",),
    ("scheduled_species_turnover@1", "scheduled_species_exchange@1"),
    ("local_species_reactions@1",),
    ("species_regulated_availability@1",),
    ("electrode_current_injection@1",),
    ("scheduled_cell_replacement@1",),
    ("scheduled_bath_composition@1",),
)


@pytest.mark.parametrize("name", sorted(STRUCTURE_REFUSED))
def test_the_structure_check_refuses_providers_and_closers_of_what_it_reads(name):
    laws, culprit = STRUCTURE_REFUSED[name]
    for order in ((*laws, LAW), (LAW, *laws)):
        errors = pump_composite.structure_errors(adapter, tuple(OPERATORS[k] for k in order))
        assert any(e.startswith(LAW + " reads") and f"but {culprit} " in e for e in errors), (
            order,
            errors,
        )


@pytest.mark.parametrize("laws", STRUCTURE_ADMITTED, ids="+".join)
def test_the_structure_check_admits_the_operators_it_composes_with(laws):
    for order in ((*laws, LAW), (LAW, *laws)):
        assert pump_composite.structure_errors(adapter, tuple(OPERATORS[k] for k in order)) == []
