"""cells.rate_equations@1, OL6's first slice (S1; docs/OL6_DETERMINISTIC_REPRESENTATION_DESIGN.md).

The deterministic representation of OL1's laws in a single lineage: its parse and refusals, the
limit's check with two planted failures (P-D2, a power off by one; P-D7, a shifted μ° in F_cont
only), parity with the exact kernel, a linear network against its matrix exponential, and a closed
membrane world that relaxes to F_cont's minimum with its books closed. A new file for a new
representation (D224); about 60 s, compiling included.
"""

import copy
import dataclasses

import jax
import jax.numpy as jnp
import numpy as np
import pytest
from scipy.linalg import expm

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages_v2 import (
    IDEAL_MIXING,
    MASS_ACTION,
    REGULAR_MIXING,
    TRANSITION_STATE,
    balance,
    rate_equations,
    runner,
)
from cells.registry import laws as law_registry
from tests.assembly_lineage_v2_fixtures import CONVENTIONS, definition, species, step

jax.config.update("jax_enable_x64", True)

ENVELOPE = {"min_count": 100.0, "provenance": "a test envelope"}
INTEGRATOR = {"id": "rosenbrock_rodas4_dense@1", "rtol": 1e-9, "atol_count": 1e-6,
              "step_limit": 100000}  # fmt: skip


def as_representation(raw, envelope=ENVELOPE, integrator=INTEGRATOR):
    out = copy.deepcopy(raw)
    x = out["execution"]
    for key in ("molecule_capacity", "chunk_events"):
        x.pop(key, None)
    x["representation"] = {"id": "cells.rate_equations@1", "envelope": dict(envelope),
                           "integrator": dict(integrator)}  # fmt: skip
    out["experiment"]["trace"] = False
    return out


def linear_world():
    """A ⇌ B ⇌ C in a finite pool, first order, and one inert membrane molecule (no rate reads
    it): the rate equations are linear, so their solution is a matrix exponential."""
    return {
        "units": {"time": "s", "temperature_K": 298.15, "standard_concentration_mM": 1000.0},
        "conventions": dict(CONVENTIONS, condensed_measure="multinomial", last_molecule="kept"),
        "species": [species("A", {"x": 1}, solution=0.0), species("B", {"x": 1}, solution=-0.5),
                    species("C", {"x": 1}, solution=-1.0), species("M", None, bilayer=0.0)],
        "phases": {"pool": {"volume_L": 1e-18, "species": [
            {"id": s, "kind": "finite"} for s in ("A", "B", "C")]},
                   "membrane": {"species": ["M"]}},
        "steps": [step("ab", {"A": 1}, {"B": 1}, 2.0, phase="pool"),
                  step("bc", {"B": 1}, {"C": 1}, 1.0, phase="pool")],
        "free_energy": [{"law": IDEAL_MIXING}],
        "founder": {"A@pool": 10000, "B@pool": 2000, "C@pool": 1000, "M@membrane": 1},
    }  # fmt: skip


def membrane_world():
    """A closed world: T and U exchange between a finite pool and a membrane, and dimerise in the
    membrane (order 2 there), catalysed (the transition-state factor) with regular mixing."""
    return {
        "units": {"time": "s", "temperature_K": 298.15, "standard_concentration_mM": 1000.0},
        "conventions": dict(CONVENTIONS, condensed_measure="multinomial_less_one",
                            last_molecule="kept"),
        "species": [species("T", {"t": 1}, solution=0.0, bilayer=-2.0),
                    species("U", {"u": 1}, solution=0.0, bilayer=-1.5),
                    species("D", {"t": 1, "u": 1}, bilayer=-4.0)],
        "phases": {"pool": {"volume_L": 1e-20, "species": [
            {"id": "T", "kind": "finite"}, {"id": "U", "kind": "finite"}]},
                   "membrane": {"species": ["T", "U", "D"]}},
        "steps": [step("join_T", {"T@pool": 1}, {"T@membrane": 1}, 3.0, locus="membrane"),
                  step("join_U", {"U@pool": 1}, {"U@membrane": 1}, 2.0, locus="membrane"),
                  step("dimer", {"T": 1, "U": 1}, {"D": 1}, 5.0, phase="membrane")],
        "free_energy": [{"law": IDEAL_MIXING},
                        {"law": REGULAR_MIXING, "chi_kT": [{"pair": ["T", "U"], "chi": 1.0}]}],
        "rate_factor": {"law": TRANSITION_STATE, "catalysing_phase": "membrane",
                        "entries": [{"catalyst": "D", "step": "join_T", "ddG_kT": 1.2},
                                    {"catalyst": "T", "step": "dimer", "ddG_kT": 0.7}]},
        "founder": {"T@pool": 3000, "U@pool": 2500, "T@membrane": 2000, "U@membrane": 1500,
                    "D@membrane": 500},
    }  # fmt: skip


def test_a_representation_parses_beside_its_exact_twin_and_round_trips():
    exact = parse_spec(definition(linear_world(), trace=False, molecules=20000))
    spec = parse_spec(as_representation(definition(linear_world(), observations=(0.5,))))
    assert rate_equations.is_representation(spec) and not rate_equations.is_representation(exact)
    assert spec.model.world == exact.model.world  # one world, two representations
    assert spec.fingerprint != exact.fingerprint
    again = parse_spec(spec.to_dict() if hasattr(spec, "to_dict") else _to_dict(spec))
    assert again.fingerprint == spec.fingerprint


def _to_dict(spec):
    from cells.models.assembly_lineages_v2.spec import to_dict

    return to_dict(spec)


def _edit(path, value):
    def edit(raw):
        node = raw
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
        return raw

    return edit


@pytest.mark.parametrize(
    "edit, words",
    [
        (_edit(("execution", "molecule_capacity"), 64), "does not apply"),
        (_edit(("execution", "representation", "integrator", "id"), "rk4"), "integrator's id"),
        (_edit(("execution", "representation", "integrator", "rtol"), 1e-2), "rtol"),
        (_edit(("execution", "representation", "envelope", "min_count"), 0.5), "min_count"),
        (_edit(("experiment", "trace"), True), "event-level readout"),
        (_edit(("model", "world", "founder", "C@pool"), 50), "below the envelope"),
        (_edit(("execution", "mode"), "population"), "mode population exactly when"),
    ],
)
def test_refusals(edit, words):
    raw = edit(as_representation(definition(linear_world())))
    with pytest.raises(ConfigError, match=words):
        parse_spec(raw)


def test_the_limit_check_passes_on_the_generic_probes_and_catches_two_plants():
    verdict = rate_equations.verdict()
    assert verdict["worlds"] == len(rate_equations.generic_probes()) + 2 == 6
    assert verdict["identity"] <= rate_equations.IDENTITY_ATOL
    assert verdict["potential"] <= 1e-6 and verdict["dissipation_margin"] >= 0.0
    spec = parse_spec(as_representation(definition(membrane_world())))
    problem = rate_equations.Problem(spec)
    rng = np.random.default_rng(3)
    rate_equations.limit_check(problem, rng, states=2)

    # P-D7: one species' μ° shifted by 0.5 k_BT in F_cont only.
    ideal = problem.terms[0]
    shifted = dataclasses.replace(
        ideal, limit=lambda n, t, lay, xp: ideal.limit(n, t, lay, xp) + 0.5 * n[0]
    )
    problem.terms = (shifted, *problem.terms[1:])
    with pytest.raises(ConfigError, match="not the products' law"):
        rate_equations.limit_check(problem, rng, states=2)

    # P-D2: a power off by one in mass action's limit (n^(a+1) for every coefficient a).
    problem = rate_equations.Problem(spec)
    law = problem.reactions[0]

    def off_by_one(view, *args):
        bumped = view._replace(coeff=jnp.where(view.coeff > 0, view.coeff + 1, 0))
        return law.limit(bumped, *args)

    problem.reactions = tuple(dataclasses.replace(r, limit=off_by_one) for r in problem.reactions)
    with pytest.raises(ConfigError, match="not the products' law"):
        rate_equations.limit_check(problem, rng, states=2)


def test_each_limit_tends_to_its_exact_form_as_one_over_the_counts():
    """Item 4, run before every run on the generic probes (both measures; the osmotic probe's
    geometric and lumen laws too), and its planted failure: a limit off by a constant factor."""
    verdict = rate_equations.verdict()
    assert verdict["worlds"] == len(rate_equations.generic_probes()) + 2
    assert len(verdict["parity_orders"]) + verdict["parity_identical"] == verdict["worlds"]
    assert min(verdict["parity_orders"]) >= 0.9
    rng = np.random.default_rng(5)
    raw = balance.probe_world(rng, "multinomial_less_one", "kept", regular=True, catalysis=True)
    honest = law_registry.active().lookup(MASS_ACTION)
    planted = dataclasses.replace(
        honest, law_id="tests.limit_off_by_a_constant@1",
        limit=lambda view, *rest: honest.limit(view, *rest) + 0.1,
    )  # fmt: skip
    for step_ in raw["model"]["world"]["steps"]:
        if step_["law"] == MASS_ACTION:
            step_["law"] = planted.law_id
    with law_registry.scope(law_registry.BUILTIN.extended(planted)):
        with pytest.raises(ConfigError, match="does not tend to its exact form"):
            rate_equations.parity(raw, rng)


def test_a_linear_network_follows_its_matrix_exponential(tmp_path):
    times = (0.25, 0.5, 1.0, 2.0)
    spec = parse_spec(as_representation(definition(linear_world(), horizon=2.0,
                                                   observations=times)))  # fmt: skip
    run = runner.run(spec)
    assert run.status == "complete"
    k1, k1r = 2.0, 2.0 * np.exp(-0.5)  # k⁻ = k_f exp(Σ ν μ°)
    k2, k2r = 1.0, 1.0 * np.exp(-0.5)
    rates = np.array([[-k1, k1r, 0.0], [k1, -k1r - k2, k2r], [0.0, k2, -k2r]])
    start = np.array([10000.0, 2000.0, 1000.0])
    observed = run.rows["row_kind"] == "observed"
    for t, counts in zip(run.rows["row_time_s"][observed], run.rows["counts"][observed],
                         strict=True):  # fmt: skip
        expected = expm(rates * t) @ start
        assert np.max(np.abs(counts[:3] - expected) / expected) < 1e-7
    run.check_books()
    # The records (FORMAT_RATE_EQUATIONS.md), through the family's own write_run.
    import json

    from cells.models.assembly_lineages_v2 import records

    records.write_run(tmp_path / "bundle", run)
    record = json.loads((tmp_path / "bundle" / "run.json").read_text())
    assert record["format"] == "cells.rate_equations_run@1" and record["status"] == "complete"
    assert record["engine_models"]["representation"] == "cells.rate_equations@1"
    assert record["ledger"]["closes"] and record["moieties"]["closes"]
    assert all(law["limit_formulas"] for law in record["laws"])
    assert "qualification" not in record["representation"]  # FR-47's status: its paths only
    saved = np.load(tmp_path / "bundle" / "rows.npz")
    assert np.array_equal(saved["counts"], run.rows["counts"])


def test_a_closed_membrane_relaxes_to_f_cont_s_minimum_with_its_books_closed():
    raw = as_representation(definition(membrane_world(), horizon=40.0, observations=(1.0, 10.0)))
    spec = parse_spec(raw)
    run = runner.run(spec)
    assert run.status == "complete"
    run.check_books()
    assert run.dissipation["holds"]
    problem = rate_equations.Problem(spec)
    final = np.zeros(problem.P)
    final[: len(spec.model.world.places)] = run.rows["counts"][-1]
    _, d_f = problem.flux(jnp.asarray(final))
    assert np.max(np.abs(np.asarray(d_f))) < 1e-6  # every step at its equilibrium
    heat = run.rows["heat_kT"]
    assert np.all(np.diff(heat) >= -1e-9)  # dQ/dt >= 0 between rows
    again = runner.run(spec)  # deterministic: the same bits
    for name, values in run.rows.items():
        assert np.array_equal(values, again.rows[name]), name


# ------------------------------------------------------------------ FR-47's E2 and refusals (D323)


def e2_shell(delta=0.5):
    """A single-lineage entry-only shell (shell_interior's lumen_shell, equal pool and lumen
    volumes) with both tracer places empty at the founder, so both are E2's; a lumen potential
    Δ = 0.5, so the first-order law is J = κ_in n_A − κ_out n_C with κ_in = P A / V = 200 per s
    and κ_out = κ_in e^Δ."""
    from tests.unit.test_assembly_lineages_v2_shell_interior import lumen_shell

    w = lumen_shell(solution=0.7, lumen=0.7 + delta, n_out=0, n_in=0)
    spec = parse_spec(as_representation(definition(w), envelope={"min_count": 1.0,
                                                                 "provenance": "a test"}))
    problem = rate_equations.Problem(spec)
    names = [p.name for p in spec.model.world.places]
    return problem, names.index("S@pool"), names.index("S@lumen"), 200.0, 200.0 * np.exp(delta)


def _factored(problem):
    """The plant: the same problem with E2's steps in the old factored form."""
    planted = copy.copy(problem)
    planted.e2_step = np.zeros_like(problem.e2_step)
    return planted


@pytest.mark.parametrize("empty", ["reactant", "product"])
def test_e2_s_flux_and_its_one_sided_derivative_are_the_first_order_law_s(empty):
    """CRITERIA's E2 rows: at an empty reactant (n_A = 0, n_C = 1000) and an empty product (the
    reverse), J and its derivatives equal the first-order law's, J = κ_in n_A − κ_out n_C with
    dJ/dn_A = κ_in and dJ/dn_C = −κ_out, to rounding. The plant, the old factored form, gives
    J = −0 and derivatives −0 at an empty reactant, and at an empty product treats the place as
    one molecule, with dJ/dn_C = 0. No compile beyond a forward derivative: about 2 s."""
    problem, a, c, k_in, k_out = e2_shell()
    assert problem.e2[a] and problem.e2[c] and problem.e2_step[0]
    n = np.zeros(problem.P)
    n[a], n[c] = (0.0, 1000.0) if empty == "reactant" else (1000.0, 0.0)
    law = (k_in * n[a] - k_out * n[c], k_in, -k_out)

    def at(p):
        def flux(m):
            return p.flux(m)[0]

        j, d = jax.jit(lambda m: (flux(m), jax.jacfwd(flux)(m)))(jnp.asarray(n))
        return float(j[0]), float(d[0, a]), float(d[0, c])

    got = at(problem)
    assert np.allclose(got, law, rtol=1e-13, atol=0.0), (got, law)
    planted = at(_factored(problem))
    if empty == "reactant":
        assert planted == (0.0, 0.0, 0.0) and all(np.signbit(planted))  # −0, −0, −0
    else:
        assert planted[2] == 0.0 and abs(planted[0] - (law[0] - k_out)) <= 1e-9 * law[0]


def test_one_rodas4_step_from_a_zero_keeps_its_order_and_the_factored_form_loses_it():
    """CRITERIA's step-halving row: from an empty pool and a full lumen (the full wash's state),
    the error at a fixed time reached in 2, 4, 8 and 16 Rodas4 steps, against the two-place
    matrix exponential, falls by about 2⁴ per halving (order 4; one step's local error would fall
    by 2⁵). The plant, the factored form with its zero derivative, never leaves the zero: its
    error does not fall. Host loop over the integrator's own step: about 3 s."""
    from cells.numerics import rosenbrock_dense as rd

    problem, a, c, k_in, k_out = e2_shell()
    span = 0.004  # about two relaxation times (κ_in + κ_out = 530 per s)
    exact = expm(np.array([[-k_in, k_out], [k_in, -k_out]]) * span) @ np.array([0.0, 3000.0])
    y0 = np.zeros(2 * problem.P + 2)
    y0[c] = 3000.0
    alive = jnp.ones(1, dtype=bool)

    def errors(p):
        shape = rate_equations.Shape(p)

        def f(z):
            return shape.rhs(z, alive)

        one = jax.jit(lambda y, h: rd.step(f, jax.jacfwd(f), y, h).y)  # h traced: one compile
        out = []
        for steps in (2, 4, 8, 16):
            y = jnp.asarray(y0)
            for _ in range(steps):
                y = one(y, span / steps)
            y = np.asarray(y)
            out.append(max(abs(y[a] - exact[0]), abs(y[c] - exact[1])))
        return out

    honest = errors(problem)
    ratios = [x / y for x, y in zip(honest, honest[1:], strict=False)]
    assert all(2.0**3.5 <= r <= 2.0**4.5 for r in ratios), ratios
    planted = errors(_factored(problem))
    assert min(planted) >= 0.5 * exact[0] and max(planted) / min(planted) < 1.01, planted


def _shell(edit):
    """FR-21's shell fixture (the geometry tests'), edited, in this representation."""
    from tests.unit.test_assembly_lineages_v2_geometry import shell_world

    w = edit(shell_world())
    return as_representation(definition(w), envelope={"min_count": 1.0, "provenance": "a test"})


def _unbound(w):
    """The shell without its site and ligand: a gate of fixed forms G and H, and a subunit B."""
    w.pop("sites")
    w["steps"] = [s for s in w["steps"] if s["id"] != "bind"]
    w["species"] = [s for s in w["species"] if s["id"] not in ("X", "XR")]
    w["phases"]["pool"]["species"] = [s for s in w["phases"]["pool"]["species"] if s["id"] != "X"]
    w["phases"]["membrane"]["species"].remove("XR")
    w["founder"] = {k: v for k, v in w["founder"].items() if not k.startswith("X")}
    return w


def _driven(w):
    w = _unbound(w)
    w["steps"].append(step("drive", {"B": 1, "H": 1}, {"B": 1, "G": 1}, 1.0, phase="membrane"))
    return w


def _gate_on_a_bilayer(raw):
    from tests.unit.test_assembly_lineages_v2_lumen import K_L, osmotic_world

    w = osmotic_world(L_pool=30, L_mem=8, S_pool=6, S_lumen=2, I_lumen=2, floor=4 * K_L)
    for name in ("G", "H"):
        w["species"].append(species(name, {"g": 1}, solution=0.0, bilayer=-2.0))
        w["phases"]["membrane"]["species"].append(name)
        w["phases"]["pool"]["species"].append({"id": name, "kind": "finite"})
        w["geometry"]["area_per_leaflet"][name] = {"quanta": K_L, "provenance": "a test"}
        w["founder"] |= {f"{name}@membrane": 1, f"{name}@pool": 0}
    w["rate_factor"] = {"law": "cells.gate_factor@1", "forms": ["G", "H"],
                        "entries": [{"form": "G", "step": "entry", "ddG_kT": 1.0}]}  # fmt: skip
    return as_representation(definition(w), envelope={"min_count": 1.0, "provenance": "a test"})


def _inert_on_a_bilayer(raw):
    """An osmotic bilayer vesicle with a membrane species J that no step moves, at 1 copy against
    min_count 2: its quanta enter the footprint W(n), which the bilayer's extents read."""
    from tests.unit.test_assembly_lineages_v2_lumen import K_L, osmotic_world

    w = osmotic_world(L_pool=30, L_mem=8, S_pool=6, S_lumen=2, I_lumen=2, floor=4 * K_L)
    w["species"].append(species("J", {"j": 1}, solution=0.0, bilayer=-2.0))
    w["phases"]["membrane"]["species"].append("J")
    w["phases"]["pool"]["species"].append({"id": "J", "kind": "finite"})
    w["geometry"]["area_per_leaflet"]["J"] = {"quanta": K_L, "provenance": "a test"}
    w["founder"] |= {"J@membrane": 1, "J@pool": 0}
    return as_representation(definition(w), envelope={"min_count": 2.0, "provenance": "a test"})


def inert_wall_definition(wall, *, wall_reads=None):
    """One prescribed shell (a single lineage: the envelope's rule is the same for one slot of a
    population) with equal pool and lumen volumes, passive exchange at 1 per s each way
    (P A / V = 1), one tracer in the lumen and none outside, and a wall species W at `wall`
    copies, in (d) at min_count 2 (rtol 1e-9, atol_count 1e-9). W is inert: no step, factor or law
    reads it. With `wall_reads` "gate", W and a second form V gate the entry; with "step", W
    switches to V by a wall step: either way a rate reads W's count."""
    from cells.models.assembly_lineages_v2 import GATE_FACTOR, PRESCRIBED_SHELL, SHELL_PERMEATION

    u = "unsourced; test"
    names = [("S", {"s": 1}, {"solution": 0.0}), ("W", {"w": 1}, {"bilayer": -1.0})]
    slot = {"S@lumen": 1, "W@membrane": wall}
    if wall_reads is not None:
        names.append(("V", {"w": 1}, {"bilayer": -1.0}))
        slot["V@membrane"] = 5
    w = {
        "units": {"time": "s", "temperature_K": 296.15, "standard_concentration_mM": 1000.0},
        "conventions": dict(CONVENTIONS, condensed_measure="multinomial", lumen_volume="declared",
                            last_molecule="kept"),
        "species": [species(n, m, **mu) for n, m, mu in names],
        "phases": {"pool": {"volume_L": 1e-18, "species": [{"id": "S", "kind": "finite"}]},
                   "membrane": {"species": [n for n, _, mu in names if "bilayer" in mu]},
                   "lumen": {"volume_L": 1e-18, "species": ["S"]}},
        "steps": [{"id": "entry", "locus": "membrane", "reactants": {"S@pool": 1},
                   "products": {"S@lumen": 1}, "law": SHELL_PERMEATION,
                   "permeability_m_per_s": {"value": 1e-6, "provenance": u}}],
        "free_energy": [{"law": IDEAL_MIXING}],
        "founder": {"S@pool": 0, **slot},
        "geometry": {"law": PRESCRIBED_SHELL, "area_m2": {"value": 1e-15, "provenance": u}},
    }  # fmt: skip
    if wall_reads == "gate":
        w["rate_factor"] = {"law": GATE_FACTOR, "forms": ["W", "V"],
                            "entries": [{"form": "W", "step": "entry", "ddG_kT": 0.5}]}
    elif wall_reads == "step":
        w["steps"].append(step("switch", {"W": 1}, {"V": 1}, 1.0, phase="membrane"))
    d = as_representation(definition(w, horizon=1.0, observations=(1.0,)),
                          envelope={"min_count": 2.0, "provenance": "a test"},
                          integrator=dict(INTEGRATOR, atol_count=1e-9))  # fmt: skip
    return d


def _wall_read(reads):
    return inert_wall_definition(1, wall_reads=reads)


@pytest.mark.parametrize(
    "raw, words",
    [
        (_shell(lambda w: w), "site binding in a cells.prescribed_shell@1 world"),
        (_shell(_driven), "a gate driven by bound states, or by anything but its own forms"),
        (_gate_on_a_bilayer(None), "cells.gate_factor@1 is refused in version 1 outside"),
        (_wall_read("gate"), "the founder's W@membrane holds 1, below the envelope"),
        (_wall_read("step"), "the founder's W@membrane holds 1, below the envelope"),
        (_inert_on_a_bilayer(None), "J@membrane holds 1, below the envelope"),
    ],
)  # fmt: skip
def test_fr47_s_refusals_by_name(raw, words):
    """D323: site binding in a shell's world (R9), a gate driven by anything but its own forms
    (R7) and the gate factor outside a shell's world, each by name at the parse. The shell without
    its binding and with a fixed or an autonomously switching gate is admitted. The envelope's
    guard stays wherever a rate or the geometry reads a wall count (FR-47's inert-wall fix): a
    gate's form, a wall step's species and a bilayer's membrane species (its footprint W(n)), each
    at 1 copy against min_count 2. Parse only."""
    with pytest.raises(ConfigError, match=words):
        parse_spec(raw)


def test_a_shell_with_a_fixed_or_an_autonomous_gate_is_admitted():
    parse_spec(_shell(_unbound))

    def flipping(w):
        w = _unbound(w)
        w["steps"].append(step("flip", {"G": 1}, {"H": 1}, 1.0, phase="membrane"))
        return w

    parse_spec(_shell(flipping))


@pytest.mark.parametrize("wall", [1, 2])
def test_an_inert_wall_species_is_outside_the_envelope(wall):
    """FR-47's inert-wall fix: a prescribed shell reads no wall count (its extent is constant) and
    its permeation moves no membrane molecule, so a wall species that no step, factor or law reads
    is outside the envelope, at 1 copy as at 2, below and at min_count 2. The one tracer in the
    lumen relaxes to the two-state mean, (1 + e^-2)/2 inside at 1 s, within 1e-7, and the tracer
    is conserved to the moieties' tolerance with the books closed. The guard stays where a rate
    reads the wall (test_fr47_s_refusals_by_name). Two small programs (the founders differ, so do
    the worlds) and two short runs: about 20 s."""
    spec = parse_spec(inert_wall_definition(wall))
    run = runner.run(spec)
    assert run.status == "complete" and run.moieties["closes"] and run.ledger["closes"]
    names = [p.name for p in spec.model.world.places]
    seen = run.rows["row_kind"] == "observed"
    inside = run.rows["counts"][seen][0, names.index("S@lumen")]
    outside = run.rows["counts"][seen][0, names.index("S@pool")]
    assert abs(inside - (1.0 + np.exp(-2.0)) / 2.0) <= 1e-7
    assert abs(inside + outside - 1.0) <= 1e-12
