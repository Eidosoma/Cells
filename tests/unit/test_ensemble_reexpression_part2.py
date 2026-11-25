"""The builder's side of the ensemble's re-expression, Part 2: the calcium clusters' definitions,
readouts and tables.

Parse only, and fabricated records: no row compiles or runs a world. The worlds are invented
(sample_part2), and no registered definition is parsed here. Every array is numbered, so that a
swapped index, a turned sign or a shifted axis changes a number that a row holds.
"""

import collections
import copy
import json
import math

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.kinds import passive_routes
from cells.laws.electrochemistry import CHARGE_PER_FMOL, R
from cells.operators import OPERATORS
from cells.registry.models import get_model
from validation.ensemble_reexpression import (
    blocks,
    definitions,
    labels,
    readouts,
    refusals,
    sample_part2,
    stores,
    worlds,
)
from validation.ensemble_reexpression import run as driver
from validation.ensemble_reexpression import table as exporter
from validation.ensemble_reexpression.inputs import BESIDE, Inputs, InputsError, flat
from validation.ensemble_reexpression.pieces import Pieces

SMALL, WHOLE, PAIR = sample_part2.SMALL, sample_part2.WHOLE, sample_part2.PAIR
ONES = [[0.0, 1.0]]
CHILDREN = {  # The four children's forms: which pieces a block has beside its stores.
    "spatial": dict(transport=False, channels=False, ip3=False),
    "plasma": dict(transport=True, channels=False, ip3=False),
    "gated": dict(transport=True, channels=True, ip3=False),
    "ip3": dict(transport=True, channels=True, ip3=True),
}


@pytest.fixture(autouse=True)
def _one_revision(monkeypatch):
    """Where the driver would ask Git, which of these rows none is about."""
    monkeypatch.setattr(driver, "revision", lambda: ("0" * 40, False, "none", "0" * 64))


@pytest.fixture(scope="module")
def invented(tmp_path_factory):
    path = tmp_path_factory.mktemp("inputs") / "inputs_part2.json"
    path.write_text(json.dumps(sample_part2.invented()))
    return Inputs(path)


@pytest.fixture(scope="module")
def whole(invented):
    """(the block, the raw definition, its parsed form) of the world with every piece."""
    world = invented.worlds[WHOLE]
    raw = definitions.ionic(world, 2e-05)
    return world.block, raw, parse_spec(raw).to_dict()


def child(name):
    return flat(sample_part2.blocks(sample_part2.BOTH, **CHILDREN[name]))


def written(block):
    return worlds.write(
        block,
        step=2e-05,
        observation_times=[0.0, 0.0002],
        solver=labels.string("imex"),
        field_solver=labels.string("field_solver_floor"),
    )


# ------------------------------------------------------------------ definitions


def beside(found, block, path=()):
    """The paths of a block that was read back that the block itself does not have."""
    if not (isinstance(found, dict) and isinstance(block, dict)):
        return []
    out = [(*path, key) for key in found if key not in block]
    return out + [
        p for key in found if key in block for p in beside(found[key], block[key], (*path, key))
    ]


@pytest.mark.parametrize("name", CHILDREN)
def test_each_childs_block_is_read_back_from_its_parsed_definition(name):
    """PART2 §2: leaf for leaf, with no departure by the rule and none by the doubles but for what
    is derived, and the strings that §4.3 names, each in its place of the note."""
    block = child(name)
    raw = parse_spec(written(block)).to_dict()
    found = worlds.read(raw)
    assert worlds.departures(found, block) == [] == worlds.departures(found, block, exact=True)
    assert set(found) == set(block) and set(worlds.shown(found)) == {"ionic", *BESIDE} & set(
        worlds.shown(block)
    )
    assert {p[-1] for p in beside(found, block)} == set(stores.OWN)  # A pump's two further keys.
    for cell, node in found["cells"].items():  # By the anchor rule, so not the block's.
        own = block["cells"][cell]["fixed_charge_equivalent_fmol"]
        assert node["fixed_charge_equivalent_fmol"] != own
    declared = labels.declared_strings(raw)
    expected = {"composite_model", "inner_model", "imex", "field_solver_floor", "closure"}
    expected |= {"constant_field", "kv15_mh", "nak_pump_positive", "maintained_fuel"}
    expected |= {"junction_relaxation", "logmean_face", "passive_routes_kind", "transporter_kind"}
    expected |= {"species_condition_kind", "compartment_law", "local_reactions"}
    expected |= {"mass_action_passive", "calcium_pump_positive", "hill_product_factor"}
    expected |= {"passive_constant_field"}
    expected |= {"exchanger_3na_1ca"} if name != "spatial" else set()
    expected |= {"cav12_m2h"} if name in ("gated", "ip3") else set()
    assert set(labels.strings(declared)) == expected
    assert sorted(labels.strings(declared).values()) == declared
    note = labels.note_entry(declared)
    assert (note["model"], note["solver"]) == ("composite_model", "imex")
    assert note["field_solver"] == "field_solver_floor" and "inner_model" in note["laws"]
    assert note["operators"] == ["compartment_law", "local_reactions"]
    assert note["kinds"] == ["passive_routes_kind", "species_condition_kind", "transporter_kind"]
    laws = expected - {"composite_model", "imex", "field_solver_floor", *note["operators"]}
    assert note["laws"] == sorted(laws - set(note["kinds"]))


NA, K, CL, CA, B, CAB, CA2B, IP3, IP3_BUFFER, IP3_BOUND, ATP, ADP, PI = range(13)
ROWS = ["Na", "K", "Cl", "Ca", "B", "CaB", "Ca2B", "IP3", "IP3_buffer", "IP3_bound"]
FUEL = ["ATP", "ADP", "Pi"]
CELLS, REGIONS = ["c_a", "c_b"], ["bath", "shell", "rim"]


def by_id(rows):
    return {row["id"]: row for row in rows}


def test_a_composite_says_the_blocks_names_in_the_engines_words(whole):
    """PART2 §2, read from the raw definition and not through worlds.read, so that a pair of turned
    names, one in the writing and one in the reading, is seen."""
    block, raw, _ = whole
    model = raw["model"]
    assert model["id"] == labels.LABELS["composite_model"]
    assert model["inner_model"] == labels.LABELS["inner_model"]
    assert [s["id"] for s in model["species"]] == [*ROWS, *FUEL]
    assert model["standard_concentration_mM"] == 1.0
    assert [o["law"] for o in model["operators"]] == [
        labels.LABELS["compartment_law"],
        labels.LABELS["local_reactions"],
    ]
    compartments, reactions = model["operators"]
    assert compartments["compartments"] == [
        {"id": f"compartment_{c}", "node": f"store_{c}", "patch": f"store_membrane_{c}"}
        | {"owner": c, "label": None, "reference": None}
        for c in CELLS
    ]
    # The nodes: the stores after the regions, each row of each, the traces and the anchors.
    cells, outside = by_id(model["cells"]), by_id(model["extracellular"])
    assert list(outside) == [*REGIONS, "store_c_a", "store_c_b"]
    valence = {s["id"]: s["valence"] for s in model["species"]}
    for c in CELLS:
        store, node = block["stores"][c], cells[c]
        held = {"ATP": 1.3, "ADP": 0.12, "Pi": 0.14}
        fuel = {s: mM * node["volume_pL"] for s, mM in held.items()}
        own = store["compartments"]["cytosol"]["initial_amount_fmol"]
        assert node["initial_amount_fmol"] == own | fuel
        assert node["initial_charge_C"] == block["cells"][c]["initial_charge_C"]
        er, lumen = store["compartments"]["er"], outside[f"store_{c}"]
        traces = {s: 1e-12 * er["volume_pL"] for s in FUEL}
        assert lumen["initial_amount_fmol"] == er["initial_amount_fmol"] | traces
        assert lumen["volume_pL"] == er["volume_pL"] and lumen["initial_charge_C"] == 0.0
        assert lumen["reservoir"] is False and lumen["boundary_potential_V"] == 0.0
        for entry in (node, lumen):
            content = math.fsum(valence[s] * n for s, n in entry["initial_amount_fmol"].items())
            total = entry["initial_charge_C"] / CHARGE_PER_FMOL - content
            assert entry["fixed_charge_equivalent_fmol"] == total
    for r in REGIONS:
        own, node = block["outside"][r], outside[r]
        traces = {s: 1e-12 * own["volume_pL"] for s in [*ROWS[B:], *FUEL]}
        assert node["initial_amount_fmol"] == own["initial_amount_fmol"] | traces
        assert node["fixed_charge_equivalent_fmol"] == own["fixed_charge_equivalent_fmol"]
    # The patches and the routes: calcium by passive routes alone, the store's K by its own patch.
    membranes = by_id(model["membranes"])
    assert list(membranes) == ["m_a", "m_b", "store_membrane_c_a", "store_membrane_c_b"]
    routes = by_id(model["passive_routes"])
    expected = {}
    for m in ("m_a", "m_b"):
        own = block["membranes"][m]["passive"]["permeability_m_per_s"]
        assert membranes[m]["permeability_m_per_s"] == own | {"Ca": 0.0} | {
            s: 0.0 for s in [*ROWS[B:], *FUEL]
        }
        expected[f"leak_Ca_{m}"] = ("patch", m, own["Ca"], None)
    for c in CELLS:
        own, patch = block["stores"][c]["membrane"], membranes[f"store_membrane_{c}"]
        assert (patch["inside"], patch["outside"]) == (c, f"store_{c}")
        assert patch["area_m2"] == own["area_m2"]
        assert patch["capacitance_F"] == own["capacitance_F"]
        assert patch["pump"] is None and patch["calcium_pump"] is None
        carried = {s: 0.0 for s in [*ROWS, *FUEL]} | {"K": own["permeability_m_per_s"]["K"]}
        assert patch["permeability_m_per_s"] == carried and carried["K"] == 0.9e-07
        leak = own["permeability_m_per_s"]["Ca"]
        expected[f"store_leak_Ca_{c}"] = ("patch", f"store_membrane_{c}", leak, None)
        expected[f"store_release_{c}"] = (
            "patch",
            f"store_membrane_{c}",
            own["release"]["permeability_m_per_s"],
            [f"release_factor_{c}"],
        )
    (junction,) = model["junctions"]
    own = block["junctions"]["j_ab"]["permeability_m_per_s"]
    assert junction["permeability_m_per_s"]["Ca"] == 0.0 != own["Ca"]
    assert junction["permeability_m_per_s"]["K"] == own["K"]
    expected["junction_Ca_j_ab"] = ("junction", "j_ab", own["Ca"], None)
    assert routes == {
        name: {"id": name, host: at, "law": labels.LABELS["passive_constant_field"]}
        | {"species": "Ca", "permeability_m_per_s": value}
        | ({"factors": factors} if factors else {})
        for name, (host, at, value, factors) in expected.items()
    }
    for face in model["faces"]:
        carried = face["diffusivity_m2_per_s"]
        assert carried["Ca"] == 7.7e-10 and not any(carried[s] for s in [*ROWS[B:], *FUEL])
    # The release's factor, the populations, the channels.
    assert model["species_conditions"] == [
        {"id": f"release_factor_{c}", "node": c, "law": labels.LABELS["hill_product_factor"]}
        | {
            "reads": [
                {"species": "Ca", "form": "hill_activation"}
                | {"half_saturation_mM": 0.0012, "hill_coefficient": 2},
                {"species": "Ca", "form": "hill_inhibition"}
                | {"half_saturation_mM": 0.023, "hill_coefficient": 2},
                {"species": "IP3", "form": "hill_activation"}
                | {"half_saturation_mM": 0.00014, "hill_coefficient": 2},
            ]
        }
        for c in CELLS
    ]
    populations = by_id(model["transporters"])
    hosts = {p["id"]: p["host"] for p in model["transporters"]}
    assert hosts == {
        "store_pump_c_a": "store_membrane_c_a",
        "store_pump_c_b": "store_membrane_c_b",
        "calcium_pump_m_a": "m_a",
        "exchanger_m_a": "m_a",
        "calcium_pump_m_b": "m_b",
        "exchanger_m_b": "m_b",
    }
    assert populations["calcium_pump_m_b"]["capacity_fmol_s"] == 0.0021 * 1.3
    assert populations["store_pump_c_a"] == {
        "id": "store_pump_c_a",
        "host": "store_membrane_c_a",
        "law": labels.LABELS["calcium_pump_positive"],
        "orientation": {"N": "a"},
        "capacity_fmol_s": 0.0031,
        "roles": {"role": "Ca", "ATP": "ATP", "ADP": "ADP", "Pi": "Pi"},
        "parameters": {"stoichiometry": 1, "km_role_mM": 0.0012, "km_atp_mM": 0.45},
        "held_rows": [["ATP", "N"], ["ADP", "N"], ["Pi", "N"]],
    }
    assert populations["exchanger_m_a"] == {
        "id": "exchanger_m_a",
        "host": "m_a",
        "law": labels.LABELS["exchanger_3na_1ca"],
        "orientation": {"N": "a"},
        "capacity_fmol_s": 0.0019,
        "roles": {"Na": "Na", "Ca": "Ca"},
        "parameters": {"km_na_mM": 19.0, "km_ca_mM": 0.0011},
        "held_rows": [],
    }
    channels = by_id(model["channels"])
    assert list(channels) == ["k_a", "k_b", "ca_a", "ca_b"]
    assert channels["ca_b"]["permeant_ions"] == [{"species_id": "Ca", "relative_permeability": 1.0}]
    assert channels["ca_b"]["initial_gate"] == [0.22, 0.68]
    assert (channels["ca_b"]["membrane_id"], channels["ca_b"]["abundance"]) == ("m_b", 0.4)
    # The reactions: each once, at both cells or both stores, with the moieties they imply.
    sites = {r["id"]: r["sites"] for r in reactions["reactions"]}
    inside, lumen = {"cells": CELLS}, {"outside": ["store_c_a", "store_c_b"]}
    assert sites == {
        "bind_0_first": inside,
        "bind_0_second": inside,
        "bind_1_first": lumen,
        "bind_1_second": lumen,
        "ip3_binding": inside,
    }
    made = {s["id"]: s["moieties"] for s in reactions["species"]}
    assert made == {
        "Ca": None,
        "B": None,
        "CaB": {"Ca": 1, "B": 1},
        "Ca2B": {"Ca": 2, "B": 1},
        "IP3": None,
        "IP3_buffer": None,
        "IP3_bound": {"IP3": 1, "IP3_buffer": 1},
    }
    potential = {s["id"]: s["standard_mu_RT"] for s in model["species"]}
    for s in reactions["species"]:
        assert s["standard_mu_RT"] == potential[s["id"]]
    assert potential["Na"] == potential["K"] == potential["Ca"] == potential["ATP"] == 0.0
    assert potential["CaB"] == -math.log(700.0) and potential["Pi"] == 0.0
    molar = R * 301.0 * (potential["ADP"] + math.log(1000.0))
    assert molar == pytest.approx(-19123.4, rel=1e-14)
    # The schedules, the tolerances and the execution.
    experiment, execution = raw["experiment"], raw["execution"]
    one = [{"time": 0.0, "availability": 1.0}]
    for key, name, ids in (
        ("membrane_controls", "membrane_id", list(membranes)),
        ("channel_controls", "channel_id", list(channels)),
        ("transporter_controls", "transporter_id", list(populations)),
    ):
        assert experiment[key] == [{name: i, "schedule": one} for i in ids]
    places = {name: at["cells"] if "cells" in at else at["outside"] for name, at in sites.items()}
    assert [(g["reaction_id"], g["site"]) for g in experiment["reaction_controls"]] == [
        (name, node) for name, nodes in places.items() for node in nodes
    ]
    assert all(
        g["schedule"] == [{"time": 0.0, "multiplier": 1.0}] for g in experiment["reaction_controls"]
    )
    assert execution["material_balance_atol_fmol"] == {
        **{s: 3e-11 for s in ("Na", "K", "Cl")},
        **{s: 1e-10 for s in [*ROWS[CA:], *FUEL]},
    }
    assert execution["solver"] == labels.LABELS["imex"]
    assert execution["field_solver"] == labels.LABELS["field_solver_floor"]
    sizes = ("extracellular_capacity", "membrane_capacity", "channel_capacity", "capacity")
    assert [execution[k] for k in sizes] == [5, 4, 4, 2]


def _entity(rows, name):
    return by_id(rows)[name]


def _times(schedule, time, value, key="availability"):
    schedule.append({"time": time, key: value})


DRIFTS = {
    "the release's permeability": lambda m, e: _entity(
        m["passive_routes"], "store_release_c_b"
    ).update(permeability_m_per_s=np.nextafter(1.3e-07 * 1.3, 1.0)),
    "calcium's plasma leak": lambda m, e: _entity(m["passive_routes"], "leak_Ca_m_a").update(
        permeability_m_per_s=5.3e-08
    ),
    "two leaks exchanged": lambda m, e: (
        _entity(m["passive_routes"], "leak_Ca_m_a").update(patch="m_b"),
        _entity(m["passive_routes"], "leak_Ca_m_b").update(patch="m_a"),
    ),
    "the junction's route left out": lambda m, e: m["passive_routes"].remove(
        _entity(m["passive_routes"], "junction_Ca_j_ab")
    ),
    "the store's K": lambda m, e: _entity(m["membranes"], "store_membrane_c_a")[
        "permeability_m_per_s"
    ].update(K=0.8e-07),
    "the store's capacitance": lambda m, e: _entity(m["membranes"], "store_membrane_c_a").update(
        capacitance_F=1.2e-11
    ),
    "the store's volume": lambda m, e: _entity(m["extracellular"], "store_c_a").update(
        volume_pL=0.07
    ),
    "the factor's two constants exchanged": lambda m, e: (
        m["species_conditions"][0]["reads"][0].update(half_saturation_mM=0.023),
        m["species_conditions"][0]["reads"][1].update(half_saturation_mM=0.0012),
    ),
    "the factor's further read": lambda m, e: m["species_conditions"][1]["reads"][2].update(
        hill_coefficient=3
    ),
    "a pump's capacity": lambda m, e: m["transporters"][0].update(capacity_fmol_s=0.0030),
    "a pump's constant": lambda m, e: m["transporters"][2]["parameters"].update(km_role_mM=0.0011),
    "the pump's free energy": lambda m, e: _entity(m["species"], "ADP").update(
        standard_mu_RT=_entity(m["species"], "ADP")["standard_mu_RT"] * (1 + 1e-11)
    ),
    "the fuel at one cell": lambda m, e: m["cells"][1]["initial_amount_fmol"].update(ATP=0.79),
    "an exchanger's constant": lambda m, e: m["transporters"][3]["parameters"].update(
        km_na_mM=20.0
    ),
    "a calcium channel's abundance": lambda m, e: _entity(m["channels"], "ca_a").update(
        abundance=0.4
    ),
    "a calcium channel's membrane": lambda m, e: _entity(m["channels"], "ca_a").update(
        membrane_id="m_b"
    ),
    "a reaction's rate": lambda m, e: m["operators"][1]["reactions"][4].update(
        forward_rate_per_s=16000.0
    ),
    "a reaction at one cell alone": lambda m, e: (
        m["operators"][1]["reactions"][0]["sites"].update(cells=["c_a"]),
        e["reaction_controls"].remove(
            next(
                g
                for g in e["reaction_controls"]
                if (g["reaction_id"], g["site"]) == ("bind_0_first", "c_b")
            )
        ),
    ),
    "a standard potential": lambda m, e: (
        _entity(m["species"], "CaB").update(standard_mu_RT=-6.0),
        _entity(m["operators"][1]["species"], "CaB").update(standard_mu_RT=-6.0),
    ),
    "the buffer in the cytosol": lambda m, e: m["cells"][0]["initial_amount_fmol"].update(B=0.05),
    "the store's schedule": lambda m, e: _times(
        _entity_of(e["membrane_controls"], "membrane_id", "store_membrane_c_b"), 8e-05, 0.5
    ),
    "a pump's schedule": lambda m, e: _times(
        _entity_of(e["transporter_controls"], "transporter_id", "store_pump_c_a"), 8e-05, 0.5
    ),
    "an exchanger's schedule": lambda m, e: _times(
        _entity_of(e["transporter_controls"], "transporter_id", "exchanger_m_b"), 8e-05, 0.5
    ),
    "a calcium channel's schedule": lambda m, e: _times(
        _entity_of(e["channel_controls"], "channel_id", "ca_b"), 8e-05, 0.5
    ),
    "a reaction's schedule": lambda m, e: _times(
        _entity_of(e["reaction_controls"], "site", "store_c_b"), 8e-05, 0.5, "multiplier"
    ),
    "the trace is recorded, and no drift": None,
}


def _entity_of(groups, key, name):
    return next(g for g in groups if g[key] == name)["schedule"]


@pytest.mark.parametrize("drift", DRIFTS)
def test_a_composite_that_drifts_from_its_block_is_found(whole, drift):
    """Plants: each changed definition parses, and its block departs from the registered one by the
    rule or by the doubles."""
    block, raw, _ = whole
    raw = copy.deepcopy(raw)
    if DRIFTS[drift] is None:
        raw["model"]["extracellular"][3]["initial_amount_fmol"]["ATP"] = 2e-14
        raw["model"]["extracellular"][1]["initial_amount_fmol"]["Pi"] = 2e-14
    else:
        DRIFTS[drift](raw["model"], raw["experiment"])
        stores.anchor(raw)
    found = worlds.read(parse_spec(raw).to_dict())
    faults = definitions.block_faults(found, block, "run", driven=False)
    assert bool(faults) is (DRIFTS[drift] is not None), faults


def _extra_route(**more):
    route = {"id": "another", "law": labels.LABELS["passive_constant_field"], "species": "Ca"}
    return route | {"permeability_m_per_s": 1e-09} | more


UNPLACED = {
    "a second leak of a membrane": lambda m: m["passive_routes"].append(_extra_route(patch="m_a")),
    "a second leak of a store": lambda m: m["passive_routes"].append(
        _extra_route(patch="store_membrane_c_a")
    ),
    "a second route of the junction": lambda m: m["passive_routes"].append(
        _extra_route(junction="j_ab")
    ),
    "a leak with the release's factor": lambda m: _entity(
        m["passive_routes"], "leak_Ca_m_a"
    ).update(factors=["release_factor_c_a"]),
    "a release that reads the other cell": lambda m: (
        _entity(m["passive_routes"], "store_release_c_a").update(factors=["release_factor_c_b"]),
        m["species_conditions"].pop(0),
    ),
    "a pump with N at its store": lambda m: m["transporters"][0].update(orientation={"N": "b"}),
    "a condition that nothing names": lambda m: m["species_conditions"].append(
        m["species_conditions"][0] | {"id": "another"}
    ),
    "a one-way record": lambda m: m["transporters"][2].update(one_way=True),
    "a release of two factors": lambda m: _entity(m["passive_routes"], "store_release_c_a").update(
        factors=["release_factor_c_a", "release_factor_c_b"]
    ),
    "a factor read in the other cell": lambda m: m["species_conditions"][0].update(node="c_b"),
    "a release's one-way record": lambda m: _entity(
        m["passive_routes"], "store_release_c_a"
    ).update(one_way=True),
    "a leak's one-way record": lambda m: _entity(m["passive_routes"], "leak_Ca_m_b").update(
        one_way=True
    ),
    "a store leak's one-way record": lambda m: _entity(
        m["passive_routes"], "store_leak_Ca_c_b"
    ).update(one_way=True),
    "an exchanger with N outside": lambda m: m["transporters"][3].update(orientation={"N": "b"}),
    "a factor of an activation alone": lambda m: m["species_conditions"][0]["reads"].pop(1),
    "a factor with a second further read": lambda m: m["species_conditions"][0]["reads"].append(
        m["species_conditions"][0]["reads"][2] | {"species": "B"}
    ),
}
UNREADABLE = {  # What the engine refuses too, so that the declaration as submitted is read.
    "a store's calcium by its own patch too": lambda m: _entity(
        m["membranes"], "store_membrane_c_a"
    )["permeability_m_per_s"].update(Ca=1e-08),
    "a membrane's calcium by its own route too": lambda m: _entity(m["membranes"], "m_b")[
        "permeability_m_per_s"
    ].update(Ca=1e-08),
    "the junction's calcium by its own route too": lambda m: m["junctions"][0][
        "permeability_m_per_s"
    ].update(Ca=1e-08),
    "a held store": lambda m: _entity(m["extracellular"], "store_c_b").update(reservoir=True),
    "an operator that no block has": lambda m: m["operators"].append({"law": "another@1"}),
    "a second store of a cell": lambda m: m["operators"][0]["compartments"].append(
        m["operators"][0]["compartments"][0] | {"id": "another", "node": "rim", "patch": "m_b"}
    ),
    "a reaction at a region": lambda m: m["operators"][1]["reactions"][2]["sites"].update(
        outside=["rim"]
    ),
    "a pump of another stoichiometry": lambda m: m["transporters"][1]["parameters"].update(
        stoichiometry=2
    ),
    "a route of another species": lambda m: m["passive_routes"].append(
        _extra_route(patch="m_a", species="B")
    ),
    "a route of another law": lambda m: _entity(m["passive_routes"], "leak_Ca_m_a").update(
        law="passive_neutral_permeation@1"
    ),
    "a second pump of a store": lambda m: m["transporters"].append(
        m["transporters"][0] | {"id": "another"}
    ),
    "a pump with a store's host": lambda m: m["transporters"][3].update(host="store_membrane_c_a"),
    "a reaction with a factor": lambda m: m["operators"][1]["reactions"][0].update(factors=[1]),
    "a row with a background": lambda m: _entity(m["species"], "B").update(background={}),
}


@pytest.mark.parametrize("piece", UNPLACED)
def test_a_piece_that_a_block_has_no_place_for_is_refused_by_name(whole, piece):
    """A composite's extra piece is read back under no name, so its block is not written."""
    _, raw, _ = whole
    raw = copy.deepcopy(raw)
    UNPLACED[piece](raw["model"])
    found = exporter.readable(exporter.block, parse_spec(raw).to_dict())
    assert list(found) == ["unreadable"] and "no_section: " in found["unreadable"]


@pytest.mark.parametrize("piece", UNREADABLE)
def test_a_declaration_that_a_block_has_no_place_for_is_refused_by_name(whole, piece):
    """The same of a declaration that the engine refuses, which is read as it was submitted."""
    _, raw, _ = whole
    raw = copy.deepcopy(raw)
    UNREADABLE[piece](raw["model"])
    found = exporter.readable(exporter.block, raw)
    assert list(found) == ["unreadable"] and "no_section: " in found["unreadable"], found


BROKEN = {
    "another fuel in one pump": lambda b: b["plasma_transport"]["m_a"]["pump"].update(atp_mM=1.2),
    "another energy in one pump": lambda b: b["plasma_transport"]["m_a"]["pump"].update(
        delta_g0_at_1M_J_per_mol=-19000.0
    ),
    "a store's schedules that differ": lambda b: b["calcium_controls"]["store_release"].update(
        c_a=[[0.0, 1.0], [8e-05, 0.5]]
    ),
    "two leaks' schedules that differ": lambda b: b["calcium_controls"]["store_passive"][
        "c_b"
    ].update(K=[[0.0, 1.0], [8e-05, 0.5]]),
    "a store's own temperature": lambda b: b["stores"]["c_b"].update(temperature_K=300.0),
    "the stores' temperature": lambda b: [
        s.update(temperature_K=300.0) for s in b["stores"].values()
    ],
    "another species in one store": lambda b: b["stores"]["c_b"].update(
        species=b["stores"]["c_b"]["species"] | {"X": {"valence": 0, "standard_mu_RT": 0.0}}
    ),
    "a cytosol that is not its cell": lambda b: b["stores"]["c_a"]["compartments"]["cytosol"][
        "initial_amount_fmol"
    ].update(K=100.0),
    "a cytosol of another volume": lambda b: b["stores"]["c_a"]["compartments"]["cytosol"].update(
        volume_pL=0.9
    ),
    "a row of two valences": lambda b: [
        s["species"]["K"].update(valence=2) for s in b["stores"].values()
    ],
    "a charged store": lambda b: b["stores"]["c_a"]["membrane"].update(initial_charge_C=1e-15),
    "a field with no place": lambda b: b["stores"]["c_a"]["membrane"].update(colour=1),
    "a control with no place": lambda b: b["calcium_controls"].update(nothing={}),
    "a control of no piece": lambda b: b["calcium_controls"]["exchanger"].update(
        m_c=[[0.0, 1.0], [8e-05, 0.5]]
    ),
    "a control of no reaction": lambda b: b["calcium_controls"]["reactions"]["c_a"].update(
        bind_9=[[0.0, 1.0], [8e-05, 0.5]]
    ),
    "a control of no store": lambda b: b["calcium_controls"]["store_passive"].update(
        c_c={"Ca": [[0.0, 1.0], [8e-05, 0.5]]}
    ),
    "a reaction that differs by cell": lambda b: b["stores"]["c_b"]["reactions"][
        "bind_0_first"
    ].update(forward_rate_per_s=1.0),
    "a further read of another law": lambda b: b["ip3_release"]["c_a"].update(law="cav12_m2h"),
    "a further read without a release": lambda b: b["stores"]["c_a"]["membrane"].update(
        release=None
    ),
    "a world without stores": lambda b: b.pop("stores"),
}


@pytest.mark.parametrize("broken", BROKEN)
def test_a_block_that_one_definition_cannot_hold_is_refused_by_name(whole, broken):
    """Nothing in a block is dropped or averaged in silence (the lead's answers 4 and 7)."""
    block = copy.deepcopy(whole[0])
    BROKEN[broken](block)
    with pytest.raises(blocks.NoSection, match="no_section: "):
        written(block)


def test_a_volume_that_takes_no_round_trip_is_no_fault_of_the_held_fuel(whole):
    """A pump's fuel is held as mM times the volume and read back over it: at 0.7 pL none of these
    numbers comes back as its own double, and the rule's 1e-12 holds. Any other leaf is exact."""
    assert all(mM * 0.7 / 0.7 != mM for mM in (1.5, 0.1))
    block = copy.deepcopy(whole[0])
    block["cells"]["c_b"]["volume_pL"] = 0.7
    block["stores"]["c_b"]["compartments"]["cytosol"]["volume_pL"] = 0.7
    pumps = [block["stores"]["c_b"]["membrane"]["pump"], block["plasma_transport"]["m_b"]["pump"]]
    for pump in pumps:
        pump.update(atp_mM=1.5, adp_mM=0.1, pi_mM=0.1)
    found = worlds.read(parse_spec(written(block)).to_dict())
    assert found["stores"]["c_b"]["membrane"]["pump"]["atp_mM"] != 1.5
    assert definitions.block_faults(found, block, "run", driven=False) == []
    for path, value in (("atp_mM", 1.5 * (1 + 2e-12)), ("km_atp_mM", np.nextafter(0.45, 1.0))):
        moved = copy.deepcopy(found)
        moved["plasma_transport"]["m_b"]["pump"][path] = value
        assert definitions.block_faults(moved, block, "run", driven=False) != []


def test_the_echo_of_a_pumps_energy_and_of_part_2s_defaults(whole):
    """PART2 §2.4: 1e-12 of itself plus 16 eps R T A, A at most 3,200; an omitted zero permeability
    and an omitted schedule refuse nothing, and a declared zero is exactly zero."""
    block, _, parsed = whole
    found = worlds.read(parsed)
    energy = block["stores"]["c_a"]["membrane"]["pump"]["delta_g0_at_1M_J_per_mol"]

    def departs(value, fuel=None):
        moved = copy.deepcopy(found)
        pump = moved["stores"]["c_a"]["membrane"]["pump"]
        pump["delta_g0_at_1M_J_per_mol"] = value
        if fuel is not None:
            pump["fuel_standard_mu_RT"] = fuel
        return [path for path, _, _ in worlds.departures(moved, block)] != []

    assert not departs(energy * (1 + 5e-13)) and departs(energy * (1 + 2e-12))
    large = {"ATP": 1500.0, "ADP": 1500.0, "Pi": 100.0}
    wide = 16 * 2.0**-52 * R * 301.0 * (3100.0 + math.log(1000.0)) + 1e-12 * abs(energy)
    assert wide > 2e-12 * abs(energy)
    assert not departs(energy + 0.99 * wide, large) and departs(energy + 1.01 * wide, large)
    assert departs(energy, large | {"Pi": 200.0})  # A above 3,200.
    own = found["stores"]["c_a"]["membrane"]["pump"]
    size = sum(abs(v) for v in own["fuel_standard_mu_RT"].values()) + math.log(1000.0)
    assert size < 30.0 and own["standard_concentration_mM"] == 1.0
    assert set(own) - set(block["stores"]["c_a"]["membrane"]["pump"]) == set(stores.OWN)
    short = copy.deepcopy(found)
    del short["calcium_controls"]
    for store in short["stores"].values():
        carried = store["membrane"]["permeability_m_per_s"]
        store["membrane"]["permeability_m_per_s"] = {s: v for s, v in carried.items() if v}
    assert worlds.departures(short, block) == []
    # A default written out for a piece that is not there says nothing, as in Part 1.
    told = copy.deepcopy(block)
    own = told["calcium_controls"]
    own["store_pump"]["c_c"] = own["exchanger"]["m_c"] = own["calcium_channel"]["ca_c"] = ONES
    own["reactions"]["c_a"]["bind_9"] = own["store_passive"]["c_a"]["Na"] = ONES
    own["reactions"]["c_c"] = own["store_passive"]["c_c"] = {"x": ONES}
    assert written(told) == written(block)
    assert worlds.departures(told, block) == [] == worlds.departures(block, told)
    own["calcium_pump"]["m_a"] = [[0.0, 1.0], [8e-05, 0.5]]
    assert [p for p, _, _ in worlds.departures(told, block)] == [
        ("calcium_controls", "calcium_pump", "m_a")
    ]
    for path in (("species", "B", "standard_mu_RT"), ("species", "K", "standard_mu_RT")):
        moved = copy.deepcopy(found)
        moved["stores"]["c_b"][path[0]][path[1]][path[2]] = 1e-300
        assert worlds.departures(moved, block) != []


def told(atp, pi, *, off=0.0):
    """Potentials of the fuel rows whose combination is the invented pumps' free energy at 1 M."""
    adp = -19123.4 / (R * 301.0) - math.log(1000.0) + atp - pi
    return {"ATP": atp, "ADP": adp + off, "Pi": pi}


def with_potentials(invented, fuel, **more):
    """The inputs, with a world's entry that gives its fuel's potentials beside `p`."""
    raw = copy.deepcopy(invented.raw)
    raw["worlds"][WHOLE] |= {"fuel_standard_mu_RT": fuel} | more
    path = invented.path.with_name("told.json")
    path.write_text(json.dumps(raw))
    return Inputs(path)


def test_a_world_may_give_its_fuel_rows_potentials(invented, whole):
    """The lead's request for the rehearsal: potentials that are large against their difference (A
    between a half and the whole of its cap) are declared as given, the engine's drive follows their
    combination, the exporter echoes them, and nothing else of the definition moves."""
    block, raw, parsed = whole
    fuel = told(1000.0, 400.0)
    size = sum(map(abs, fuel.values())) + math.log(1000.0)
    assert 1600.0 <= size <= 3200.0
    inputs = with_potentials(invented, fuel)
    world = inputs.worlds[WHOLE]
    assert world.block == block and "fuel_standard_mu_RT" not in world.root
    own = definitions.ionic(world, 2e-05)
    potentials = {s["id"]: s["standard_mu_RT"] for s in own["model"]["species"]}
    assert {s: potentials[s] for s in FUEL} == fuel
    plain = copy.deepcopy(own)
    for entry in plain["model"]["species"]:
        if entry["id"] in FUEL:
            default = _entity(raw["model"]["species"], entry["id"])
            entry["standard_mu_RT"] = default["standard_mu_RT"]
    assert plain == raw
    spec = parse_spec(own)
    found = worlds.read(spec.to_dict())
    pumps = [s["membrane"]["pump"] for s in found["stores"].values()]
    pumps += [t["pump"] for t in found["plasma_transport"].values()]
    assert len(pumps) == 4 and all(pump["fuel_standard_mu_RT"] == fuel for pump in pumps)
    assert definitions.block_faults(found, block, "run", driven=False) == []
    run = inputs.run(f"{WHOLE} h=2e-05")
    assert definitions.check(inputs, runs=[run])[0] == []
    # The engine's own drive, from the two declarations: the same within the tolerance's own term.
    drives = []
    for made in (spec, parse_spec(parsed)):
        _, p = get_model(made.model).initial_values(made)
        drives.append(np.asarray(p.cycle_held_standard_RT) + np.asarray(p.cycle_moved_standard_RT))
    assert drives[0].shape == (1, 6) and np.abs(drives[0]).max() > 10.0
    assert np.abs(drives[0] - drives[1]).max() <= 16 * 2.0**-52 * size
    assert invented.worlds[WHOLE].told == {} and world.told == {"fuel_standard_mu_RT": fuel}


TOLD = {
    "a combination off by more than the tolerance": told(1000.0, 400.0, off=2e-11),
    "A above its cap": told(1800.0, 200.0),
    "two numbers": {"ATP": 0.0, "ADP": -14.5},
    "a fourth number": told(10.0, 0.0) | {"AMP": 0.0},
    "a number that is none": told(10.0, 0.0) | {"Pi": math.nan},
    "a sentence": "as the engine's",
    "none": None,
}


@pytest.mark.parametrize("fuel", TOLD)
def test_potentials_that_do_not_make_the_blocks_energy_are_refused_by_name(invented, fuel):
    """A world whose combination misses the block's energy at 1 M by more than PART2 §2.4's
    tolerance, or whose A is above 3,200, is refused before the engine sees it."""
    inputs = with_potentials(invented, TOLD[fuel])
    with pytest.raises(blocks.NoSection, match="no_section: .*fuel_standard_mu_RT"):
        definitions.definition(inputs, inputs.run(f"{WHOLE} h=2e-05"))


def test_potentials_at_the_tolerances_edge_and_of_no_pump(invented, whole):
    """The tolerance is the criteria's, not a smaller one; and potentials that nothing would read
    are not passed over."""
    fuel = told(1000.0, 400.0)
    size = sum(map(abs, fuel.values())) + math.log(1000.0)
    wide = 1e-12 * 19123.4 / (R * 301.0) + 16 * 2.0**-52 * size
    inputs = with_potentials(invented, told(1000.0, 400.0, off=0.9 * wide))
    definitions.definition(inputs, inputs.run(f"{WHOLE} h=2e-05"))
    with pytest.raises(blocks.NoSection, match="make .* J/mol at 1 M"):
        inputs = with_potentials(invented, told(1000.0, 400.0, off=1.1 * wide))
        definitions.definition(inputs, inputs.run(f"{WHOLE} h=2e-05"))
    for key in ("stores", "plasma_transport"):
        block = copy.deepcopy(whole[0])
        for store in block["stores"].values():
            store["membrane"]["pump"] = None
            block["calcium_controls"]["store_pump"] = {}
        for transport in block["plasma_transport"].values():
            transport["pump"] = None
        block["calcium_controls"]["calcium_pump"] = {}
        if key == "stores":
            block = {k: v for k, v in block.items() if k not in BESIDE}
        with pytest.raises(blocks.NoSection, match="without calcium pumps has fuel_standard_mu_RT"):
            worlds.write(
                block,
                step=2e-05,
                observation_times=[0.0],
                solver="rk4",
                field_solver="none",
                told={"fuel_standard_mu_RT": fuel},
            )


# ------------------------------------------------------------------ the plants and the runs


def test_the_plants_of_part_2_are_declared_by_the_worlds_blocks(invented):
    """PART2 §11: EP3 is both stores' release times 1.01 and EP4 is EP2's exchange; a declared
    change's path begins in the world's blocks (the lead's answer 16)."""
    plant = invented.run(f"{WHOLE} plant release")
    change = definitions.declared_change(invented, plant)
    path = ["membrane", "release", "permeability_m_per_s"]
    was = [1.3e-07, 1.3e-07 * 1.3]
    assert change == [
        {"path": ["stores", c, *path], "value": v * 1.01} for c, v in zip(CELLS, was, strict=True)
    ]
    world = invented.worlds[WHOLE]
    changed = definitions.block_of(world, change)
    assert [p for p, _, _ in worlds.departures(changed, world.block)] == [
        ("stores", c, *path) for c in CELLS
    ]
    raw = definitions.definition(invented, plant)
    honest = definitions.ionic(world, plant.step_s)
    moved = [
        r["id"]
        for r in raw["model"]["passive_routes"]
        if r not in honest["model"]["passive_routes"]
    ]
    assert moved == ["store_release_c_a", "store_release_c_b"]
    raw["model"]["passive_routes"] = honest["model"]["passive_routes"]
    assert raw == honest
    swap = definitions.definition(invented, invented.run(f"{PAIR} plant swapped"))
    plain = definitions.definition(invented, invented.run(f"{PAIR} s1 w0 h=2e-05"))
    assert [p["channels"] for p in swap["pools"]] == [["k_b"], ["k_a"]]
    assert [p["channels"] for p in plain["pools"]] == [["k_a"], ["k_b"]]
    assert [p["pool"]["seed"] for p in swap["pools"]] == [812, 822]
    assert swap["ionic"] == plain["ionic"]
    inner = [{"path": ["ionic", "channels", "k_a", "abundance"], "value": 0.25}]
    found = definitions.block_of(world, inner)
    assert found["channels"]["k_a"]["abundance"] == 0.25 and "ionic" not in found
    with pytest.raises(InputsError, match="is not in the block"):
        definitions.block_of(world, [{"path": ["channels", "k_a", "abundance"], "value": 0.25}])


def test_a_cluster_is_its_child_with_the_pools_path(invented):
    """inputs_part2.json `same_as`: the child's blocks with a sentence for the channels' schedules,
    and the summary times; a child's compared times are two grids one after the other (PART2 §5)."""
    pair, whole_ = invented.worlds[PAIR], invented.worlds[WHOLE]
    own = copy.deepcopy(whole_.root)
    own["ionic"]["controls"]["channel"] = "the pool's path (SPEC.md section 3.2)"
    assert pair.root == own and whole_.root["ionic"]["controls"]["channel"] == {
        "k_a": ONES,
        "k_b": ONES,
    }
    assert pair.row_times == (0.0, 8e-05, 0.0002) == pair.potential_times and pair.order == 2
    fine, coarse = [0.0, 2e-05, 4e-05], [k * 4e-05 for k in range(2, 6)]
    assert list(whole_.row_times) == [*fine, *coarse]
    raw = definitions.definition(invented, invented.run(f"{PAIR} s1 w0 h=2e-05"))
    assert raw["ionic"]["experiment"]["channel_controls"][0]["schedule"] == [
        {"time": 0.0, "availability": 1.0}
    ]
    assert raw["ionic"] == definitions.ionic(pair, 2e-05)
    run = invented.run(f"{PAIR} s1 pool")
    assert (
        definitions.definition(invented, run) == raw
    )  # Its world's composed file at the first step.
    runs = [run, invented.run(f"{PAIR} s1 w0 h=2e-05"), invented.run(f"{SMALL} h=2e-05")]
    faults, counts = definitions.check(invented, runs=runs)
    assert faults == [] and (counts["composed files"], counts["ionic definitions"]) == (1, 1)
    charged = copy.deepcopy(invented.raw["worlds"][WHOLE])
    charged["stores"]["c_b"]["membrane"]["initial_voltage_V"] = 0.01
    world = type(whole_)(WHOLE, "ip3_calcium", charged)
    assert definitions.derived_faults(world) == [f"{WHOLE} c_b: its store is charged"]
    assert definitions.derived_faults(whole_) == []
    for broken, text in (
        ({"same_as": "no_such"}, "which is no world"),
        ({"final_s": 0.0003}, "ends at 0.0003 s"),
        ({"stores": {}}, "blocks of its own"),
    ):
        raw = copy.deepcopy(invented.raw)
        raw["worlds"][PAIR] |= broken
        path = invented.path.with_name("broken.json")
        path.write_text(json.dumps(raw))
        with pytest.raises(InputsError, match=text):
            Inputs(path)


def test_a_change_off_the_grid_is_found_in_every_schedule_of_the_calcium_pieces(invented):
    raw = copy.deepcopy(invented.raw)
    controls = raw["worlds"][WHOLE]["calcium_controls"]
    run = invented.run(f"{WHOLE} h=2e-05")
    assert definitions.grid_faults(invented, run) is None
    for key, name in (("store_pump", "c_a"), ("reactions", "c_b"), ("calcium_channel", "ca_a")):
        moved = copy.deepcopy(controls)
        if key == "reactions":
            moved[key][name]["bind_1_first"] = [[0.0, 1.0], [3.1e-05, 0.5]]
        else:
            moved[key][name] = [[0.0, 1.0], [3.1e-05, 0.5]]
        changed = copy.copy(invented)
        entry = raw["worlds"][WHOLE] | {"calcium_controls": moved}
        changed.worlds = invented.worlds | {
            WHOLE: type(invented.worlds[WHOLE])(WHOLE, "ip3_calcium", entry)
        }
        fault = definitions.grid_faults(changed, run)
        assert fault.startswith("off_grid_change: calcium_controls") and name in fault


# ------------------------------------------------------------------ fabricated records


def _numbered(name, shape):
    """An array whose every element differs, and differs from every other array's."""
    base = sum(ord(c) * 7.0 for c in name) + 1.0
    return base + 1e-3 * np.arange(float(np.prod(shape))).reshape(shape)


def arrays(spec, times, observed):
    """A run's recorded arrays, as trajectory.npz names them: the composite's own state fields."""
    state, _ = get_model(spec.model).initial_values(spec)
    out = {"accepted_times": np.asarray(times), "observation_times": np.asarray(observed)}
    for name in state._fields:
        shape = np.asarray(getattr(state, name)).shape
        out[name] = _numbered(name, (len(times), *shape))
    membranes, outside = len(spec.model.membranes), len(spec.model.extracellular)
    out["observed_membrane_voltage_V"] = _numbered("V", (len(observed), membranes))
    out["observed_extracellular_potential_V"] = _numbered("phi", (len(observed), outside))
    return out


EXPECTED = {  # {readout: (array, its place after the time axis, sign, the entity there)}.
    "n_out_Ca": ("extracellular_amount_increment", (CA, 2), 1, "rim"),
    "n_out_Na": ("extracellular_amount_increment", (NA, 0), 1, "bath"),
    "cyt_B": ("amount_increment", (B, 1), 1, "c_b"),
    "cyt_K": ("amount_increment", (K, 0), 1, "c_a"),
    "cyt_IP3_bound": ("amount_increment", (IP3_BOUND, 1), 1, "c_b"),
    "store_Ca": ("extracellular_amount_increment", (CA, 3), 1, "c_a"),
    "store_Ca2B": ("extracellular_amount_increment", (CA2B, 4), 1, "c_b"),
    "store_Cl": ("extracellular_amount_increment", (CL, 4), 1, "c_b"),
    "leak_Na": ("membrane_transferred", (NA, 1), -1, "m_b"),
    "leak_Ca": ("passive_transferred", (CA, 1), 1, "m_a"),
    "channel_K": ("channel_transferred", (K, 1), -1, "k_b"),
    "junction_Cl": ("junction_transferred", (CL, 0), 1, "j_ab"),
    "junction_Ca": ("passive_transferred", (CA, 0), -1, "j_ab"),
    "face_Ca": ("face_transferred", (CA, 2), 1, "f_2"),
    "pump": ("pump_cycles", (1,), 1, "m_b"),
    "gate_h": ("channel_gate", (1, 0), 1, "k_a"),
    "junction_gate": ("junction_gate", (0,), 1, "j_ab"),
    "store_leak_Ca": ("passive_transferred", (CA, 4), -1, "c_b"),
    "store_leak_K": ("membrane_transferred", (K, 2), 1, "c_a"),
    "store_pump": ("cycle_count", (0, 1), 1, "c_b"),
    "store_release": ("passive_transferred", (CA, 5), -1, "c_a"),
    "ca_pump": ("cycle_count", (0, 4), 1, "m_b"),
    "exchanger": ("cycle_count", (0, 3), 1, "m_a"),
    "ca_channel": ("channel_transferred", (CA, 3), -1, "ca_b"),
    "ca_gate_m": ("channel_gate", (0, 2), 1, "ca_a"),
    "ca_gate_h": ("channel_gate", (1, 3), 1, "ca_b"),
    "extent_bind_0_first": ("reaction_extent_fmol", (1,), 1, "c_b"),
    "extent_bind_0_second": ("reaction_extent_fmol", (2,), 1, "c_a"),
    "extent_bind_1_first": ("reaction_extent_fmol", (4,), 1, "c_a"),
    "extent_bind_1_second": ("reaction_extent_fmol", (7,), 1, "c_b"),
    "extent_ip3_binding": ("reaction_extent_fmol", (9,), 1, "c_b"),
    "heat_leak": ("membrane_dissipated_energy_pJ", (1,), 1, "m_b"),
    "heat_leak_Ca": ("passive_dissipated_energy_pJ", (2,), 1, "m_b"),
    "heat_pump": ("pump_dissipated_energy_pJ", (0,), 1, "m_a"),
    "heat_junction_own": ("junction_dissipated_energy_pJ", (0,), 1, "j_ab"),
    "heat_junction_Ca": ("passive_dissipated_energy_pJ", (0,), 1, "j_ab"),
    "heat_face": ("face_dissipated_energy_pJ", (1,), 1, "f_1"),
    "heat_store_leak_Ca": ("passive_dissipated_energy_pJ", (3,), 1, "c_a"),
    "heat_store_leak_K": ("membrane_dissipated_energy_pJ", (3,), 1, "c_b"),
    "heat_store_pump": ("cycle_dissipated_energy_pJ", (0,), 1, "c_a"),
    "heat_store_release": ("passive_dissipated_energy_pJ", (6,), 1, "c_b"),
    "heat_ca_pump": ("cycle_dissipated_energy_pJ", (2,), 1, "m_a"),
    "heat_exchanger": ("cycle_dissipated_energy_pJ", (5,), 1, "m_b"),
    "heat_reactions_cytosol": ("reaction_dissipated_energy_pJ", (1,), 1, "c_b"),
    "heat_reactions_store": ("reaction_outside_dissipated_energy_pJ", (3,), 1, "c_a"),
    "work_pump": ("metabolic_work_pJ", (1,), 1, "m_b"),
    "work_store_pump": ("cycle_metabolic_work_pJ", (1,), 1, "c_b"),
    "work_ca_pump": ("cycle_metabolic_work_pJ", (4,), 1, "m_b"),
}
SUMMED = {"heat_channel": (0, "k_a"), "heat_ca_channel": (3, "ca_b")}  # Over the species.


def test_every_readout_of_part_2_is_its_own_slot(whole):
    """PART2 §6.1 on numbered arrays: the turned signs, the index of every entity on its axis (the
    passive routes' in the order of their IDs), and no name that the table does not have."""
    _, _, parsed = whole
    spec = parse_spec(parsed)
    found = arrays(spec, [0.0, 2e-05, 4e-05], [0.0, 4e-05])
    rows = readouts.rows(parsed, found, [0, 2])
    for name, (array, slot, sign, entity) in EXPECTED.items():
        assert rows[name][entity] == [sign * found[array][(k, *slot)] for k in (0, 2)], name
    for name, (slot, entity) in SUMMED.items():
        heat = found["channel_dissipated_energy_pJ"][:, :, slot].sum(axis=1)
        assert rows[name][entity] == [heat[k] for k in (0, 2)], name
    four, three = ("Na", "K", "Cl", "Ca"), ("Na", "K", "Cl")
    families = {f"{n}_{x}" for n in ("n_out", "face") for x in four}
    families |= {f"{n}_{x}" for n in ("leak", "junction") for x in three}
    families |= {f"{n}_{c}" for n in ("cyt", "store") for c in ROWS}
    assert set(rows) == families | set(EXPECTED) | set(SUMMED) | {"gate_m"}
    owners = {"c_a", "c_b"}
    for name in rows:
        if name.startswith(
            ("store_", "cyt_", "extent_", "heat_store", "heat_reactions", "work_store")
        ):
            assert set(rows[name]) == owners, name
    assert set(rows["n_out_Ca"]) == set(REGIONS) and set(rows["heat_leak"]) == {"m_a", "m_b"}
    assert set(rows["pump"]) == {"m_a", "m_b"} and set(rows["gate_m"]) == {"k_a", "k_b"}
    voltage = found["observed_membrane_voltage_V"]
    phi = found["observed_extracellular_potential_V"]
    assert readouts.potentials(parsed, found, [0, 1]) == {
        "voltage": {"m_a": voltage[:, 0].tolist(), "m_b": voltage[:, 1].tolist()},
        "phi_out": {"shell": phi[:, 1].tolist(), "rim": phi[:, 2].tolist()},
        "store_voltage": {"c_a": (-voltage[:, 2]).tolist(), "c_b": (-voltage[:, 3]).tolist()},
    }
    found["observed_membrane_voltage_V"] = np.zeros_like(voltage)  # And never a negative zero.
    zero = readouts.potentials(parsed, found, [0])["store_voltage"]["c_a"]
    assert zero == [0.0] and math.copysign(1.0, zero[0]) == 1.0


def test_the_first_childs_readouts_are_the_ones_it_has():
    """A series of a piece that a world lacks is not there (READOUTS §2)."""
    parsed = parse_spec(written(child("spatial"))).to_dict()
    spec = parse_spec(parsed)
    rows = readouts.rows(parsed, arrays(spec, [0.0, 2e-05], [0.0]), [1])
    lacking = {"ca_pump", "exchanger", "heat_ca_pump", "heat_exchanger", "work_ca_pump"}
    lacking |= {"ca_channel", "heat_ca_channel", "ca_gate_m", "ca_gate_h", "extent_ip3_binding"}
    assert not lacking & set(rows) and not any("IP3" in name for name in rows)
    assert {
        "store_release",
        "heat_store_pump",
        "leak_Ca",
        "cyt_Ca2B",
        "extent_bind_1_first",
    } <= set(rows)
    assert not {"n_cell_K", "heat_junction"} & set(rows)
    # A reaction that one cell lacks has no slot there, and moves the others' along the axis.
    block = child("spatial")
    for name in ("bind_0_first", "bind_0_second"):
        del block["stores"]["c_b"]["reactions"][name]
        del block["calcium_controls"]["reactions"]["c_b"][name]
    raw = parse_spec(written(block)).to_dict()
    assert worlds.departures(worlds.read(raw), block) == []
    found = arrays(parse_spec(raw), [0.0, 2e-05], [0.0])
    rows = readouts.rows(raw, found, [1])
    extents = {"bind_0_second": {"c_a": 1}, "bind_1_first": {"c_a": 2, "c_b": 3}}
    for name, places in extents.items():
        assert rows[f"extent_{name}"] == {
            cell: [found["reaction_extent_fmol"][1, k]] for cell, k in places.items()
        }
    assert set(rows["heat_reactions_cytosol"]) == {"c_a"}
    assert set(rows["heat_reactions_store"]) == {"c_a", "c_b"}


SOURCE = {name: kind() for name, kind in exporter.SOURCE.items()}


def record(tmp_path, inputs, run, raw, parsed, saved, **facts):
    """A run's record, made by the driver's own code around these files."""
    folders = driver.Folders(tmp_path, held=run.retry)
    attempt = driver.next_attempt(folders.run(run))
    driver.write_json(attempt / "job.json", {"started_utc": "then"})
    driver.write_json(attempt / "submitted.json", raw)
    driver.write_json(attempt / "parsed.json", parsed)
    (attempt / "output").mkdir()
    np.savez(attempt / "output/trajectory.npz", **saved)
    own = {"definition": {}, "resolution": None, "restart": None, "timings": {}} | facts
    outcome = {"status": "completed", "refusal": None, "source": SOURCE, "facts": own}
    driver.write_json(attempt / "outcome.json", outcome)
    made = driver.made(inputs, run, attempt, None, tag=None, off_grid=False)
    driver.write_json(folders.run(run) / driver.RECORD, made)
    return folders, attempt


def test_an_ionic_entry_of_part_2_is_the_contracts(invented, tmp_path, whole):
    """PART2_BLOCKS: `inputs` holds the world's blocks by their names; the rows are at the child's
    two grids; `definition` holds what PART2 §2.5 says beside the engine's own form."""
    _, raw, parsed = whole
    run = invented.run(f"{WHOLE} h=2e-05")
    times = [k * 2e-05 for k in range(11)]
    observed = [0.0, 4e-05, 0.00012, 0.0002]
    saved = arrays(parse_spec(parsed), times, observed)
    folders, _ = record(tmp_path, invented, run, raw, parsed, saved)
    entry = exporter.entry(invented, run, folders)
    assert exporter.entry_faults(run.name, entry) == [] and entry["refusal"] is None
    assert entry["t"] == [times[k] for k in (0, 1, 2, 4, 6, 8, 10)]
    assert (entry["steps"], entry["potential_t"]) == (10, observed)
    assert list(entry["inputs"]) == [
        "ionic",
        "stores",
        "plasma_transport",
        "calcium_channels",
        "ip3_release",
        "calcium_controls",
    ]
    world = invented.worlds[WHOLE]
    assert set(entry["inputs"]["ionic"]) == set(world.root["ionic"])
    assert worlds.departures(flat(entry["inputs"]), world.block) == []
    assert set(entry["strings"]) == definitions._labels(invented, run)
    assert entry["declared_strings"] == sorted(entry["strings"].values())
    beyond = entry["definition"]
    assert beyond["ionic"] == parsed and beyond == {"ionic": parsed} | exporter.beyond(parsed)
    assert json.loads(json.dumps(entry)) == entry


COUNTS = {  # PART2 §2.5's table, for two cells with a store each: {child: what differs}.
    "spatial": {"channels": 2, "populations": 2, "reactions": 4},
    "plasma": {"channels": 2, "populations": 6, "reactions": 4},
    "gated": {"channels": 4, "populations": 6, "reactions": 4},
    "ip3": {"channels": 4, "populations": 6, "reactions": 5},
}


@pytest.mark.parametrize("name", CHILDREN)
def test_definition_says_exactly_what_stands_beyond_the_block(name):
    """PART2 §2.5: the sorted species rows (ten, or thirteen), the sorted rows that hold the trace
    at each region and store ("store:" and the cell), and the counts. Names by code point."""
    found = exporter.beyond(parse_spec(written(child(name))).to_dict())
    further = ["IP3", "IP3_bound", "IP3_buffer"] if name == "ip3" else []
    own = ["B", "Ca", "Ca2B", "CaB", "Cl", *further, "K", "Na"]
    assert found["species_rows"] == sorted([*own, "ATP", "ADP", "Pi"])
    assert found["species_rows"][0] == "ADP" and len(found["species_rows"]) == 10 + len(further)
    region = sorted(["B", "CaB", "Ca2B", "ATP", "ADP", "Pi", *further])
    assert found["traces"] == {r: region for r in REGIONS} | {
        f"store:{c}": ["ADP", "ATP", "Pi"] for c in CELLS
    }
    assert region[:3] == ["ADP", "ATP", "B"]
    everywhere = dict(cells=2, outside_nodes=5, membranes=4, junctions=1, faces=3, compartments=2)
    everywhere |= dict(passive_routes=7, species_conditions=2, operators=2)
    assert found["entities"] == everywhere | COUNTS[name]
    assert found["release_conditions"] == {c: f"release_factor_{c}" for c in CELLS}
    assert {node: sorted(rows) for node, rows in found["trace_mM"].items()} == found["traces"]
    for rows in found["trace_mM"].values():
        assert all(v == pytest.approx(1e-12, rel=1e-15) for v in rows.values())


def test_a_row_or_an_entity_beyond_the_table_shows(whole):
    """A row that a block does not name at a node, at another concentration than the trace, is in no
    list of the traces; a cell without a store or without a pump has a list of its own; another
    entity is counted. A definition of the inner model has none of these keys."""
    _, raw, parsed = whole
    honest = exporter.beyond(parsed)
    moved = copy.deepcopy(raw)
    rim = moved["model"]["extracellular"][2]
    rim["initial_amount_fmol"]["Pi"] = 2e-12 * rim["volume_pL"]
    found = exporter.beyond(parse_spec(moved).to_dict())
    assert found["traces"]["rim"] == [s for s in honest["traces"]["rim"] if s != "Pi"]
    assert found["trace_mM"]["rim"]["Pi"] == pytest.approx(2e-12)
    assert {k: v for k, v in found.items() if k not in ("traces", "trace_mM")} == {
        k: v for k, v in honest.items() if k not in ("traces", "trace_mM")
    }
    bare = copy.deepcopy(raw)  # Read as submitted: no pump and no store at c_b.
    model = bare["model"]
    model["transporters"] = [t for t in model["transporters"] if t["id"] != "store_pump_c_b"]
    assert "c_b" not in exporter.beyond(bare)["traces"]  # Its plasma pump names its fuel.
    model["operators"].append({"law": "another@1"})
    assert exporter.beyond(bare)["entities"]["operators"] == 3
    model["operators"].pop()
    model["transporters"] = [t for t in model["transporters"] if not t["id"].endswith("b")]
    cell = _entity(model["cells"], "c_b")
    for s in FUEL:
        cell["initial_amount_fmol"][s] = 1e-12 * cell["volume_pL"]
    assert exporter.beyond(bare)["traces"]["c_b"] == ["ADP", "ATP", "Pi"]
    assert exporter.beyond(bare)["entities"]["populations"] == 3
    del model["operators"][0]["compartments"][1]
    mixed = sorted([*ROWS[B:], *FUEL])
    assert exporter.beyond(bare)["traces"]["c_b"] == [s for s in mixed if s in FUEL]
    assert exporter.beyond(bare)["trace_mM"]["c_b"]["B"] > 1e-3
    assert exporter.beyond(bare)["entities"]["compartments"] == 1
    twice = copy.deepcopy(raw)
    twice["model"]["species"].append({"id": "X", "valence": 0})
    for node in (*twice["model"]["cells"], *twice["model"]["extracellular"]):
        node["initial_amount_fmol"]["X"] = 1e-12 * node["volume_pL"]
    assert "X" in exporter.beyond(twice)["species_rows"]
    assert exporter.beyond({"model": written_inner()}) == {}


def test_a_row_that_the_block_gives_no_potential_has_zero():
    """PART2 §2.2: the registry declares a standard potential for every row."""
    block = child("spatial")
    for cell in ("c_a", "c_b"):
        store = block["stores"][cell]
        del store["species"]["Na"], store["membrane"]["permeability_m_per_s"]["Na"]
        del store["compartments"]["er"]["initial_amount_fmol"]["Na"]
    raw = written(block)
    assert all("standard_mu_RT" in s for s in raw["model"]["species"])
    assert _entity(raw["model"]["species"], "Na")["standard_mu_RT"] == 0.0
    parse_spec(raw)


def test_a_clusters_entry_says_what_its_schedule_came_from(invented, tmp_path):
    """`inputs.assembly` beside the blocks, the seeds and the switches by the K channels' pools and
    never by a calcium channel's, and the swapped plant's seeds by position (PART2 §11)."""
    run = invented.run(f"{PAIR} plant swapped")
    composed = definitions.definition(invented, run)
    raw = copy.deepcopy(composed["ionic"])
    control = _entity_of(raw["experiment"]["channel_controls"], "channel_id", "k_b")
    control.append({"time": 3.3e-05, "availability": 0.0})
    parsed = parse_spec(raw).to_dict()
    made_from = {
        "composed_file_sha256": "c" * 64,
        "pools": [
            {"channels": p["channels"], "observable": p["observable"], "seed": p["pool"]["seed"]}
            for p in composed["pools"]
        ],
        "worlds": [
            {"world": 0, "switches": [{"pool": 0, "time": 3.3e-05, "level": 0.0, "event": 0}]}
        ],
    }
    times = sorted({*(k * 2e-05 for k in range(11)), 3.3e-05})
    saved = arrays(parse_spec(parsed), times, [0.0, 8e-05, 0.0002])
    folders, attempt = record(tmp_path, invented, run, composed, parsed, saved)
    driver.write_json(
        attempt / "output/manifest.json", {"provenance": {"operation": "run", "inputs": made_from}}
    )
    entry = exporter.entry(invented, run, folders)
    assert exporter.entry_faults(run.name, entry) == [] and entry["refusal"] is None
    assert entry["steps"] == 11 and entry["t"] == [0.0, 8e-05, 0.0002] == entry["potential_t"]
    assert entry["inputs"]["assembly"] == {
        "assembly_observable": "assembly_observable",
        "composed_file_fingerprint": "c" * 64,
        "pool_seeds": {"c_a": 812, "c_b": 822},
        "switch_list": {"k_b": [[3.3e-05, 0.0]], "k_a": []},
    }
    assert list(entry["inputs"])[0] == "ionic" and "stores" in entry["inputs"]
    channel = entry["inputs"]["ionic"]["controls"]["channel"]
    assert channel == {"k_a": ONES, "k_b": [[0.0, 1.0], [3.3e-05, 0.0]]}
    assert entry["inputs"]["calcium_controls"]["calcium_channel"] == {"ca_a": ONES, "ca_b": ONES}
    assert "assembly_observable" in entry["strings"]
    assert exporter.driven_cells(parsed) == CELLS
    lone = copy.deepcopy(parsed)  # A calcium channel makes no cell a driven one.
    lone["model"]["channels"].pop(0)
    assert exporter.driven_cells(lone) == ["c_b"]


# ------------------------------------------------------------------ condition 8


def test_calciums_junction_route_is_opened_by_the_gate_and_the_availability(whole):
    """PART2 §3's condition 8, on the engine's own kernel at a parsed invented world: the flux of
    calcium's junction route is proportional to the junction's gate times its availability, and no
    other route's depends on them."""
    _, _, parsed = whole
    spec = parse_spec(parsed)
    state, p = get_model(spec.model).initial_values(spec)
    names = [r["id"] for r in parsed["model"]["passive_routes"]]
    Control = collections.namedtuple("Control", ("membrane", "junction", passive_routes.MULTIPLIER))

    def flux(gate, availability):
        gated = state._replace(junction_gate=np.full_like(state.junction_gate, gate))
        control = Control(
            np.ones(p.membrane_active.shape),
            np.full(p.junction_active.shape, availability),
            np.ones(len(names)),
        )
        return passive_routes.clamped_flux(gated, control, p, 0.013)[0][CA]

    whole_open, junction = flux(1.0, 1.0), names.index("junction_Ca_j_ab")
    assert junction == 0 and whole_open[junction] != 0.0
    for gate, availability in ((0.55, 1.0), (0.3, 1.0), (1.0, 0.4), (0.3, 0.4), (0.0, 1.0)):
        found = flux(gate, availability)
        share = found[junction] / whole_open[junction]
        assert share == pytest.approx(gate * availability, rel=1e-14, abs=1e-300)
        assert np.array_equal(found[1:], whole_open[1:])


# ------------------------------------------------------------------ the retry's runs, the strings


def test_the_retrys_runs_made_up_front_open_by_the_notes_sha256_alone(invented, tmp_path, whole):
    """The lead's answer 21: every family's fourth run in the batch, apart, and exported only with
    the hash of the judge's note."""
    retries = [r.name for r in invented.retries()]
    assert retries == [
        f"{SMALL} h=1e-05 retry",
        f"{WHOLE} h=5e-06 retry",
        f"{PAIR} s1 w0 h=1e-05 retry",
    ]
    runs = driver.ordered(invented, retries=True)
    assert [r.retry for r in runs] == [False] * 7 + [True] * 3 + [False]
    assert runs[-1].restart_time is not None and len(driver.ordered(invented)) == 8
    note = {"kind": "ensemble-reexpression retry owed, version 1", "part": 2, "why": {}}
    owed = tmp_path / "retry_owed.json"
    owed.write_text(json.dumps(note | {"runs": [retries[0]]}))
    with pytest.raises(InputsError, match="and not both"):
        driver.ordered(invented, owed=owed, retries=True)
    run = invented.run(retries[0])
    raw = definitions.definition(invented, run)
    spec = parse_spec(raw)
    times = [k * 1e-05 for k in range(21)]
    saved = arrays(spec, times, [0.0, 4e-05, 0.00012, 0.0002])
    folder = tmp_path / "records"
    folders, _ = record(folder, invented, run, raw, spec.to_dict(), saved)
    assert folders.run(run).parent == folder / "retries"
    assert driver.Folders(folder).record(run) is None  # Nothing else finds it.
    command = ["export", "--inputs", str(invented.path), "--runs", str(folder), "--owed", str(owed)]
    sha256 = driver.digest(owed)
    for given, text in (
        ([], "was made up front"),
        (["--owed-sha256", "0" * 64], "is not the sha256"),
    ):
        out = tmp_path / f"refused-{len(given)}"
        assert exporter.main([*command, "--output", str(out), *given]) == 2 and not out.exists(), (
            text
        )
    out = tmp_path / "table-retry"
    assert exporter.main([*command, "--output", str(out), "--owed-sha256", sha256]) == 0
    (table,) = out.glob("table_*.json")
    found = json.loads(table.read_text())
    assert list(found["runs"]) == [retries[0]] and found["part"] == 2 and found["missing"] == []
    owed.write_text(json.dumps(note | {"runs": [retries[0]], "part": 1}))
    with pytest.raises(InputsError, match="retry note of part 1"):
        invented.owed(owed)


def test_the_strings_of_every_run_are_one_file(invented, tmp_path):
    """For the lead's note: each kind of run's labels and strings, and no string without a label."""
    out = tmp_path / "strings.json"
    command = ["strings", "--inputs", str(invented.path), "--json", str(out)]
    assert definitions.main(command) == 0
    found = json.loads(out.read_text())
    assert found["strings_without_a_label"] == [] and set(found["runs"]) == set(invented.runs)
    assert list(found["run_kinds"]) == [
        "spatial_calcium ionic",
        "ip3_calcium ionic",
        "pool",
        "cluster_gated_calcium ionic",
    ]
    for name, run in invented.runs.items():
        kind = found["run_kinds"][found["runs"][name]]
        assert sorted(kind["strings"].values()) == kind["declared_strings"]
        if run.kind != "pool":
            assert set(kind["strings"]) == definitions._labels(invented, run) | (
                {"assembly_observable"} if run.kind == "driven" else set()
            )
    assert found["labels"] == {k: v for k, v in labels.LABELS.items() if k in found["labels"]}
    # A run that the generator refuses has no declaration, and one that the engine refuses to parse
    # has the strings of what it submits.
    refused, told = with_potentials(invented, TOLD["two numbers"]), f"{WHOLE} h=2e-05"
    note = definitions.strings_note(refused)
    assert "no_section" in note["runs"][told]["no_declaration"]
    assert (
        note["runs"][f"{PAIR} s1 pool"] == "pool" and "ip3_calcium ionic" not in note["run_kinds"]
    )
    raw = copy.deepcopy(invented.raw)
    for store in raw["worlds"][SMALL]["stores"].values():
        store["temperature_K"] = 151.0
    raw["worlds"][SMALL]["ionic"]["temperature_K"] = 151.0
    path = invented.path.with_name("cold.json")
    path.write_text(json.dumps(raw))
    with pytest.raises(ConfigError, match="200-400 K"):
        parse_spec(definitions.definition(Inputs(path), Inputs(path).run(f"{SMALL} h=2e-05")))
    cold = definitions.strings_note(Inputs(path))
    assert cold["run_kinds"]["spatial_calcium ionic"] == found["run_kinds"]["spatial_calcium ionic"]


def test_part_2s_literal_blocks_are_read_as_its_text_prints_them(tmp_path):
    """PART2_BLOCKS prints one `ionic`, two `stores` and the last child's schedules, and says what
    the others lack (its §7): on an invented text of that form."""
    blocks_ = {name: sample_part2.blocks(sample_part2.BOTH, **kw) for name, kw in CHILDREN.items()}
    last = blocks_["ip3"]
    printed = [last["ionic"], blocks_["gated"]["stores"], last["stores"], last["plasma_transport"]]
    printed += [last["calcium_channels"], last["ip3_release"], last["calcium_controls"], {"p": 1}]
    path = tmp_path / "PART2_BLOCKS.md"
    sections = [f"## {k + 1}. x\n\n```json\n{json.dumps(b)}\n```" for k, b in enumerate(printed)]
    sections[2] += "\n\n```json\n{}\n```"  # A second block, or a ninth section, moves nothing.
    path.write_text("\n\n".join(["# x", *sections, "## 9. y\n\n```json\n{}\n```"]))
    found, pool_run = definitions.part2_literals(path)
    assert pool_run == {"p": 1}
    assert found == {f"{name}_calcium": value for name, value in blocks_.items()}


@pytest.mark.parametrize(
    "message, kind",
    [
        ("passive_routes r: permeability_m_per_s is finite and >= 0", "domain"),
        ("local_species_reactions@1: x's forward_rate_per_s must be > 0", "domain"),
        ("local_species_reactions@1: a multiplier of x must be >= 0", "domain"),
        ("species B's trace_mM must be a finite positive number", "domain"),
        ("transporter 'p': parameter km_role_mM is positive", "domain"),
        ("condition 'c', read 0: K is a normal float, at least 2.2e-308", "domain"),
        ("transporter 'p': law is one of a, b", "definition"),
        ("passive_routes: route IDs must be unique", "definition"),
        (
            "cell_owned_compartments@1: the patch 'x' of compartment 'y' is not declared",
            "definition",
        ),
    ],
)
def test_a_refusal_of_a_calcium_piece_is_mapped_to_a_kind(message, kind):
    assert refusals.kind_of(ConfigError(message), stage="parse") == kind


def test_the_operators_of_part_2_have_no_ledger_of_their_own():
    """So every ledger's failure in a composite has the inner model's words, which are a check's
    (an operator's own ledger with an empty message would be read as a domain's)."""
    for law in ("compartment_law", "local_reactions"):
        operator = OPERATORS[labels.LABELS[law]]
        assert operator.LEDGERS == () == operator.LEDGER_DIAGNOSTICS


def test_no_readout_has_two_sources(whole):
    _, _, parsed = whole
    found = arrays(parse_spec(parsed), [0.0, 2e-05], [0.0])
    twice = (*readouts.SERIES, readouts.Series("pump_cycles", "pump", readouts._plasma))
    with pytest.raises(ValueError, match="pump has two sources"):
        readouts._read(twice, Pieces(parsed), found, [0])


def test_the_blocks_of_part_2_have_one_list_of_names():
    """The inputs' names of the blocks and the sections that write them are the same."""
    assert tuple(key for section in stores.SECTIONS for key in section.keys) == BESIDE
    assert Pieces({"model": written_inner()}).composite is False


def written_inner():
    from validation.ensemble_reexpression import sample

    return worlds.write(
        sample.sheet(), step=2e-05, observation_times=[0.0], solver="rk4", field_solver="none"
    )["model"]
