"""R-ops (validation/division/partition_reference.py): the partition map's identities on random
states and its analytic limits (docs/CELL_DIVISION_S5_DESIGN.md Appendix A.6-A.7, §7.1, §7.3).

Every state here is synthetic and random: no J1 input, no DFS74 value.
"""

import math
from dataclasses import replace

import numpy as np
import pytest

from validation.division import partition_reference as rops

SPECIES = ("Na", "K", "Cl")
Z = (1, 1, -1)
TOL = rops.TOLERANCE_EPS * rops.EPS  # 64 eps
CHARGE_PER_FMOL = 1e-15 * rops.F  # C per fmol of charge equivalent
# The reference's own self-checks (a pass at 64 eps x magnitude) use the tight scale: the
# magnitudes without A.8's charge term, which is for comparing with the engine.
OWN = dict(charge_term=False)


def charges_from_potentials(free, held, edges, phi):
    """Q = K phi over the free nodes, assembled here independently of R-ops' solve."""
    q = {node: 0.0 for node in free}
    potential = dict(held, **phi)
    for inside, outside, c in edges:
        v = potential[inside] - potential[outside]
        if inside in q:
            q[inside] += c * v
        if outside in q:
            q[outside] -= c * v
    return q


def random_state(rng, *, held_potential=None, n_patches=None, amount_scale=None):
    """A parent P with 2-3 patches (to a held bath and a free cleft), a neighbour M with a contact,
    populations and random history; the division's f, a_k and transference numbers."""
    log_uniform = lambda lo, hi: float(10.0 ** rng.uniform(math.log10(lo), math.log10(hi)))  # noqa: E731
    temperature = float(rng.uniform(285.0, 305.0))
    bath = float(rng.uniform(-0.01, 0.01)) if held_potential is None else held_potential
    n_patches = int(rng.integers(2, 4)) if n_patches is None else n_patches
    nodes = ["bath", "cleft"] + [str(rng.choice(["bath", "cleft"])) for _ in range(n_patches - 2)]
    patches = {}
    for i, node in enumerate(nodes):
        area, cap = log_uniform(1e-10, 1e-8), log_uniform(1e-12, 1e-10)
        patches[f"p{i}"] = rops.Patch(
            "P",
            node,
            area,
            cap,
            area * float(rng.uniform(-0.3, 0.3)),
            cap * float(rng.uniform(-0.3, 0.3)),
        )
    patches["m0"] = rops.Patch("M", "bath", log_uniform(1e-10, 1e-8), log_uniform(1e-12, 1e-10))
    if rng.uniform() < 0.5:
        patches["m1"] = rops.Patch(
            "M", "cleft", log_uniform(1e-10, 1e-8), log_uniform(1e-12, 1e-10)
        )
    free, held = ["P", "M", "cleft"], {"bath": bath}
    edges = [(p.cell, p.node, p.capacitance_F) for p in patches.values()]
    phi = {
        "P": float(rng.uniform(-0.1, 0.05)),
        "M": float(rng.uniform(-0.1, 0.05)),
        "cleft": float(rng.uniform(-0.02, 0.02)),
    }
    q = charges_from_potentials(free, held, edges, phi)
    lo, hi = (1e1, 1e7) if amount_scale is None else amount_scale

    def cell(charge):
        reference = np.array([log_uniform(lo, hi) for _ in SPECIES])
        increment = reference * rng.uniform(-0.1, 0.1, size=3)
        n = reference + increment
        background = charge / CHARGE_PER_FMOL - math.fsum(np.multiply(Z, n))
        return rops.Cell(
            tuple(reference),
            tuple(increment),
            log_uniform(0.1, 1e3),
            background,
            charge,
            charge * float(rng.uniform(0.5, 1.5)),
        )

    cells = {"P": cell(q["P"]), "M": cell(q["M"])}
    clefts = {"cleft": rops.Cleft(tuple(rng.uniform(1.0, 100.0, size=3)), 1e-3, q["cleft"])}
    on_p = [k for k in patches if patches[k].cell == "P"]
    populations = {
        "j0": rops.Population(on_p[0], 1e3, 12.5, (0.3, 0.7)),
        "j1": rops.Population(on_p[-1], 4e2, -3.0, (0.9,)),
        "jm": rops.Population("m0", 5e2, 0.0, (0.5,)),
    }
    contacts = {"e": rops.Contact(("P", "M"), log_uniform(1e-12, 1e-10), (0.8,))}
    history = {
        "membrane_transferred_fmol": {k: rng.normal(size=3) for k in patches},
        "membrane_heat_pJ": {k: float(rng.uniform(0.0, 5.0)) for k in patches},
        "junction_transferred_fmol": {"e": rng.normal(size=3)},
        "junction_heat_pJ": {"e": float(rng.uniform(0.0, 1.0))},
        "channel_transferred_fmol": {j: rng.normal(size=3) for j in populations},
        "channel_heat_pJ": {j: rng.uniform(0.0, 1.0, size=3) for j in populations},
    }
    snapshot = rops.Snapshot(
        SPECIES, Z, temperature, held, cells, clefts, patches, populations, contacts, {}, history
    )
    t = rng.dirichlet(np.ones(3))
    division = rops.Division(
        "P",
        ("D1", "D2"),
        float(rng.uniform(0.05, 0.95)),
        {k: (f"{k}a", f"{k}b", float(rng.uniform(0.05, 0.95))) for k in on_p},
        {"j0": ("j0a", "j0b"), "j1": ("j1a", "j1b")},
        {"e": ("ea", "eb", float(rng.uniform(0.0, 1.0)))},
        {"Na": float(t[0]), "K": float(t[1]), "Cl": float(1.0 - t[0] - t[1])},
        "bridge",
        2e-5,
    )
    return snapshot, division, phi


def symmetric(division):
    return rops.Division(
        division.parent,
        division.daughters,
        0.5,
        {k: (a, b, 0.5) for k, (a, b, _) in division.patches.items()},
        division.populations,
        {e: (a, b, 0.5) for e, (a, b, _) in division.contacts.items()},
        {},
        division.bridge,
        division.bridge_a0_m,
    )


# ---------------------------------------------------------------- the solve


def test_the_nodal_solve_inverts_the_capacitor_law_on_random_networks():
    rng = np.random.default_rng(1)
    for _ in range(50):
        snapshot, _, phi = random_state(rng)
        free, edges, charges = rops.network(snapshot)
        solved, magnitude = rops.nodal_solve(free, snapshot.held, edges, charges)
        for node, value in phi.items():
            assert abs(solved[node] - value) <= TOL * magnitude[node]


def test_the_nodal_solve_matches_a_two_capacitor_chain_by_hand():
    # cell -C1- bath, cell -C2- cleft: phi_cell = (Q_i + Q_c) / C1, phi_c = phi_cell + Q_c / C2.
    c1, c2, qi, qc = 3e-11, 2e-12, 1.5e-12, -4e-14
    phi, _ = rops.nodal_solve(
        ["cell", "cleft"],
        {"bath": 0.0},
        [("cell", "bath", c1), ("cell", "cleft", c2)],
        {"cell": qi, "cleft": qc},
    )
    assert phi["cell"] == pytest.approx((qi + qc) / c1, rel=1e-15)
    assert phi["cleft"] == pytest.approx((qi + qc) / c1 + qc / c2, rel=1e-14)


def test_a_component_without_a_held_node_is_refused():
    with pytest.raises(rops.PartitionRefused, match="floating"):
        rops.nodal_solve(["a", "b"], {"bath": 0.0}, [("a", "b", 1e-12)], {"a": 1e-15, "b": -1e-15})


# ---------------------------------------------------------------- identities on random states


def test_every_identity_holds_on_200_random_states_to_64_eps():
    rng = np.random.default_rng(20261113)
    worst = []
    for i in range(200):
        snapshot, division, _ = random_state(rng, held_potential=0.0 if i % 2 else None)
        result = rops.apply(snapshot, division, **OWN)
        name, ratio = result.worst()
        worst.append(ratio)
        assert ratio <= rops.TOLERANCE_EPS, (i, name, ratio)
        assert result.values["unmixing_pJ"] >= 0.0
    assert max(worst) > 0.0  # The identities are evaluated, not vacuous.


def test_the_map_writes_the_fractions_of_the_appendix():
    rng = np.random.default_rng(7)
    snapshot, division, _ = random_state(rng)
    r = rops.apply(snapshot, division)
    v, s, d = r.values, r.snapshot, division
    p = snapshot.cells["P"]
    f = d.f
    dq = math.fsum((a - f) * v["patch_q_before_C"][k] for k, (_, _, a) in d.patches.items())
    assert v["mismatch_C"] == dq
    for i, name in enumerate(SPECIES):
        assert v["delta_fmol"][i] == 1e15 * d.carriers[name] * dq / (Z[i] * rops.F)
    n_p = np.add(p.reference_fmol, p.increment_fmol)
    assert np.array_equal(v["amounts_D1_fmol"], f * n_p + v["delta_fmol"])
    assert np.array_equal(v["amounts_D2_fmol"], n_p - v["amounts_D1_fmol"])
    assert np.array_equal(
        s.cells["D1"].increment_fmol, f * np.asarray(p.increment_fmol) + v["delta_fmol"]
    )
    assert np.array_equal(s.cells["D1"].reference_fmol, f * np.asarray(p.reference_fmol))
    assert s.cells["D1"].volume_pL == f * p.volume_pL
    assert s.cells["D2"].volume_pL == p.volume_pL - f * p.volume_pL
    assert s.cells["D1"].background_fmol == f * p.background_fmol
    assert s.cells["D1"].charge_C == f * p.charge_C + dq
    assert s.cells["D1"].charge_reference_C == f * p.charge_reference_C
    assert np.array_equal(v["moved_fmol"]["P"], -np.asarray(p.increment_fmol))
    for k, (k1, k2, a) in d.patches.items():
        parent = snapshot.patches[k]
        assert s.patches[k1].area_reference_m2 == a * parent.area_reference_m2
        assert s.patches[k1].capacitance_increment_F == a * parent.capacitance_increment_F
        assert (
            s.patches[k2].area_increment_m2
            == parent.area_increment_m2 - a * parent.area_increment_m2
        )
        assert (s.patches[k1].cell, s.patches[k2].cell) == ("D1", "D2")
        assert s.patches[k1].node == s.patches[k2].node == parent.node
        assert k not in s.patches
    assert "P" not in s.cells and set(s.bridges) == {"bridge"}
    assert s.bridges["bridge"] == rops.Bridge(("D1", "D2"), 2e-5)


def test_populations_and_contacts_split_their_extensive_parts_and_copy_their_gates():
    rng = np.random.default_rng(11)
    snapshot, division, _ = random_state(rng)
    r = rops.apply(snapshot, division)
    s = r.snapshot
    for j, (j1, j2) in division.populations.items():
        parent = snapshot.populations[j]
        k1, k2, a = division.patches[parent.patch]
        assert (s.populations[j1].patch, s.populations[j2].patch) == (k1, k2)
        assert s.populations[j1].abundance_reference == a * parent.abundance_reference
        assert s.populations[j1].gates == s.populations[j2].gates == parent.gates
        moved = r.values["units_moved"]
        assert moved[j] == -parent.abundance_increment
        assert moved[j1] + moved[j2] + moved[j] == pytest.approx(0.0, abs=4 * rops.EPS * 20)
        assert j not in s.populations
    assert s.populations["jm"] == snapshot.populations["jm"]  # The neighbour's is untouched.
    (e1, e2, a_e) = division.contacts["e"]
    c = snapshot.contacts["e"]
    assert s.contacts[e1] == rops.Contact(("D1", "M"), a_e * c.area_m2, c.gates)
    assert s.contacts[e2] == rops.Contact(("D2", "M"), c.area_m2 - a_e * c.area_m2, c.gates)
    assert "e" not in s.contacts


def test_the_record_holds_the_retired_history_and_adds_back_exactly():
    rng = np.random.default_rng(3)
    snapshot, division, _ = random_state(rng)
    r = rops.apply(snapshot, division)
    retired = {*division.patches, *division.populations, *division.contacts}
    for kind, entries in snapshot.history.items():
        record = r.values["record"][kind]
        after = r.snapshot.history[kind]
        assert set(record) == retired & set(entries)
        for slot, value in entries.items():
            if slot in retired:
                assert np.all(np.asarray(after[slot]) == 0.0)
                assert np.array_equal(np.asarray(after[slot]) + record[slot], value)
            else:
                assert after[slot] is value


# ---------------------------------------------------------------- analytic limits (§7.3)


def test_a_symmetric_division_is_bitwise_and_books_exact_zeros():
    rng = np.random.default_rng(5)
    for _ in range(20):
        snapshot, division, _ = random_state(rng)
        r = rops.apply(snapshot, symmetric(division), **OWN)
        v, s = r.values, r.snapshot
        assert np.all(v["delta_fmol"] == 0.0) and v["mismatch_C"] == 0.0
        assert s.cells["D1"] == s.cells["D2"]
        assert np.array_equal(v["amounts_D1_fmol"], v["amounts_D2_fmol"])
        assert np.all(v["moved_fmol"]["D1"] + v["moved_fmol"]["D2"] + v["moved_fmol"]["P"] == 0.0)
        for k, (k1, k2, _) in division.patches.items():
            assert (s.patches[k1].area_m2, s.patches[k1].capacitance_F) == (
                s.patches[k2].area_m2,
                s.patches[k2].capacitance_F,
            )
            assert v["area_moved_m2"][k1] + v["area_moved_m2"][k2] + v["area_moved_m2"][k] == 0.0
        assert v["free_energy_change_pJ"] == 0.0
        assert v["unmixing_pJ"] == 0.0
        # The capacitor terms are zero to rounding (the potentials are solved again).
        assert abs(v["image_charge_C"]["bath"]) <= TOL * r.magnitudes["image_charge_C"]["bath"]
        assert (
            abs(v["capacitor_energy_change_J"]) <= TOL * r.magnitudes["capacitor_energy_change_J"]
        )
        name, ratio = r.worst()
        assert ratio <= rops.TOLERANCE_EPS, (name, ratio)


def test_the_unmixing_term_is_nonnegative_and_follows_its_leading_order():
    rng = np.random.default_rng(9)
    accepted = 0
    for _ in range(200):
        # Small contents so that delta / n is visible (about 1e-4 to 1e-2).
        snapshot, division, _ = random_state(rng, amount_scale=(0.05, 2.0), held_potential=0.0)
        try:
            r = rops.apply(snapshot, division, **OWN)
        except rops.PartitionRefused as refused:  # delta beyond a daughter's share (A.6 step 7)
            assert "amount <= 0" in str(refused)
            continue
        accepted += 1
        v = r.values
        gap, leading = v["unmixing_pJ"], v["unmixing_leading_pJ"]
        assert gap >= 0.0 and leading >= 0.0
        n_p = np.add(snapshot.cells["P"].reference_fmol, snapshot.cells["P"].increment_fmol)
        f = division.f
        d = np.max(np.abs(v["delta_fmol"]) / (n_p * min(f, 1.0 - f)))
        assert abs(gap / leading - 1.0) <= d  # Next order: |d| (p/(1-p) - (1-p)/p) / 3.
        # The booked work is dG at a bath held at 0 V, to the capacitor term's rounding.
        assert v["work_pJ"] == pytest.approx(
            v["free_energy_change_pJ"], abs=TOL * r.magnitudes["work_pJ"]
        )
    assert accepted >= 100


def test_the_unmixing_term_is_exactly_zero_without_mismatch_at_one_half():
    rng = np.random.default_rng(13)
    snapshot, division, _ = random_state(rng)
    r = rops.apply(snapshot, symmetric(division))
    assert r.values["unmixing_pJ"] == 0.0 == r.values["unmixing_leading_pJ"]


def test_without_mismatch_the_free_energy_change_vanishes_to_rounding():
    rng = np.random.default_rng(17)
    for _ in range(20):
        snapshot, division, _ = random_state(rng)
        f = division.f
        plain = rops.Division(
            "P",
            ("D1", "D2"),
            f,
            {k: (a, b, f) for k, (a, b, _) in division.patches.items()},
            division.populations,
            division.contacts,
            {},
            "bridge",
            2e-5,
        )
        r = rops.apply(snapshot, plain, **OWN)
        assert np.all(r.values["delta_fmol"] == 0.0)
        assert abs(r.values["free_energy_change_pJ"]) <= TOL * r.magnitudes["free_energy_change_pJ"]
        assert r.values["unmixing_pJ"] <= 1e-20 * abs(r.values["free_energy_parts_pJ"][2])


def one_patch_chain(*, with_cleft):
    """A cell with one patch per outside node: the bath, and (optionally) a cleft that only this
    cell's patch faces."""
    patches = {"old": rops.Patch("P", "bath", 4e-9, 4e-11)}
    edges = [("P", "bath", 4e-11)]
    phi = {"P": -0.05}
    clefts = {}
    if with_cleft:
        patches["furrow"] = rops.Patch("P", "cleft", 1e-9, 1e-11)
        edges.append(("P", "cleft", 1e-11))
        phi["cleft"] = -0.003
    free = ["P", *(["cleft"] if with_cleft else [])]
    q = charges_from_potentials(free, {"bath": 0.0}, edges, phi)
    n = np.array([10.0, 140.0, 30.0])
    cell = rops.Cell(
        tuple(n),
        (0.0, 0.0, 0.0),
        1.0,
        q["P"] / CHARGE_PER_FMOL - math.fsum(np.multiply(Z, n)),
        q["P"],
    )
    if with_cleft:
        clefts["cleft"] = rops.Cleft((140.0, 5.0, 145.0), 1e-4, q["cleft"])
    return rops.Snapshot(SPECIES, Z, 300.0, {"bath": 0.0}, {"P": cell}, clefts, patches)


@pytest.mark.parametrize("with_cleft", [False, True])
def test_the_isopotential_split_of_a_one_patch_per_node_chain(with_cleft):
    snapshot = one_patch_chain(with_cleft=with_cleft)
    shares = {"old": 0.3, "furrow": 0.65}
    division = rops.Division(
        "P",
        ("D1", "D2"),
        0.45,
        {k: (f"{k}1", f"{k}2", shares[k]) for k in snapshot.patches},
        carriers={"K": 0.6, "Cl": 0.4},
    )
    r = rops.apply(snapshot, division, **OWN)
    before, after = r.values["potentials_before_V"], r.values["potentials_after_V"]
    mag0, mag = r.magnitudes["potentials_before_V"], r.magnitudes["potentials_after_V"]
    for d in ("D1", "D2"):
        assert abs(after[d] - before["P"]) <= TOL * (mag[d] + mag0["P"])
    if with_cleft:
        assert abs(after["cleft"] - before["cleft"]) <= TOL * (mag["cleft"] + mag0["cleft"])
    q_before, q_after = r.values["patch_q_before_C"], r.values["patch_q_after_C"]
    for k, a in ((k, shares[k]) for k in snapshot.patches):
        assert q_after[f"{k}1"] == pytest.approx(a * q_before[k], rel=TOL * 8)
        assert q_after[f"{k}2"] == pytest.approx((1.0 - a) * q_before[k], rel=TOL * 8)
    # The daughter's charge follows its patches (q_D = a q_P for the one-patch cell).
    q_d1 = math.fsum(shares[k] * q_before[k] for k in snapshot.patches)
    assert r.snapshot.cells["D1"].charge_C == pytest.approx(q_d1, rel=TOL * 8)
    assert abs(r.values["image_charge_C"]["bath"]) <= TOL * r.magnitudes["image_charge_C"]["bath"]
    assert np.any(r.values["delta_fmol"] != 0.0)  # A real mismatch was moved.


# ---------------------------------------------------------------- refusals


def test_a_daughter_amount_at_or_below_zero_refuses_and_leaves_the_input():
    # Tiny contents and a large mismatch: delta exceeds f n for K.
    snapshot = one_patch_chain(with_cleft=True)
    cell = snapshot.cells["P"]
    tiny = rops.Cell((1e-6, 1e-6, 2e-6), (0.0, 0.0, 0.0), 1.0, cell.background_fmol, cell.charge_C)
    snapshot = rops.Snapshot(
        SPECIES, Z, 300.0, snapshot.held, {"P": tiny}, snapshot.clefts, snapshot.patches
    )
    frozen = repr(snapshot)
    division = rops.Division(
        "P",
        ("D1", "D2"),
        0.5,
        {"old": ("o1", "o2", 0.05), "furrow": ("f1", "f2", 0.95)},
        carriers={"K": 1.0},
    )
    with pytest.raises(rops.PartitionRefused, match="amount <= 0"):
        rops.apply(snapshot, division)
    assert repr(snapshot) == frozen


@pytest.mark.parametrize(
    "change, message",
    [
        (dict(f=0.0), "outside"),
        (dict(f=1.0), "outside"),
        (dict(patches={"old": ("o1", "o2", 1.0), "furrow": ("f1", "f2", 0.5)}), "outside"),
        (dict(patches={"old": ("o1", "o2", 0.5)}), "cover the parent's live patches"),
        (dict(patches={"old": ("o1", "o2", 0.4), "furrow": ("f1", "f2", 0.5)}), "required"),
        (dict(carriers={"K": 0.5, "Cl": 0.4}), "sum to 1"),
        (dict(carriers={"K": 1.2, "Cl": -0.2}), "negative"),
        (dict(carriers={"water": 1.0}), "charged"),
        (dict(daughters=("D1", "D1")), "distinct"),
        (dict(daughters=("P", "D2")), "already live"),
        (dict(bridge="b", bridge_a0_m=0.0), "positive"),
    ],
)
def test_inadmissible_divisions_are_refused(change, message):
    snapshot = one_patch_chain(with_cleft=True)
    base = dict(
        parent="P",
        daughters=("D1", "D2"),
        f=0.5,
        patches={"old": ("o1", "o2", 0.5), "furrow": ("f1", "f2", 0.5)},
    )
    with pytest.raises(rops.PartitionRefused, match=message):
        rops.apply(snapshot, rops.Division(**(base | change)))


def test_a_parent_with_an_open_bridge_is_refused_and_a_closed_one_retires():
    snapshot = one_patch_chain(with_cleft=False)
    cells = dict(snapshot.cells)
    sister = cells["P"]
    cells["S"] = sister
    patches = dict(snapshot.patches, s_old=rops.Patch("S", "bath", 4e-9, 4e-11))
    division = rops.Division("P", ("D1", "D2"), 0.5, {"old": ("o1", "o2", 0.5)})
    for aperture, refused in ((1e-9, True), (0.0, False)):
        s = rops.Snapshot(
            SPECIES,
            Z,
            300.0,
            snapshot.held,
            cells,
            {},
            patches,
            bridges={"b": rops.Bridge(("P", "S"), aperture)},
            history={"junction_heat_pJ": {"b": 0.25}},
        )
        if refused:
            with pytest.raises(rops.PartitionRefused, match="open"):
                rops.apply(s, division)
        else:
            r = rops.apply(s, division)
            assert "b" not in r.snapshot.bridges
            assert r.values["record"]["junction_heat_pJ"] == {"b": 0.25}
            assert r.values["junction_gates_before"]["b"] == (1.0,)
            assert r.values["junction_gates_after"]["b"] == (0.0,)


def test_junction_gates_read_zero_when_not_live_and_the_bridge_opens_with_its_gate():
    # The lead's addition to A.6 item 5 (13 November): a contact that is not live (pending, or
    # with a retired endpoint) reads gate 0; the bridge becomes live with its declared gate (1,
    # fixed open); the daughter contacts take g_e.
    rng = np.random.default_rng(19)
    snapshot, division, _ = random_state(rng)
    r = rops.apply(snapshot, division)
    e1, e2, _ = division.contacts["e"]
    g = snapshot.contacts["e"].gates
    assert g == (0.8,)
    assert r.values["junction_gates_before"] == {
        "e": g,
        e1: (0.0,),
        e2: (0.0,),
        "bridge": (0.0,),
    }
    assert r.values["junction_gates_after"] == {"e": (0.0,), e1: g, e2: g, "bridge": (1.0,)}
    assert r.snapshot.contacts[e1].gates == r.snapshot.contacts[e2].gates == g
    assert r.snapshot.bridges["bridge"].gates == (1.0,)
    half_open = rops.Division(**(division.__dict__ | dict(bridge_gates=(0.5,))))
    assert rops.apply(snapshot, half_open).snapshot.bridges["bridge"].gates == (0.5,)


# ---------------------------------------------------------------- free energy and the bridge


def test_the_free_energy_is_the_appendix_formula():
    n, v, t = (12.0, 140.0, 30.0), 2.0, 300.0
    expected = 1e-3 * rops.R * t * sum(x * (math.log(x / v) - 1.0) for x in n)
    assert rops.free_energy_pJ(n, v, t) == pytest.approx(expected, rel=1e-15)
    # The gap form equals G(D1) + G(D2) - G(P) when the parts sum to the whole.
    n1, n2, v1, v2 = (5.0, 60.0, 14.0), (7.0, 80.0, 16.0), 0.9, 1.1
    whole = tuple(a + b for a, b in zip(n1, n2, strict=True))
    direct = rops.free_energy_pJ(n1, v1, t) + rops.free_energy_pJ(n2, v2, t)
    direct -= rops.free_energy_pJ(whole, v1 + v2, t)
    assert rops.unmixing_pJ(n1, v1, n2, v2, t) == pytest.approx(direct, rel=1e-9)


@pytest.mark.parametrize("x", [1e-9, -3e-7, 2e-4, -9e-4, 1.5e-3, -0.2, 0.7])
def test_the_relative_entropy_term_is_accurate_near_one(x):
    m = 3.0
    exact = m * math.fsum((-1) ** k * x**k / (k * (k - 1)) for k in range(2, 400))
    assert rops.relative_entropy_term(m * (1.0 + x), m) == pytest.approx(exact, rel=1e-9)


# ---------------------------------------------------------------- A.8 as amended (14 November)
# A cell's node charge has the magnitude |Q| + |Q-bar| + 1e-15 F sum_s |z_s Delta_s|, carried
# through the capacitor solve into every potential and on into every dependent output.


def charge_term(cell):
    """The amended term, from a Cell's own fields (an input cell, or a daughter R-ops wrote)."""
    return abs(cell.charge_reference_C) + CHARGE_PER_FMOL * math.fsum(
        abs(z * d) for z, d in zip(Z, cell.increment_fmol, strict=True)
    )


def free_matrix(snapshot):
    """(free nodes, K_ff) of a snapshot, cells then clefts, assembled here from its patches."""
    free = [*snapshot.cells, *snapshot.clefts]
    index = {node: i for i, node in enumerate(free)}
    K = np.zeros((len(free), len(free)))
    for p in snapshot.patches.values():
        a, b, c = index[p.cell], index.get(p.node), p.capacitance_F
        K[a, a] += c
        if b is not None:
            K[b, b] += c
            K[a, b] -= c
            K[b, a] -= c
    return free, K


def same(a, b):
    """Exact equality of two Result value trees (dicts, sequences, arrays and floats)."""
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, (tuple, list)) and a and isinstance(a[0], (dict, tuple, list)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b, strict=True))
    return np.array_equal(np.asarray(a, dtype=float), np.asarray(b, dtype=float))


def flat(result):
    """Every magnitude of a Result, its outputs' and its identities', as one array in key order."""
    out = []

    def walk(x):
        if isinstance(x, dict):
            for key in sorted(x):
                walk(x[key])
        else:
            out.extend(np.ravel(np.asarray(x, dtype=float)))

    walk(result.magnitudes)
    walk({k: m for k, (_, m) in result.identities.items()})
    return np.array(out)


def test_the_charge_term_comes_from_the_inputs_and_the_maps_own_outputs():
    rng = np.random.default_rng(23)
    for _ in range(50):
        snapshot, division, _ = random_state(rng)
        amended = rops.apply(snapshot, division)
        plain = rops.apply(snapshot, division, charge_term=False)
        for name, cell in snapshot.cells.items():  # The input cells.
            m = amended.magnitudes["charges_before_C"][name]
            assert m == abs(cell.charge_C) + charge_term(cell)
            assert plain.magnitudes["charges_before_C"][name] == abs(cell.charge_C)
        for name, cleft in snapshot.clefts.items():  # Clefts are unchanged.
            assert amended.magnitudes["charges_before_C"][name] == abs(cleft.charge_C)
        f, t_parent = division.f, charge_term(snapshot.cells["P"])
        # The mismatch's magnitude grows through the potentials (their charges' terms).
        dq = amended.magnitudes["mismatch_C"] - plain.magnitudes["mismatch_C"]
        assert dq > 0.0
        # Q_D1 = f Q_P + dq and Q_D2 = Q_P - Q_D1, each with its own anchor and increments.
        for d, share in (("D1", f), ("D2", 1.0 + f)):
            t_daughter = charge_term(amended.snapshot.cells[d])  # R-ops' own output.
            added = amended.magnitudes[f"charge_{d}_C"] - plain.magnitudes[f"charge_{d}_C"]
            assert added == pytest.approx(share * t_parent + dq + t_daughter, rel=1e-12)
            assert amended.magnitudes["charges_after_C"][d] == amended.magnitudes[f"charge_{d}_C"]
        assert same(amended.values, plain.values)  # Only the magnitudes change.


def test_a_potentials_magnitude_includes_its_charges_term():
    rng = np.random.default_rng(29)
    for _ in range(50):
        snapshot, division, _ = random_state(rng)
        amended = rops.apply(snapshot, division)
        plain = rops.apply(snapshot, division, charge_term=False)
        for snap, key in (
            (snapshot, "potentials_before_V"),
            (amended.snapshot, "potentials_after_V"),
        ):
            free, K = free_matrix(snap)
            terms = np.array([charge_term(snap.cells[n]) if n in snap.cells else 0.0 for n in free])
            carried = np.abs(np.linalg.inv(K)) @ terms  # |K_ff^-1| applied to the charges' terms
            for i, node in enumerate(free):
                added = amended.magnitudes[key][node] - plain.magnitudes[key][node]
                assert carried[i] > 0.0
                assert added == pytest.approx(carried[i], rel=1e-9)


def test_no_magnitude_decreases_with_the_charge_term():
    rng = np.random.default_rng(31)
    for i in range(100):
        snapshot, division, _ = random_state(rng, held_potential=0.0 if i % 2 else None)
        amended, plain = (
            flat(rops.apply(snapshot, division)),
            flat(rops.apply(snapshot, division, charge_term=False)),
        )
        assert amended.shape == plain.shape
        assert np.all(amended >= plain)
        assert np.any(amended > plain)


def test_a_zero_anchor_with_zero_increments_reproduces_the_magnitudes_exactly():
    rng = np.random.default_rng(37)
    for _ in range(20):
        snapshot, division, _ = random_state(rng)
        cells = {  # Every charge anchor 0, every increment 0 (the amounts as anchors).
            name: rops.Cell(
                tuple(c.amounts_fmol), (0.0,) * 3, c.volume_pL, c.background_fmol, c.charge_C
            )
            for name, c in snapshot.cells.items()
        }
        state = replace(snapshot, cells=cells)
        # No mismatch, so the daughters' increments are zero as well.
        even = replace(
            division,
            patches={k: (a, b, division.f) for k, (a, b, _) in division.patches.items()},
            carriers={},
        )
        amended = rops.apply(state, even)
        plain = rops.apply(state, even, charge_term=False)
        assert np.all(amended.values["delta_fmol"] == 0.0)
        assert np.array_equal(flat(amended), flat(plain))


def test_the_closure_laws():
    a0, tb, tau = 2e-5, 1.0, 0.4
    assert rops.aperture(a0, "linear", tau, tb, 0.5) == a0
    assert rops.aperture(a0, "linear", tau, tb, tb) == a0
    assert rops.aperture(a0, "linear", tau, tb, 1.1) == pytest.approx(a0 * 0.75, rel=1e-15)
    assert rops.aperture(a0, "linear", tau, tb, 1.4) == 0.0
    assert rops.aperture(a0, "linear", tau, tb, 3.0) == 0.0
    assert rops.closure_end("linear", tau, tb) == 1.4
    assert rops.aperture(a0, "exponential", tau, tb, 1.8) == pytest.approx(
        a0 * math.exp(-2.0), rel=1e-15
    )
    assert rops.closure_end("exponential", tau, tb) == math.inf
    assert rops.aperture(a0, "linear", math.inf, tb, 50.0) == a0
    with pytest.raises(ValueError):
        rops.aperture(a0, "cubic", tau, tb, 2.0)


def test_the_bridge_conductance_is_two_a_sigma_at_the_declared_composition():
    composition = (12.0, 140.0, 30.0)
    free = (1.33e-9, 1.96e-9, 2.03e-9)
    sigma_cyt, a, t = 0.5, 2.5e-5, 293.15
    cyt = rops.bridge_diffusivities(free, sigma_cyt, composition, Z, t)
    assert cyt[0] / free[0] == pytest.approx(cyt[2] / free[2], rel=1e-15)  # One factor.
    assert rops.free_conductivity(composition, Z, cyt, t) == pytest.approx(sigma_cyt, rel=1e-14)
    g = rops.bridge_conductance(a, cyt, composition, Z, t)
    assert g == pytest.approx(2.0 * a * sigma_cyt, rel=1e-14)
    # sigma_free of the composition by hand: (F^2/RT) sum z^2 c D.
    by_hand = rops.F**2 / (rops.R * t) * sum(c * d for c, d in zip(composition, free, strict=True))
    assert rops.free_conductivity(composition, Z, free, t) == pytest.approx(by_hand, rel=1e-14)
