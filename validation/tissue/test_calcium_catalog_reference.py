"""Independent owned-calcium/catalog stages; no production imports or long clocks.

The reference has real-owner arrays only. Padding checks here verify the active
projection is unchanged, not production padding rejection or padded GPU kernels.
Assembly inputs are prescribed owner levels, not assembly kinetics or feedback.
"""

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from validation.tissue import surface_calcium_reference as ref
from validation.tissue import surface_kinetic_reference as ionic

ARMS = ("open", "blocked", "release", "reordered")
pytestmark = pytest.mark.skipif(
    "CELLS_CALCIUM_CATALOG_INPUTS" not in os.environ,
    reason="Independent checks require separately serialized, hashed raw JSON inputs",
)


def raw_input(arm="open"):
    return json.loads(
        (Path(os.environ["CELLS_CALCIUM_CATALOG_INPUTS"]) / f"{arm}.json").read_text()
    )


def evidence(name, value):
    if directory := os.environ.get("CELLS_REFERENCE_EVIDENCE"):
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def modified_state(c, *, changed=False):
    d = ref.unpack(c, ref.initial(c))
    if changed:
        for i, store in enumerate(c["stores"]):
            h = 1e-4 * (i + 1)
            d["chemical_amount_increment"][
                i, [store.ids.index(k) for k in ("Ca", "B", "CaB")], store.cy
            ] += h * np.array([-1, -1, 1])
            d["chemical_amount_increment"][i, store.ids.index("Na"), [store.cy, store.er]] += (
                h * np.array([-1, 1])
            )
        d["channel_gate"][:] = np.array([[0.31], [0.63]])
        d["calcium_gate"][:] = np.array([[0.27], [0.66]])
    return ref.flatten(c, d)


def owner_maps(c):
    m = c["raw"]["model"]
    cells, outside = ([row["id"] for row in m[k]] for k in ("cells", "extracellular"))
    patches = {row["id"]: row for row in m["membranes"]}
    return [
        (
            cells.index(patches[ch["membrane_id"]]["inside"]),
            outside.index(patches[ch["membrane_id"]]["outside"]),
        )
        for ch in m["channels"]
    ]


def owned_exchange(c, transferred):
    ions = [row["id"] for row in c["raw"]["model"]["species"]]
    inside, outside = np.zeros_like(c["ai"]), np.zeros_like(c["ao"])
    chemical = np.zeros(c["shapes"]["chemical_amount_increment"])
    for j, (i, o) in enumerate(owner_maps(c)):
        store = c["stores"][i]
        inside[:, i] -= transferred[:, j]
        outside[:, o] += transferred[:, j]
        for s, ion in enumerate(ions):
            chemical[i, store.ids.index(ion), store.cy] -= transferred[s, j]
    return inside, outside, chemical


def ownership_checks(c, derivative):
    """Explicit reaction/ER/external sums and global conserved chemical groups."""
    d = ref.unpack(c, derivative)
    ion_ids = [s["id"] for s in c["raw"]["model"]["species"]]
    groups = sorted({k for store in c["stores"] for row in store.species for k in row["moieties"]})
    total = {name: 0.0 for name in groups}
    max_ledger = 0.0
    for i, store in enumerate(c["stores"]):
        expected = np.zeros_like(store.n0)
        for j, reaction in enumerate(store.reactions):
            owner = store.owners.index(reaction["compartment"])
            for s, species in enumerate(store.ids):
                nu = reaction["products"].get(species, 0) - reaction["reactants"].get(species, 0)
                expected[s, owner] += nu * d["reaction_extent"][i, j]
        exchange = d["er_passive_transferred"][i].copy()
        exchange[store.ca] += d["er_pump_transferred"][i, 0] + d["er_release_transferred"][i, 0]
        expected[:, store.cy] -= exchange
        expected[:, store.er] += exchange
        for s, name in enumerate(ion_ids):
            expected[store.ids.index(name), store.cy] += d["amount_increment"][s, i]
        np.testing.assert_allclose(
            expected, d["chemical_amount_increment"][i], rtol=3e-14, atol=3e-13
        )
        max_ledger = max(
            max_ledger, float(np.max(np.abs(expected - d["chemical_amount_increment"][i])))
        )
        # Plasma charge tracks whole-cell external transfer, including bound ions.
        chemical_charge_rate = np.sum(store.z[:, None] * d["chemical_amount_increment"][i])
        ionic_charge_rate = np.sum(
            np.asarray(c["layout"]["valence"])[:, 0] * d["amount_increment"][:, i]
        )
        np.testing.assert_allclose(chemical_charge_rate, ionic_charge_rate, rtol=3e-13, atol=3e-13)
        for s, species in enumerate(store.species):
            for name, coefficient in species["moieties"].items():
                total[name] += coefficient * d["chemical_amount_increment"][i, s].sum()
    for j, name in enumerate(ion_ids):
        total[name] += d["extracellular_amount_increment"][j].sum()
    np.testing.assert_allclose(list(total.values()), 0, rtol=0, atol=3e-13)
    assert (
        min(float(v.min(initial=0)) for k, v in d.items() if k.endswith("_dissipated_energy_pJ"))
        >= -3e-14
    )
    return dict(
        max_chemical_ledger_residual_fmol_s=max_ledger, global_moiety_rate_residual_fmol_s=total
    )


@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize("changed", [False, True])
def test_complete_catalog_uses_owned_free_ions_and_conserves_chemistry(arm, changed):
    raw = raw_input(arm)
    assert raw["model"]["id"] == "resolved_calcium@7"
    assert raw["model"]["ionic"]["id"] == "resolved_tissue@8"
    c = ref.bind(raw)
    assert len(c["shapes"]) == 34 and c["shapes"]["channel_transferred"] == (4, 39)
    assert {ch["kinetic_law"] for ch in c["raw"]["model"]["channels"]} == set(
        ionic.CATALOG_PERMEABILITIES
    )
    y = modified_state(c, changed=changed)
    times = sorted(
        {
            row["time"]
            for group in raw["experiment"]["channel_controls"]
            for row in group["schedule"]
        }
    )
    results = []
    for time in times:
        derivative, phi, proof = ref.evaluate(c, y, time)
        checks = ownership_checks(c, derivative)
        assert abs(proof["physical_energy_balance_pJ_s"]) < 3e-10
        d = ref.unpack(c, derivative)
        for j, channel in enumerate(c["raw"]["model"]["channels"]):
            if ionic.availability(c, "channel", channel["id"], time) == 0:
                assert not np.any(d["channel_transferred"][:, j])
                assert not np.any(d["channel_dissipated_energy_pJ"][:, j])
        results.append(
            dict(
                time=time,
                derivative=derivative.tolist(),
                potential_V=phi.tolist(),
                proof=proof,
                ownership=checks,
            )
        )
    evidence(
        f"complete-{arm}-{changed}",
        dict(
            inputs=raw,
            state=y.tolist(),
            checks=results,
            scope="Instantaneous complete-state stages; no trajectory or settling claim",
        ),
    )


@pytest.mark.parametrize("owner", [0, 1])
@pytest.mark.parametrize("kind", ["calcium_binding", "calcium_er", "sodium_er"])
def test_internal_redistribution_changes_free_routes_without_plasma_charge(kind, owner):
    c = ref.bind(raw_input())
    original = ref.initial(c)
    d = ref.unpack(c, original.copy())
    store = c["stores"][owner]
    h = 1e-4
    affected = "Na" if kind == "sodium_er" else "Ca"
    if kind == "calcium_binding":
        d["chemical_amount_increment"][
            owner, [store.ids.index(k) for k in ("Ca", "B", "CaB")], store.cy
        ] += h * np.array([-1, -1, 1])
    else:
        d["chemical_amount_increment"][owner, store.ids.index(affected), [store.cy, store.er]] += (
            h * np.array([-1, 1])
        )
    changed = ref.flatten(c, d)
    baseline, phi0, _ = ref.evaluate(c, original, 0)
    after, phi1, proof = ref.evaluate(c, changed, 0)
    a, b = ref.unpack(c, baseline), ref.unpack(c, after)
    # Internal redistribution does not charge plasma capacitors. Absolute
    # component offsets can nevertheless shift to rebalance junction currents;
    # their equality is not the physical invariant in this resolved field model.
    matrix = ref.electrical.topology(ionic.base.stage(c, original, 0))[0]
    np.testing.assert_allclose(matrix @ (phi1 - phi0), 0, rtol=0, atol=3e-25)
    inside = np.asarray(c["layout"]["membrane_cell"])
    outside = len(c["vi"]) + np.asarray(c["layout"]["membrane_outside"])
    np.testing.assert_allclose(
        phi1[inside] - phi1[outside], phi0[inside] - phi0[outside], rtol=0, atol=3e-14
    )
    np.testing.assert_array_equal(d["amount_increment"], 0)
    np.testing.assert_array_equal(d["extracellular_amount_increment"], 0)
    ions = [s["id"] for s in c["raw"]["model"]["species"]]
    s = ions.index(affected)
    changed_routes = []
    for j, (inside, _) in enumerate(owner_maps(c)):
        for k in range(len(ions)):
            if inside != owner or k != s:
                np.testing.assert_allclose(
                    b["channel_transferred"][k, j],
                    a["channel_transferred"][k, j],
                    rtol=3e-13,
                    atol=3e-16,
                )
        route = c["raw"]["model"]["channels"][j]
        weight = dict(
            (v["species_id"], v["relative_permeability"]) for v in route["permeant_ions"]
        ).get(affected, 0)
        if inside == owner and weight > 0:
            assert b["channel_transferred"][s, j] != a["channel_transferred"][s, j]
            changed_routes.append(route["id"])
    assert changed_routes
    ownership_checks(c, after)
    assert abs(proof["physical_energy_balance_pJ_s"]) < 3e-10
    evidence(
        f"redistribution-{kind}-{owner}",
        dict(
            owner=owner,
            kind=kind,
            state=changed.tolist(),
            changed_routes=changed_routes,
            plasma_potential_V=phi1.tolist(),
            absolute_node_offset_change_V=(phi1 - phi0).tolist(),
            proof=proof,
        ),
    )


@pytest.mark.parametrize("levels", [[0.0, 1.0], [1.0, 0.0], [0.35, 0.8]])
def test_prescribed_assembly_owner_levels_scale_shared_routes_once(levels):
    c = ref.bind(raw_input())
    y = modified_state(c, changed=True)
    baseline, phi0, _ = ref.evaluate(c, y, 0)
    changed, phi1, proof = ref.evaluate(c, y, 0, channel_levels=np.asarray(levels))
    a, b = ref.unpack(c, baseline), ref.unpack(c, changed)
    factors = np.asarray([levels[i] for i, _ in owner_maps(c)])
    expected = a["channel_transferred"] * factors
    np.testing.assert_allclose(b["channel_transferred"], expected, rtol=3e-15, atol=3e-16)
    np.testing.assert_allclose(
        b["channel_dissipated_energy_pJ"],
        a["channel_dissipated_energy_pJ"] * factors,
        rtol=3e-15,
        atol=3e-16,
    )
    np.testing.assert_array_equal(b["channel_gate"], a["channel_gate"])
    np.testing.assert_array_equal(phi0, phi1)
    # Dedicated patch CaV populations have a different, explicitly owned control.
    for name in (
        "calcium_gate",
        "calcium_channel_transferred",
        "calcium_channel_dissipated_energy_pJ",
        "plasma_pump_cycles",
        "plasma_exchange_cycles",
    ):
        np.testing.assert_array_equal(a[name], b[name])
    exchanges = owned_exchange(c, expected - a["channel_transferred"])
    for name, value in zip(
        ("amount_increment", "extracellular_amount_increment", "chemical_amount_increment"),
        exchanges,
        strict=True,
    ):
        np.testing.assert_allclose(b[name] - a[name], value, rtol=3e-13, atol=3e-14)
    ownership_checks(c, changed)
    assert abs(proof["physical_energy_balance_pJ_s"]) < 3e-10
    evidence(
        "assembly-owner-levels-" + "-".join(map(str, levels)),
        dict(
            levels=levels,
            shared_route_count=len(factors),
            proof=proof,
            interpretation=(
                "Prescribed one-way owner levels; no assembly kinetics or reciprocal feedback"
            ),
        ),
    )


def test_catleak_zero_calcium_and_catleak2_divalent_owned_route():
    raw = raw_input()
    c = ref.bind(raw)
    y = ref.initial(c)
    slope, _, _ = ref.evaluate(c, y, 0)
    rate = ref.unpack(c, slope)
    ca = [s["id"] for s in c["raw"]["model"]["species"]].index("Ca")
    channels = c["raw"]["model"]["channels"]
    first = next(j for j, ch in enumerate(channels) if ch["kinetic_law"] == "betse_catleak_na_k@1")
    second = next(
        j for j, ch in enumerate(channels) if ch["kinetic_law"] == "betse_catleak2_na_k_ca@1"
    )
    assert channels[first]["permeant_ions"][-1] == dict(species_id="Ca", relative_permeability=0.0)
    assert (
        rate["channel_transferred"][ca, first]
        == rate["channel_dissipated_energy_pJ"][ca, first]
        == 0
    )
    assert rate["channel_transferred"][ca, second] != 0
    blocked = deepcopy(raw)
    group = next(
        g
        for g in blocked["experiment"]["channel_controls"]
        if g["channel_id"] == channels[second]["id"]
    )
    group["schedule"] = [dict(time=0.0, availability=0.0)]
    stopped = ref.unpack(c, ref.evaluate(ref.bind(blocked), y, 0)[0])
    selected = np.zeros_like(rate["channel_transferred"])
    selected[:, second] = rate["channel_transferred"][:, second]
    for name, expected in zip(
        ("amount_increment", "extracellular_amount_increment", "chemical_amount_increment"),
        owned_exchange(c, selected),
        strict=True,
    ):
        np.testing.assert_allclose(rate[name] - stopped[name], expected, rtol=3e-13, atol=3e-14)
    np.testing.assert_array_equal(rate["channel_gate"], stopped["channel_gate"])


def test_moving_one_dedicated_cav_to_shared_population_does_not_duplicate_current():
    raw = raw_input()
    original = ref.bind(raw)
    a, phi0, _ = ref.evaluate(original, ref.initial(original), 0)
    previous = ref.unpack(original, a)
    moved = deepcopy(raw)
    dedicated = moved["model"]["calcium_channels"][0]
    population = dict(
        id="reference_shared_cav_replacement",
        membrane_id=dedicated["membrane_id"],
        kinetic_law="betse_cav1p2_m2h@1",
        max_permeability_m_per_s=dedicated["max_permeability_m_per_s"],
        abundance=dedicated["abundance"],
        initial_gate=[dedicated["initial_gate"][k] for k in ("m", "h")],
        permeant_ions=[dict(species_id="Ca", relative_permeability=1.0)],
    )
    dedicated["abundance"] = 0.0
    moved["model"]["ionic"]["channels"].append(population)
    moved["experiment"]["channel_controls"].append(
        dict(
            channel_id=population["id"],
            schedule=deepcopy(moved["experiment"]["calcium_channel_controls"][0]["schedule"]),
        )
    )
    moved["execution"]["channel_capacity"] += 1
    c = ref.bind(moved)
    b, phi1, proof = ref.evaluate(c, ref.initial(c), 0)
    current = ref.unpack(c, b)
    np.testing.assert_array_equal(phi0, phi1)
    for name in (
        "amount_increment",
        "extracellular_amount_increment",
        "chemical_amount_increment",
        "reaction_extent",
        "er_passive_transferred",
        "plasma_pump_cycles",
        "plasma_exchange_cycles",
    ):
        np.testing.assert_allclose(current[name], previous[name], rtol=3e-13, atol=3e-14)
    ca = [s["id"] for s in c["raw"]["model"]["species"]].index("Ca")
    np.testing.assert_allclose(
        current["channel_transferred"][ca, -1],
        previous["calcium_channel_transferred"][0],
        rtol=3e-15,
        atol=3e-18,
    )
    assert current["calcium_channel_transferred"][0] == 0
    for name in ("channel_transferred", "channel_dissipated_energy_pJ"):
        np.testing.assert_array_equal(current[name][:, :-1], previous[name])
    total_before = (
        previous["channel_dissipated_energy_pJ"].sum()
        + previous["calcium_channel_dissipated_energy_pJ"].sum()
    )
    total_after = (
        current["channel_dissipated_energy_pJ"].sum()
        + current["calcium_channel_dissipated_energy_pJ"].sum()
    )
    np.testing.assert_allclose(total_before, total_after, rtol=3e-15, atol=3e-16)
    assert abs(proof["physical_energy_balance_pJ_s"]) < 3e-10
    evidence(
        "dedicated-shared-replacement",
        dict(
            proof=proof,
            original_dedicated_flux_fmol_s=float(previous["calcium_channel_transferred"][0]),
            replacement_shared_flux_fmol_s=float(current["channel_transferred"][ca, -1]),
            dedicated_disabled=True,
        ),
    )


def test_old_calcium_six_reduction_preserves_every_reference_field_exactly():
    raw = raw_input()
    channels = raw["model"]["ionic"]["channels"]
    added = {*ionic.ADDED_SODIUM_LAWS, *ionic.ADDED_POTASSIUM_LAWS, *ionic.ADDED_LEAK_LAWS}
    raw["model"]["ionic"]["channels"] = [ch for ch in channels if ch["kinetic_law"] not in added]
    names = {ch["id"] for ch in raw["model"]["ionic"]["channels"]}
    raw["experiment"]["channel_controls"] = [
        g for g in raw["experiment"]["channel_controls"] if g["channel_id"] in names
    ]
    c = ref.bind(raw)
    y = modified_state(c, changed=True)
    expanded = ref.evaluate(c, y, 0)
    raw["model"]["id"], raw["model"]["ionic"]["id"] = "resolved_calcium@6", "resolved_tissue@7"
    previous = ref.evaluate(ref.bind(raw), y, 0)
    for actual, expected in zip(expanded[:2], previous[:2], strict=True):
        np.testing.assert_array_equal(actual, expected)
    assert expanded[2] == previous[2]


def test_capacity_padding_does_not_create_independent_physical_owners():
    raw = raw_input()
    padded = deepcopy(raw)
    for key in padded["execution"]:
        if key.endswith("capacity"):
            padded["execution"][key] += 3
    a, b = ref.bind(raw), ref.bind(padded)
    assert a["shapes"] == b["shapes"]
    first, second = (ref.evaluate(c, modified_state(c, changed=True), 0) for c in (a, b))
    for actual, expected in zip(first[:2], second[:2], strict=True):
        np.testing.assert_array_equal(actual, expected)
    assert first[2] == second[2]


@pytest.mark.parametrize(
    "fault",
    [
        "free_calcium",
        "er_calcium",
        "bound_calcium",
        "unused_leak_gate",
        "nonfinite",
        "assembly_levels",
    ],
)
def test_blocked_shared_routes_still_require_valid_owned_state(fault):
    c = ref.bind(raw_input("blocked"))
    d = ref.unpack(c, ref.initial(c))
    store = c["stores"][0]
    if fault in ("free_calcium", "er_calcium", "bound_calcium"):
        species = store.ids.index("CaB" if fault == "bound_calcium" else "Ca")
        compartment = store.er if fault == "er_calcium" else store.cy
        d["chemical_amount_increment"][0, species, compartment] = -store.n0[species, compartment]
    elif fault == "unused_leak_gate":
        j = next(
            j
            for j, ch in enumerate(c["raw"]["model"]["channels"])
            if ch["kinetic_law"] == "betse_catleak_na_k@1"
        )
        d["channel_gate"][1, j] = 1.1
    elif fault == "nonfinite":
        d["chemical_amount_increment"][0, 0, 0] = np.nan
    with pytest.raises(ValueError):
        ref.evaluate(
            c,
            ref.flatten(c, d),
            0,
            channel_levels=np.array([1.1, 0.0]) if fault == "assembly_levels" else None,
        )


def test_independent_worker_has_no_production_or_jax_imports():
    assert not any(name == "cells" or name.startswith("cells.") for name in sys.modules)
    assert not any(name == "jax" or name.startswith("jax.") for name in sys.modules)
