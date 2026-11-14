"""R-tissue (validation/division/cleft_tissue_reference.py): division runs on synthetic worlds.

The analytic limits of docs/CELL_DIVISION_S5_DESIGN.md §7.3 (the symmetric split, the
isopotential split, the two bridge limits), the lumen through a birth, conservation, junction
gates (the lead's addition to A.6 item 5) and refusals. Every world here is synthetic and built
in this module: no J1 input, no DFS74 value.
"""

import math
from dataclasses import replace

import numpy as np
import pytest

from validation.division import cleft_egg_reference as rfull
from validation.division import cleft_tissue_reference as rt
from validation.division import partition_reference as rops

T = 300.0
Z = (1, 1, -1)
BATH = (140.0, 5.0, 145.0)
CYT = (12.0, 140.0, 30.0)
D_FREE = (1.33e-9, 1.96e-9, 2.03e-9)
D_CYT = rops.bridge_diffusivities(D_FREE, 0.5, CYT, Z, T)
# Absolute tolerances for these small cells (charges of order 1e-3 fmol).
SMALL = dict(
    cell_charge=1e-15, cleft_charge=1e-17, cell_amount=1e-12, cleft_amount=1e-14, heat=1e-15
)
EPS = rops.EPS
OLD = (1e-10, 2e-9, 5e-10)  # m/s per unit area: a passive membrane
FURROW = (5e-10, 2e-8, 0.0)
NO_PULSES = rfull.Pulses(enabled=False)


def run(world, t_end, record=()):
    return rt.simulate_divisions(world, t_end, record=record, atol=SMALL)


def own_scale(event):
    """R-ops at an event on the reference's own scale (charge_term=False: the magnitudes without
    A.8's charge term), from the pre-event snapshot and the R-ops Division R-tissue applied. Its
    values are the event's; the self-checks at 64 eps x magnitude use it."""
    result = rops.apply(event["before"], event["map"], charge_term=False)
    assert result.snapshot.cells == event["result"].snapshot.cells
    return result


def compact(
    *,
    f=0.5,
    a_old=0.5,
    a_furrow=0.5,
    carriers=None,
    law="linear",
    tau=0.05,
    a0=3e-8,
    access=1e-7,
    gap=1e-6,
    injections=(),
):
    """A cell with an old patch on the bath, a furrow from 0.02 s into a cleft with an access,
    a division at 0.1 s with a bridge, and insertion continuing on the daughters' furrows."""
    division = rt.DivisionSpec(
        "P",
        ("D1", "D2"),
        0.1,
        f,
        {"P.old": ("D1.old", "D2.old", a_old), "P.furrow": ("D1.furrow", "D2.furrow", a_furrow)},
        carriers=carriers or {},
        bridge="b",
        bridge_spec=rt.BridgeSpec(a0, D_CYT, law, tau),
    )
    share = ((0.1, 2e-10 * a_furrow), (0.2, 0.0)), ((0.1, 2e-10 * (1.0 - a_furrow)), (0.2, 0.0))
    patches = {
        "P.old": rt.PatchSpec("P", "bath", OLD, area_m2=4e-10, capacitance_F=4e-12),
        "P.furrow": rt.PatchSpec(
            "P",
            "c",
            FURROW,
            area_m2=1e-11,
            specific_capacitance_F_m2=1e-2,
            onset_s=0.02,
            schedule=((0.02, 2e-10), (0.1, 0.0)),
        ),
        "D1.old": rt.PatchSpec("D1", "bath", OLD),
        "D2.old": rt.PatchSpec("D2", "bath", OLD),
        "D1.furrow": rt.PatchSpec(
            "D1", "c", FURROW, specific_capacitance_F_m2=1e-2, schedule=share[0]
        ),
        "D2.furrow": rt.PatchSpec(
            "D2", "c", FURROW, specific_capacitance_F_m2=1e-2, schedule=share[1]
        ),
    }
    return rt.World(
        temperature_K=T,
        bath_mM=BATH,
        cells={"P": rt.CellSpec(2.0, CYT), "D1": rt.CellSpec(), "D2": rt.CellSpec()},
        clefts={"c": rt.CleftSpec(gap)},
        patches=patches,
        faces={"c.access": rt.FaceSpec(("c", "bath"), access, D_FREE)},
        injections=injections,
        divisions={"d1": division},
    )


RECORDS = (0.05, 0.1, 0.1 + 1e-3, 0.12, 0.15, 0.2, 0.3)


# ---------------------------------------------------------------- the two entry points


def test_the_static_and_division_entry_points_are_kept_apart():
    world = compact()
    with pytest.raises(ValueError, match="without divisions"):
        rt.simulate_static(world, 0.2)
    egg = rfull.Egg(  # A hand-written synthetic egg (no declared input).
        temperature_K=T,
        cytosol_volume_m3=1e-12,
        cytosol_mM=CYT,
        bath_mM=BATH,
        old_area_m2=1e-8,
        old_capacitance_F=1e-10,
        old_relative=(0.05, 1.0, 0.0),
        p_old=1e-8,
        new_permeability=(2e-11, 4e-10, 0.0),
        new_specific_capacitance_F_m2=1e-2,
        onset_s=1.0,
        activation_area_m2=1e-9,
        schedule=((1.0, 0.0),),
        gap_width_m=1e-6,
        access_law="logmean",
        access_D=D_FREE,
        a_over_l_m=1e-7,
        pulses=NO_PULSES,
    )
    converted = rt.from_egg(egg)
    assert converted.origin == rt.ORIGIN_EGG
    for candidate in (converted, replace(converted, divisions=world.divisions)):
        with pytest.raises(ValueError, match="bright line"):
            rt.simulate_divisions(candidate, 0.5)


# ---------------------------------------------------------------- the symmetric split (§7.3)


def test_a_symmetric_division_gives_identical_daughters_and_equal_trajectories():
    r = run(compact(), 0.3, RECORDS)
    (event,) = r.events
    v = event["result"].values
    assert event["time_s"] == 0.1 and np.all(v["delta_fmol"] == 0.0)
    assert v["free_energy_change_pJ"] == 0.0 and v["unmixing_pJ"] == 0.0
    born = r.at[0.1]  # After the event (R-full's record convention).
    assert born["cells"]["D1"] == born["cells"]["D2"]  # Bitwise at the event.
    for k in ("old", "furrow"):  # (Their voltages are solved again: equal to rounding.)
        p1, p2 = born["patches"][f"D1.{k}"], born["patches"][f"D2.{k}"]
        assert (p1["area_m2"], p1["capacitance_F"]) == (p2["area_m2"], p2["capacitance_F"])
    assert born["phase"]["cells"] == {"P": "retired", "D1": "live", "D2": "live"}
    worst = 0.0
    for t in RECORDS[1:]:
        rec = r.at[t]
        v1, v2 = rec["V"]["D1"], rec["V"]["D2"]
        worst = max(worst, abs(v1 - v2) / (EPS * abs(v1)))
        n1, n2 = (np.array(rec["cells"][x]["amounts_fmol"]) for x in ("D1", "D2"))
        assert np.all(np.abs(n1 - n2) <= 1e3 * EPS * np.abs(n1))
        assert abs(rec["junctions"]["b"]["current_A"]) <= 1e-24
    assert worst <= 1e3  # Equal to rounding (elimination order), not bitwise (§7.3).
    name, ratio = own_scale(event).worst()
    assert ratio <= rops.TOLERANCE_EPS, (name, ratio)


# ---------------------------------------------------------------- the isopotential split (§7.3)


def test_an_asymmetric_division_is_isopotential_with_charges_following_the_patches():
    world = compact(f=0.4, a_old=0.3, a_furrow=0.7, carriers={"K": 0.7, "Cl": 0.3})
    r = run(world, 0.15, RECORDS[:5])
    (event,) = r.events
    result = own_scale(event)
    name, ratio = result.worst()
    assert ratio <= rops.TOLERANCE_EPS, (name, ratio)
    v = result.values
    assert np.any(v["delta_fmol"] != 0.0) and v["unmixing_pJ"] > 0.0
    before = v["potentials_before_V"]
    born = r.at[0.1]
    mag = result.magnitudes["potentials_after_V"]
    for d in ("D1", "D2"):
        assert abs(born["V"][d] - before["P"]) <= 64 * EPS * (mag[d] + abs(before["P"]))
    assert born["phi"]["c"] == pytest.approx(before["c"], abs=64 * EPS * mag["c"])
    q_old = v["patch_q_before_C"]
    for k, a in (("old", 0.3), ("furrow", 0.7)):
        assert v["patch_q_after_C"][f"D1.{k}"] == pytest.approx(a * q_old[f"P.{k}"], rel=1e-13)
    # The daughters' contents and volumes are A.6's (f n + delta, complement).
    n_p = np.array(event["before"].cells["P"].amounts_fmol)
    assert born["cells"]["D1"]["volume_pL"] == 0.4 * 2.0
    assert np.allclose(born["cells"]["D1"]["amounts_fmol"], 0.4 * n_p + v["delta_fmol"], rtol=1e-13)


def test_the_lumen_follows_its_live_facing_area_through_the_birth():
    r = run(compact(f=0.4, a_old=0.4, a_furrow=0.3, carriers={"K": 1.0}), 0.3, RECORDS)

    def area(t):  # The furrow patch, then the sum of its daughters (each at its share).
        return 1e-11 + 2e-10 * (min(t, 0.2) - 0.02)

    for t in RECORDS:
        volume = r.at[t]["lumens"]["c"]["volume_pL"]
        assert volume == pytest.approx(1e-6 * area(t) / 2.0 / 1e-15, rel=1e-14), t
    total = sum(r.at[0.12]["patches"][k]["area_m2"] for k in ("D1.furrow", "D2.furrow"))
    assert total == pytest.approx(area(0.12), rel=1e-14)
    assert r.at[0.12]["patches"]["D1.furrow"]["area_m2"] == pytest.approx(
        0.3 * area(0.1) + 2e-10 * 0.3 * 0.02, rel=1e-14
    )


# ---------------------------------------------------------------- bridge limits (§7.3)


def ghk_k_slope_conductance(pa, c_in, c_out):
    """dI/dV of a K-only constant-field membrane at the K equilibrium (S): with u0 = ln(c_o/c_i),
    (F^2/RT) P A c_i c_o u0 / (c_o - c_i)."""
    u0 = math.log(c_out / c_in)
    return rops.F**2 / (rops.R * T) * pa * c_in * c_out * u0 / (c_out - c_in)


def two_pulses(cell, *, start, amplitude, duration, period):
    """+I then -I into one cell, each sampled at its end (the step response's plateau)."""
    return rt.InjectionSpec(
        cell,
        rfull.Pulses(
            amplitude_A=amplitude,
            duration_s=duration,
            period_s=period,
            first_onset_s=start,
            sample_s=duration,
        ),
        {"K": 0.5, "Cl": 0.5},
    )


def coupling(r, start, duration, period):
    """V2/V1 of the injected D1 and its sister from the +I and -I steps (even orders cancel)."""
    edges = [start, start + duration, start + period, start + period + duration]
    v = {d: [r.at[t]["V"][d] for t in edges] for d in ("D1", "D2")}
    step = {d: (v[d][1] - v[d][0]) - (v[d][3] - v[d][2]) for d in v}
    return step["D2"] / step["D1"], step


def k_only_pair(*, furrow=None, access=0.0, tau=math.inf, a0=3e-8, injections=()):
    """A K-only founder at E_K (an exact steady state) dividing at 0.02 s into a symmetric pair
    with a bridge; optionally a K-only furrow from 0.001 s into a large cleft (its composition
    stays the bath's: the resistive limit) with an access A/L."""
    perm = (0.0, 1e-7, 0.0)
    patches = {
        "P.old": rt.PatchSpec("P", "bath", perm, area_m2=1e-10, capacitance_F=1e-12),
        "D1.old": rt.PatchSpec("D1", "bath", perm),
        "D2.old": rt.PatchSpec("D2", "bath", perm),
    }
    maps = {"P.old": ("D1.old", "D2.old", 0.5)}
    clefts, faces = {}, {}
    if furrow:
        patches["P.f"] = rt.PatchSpec(
            "P", "c", perm, area_m2=furrow, specific_capacitance_F_m2=1e-2, onset_s=0.001
        )
        patches["D1.f"] = rt.PatchSpec("D1", "c", perm, specific_capacitance_F_m2=1e-2)
        patches["D2.f"] = rt.PatchSpec("D2", "c", perm, specific_capacitance_F_m2=1e-2)
        maps["P.f"] = ("D1.f", "D2.f", 0.5)
        clefts = {"c": rt.CleftSpec(1e-2)}
        faces = {"c.access": rt.FaceSpec(("c", "bath"), access, D_FREE)}
    division = rt.DivisionSpec(
        "P",
        ("D1", "D2"),
        0.02,
        0.5,
        maps,
        bridge="b",
        bridge_spec=rt.BridgeSpec(a0, D_CYT, "linear", tau),
    )
    return rt.World(
        temperature_K=T,
        bath_mM=BATH,
        cells={"P": rt.CellSpec(5.0, CYT), "D1": rt.CellSpec(), "D2": rt.CellSpec()},
        clefts=clefts,
        patches=patches,
        faces=faces,
        injections=injections,
        divisions={"d": division},
    )


def test_an_open_bridge_couples_the_daughters_by_rm_over_rm_plus_rb():
    start, duration, period = 0.05, 0.05, 0.1
    world = k_only_pair(
        injections=(
            two_pulses("D1", start=start, amplitude=6e-14, duration=duration, period=period),
        )
    )
    edges = (start, start + duration, start + period, start + period + duration)
    r = run(world, 0.21, edges)
    measured, step = coupling(r, start, duration, period)
    g_m = ghk_k_slope_conductance(1e-7 * 0.5e-10, CYT[1], BATH[1])  # A daughter's old patch.
    g_b = rops.bridge_conductance(3e-8, D_CYT, CYT, Z, T)
    assert g_b == pytest.approx(2 * 3e-8 * 0.5, rel=1e-13)  # 2 a sigma_cyt (A.7)
    expected = g_b / (g_b + g_m)  # Rm / (Rm + R_b)
    assert 1e-3 < 1.0 - expected < 0.05  # R_b << Rm, the regime of the limit.
    assert abs(step["D1"]) > 1e-5
    assert measured == pytest.approx(expected, abs=1e-6)
    assert (1.0 - measured) == pytest.approx(1.0 - expected, rel=1e-3)


def t_network_coupling(g_o, g_f, g_a):
    """V2/V1 for current into D1: D1, D2 each with g_o to the bath and g_f to the cleft, the
    cleft with g_a to the bath (nodal analysis)."""
    G = np.array([[g_o + g_f, 0.0, -g_f], [0.0, g_o + g_f, -g_f], [-g_f, -g_f, 2 * g_f + g_a]])
    v = np.linalg.solve(G, [1.0, 0.0, 0.0])
    return v[1] / v[0]


@pytest.mark.parametrize("access", [5e-11, 0.0])  # g_a about g_f; then sealed
def test_a_closed_bridge_leaves_the_trans_cleft_t_network(access):
    start, duration, period = 0.05, 0.05, 0.1
    furrow = 2e-11
    world = k_only_pair(
        furrow=furrow,
        access=access,
        tau=0.01,
        injections=(
            two_pulses("D1", start=start, amplitude=6e-14, duration=duration, period=period),
        ),
    )
    edges = (start, start + duration, start + period, start + period + duration)
    r = run(world, 0.21, (0.025, 0.031, 0.035) + edges)
    assert r.at[0.025]["junctions"]["b"]["aperture_m"] == pytest.approx(1.5e-8, rel=1e-12)
    for t in (0.031, 0.035):  # Closed from t_b + tau on: no bridge current at all.
        assert r.at[t]["junctions"]["b"]["aperture_m"] == 0.0
        assert r.at[t]["junctions"]["b"]["current_A"] == 0.0
    measured, step = coupling(r, start, duration, period)
    lumen = r.at[start]["lumens"]["c"]["mM"]
    g_o = ghk_k_slope_conductance(1e-7 * 0.5e-10, CYT[1], BATH[1])
    g_f = ghk_k_slope_conductance(1e-7 * 0.5 * furrow, CYT[1], lumen[1])
    k = tuple(access * d for d in D_FREE)
    g_a = (
        rops.F**2 / (rops.R * T) * sum(z * z * ks * c for z, ks, c in zip(Z, k, lumen, strict=True))
    )
    expected = t_network_coupling(g_o, g_f, g_a)
    assert abs(step["D1"]) > 1e-5 and measured > 1e-3
    assert measured == pytest.approx(expected, rel=2e-3)
    if access == 0.0:  # The sealed limit: Rj = 2 r_new / A_face.
        r_new = 1.0 / ghk_k_slope_conductance(1e-7, CYT[1], lumen[1])  # ohm m2
        rj = (1.0 / g_o) * (1.0 / measured - 1.0)
        assert rj == pytest.approx(2.0 * r_new / (0.5 * furrow), rel=2e-3)


def test_the_closure_laws_in_the_tissue():
    inj = (two_pulses("D1", start=0.11, amplitude=1e-13, duration=0.02, period=0.05),)
    for law, tau in (("linear", 0.05), ("exponential", 0.02)):
        r = run(compact(law=law, tau=tau, injections=inj), 0.17, (0.1, 0.12, 0.155, 0.16))
        for t in (0.1, 0.12, 0.155, 0.16):
            b = r.at[t]["junctions"]["b"]
            assert b["aperture_m"] == rops.aperture(3e-8, law, tau, 0.1, t)
            assert b["gate"] == 1.0
        assert abs(r.at[0.12]["junctions"]["b"]["current_A"]) > 1e-16  # Injected D1 drives it.
        if law == "linear":  # Closed from 0.1 + 0.05 on.
            assert r.at[0.155]["junctions"]["b"]["current_A"] == 0.0
            assert r.at[0.16]["junctions"]["b"]["current_A"] == 0.0
        else:
            assert r.at[0.16]["junctions"]["b"]["aperture_m"] > 0.0


# ---------------------------------------------------------------- 1 -> 2 -> 4, contacts, gates


def four_cells(*, second_law="linear"):
    """1 -> 2 -> 4: a symmetric first division (bridge b, linear closure), then each daughter
    divides with its own bridge; every cell keeps its old patch on the bath."""
    cells = {"P": rt.CellSpec(2.0, CYT)}
    patches = {"P.old": rt.PatchSpec("P", "bath", OLD, area_m2=4e-10, capacitance_F=4e-12)}
    divisions = {}
    plan = (
        ("P", ("A", "B"), 0.05, "b"),
        ("A", ("A1", "A2"), 0.12, "bA"),
        ("B", ("B1", "B2"), 0.13, "bB"),
    )
    for parent, (d1, d2), time_s, bridge in plan:
        for d in (d1, d2):
            cells[d] = rt.CellSpec()
            patches[f"{d}.old"] = rt.PatchSpec(d, "bath", OLD)
        law = "linear" if parent == "P" else second_law
        divisions[parent] = rt.DivisionSpec(
            parent,
            (d1, d2),
            time_s,
            0.5 if parent != "B" else 0.3,
            {f"{parent}.old": (f"{d1}.old", f"{d2}.old", 0.5 if parent != "B" else 0.3)},
            bridge=bridge,
            bridge_spec=rt.BridgeSpec(3e-8, D_CYT, law, 0.04),
        )
    return rt.World(T, BATH, cells, patches, divisions=divisions)


def test_one_to_two_to_four_applies_r_ops_at_each_division_and_retires_bridges():
    r = run(four_cells(), 0.2, (0.04, 0.05, 0.1, 0.12, 0.13, 0.2))
    assert [e["division"] for e in r.events] == ["P", "A", "B"]
    for e in r.events:
        name, ratio = own_scale(e).worst()
        assert ratio <= rops.TOLERANCE_EPS, (e["division"], name, ratio)
    final = r.at[0.2]
    assert set(final["V"]) == {"A1", "A2", "B1", "B2"}
    assert final["phase"]["bridges"] == {"b": "retired", "bA": "live", "bB": "live"}
    assert final["junction_gates"] == {"b": 0.0, "bA": 1.0, "bB": 1.0}
    assert r.at[0.04]["junction_gates"] == {"b": 0.0, "bA": 0.0, "bB": 0.0}
    assert r.at[0.1]["junction_gates"] == {"b": 1.0, "bA": 0.0, "bB": 0.0}
    volumes = [final["cells"][x]["volume_pL"] for x in ("A1", "A2", "B1", "B2")]
    assert volumes == [0.5, 0.5, 0.3, 0.7]


def test_a_parent_whose_bridge_is_still_open_cannot_divide():
    # Exponential closure never ends, so a daughter with that bridge cannot divide (§3.8).
    world = four_cells()
    divisions = dict(world.divisions)
    first = divisions["P"]
    divisions["P"] = replace(first, bridge_spec=replace(first.bridge_spec, law="exponential"))
    with pytest.raises(ValueError, match="still open"):
        rt.check_world(replace(world, divisions=divisions))
    early = four_cells()
    late = dict(early.divisions)
    late["A"] = replace(late["A"], time_s=0.08)  # Before the first bridge closes (0.09).
    with pytest.raises(ValueError, match="still open"):
        rt.check_world(replace(early, divisions=late))
    rt.check_world(early)  # 0.12 >= 0.05 + 0.04: closed.


def compact_four():
    """The topology of design §4.3 and §6.2 (1 -> 2 -> 4 with second furrows): P's furrow opens
    cleft c1; P divides at 0.1 s (bridge b, closed by 0.2 s); each daughter opens its own second
    furrow into a new cleft (c2a, c2b) joined to c1 at the centre, then divides with its three
    patches (old, first furrow, second furrow). 7 cells, 3 clefts, 20 patches, 5 faces,
    3 bridges; B divides asymmetrically (carriers K and Cl)."""
    w = 1e-6
    cells = {"P": rt.CellSpec(2.0, CYT)}
    patches = {
        "P.old": rt.PatchSpec("P", "bath", OLD, area_m2=4e-10, capacitance_F=4e-12),
        "P.f1": rt.PatchSpec(
            "P",
            "c1",
            FURROW,
            area_m2=1e-11,
            specific_capacitance_F_m2=1e-2,
            onset_s=0.02,
            schedule=((0.02, 2e-10), (0.1, 0.0)),
        ),
    }
    plan = (
        ("P", ("A", "B"), 0.1, 0.5, 0.5, "b"),
        ("A", ("A1", "A2"), 0.25, 0.5, 0.5, "bA"),
        ("B", ("B1", "B2"), 0.26, 0.4, 0.6, "bB"),
    )
    second = {"A": ("c2a", 0.15), "B": ("c2b", 0.16)}
    divisions = {}
    for parent, daughters, t, f, a, bridge in plan:
        kinds = ("old", "f1") if parent == "P" else ("old", "f1", "f2")
        maps = {}
        for kind in kinds:
            node = {"old": "bath", "f1": "c1"}.get(kind) or second[parent][0]
            perm = OLD if kind == "old" else FURROW
            c_d = 0.0 if kind == "old" else 1e-2
            for d, share in zip(daughters, (a, 1.0 - a), strict=True):
                schedule = (
                    ((t, 1e-10 * share), (t + 0.1, 0.0)) if kind == "f1" and parent == "P" else ()
                )
                patches[f"{d}.{kind}"] = rt.PatchSpec(
                    d, node, perm, specific_capacitance_F_m2=c_d, schedule=schedule
                )
            maps[f"{parent}.{kind}"] = (f"{daughters[0]}.{kind}", f"{daughters[1]}.{kind}", a)
        for d in daughters:
            cells[d] = rt.CellSpec()
        divisions[parent] = rt.DivisionSpec(
            parent,
            daughters,
            t,
            f,
            maps,
            carriers={} if a == f else {"K": 0.5, "Cl": 0.5},
            bridge=bridge,
            bridge_spec=rt.BridgeSpec(3e-8, D_CYT, "linear", 0.1 if parent == "P" else 0.05),
        )
    for parent, (node, onset) in second.items():
        patches[f"{parent}.f2"] = rt.PatchSpec(
            parent,
            node,
            FURROW,
            area_m2=5e-12,
            specific_capacitance_F_m2=1e-2,
            onset_s=onset,
            schedule=((onset, 1e-10), (onset + 0.09, 0.0)),
        )
    # A's and B's second-furrow patches split again at their divisions (no further insertion).
    clefts = {c: rt.CleftSpec(w) for c in ("c1", "c2a", "c2b")}
    faces = {
        "c1.access": rt.FaceSpec(("c1", "bath"), 1e-7, D_FREE),
        "c2a.access": rt.FaceSpec(("c2a", "bath"), 1e-7, D_FREE),
        "c2b.access": rt.FaceSpec(("c2b", "bath"), 1e-7, D_FREE),
        "centre.a": rt.FaceSpec(("c1", "c2a"), 5e-8, D_FREE),
        "centre.b": rt.FaceSpec(("c2b", "c1"), 5e-8, D_FREE),
    }
    return rt.World(T, BATH, cells, patches, clefts, faces, divisions=divisions)


def test_the_compact_one_to_two_to_four_world_with_second_furrows():
    world = compact_four()
    assert (len(world.cells), len(world.clefts), len(world.patches), len(world.faces)) == (
        7,
        3,
        20,
        5,
    )
    times = (0.05, 0.1, 0.15, 0.16, 0.2, 0.25, 0.26, 0.3)
    r = run(world, 0.3, times)
    assert [e["division"] for e in r.events] == ["P", "A", "B"]
    for e in r.events:
        name, ratio = own_scale(e).worst()
        assert ratio <= rops.TOLERANCE_EPS, (e["division"], name, ratio)
        before = e["result"].values["potentials_before_V"]
        after = e["result"].values["potentials_after_V"]
        for node in ("c1", "c2a", "c2b"):  # Outside potentials are unchanged by a birth.
            if node in before:
                assert after[node] == pytest.approx(before[node], abs=1e-15)
    final = r.at[0.3]
    assert set(final["V"]) == {"A1", "A2", "B1", "B2"}
    assert set(final["lumens"]) == {"c1", "c2a", "c2b"}
    assert final["phase"]["bridges"] == {"b": "retired", "bA": "live", "bB": "live"}
    assert r.at[0.15]["phase"]["clefts"] == {"c1": "live", "c2a": "live", "c2b": "pending"}
    for t in times:  # Each lumen follows its live facing area (A.5), through every birth.
        rec = r.at[t]
        for c, lumen in rec["lumens"].items():
            facing = [k for k, p in rec["patches"].items() if world.patches[k].node == c]
            area = math.fsum(rec["patches"][k]["area_m2"] for k in facing)
            assert lumen["volume_pL"] == pytest.approx(1e-6 * area / 2.0 / 1e-15, rel=1e-14)
    # c1's facing area is continuous through the three births (insertion stopped by 0.2 s).
    c1 = [r.at[t]["lumens"]["c1"]["volume_pL"] for t in (0.2, 0.25, 0.26, 0.3)]
    assert max(c1) - min(c1) <= 1e-14 * c1[0]
    b = r.events[2]["result"].values
    assert np.any(b["delta_fmol"] != 0.0) and b["unmixing_pJ"] > 0.0


def with_neighbour():
    """A founder M beside P, joined by a gated contact; P divides symmetrically at 0.05 s and the
    contact splits a_e = 0.25 to D1-M, 0.75 to D2-M, each keeping the parent's gate."""
    world = compact()
    cells = dict(world.cells, M=rt.CellSpec(1.0, (30.0, 100.0, 40.0), initial_V=-0.03))
    patches = dict(
        world.patches,
        **{"M.old": rt.PatchSpec("M", "bath", OLD, area_m2=2e-10, capacitance_F=2e-12)},
    )
    perm = (1e-7, 1e-7, 1e-7)
    contacts = {
        "e": rt.ContactSpec(("P", "M"), perm, area_m2=1e-12, gate=0.7),
        "e1": rt.ContactSpec(("D1", "M"), perm),
        "e2": rt.ContactSpec(("M", "D2"), perm),
    }
    division = replace(world.divisions["d1"], contacts={"e": ("e1", "e2", 0.25)})
    return replace(
        world, cells=cells, patches=patches, contacts=contacts, divisions={"d1": division}
    )


def test_a_neighbour_contact_splits_keeps_its_gate_and_reads_zero_when_not_live():
    r = run(with_neighbour(), 0.12, (0.09, 0.1, 0.12))
    assert r.at[0.09]["junction_gates"] == {"e": 0.7, "e1": 0.0, "e2": 0.0, "b": 0.0}
    assert r.at[0.1]["junction_gates"] == {"e": 0.0, "e1": 0.7, "e2": 0.7, "b": 1.0}
    (event,) = r.events
    v = event["result"].values
    assert v["junction_gates_after"] == {"e": (0.0,), "e1": (0.7,), "e2": (0.7,), "b": (1.0,)}
    assert event["result"].snapshot.contacts["e1"].area_m2 == 0.25e-12
    # The parent's contact current, from the pre-event state, splits by area at the birth.
    before = event["before"]
    phi = v["potentials_before_V"]
    u = rops.F * (phi["P"] - phi["M"]) / (rops.R * T)
    c_p = np.array(before.cells["P"].amounts_fmol) / before.cells["P"].volume_pL
    c_m = np.array(before.cells["M"].amounts_fmol) / before.cells["M"].volume_pL
    i_e = rops.F * sum(
        z * rfull.ghk_flux(0.7 * 1e-7 * 1e-12, z, u, a, b)
        for z, a, b in zip(Z, c_p, c_m, strict=True)
    )
    j = r.at[0.1]["junctions"]
    assert j["e1"]["cells"] == ("D1", "M") and j["e2"]["cells"] == ("M", "D2")  # As declared.
    i1, i2 = j["e1"]["current_A"], -j["e2"]["current_A"]  # Both from the daughter to M.
    assert abs(i_e) > 1e-15
    assert i1 + i2 == pytest.approx(i_e, rel=1e-12)
    assert i1 / i2 == pytest.approx(1.0 / 3.0, rel=1e-12)


# ---------------------------------------------------------------- conservation and insertion


def test_a_closed_world_conserves_its_contents_and_charge_across_a_division():
    """No exchange with the bath: impermeable bath patches, a sealed cleft, no fill after the
    onset; furrows, the bridge and a contact move ions between the cells and the cleft."""
    world = with_neighbour()
    world = replace(world, cells=dict(world.cells, P=rt.CellSpec(2.0, CYT, initial_V=-0.05)))
    sealed = (0.0, 0.0, 0.0)
    patches = {
        k: (replace(p, permeability_m_s=sealed) if p.node == "bath" else replace(p, schedule=()))
        for k, p in world.patches.items()
    }
    world = replace(
        world, patches=patches, faces={"c.access": rt.FaceSpec(("c", "bath"), 0.0, D_FREE)}
    )
    times = (0.03, 0.06, 0.1, 0.13, 0.2)
    r = run(world, 0.2, times)

    def totals(rec):
        nodes = [*rec["cells"].values(), *rec["lumens"].values()]
        return (
            np.sum([n["amounts_fmol"] for n in nodes], axis=0),
            math.fsum(n["charge_C"] for n in nodes),
        )

    amounts0, charge0 = totals(r.at[0.03])
    for t in times[1:]:
        amounts, charge = totals(r.at[t])
        assert np.allclose(amounts, amounts0, rtol=1e-10, atol=0.0), t
        assert charge == pytest.approx(charge0, rel=1e-9, abs=1e-24), t


def test_one_patch_insertion_at_fixed_charge():
    """An impermeable patch inserted at a fixed charge: V = Q / C(t) and the heat is
    (1/2) Q^2 (1/C0 - 1/C(t)) (design A.4)."""
    patch = rt.PatchSpec(
        "P",
        "bath",
        (0.0, 0.0, 0.0),
        area_m2=4e-10,
        capacitance_F=4e-12,
        specific_capacitance_F_m2=1e-2,
        schedule=((0.0, 1e-9),),
    )
    world = rt.World(T, BATH, {"P": rt.CellSpec(2.0, CYT, initial_V=-0.05)}, {"P.old": patch})
    r = rt.simulate_static(world, 0.5, record=(0.25, 0.5), atol=SMALL)
    q = 4e-12 * -0.05
    for t in (0.25, 0.5):
        c = 4e-12 + 1e-2 * 1e-9 * t
        assert r.at[t]["V"]["P"] == pytest.approx(q / c, rel=1e-12)
        heat = 0.5 * q * q * (1.0 / 4e-12 - 1.0 / c) * 1e12
        assert r.at[t]["heat_pJ"] == pytest.approx(heat, rel=1e-8)


# ---------------------------------------------------------------- refusals


def refused(world, message, t_end=0.2):
    with pytest.raises(ValueError, match=message):
        rt.simulate_divisions(world, t_end, atol=SMALL)


def test_inadmissible_worlds_are_refused():
    w = compact()
    d = w.divisions["d1"]
    extra = dict(
        w.patches,
        **{"P.extra": rt.PatchSpec("P", "bath", OLD, area_m2=1e-11, capacitance_F=1e-13)},
    )
    refused(replace(w, patches=extra), "covers the parent's live patches")
    unmapped = {"P.old": d.patches["P.old"]}
    refused(replace(w, divisions={"d1": replace(d, patches=unmapped)}), "no division's map")
    late_furrow = dict(
        w.patches, **{"P.furrow": replace(w.patches["P.furrow"], schedule=((0.02, 2e-10),))}
    )
    refused(replace(w, patches=late_furrow), "outside its living interval")
    early = dict(
        w.patches, **{"D1.furrow": replace(w.patches["D1.furrow"], schedule=((0.05, 1e-10),))}
    )
    refused(replace(w, patches=early), "outside its living interval")
    late_onset = dict(w.patches, **{"P.furrow": replace(w.patches["P.furrow"], onset_s=0.1)})
    refused(replace(w, patches=late_onset), "outside its cell's life")
    floating = rt.World(
        T,
        BATH,
        {"Q": rt.CellSpec(1.0, CYT, initial_V=-0.05)},
        {
            "Q.f": rt.PatchSpec(
                "Q", "c", FURROW, area_m2=1e-12, specific_capacitance_F_m2=1e-2, onset_s=0.01
            )
        },
        clefts={"c": rt.CleftSpec(1e-6)},
    )
    refused(floating, "no patch on the bath")
    pulse = rt.InjectionSpec(
        "D1",
        rfull.Pulses(amplitude_A=1e-13, duration_s=0.02, period_s=1.0, first_onset_s=0.05),
        {"K": 1.0},
    )
    refused(replace(w, injections=(pulse,)), "living interval")
    changed = dict(
        w.patches, **{"D2.old": replace(w.patches["D2.old"], permeability_m_s=(0.0, 1e-9, 0.0))}
    )
    refused(replace(w, patches=changed), "keeps")
    refused(replace(w, divisions={"d1": replace(d, f=0.4)}), "required")
    second = dict(
        w.patches,
        **{
            "D1.f2": rt.PatchSpec(
                "D1", "c", FURROW, area_m2=1e-12, specific_capacitance_F_m2=1e-2, onset_s=0.15
            )
        },
    )
    refused(replace(w, patches=second), "already open")
    tiny = dict(w.cells, P=rt.CellSpec(2.0, (1e-12, 140.0, 30.0)))
    big_mismatch = replace(
        d,
        f=0.5,
        patches={"P.old": ("D1.old", "D2.old", 0.05), "P.furrow": ("D1.furrow", "D2.furrow", 0.95)},
        carriers={"Na": 1.0},
    )
    with pytest.raises(rops.PartitionRefused, match="amount <= 0"):
        rt.simulate_divisions(
            replace(w, cells=tiny, divisions={"d1": big_mismatch}), 0.2, atol=SMALL
        )
