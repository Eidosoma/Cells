"""fr1-closed-compartment-v1's tools on the host: the judge, the drafter and the guards (tier 1).

No engine run: synthetic records with known orders, budgets, energies and comparisons exercise the
judge's derivation and every machine criterion, each with a planted error that must fail its own
criterion; the generator's judged entry refuses before writing anything; the drafter's section is
the checked-in one, and it refuses a registered protocol; registration takes the record's status
and changes nothing else. The tests are status-agnostic: registration changes the status and adds
the record alone.
"""

import hashlib
import json
import math

import pytest

from validation.tissue import compartment_acceptance_judge as judge
from validation.tissue import compartment_acceptance_protocol as drafter
from validation.tissue import compartment_acceptance_qualification as generator

PROTOCOL = json.loads(generator.PROTOCOL.read_text())
D = drafter.derivation()
VOLUMES = {"cell_0": 1.0, "ecs_0": 0.1, "ecs_e": 1.0}
A, B = D["C4"]["a"], D["C4"]["b"]


def times(end, every=0.01):
    return [round(k * every, 10) for k in range(int(round(end / every)) + 1)]


def exact(world, t):
    """A smooth, positive two- or three-node trajectory per world (fmol)."""
    total = 1e-3
    if world == "C8":
        e = [total * math.exp(-2 * s) for s in t]
        o = [1e-7 + total * (1 - math.exp(-s)) * 0.5 for s in t]
        c = [total + 1e-6 + 1e-7 - x - y for x, y in zip(e, o, strict=True)]
        return dict(amount_S_cell_0=c, amount_S_ecs_0=o, amount_S_ecs_e=e)
    rate = dict(C4=30.0, C6=1.0, C7=1.0).get(world, 0.5)
    c = [total * (2 / 3 + math.exp(-rate * s) / 3) for s in t]
    o = [1e-7 + total - x for x in c]
    out = dict(amount_S_cell_0=c, amount_S_ecs_0=o)
    if world == "C7":
        out["amount_P_ecs_0"] = [1e-10 + 1e-5 * (1 - math.exp(-s)) for s in t]
    if world == "C6":
        out["cleared_ecs_0_fmol"] = [1e-5 * (1 - math.exp(-s)) for s in t]
    return out


def ledgers(t):
    return {f"ratio_{name}": [0.01 if name == "energy" else 0.0] * len(t)
            for name in (*drafter.MATERIAL_LEDGERS, "energy")}


def with_energy(part, routes):
    """Route work equal to the free-energy change on the part's own trajectory (A.10), each
    route's magnitude its share."""
    g0 = judge.free_energy(part, 0)
    for r in routes:
        part["series"][f"work_{r}_pJ"] = []
        part["series"][f"magnitude_{r}_pJ"] = []
    for j in range(len(part["record_s"])):
        dg = judge.free_energy(part, j) - g0
        for k, r in enumerate(routes):
            part["series"][f"work_{r}_pJ"].append(dg if k == 0 else 0.0)
            part["series"][f"magnitude_{r}_pJ"].append(abs(dg) + 1e-6)
    return part


def engine(world, dt, *, end=1.0, order=2, error=1e-9, every=0.01, routes=("load",)):
    t = times(end, every)
    series = exact(world, t)
    e = (dt / 1e-3) ** order
    series = {k: [x + (error * e * (1 - math.exp(-s)) if k.startswith("amount_") and
                       k != "amount_S_ecs_e" and "cell" not in k else 0.0)
                  for x, s in zip(v, t, strict=True)] for k, v in series.items()}
    flows = [0.1 * s + 1e-3 for s in t]
    series |= dict(energy_residual_pJ=[1e-7 * f for f in flows], energy_flows_pJ=flows,
                   energy_bound_pJ=[1.0] * len(t))
    series |= ledgers(t)
    gain = [x - series["amount_S_ecs_0"][0] for x in series["amount_S_ecs_0"]]
    for r in routes:
        series[f"moved_{r}_fmol"] = gain if r == routes[0] else [0.0] * len(t)
    part = dict(kind="engine", admitted=True, completed=True, refusal=None, dt_s=dt,
                steps=round(end / dt) if dt else 0, record_s=t, series=series,
                routes=list(routes),
                volumes_pL={k: v for k, v in VOLUMES.items()
                            if f"amount_S_{k}" in series})
    return with_energy(part, routes)


def reference_of(part):
    return dict(record_s=list(part["record_s"]),
                series={k: list(v) for k, v in part["series"].items()
                        if k.startswith(("amount_", "cleared_"))})


def step_map_of(part, dt):
    s = part["series"]
    x = s["amount_S_cell_0"][-1] / (s["amount_S_cell_0"][-1] + s["amount_S_ecs_0"][-1])
    split = -A * (A + 2 * B) * dt * dt / 96.0
    return dict(reference_of(part), x_star=x, x_eq=x / (1 + split))


def comparison(**fields):
    return dict(kind="comparison", admitted=True, completed=True, **fields)


def parts():
    out = {}
    out["C3_flux"] = engine("C3", 1e-3, end=1.0)
    out["C3_first_order"] = engine("C3", 1e-3, end=1.0)
    out["C5_saturable"] = engine("C5", 1e-3, end=1.0, routes=("release",))
    for rungs, world, routes in ((generator.C4_RUNGS, "C4", ("load", "release")),
                                 (generator.C6_RUNGS, "C6", ("load",)),
                                 (generator.C7_RUNGS, "C7", ("load",)),
                                 (generator.C8_RUNGS, "C8", ("uptake", "load"))):
        for name, dt in rungs.items():
            out[name] = engine(world, dt, routes=routes)
    for name in generator.C6_RUNGS:  # Clearance work closes the energy beside the route's.
        s = out[name]["series"]
        s["cleared_work_ecs_0_pJ"] = [0.0] * len(out[name]["record_s"])
    out["C10_rk4"] = engine("C3", 1e-4, end=0.2, every=1e-4)
    for name, (law, _) in generator.C11_PARTS.items():
        out[name] = engine("C3", 1e-3, end=0.2, every=1e-3,
                           routes=("load",) if law.endswith("export") else ("release",))
    for name in ("K1_one_way", "K2_no_clearance"):
        world = "C4" if name == "K1_one_way" else "C6"
        part = engine(world, 1e-3)
        part["series"]["amount_S_ecs_0"] = [x * 0.5 for x in part["series"]["amount_S_ecs_0"]]
        part["series"]["amount_S_cell_0"] = [x * 1.2 for x in part["series"]["amount_S_cell_0"]]
        out[name] = part
    out["C1_refusals"] = dict(kind="refusals", admitted=True, completed=True, classes={
        cls: dict(refused=[dict(refused=True, message="m", check=check)],
                  admitted=[dict(admitted=True, ran=True, message=None)])
        for cls, check in drafter.C1_CHECKS.items()})
    out["C2_identity"] = dict(kind="identity", admitted=True, completed=True,
                              pairs={f"pair {k}": [] for k in range(4)})
    live = dict(s1=True, s2=1e-3, s3=1e-6, rows=101, owner_ions_moved=True, max_phi_owner=0.06,
                max_phi_node=0.06)
    out["C9_silence"] = dict(kind="silence", admitted=True, completed=True, programs={
        k: dict(live) for k in ("scalar", "rk4", "windowed", "vector_window", "batch",
                                "restart_snapshot")} | {"S4_reported": {}})
    out["C12_restart"] = comparison(
        restarts={f"{t:g} {m}": dict(equal=True) for t in generator.RESTART_TIMES_S
                  for m in ("in_process", "snapshot")}, planted=dict(equal=False))
    def plant(ledger, margin):
        ratios = {name: 0.0 for name in (*drafter.MATERIAL_LEDGERS, "energy")}
        ratios[ledger] = margin
        if ledger == "outside":
            ratios["total"] = margin / 2
        return dict(plant=dict(kind=ledger), prefix_rows=101,
                    prefix_max_ratio={name: 1e-12 for name in ratios},
                    planted_ratios=ratios, engine=dict(
                        refused=True, message="Resolved pump accounting failed: " + ledger))
    out["C13_controls"] = dict(kind="plants", admitted=True, completed=True, plants=dict(
        move=plant("outside", 9e6), work=plant("energy", 21.0)))
    out["K3_planted"] = dict(kind="plants", admitted=True, completed=True, plants=dict(
        route=dict(plant=dict(kind="route"), s1_rows=[True] + [False] * 20,
                   s2_rows=[2e-6] + [4e4] * 20),
        anchor=dict(plant=dict(kind="anchor"), s1_rows=[True] * 21, s2_rows=[3e7] * 21)))
    out["C12_batch"] = comparison(worlds={
        f"world_{i}": dict(scalar_relative=0.0, reversed_equal=True, final_reversed_equal=True)
        for i in range(1, len(generator.C12_WORLDS) + 1)})
    worlds = {"C3_flux": reference_of(out["C3_flux"]),
              "C3_first_order": reference_of(out["C3_first_order"]),
              "C5": reference_of(out["C5_saturable"])}
    for item in ("C4", "C6", "C7", "C8"):
        declared = D[item]["ladder_parts"][0]
        worlds[item] = reference_of(engine(item, 0.0, routes=out[declared]["routes"]))
    step_map = {name: step_map_of(out[name], dt) for name, dt in generator.C4_RUNGS.items()}
    energy = {name: dict(record_s=list(out[name]["record_s"]),
                         series={k: list(v) for k, v in out[name]["series"].items()
                                 if k.startswith("amount_")})
              for name in generator.C11_PARTS}
    c6 = out[D["C10"]["c6_part"]]
    energy[D["C10"]["c6_part"]] = dict(record_s=list(c6["record_s"]), dG_pJ=[
        sum(c6["series"][f"work_{r}_pJ"][j] for r in c6["routes"])
        + c6["series"]["cleared_work_ecs_0_pJ"][j] for j in range(len(c6["record_s"]))])
    out["references"] = dict(kind="reference", admitted=True, completed=True, worlds=worlds,
                             step_map=step_map, energy=energy)
    return out


def failed(p):
    _, evaluated = judge.verdict(p, PROTOCOL)
    return sorted(c["id"] for c in evaluated["criteria"] if c["judged"] and not c["passed"])


# ------------------------------------------------------------------ the judge


def test_a_complete_run_passes_every_criterion():
    assert failed(parts()) == []


def _rungs(p, prefix, **kwargs):
    rungs = {"C4": generator.C4_RUNGS, "C6": generator.C6_RUNGS}[prefix]
    routes = p[next(iter(rungs))]["routes"]
    for name, dt in rungs.items():
        p[name] = engine(prefix, dt, routes=routes, **kwargs)


@pytest.mark.parametrize("plant, expected", [
    ("refusal_check", {"C1_refusals"}),
    ("identity", {"C2_identity"}),
    # An amount off its reference moves the free energy off the booked work too.
    ("c3_off", {"C3_loading", "C10_closure"}),
    ("c3_reconciliation", {"C3_loading"}),
    ("first_order", {"C4_order_amount_S_ecs_0"}),
    ("c4_too_large", {"C4_C8_state_error", "C4_C8_reference"}),
    ("step_map_off", {"C4_step_map"}),
    ("splitting", {"C4_splitting_term"}),
    ("c5_off", {"C5_saturable", "C10_closure"}),
    ("cleared_off", {"C6_cleared"}),
    ("s1", {"C9_S1"}),
    ("s2", {"C9_S2_S3"}),
    ("not_live", {"C9_live"}),
    ("work_off", {"C10_closure"}),
    ("rk4_energy", {"C10_rk4"}),
    ("imex_energy", {"C10_imex"}),
    ("c11", {"C11_from_trace"}),
    ("ledger", {"C11_ledgers"}),
    ("restart", {"C12_restart"}),
    ("batch_relative", {"C12_batch_scalar"}),
    ("batch_reversed", {"C12_batch_reversed"}),
    ("k1_close", {"K1"}),
    ("k2_close", {"K2"}),
    ("k4", {"K4"}),
    ("move_wrong_ledger", {"C13_move"}),
    ("move_prefix", {"C13_move"}),
    ("move_cytosol", {"C13_move"}),
    ("work_margin", {"C13_work_margin"}),
    ("work_material", {"C13_work"}),
    ("route_row0", {"K3_route"}),
    ("route_margin", {"K3_route_margin"}),
    ("anchor_row", {"K3_anchor", "K3_anchor_margin"}),
    # A dropped -1 in C6's clearance work: RT times the cleared amount (about 1e-3 fmol in the
    # world), against R-energy.
    ("c6_minus_one", {"C10_C6_reference"}),
    ("c11_trajectory", {"C11_trajectory"}),
])
def test_each_planted_error_fails_its_own_criterion(plant, expected):
    p = parts()
    if plant == "refusal_check":
        p["C1_refusals"]["classes"]["R4_an_ion_route"]["refused"][0]["check"] = "refusal 5"
    elif plant == "identity":
        p["C2_identity"]["pairs"]["pair 2"] = ["binding layout.x"]
    elif plant == "c3_off":
        p["C3_flux"]["series"]["amount_S_ecs_0"][50] *= 1 + 1e-9
    elif plant == "c3_reconciliation":
        p["C3_first_order"]["series"]["moved_load_fmol"][40] += 1e-12
    elif plant == "first_order":
        _rungs(p, "C4", order=1)
        p["references"]["step_map"] = {n: step_map_of(p[n], dt)
                                       for n, dt in generator.C4_RUNGS.items()}
    elif plant == "c4_too_large":
        _rungs(p, "C4", error=1e-5)
        p["references"]["step_map"] = {n: step_map_of(p[n], dt)
                                       for n, dt in generator.C4_RUNGS.items()}
    elif plant == "step_map_off":
        p["references"]["step_map"]["C4_rung_0p5ms"]["series"]["amount_S_ecs_0"][30] *= 1 + 1e-9
    elif plant == "splitting":
        ref = p["references"]["step_map"]["C4_rung_0p25ms"]
        ref["x_eq"] = ref["x_star"] / (1 + 1.01 * (-A * (A + 2 * B) * 2.5e-4**2 / 96.0))
    elif plant == "c5_off":
        p["C5_saturable"]["series"]["amount_S_cell_0"][10] *= 1 + 1e-8
    elif plant == "cleared_off":
        p["references"]["worlds"]["C6"]["series"]["cleared_ecs_0_fmol"][20] += 1e-5
    elif plant == "s1":
        p["C9_silence"]["programs"]["vector_window"]["s1"] = False
    elif plant == "s2":
        p["C9_silence"]["programs"]["batch"]["s2"] = 1.5
    elif plant == "not_live":
        p["C9_silence"]["programs"]["rk4"]["max_phi_owner"] = 0.01
    elif plant == "work_off":
        p["C3_flux"]["series"]["work_load_pJ"][60] *= 1 + 1e-6
    elif plant == "rk4_energy":
        p["C10_rk4"]["series"]["ratio_energy"][100] = 1.2
    elif plant == "imex_energy":
        s = p["C3_first_order"]["series"]
        s["energy_residual_pJ"] = [3e-3 * f for f in s["energy_flows_pJ"]]
    elif plant == "c11":
        p["C11_saturable_import_rk4"]["series"]["ratio_energy"][3] = 1.1
    elif plant == "ledger":
        p["C8_rung_0p25ms"]["series"]["ratio_outside"][7] = 2.0
    elif plant == "restart":
        p["C12_restart"]["restarts"]["0.5 snapshot"] = dict(equal=False)
    elif plant == "batch_relative":
        p["C12_batch"]["worlds"]["world_3"]["scalar_relative"] = 1e-11
    elif plant == "batch_reversed":
        p["C12_batch"]["worlds"]["world_2"]["reversed_equal"] = False
    elif plant == "k1_close":
        p["K1_one_way"] = engine("C4", 1e-3, routes=("load", "release"))
    elif plant == "k2_close":
        p["K2_no_clearance"] = engine("C6", 1e-3)
    elif plant == "k4":
        p["C12_restart"]["planted"] = dict(equal=True)
    elif plant == "move_wrong_ledger":
        p["C13_controls"]["plants"]["move"]["engine"]["message"] = "accounting failed: total"
    elif plant == "move_prefix":
        p["C13_controls"]["plants"]["move"]["prefix_max_ratio"]["outside"] = 1.5
    elif plant == "move_cytosol":
        p["C13_controls"]["plants"]["move"]["planted_ratios"]["local"] = 2.0
    elif plant == "work_margin":
        p["C13_controls"]["plants"]["work"]["planted_ratios"]["energy"] = 1.06
    elif plant == "work_material":
        p["C13_controls"]["plants"]["work"]["planted_ratios"]["outside"] = 1.2
    elif plant == "route_row0":
        p["K3_planted"]["plants"]["route"]["s1_rows"][0] = False
    elif plant == "route_margin":
        p["K3_planted"]["plants"]["route"]["s2_rows"][7] = 5.0
    elif plant == "anchor_row":
        p["K3_planted"]["plants"]["anchor"]["s2_rows"][3] = 0.5
    elif plant == "c6_minus_one":
        ref = p["references"]["energy"][D["C10"]["c6_part"]]
        ref["dG_pJ"] = [g + judge.RT_PJ_PER_FMOL * 1e-3 * (1 - math.exp(-t))
                        for g, t in zip(ref["dG_pJ"], ref["record_s"], strict=True)]
    elif plant == "c11_trajectory":
        p["references"]["energy"]["C11_first_order_import_rk4"]["series"][
            "amount_S_ecs_0"][50] *= 1 + 1e-9
    found = set(failed(p))
    assert expected <= found and found <= expected | {"C0_admission"}, found


def test_undefined_values_fail_through_none():
    p = parts()
    del p["references"]
    assert {"C3_loading", "C5_saturable", "C4_C8_reference", "C4_step_map", "C4_splitting_term",
            "K1", "K2"} <= set(failed(p))


def test_the_free_energy_is_appendix_a10s_form():
    part = dict(series=dict(amount_S_cell_0=[1e-3], amount_S_ecs_0=[1e-7]),
                volumes_pL=dict(cell_0=1.0, ecs_0=0.1))
    rt = 8.314462618 * 310.0 * 1e-3  # R T in pJ/fmol (R = N_A k_B, exact to 9 digits)
    want = rt * (1e-3 * (math.log(1e-3) - 1) + 1e-7 * (math.log(1e-6) - 1))
    assert judge.free_energy(part, 0) == pytest.approx(want, rel=1e-9)


# ------------------------------------------------------------------ the drafter and registration


def test_the_checked_in_judge_section_is_the_drafters():
    assert PROTOCOL["judge"] == json.loads(json.dumps(drafter.judge_section()))
    assert PROTOCOL["judged_parts"] == list(generator.PARTS)


def proposed():
    data = {k: v for k, v in PROTOCOL.items() if k != "registration"}
    if not data["status"].startswith("PROPOSED"):
        data["status"] = "PROPOSED (a test copy)"
    return data


def test_registration_takes_the_records_status_and_keeps_every_other_leaf(tmp_path):
    path, record = tmp_path / "p.json", tmp_path / "r.json"
    path.write_text(json.dumps(proposed()))
    before = json.loads(path.read_text())
    record.write_text(json.dumps(dict(status="PROPOSED again")))
    with pytest.raises(SystemExit, match="must begin 'registered'"):
        drafter.register(path, record)
    record.write_text(json.dumps(dict(status="registered by the lead (a test)", by="the lead")))
    after = drafter.register(path, record)
    assert after["registration"] == dict(status=after["status"], by="the lead")
    assert list(after)[list(after).index("status") + 1] == "registration"
    assert {k: v for k, v in after.items() if k not in ("status", "registration")} == {
        k: v for k, v in before.items() if k != "status"}


def test_draft_refuses_a_registered_protocol_and_changes_no_byte(tmp_path):
    path, record = tmp_path / "p.json", tmp_path / "r.json"
    path.write_text(json.dumps(proposed()))
    record.write_text(json.dumps(dict(status="registered by the lead (a test)")))
    drafter.register(path, record)
    before = path.read_bytes()
    with pytest.raises(SystemExit, match="only a PROPOSED protocol"):
        drafter.draft(path)
    assert path.read_bytes() == before


# ------------------------------------------------------------------ the generator's guards


def registered_copy(tmp_path):
    data = proposed()
    data["status"] = "registered (a test)"
    data["registration"] = dict(status=data["status"])
    path = tmp_path / "registered.json"
    path.write_text(json.dumps(data))
    return path


def test_the_judged_entry_refuses_before_writing_anything(tmp_path, monkeypatch):
    out = tmp_path / "out"
    unregistered = tmp_path / "proposed.json"
    unregistered.write_text(json.dumps(proposed()))
    with pytest.raises(SystemExit, match="not registered"):
        generator.main(["judged", str(unregistered), str(out), "C3_flux"])
    with pytest.raises(SystemExit, match="clean execution snapshot"):
        generator.main(["judged", str(registered_copy(tmp_path)), str(out), "C3_flux"])
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "SNAPSHOT.json").write_text(json.dumps(dict(
        status="complete", patch_sha256=hashlib.sha256(b"").hexdigest())))
    monkeypatch.setattr(generator, "judged_run_refusal", lambda protocol, root=snapshot: None)
    assert generator.STAND_INS == {}  # The references, C13's and K3's plants are all built.
    with pytest.raises(SystemExit, match="no quick horizon"):
        generator.main(["judged", str(registered_copy(tmp_path)), str(out), "C3_flux",
                        "--quick"])
    out.mkdir()
    with pytest.raises(SystemExit, match="exists"):
        generator.main(["judged", str(registered_copy(tmp_path)), str(out), "C3_flux"])
    assert not any(out.iterdir())


def test_the_refusal_classifier_names_every_check_once():
    labels = [check for check, _ in generator.CHECKS]
    assert len(labels) == len(set(labels))
    assert set(drafter.C1_CHECKS.values()) <= set(labels)
    assert generator.classify("an unrelated message") is None
    for check, phrase in generator.CHECKS:
        assert generator.classify(f"... {phrase} ...") == check
