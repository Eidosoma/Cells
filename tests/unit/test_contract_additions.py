"""The operators stream's contract additions (D176's round; host side only, no program changes).

/mnt/workspaces/Cells/d172-restructure-20261115-01/operators/CONTRACT_ADDITIONS.md:
* moves_in_step: an operator with an in-step process (PROCESS) declares the rows it moves, refused
  at registration otherwise; the default moves nothing;
* IDENTITY_ROLE ("author" or "user") and species_identities (default: none);
* VIEW_LAYERS (docs/RUN_VIEW_DESIGN.md §3): None (undeclared) or a non-empty tuple of
  {"id", "label", "representation"}, the representation simulated, modelled or prescribed;
* view_events: the default gives the births and retirements of living_intervals, each at
  {"cell": id};
* the run view's record declarations (view_sets, OBSERVATION_AXES, UNITS, RECORD_KINDS,
  ORIENTATION, RECORD_LAYERS), checked at registration against the operator's own fields;
* the pending lists: the registered operators still without VIEW_LAYERS, and the event or schedule
  operators still on the default view_events, until each owner declares them (the run-view note's
  test). A newly registered operator must declare both.
* USES_INNER (the lead's ruling): an operator that declares it receives the inner implementation
  object as `inner=` in its device parts and initial_values; every other call is unchanged.
"""

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.operators import OPERATORS
from cells.operators.contract import Operator, check_declarations
from cells.registry.models import get_model
from validation.tissue import secreted_species_fixtures as fx

# Registered before the run-view declarations: each owner removes its operator when it declares.
PENDING_LAYERS = frozenset(
    {
        "cells.operator.cell_owned_compartments@1",
        "cells.operator.cytoplasmic_bridge_closure@1",
        "cells.operator.ideal_osmosis_linear_compliance_water@1",
        "cells.operator.isopotential_partition@1",
        "cells.operator.k_anion_symport_mass_action@1",
        "cells.operator.local_species_reactions@1",
        "cells.operator.membrane_entity_state@1",
        "cells.operator.restricted_cleft_lumen@1",
        "cells.operator.restricted_cleft_lumen@2",
        "cells.operator.scheduled_bath_composition@1",
        "cells.operator.scheduled_cell_replacement@1",
        "cells.operator.scheduled_cell_replacement@2",
        "cells.operator.scheduled_membrane_insertion@1",
        "cells.operator.scheduled_membrane_insertion@2",
        "cells.operator.site_occupancy@1",
        "cells.operator.species_regulated_availability@1",
    }
)
# Those with an event map or a schedule: the default view_events until each declares its own
# (D150's two schedules declare their layers already, on the run view's branch).
PENDING_EVENTS = (
    PENDING_LAYERS
    | {"cells.operator.scheduled_species_exchange@1", "cells.operator.scheduled_species_turnover@1"}
) - {
    "cells.operator.cell_owned_compartments@1",
    "cells.operator.membrane_entity_state@1",
    "cells.operator.restricted_cleft_lumen@1",
    "cells.operator.restricted_cleft_lumen@2",
}


def operator(**attributes):
    return type(
        "Test", (Operator,), dict(LAW_ID="cells.operator.test_op@1", EVENT=True) | attributes
    )


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
        (0.5, "birth", {"cell": "cell_1"}, "sites"),
        (0.5, "retirement", {"cell": "cell_0"}, "sites"),
    ]
    assert Operator().view_events(None, None, None) == ()
    assert Operator().view_sets(None, None) == {}


OWN = dict(STATE_AXES={"moved_fmol": ("species", "cell_slot")}, READOUT_COLUMNS=("rate_fmol_s",))
SIGN = {"from": "inside", "to": "outside", "says": "a positive amount leaves the cell"}


@pytest.mark.parametrize(
    "declared, message",
    [
        (dict(OBSERVATION_AXES={"moved_fmol": ("cell_slot",)}), "OBSERVATION_AXES names fields"),
        (dict(OBSERVATION_AXES={"rate_fmol_s": ["cell_slot"]}), "a tuple of axis names"),
        (dict(UNITS={"other_fmol": "fmol"}), "UNITS names fields not its own"),
        (dict(UNITS={"moved_fmol": ""}), "a non-empty unit"),
        (dict(RECORD_KINDS={"moved_fmol": "total"}), "is one of"),
        (dict(ORIENTATION={"moved_fmol": {"from": "inside", "to": "outside"}}), "from, to and"),
        (dict(ORIENTATION={"moved_fmol": dict(SIGN, to="inside")}), "two different roles"),
        (dict(ORIENTATION={"moved_fmol": dict(SIGN, extra="x")}), "from, to and says"),
        (dict(ORIENTATION={"moved_fmol": dict(SIGN, plus="inside")}), "from, to and says"),
        (dict(ORIENTATION={"rate_fmol_s": dict(plus="a", minus="a", says="s")}), "two different"),
        (dict(RECORD_LAYERS={"moved_fmol": "elsewhere"}), "not of its VIEW_LAYERS"),
        (dict(UNITS=[("moved_fmol", "fmol")]), "UNITS maps its own fields"),
    ],
)
def test_the_run_view_record_declarations_are_checked(declared, message):
    whole = dict(
        OBSERVATION_AXES={"rate_fmol_s": ("cell_slot",)},
        UNITS={"moved_fmol": "fmol"},
        RECORD_KINDS={"moved_fmol": "cumulative", "rate_fmol_s": "rate"},
        ORIENTATION={
            "moved_fmol": dict(SIGN, confirmed="its owner"),
            "rate_fmol_s": dict(
                plus="inside", minus="outside", says="inside less outside", source="x"
            ),
        },
        RECORD_LAYERS={"moved_fmol": "sites"},
    )
    check_declarations(operator(**OWN, VIEW_LAYERS=(LAYER,), **whole))
    with pytest.raises(ValueError, match=message):
        check_declarations(operator(**OWN, VIEW_LAYERS=(LAYER,), **declared))


@pytest.mark.parametrize(
    "declared, message",
    [
        (dict(RECORD_DIAGNOSTICS=["rate_fmol_s"]), "a tuple of distinct field names"),
        (dict(RECORD_DIAGNOSTICS=("rate_fmol_s", "rate_fmol_s")), "a tuple of distinct"),
        (dict(RECORD_DIAGNOSTICS=("other_C",)), "RECORD_DIAGNOSTICS names fields not its own"),
        (dict(RECORD_REFERENCES=[("moved_fmol", "moved_reference")]), "maps its own fields"),
        (dict(RECORD_REFERENCES={"rate_fmol_s": "moved_reference"}), "an own state field to"),
        (dict(RECORD_REFERENCES={"moved_fmol": "amount_reference"}), "an own layout field"),
    ],
)
def test_diagnostics_and_references_are_checked(declared, message):
    """RECORD_DIAGNOSTICS (own fields: the step's own check residuals) and RECORD_REFERENCES (an
    own state field stored as an increment over an own layout field), checked at registration
    (the lead's ruling on a loop's closure, 16 November 2026)."""
    own = dict(OWN, LAYOUT_FIELDS=("moved_reference",))
    references = {"moved_fmol": "moved_reference"}
    check_declarations(
        operator(**own, RECORD_DIAGNOSTICS=("rate_fmol_s",), RECORD_REFERENCES=references)
    )
    with pytest.raises(ValueError, match=message):
        check_declarations(operator(**own, **declared))
    assert Operator.RECORD_DIAGNOSTICS == () and dict(Operator.RECORD_REFERENCES) == {}


def test_record_layers_may_name_the_view_fields_it_changes():
    second = dict(LAYER, id="volumes")
    check_declarations(
        operator(
            VIEW_FIELDS=("volume",),
            VIEW_LAYERS=(LAYER, second),
            RECORD_LAYERS={"volume": "volumes"},
        )
    )
    check_declarations(
        operator(CLOSES=("active",), VIEW_LAYERS=(LAYER, second), RECORD_LAYERS={"active": "sites"})
    )
    with pytest.raises(ValueError, match="RECORD_LAYERS names fields not its own"):
        check_declarations(operator(VIEW_LAYERS=(LAYER,), RECORD_LAYERS={"volume": "sites"}))


def test_a_declaration_declares_no_records():
    base = dict(LAW_ID="cells.operator.test_declaration@1", DECLARATION_ONLY=True)
    with pytest.raises(ValueError, match="declares UNITS"):
        check_declarations(type("D", (Operator,), base | dict(UNITS={"x": "1"})))
    with pytest.raises(ValueError, match="overrides view_sets"):
        check_declarations(type("D", (Operator,), base | dict(view_sets=lambda s, a, b: {})))


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


def test_the_injection_declares_its_run_view():
    """cells.operator.electrode_current_injection@1's run view (declared by the run view's owner: ruling 3 of
    docs/LOOPING_REPLAY_DESIGN.md §9): one prescribed layer, every accumulator a total since the
    start, and an event for each scheduled current at its electrode's cell, in time order."""
    from cells.definitions import pump_composite_spec as cs
    from tests.run_view_fixtures import INJECTION, injection_world

    op = OPERATORS[INJECTION]
    assert [layer["representation"] for layer in op.VIEW_LAYERS] == ["prescribed"]
    assert op.RECORD_KINDS == dict.fromkeys(op.STATE_AXES, "cumulative")
    spec = parse_spec(injection_world([(0, 1e-12), (2, -1e-12), (4, 0.0)], end=0.006))
    ((_, declaration, schedule),) = cs.entries(spec)
    events = op.view_events(spec, declaration, schedule)
    cell = spec.model.cells[0].id
    assert [(e["time"], e["kind"], e["at"], e["layer"]) for e in events] == [
        (time, "current", {"cell": cell}, "injection") for time in (0.0, 0.002, 0.004)
    ]
    assert events[1]["label"].endswith(" -1e-12 A")
    assert op.living_intervals(spec, declaration, schedule) == {}


def test_declarations_may_declare_their_run_view():
    base = dict(LAW_ID="cells.operator.test_declaration@1", DECLARATION_ONLY=True)
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
        type("U", (Operator,), dict(LAW_ID="cells.operator.test_user@1", USES_INNER=True) | parts)
    )()
    plain = check_declarations(
        type("P", (Operator,), dict(LAW_ID="cells.operator.test_plain@1") | parts)
    )()
    composition = pump_composite.Composition(adapter, (user, plain))
    spec = parse_spec(fx.world())
    state, p = get_model(spec.model).initial_values(spec)
    for op in (user, plain):
        composition._half_step(op, state, 0.5e-3, None, p, xp=np)
    assert seen == {
        "cells.operator.test_user@1": composition.inner,
        "cells.operator.test_plain@1": None,
    }
    assert composition.inner is adapter
