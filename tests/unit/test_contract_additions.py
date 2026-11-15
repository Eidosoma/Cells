"""The operators stream's contract additions (D176's round; host side only, no program changes).

/mnt/workspaces/Cells/d172-restructure-20261115-01/operators/CONTRACT_ADDITIONS.md:
* moves_in_step: an operator with an in-step process (PROCESS) declares the rows it moves, refused
  at registration otherwise; the default moves nothing;
* IDENTITY_ROLE ("author" or "user") and species_identities (default: none);
* VIEW_LAYERS (docs/RUN_VIEW_DESIGN.md §3): None (undeclared) or a non-empty tuple of
  {"id", "label", "representation"}, the representation simulated, modelled or prescribed;
* view_events: the default gives the births and retirements of living_intervals with their cells;
* the pending lists: the registered operators still without VIEW_LAYERS, and the event or schedule
  operators still on the default view_events, until each owner declares them (the run-view note's
  test). A newly registered operator must declare both.
* USES_INNER (the lead's ruling): an operator that declares it receives the inner implementation
  object as `inner=` in its device parts and initial_values; every other call is unchanged.
"""

import numpy as np
import pytest

from cells.core.specs import parse_spec
from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.models.operators import OPERATORS
from cells.models.operators.contract import Operator, check_declarations
from cells.models.registry import get_model
from validation.tissue import secreted_species_fixtures as fx

# Registered before the run-view declarations: each owner removes its operator when it declares.
PENDING_LAYERS = frozenset(
    {
        "cell_owned_compartments@1",
        "cytoplasmic_bridge_closure@1",
        "electrode_current_injection@1",
        "ideal_osmosis_linear_compliance_water@1",
        "isopotential_partition@1",
        "k_anion_symport_mass_action@1",
        "local_species_reactions@1",
        "membrane_entity_state@1",
        "restricted_cleft_lumen@1",
        "restricted_cleft_lumen@2",
        "scheduled_bath_composition@1",
        "scheduled_cell_replacement@1",
        "scheduled_cell_replacement@2",
        "scheduled_membrane_insertion@1",
        "scheduled_membrane_insertion@2",
        "scheduled_species_exchange@1",
        "scheduled_species_turnover@1",
        "site_occupancy@1",
        "species_regulated_availability@1",
    }
)
# Those with an event map or a schedule: the default view_events until each declares its own.
PENDING_EVENTS = PENDING_LAYERS - {
    "cell_owned_compartments@1",
    "membrane_entity_state@1",
    "restricted_cleft_lumen@1",
    "restricted_cleft_lumen@2",
}


def operator(**attributes):
    return type("Test", (Operator,), dict(LAW_ID="test_op@1", EVENT=True) | attributes)


def test_an_in_step_process_declares_the_rows_it_moves():
    with pytest.raises(ValueError, match="declares the rows it moves"):
        check_declarations(operator(EVENT=False, PROCESS=True))
    moves = dict(moves_in_step=lambda self, spec, declaration: (("K", "cell"),))
    check_declarations(operator(EVENT=False, PROCESS=True, **moves))
    assert Operator().moves_in_step(None, None) == ()
    for law, op in OPERATORS.items():
        if op.PROCESS:
            assert "moves_in_step" in vars(type(op)), law


@pytest.mark.parametrize("role, ok", [("author", True), ("user", True), ("owner", False)])
def test_the_identity_role(role, ok):
    if ok:
        check_declarations(operator(IDENTITY_ROLE=role))
    else:
        with pytest.raises(ValueError, match="IDENTITY_ROLE is one of"):
            check_declarations(operator(IDENTITY_ROLE=role))
    assert Operator().species_identities(None) == ()


LAYER = dict(id="sites", label="Binding sites", representation="modelled")


@pytest.mark.parametrize(
    "layers, message",
    [
        ((), "a non-empty tuple"),
        ([LAYER], "a non-empty tuple"),
        ((dict(LAYER, extra=1),), "a dict of"),
        ((dict(LAYER, id=""),), "non-empty strings"),
        ((dict(LAYER, representation="guessed"),), "representation is one of"),
    ],
)
def test_view_layers_are_checked_when_declared(layers, message):
    check_declarations(operator(VIEW_LAYERS=None))
    check_declarations(operator(VIEW_LAYERS=(LAYER,)))
    with pytest.raises(ValueError, match=message):
        check_declarations(operator(VIEW_LAYERS=layers))


def test_the_default_view_events_are_the_births_and_retirements():
    lives = {"cell_1": (0.5, None), "cell_0": (None, 0.5), "cell_2": (None, None)}
    op = operator(
        VIEW_LAYERS=(LAYER,), living_intervals=lambda self, spec, declaration, schedule: lives
    )()
    events = op.view_events(None, None, None)
    assert [(e["time"], e["kind"], e["at"], e["layer"]) for e in events] == [
        (0.5, "birth", ({"cells": "cell_1"},), "sites"),
        (0.5, "retirement", ({"cells": "cell_0"},), "sites"),
    ]
    assert Operator().view_events(None, None, None) == ()


def test_the_pending_run_view_declarations_only_shrink():
    """The run-view note's test: an operator registered later declares its layers and, with an
    event map or a schedule, its events; the ones registered before are listed until they do."""
    undeclared = {law for law, op in OPERATORS.items() if op.VIEW_LAYERS is None}
    assert undeclared <= PENDING_LAYERS
    events = {
        law
        for law, op in OPERATORS.items()
        if (op.EVENT or op.EXPERIMENT_KEYS) and "view_events" not in vars(type(op))
    }
    assert events <= PENDING_EVENTS


def test_declarations_may_declare_their_run_view():
    base = dict(LAW_ID="test_declaration@1", DECLARATION_ONLY=True)
    check_declarations(type("D", (Operator,), base | dict(VIEW_LAYERS=(LAYER,))))
    with pytest.raises(ValueError, match="declares IDENTITY_ROLE"):
        check_declarations(type("D", (Operator,), base | dict(IDENTITY_ROLE="user")))


def test_uses_inner_passes_the_inner_object_only_to_declaring_operators():
    seen = {}

    def half_step(self, state, h, control, p, *, xp, inner=None):
        seen[self.LAW_ID] = inner
        return state, None

    parts = dict(EVENT=False, SPLIT=True, RK4="split", half_step=half_step)
    user = check_declarations(
        type("U", (Operator,), dict(LAW_ID="test_user@1", USES_INNER=True) | parts)
    )()
    plain = check_declarations(type("P", (Operator,), dict(LAW_ID="test_plain@1") | parts))()
    composition = pump_composite.Composition(adapter, (user, plain))
    spec = parse_spec(fx.world())
    state, p = get_model(spec.model).initial_values(spec)
    for op in (user, plain):
        composition._half_step(op, state, 0.5e-3, None, p, xp=np)
    assert seen == {"test_user@1": composition.inner, "test_plain@1": None}
    assert composition.inner is adapter
