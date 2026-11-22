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


# ------------------------------------------------------------------ label families (D1)


def _two_node(**charge):
    """The reviewer's two-node diffusion (validation/regions/example.py) with its label rows L and
    U declared one family; charge {row: valence} makes rows charged (each node's anchor kept)."""
    from validation.regions import example

    raw = example.two_node_diffusion()
    raw["model"]["label_families"] = [{"id": "S_labels", "rows": ["L", "U"]}]
    for e in raw["model"]["species"]:
        if e["id"] in charge:
            e["valence"] = charge[e["id"]]
    for node in (*raw["model"]["cells"], *raw["model"]["extracellular"]):
        for row, z in charge.items():
            node["fixed_charge_equivalent_fmol"] -= z * node["initial_amount_fmol"].get(row, 0.0)
    return raw


def test_a_label_family_admits_row_linear_movers_only():
    """D1 (the lead's approval; the Lean lane's finding of 21 November 2026; host only, parses,
    about 4 s). The two-node neutral control is admitted, and its family round-trips. Each refusal
    names its family:
    - L and U charged on the face: logmean_electrodiffusion@1's drift carries the log-mean of a
      row's two ends, which does not add across rows (the Lean lane measured 72.82% of the unsplit
      flux at +10 mV);
    - unequal face diffusivities, unequal standard potentials, unequal valences;
    - a row with registry forms, which a closure would equilibrate;
    - an operator law not shown linear in each row, and turnover clearance differing between rows
      (FR-33's synapse world, validation/regions/example.synapse_world).
    And the membrane and junction route (selective_flux, GHK at the shared voltage) is linear in
    each row: two rows' fluxes sum to the unsplit one."""
    import numpy as np

    from cells.definitions.specs import ConfigError, parse_spec
    from cells.laws.junctions.selective import selective_flux
    from validation.regions import example

    spec = parse_spec(_two_node())
    (family,) = spec.model.species_registry.families
    assert (family.id, family.rows) == ("S_labels", ("L", "U"))
    assert registry.to_entries(spec.model.species_registry)[1]["label_families"] == [
        {"id": "S_labels", "rows": ["L", "U"]}
    ]
    with pytest.raises(ConfigError, match="S_labels: face face_lr moves L by logmean_electrodiff"):
        parse_spec(_two_node(L=1, U=1))
    planted = []
    raw = _two_node()
    raw["model"]["faces"][0]["diffusivity_m2_per_s"]["U"] *= 2.0
    planted.append((raw, "face face_lr's diffusivity_m2_per_s differs"))
    raw = _two_node()
    raw["model"]["standard_concentration_mM"] = 1000.0
    for e in raw["model"]["species"]:
        if e["id"] in ("L", "U"):
            e["standard_mu_RT"] = 0.0 if e["id"] == "L" else 1.0
    planted.append((raw, "standard potentials differ"))
    planted.append((_two_node(L=0, U=-1), "valences differ"))
    raw = _two_node()
    raw["model"]["standard_concentration_mM"] = 1000.0
    for e in raw["model"]["species"]:
        if e["id"] in ("L", "U", "S"):
            e["standard_mu_RT"] = 0.0
    lw = next(e for e in raw["model"]["species"] if e["id"] == "L")
    lw["forms"] = [dict(id="LS", counts={"S": 1}, standard_mu_RT=-1.0)]
    planted.append((raw, "L has (registry )?forms"))  # Or by the forms' own movers rule first.
    for raw, message in planted:
        with pytest.raises(ConfigError, match=message):
            parse_spec(raw)
    parse_spec(example.synapse_world(degrade=0.5))
    uneven = example.synapse_world(degrade=0.5)
    uneven["experiment"]["turnover_controls"][1]["schedule"][0]["rate"] = 0.25
    with pytest.raises(ConfigError, match="family P: scheduled_species_turnover@1's clearance"):
        parse_spec(uneven)
    other = example.synapse_world()
    other["model"]["operators"].append(
        dict(law="scheduled_species_exchange@1", species=[dict(id="S", catalogue=None,
             evidence=None)], routes=[dict(id="x", species="S", patch="contact_1",
             direction="import", law="first_order")], templates=[])
    )  # fmt: skip
    other["experiment"]["exchange_controls"] = [
        dict(route_id="x", carrier_id="cell_0", schedule=[dict(time=0.0, rate=0.0)])
    ]
    with pytest.raises(ConfigError, match="scheduled_species_exchange@1 is composed beside label"):
        parse_spec(other)
    rng = np.random.default_rng(3)
    a1, a2, b1, b2 = rng.uniform(0.1, 2.0, 4)
    for z in (0, 1, -2):
        args = (z, 310.0, 1e-11, 1e-8, 0.0, 1.0, 1.0)
        whole = selective_flux(a1 + a2, b1 + b2, 0.01, *args, xp=np)
        parts = sum(selective_flux(a, b, 0.01, *args, xp=np) for a, b in ((a1, b1), (a2, b2)))
        assert parts == pytest.approx(whole, rel=4 * np.finfo(float).eps), z
