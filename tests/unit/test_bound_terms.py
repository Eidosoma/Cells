"""The explicit-rate bound's two closing terms (docs/INNER_MODEL_V4_DESIGN.md §13.6, §7.4 (g) 3).

Finding 3's z = 0 term (neutral_material_rate) and B7's face-free-node term (face_free_node_rate)
join surface_pump.explicit_rate_bound, which @1, @2 and @3 share, at its ordinary constant. The
controls are probe P3's, with known answers from the declared values: a neutral species on a
junction (2 P A / V) and a chloride route on a face-free node's patch (G / C). D150's face-free
world, with no ion route on its free node's patches, gives zero; a node held as the gauge is
excluded (as P5's face-free gauge is); the bound reads both terms.
"""

import dataclasses

import numpy as np

from cells.definitions.specs import parse_spec
from cells.laws.electrochemistry import F, R
from cells.models import surface_kinetic as kinetic
from cells.models import surface_pump as first
from validation.tissue import secreted_species_fixtures as sf

P_NEUTRAL = 1e-9  # m/s, S on the junction (finding 3's case)
P_CL = 1.2e-7  # m/s, Cl on the bounding patch (CLOSED_COMPARTMENT_DESIGN.md §3.4's value)


def neutral_junction():
    raw = sf.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=(),
        contacts=(),
        faces=(),
        junctions=(("junction_0", "cell_0", "cell_1"),),
    )
    raw["model"]["junctions"][0]["permeability_m_per_s"]["S"] = P_NEUTRAL
    return raw


def face_free_chloride():
    raw = sf.face_free()
    patch = next(m for m in raw["model"]["membranes"] if m["id"] == "contact_0")
    patch["permeability_m_per_s"]["Cl"] = P_CL
    return raw


def terms(raw):
    """(T1, T2, the bound) of a definition, the terms on the bound's own layout."""
    spec = parse_spec(raw)
    _, p = kinetic.initial_values(spec)
    slope = F * F / (R * p.temperature)
    gm = (
        slope
        * np.sum(
            p.valence**2
            * p.membrane_permeability
            * np.maximum(
                np.where(p.active, p.amount_reference / p.volume, 0.0)[:, p.membrane_cell],
                np.where(
                    p.outside_active, p.extracellular_amount_reference / p.extracellular_volume, 0.0
                )[:, p.membrane_outside],
            ),
            axis=0,
        )
        * np.where(p.membrane_active, p.membrane_area, 0.0)
    )
    volume = np.where(p.outside_active & ~p.reservoir, p.extracellular_volume * 1e-15, np.inf)
    return (
        first.neutral_material_rate(p, volume),
        first.face_free_node_rate(spec, p, gm),
        first.explicit_rate_bound(spec),
    )


def test_the_neutral_material_term_on_a_junction():
    raw = neutral_junction()
    t1, t2, bound = terms(raw)
    area = raw["model"]["junctions"][0]["area_m2"]
    expected = 2.0 * P_NEUTRAL * area / (1.0 * 1e-15)
    assert abs(t1 - expected) <= 1e-12 * expected
    assert t2 == 0.0
    assert bound >= t1


def test_the_face_free_node_term_on_a_chloride_route():
    t1, t2, bound = terms(face_free_chloride())
    c_max = sf.BATH_mM["Cl"]  # The cell and the node both at the bath's composition.
    expected = (F * F / (R * 310.0)) * P_CL * sf.CONTACT_AREA_M2 * c_max / sf.CONTACT_C_F
    assert abs(t2 - expected) <= 1e-9 * expected
    assert t1 == 0.0
    assert bound >= t2


def test_free_nodes_gauges_and_ion_free_patches():
    t1, t2, _ = terms(sf.face_free())  # D150's face-free world: its free node has no ion route.
    assert (t1, t2) == (0.0, 0.0)
    spec = parse_spec(face_free_chloride())
    _, p = kinetic.initial_values(spec)
    gm = np.ones(p.membrane_area.shape)
    free = [n.id for n in spec.model.extracellular]
    assert first.face_free_node_rate(spec, p, gm) > 0.0
    for node in free:  # The node held as the gauge is excluded, as P5's face-free gauge is.
        gauged = dataclasses.replace(spec, model=dataclasses.replace(spec.model, gauge_reference=node))
        if first.face_free_node_rate(gauged, p, gm) == 0.0:
            break
    else:
        raise AssertionError("no extracellular node, held as the gauge, removed the term")


def test_the_bound_reads_both_terms(monkeypatch):
    raw = face_free_chloride()
    spec = parse_spec(raw)
    base = first.explicit_rate_bound(spec)
    monkeypatch.setattr(first, "neutral_material_rate", lambda p, volume: 7.0 * base)
    assert first.explicit_rate_bound(spec) == 7.0 * base
    monkeypatch.setattr(first, "neutral_material_rate", lambda p, volume: 0.0)
    monkeypatch.setattr(first, "face_free_node_rate", lambda spec, p, gm: 9.0 * base)
    assert first.explicit_rate_bound(spec) == 9.0 * base
