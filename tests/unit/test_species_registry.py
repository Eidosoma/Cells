"""The species registry (registry/species_registry.py; D176): one authority per species, and "moved by
the step".

* The catalogue parser moved there, unchanged, and is still importable from membrane_state.
* The model's entries parse (identity, standard_mu_RT at the model's c0, background) with their
  refusals.
* Without entries, identities resolve from the operator blocks: authors (D150's, D152's) before
  users (the coupling operator, FR-3's sites), in declared order; a differing later source is
  refused naming the first, in the pairwise checks' words. With entries, the model is the
  authority.
* A declared background holds against the amounts and the ledger floor; a declared potential is
  read with its standard state.
* moved_in_step names each in-step mover of each species' cell and outside rows: routes, pumps,
  the symport's in-step process; an in-step process that declares nothing is refused.
* The coupling operator refuses an instantaneous read of a row something moves in the step.
* No pairwise identity check is left in src/.
The refusal tests of D150, D152, the coupling operator and FR-3 pass unedited beside these.
"""  # noqa: E501

from dataclasses import dataclass
from pathlib import Path

import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.operators import k_anion_symport, membrane_state
from cells.operators import species_regulated_availability as sra
from cells.registry import species_registry as registry
from validation.tissue import cell_replacement_fixtures as rfx
from validation.tissue import pump_water_fixtures as wfx
from validation.tissue import regulated_availability_fixtures as rf

ROOT = Path(__file__).resolve().parents[2]
TAG = dict(catalogue=dict(catalogue="uniprot", entry="P00001"), evidence="model")


class _Model:
    """A parsed model with a declared registry (the core parser's hook, not yet landed)."""

    def __init__(self, model, declared):
        self._model, self.species_registry = model, declared

    def __getattr__(self, name):
        return getattr(self._model, name)


class _Spec:
    def __init__(self, spec, declared):
        self.model = _Model(spec.model, declared)
        self.experiment, self.execution = spec.experiment, spec.execution


@dataclass(frozen=True)
class _Item:
    id: str
    catalogue: tuple | None
    evidence: str | None


def coupled(*, reverse=False, coupling_tag=None):
    """The coupling sheet: D150's turnover clears R (an author, R unassigned), and a Hill coupling
    reads R (a user, with coupling_tag's identity when given)."""
    raw = rf.with_turnover(rf.sheet(), "cell_0", 0.5)
    hill = rf.hill_coupling(
        "c", "junction", ["junction_0"], "R", "hill_activation", 1e-3, 1.0, side="first"
    )
    raw = rf.with_coupling(raw, species=["R"], couplings=[hill])
    if coupling_tag is not None:
        raw["model"]["operators"][-1]["species"][0].update(coupling_tag)
    if reverse:
        raw["model"]["operators"].reverse()
    return raw


def symport_world():
    """[water, symport] on the replacement fixtures' heredity sheet (one route per membrane)."""
    raw = rfx.heredity_sheet(radius=1, disc=0, dt=1e-3, end_time=0.02)
    return cs.frozen_definition(wfx.with_symport(wfx.with_water(raw)))


def test_the_catalogue_parser_moved_unchanged():
    assert membrane_state.parse_catalogue is registry.parse_catalogue
    assert registry.parse_catalogue(None) is None
    assert registry.parse_catalogue(dict(catalogue="uniprot", entry="P1")) == ("uniprot", "P1")
    with pytest.raises(ConfigError, match="names a catalogue and an entry"):
        registry.parse_catalogue(dict(catalogue="", entry="P1"))


def test_the_model_entries_parse_with_their_refusals():
    background = dict(trace_mM=1e-5, floor_fmol=1e-20)
    declared = registry.build(
        [dict(id="S", identity=TAG, standard_mu_RT=-2.5, background=background), dict(id="P")],
        standard_concentration_mM=1.0,
    )
    s = declared.entry("S")
    assert s.identity == registry.Identity(("uniprot", "P00001"), "model")
    assert (s.standard_mu_RT, declared.standard_concentration_mM) == (-2.5, 1.0)
    assert s.background == registry.Background(1e-5, 1e-20)
    assert declared.entry("P") == registry.Entry("P", None, None, None)
    unassigned = dict(catalogue=None, evidence="model")
    unknown = dict(catalogue=TAG["catalogue"], evidence="guess")
    refusals = {
        "kind of evidence is given with a catalogue": [dict(id="S", identity=unassigned)],
        "records its kind of evidence": [dict(id="S", identity=unknown)],
        "which the model does not declare": [dict(id="S", standard_mu_RT=1.0)],
        "trace_mM must be": [dict(id="S", background=dict(trace_mM=0.0, floor_fmol=1e-20))],
        "lists a species twice": [dict(id="S"), dict(id="S")],
    }
    for message, raw in refusals.items():
        with pytest.raises(ConfigError, match=message):
            registry.build(raw)


def test_without_entries_authors_come_before_users_in_either_order():
    for reverse in (False, True):
        spec = parse_spec(coupled(reverse=reverse))
        resolved = registry.identities(spec)
        assert resolved["R"] == (
            "cells.operator.scheduled_species_turnover@1",
            registry.Identity(None, None),
        )
        with pytest.raises(ConfigError) as caught:
            parse_spec(coupled(reverse=reverse, coupling_tag=TAG))
        assert str(caught.value).endswith(
            "cells.operator.species_regulated_availability@1 declares species 'R' with another "
            "identity than "
            "cells.operator.scheduled_species_turnover@1 (catalogue reference and kind of evidence "
            "must agree)"
        )


def test_with_entries_the_model_is_the_authority():
    spec = parse_spec(coupled())
    tagged = _Spec(spec, registry.build([dict(id="R", identity=TAG)]))
    assert registry.identities(tagged)["R"] == (
        registry.MODEL_SOURCE,
        registry.Identity(("uniprot", "P00001"), "model"),
    )
    turnover = "cells.operator.scheduled_species_turnover@1"
    with pytest.raises(ConfigError, match="another identity than the model's species entries"):
        registry.check_identities(tagged, turnover, (_Item("R", None, None),))
    registry.check_identities(tagged, turnover, (_Item("R", ("uniprot", "P00001"), "model"),))


def test_a_declared_background_and_potential_are_checked_and_read():
    spec = parse_spec(coupled())
    good = registry.build(
        [dict(id="R", background=dict(trace_mM=rf.REGULATOR_mM, floor_fmol=rf.FLOOR_FMOL),
              standard_mu_RT=-1.0)],
        standard_concentration_mM=1.0,
    )  # fmt: skip
    registry.check_background(_Spec(spec, good))
    assert registry.standard_potential(_Spec(spec, good), "R") == (-1.0, 1.0)
    assert registry.standard_potential(_Spec(spec, good), "Na") is None
    high = registry.build(
        [dict(id="R", background=dict(trace_mM=2 * rf.REGULATOR_mM, floor_fmol=rf.FLOOR_FMOL))]
    )
    with pytest.raises(ConfigError, match="below its declared trace"):
        registry.check_background(_Spec(spec, high))
    floor = registry.build(
        [dict(id="R", background=dict(trace_mM=rf.REGULATOR_mM, floor_fmol=1e-19))]
    )
    with pytest.raises(ConfigError, match="is not its material_balance_atol_fmol"):
        registry.check_background(_Spec(spec, floor))


def test_moved_in_step_names_each_mover():
    moved = registry.moved_in_step(parse_spec(coupled()))
    assert moved["R"]["cell"] == ()  # Neutral, no route: nothing moves it in its cells.
    assert any(m.startswith("the Na/K pump on membrane ") for m in moved["Na"]["cell"])
    assert any(m.startswith("the Na/K pump on membrane ") for m in moved["K"]["outside"])
    symport = parse_spec(symport_world())
    process = "cells.operator.k_anion_symport_mass_action@1 (its in-step process)"
    moved = registry.moved_in_step(symport)
    roles = next(d for d in symport.model.operators if d.law == k_anion_symport.LAW_ID)
    for species in (roles.potassium, roles.anion):
        assert process in moved[species]["cell"] and process in moved[species]["outside"]


def test_an_in_step_process_must_declare_what_it_moves(monkeypatch):
    """The contract refuses it at registration (contract.check_declarations, D176's additions):
    the base's moves_in_step moves nothing, so the registry's own check cannot meet one."""
    from cells.operators.contract import check_declarations

    monkeypatch.delattr(k_anion_symport.KAnionSymport, "moves_in_step")
    with pytest.raises(ValueError, match="declares the rows it moves"):
        check_declarations(k_anion_symport.KAnionSymport)


def test_the_coupling_refuses_an_instantaneous_read_of_a_moved_row():
    spec = parse_spec(coupled())
    declaration = next(d for d in spec.model.operators if d.law == sra.LAW_ID)
    sra.check_unmoved_sources(declaration, registry.moved_in_step(spec))
    fuel = {"R": {"cell": ("the Na/K pump on membrane membrane_0",), "outside": ()}}
    with pytest.raises(ConfigError, match="the Na/K pump on membrane membrane_0 moves it inside"):
        sra.check_unmoved_sources(declaration, fuel)


def test_no_pairwise_identity_check_is_left_in_src():
    """The identity refusal is raised in one place: an f-string naming the declaring law and the
    species ("declares species {"), only in the registry."""
    holders = sorted(
        str(path.relative_to(ROOT))
        for path in (ROOT / "src" / "cells").rglob("*.py")
        if "declares species {" in path.read_text()
    )
    assert holders == ["src/cells/registry/species_registry.py"]
