"""OL2's geometry worlds in cells.model.assembly_lineages@2: the bilayer geometry, phase exchange and
permeation (docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md §1, §5; the design note's §0.2b-§0.2d).

Each claim with a planted error it must catch (D187):
- X2: at equal quanta, insertion area at c = 1 has OL1's count_on_m rate table, with
  k_f = k_ins (q k / 2) rho0, on every pair at or above the floor (planted: c = 0 in one world);
- the extents are their closed forms: D 4 pi R(m) rho0 theta for a join under diffusion_radius,
  P A(m) rho0 theta for an entry (planted: the area at the result n' instead of m);
- §0.2c rule 5: below the floor an area-keeping step fires and an area-changing one is zero
  (planted: a molecule floor would zero the dimerisation);
- the kernel identity on the geometry probe and on a run's own world, and the ledger closes; a
  world whose floor no drawn state reaches has its probe states lifted to the floor, so its joins
  are paired (planted: without the lift its report refuses, no pair checked; with it, an error in
  the join's reverse is refused);
- a geometry run's bundle is written and read back with its geometry records, and the host oracle
  replays its trace from the saved uniforms (planted: a reverse weight changes the replay); a
  one-slot population with that declared lumen records its one event and writes a bundle without
  the osmotic volume and tension, which need an outside osmolarity it does not have (the Lean
  proofs project's finding at 5011ed3d, whose run returned no records);
- OL1's worlds carry no geometry: no layout leaf, no key written, OL1's verdict;
- every refusal of §0.2b-§0.2c that this version owns;
- FR-21's site step (§0.2f): a declared binding's closed-form rates and the identity, and the
  shapes rule 3 still refuses;
- FR-21's shell (§0.2g), the requester's acceptance: a tracer's entry and exit follow the declared
  conductance P_s A_sh alone (planted: the transition-state factor over every wall molecule, under
  which the site count moves the gated rate); the shell probe keeps the identity, a short run
  closes its books, and every refusal of a shell.

World-compiling cost: two runs of the lumen world at 128 molecules (the ledger's, and the
bundle's with its uniforms recorded), one run of the declared-lumen population, and FR-21's one
short shell run; the rate tables, the probes and the refusals are host arithmetic. Reason: the
ledger's closure and the oracle's replay need the device's run.
"""

import copy
import math

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages_v2 import (
    BILAYER_GEOMETRY,
    GATE_FACTOR,
    IDEAL_MIXING,
    MASS_ACTION,
    MEMBRANE_PERMEATION,
    PHASE_EXCHANGE,
    PRESCRIBED_SHELL,
    SHARED_POOL,
    SHEAR_FISSION,
    SHELL_PERMEATION,
    TRANSITION_STATE,
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
    "an inner pair outside a shell": (  # FR-46 (R6): refused by name, even with no inner step
        lambda w: _inner_pair(site_binding(w)), "admits in a cells.assembly_geometry.prescribed_shell@1 world only"),
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


def _inner_pair(w):
    """FR-46: the fixture's declared pair on the inner face, in a bilayer world."""
    w["sites"][0]["face"] = "inner"
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


def shell_world(*, area=1e-15, P=2e-7, B=3, R=4, XR=2, out=6, inside=2, factor=GATE_FACTOR):
    """FR-21's shell: a wall of gate forms G and H (one each, no flip: a fixed gate state), sites R
    and their complexes XR (a ligand X binds in one step), and a subunit B; a tracer S at fixed
    counts outside and inside; its entry by the shell's permeation, gated over the gate's forms."""
    u = "unsourced; test"
    gate = [{"form": "G", "step": "entry", "ddG_kT": 2.0},
            {"form": "H", "step": "entry", "ddG_kT": -2.0}]  # fmt: skip
    rate_factor = {"law": GATE_FACTOR, "forms": ["G", "H"], "entries": gate}
    if factor == TRANSITION_STATE:  # the planted factor: fractions over every wall molecule
        rate_factor = {"law": TRANSITION_STATE, "catalysing_phase": "membrane",
                       "entries": [{"catalyst": e["form"], "step": "entry",
                                    "ddG_kT": e["ddG_kT"]} for e in gate]}  # fmt: skip
    return {
        "units": {"time": "s", "temperature_K": 296.15, "standard_concentration_mM": C0_MM},
        "conventions": {"free_energy_form": "discrete", "condensed_measure": "multinomial",
                        "membrane_kinetics": "count_on_m", "lumen_volume": "declared",
                        "empty_catalyst_phase": "uncatalysed", "last_molecule": "kept"},
        "species": [species("S", {"s": 1}, solution=0.0), species("X", {"x": 1}, solution=0.0),
                    species("G", {"g": 1}, bilayer=-1.0), species("H", {"g": 1}, bilayer=-1.5),
                    species("R", {"r": 1}, bilayer=-2.0),
                    species("XR", {"x": 1, "r": 1}, bilayer=-6.0),
                    species("B", {"b": 1}, bilayer=-3.0)],
        "phases": {"pool": {"volume_L": 1e-21, "species": [{"id": "S", "kind": "finite"},
                                                            {"id": "X", "kind": "finite"}]},
                   "membrane": {"species": ["G", "H", "R", "XR", "B"]},
                   "lumen": {"volume_L": 1e-22, "species": ["S"]}},
        "steps": [{"id": "entry", "locus": "membrane", "reactants": {"S@pool": 1},
                   "products": {"S@lumen": 1}, "law": SHELL_PERMEATION,
                   "permeability_m_per_s": {"value": P, "provenance": u}},
                  {"id": "bind", "locus": "membrane", "reactants": {"X@pool": 1, "R@membrane": 1},
                   "products": {"XR@membrane": 1}, "law": MASS_ACTION,
                   "forward_rate_per_s": 3.0}],
        "free_energy": [{"law": IDEAL_MIXING}],
        "rate_factor": rate_factor,
        "sites": [{"site": "R", "complex": "XR"}],
        "founder": {"S@pool": out, "X@pool": 5, "S@lumen": inside, "G@membrane": 1,
                    "H@membrane": 1, "R@membrane": R, "XR@membrane": XR, "B@membrane": B},
        "geometry": {"law": PRESCRIBED_SHELL, "area_m2": {"value": area, "provenance": u}},
    }  # fmt: skip


def test_a_shell_s_rates_follow_its_declared_conductance_alone():
    """FR-21's shell, the requester's acceptance (docs/FEATURE_REQUESTS.md, FR-21), on the host:
    with the tracer's counts and the gate's forms fixed, (1) doubling A_sh while halving P_s keeps
    the entry and the exit rate to rounding; (2) doubling P_s alone doubles both, exactly (k_f
    scales the rate after the exponential); (3) changing only the wall's inventory or the site
    count keeps both rates bit for bit, and the declared lumen volume. The entry is
    P_s A_sh rho0 theta+ g, with g = (e^2 + e^-2)/2 over the gate's forms."""

    def rates(**kw):
        s = spec_of(shell_world(**kw))
        structure, layout = model.structure(s), model.layout(s)
        c = model.founder(s)
        totals = kernel.totals_of(c, layout, np)
        f, t = kernel.states(c, totals, layout, structure, np)
        a = kernel.rates(c, totals, f, t, layout, structure, np)
        r = [st.id for st in s.model.world.steps].index("entry")
        return float(a[r]), float(a[structure.steps + r]), s.model.world.volume("lumen")

    base = rates()
    X_pool = RHO0 * 1e-21 * 1e-3  # N_A V c0: the pool's molecules at unit activity
    g = (math.exp(2.0) + math.exp(-2.0)) / 2.0
    assert base[0] == pytest.approx(2e-7 * 1e-15 * RHO0 * (6 / X_pool) * g, rel=1e-13, abs=0)
    entry, exit_, volume = rates(area=2e-15, P=1e-7)  # (1)
    assert entry == pytest.approx(base[0], rel=1e-14) and exit_ == pytest.approx(base[1], rel=1e-14)
    assert rates(P=4e-7)[:2] == (2.0 * base[0], 2.0 * base[1])  # (2)
    assert rates(B=11) == base and rates(R=9, XR=0) == base  # (3), the lumen volume included
    # Planted: the transition-state factor's fractions over every wall molecule move the gated
    # rate with the site count, which the gate factor's own forms do not.
    planted = rates(factor=TRANSITION_STATE)
    assert rates(factor=TRANSITION_STATE, R=9, XR=0)[0] != planted[0]
    verdict = balance.shell_verdict()
    assert verdict["holds"] and verdict["probe"]["max_abs_deviation_ln"] <= balance.ATOL
    d = definition(shell_world(), molecules=64, horizon=0.5, event_limit=500)
    run = runner.run(parse_spec(d)).check()
    assert run.closure["holds"] and run.verdict == verdict


def test_a_shell_run_records_the_shell_probe_in_both_modes(tmp_path, monkeypatch):
    """A review finding of 20 November: a shell's population run took the bilayer's probe. Now a
    single-lineage run and a one-slot population run of shell_world() each record the shell probe's
    verdict, in the run and in run.json's check.probe after a write and a read, and neither writes
    the bilayer's footprint rows. Planted: the bilayer's probe in population mode is caught. Two
    short compiled runs (0.001 s, capacity 64), since the verdict is the run's own record."""
    verdict = balance.shell_verdict()

    def population_spec():
        w = shell_world()
        slot = {k: v for k, v in w["founder"].items() if not k.endswith("@pool")}
        w["founder"] = {k: (v if k.endswith("@pool") else 0) for k, v in w["founder"].items()}
        w["population"] = {"structure": SHARED_POOL, "slots": 1, "founders": [slot]}
        d = definition(w, molecules=64, horizon=0.001, event_limit=500)
        d["execution"]["mode"] = "population"
        return parse_spec(d)

    single = parse_spec(definition(shell_world(), molecules=64, horizon=0.001, event_limit=500))
    for name, spec in (("single", single), ("population", population_spec())):
        run = runner.run(spec).check()
        records.write_run(tmp_path / name, run)
        _, run_json, arrays = records.read(tmp_path / name)
        assert run.verdict == verdict and run_json["check"]["probe"] == verdict, name
        assert "membrane_footprint_quanta" not in arrays, name
    monkeypatch.setattr(balance, "shell_verdict", balance.geometry_verdict)  # planted
    assert runner.run(population_spec()).check().verdict != verdict


def test_an_identity_checked_on_no_pair_is_refused_never_reported_as_zero(monkeypatch):
    """D263 (a vacuous check): a check that finds no pair for a world with steps refuses, never
    reporting a zero error. The world's own report, the shell probe and every other probe (the
    bilayer's, the osmotic lumen's and OL1's) are planted with deviations that find no pair. The
    real shell probe and a shell world's own report count their pairs. Host arithmetic; the planted
    probes stop at their first world."""
    assert balance.shell_verdict()["probe"]["pairs"] > 1000
    spec = spec_of(shell_world())
    assert balance.world_report(spec)["pairs"] > 0
    # The independent checker's case: a shell at molecule_capacity 2 (X binding a wall site R, S
    # entering, one molecule of each). Its probe states are now drawn within its capacity, so its
    # own data is checked; drawn up to 12 a place, as before, it checked no pair, which now refuses.
    tiny = shell_world(B=0, R=1, XR=0, out=1, inside=0)
    tiny.pop("rate_factor")
    for form in ("G", "H"):
        tiny["species"] = [x for x in tiny["species"] if x["id"] != form]
        tiny["phases"]["membrane"]["species"].remove(form)
        del tiny["founder"][f"{form}@membrane"]
    tiny["species"] = [x for x in tiny["species"] if x["id"] != "B"]
    tiny["phases"]["membrane"]["species"].remove("B")
    del tiny["founder"]["B@membrane"]
    tiny["founder"]["X@pool"] = 1
    low = spec_of(tiny, capacity=2)
    assert balance.world_report(low)["pairs"] > 0
    # OL5's registered OL3 worlds (floors of 200 to 1,500 quanta at a quantum a molecule): a world
    # whose floor no drawn state reaches has its states lifted to it, so its joins are paired.
    high = floor_world()
    high["steps"] = [x for x in high["steps"] if x["id"] == "join"]  # every step changes W
    high["geometry"]["vesicle_floor"]["quanta"] = 100
    high["founder"]["A@membrane"] = 100
    high_spec = spec_of(high, capacity=256)
    assert balance.world_report(high_spec)["pairs"] > 0
    real_rates = balance.host_log_rates

    def wrong_reverse(n, layout, structure):  # planted: the join's reverse off by 1e-6 in ln
        out = np.array(real_rates(n, layout, structure), dtype=np.float64)
        if np.isfinite(out[structure.steps]):
            out[structure.steps] += 1e-6
        return out

    with monkeypatch.context() as m:
        m.setattr(balance, "_WORLD_REPORTS", {})
        m.setattr(balance, "lifted_to_floor", lambda counts, *rest: counts)  # planted: no lift
        with pytest.raises(ConfigError, match="checked on no pair"):
            balance.world_report(high_spec)
    with monkeypatch.context() as m:
        m.setattr(balance, "_WORLD_REPORTS", {})
        m.setattr(balance, "host_log_rates", wrong_reverse)
        with pytest.raises(ConfigError, match="fail the identity"):
            balance.world_report(high_spec)
    real_state = balance.random_state

    def old_draw(world, places, rng, max_count):  # planted: the old draw, up to 12 a place
        return real_state(world, places, rng, 12)

    monkeypatch.setattr(balance, "random_state", old_draw)
    with pytest.raises(ConfigError, match="checked on no pair"):
        balance.world_report(low, states=60)
    monkeypatch.setattr(balance, "deviations", lambda *args, **kwargs: np.zeros(0))
    monkeypatch.setattr(balance, "_WORLD_REPORTS", {})  # the planted check is not a kept report
    checks = (lambda: balance.world_report(spec), balance._shell_verdict.__wrapped__,
              balance._geometry_verdict.__wrapped__, balance._osmotic_verdict.__wrapped__,
              balance._verdict.__wrapped__)  # fmt: skip
    for check in checks:
        with pytest.raises(ConfigError, match="checked on no pair"):
            check()


SHELL_REFUSALS = {
    "a join on a shell": (
        lambda w: w["steps"].append({"id": "join", "locus": "membrane",
                                     "reactants": {"X@pool": 1}, "products": {"X@membrane": 1},
                                     "law": PHASE_EXCHANGE,
                                     "insertion_velocity_m_per_s": {"value": 1e-9,
                                                                    "provenance": "t"}}),
        "has no join"),
    "the bilayer's permeation on a shell": (
        lambda w: w["steps"][0].update(law=MEMBRANE_PERMEATION), "a shell's entry takes"),
    "an osmotic shell": (
        lambda w: w["conventions"].update(lumen_volume="osmotic"), "does not swell"),
    "an exchange encounter on a shell": (
        lambda w: w["conventions"].update(exchange_encounter="insertion_area"),
        "declares no exchange_encounter"),
    "area quanta on a shell": (
        lambda w: w["geometry"].update(area_per_leaflet={}), "declares no area_per_leaflet"),
    "a floor on a shell": (
        lambda w: w["geometry"].update(vesicle_floor={"quanta": 1, "provenance": "t"}),
        "declares no vesicle_floor"),
    "a lysis tension on a shell": (
        lambda w: w["geometry"].update(sigma_max_N_per_m={"value": 1.0, "provenance": "t"}),
        "declares no sigma_max_N_per_m"),
    "a shell without its lumen": (
        lambda w: (w["phases"].pop("lumen"), w["founder"].pop("S@lumen"), w["steps"].pop(0),
                   w.pop("rate_factor")), "owns a lumen"),
    "a shell's division": (
        lambda w: w.update(division={"law": SHEAR_FISSION}), "needs a geometry and an osmotic"),
    "a gate form that is not in the wall": (
        lambda w: w["rate_factor"].update(forms=["G", "S"]), "not a membrane species"),
    "the shell's permeation on a bilayer": (
        lambda w: w.clear() or w.update(_bilayer_with_shell_entry()), "is a prescribed shell's"),
    # FR-48 (D323): a lumen potential's version 1 scope, each refused by name
    "a lumen potential on a species with no lumen place": (
        lambda w: w["species"][1]["standard_mu_RT"].update(lumen=0.5), "has no lumen place"),
    "a lumen potential without a solution potential": (
        lambda w: (w["species"].append(species("Q", {"q": 1}, lumen=0.3)),
                   w["phases"]["lumen"]["species"].append("Q"),
                   w["founder"].update({"Q@lumen": 1})),
        "without a solution potential"),
    "a lumen potential on a bilayer": (
        lambda w: w.clear() or w.update(_bilayer_with_lumen_potential()),
        "admits in a cells.assembly_geometry.prescribed_shell@1 world only"),
}  # fmt: skip


def _bilayer_with_lumen_potential():
    w = lipid_world(lumen=True)
    for entry in w["species"]:
        if entry["id"] == "S":
            entry["standard_mu_RT"]["lumen"] = entry["standard_mu_RT"].get("solution", 0.0) + 0.5
    return w


def _bilayer_with_shell_entry():
    w = lipid_world(lumen=True)
    entry = next(s for s in w["steps"] if s["id"] == "entry")
    entry["law"] = SHELL_PERMEATION
    return w


@pytest.mark.parametrize("case", sorted(SHELL_REFUSALS))
def test_every_refusal_of_a_shell(case):
    edit, message = SHELL_REFUSALS[case]
    w = shell_world()
    edit(w)
    with pytest.raises(ConfigError, match=message):
        spec_of(w)


def test_a_geometric_law_without_a_geometry_is_refused():
    w = lipid_world()
    w.pop("geometry")
    w["conventions"].pop("exchange_encounter")
    with pytest.raises(ConfigError, match="takes its encounter from a geometry"):
        spec_of(w)
