"""FR-48 and FR-46 (D323): the inside of a prescribed shell, a lumen standard potential and binding
from the inner face, in exact events. Split from test_assembly_lineages_v2_geometry.py, whose cold
seconds reached its tier's cap with these tests (88.78 s of 90 s, measured on the timed lane); their
refusal rows stay there, in SHELL_REFUSALS, beside FR-21's.

- FR-48: the stationary law and the pair identity under a lumen potential, its offset plant, the
  undeclared default, the records' offset and (d)'s exit with e^D (FR-47 admits it there);
- FR-46: the face rule's rows (the reviewer's counterexample first), the inner face's closed-form
  rates and identity, and the run-level row.
"""

import math

import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages_v2 import (
    GATE_FACTOR,
    IDEAL_MIXING,
    MASS_ACTION,
    PRESCRIBED_SHELL,
    SHELL_PERMEATION,
    balance,
    kernel,
    model,
    records,
    runner,
)
from cells.models.assembly_lineages_v2 import spec as spec_rules
from tests.assembly_lineage_v2_fixtures import definition
from tests.unit.test_assembly_lineages_v2_geometry import C0_MM, shell_world, spec_of, species


def lumen_shell(*, solution=0.7, lumen=None, n_out=12, n_in=0, P=2e-7):
    """FR-48: an entry-only shell at equal pool and lumen volumes, a tracer S with a nonzero
    solution potential and, when declared, an absolute lumen potential; a wall of one subunit B."""
    u = "unsourced; test"
    mu = {"solution": solution} if lumen is None else {"solution": solution, "lumen": lumen}
    return {
        "units": {"time": "s", "temperature_K": 296.15, "standard_concentration_mM": C0_MM},
        "conventions": {"free_energy_form": "discrete", "condensed_measure": "multinomial",
                        "membrane_kinetics": "count_on_m", "lumen_volume": "declared",
                        "empty_catalyst_phase": "uncatalysed", "last_molecule": "kept"},
        "species": [species("S", {"s": 1}, **mu), species("B", {"b": 1}, bilayer=-3.0)],
        "phases": {"pool": {"volume_L": 1e-21, "species": [{"id": "S", "kind": "finite"}]},
                   "membrane": {"species": ["B"]}, "lumen": {"volume_L": 1e-21, "species": ["S"]}},
        "steps": [{"id": "entry", "locus": "membrane", "reactants": {"S@pool": 1},
                   "products": {"S@lumen": 1}, "law": SHELL_PERMEATION,
                   "permeability_m_per_s": {"value": P, "provenance": u}}],
        "free_energy": [{"law": IDEAL_MIXING}],
        "founder": {"S@pool": n_out, "S@lumen": n_in, "B@membrane": 3},
        "geometry": {"law": PRESCRIBED_SHELL, "area_m2": {"value": 1e-15, "provenance": u}},
    }  # fmt: skip


def _stationary_law(spec, total):
    """The stationary law of n_in = 0..total along the entry's chain, from the kernel's own rates
    (detailed balance: pi(n + 1) a-(n + 1) = pi(n) a+(n)), on the host."""
    structure, layout = model.structure(spec), model.layout(spec)
    at = {p.name: i for i, p in enumerate(spec.model.world.places)}
    rates = []
    for n_in in range(total + 1):
        c = np.zeros(structure.places, dtype=np.int64)
        c[[at["S@pool"], at["S@lumen"], at["B@membrane"]]] = (total - n_in, n_in, 3)
        totals = kernel.totals_of(c, layout, np)
        f, t = kernel.states(c, totals, layout, structure, np)
        a = kernel.rates(c, totals, f, t, layout, structure, np)
        rates.append((float(a[0]), float(a[structure.steps])))
    log_pi = np.concatenate(([0.0], np.cumsum(
        [math.log(rates[n][0]) - math.log(rates[n + 1][1]) for n in range(total)])))  # fmt: skip
    pi = np.exp(log_pi - log_pi.max())
    return pi / pi.sum()


def _same_leaves(a, b):
    """Bitwise equality of two layouts, leaf by leaf (they nest tuples of arrays)."""
    if isinstance(a, (tuple, list)):
        return len(a) == len(b) and all(_same_leaves(x, y) for x, y in zip(a, b, strict=True))
    x, y = np.asarray(a), np.asarray(b)
    return x.shape == y.shape and x.dtype == y.dtype and np.array_equal(x, y)


def _binomial(total, p):
    return np.asarray([math.comb(total, k) * p**k * (1.0 - p) ** (total - k)
                       for k in range(total + 1)])  # fmt: skip


def test_a_lumen_potential_sets_the_equilibrium_ratio_and_keeps_detailed_balance(monkeypatch):
    """FR-48 (D323): a species' absolute lumen potential mu0_L = mu0_sol + D, with a nonzero
    solution potential (0.7). What is claimed, from the kernel's own rates on the host: the
    stationary inside count at equal volumes is Binomial(N, 1/(1 + e^D)), one third at D = ln 2
    and one half at D = 0; and detailed balance, the pair identity at random states from both
    founders, with a short run from each closing its ledger (D per crossing through F). The
    relaxation time follows the law's convention (all of D on the exit) and is not claimed.
    Planted: the lumen value read as an offset from the solution one moves the law. The undeclared
    default is today's world: the solution potential in the lumen, no key in the world's dict, no
    offset in the records, and the same arrays as an explicit D = 0. In (d), which FR-47 admits
    it in (D323), the exit carries e^D: κ_out/κ_in = e^D at equal volumes."""
    total, delta = 12, math.log(2.0)
    declared = spec_of(lumen_shell(lumen=0.7 + delta))
    assert np.max(np.abs(_stationary_law(declared, total) - _binomial(total, 1.0 / 3.0))) < 1e-12
    equal = spec_of(lumen_shell(lumen=0.7))
    assert np.max(np.abs(_stationary_law(equal, total) - _binomial(total, 0.5))) < 1e-12
    # the undeclared default: the solution potential in the lumen, bitwise the explicit D = 0
    default = spec_of(lumen_shell())
    assert np.max(np.abs(_stationary_law(default, total) - _binomial(total, 0.5))) < 1e-12
    w_default, w_equal = default.model.world, equal.model.world
    assert "lumen" not in spec_rules.world_to_dict(w_default)["species"][0]["standard_mu_RT"]
    assert spec_rules.world_to_dict(w_equal)["species"][0]["standard_mu_RT"]["lumen"] == 0.7
    assert _same_leaves(model.layout(default), model.layout(equal))
    rows = {r["name"]: r for r in records.places_table(declared.model.world)}
    assert rows["S@lumen"]["standard_mu_RT"] == 0.7 + delta
    assert rows["S@lumen"]["lumen_offset_RT"] == pytest.approx(delta, rel=0, abs=1e-15)
    assert "lumen_offset_RT" not in rows["S@pool"]
    assert all("lumen_offset_RT" not in r for r in records.places_table(w_default))
    # detailed balance from both founders, and a short run from each closes its ledger
    for n_out, n_in in ((total, 0), (0, total)):
        s = spec_of(lumen_shell(lumen=0.7 + delta, n_out=n_out, n_in=n_in))
        found = balance.deviations(s, np.random.default_rng(5), states=200)
        assert found.size > 100 and np.max(np.abs(found)) <= balance.ATOL
        run = runner.run(parse_spec(definition(lumen_shell(lumen=0.7 + delta, n_out=n_out,
                                                           n_in=n_in), molecules=64,
                                               horizon=1.0, event_limit=400))).check()  # fmt: skip
        assert run.closure["holds"]
    # planted: the lumen value read as an offset, mu0_L = mu0_sol + mu0_lumen (0.7 + 0.7 + ln 2)
    from cells.models.assembly_lineages_v2 import world as world_rules

    def as_offset(self, phase):
        base = self.mu_bilayer if world_rules.KIND_OF[phase] == "bilayer" else self.mu_solution
        if phase == world_rules.LUMEN and self.mu_lumen is not None:
            return self.mu_solution + self.mu_lumen
        return base

    monkeypatch.setattr(world_rules.Species, "mu", as_offset)
    planted = _stationary_law(spec_of(lumen_shell(lumen=0.7 + delta)), total)
    assert np.max(np.abs(planted - _binomial(total, 1.0 / 3.0))) > 0.05
    assert np.max(np.abs(planted - _binomial(total, 1.0 / (1.0 + math.exp(0.7 + delta))))) < 1e-12
    monkeypatch.undo()
    # (d), FR-47 (D323): admitted, and its exit carries e^D (P1's mechanism, at the host)
    from cells.models.assembly_lineages_v2 import rate_equations

    d = definition(lumen_shell(lumen=0.7 + delta, n_out=40, n_in=40), molecules=64, trace=False)
    d["execution"] = {"backend": "cpu", "precision": "float64", "mode": "single_lineage",
                      "stream": {"seed": 1, "environment": 0, "lineage": 0, "branch": 0},
                      "representation": {"id": "cells.assembly_representation.rate_equations@1",
                                         "envelope": {"min_count": 1.0, "provenance": "test"},
                                         "integrator": {"id": "cells.solver.rosenbrock_rodas4_dense@1",
                                                        "rtol": 1e-10, "atol_count": 1e-6,
                                                        "step_limit": 100000}}}  # fmt: skip
    problem = rate_equations.Problem(parse_spec(d))
    n = np.zeros(problem.P)
    n[:3] = (40.0, 3.0, 40.0)  # S@pool, B@membrane, S@lumen: equal counts at equal volumes
    forward = float(problem.log_direction(jnp.asarray(n), True)[0])
    reverse = float(problem.log_reverse(jnp.asarray(n))[0])
    assert reverse - forward == pytest.approx(delta, abs=1e-13)


def face_world(kind="separate", *, x_pool=5, x_lumen=0, P=2e-7, k_bind=3.0, k_wall=1.0):
    """FR-46: FR-21's shell with the ligand X in the pool and the lumen, an outer pair (R, XR) bound
    from the pool and an inner pair (R, XRi) bound from the lumen, and wall steps per `kind`:
    "separate" (none), "zero" (XR -> XRi), "one" (XR -> Y1 -> XRi, Y1 a ligand-bearing wall state
    with no pair of its own: the reviewer's counterexample), "two" (XR -> Y1 -> Y2 -> XRi), and
    "same face" (XR -> Y1 -> XR2, XR2 a second outer complex, bound from the pool too),
    "co-ligand" (a carrier through a binding step: a co-ligand Z binds the outer complex XR from the
    lumen, XR + Z@lumen -> XRZ on an inner pair (XR, XRZ), and a wall step XRZ -> XRi + Zm hands X
    to the inner complex XRi, which releases it into the lumen), and "pool on inner" (the inner
    pair (R, XRi) bound from the pool, against its own face)."""
    w = shell_world(XR=0, P=P)
    w["phases"]["lumen"]["species"] = ["S", "X"]
    w["founder"].update({"X@pool": x_pool, "X@lumen": x_lumen})
    next(st for st in w["steps"] if st["id"] == "bind")["forward_rate_per_s"] = k_bind

    def wall_state(name):
        w["species"].append(species(name, {"x": 1, "r": 1}, bilayer=-6.0))
        w["phases"]["membrane"]["species"].append(name)
        w["founder"][f"{name}@membrane"] = 0

    def binding(name, ligand, complex_):
        w["steps"].append({"id": name, "locus": "membrane",
                           "reactants": {ligand: 1, "R@membrane": 1},
                           "products": {f"{complex_}@membrane": 1}, "law": MASS_ACTION,
                           "forward_rate_per_s": k_bind})  # fmt: skip

    wall_state("XRi")
    w["sites"].append({"site": "R", "complex": "XRi", "face": "inner"})
    binding("bind_inner", "X@pool" if kind == "pool on inner" else "X@lumen", "XRi")
    if kind == "co-ligand":
        w["species"] += [species("Z", {"z": 1}, solution=0.0),
                         species("XRZ", {"x": 1, "r": 1, "z": 1}, bilayer=-7.0),
                         species("Zm", {"z": 1}, bilayer=-1.0)]  # fmt: skip
        w["phases"]["lumen"]["species"].append("Z")
        w["phases"]["membrane"]["species"] += ["XRZ", "Zm"]
        w["founder"].update({"Z@lumen": 4, "XRZ@membrane": 0, "Zm@membrane": 0})
        w["sites"].append({"site": "XR", "complex": "XRZ", "face": "inner"})
        w["steps"] += [{"id": "bind_co", "locus": "membrane",
                        "reactants": {"Z@lumen": 1, "XR@membrane": 1},
                        "products": {"XRZ@membrane": 1}, "law": MASS_ACTION,
                        "forward_rate_per_s": k_bind},
                       {"id": "hand_over", "phase": "membrane", "reactants": {"XRZ": 1},
                        "products": {"XRi": 1, "Zm": 1}, "law": MASS_ACTION,
                        "forward_rate_per_s": k_wall}]  # fmt: skip
    chain = {"separate": [], "zero": ["XR", "XRi"], "one": ["XR", "Y1", "XRi"],
             "two": ["XR", "Y1", "Y2", "XRi"], "same face": ["XR", "Y1", "XR2"],
             "co-ligand": [], "pool on inner": []}[kind]  # fmt: skip
    for name in chain:
        if name not in ("XR", "XRi"):
            wall_state(name)
    if kind == "same face":
        w["sites"].append({"site": "R", "complex": "XR2"})
        binding("bind_outer_2", "X@pool", "XR2")
    for i, (a, b) in enumerate(zip(chain, chain[1:], strict=False)):
        w["steps"].append({"id": f"wall_{i}", "phase": "membrane", "reactants": {a: 1},
                           "products": {b: 1}, "law": MASS_ACTION, "forward_rate_per_s": k_wall})
    return w


FACE_RULE = {
    "the reviewer's counterexample, a carrier through one wall state with no pair": (
        "one", "a carrier across the wall"),
    "a carrier with no intermediate": ("zero", "a carrier across the wall"),
    "a carrier through two wall states with no pair": ("two", "a carrier across the wall"),
    "a carrier through a binding step, a co-ligand bound from the lumen onto the outer complex": (
        "co-ligand", "a carrier across the wall"),
    "a pool step on an inner pair, against its own face": (
        "pool on inner", "crosses phases at the membrane"),
    "a same-face isomerization": ("same face", None),
    "an outer and an inner pair kept apart": ("separate", None),
}  # fmt: skip


@pytest.mark.parametrize("case", sorted(FACE_RULE))
def test_the_face_rule_refuses_every_carrier_and_admits_one_face(case):
    """FR-46 (D323): one face per complex. A ligand moiety that can pass through the wall's states
    from an outer complex to an inner one is a carrier across the wall, refused by name, whether the
    conversion is direct or goes through wall states with no binding pair of their own. A
    same-face isomerization and an outer and an inner pair kept apart are admitted."""
    kind, message = FACE_RULE[case]
    w = face_world(kind)
    if message is None:
        spec_of(w)
    else:
        with pytest.raises(ConfigError, match=message):
            spec_of(w)


def test_inner_face_binding_has_its_closed_form_rates_and_keeps_the_identity():
    """FR-46 (D323): X@lumen + R@membrane -> XRi@membrane for a declared inner pair, in a shell,
    with FR-48's lumen potential on the ligand (solution 0.0, lumen 0.4). a+ = k_f theta+ n_R,
    theta+ the lumen's activity x / X_lumen, and a- = k_f e^(mu_XRi - mu_R - mu_X@lumen) n_XRi:
    dissociation returns X to the lumen. The pair identity at random states, and a short run's
    ledger. Host arithmetic, apart from the run."""
    w = face_world("separate", x_lumen=3)
    next(sp for sp in w["species"] if sp["id"] == "X")["standard_mu_RT"] = {"solution": 0.0,
                                                                            "lumen": 0.4}
    s = spec_of(w)
    world_, structure, layout = s.model.world, model.structure(s), model.layout(s)
    R, r = structure.steps, [st.id for st in world_.steps].index("bind_inner")
    at = {p.name: i for i, p in enumerate(world_.places)}
    X_lumen = (6.02214076e23 * world_.volume("lumen")
               * world_.units.standard_concentration_mM * 1e-3)  # fmt: skip
    k_rev = 3.0 * math.exp(-6.0 - (-2.0) - 0.4)
    for x, n_r, n_xri in ((3, 4, 0), (1, 5, 1), (0, 4, 2), (6, 0, 6)):
        c = np.asarray(model.founder(s)).copy()
        c[[at["X@lumen"], at["R@membrane"], at["XRi@membrane"]]] = (x, n_r, n_xri)
        log = balance.host_log_rates(c, layout, structure)
        assert math.exp(log[r]) == pytest.approx(3.0 * (x / X_lumen) * n_r, rel=1e-13, abs=0)
        assert math.exp(log[R + r]) == pytest.approx(k_rev * n_xri, rel=1e-13, abs=0)
    found = balance.deviations(s, np.random.default_rng(5), states=200)
    assert found.size > 200 and np.max(np.abs(found)) <= balance.ATOL
    run = runner.run(parse_spec(definition(w, molecules=64, horizon=0.5, event_limit=500))).check()
    assert run.closure["holds"]


def test_a_shell_closed_to_the_ligand_keeps_its_lumen_empty():
    """FR-46 (D323), at the run level: an admitted shell with an outer pair, a same-face
    isomerization through a wall state with no pair, and an inner pair; no permeation of X, and X
    in the pool only. Over a run whose binding events dominate (S's permeation slowed), the lumen's
    X stays at zero at every row and no inner channel fires."""
    w = face_world("same face", x_pool=5, x_lumen=0, P=2e-12, k_bind=500.0, k_wall=20.0)
    d = definition(w, molecules=64, horizon=20.0, event_limit=3000, row_every=1, trace=True)
    s = parse_spec(d)
    run = runner.run(s).check()
    names = [p.name for p in s.model.world.places]
    counts = np.asarray(run.rows["place_count"])[:, names.index("X@lumen")]
    assert counts.size > 100 and np.all(counts == 0)
    ids = [st.id for st in s.model.world.steps]
    fired = {ids[abs(int(k)) - 1] for k in np.asarray(run.trace["event_channel"])}
    assert "bind_inner" not in fired and {"bind", "wall_0"} <= fired
    assert run.closure["holds"]



def test_the_occupied_inner_site_takes_part_in_a_gate_rule():
    """FR-46's request: the occupied wall state can take part in a declared gate rule. A gate whose
    forms are the site R and its inner complex XRi gates the shell's entry, so the entry follows the
    inner face's occupancy: g = (n_R e^1 + n_XRi e^-1)/(n_R + n_XRi), on both directions, the
    gate's own forms only. Host rates against that closed form, and the pair identity."""
    w = face_world("separate", x_lumen=3)
    w["rate_factor"] = {"law": GATE_FACTOR, "forms": ["R", "XRi"],
                        "entries": [{"form": "R", "step": "entry", "ddG_kT": 1.0},
                                    {"form": "XRi", "step": "entry", "ddG_kT": -1.0}]}  # fmt: skip
    s = spec_of(w)
    structure, layout = model.structure(s), model.layout(s)
    at = {p.name: i for i, p in enumerate(s.model.world.places)}
    r = [st.id for st in s.model.world.steps].index("entry")
    base = None
    for n_r, n_xri in ((4, 0), (2, 2), (1, 3)):
        c = np.asarray(model.founder(s)).copy()
        c[[at["R@membrane"], at["XRi@membrane"]]] = (n_r, n_xri)
        totals = kernel.totals_of(c, layout, np)
        f, t = kernel.states(c, totals, layout, structure, np)
        a = kernel.rates(c, totals, f, t, layout, structure, np)
        g = (n_r * math.e + n_xri / math.e) / (n_r + n_xri)
        if base is None:
            base = (float(a[r]) / g, float(a[structure.steps + r]) / g)
        assert float(a[r]) / g == pytest.approx(base[0], rel=1e-13, abs=0)
        assert float(a[structure.steps + r]) / g == pytest.approx(base[1], rel=1e-13, abs=0)
    found = balance.deviations(s, np.random.default_rng(5), states=200)
    assert found.size > 200 and np.max(np.abs(found)) <= balance.ATOL


def sealed_shell(*, y_binding=True):
    """A reviewer's carrier across a sealed shell (D323, relayed by the user): one X outside, one Y
    inside, one free wall site R, and no permeation of X. The four steps, each conserving X, Y and
    the scaffold r, with positive rates: X_out + R -> A (the outer pair (R, A)); Y_in + A -> C (the
    inner pair (A, C): Y binds A, which already holds X); C -> D (a wall step); and D -> B + X_in,
    the release of the inner pair (B, D), declared as its binding X_in + B -> D. So X can end up
    inside. Without the Y-binding step the shell is sealed: the control."""
    w = shell_world()  # its units, conventions and the shell geometry, with their provenance
    w["species"] = [species("X", {"x": 1}, solution=0.0), species("Y", {"y": 1}, solution=0.0),
                    species("R", {"r": 1}, bilayer=-2.0),
                    species("A", {"x": 1, "r": 1}, bilayer=-4.0),
                    species("C", {"x": 1, "r": 1, "y": 1}, bilayer=-5.0),
                    species("D", {"x": 1, "r": 1, "y": 1}, bilayer=-5.5),
                    species("B", {"r": 1, "y": 1}, bilayer=-3.0),
                    species("W", {"w": 1}, bilayer=-3.0)]  # fmt: skip
    w["phases"] = {"pool": {"volume_L": 1e-21, "species": [{"id": "X", "kind": "finite"}]},
                   "membrane": {"species": ["R", "A", "C", "D", "B", "W"]},
                   "lumen": {"volume_L": 1e-22, "species": ["X", "Y"]}}  # fmt: skip

    def bind(name, ligand, site, complex_):
        return {"id": name, "locus": "membrane", "reactants": {ligand: 1, f"{site}@membrane": 1},
                "products": {f"{complex_}@membrane": 1}, "law": MASS_ACTION,
                "forward_rate_per_s": 50.0}  # fmt: skip

    w["steps"] = [bind("x_out_binds_R", "X@pool", "R", "A")]
    if y_binding:
        w["steps"].append(bind("y_in_binds_A", "Y@lumen", "A", "C"))
    w["steps"] += [{"id": "c_to_d", "phase": "membrane", "reactants": {"C": 1},
                    "products": {"D": 1}, "law": MASS_ACTION, "forward_rate_per_s": 20.0},
                   bind("x_in_binds_B", "X@lumen", "B", "D")]  # fmt: skip
    w["sites"] = [{"site": "R", "complex": "A"}, {"site": "A", "complex": "C", "face": "inner"},
                  {"site": "B", "complex": "D", "face": "inner"}]  # fmt: skip
    w["founder"] = {"X@pool": 1, "X@lumen": 0, "Y@lumen": 1, "R@membrane": 1, "A@membrane": 0,
                    "C@membrane": 0, "D@membrane": 0, "B@membrane": 0, "W@membrane": 3}
    w.pop("rate_factor")
    return w


def test_a_reviewers_sealed_shell_carrier_is_refused_and_its_sealed_control_admitted():
    """D323, the user's relay of a reviewer's case: the transfer hides where Y binds A, which
    already holds X. The face rule joins each step's membrane reactant and product per ligand
    moiety, binding and release steps included, so A, C and D share moiety x, seeded outer at A and
    inner at D: a carrier, refused by name. Without the Y-binding step, nothing joins A to C, and
    the same shell is admitted."""
    with pytest.raises(ConfigError, match=r"the ligand moiety x can pass through the wall's states "
                                          r"\['A', 'C', 'D'\]"):
        spec_of(sealed_shell())
    spec_of(sealed_shell(y_binding=False))
