"""FR-48 and FR-46 (D323): the inside of a prescribed shell, a lumen standard potential and binding
from the inner face, in exact events. Split from test_assembly_lineages_v2_geometry.py, whose cold
seconds reached its tier's cap with these tests (88.78 s of 90 s, measured on the timed lane); their
refusal rows stay there, in SHELL_REFUSALS, beside FR-21's.

- FR-48: the stationary law and the pair identity under a lumen potential, its offset plant, the
  undeclared default, the records' offset and (d)'s refusal;
- FR-46: the face rule's rows (the reviewer's counterexample first), the inner face's closed-form
  rates and identity, and the run-level row.
"""

import math

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages_v2 import (
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
    offset in the records, and the same arrays as an explicit D = 0. Refused in (d) by name."""
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
    # refused in the deterministic representation by name, until FR-47's qualification
    d = definition(lumen_shell(lumen=0.7 + delta), molecules=64)
    d["execution"] = {"backend": "cpu", "precision": "float64", "mode": "single_lineage",
                      "stream": {"seed": 1, "environment": 0, "lineage": 0, "branch": 0},
                      "representation": {"id": "cells.rate_equations@1",
                                         "envelope": {"min_count": 10.0, "provenance": "test"},
                                         "integrator": {"id": "rosenbrock_rodas4_dense@1",
                                                        "rtol": 1e-10, "atol_count": 1e-6,
                                                        "step_limit": 100000}}}  # fmt: skip
    with pytest.raises(ConfigError, match="a lumen standard potential"):
        parse_spec(d)


def face_world(kind="separate", *, x_pool=5, x_lumen=0, P=2e-7, k_bind=3.0, k_wall=1.0):
    """FR-46: FR-21's shell with the ligand X in the pool and the lumen, an outer pair (R, XR) bound
    from the pool and an inner pair (R, XRi) bound from the lumen, and wall steps per `kind`:
    "separate" (none), "zero" (XR -> XRi), "one" (XR -> Y1 -> XRi, Y1 a ligand-bearing wall state
    with no pair of its own: the reviewer's counterexample), "two" (XR -> Y1 -> Y2 -> XRi), and
    "same face" (XR -> Y1 -> XR2, XR2 a second outer complex, bound from the pool too)."""
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
    binding("bind_inner", "X@lumen", "XRi")
    chain = {"separate": [], "zero": ["XR", "XRi"], "one": ["XR", "Y1", "XRi"],
             "two": ["XR", "Y1", "Y2", "XRi"], "same face": ["XR", "Y1", "XR2"]}[kind]  # fmt: skip
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
