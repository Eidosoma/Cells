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
"""

import json
from pathlib import Path

import pytest

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
