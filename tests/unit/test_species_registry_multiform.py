"""Multi-form rows in the species registry: seam C's registry forms (registry/species_registry.py,
``forms``; docs/CORE_SEAMS_DESIGN.md §5.1 and §19 item 6).

* The hook pops ``forms`` with the other registry keys, and to_entries writes each form back as
  declared: its keys, its counts in their order, its valence only where given. A definition
  without forms keeps today's entries, key for key (FR-4's world).
* Each refusal names its row and form: the structure, the ligands, isomers, version 1's spelling
  beside the forms, and a declared valence that its counts contradict. A form with counts of both
  signs is admitted (the C4 follow-up: the closure's read checks the exact joint margin).
* One authority: ln beta_f = mu°_base/RT + sum n mu°_L/RT - mu°_f/RT. A two-form row written as
  forms gives version 1's dissociation constant, and the stability's speciation makes each form's
  potential its base's plus its ligands', unchanged when every potential moves to another c0.
* The derived valences z_base + sum n z_L, and the floor counts min_f n_L,f, negative for a form
  below its base.
* A row with forms is inert, as a two-form row is, until a law declares how it moves the forms
  (§5.2's admission, version 2, comes with the closure).

Each test carries a planted error that it must catch (D187). The constants are this file's own
synthetic values (D152 §2.4), not the core-seams references' inputs.
"""

import copy
import json
import math
from types import SimpleNamespace

import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.registry import species_registry as registry
from cells.registry.inventory_species import add_inventory_species
from validation.compartment_ph_engine import definitions as fr
from validation.tissue import cell_replacement_fixtures as rfx

C0 = 1000.0
# A nucleotide-like binder (base valence -4) with forms holding H, Mg or both, and a phosphate-like
# one (base -2) with a form below its base. The MgHN form's counts are declared out of sorted order,
# so a write-back that sorts them is caught.
NUC_FORMS = [
    dict(id="HN", counts={"H": 1}, standard_mu_RT=-15.25),
    dict(id="MgN", counts={"Mg": 1}, standard_mu_RT=-7.5, valence=-2),
    dict(id="MgHN", counts={"Mg": 1, "H": 1}, standard_mu_RT=-21.0),
]
PHOS_FORMS = [
    dict(id="H2P", counts={"H": 1}, standard_mu_RT=-18.0),
    dict(id="P3", counts={"H": -1}, standard_mu_RT=27.5),
    dict(id="MgP", counts={"Mg": 1}, standard_mu_RT=-3.25),
]
VALENCE = dict(H=1, Mg=2, N=-4, P=-2, Na=1)


def raw_model():
    """A model block with two multi-form rows and their ligands (the core parser's copy)."""
    species = [
        dict(id="H", valence=1, standard_mu_RT=0.0),
        dict(id="Mg", valence=2, standard_mu_RT=1.0),
        dict(id="N", valence=-4, standard_mu_RT=3.5, forms=copy.deepcopy(NUC_FORMS)),
        dict(id="P", valence=-2, standard_mu_RT=-1.5, forms=copy.deepcopy(PHOS_FORMS)),
        dict(id="Na", valence=1),
    ]
    return dict(
        id="cells.model.resolved_pump_tissue@3", standard_concentration_mM=C0, species=species
    )


def spec_of(declared):
    """A minimal spec around a registry: the model's species order and valences."""
    ids = tuple(e.id for e in declared.entries)
    model = SimpleNamespace(
        species_registry=declared, species_ids=ids, valence=tuple(VALENCE[s] for s in ids)
    )
    return SimpleNamespace(model=model)


def written_back(raw):
    """raw's model block after the hook and to_entries: the species entries as the model's to_dict
    writes them (the entry left by the hook, updated by its registry keys), and the model keys
    (which the model's to_dict appends to its block)."""
    declared = registry.parse_entries(raw)
    species, keys = registry.to_entries(declared)
    entries = [dict(e, **species.get(e["id"], {})) for e in raw["species"]]
    return entries, keys, declared


def same_bytes(a, b):
    """Equal as JSON text in insertion order: keys, their order and every value."""
    return json.dumps(a) == json.dumps(b)


def test_forms_round_trip_as_declared_and_a_write_back_that_reorders_is_caught(monkeypatch):
    declared_raw = raw_model()
    entries, keys, declared = written_back(copy.deepcopy(declared_raw))
    assert same_bytes(entries, declared_raw["species"])
    assert keys == dict(standard_concentration_mM=C0)
    n = declared.entry("N")
    assert [f.id for f in n.forms] == ["HN", "MgN", "MgHN"]
    assert n.forms[2].counts == (("Mg", 1), ("H", 1))  # Declared order, kept.
    assert (n.forms[1].valence, n.forms[0].valence) == (-2, None)  # Given only where declared.
    assert declared.entry("P").forms[1] == registry.Form("P3", (("H", -1),), 27.5)
    assert declared.entry("H").forms == () and declared.entry("Na") == registry.Entry(
        "Na", None, None, None
    )
    # Planted: a write-back that sorts the counts, and one that drops the declared valence.
    form_to_dict = registry._form_to_dict

    def sorted_counts(form):
        return dict(form_to_dict(form), counts=dict(sorted(form.counts)))

    def no_valence(form):
        return {k: v for k, v in form_to_dict(form).items() if k != "valence"}

    for planted in (sorted_counts, no_valence):
        monkeypatch.setattr(registry, "_form_to_dict", planted)
        assert not same_bytes(written_back(copy.deepcopy(declared_raw))[0], declared_raw["species"])


def registry_keys(entries):
    """Each species entry's registry keys, in their order (the hook's keys only)."""
    return [[(k, e[k]) for k in e if k in registry.REGISTRY_KEYS] for e in entries]


def fr4_written():
    """FR-4's world as its development rungs parse it (@3 and the kinds, without FR-1's operator):
    the builder's model block, the parsed spec and its written species entries."""
    raw = fr.development_world(fr.fr4_world())
    spec = parse_spec(copy.deepcopy(raw))
    return raw, spec, spec.to_dict()["model"]["species"]


def test_a_definition_without_forms_keeps_its_entries_key_for_key(monkeypatch):
    """FR-4's world: its registry keys (two-form buffers, fuel potentials, backgrounds) are
    written back exactly and in order, with no forms key, and its fingerprint survives the round
    trip. Planted: a write-back that gives every row with a potential an empty forms key."""
    raw, spec, written = fr4_written()
    assert same_bytes(registry_keys(written), registry_keys(raw["model"]["species"]))
    assert all("forms" not in entry for entry in written)
    inner = registry.declared(spec) or registry.declared(
        SimpleNamespace(model=registry._inner_model(spec))
    )
    assert all(e.forms == () for e in inner.entries)
    assert parse_spec(spec.to_dict()).fingerprint == spec.fingerprint
    to_entries = registry.to_entries

    def planted(declared):
        species, keys = to_entries(declared)
        return {s: dict(v, forms=[]) for s, v in species.items()}, keys

    monkeypatch.setattr(registry, "to_entries", planted)
    _, _, written = fr4_written()
    assert not same_bytes(registry_keys(written), registry_keys(raw["model"]["species"]))


def _set(path, value):
    """A raw_model() mutation: path = (species ID, "forms", index, key) or (species ID, key)."""

    def edit(raw):
        entry = next(e for e in raw["species"] if e["id"] == path[0])
        target = entry
        for key in path[1:-1]:
            target = target[key]
        if value is DELETE:
            del target[path[-1]]
        else:
            target[path[-1]] = value
        return raw

    return edit


DELETE = object()
REFUSALS = {
    "not a list": (_set(("N", "forms"), {"HN": 1}), "a non-empty list"),
    "empty": (_set(("N", "forms"), []), "a non-empty list"),
    "not an object": (_set(("N", "forms", 0), "HN"), "each form is an object"),
    "unknown key": (_set(("N", "forms", 0, "charge"), -3), r"unknown=\['charge'\]"),
    "no potential": (_set(("N", "forms", 0, "standard_mu_RT"), DELETE), "missing="),
    "empty id": (_set(("N", "forms", 0, "id"), ""), "a non-empty string"),
    "no counts": (_set(("N", "forms", 0, "counts"), {}), "counts map each ligand"),
    "zero count": (_set(("N", "forms", 0, "counts"), {"H": 0}), "a nonzero integer"),
    "bool count": (_set(("N", "forms", 0, "counts"), {"H": True}), "a nonzero integer"),
    "float count": (_set(("N", "forms", 0, "counts"), {"H": 1.0}), "a nonzero integer"),
    "float valence": (_set(("N", "forms", 1, "valence"), -2.0), "its valence is an integer"),
    "infinite potential": (_set(("N", "forms", 0, "standard_mu_RT"), math.inf), "finite number"),
    "no base potential": (_set(("N", "standard_mu_RT"), DELETE), "without its base form's"),
    "both spellings": (_set(("N", "protonated_standard_mu_RT"), -15.25), "both forms and"),
    "a species' id": (_set(("N", "forms", 0, "id"), "Na"), "already a species' or a form's"),
    "another row's form": (_set(("P", "forms", 0, "id"), "HN"), "already a species' or a form's"),
    "unknown ligand": (_set(("N", "forms", 0, "counts"), {"K": 1}), "not another species"),
    "its own ligand": (_set(("N", "forms", 0, "counts"), {"N": 1}), "not another species"),
    "ligand without potential": (
        _set(("N", "forms", 0, "counts"), {"Na": 1}),
        "Na declares no standard_mu_RT",
    ),
    "ligand with forms": (_set(("N", "forms", 0, "counts"), {"P": 1}), "has forms of its own"),
    "isomers": (_set(("N", "forms", 0, "counts"), {"H": 1, "Mg": 1}), "two forms have the counts"),
}


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_each_malformed_form_is_refused_naming_its_row(case):
    edit, message = REFUSALS[case]
    registry.parse_entries(raw_model())  # The control: the declared model is admitted.
    with pytest.raises(ConfigError, match=message):
        registry.parse_entries(edit(raw_model()))


def test_a_form_with_counts_of_both_signs_is_admitted():
    """The C4 follow-up (the lead's ruling, 19 November 2026): a form below its base in one ligand
    and above it in another (mgx_MgmH's H -1, Mg +1 in the references) is admitted, and its
    counts write back as declared. Its validity is the closure's joint margin, at the read."""
    raw = _set(("P", "forms", 1, "counts"), {"H": -1, "Mg": 1})(raw_model())
    declared = registry.parse_entries(raw)
    form = next(f for f in declared.entry("P").forms if f.id == "P3")
    assert dict(form.counts) == {"H": -1, "Mg": 1}


def test_the_stabilities_come_from_the_one_authority():
    declared = registry.parse_entries(raw_model())
    spec = spec_of(declared)
    mu = {e.id: e.standard_mu_RT for e in declared.entries if e.standard_mu_RT is not None}
    logs, c0 = registry.form_log_constants(spec, "N")
    expected = [
        0.0,
        mu["N"] + mu["H"] - (-15.25),
        mu["N"] + mu["Mg"] - (-7.5),
        mu["N"] + mu["Mg"] + mu["H"] - (-21.0),
    ]
    assert c0 == C0
    assert all(math.isclose(a, b, rel_tol=0, abs_tol=4 * math.ulp(30.0)) for a, b in zip(
        logs, expected, strict=True))  # fmt: skip
    # A two-form row written as forms gives version 1's K = c0 exp(mu°_HB - mu°_B - mu°_H).
    mu_b, mu_hb, mu_h = 0.4, -16.2, -0.3
    pair = registry.build(
        [dict(id="H", standard_mu_RT=mu_h),
         dict(id="B", standard_mu_RT=mu_b, protonated_standard_mu_RT=mu_hb),
         dict(id="B2", standard_mu_RT=mu_b,
              forms=[dict(id="HB2", counts={"H": 1}, standard_mu_RT=mu_hb)])],
        C0,
    )  # fmt: skip
    two = SimpleNamespace(
        model=SimpleNamespace(
            species_registry=pair, species_ids=("H", "B", "B2"), valence=(1, -1, -1)
        )
    )
    k_v1 = registry.dissociation_constant_mM(two, "B", "H")
    assert registry.one_step_dissociation_constant_mM(two, "B2") == k_v1  # Bit for bit.
    log_beta = registry.form_log_constants(two, "B2")[0][1]
    k_forms = C0 * math.exp(-log_beta)  # The general path: the exponent's rounding, scaled.
    assert math.isclose(k_forms, k_v1, rel_tol=4 * math.ulp(abs(log_beta)))
    # Planted: the count's sign flipped puts the form below its base, far from version 1's K, and
    # it is no one-step two-form row.
    flipped = registry.build(
        [dict(id="H", standard_mu_RT=mu_h),
         dict(id="B2", standard_mu_RT=mu_b,
              forms=[dict(id="HB2", counts={"H": -1}, standard_mu_RT=mu_hb)])],
        C0,
    )  # fmt: skip
    k_flipped = C0 * math.exp(-registry.form_log_constants(spec_of_ids(flipped), "B2")[0][1])
    assert not math.isclose(k_flipped, k_v1, rel_tol=1e-6)
    with pytest.raises(ConfigError, match="not a one-step two-form row"):
        registry.one_step_dissociation_constant_mM(spec_of_ids(flipped), "B2")


def spec_of_ids(declared):
    ids = tuple(e.id for e in declared.entries)
    valence = {"H": 1, "B": -1, "B2": -1}
    return SimpleNamespace(
        model=SimpleNamespace(
            species_registry=declared, species_ids=ids, valence=tuple(valence[s] for s in ids)
        )
    )


def speciation(spec, row, base_mM, free_mM):
    """Every form's concentration (mM), base first, at a free base form and free ligands, from the
    stabilities: c_f = c_base beta_f prod (x_L / c0)^n_L."""
    logs, c0 = registry.form_log_constants(spec, row)
    out = []
    for (_, counts, _), log_beta in zip(registry.forms_of(spec, row), logs, strict=True):
        exponent = log_beta + sum(n * math.log(free_mM[ligand] / c0) for ligand, n in counts)
        out.append(base_mM * math.exp(exponent))
    return out


def form_potentials_RT(declared, row, concentrations, c0):
    """mu_f/RT = mu°_f/RT + ln(c_f / c0) for every form, base first."""
    entry = declared.entry(row)
    standard = [entry.standard_mu_RT, *(f.standard_mu_RT for f in entry.forms)]
    return [m + math.log(c / c0) for m, c in zip(standard, concentrations, strict=True)]


def test_the_speciation_is_each_forms_equilibrium_at_any_standard_concentration():
    """At the stabilities' speciation, mu_f = mu_base + sum n mu_L for every form: the equilibrium
    the closure solves. Moving every potential to c0 = 1 mM (mu°/RT + ln(1 mM / c0)) gives the same
    concentrations. Planted: moving the forms' potentials but not the base's does not."""
    free = {"H": 6.3e-5, "Mg": 0.8}
    for row, base_mM in (("N", 2.5), ("P", 7.0)):
        declared = registry.parse_entries(raw_model())
        spec = spec_of(declared)
        conc = speciation(spec, row, base_mM, free)
        mu = form_potentials_RT(declared, row, conc, C0)
        ligand = {s: declared.entry(s).standard_mu_RT + math.log(free[s] / C0) for s in free}
        for (_, counts, _), mu_f in zip(registry.forms_of(spec, row), mu, strict=True):
            balance = mu[0] + sum(n * ligand[s] for s, n in counts)
            assert math.isclose(mu_f, balance, rel_tol=0, abs_tol=64 * math.ulp(30.0))
        for shift_base in (True, False):  # The control, then the plant.
            moved = registry.parse_entries(shifted_model(1.0, shift_base))
            again = speciation(spec_of(moved), row, base_mM, free)
            agree = all(math.isclose(a, b, rel_tol=1e-12) for a, b in zip(conc, again, strict=True))
            assert agree is shift_base


def shifted_model(c0, shift_base):
    """raw_model() with every mu°/RT moved to c0 (mu°/RT + ln(c0 / C0)); the binders' base forms
    left unmoved when shift_base is False (the planted error)."""
    raw = raw_model()
    shift = math.log(c0 / C0)
    raw["standard_concentration_mM"] = c0
    for entry in raw["species"]:
        if "standard_mu_RT" in entry and (shift_base or "forms" not in entry):
            entry["standard_mu_RT"] += shift
        for form in entry.get("forms", ()):
            form["standard_mu_RT"] += shift
    return raw


def test_valences_and_floor_counts_are_derived_and_a_contradicting_valence_is_refused():
    declared = registry.parse_entries(raw_model())
    spec = spec_of(declared)
    assert registry.form_valences(spec, "N") == (-4, -3, -2, -1)
    assert registry.form_valences(spec, "P") == (-2, -1, -3, 0)
    assert registry.ligand_floor_counts(spec, "N") == {"H": 0, "Mg": 0}
    assert registry.ligand_floor_counts(spec, "P") == {"H": -1, "Mg": 0}
    registry.check_forms(spec)  # The control: MgN declares -2, which its counts give.
    planted = raw_model()
    planted["species"][2]["forms"][1]["valence"] = -1  # Derived: -4 + 2 = -2.
    with pytest.raises(ConfigError, match=r"form MgN declares valence -1, .* give -2"):
        registry.check_forms(spec_of(registry.parse_entries(planted)))
    with pytest.raises(ConfigError, match="species H declares no forms"):
        registry.form_valences(spec, "H")


class _Model:
    """A parsed model with a declared registry (attributes otherwise the parsed model's)."""

    def __init__(self, model, declared):
        self._model, self.species_registry = model, declared

    def __getattr__(self, name):
        return getattr(self._model, name)


def _spec(spec, declared):
    return SimpleNamespace(
        model=_Model(spec.model, declared), experiment=spec.experiment, execution=spec.execution
    )


def sheet_with_forms(valence=None):
    """The heredity sheet (plain @3, no faces) with a trace row B (valence 0) that nothing moves,
    declared with one form on the ligand K (derived valence +1), and the registry's keys at c0."""
    raw = add_inventory_species(
        rfx.heredity_sheet(radius=1, disc=0, dt=1e-3, end_time=0.02),
        "B", trace_mM=1e-6, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20,
    )  # fmt: skip
    form = dict(id="KB", counts={"K": 1}, standard_mu_RT=-6.0)
    if valence is not None:
        form["valence"] = valence
    m = raw["model"]
    for entry in m["species"]:
        if entry["id"] == "K":
            entry["standard_mu_RT"] = 0.0
        if entry["id"] == "B":
            entry.update(standard_mu_RT=0.0, forms=[form])
    m["standard_concentration_mM"] = C0
    return raw


def test_forms_pass_through_the_inner_models_parser_and_fingerprint():
    """@3's own parse (the registry hook, then check_definition ahead of @3's checks): the forms
    are parsed, written back by the model's to_dict as declared, and the fingerprint survives the
    round trip; a consistent declared valence is part of the definition. Planted: a valence its
    counts contradict is refused by the parser itself."""
    spec = parse_spec(sheet_with_forms())
    assert registry.declared(spec).entry("B").forms == (registry.Form("KB", (("K", 1),), -6.0),)
    written = next(e for e in spec.to_dict()["model"]["species"] if e["id"] == "B")
    assert written["forms"] == [dict(id="KB", counts={"K": 1}, standard_mu_RT=-6.0)]
    assert parse_spec(spec.to_dict()).fingerprint == spec.fingerprint
    assert parse_spec(sheet_with_forms(valence=1)).fingerprint != spec.fingerprint
    with pytest.raises(ConfigError, match=r"form KB declares valence 0, .* give 1"):
        parse_spec(sheet_with_forms(valence=0))


def test_a_row_with_forms_is_inert_until_a_law_declares_its_forms():
    """The heredity sheet with a trace row B that nothing moves, and Na, which its membranes move.
    B with forms on the ligand K is admitted (the control); Na with forms is refused, naming the
    mover, as version 1 refuses a moved two-form row."""
    raw = add_inventory_species(
        rfx.heredity_sheet(radius=1, disc=0, dt=1e-3, end_time=0.02),
        "B", trace_mM=1e-6, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20,
    )  # fmt: skip
    spec = parse_spec(raw)
    form = [dict(id="KX", counts={"K": 1}, standard_mu_RT=-6.0)]
    inert = registry.build(
        [dict(id="K", standard_mu_RT=0.0), dict(id="B", standard_mu_RT=0.0, forms=form)], C0
    )
    registry.check_two_form_rows(_spec(spec, inert))
    moved = registry.build(
        [dict(id="K", standard_mu_RT=0.0), dict(id="Na", standard_mu_RT=0.0, forms=form)], C0
    )
    with pytest.raises(
        ConfigError, match=r"species Na has forms \(KX beside its base\): .+ moves its (cell|outside)"
    ):
        registry.check_two_form_rows(_spec(spec, moved))
