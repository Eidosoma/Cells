"""§5.2's admission of a mover mode at a general closure's rows, its charge half
(registry/species_registry.mode_errors; docs/CORE_SEAMS_DESIGN.md §5.2 and §19 as amended),
against the core-seams references' C3 movers (validation/core_seams/references,
reference_inputs.json seam_c.movers). Each mode is given resolved, as (species, node, count) rows.
- Admitted: the base-form hydrolysis with every ligand written out, and MgATP moved as its base
  row and its ligand.
- Refused: the hydrolysis with its proton omitted (charge -1), MgATP moved as a form (a form
  moved as if it were a row), and a mover whose law declares no base forms.
The moiety half waits for item 6's registry moieties. The resolution of a law's change rows
(registry/laws.cycle_changes, through the kind's role_species) to these rows is entity_modes;
its planted movers are test_rapid_binding_world.py's.

The writers of one row (FR-43 part 3; docs/FR43_PART3_COWRITERS_DESIGN.md §3.2), on stub
operators, host only: a transfer shares a row with a declared writer; a row a writer claims alone
refuses a second writer at its node, and a claim at one node leaves the others; an undeclared split
row writer fails closed. Every built-in split row writer declares, and replacement@1 and @2, which
write amounts at their events only, are none. Plants, refused at registration: a conversion that
declares itself a transfer, and the declarations' other misuses.
"""

import json
from pathlib import Path

import pytest

from cells.definitions.specs import ConfigError
from cells.operators import OPERATORS
from cells.operators import species_turnover as turnover
from cells.operators.contract import Operator, check_declarations, writes_rows
from cells.registry import species_registry as registry

REFS = Path(__file__).resolve().parents[2] / "validation" / "core_seams" / "references"
INPUTS = json.loads((REFS / "reference_inputs.json").read_text())["seam_c"]
MESSAGES = {
    "base_form_hydrolysis_no_proton": r"charge per cycle is -1, not zero",
    "mgatp_as_a_unit": r"moves the forms \['nuc4_Mg'\] as rows",
    "undeclared_mover": r"declares no base forms",
}


def rows_and_forms():
    """{species: valence} over the references' rows (ligands, and each binder at its base form's
    valence), and every binder form's ID that is not a row's own."""
    reg = INPUTS["registry"]
    valence = {s: entry["valence"] for s, entry in reg["species"].items()}
    valence |= {b: entry["base_valence"] for b, entry in reg["binders"].items()}
    forms = {f["id"] for entry in reg["binders"].values() for f in entry["forms"]} - set(valence)
    return valence, forms


@pytest.mark.parametrize("mover", INPUTS["movers"], ids=lambda m: m["id"])
def test_each_registered_mover_meets_its_verdict(mover):
    valence, forms = rows_and_forms()
    rows = tuple((species, node, count) for species, node, count in mover["nu"])
    errors = registry.mode_errors(valence, forms, rows, mover["declares_base_forms"])
    assert (not errors) is (mover["expected"] == "admitted"), errors
    if mover["expected"] == "refused":
        assert any(__import__("re").search(MESSAGES[mover["id"]], e) for e in errors), errors


def test_a_row_the_model_lacks_is_refused():
    """Planted: a mode naming a species that is neither a row nor a form."""
    valence, forms = rows_and_forms()
    errors = registry.mode_errors(valence, forms, (("Zn", "N", 1), ("Zn", "P", -1)), True)
    assert errors and "not rows of the model" in errors[0]


# ------------------------------------------------------------------ the writers of one row

GUARD = "tests.operator.planted_guard@1"
AMOUNTS = ("amount_increment", "extracellular_amount_increment")


def _writer(law, moves, rows=(), claims=(), writes=AMOUNTS):
    """A stub split row writer: its ROW_MOVES (None: undeclared), written rows and claims."""
    attrs = dict(
        LAW_ID=law,
        SPLIT=True,
        RK4="split",
        ROW_MOVES=moves,
        STATE_AXES={"moved_fmol": ["route"]},
        ENTITY_WRITES=dict.fromkeys(writes, ("moved_fmol",)),
    )
    if moves is not None:
        attrs["written_rows"] = lambda self, spec, declaration: tuple(rows)
        attrs["sole_rows"] = lambda self, spec, declaration: tuple(claims)
    return type("Writer", (Operator,), attrs)()


CLAIM = ("S", "cell_0", "a row the guard claims alone")
ROWS = {
    "a transfer shares a row with a declared conversion": (
        [_writer(GUARD, "conversion", [("S", "cell_0")]),
         _writer("tests.operator.transfer@1", "transfer", [("S", "cell_0"), ("S", "ecs_0")])],
        None,
    ),
    "a claimed row refuses a transfer at its node": (
        [_writer(GUARD, "conversion", [("S", "cell_0")], claims=[CLAIM]),
         _writer("tests.operator.transfer@1", "transfer", [("S", "cell_0"), ("S", "ecs_0")])],
        "tests.operator.transfer@1 writes 'S' at cell_0, a row the guard claims alone",
    ),
    "a claim of every node refuses a conversion at another": (
        [_writer(GUARD, "conversion", [("S", "cell_0")], claims=[("S", None, "claimed")]),
         _writer("tests.operator.other@1", "conversion", [("S", "cell_1")])],
        "tests.operator.other@1 writes 'S' at cell_1, claimed",
    ),
    "a claim at one node leaves the others": (
        [_writer(GUARD, "conversion", [("S", "cell_0")], claims=[CLAIM]),
         _writer("tests.operator.other@1", "conversion", [("S", "cell_1")])],
        None,
    ),
    "an undeclared split row writer fails closed": (
        [_writer(GUARD, "conversion", [("S", "cell_0")]),
         _writer("tests.operator.undeclared@1", None, writes=AMOUNTS[:1])],
        "tests.operator.undeclared@1 writes species rows in its half-steps and declares no "
        "ROW_MOVES",
    ),
}  # fmt: skip


@pytest.mark.parametrize("name", sorted(ROWS))
def test_the_writers_of_one_row(name, monkeypatch):
    """species_registry.check_row_writers on stub operators, called by the guard (FR-43 part 3)."""
    operators, message = ROWS[name]
    monkeypatch.setattr(registry, "_entries", lambda spec: tuple((op, None) for op in operators))
    if message is None:
        registry.check_row_writers(None, GUARD)
        return
    with pytest.raises(ConfigError, match=message):
        registry.check_row_writers(None, GUARD)


def test_every_built_in_split_row_writer_declares():
    """The eleven split row writers declare ROW_MOVES, the two transfers among them, and
    replacement@1 and @2, which write amounts at their events only, are none (contract
    .writes_rows: a predicate blind to EVENT_REPLACES would count them, and the gene unit, which
    composes with replacement@1, would refuse it)."""
    writers = {law: op.ROW_MOVES for law, op in OPERATORS.items() if writes_rows(op)}
    assert len(writers) == 11 and None not in writers.values(), writers
    transfers = sorted(law for law, moves in writers.items() if moves == "transfer")
    assert transfers == [
        "cells.operator.integer_unit_population@1",
        "cells.operator.scheduled_species_exchange@1",
    ]
    for law in ("cells.operator.scheduled_cell_replacement@1",
                "cells.operator.scheduled_cell_replacement@2"):  # fmt: skip
        assert "amount_increment" in OPERATORS[law].ENTITY_WRITES and law not in writers


def _turnover_like(**changes):
    """A planted class with turnover's declarations (a conversion booking production and clearance
    in separate accumulators) and none of its hooks, changed as given."""
    base = turnover.ScheduledSpeciesTurnover
    own = ("LAW_ID", "SPLIT", "RK4", "STATE_AXES", "WORK_FIELDS", "ENTITY_WRITES")
    return type("Planted", (Operator,), {k: getattr(base, k) for k in own} | changes)


def _written(self, spec, declaration):
    return ()


MISUSES = {
    "a conversion that declares itself a transfer": (
        dict(ROW_MOVES="transfer", written_rows=_written),
        "a transfer books its writes at the cell and at the outside node in the same accumulators",
    ),
    "an unknown kind of moves": (
        dict(ROW_MOVES="both", written_rows=_written),
        "ROW_MOVES is one of",
    ),
    "a claim without declared moves": (
        dict(sole_rows=lambda self, spec, declaration: ()),
        "are a declared split row writer's",
    ),
    "declared moves without written rows": (
        dict(ROW_MOVES="conversion"),
        "declares the rows it writes",
    ),
}


@pytest.mark.parametrize("name", sorted(MISUSES))
def test_a_misdeclared_row_writer_is_refused_at_registration(name):
    """Plants on a class with turnover's declarations: each misuse of the row declarations is
    refused by the contract's check_declarations, and the same class declared as a conversion with
    its written rows registers."""
    changes, message = MISUSES[name]
    with pytest.raises(ValueError, match=message):
        check_declarations(_turnover_like(**changes))
    check_declarations(_turnover_like(ROW_MOVES="conversion", written_rows=_written))
