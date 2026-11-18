"""The core's registry hook in @3's parser (docs/INNER_MODEL_V4_DESIGN.md §7.4 (f) 7; D176).

@3's parse pops the species registry's keys from its copy of the model
(species_registry.parse_entries) before @2's strict species parse, keeps the declared registry on
the model (`species_registry`, None when nothing is declared, so to_dict and every fingerprint are
unchanged), runs species_registry.check_definition ahead of @3's own checks, and to_dict writes the
keys back. The families that copy @3's fields carry it: the composite, cell replacement (both
generated from @3's fields) and water@1 and @2 (one field each).
"""

import copy

import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.registry import species_registry as registry
from cells.registry.inventory_species import add_inventory_species
from validation.tissue import cell_replacement_fixtures as rfx
from validation.tissue import pump_water_fixtures as wfx
from validation.tissue import regulated_availability_fixtures as rf

TRACE = dict(trace_mM=1e-6, floor_fmol=1e-20)


def with_b(raw):
    """A neutral inventory row B at a trace in every node, with its ledger floor."""
    return add_inventory_species(raw, "B", diffusivity_m2_per_s=1e-10, **TRACE)


def worlds():
    return {
        "plain": with_b(rfx.heredity_sheet(radius=1, disc=0, dt=1e-3, end_time=0.02)),
        "composite": with_b(rf.with_turnover(rf.sheet(), "cell_0", 0.5)),
        "water": with_b(wfx.with_water(wfx.heredity_cell("D", end_time=0.01), pf_m_s=5e-4)),
    }


def with_registry(raw, background=TRACE):
    """raw with c0 and B's registry keys: its standard potential and its background."""
    raw = copy.deepcopy(raw)
    m = raw["model"]
    m["standard_concentration_mM"] = 1000.0
    for entry in m["species"]:
        if entry["id"] == "B":
            entry["standard_mu_RT"] = -2.0
            entry["background"] = dict(background)
    return raw


@pytest.mark.parametrize("name", ["plain", "composite", "water"])
def test_without_a_registry_nothing_changes(name):
    spec = parse_spec(worlds()[name])
    assert spec.model.species_registry is None
    out = spec.to_dict()
    assert "standard_concentration_mM" not in out["model"]
    assert all(set(entry) == {"id", "valence"} for entry in out["model"]["species"])
    assert parse_spec(out) == spec


@pytest.mark.parametrize("name", ["plain", "composite", "water"])
def test_a_declared_registry_parses_and_round_trips(name):
    spec = parse_spec(with_registry(worlds()[name]))
    declared = spec.model.species_registry
    assert isinstance(declared, registry.Declared)
    assert declared.standard_concentration_mM == 1000.0
    assert declared.entry("B") == registry.Entry(
        "B", None, -2.0, registry.Background(1e-6, 1e-20), None
    )
    assert registry.declared(spec) is declared
    out = spec.to_dict()
    b = next(entry for entry in out["model"]["species"] if entry["id"] == "B")
    assert b == dict(id="B", valence=0, standard_mu_RT=-2.0, background=TRACE)
    assert out["model"]["standard_concentration_mM"] == 1000.0
    assert parse_spec(out) == spec


def test_the_registry_checks_run_in_the_hook():
    raw = with_registry(worlds()["plain"], background=dict(trace_mM=1e-3, floor_fmol=1e-20))
    with pytest.raises(ConfigError, match="below its declared trace"):
        parse_spec(raw)
    raw = with_registry(worlds()["plain"], background=dict(trace_mM=1e-6, floor_fmol=1e-18))
    with pytest.raises(ConfigError, match="is not its material_balance_atol_fmol"):
        parse_spec(raw)


def test_the_registry_refuses_ahead_of_the_models_own_checks(monkeypatch):
    from cells.models import surface_pump_v3

    def own(spec, *, structure=None):
        raise ValueError("@3's own check")

    monkeypatch.setattr(surface_pump_v3, "check_definition", own)
    low = with_registry(worlds()["plain"], background=dict(trace_mM=1e-3, floor_fmol=1e-20))
    with pytest.raises(ConfigError, match="below its declared trace"):
        parse_spec(low)
    with pytest.raises(ConfigError, match="@3's own check"):
        parse_spec(with_registry(worlds()["plain"]))
