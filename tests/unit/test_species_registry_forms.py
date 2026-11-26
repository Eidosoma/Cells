"""The species registry's hook, absent rows and two-form rows (registry/species_registry.py; D176).

* The core parser's hook (docs/INNER_MODEL_V4_DESIGN.md §7.4 (f) 7): parse_entries pops the
  registry keys from the parser's copy of the model, returns None when the model declares none,
  and to_entries writes the entries back.
* Absent rows (operators/PLAN.md §2.4, accepted 15 November 2026): with a registry declared, a row
  is never an exact zero at a node; the refusal names the background to declare. Without one, the
  inner model's own refusal stands.
* Two-form rows (the lead, 15 November 2026): the row's standard_mu_RT is the base form's at its
  valence z, protonated_standard_mu_RT the form at z + 1. With the proton row's potential they give
  K = c0 exp(mu°_HB - mu°_B - mu°_H): planted round trips to pK 7.2 and 6.0 at c0 = 1000 mM, the
  same K from consistently converted potentials at c0 = 1 mM. A route or reaction naming a two-form
  row is refused.
* Moved by the step reads the inner model's movers from the core's join (surface_pump_v3's
  moved_rows through the structure, §7.4 (f) 6 and (k) 7): the movers are the registry's earlier
  walk's, and a planted kind that moves a two-form row is refused.
"""

import copy
import dataclasses
import math
import re
from types import SimpleNamespace

import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.registry import species_registry as registry
from cells.registry.inventory_species import add_inventory_species
from validation.tissue import cell_replacement_fixtures as rfx
from validation.tissue import regulated_availability_fixtures as rf

LN10 = math.log(10.0)


class _Model:
    """A parsed model with a declared registry (the core's hook is not yet in its parser), with
    attributes overridden as given."""

    def __init__(self, model, declared, **overrides):
        self._model, self.species_registry = model, declared
        self.__dict__.update(overrides)

    def __getattr__(self, name):
        return getattr(self._model, name)


class _Spec:
    def __init__(self, spec, declared, **overrides):
        self.model = _Model(spec.model, declared, **overrides)
        self.experiment, self.execution = spec.experiment, spec.execution


def sheet_with_buffer():
    """The heredity sheet (plain @3, no faces) with a neutral row B at a trace: nothing moves B."""
    raw = rfx.heredity_sheet(radius=1, disc=0, dt=1e-3, end_time=0.02)
    return add_inventory_species(
        raw, "B", trace_mM=1e-6, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
    )


def with_amount(spec, declared, node_id, species, value):
    """spec with one node's amount of one species replaced (a proxy: parse_spec refuses a zero)."""
    row = spec.model.species_ids.index(species)

    def edit(node):
        if node.id != node_id:
            return node
        amounts = list(node.initial_amount_fmol)
        amounts[row] = value
        return dataclasses.replace(node, initial_amount_fmol=tuple(amounts))

    m = spec.model
    return _Spec(
        spec,
        declared,
        cells=tuple(edit(c) for c in m.cells),
        extracellular=tuple(edit(n) for n in m.extracellular),
    )


def forms(c0, mu_b, mu_hb, mu_h, proton_valence=1):
    """A minimal spec: the proton row H and a two-form row B at c0."""
    declared = registry.build(
        [dict(id="H", standard_mu_RT=mu_h),
         dict(id="B", standard_mu_RT=mu_b, protonated_standard_mu_RT=mu_hb)],
        c0,
    )  # fmt: skip
    model = SimpleNamespace(
        species_registry=declared, species_ids=("H", "B"), valence=(proton_valence, -1)
    )
    return SimpleNamespace(model=model)


def planted(pk, c0, mu_b, mu_h):
    """mu°_HB/RT giving pK = pk at c0 (mM): K = 10**(3 - pk) mM = c0 exp(mu_HB - mu_B - mu_H)."""
    return mu_b + mu_h + math.log(10.0 ** (3.0 - pk) / c0)


def test_the_hook_pops_the_registry_keys_and_round_trips():
    raw = dict(
        id="cells.model.resolved_pump_tissue@3",
        standard_concentration_mM=1000.0,
        species=[
            dict(id="H", valence=1, standard_mu_RT=0.0),
            dict(id="B", valence=-1, standard_mu_RT=0.0, protonated_standard_mu_RT=-7.2 * LN10,
                 background=dict(trace_mM=1e-9, floor_fmol=1e-12)),
            dict(id="Na", valence=1),
        ],
    )  # fmt: skip
    declared = registry.parse_entries(raw)
    assert raw["species"] == [
        dict(id="H", valence=1),
        dict(id="B", valence=-1),
        dict(id="Na", valence=1),
    ]
    assert "standard_concentration_mM" not in raw
    b = declared.entry("B")
    assert (b.standard_mu_RT, b.protonated_standard_mu_RT) == (0.0, -7.2 * LN10)
    assert b.background == registry.Background(1e-9, 1e-12)
    assert declared.entry("Na") == registry.Entry("Na", None, None, None)
    species, model = registry.to_entries(declared)
    assert model == dict(standard_concentration_mM=1000.0)
    assert set(species) == {"H", "B"}
    again = registry.build(
        [dict(id=e.id, **species.get(e.id, {})) for e in declared.entries], 1000.0
    )
    assert again == declared
    plain = dict(species=[dict(id="Na", valence=1)])
    assert registry.parse_entries(copy.deepcopy(plain)) is None


def test_an_absent_row_is_a_declared_trace_never_zero():
    spec = parse_spec(sheet_with_buffer())
    cell = spec.model.cells[0].id
    bare = registry.build([dict(id="B")])
    registry.check_background(_Spec(spec, bare))
    for value in (0.0, -1e-30, math.nan):
        with pytest.raises(ConfigError, match=rf"species B: {cell} holds .* fmol\. A row absent"):
            registry.check_background(with_amount(spec, bare, cell, "B", value))
    declared = registry.build([dict(id="B", background=dict(trace_mM=1e-6, floor_fmol=1e-20))])
    registry.check_background(_Spec(spec, declared))
    with pytest.raises(ConfigError, match="below its declared trace"):
        registry.check_background(with_amount(spec, declared, cell, "B", 0.0))
    # Without a registry, the inner model's own refusal stands, unchanged.
    raw = sheet_with_buffer()
    raw["model"]["cells"][0]["initial_amount_fmol"]["B"] = 0.0
    with pytest.raises(ConfigError, match="amount must be finite and positive"):
        parse_spec(raw)


@pytest.mark.parametrize("pk", [7.2, 6.0])
def test_two_form_potentials_give_the_planted_pk_at_any_standard_concentration(pk):
    for mu_b, mu_h in ((0.0, 0.0), (1.3, -0.4)):
        spec = forms(1000.0, mu_b, planted(pk, 1000.0, mu_b, mu_h), mu_h)
        k = registry.dissociation_constant_mM(spec, "B", "H")
        assert math.isclose(k, 10.0 ** (3.0 - pk), rel_tol=1e-12)
        assert math.isclose(registry.pK(spec, "B", "H"), pk, rel_tol=0, abs_tol=1e-12)
        assert registry.standard_potential(spec, "B") == (mu_b, 1000.0)  # The scalar reader.
        # The same species at c0 = 1 mM: every mu°/RT gains ln(1 / 1000); K and pK are unchanged.
        shift = math.log(1.0 / 1000.0)
        moved = forms(1.0, mu_b + shift, planted(pk, 1000.0, mu_b, mu_h) + shift, mu_h + shift)
        assert math.isclose(registry.dissociation_constant_mM(moved, "B", "H"), k, rel_tol=1e-12)
        assert math.isclose(registry.pK(moved, "B", "H"), pk, rel_tol=0, abs_tol=1e-12)


def test_two_form_refusals():
    with pytest.raises(ConfigError, match="without its base form's"):
        registry.build([dict(id="B", protonated_standard_mu_RT=-3.0)], 1000.0)
    with pytest.raises(ConfigError, match="protonated_standard_mu_RT must be a finite number"):
        registry.build([dict(id="B", standard_mu_RT=0.0, protonated_standard_mu_RT=math.inf)], 1.0)
    with pytest.raises(ConfigError, match="the proton row H must have valence"):
        registry.dissociation_constant_mM(
            forms(1000.0, 0.0, -10.0, 0.0, proton_valence=2), "B", "H"
        )
    spec = forms(1000.0, 0.0, -10.0, 0.0)
    with pytest.raises(ConfigError, match="the proton row B cannot have two forms"):
        registry.dissociation_constant_mM(spec, "B", "B")
    bare = SimpleNamespace(
        model=SimpleNamespace(
            species_registry=registry.build(
                [dict(id="H"), dict(id="B", standard_mu_RT=0.0, protonated_standard_mu_RT=-1.0)],
                1000.0,
            ),
            species_ids=("H", "B"),
            valence=(1, -1),
        )
    )
    with pytest.raises(ConfigError, match="the proton row H declares no standard_mu_RT"):
        registry.dissociation_constant_mM(bare, "B", "H")


def test_a_route_or_a_reaction_naming_a_two_form_row_is_refused(monkeypatch):
    spec = parse_spec(sheet_with_buffer())
    two = dict(standard_mu_RT=0.0, protonated_standard_mu_RT=-7.2 * LN10)
    inert = registry.build([dict(id="B", **two)], 1000.0)
    registry.check_definition(_Spec(spec, inert))  # Nothing moves B and no operator names it.
    moved = registry.build([dict(id="Na", **two)], 1000.0)
    with pytest.raises(ConfigError, match="species Na has two forms .* moves its cell rows"):
        registry.check_two_form_rows(_Spec(spec, moved))
    # A reaction's owner: D150's turnover names R on the coupling sheet; nothing moves R in the
    # step there (its in-step movers are the real world's).
    coupled = parse_spec(rf.with_turnover(rf.sheet(), "cell_0", 0.5))
    movers = registry.moved_in_step(coupled)
    assert movers["R"] == {"cell": (), "outside": ()}
    monkeypatch.setattr(registry, "moved_in_step", lambda _: movers)
    tagged = registry.build([dict(id="R", **two)], 1000.0)
    with pytest.raises(
        ConfigError,
        match="species R has two forms .* cells.operator.scheduled_species_turnover@1 names it",
    ):
        registry.check_two_form_rows(_Spec(coupled, tagged))


def walked(spec):
    """The registry's own walk of the inner model before it read the core's join (e66fea95's
    moved_in_step without its operators): {species: {kind: set of movers}}."""
    m = registry._inner_model(spec)
    ids, both = m.species_ids, ("cell", "outside")
    moved = {s: {"cell": set(), "outside": set()} for s in ids}
    for p in m.membranes:
        for row, value in enumerate(p.permeability_m_per_s):
            if value != 0:
                for k in both:
                    moved[ids[row]][k].add(f"membrane {p.id}")
        if p.pump is not None:
            for s in p.pump.roles:
                for k in both:
                    moved[s][k].add(f"the Na/K pump on membrane {p.id}")
        if p.calcium_pump is not None:
            for k in both:
                moved[p.calcium_pump.role][k].add(f"the calcium pump on membrane {p.id}")
    for j in m.junctions:
        for row, value in enumerate(j.permeability_m_per_s):
            if value != 0:
                moved[ids[row]]["cell"].add(f"junction {j.id}")
    for c in m.channels:
        for ion in c.permeant_ions:
            if ion.relative_permeability != 0:
                for k in both:
                    moved[ion.species_id][k].add(f"channel {c.id}")
    for f in m.faces:
        for row, value in enumerate(f.diffusivity_m2_per_s):
            if value != 0:
                moved[ids[row]]["outside"].add(f"face {f.id}")
    return moved


def test_the_core_join_gives_the_registry_walks_movers():
    from validation.tissue import surface_pump_v3_fixtures as v3fx

    for raw in (
        sheet_with_buffer(),  # Junctions, channels, pumps.
        v3fx.definition("release"),  # A calcium pump, padded slots.
        rf.with_turnover(rf.sheet(), "cell_0", 0.5),  # A composite's inner model.
    ):
        spec = parse_spec(raw)
        moved = registry.moved_in_step(spec)
        expected = walked(spec)
        for species, kinds in expected.items():
            for kind, movers in kinds.items():
                assert set(moved[species][kind]) == movers, (species, kind)


def test_a_planted_kind_that_moves_a_two_form_row_is_refused(monkeypatch):
    """A declared kind's moved rows reach moved_in_step through the core's join (§7.4 (k) 7):
    planted here as one more entry of surface_pump_v3.moved_rows, (kind, law, node IDs)."""
    from cells.models import surface_pump_v3

    spec = parse_spec(sheet_with_buffer())
    cell = spec.model.cells[0].id
    two = dict(standard_mu_RT=0.0, protonated_standard_mu_RT=-7.2 * LN10)
    declared = registry.build([dict(id="B", **two)], 1000.0)
    registry.check_two_form_rows(_Spec(spec, declared))  # Today nothing moves B.
    join = surface_pump_v3.moved_rows

    def planted(model):
        rows = dict(join(model))
        rows["B"] = (*rows.get("B", ()), ("planted_kind", "planted_exchange@1", (cell,)))
        return rows

    monkeypatch.setattr(surface_pump_v3, "moved_rows", planted)
    mover = f"planted_kind (planted_exchange@1) at {cell}"
    assert registry.moved_in_step(spec)["B"] == {"cell": (mover,), "outside": ()}
    with pytest.raises(ConfigError, match=rf"species B has two forms .*{re.escape(mover)} moves"):
        registry.check_two_form_rows(_Spec(spec, declared))
