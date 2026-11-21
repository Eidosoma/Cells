"""OL2's geometry worlds in cells.assembly_lineages@2: the bilayer geometry, phase exchange and
permeation (docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md §1, §5; the design note's §0.2b-§0.2d).

Each claim with a planted error it must catch (D187):
- X2: at equal quanta, insertion area at c = 1 has OL1's count_on_m rate table, with
  k_f = k_ins (q k / 2) rho0, on every pair at or above the floor (planted: c = 0 in one world);
- the extents are their closed forms: D 4 pi R(m) rho0 theta for a join under diffusion_radius,
  P A(m) rho0 theta for an entry (planted: the area at the result n' instead of m);
- §0.2c rule 5: below the floor an area-keeping step fires and an area-changing one is zero
  (planted: a molecule floor would zero the dimerisation);
- the kernel identity on the geometry probe and on a run's own world, and the ledger closes;
- a geometry run's bundle is written and read back with its geometry records, and the host oracle
  replays its trace from the saved uniforms (planted: a reverse weight changes the replay); a
  one-slot population with that declared lumen records its one event and writes a bundle without
  the osmotic volume and tension, which need an outside osmolarity it does not have (the Lean
  proofs project's finding at 5011ed3d, whose run returned no records);
- OL1's worlds carry no geometry: no layout leaf, no key written, OL1's verdict;
- every refusal of §0.2b-§0.2c that this version owns.

World-compiling cost: two runs of the lumen world at 128 molecules (the ledger's, and the
bundle's with its uniforms recorded), and one run of the declared-lumen population, 43.92 s for
the whole file on the timed lane; the rate
tables, the probe and the refusals are host arithmetic. Reason: the ledger's closure and the
oracle's replay need the device's run.
"""

import copy
import math

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages_v2 import (
    BILAYER_GEOMETRY,
    IDEAL_MIXING,
    MASS_ACTION,
    MEMBRANE_PERMEATION,
    PHASE_EXCHANGE,
    SHARED_POOL,
    balance,
    kernel,
    model,
    records,
    reference,
    runner,
)
from cells.models.assembly_lineages_v2 import geometry as geometry_rules
from cells.models.assembly_lineages_v2 import spec as spec_rules
from tests.assembly_lineage_v2_fixtures import definition, site_binding, world

Q = 5e-21  # m², the probe's quantum
C0_MM = 1000.0
RHO0 = 6.02214076e23 * C0_MM * 1e-3 * 1e3  # molecules per m³


def tokens(measure="multinomial", encounter="insertion_area"):
    out = {
        "free_energy_form": "discrete",
        "condensed_measure": measure,
        "membrane_kinetics": "count_on_m",
        "lumen_volume": "declared",
        "empty_catalyst_phase": "uncatalysed",
        "last_molecule": "kept",
    }
    if encounter is not None:
        out["exchange_encounter"] = encounter
    return out


def species(name, moieties, **mu):
    return {"id": name, "moieties": moieties, "standard_mu_RT": mu, "catalogue": None,
            "evidence": None}  # fmt: skip


def geometry_block(quanta, floor=60, closure=12.5):
    return {
        "law": BILAYER_GEOMETRY,
        "area_quantum_m2": Q,
        "area_per_leaflet": {
            s: {"quanta": k, "provenance": "test", "sourced_m2": k * Q, "source": "test"}
            for s, k in quanta.items()
        },  # fmt: skip
        "vesicle_floor": {"quanta": floor, "provenance": "unsourced; test"},
        "closure_cost_kT": {"value": closure, "provenance": "unsourced; test"},
    }


def lipid_world(*, geometry=True, measure="multinomial", encounter="insertion_area",
                quanta=None, k_join=2e-8, lumen=False, floor=None):  # fmt: skip
    """A membrane of L and P exchanging L with a finite pool, an L -> P isomerisation inside."""
    quanta = quanta or {"L": 60, "P": 60}
    steps = [
        {"id": "iso", "phase": "membrane", "reactants": {"L": 1}, "products": {"P": 1},
         "law": MASS_ACTION, "forward_rate_per_s": 0.7},
    ]  # fmt: skip
    if geometry:
        key = "insertion_velocity_m_per_s" if encounter == "insertion_area" else (
            "diffusivity_m2_per_s")  # fmt: skip
        steps.insert(
            0,
            {
                "id": "join",
                "locus": "membrane",
                "reactants": {"L@pool": 1},
                "products": {"L@membrane": 1},
                "law": PHASE_EXCHANGE,
                key: {"value": k_join, "provenance": "unsourced; test"},
            },
        )
    else:  # OL1's count_on_m join, with insertion area's constant at equal quanta (X2).
        k = next(iter(quanta.values()))
        steps.insert(
            0,
            {
                "id": "join",
                "locus": "membrane",
                "reactants": {"L@pool": 1},
                "products": {"L@membrane": 1},
                "law": MASS_ACTION,
                "forward_rate_per_s": k_join * (Q * k / 2.0) * RHO0,
            },
        )
    phases = {
        "pool": {"volume_L": 1e-21, "species": [{"id": "L", "kind": "finite"}]},
        "membrane": {"species": ["L", "P"]},
    }
    founder = {"L@pool": 6, "L@membrane": 3, "P@membrane": 2}
    if lumen:
        phases["pool"]["species"].append({"id": "S", "kind": "finite"})
        phases["lumen"] = {"volume_L": 1e-22, "species": ["S"]}
        founder.update({"S@pool": 4, "S@lumen": 1})
        steps.append({"id": "entry", "locus": "membrane", "reactants": {"S@pool": 1},
                      "products": {"S@lumen": 1}, "law": MEMBRANE_PERMEATION,
                      "permeability_m_per_s": {"value": 3e-9,
                                               "provenance": "unsourced; test"}})  # fmt: skip
    out = {
        "units": {"time": "s", "temperature_K": 296.15, "standard_concentration_mM": C0_MM},
        "conventions": tokens(measure, encounter if geometry else None),
        "species": [
            species("L", {"l": 1}, solution=0.0, bilayer=-2.0),
            species("P", {"l": 1}, bilayer=-2.5),
            species("S", {"s": 1}, solution=0.0),
        ],  # fmt: skip
        "phases": phases,
        "steps": steps,
        "free_energy": [{"law": IDEAL_MIXING}],
        "founder": founder,
    }
    if geometry:
        k = min(quanta.values())
        out["geometry"] = geometry_block(quanta, floor=floor if floor is not None else k)
    return out


def spec_of(world_dict, capacity=64):
    return parse_spec(definition(world_dict, molecules=capacity))


def host_log_rates(spec, counts):
    structure, layout = model.structure(spec), model.layout(spec)
    counts = np.asarray(counts, dtype=np.int64)
    padded = np.zeros(structure.places, dtype=np.int64)
    padded[: counts.size] = counts
    return balance.host_log_rates(padded, layout, structure)


def states(spec, rng, n=60):
    world_ = spec.model.world
    out = []
    for _ in range(n):
        c = np.zeros(len(world_.places), dtype=np.int64)
        for i in range(len(world_.places)):
            c[i] = rng.integers(0, 9)
        membrane = [i for i, p in enumerate(world_.places) if p.phase == "membrane"]
        if c[membrane].sum() == 0:
            c[membrane[0]] = 1
        out.append(c)
    return out


def test_insertion_area_at_equal_quanta_is_count_on_m_at_c_1():
    rng = np.random.default_rng(11)
    geo = spec_of(lipid_world(geometry=True, measure="multinomial_less_one"))
    ol1 = spec_of(lipid_world(geometry=False, measure="multinomial_less_one"))
    assert model.structure(geo).geometry == BILAYER_GEOMETRY
    assert model.structure(ol1).geometry is None and model.layout(ol1).geometry == ()
    for c in states(geo, rng):
        a, b = host_log_rates(geo, c), host_log_rates(ol1, c)
        assert np.array_equal(np.isfinite(a), np.isfinite(b))
        finite = np.isfinite(a)
        np.testing.assert_allclose(a[finite], b[finite], rtol=0, atol=1e-11)
    # Planted: c = 0 in the OL1 world (its join's extent is N + 1, not N): the tables differ.
    planted = spec_of(lipid_world(geometry=False, measure="multinomial"))
    c = np.asarray([6, 3, 2], dtype=np.int64)
    assert not np.allclose(host_log_rates(geo, c)[:1], host_log_rates(planted, c)[:1])


def test_permeation_and_diffusion_radius_rates_are_their_closed_forms():
    s = spec_of(lipid_world(encounter="diffusion_radius", k_join=4e-17, lumen=True))
    w = s.model.world
    names = [p.name for p in w.places]
    x_pool = 6.02214076e23 * 1e-21 * 1.0  # N_A V c0 (V in L, c0 in mol/L)
    for c in ([6, 4, 3, 2, 1], [2, 1, 5, 0, 3], [9, 2, 1, 7, 2]):
        counts = dict(zip(names, c, strict=True))
        log_a = host_log_rates(s, c)
        footprint = 60 * (counts["L@membrane"] + counts["P@membrane"])
        radius = math.sqrt(Q * footprint / 2.0 / (4.0 * math.pi))  # m = n for a join
        join = 4e-17 * 4.0 * math.pi * radius * RHO0 * counts["L@pool"] / x_pool
        entry = 3e-9 * (Q * footprint / 2.0) * RHO0 * counts["S@pool"] / x_pool
        steps = [st.id for st in w.steps]
        assert math.isclose(math.exp(log_a[steps.index("join")]), join, rel_tol=1e-12)
        assert math.isclose(math.exp(log_a[steps.index("entry")]), entry, rel_tol=1e-12)
        # Planted: the join's area at the result n' (one more L) is not the kernel's.
        planted = 4e-17 * 4.0 * math.pi * math.sqrt(Q * (footprint + 60) / 8.0 / math.pi) * RHO0
        planted *= counts["L@pool"] / x_pool
        assert not math.isclose(math.exp(log_a[steps.index("join")]), planted, rel_tol=1e-6)


def floor_world():
    """probe_floor.py's world: A (1 quantum) and its dimer B (2), the dimerisation keeps W."""
    return {
        "units": {"time": "s", "temperature_K": 296.15, "standard_concentration_mM": C0_MM},
        "conventions": tokens(),
        "species": [
            species("A", {"a": 1}, solution=0.0, bilayer=-1.0),
            species("B", {"a": 2}, bilayer=-3.0),
        ],  # fmt: skip
        "phases": {
            "pool": {"volume_L": 1e-21, "species": [{"id": "A", "kind": "finite"}]},
            "membrane": {"species": ["A", "B"]},
        },  # fmt: skip
        "steps": [
            {
                "id": "join",
                "locus": "membrane",
                "reactants": {"A@pool": 1},
                "products": {"A@membrane": 1},
                "law": PHASE_EXCHANGE,
                "insertion_velocity_m_per_s": {"value": 1e-6, "provenance": "unsourced; test"},
            },
            {
                "id": "dimer",
                "phase": "membrane",
                "reactants": {"A": 2},
                "products": {"B": 1},
                "law": MASS_ACTION,
                "forward_rate_per_s": 0.5,
            },
        ],  # fmt: skip
        "free_energy": [{"law": IDEAL_MIXING}],
        "founder": {"A@pool": 4, "A@membrane": 6, "B@membrane": 1},
        "geometry": geometry_block({"A": 1, "B": 2}, floor=6),
    }


def test_below_the_floor_an_area_keeping_step_fires_and_an_area_changing_one_is_zero():
    s = spec_of(floor_world())
    R = model.structure(s).steps
    log_a = host_log_rates(s, [4, 2, 1])  # W = 2 + 2 = 4 < 6, N = 3
    join, dimer = 0, 1
    assert log_a[join] == -np.inf and log_a[R + join] == -np.inf  # changes W, below the floor
    assert np.isfinite(log_a[dimer]) and np.isfinite(log_a[R + dimer])  # keeps W: fires
    above = host_log_rates(s, [4, 6, 1])  # W = 8
    assert np.isfinite(above[join]) and np.isfinite(above[R + join])
    # The dimerisation fires at its own count_on_m rate, k E(m) ff(2, 2)/ff(3, 2) with
    # E(m) = N(m) + 1 = 2: 0.5 * 2 * 2 / 6. A molecule floor (planted, N >= 4) would zero it.
    assert math.isclose(math.exp(log_a[dimer]), 0.5 * 2 * 2 / 6, rel_tol=1e-12)
    molecule_floor = 4
    assert min(2 + 1, 0 + 2) < molecule_floor  # Both end states below it: the plant gives zero.
    # §0.2e rule 6: the closure cost from the bending moduli, by the engine's own law.
    moduli = floor_world()
    moduli["geometry"].pop("closure_cost_kT")
    moduli["geometry"].update(
        kappa_kT={"value": 10.0, "provenance": "unsourced; test"},
        kappa_bar_kT={"value": -5.0, "provenance": "unsourced; test"},
    )
    closure = geometry_rules.closure_kT(spec_of(moduli).model.world)
    assert closure == 8.0 * math.pi * 10.0 + 4.0 * math.pi * (-5.0)
    # The world's own identity holds, the floor's zeroed pairs skipped.
    assert balance.world_report(s)["max_abs_deviation_ln"] <= balance.ATOL


def test_the_geometry_probe_keeps_the_identity_and_a_run_closes_its_ledger():
    verdict = balance.geometry_verdict()
    assert verdict["holds"] and verdict["probe"]["pairs"] > 1000
    assert verdict["probe"]["max_abs_deviation_ln"] <= balance.ATOL
    d = copy.deepcopy(definition(lipid_world(lumen=True), molecules=128))
    d["experiment"].update(time_horizon_s=20.0, event_limit=2000, row_every_events=50)
    s = parse_spec(d)
    run = runner.run(s).check()
    assert run.closure["holds"] and run.verdict == verdict
    footprint = run.rows["membrane_footprint_quanta"]
    assert footprint.min() >= geometry_rules.floor_quanta(s.model.world)
    # F carries the closure cost once (one living vesicle): F(n_0) differs by exactly C_close.
    free = model.tables(s)
    assert run.rows["free_energy_kT"][0] == pytest.approx(
        balance.ledger.free_energy(model.founder(s), free, s.model.world.terms,
                                   model.layout(s).terms) + 12.5, abs=1e-12)  # fmt: skip


def test_a_geometry_bundle_reads_back_and_the_host_oracle_replays_its_trace(tmp_path):
    d = copy.deepcopy(definition(lipid_world(lumen=True), molecules=128, uniforms=True))
    d["experiment"].update(time_horizon_s=20.0, event_limit=600, row_every_events=50)
    s = parse_spec(d)
    run = runner.run(s).check()
    records.write_run(tmp_path / "bundle", run)
    world_record, run_record, arrays = records.read(tmp_path / "bundle")
    assert world_record["world"]["geometry"]["law"] == BILAYER_GEOMETRY
    assert world_record["world"]["conventions"]["exchange_encounter"] == "insertion_area"
    derived = world_record["derived"]["geometry"]
    assert derived["floor_quanta"] == 60 and derived["closure_kT"] == 12.5
    footprint = arrays["membrane_footprint_quanta"]
    assert np.array_equal(footprint, run.rows["membrane_footprint_quanta"])
    assert run_record["records"]["membrane_footprint_quanta"]["unit"] == "quanta"
    assert BILAYER_GEOMETRY in run_record["engine_models"]["laws"]
    # The host oracle (NumPy, from the saved uniforms) replays the device's trace exactly.
    channels, times = reference.replay(s, arrays["event_uniforms"])
    assert np.array_equal(channels, arrays["event_channel"])
    np.testing.assert_allclose(times, arrays["event_time"], rtol=1e-12, atol=0)
    # Planted: every reverse rate weighted before the draw, which the replay must not match.
    planted, _ = reference.replay(s, arrays["event_uniforms"], reverse_weight=1.5)
    assert not np.array_equal(planted, arrays["event_channel"])
    # A one-slot population with this declared lumen (the Lean proofs project's reproducer): its
    # one event, S's entry, is recorded, with no osmotic volume or tension rows.
    raw = lipid_world(lumen=True)
    raw["steps"] = [step for step in raw["steps"] if step["id"] == "entry"]
    raw["founder"] = {"L@pool": 0, "S@pool": 1, "L@membrane": 0, "P@membrane": 0, "S@lumen": 0}
    founder = {"L@membrane": 0, "P@membrane": 4, "S@lumen": 0}
    raw["population"] = {"structure": SHARED_POOL, "slots": 1, "founders": [founder]}
    d = definition(raw, molecules=16, horizon=1e7, event_limit=1, row_every=1)
    d["execution"]["mode"] = "population"
    pop = runner.run(parse_spec(d)).check()
    inside = pop.spec.model.world.place_index("S@lumen")
    assert pop.rows["slot_count"][-1, 0, inside] == 1
    records.write_run(tmp_path / "population", pop)
    _, saved_run, saved = records.read(tmp_path / "population")
    assert not {"lumen_volume_L", "tension_N_per_m"} & (set(saved) | set(saved_run["records"]))
    assert np.array_equal(saved["slot_count"], pop.rows["slot_count"])


def test_ol1_worlds_carry_no_geometry():
    s = parse_spec(definition(world()))
    assert model.structure(s).geometry is None and model.layout(s).geometry == ()
    body = spec_rules.world_to_dict(s.model.world)
    assert "geometry" not in body and "exchange_encounter" not in body["conventions"]
    assert all("rate_key" not in step for step in body["steps"])
    assert kernel.Layout._fields[-1] == "geometry"  # The one new field, last, empty here.


REFUSALS = {
    "exchange_encounter without a geometry": (
        lambda w: (w.pop("geometry"), w["steps"].pop(0)), "declared only by a world that declares"),
    "a geometry without exchange_encounter": (
        lambda w: w["conventions"].pop("exchange_encounter"), "declares exchange_encounter"),
    "a mass-action join in a geometry world": (
        lambda w: w["steps"][0].update(law=MASS_ACTION, forward_rate_per_s=1.0)
        or w["steps"][0].pop("insertion_velocity_m_per_s"), "crosses phases at the membrane"),
    "a join declared as the leave": (
        lambda w: w["steps"][0].update(reactants={"L@membrane": 1}, products={"L@pool": 1}),
        "declared as a join"),
    "a floor with last_molecule reversible": (
        lambda w: w["conventions"].update(last_molecule="reversible"), "requires last_molecule"),
    "a founder below the floor": (
        lambda w: w["geometry"].update(
            vesicle_floor={"quanta": 10**6, "provenance": "unsourced; test"}
        ),
        "below the vesicle floor"),
    "sigma_max before the osmotic lumen": (
        lambda w: w["geometry"].update(sigma_max_N_per_m={"value": 0.01, "provenance": "t"}),
        "only under lumen_volume osmotic",
    ),
    "a membrane species without its area": (
        lambda w: w["geometry"]["area_per_leaflet"].pop("P"), "every membrane species"),
    "quanta that are not the nearest": (
        lambda w: w["geometry"]["area_per_leaflet"]["P"].update(quanta=61), "a nearest quantum"),
    # §0.2e rules 3, 5, 6 and 7 (19 November 2026).
    "an area without its provenance": (
        lambda w: w["geometry"]["area_per_leaflet"]["P"].pop("provenance"), "quanta, provenance"),
    "a sourced area without its source": (
        lambda w: w["geometry"]["area_per_leaflet"]["P"].pop("source"),
        "sourced_m2 and source together",
    ),
    "both forms of the closure cost": (
        lambda w: w["geometry"].update(kappa_kT={"value": 10.0, "provenance": "t"},
                                       kappa_bar_kT={"value": -5.0, "provenance": "t"}),
        "closure cost is declared as"),
    "a rate key without its provenance": (
        lambda w: w["steps"][0].update(insertion_velocity_m_per_s=2e-8), "value, provenance"),
    # FR-21 (§0.2f): rule 3 admits exactly X@pool + site@membrane -> complex@membrane for a
    # declared pair; every other interfacial shape stays refused, declared pair or not.
    "a site binding whose pair is undeclared": (
        lambda w: site_binding(w, declared=False), "crosses phases at the membrane"),
    "a second binding on an undeclared pair": (
        lambda w: _second_pair(site_binding(w)), "crosses phases at the membrane"),
    "a binding of two ligands": (
        lambda w: _two_ligands(site_binding(w)), "crosses phases at the membrane"),
    "a binding from the lumen": (
        lambda w: _lumen_ligand(site_binding(w)), "crosses phases at the membrane"),
    "a binding declared as the release": (
        lambda w: _as_release(site_binding(w)), "crosses phases at the membrane"),
    "a site that is no membrane species": (
        lambda w: site_binding(w)["sites"][0].update(site="X"), "not a membrane species"),
    "a complex declared for two sites": (
        lambda w: site_binding(w)["sites"].append({"site": "P", "complex": "XR"}),
        "declared twice"),
}  # fmt: skip


def _bind_step(w):
    return next(s for s in w["steps"] if s["id"] == "bind")


def _second_pair(w):
    """A second complex, XP, of the undeclared site P, bound in one step from the pool."""
    w["species"].append(species("XP", {"x": 1, "l": 1}, bilayer=-6.0))
    w["phases"]["membrane"]["species"].append("XP")
    w["geometry"]["area_per_leaflet"]["XP"] = {"quanta": 60, "provenance": "test"}
    w["founder"]["XP@membrane"] = 0
    w["steps"].append(dict(_bind_step(w), id="bind_P", reactants={"X@pool": 1, "P@membrane": 1},
                           products={"XP@membrane": 1}))  # fmt: skip
    return w


def _two_ligands(w):
    """The declared pair's complex holding two ligands, bound in one step: X2R."""
    w["species"].append(species("X2R", {"x": 2, "r": 1}, bilayer=-8.0))
    w["phases"]["membrane"]["species"].append("X2R")
    w["geometry"]["area_per_leaflet"]["X2R"] = {"quanta": 60, "provenance": "test"}
    w["founder"]["X2R@membrane"] = 0
    w["sites"] = [{"site": "R", "complex": "X2R"}]
    _bind_step(w).update(reactants={"X@pool": 2, "R@membrane": 1}, products={"X2R@membrane": 1})
    return w


def _lumen_ligand(w):
    w["phases"]["lumen"] = {"volume_L": 1e-22, "species": ["X"]}
    w["founder"]["X@lumen"] = 0
    _bind_step(w)["reactants"] = {"X@lumen": 1, "R@membrane": 1}
    return w


def _as_release(w):
    _bind_step(w).update(reactants={"XR@membrane": 1}, products={"X@pool": 1, "R@membrane": 1})
    return w


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_every_refusal_this_version_owns(case):
    edit, message = REFUSALS[case]
    w = lipid_world()
    edit(w)
    with pytest.raises(ConfigError, match=message):
        spec_of(w)


def test_a_declared_site_binding_has_its_closed_form_rates_and_keeps_the_identity():
    """FR-21 (§0.2f): X@pool + R@membrane -> XR@membrane, its pair declared, on the osmotic
    vesicle. a+ = k_f theta+ n_R and a- = k_f e^(mu_XR - mu_R - mu_X) n_XR at equal site and complex
    areas (theta+ the pool's activity; 0 without a free X); the pair identity at random states,
    also with the complex larger than the site, where the osmotic excess moves. Host arithmetic."""
    from tests.unit.test_assembly_lineages_v2_lumen import K_L, osmotic_world

    def vesicle(complex_quanta=None):
        w = osmotic_world(L_pool=30, L_mem=8, S_pool=6, S_lumen=0, I_lumen=2, floor=4 * K_L)
        site_binding(w, k_f=50.0, mu_complex=-6.0, complex_quanta=complex_quanta)
        return spec_of(w, capacity=128)

    s = vesicle()
    w, structure, layout = s.model.world, model.structure(s), model.layout(s)
    R, r = structure.steps, [st.id for st in w.steps].index("bind")
    at = {p.name: i for i, p in enumerate(w.places)}
    X = 6.02214076e23 * w.volume("pool") * w.units.standard_concentration_mM * 1e-3
    k_rev = 50.0 * math.exp(-6.0 - (-2.0) - 0.0)
    for x, n_r, n_xr in ((8, 4, 2), (1, 5, 1), (0, 4, 2), (5, 0, 6)):
        c = np.zeros(structure.places, dtype=np.int64)
        c[[at["L@pool"], at["S@pool"], at["L@membrane"], at["I@lumen"]]] = (30, 6, 8, 2)
        c[[at["X@pool"], at["R@membrane"], at["XR@membrane"]]] = (x, n_r, n_xr)
        log = balance.host_log_rates(c, layout, structure)
        assert math.exp(log[r]) == pytest.approx(50.0 * (x / X) * n_r, rel=1e-13, abs=0)
        assert math.exp(log[R + r]) == pytest.approx(k_rev * n_xr, rel=1e-13, abs=0)
    for quanta in (None, 90):  # the complex's area equal to the site's, then larger
        found = balance.deviations(vesicle(quanta), np.random.default_rng(5), states=200)
        assert found.size > 400 and np.max(np.abs(found)) <= balance.ATOL


def test_a_geometric_law_without_a_geometry_is_refused():
    w = lipid_world()
    w.pop("geometry")
    w["conventions"].pop("exchange_encounter")
    with pytest.raises(ConfigError, match="takes its encounter from a geometry"):
        spec_of(w)
