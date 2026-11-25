"""fr3-site-occupancy-v1's tools on the host: the judge, the drafter and the guards (tier 1).

No engine run: synthetic records with known orders, budgets, energies and comparisons, laid out as
the references' registered worlds (their nodes and populations), exercise the judge's derivation
and every machine criterion, each with a planted error that must fail its own criterion; the
generator's judged entry refuses before writing anything; the drafter's section is the checked-in
one, and it refuses a registered protocol; registration takes the record's status and changes
nothing else; the refusal classifier names every check once; the plants' site free energy is
Appendix A.3's form. The tests are status-agnostic: registration changes the status and adds the
record alone.
"""

import copy
import hashlib
import json
import math

import pytest

from validation import id_table
from validation.tissue import site_occupancy_acceptance_fixtures as af
from validation.tissue import site_occupancy_acceptance_judge as judge
from validation.tissue import site_occupancy_acceptance_plants as plants
from validation.tissue import site_occupancy_acceptance_protocol as drafter
from validation.tissue import site_occupancy_acceptance_qualification as generator

PROTOCOL = id_table.load(generator.PROTOCOL)
D = drafter.derivation()
INPUTS = af.inputs()["worlds"]
RECORD_MS = list(range(0, 1001, 100))
RICCATI = {"q2_large", "q2_closed", "q3_association", "q3_dissociation", "q5_passive_from_zero",
           "q5_passive_preformed", *(w for w in INPUTS if w.startswith("q4_"))}
EQUILIBRIUM = RICCATI | {"q2_two_populations", "q3_binding_multiplier"}
QSS = {"q1_eps_1e-1": (0.1, 7.5e-2), "q1_eps_1e-2": (0.01, 8.0e-3),
       "q1_eps_1e-3": (0.001, 8.0e-4)}
EPS = 2.0**-52


def layout(world_id):
    w = INPUTS[world_id]
    cells = [n for n, v in w["nodes"].items() if v["kind"] == "cell"]
    finite = [n for n, v in w["nodes"].items() if v["kind"] == "finite_outside"]
    return w, cells, finite


def trajectories(world_id, *, bound_shift=None, internalised_shift=None):
    """A conserving trajectory per world: B_k = b_k (1 - e^-t), U_k = u_k t (internalised), the
    facing node losing B + U, the receiving cell gaining U; heat and work smooth. The shifts are
    functions of t added to B and U (moving the facing node and the cell to conserve)."""
    w, cells, finite = layout(world_id)
    series = {}
    amounts = {n: w["nodes"][n]["L_mM"] * w["nodes"][n]["volume_pL"] for n in (*cells, *finite)}
    t_s = [t * 1e-3 for t in RECORD_MS]
    for name in amounts:
        series[f"amount_{name}"] = [amounts[name]] * len(t_s)
    internalising = False
    for p in w["populations"]:
        pid, f = p["id"], p["owner"]["faces_node"]
        s = p["accessible_fraction"] * 1e-4
        b = [0.1 * s * (1 - math.exp(-t)) + (bound_shift(t) if bound_shift else 0.0)
             for t in t_s]
        u = [(1e-6 * t + (internalised_shift(t) if internalised_shift else 0.0))
             if p["internalisation"] else 0.0 for t in t_s]
        internalising |= p["internalisation"] is not None
        series[f"B_{pid}"], series[f"R_{pid}"] = b, [s - x for x in b]
        series[f"internalised_{pid}"] = u
        series[f"amount_{f}"] = [x - y - z for x, y, z in zip(series[f"amount_{f}"], b, u,
                                                                strict=True)]
        if p["internalisation"]:
            r = p["owner"]["cell"]
            series[f"amount_{r}"] = [x + z for x, z in zip(series[f"amount_{r}"], u, strict=True)]
    series["heat_pJ"] = [1e-5 * (1 - math.exp(-t)) for t in t_s]
    series["work_pJ"] = [-1e-5 * t if internalising else 0.0 for t in t_s]
    return series


def reference_of(world_id):
    w, cells, finite = layout(world_id)
    series = trajectories(world_id)
    for name in list(series):
        series["floor_" + name] = [1e-20] * len(RECORD_MS)
    pops = [p["id"] for p in w["populations"]]
    out = dict(record_ms=list(RECORD_MS), series=series, nodes=sorted(w["nodes"]),
               populations=pops,
               sites_fmol={p["id"]: p["accessible_fraction"] * 1e-4 for p in w["populations"]},
               volumes_pL={n: v["volume_pL"] for n, v in w["nodes"].items()},
               facing={p["id"]: p["owner"]["faces_node"] for p in w["populations"]})
    if world_id in RICCATI:
        (pid,) = pops
        node = out["facing"][pid]
        out["riccati"] = dict(population=pid, node=node, record_ms=list(RECORD_MS),
                              series={f"B_{pid}": list(series[f"B_{pid}"]),
                                      f"amount_{node}": list(series[f"amount_{node}"])},
                              B_eq_fmol=series[f"B_{pid}"][-1])
    if world_id in EQUILIBRIUM:
        node = sorted(set(out["facing"].values()))[0]
        out["equilibrium"] = dict(
            c_mM=series[f"amount_{node}"][-1] / out["volumes_pL"][node],
            B_fmol={p: series[f"B_{p}"][-1] for p in pops},
            heat_to_equilibrium_pJ=series["heat_pJ"][-1])
    if world_id in QSS:
        eps, error = QSS[world_id]
        out["qss"] = dict(epsilon=eps, relative_error_over_uptake=error)
    return out


def engine_of(world_id, *, dt=1e-3, bound_shift=None, internalised_shift=None,
              heat_shift=None, arm=None):
    """An engine record of a world: its trajectory with the shifts, every check at a small
    fraction of its bound."""
    w, cells, finite = layout(world_id)
    s_world = sum(p["accessible_fraction"] * 1e-4 for p in w["populations"])
    small = 0.01 * drafter.F_STATE * s_world
    shift = bound_shift or (lambda t: small)
    series = trajectories(world_id, bound_shift=shift, internalised_shift=internalised_shift)
    t_s = [t * 1e-3 for t in RECORD_MS]
    if heat_shift is not None:
        series["heat_pJ"] = [h + heat_shift(t) for h, t in zip(series["heat_pJ"], t_s,
                                                                 strict=True)]
    facing = w["populations"][0]["owner"]["faces_node"]
    for n in (*cells, *finite):
        series[f"heat_{n}_pJ"] = (list(series["heat_pJ"]) if n == facing
                                  else [0.0] * len(RECORD_MS))
    steps = [max(1, round(t * 1e-3 / dt)) for t in RECORD_MS]
    series["energy_magnitude_pJ"] = [1e-3] * len(RECORD_MS)
    series["energy_residual_pJ"] = [0.1 * drafter.CLOSURE_ROUNDING * EPS * n * 1e-3
                                    for n in steps]
    for name in [*drafter.LEDGERS, "energy"]:
        series[f"ratio_{name}"] = [0.01] * len(RECORD_MS)
    pops = [p["id"] for p in w["populations"]]
    return dict(kind="engine", admitted=True, completed=True, refusal=None, dt_s=dt,
                steps=round(1.0 / dt), record_ms=list(RECORD_MS),
                record_s=[t * 1e-3 for t in RECORD_MS], series=series, cells=cells,
                finite_nodes=finite, populations=pops, ligand_floor_fmol=1e-20,
                ids=list(drafter.ENGINE_IDS[:7]), arm=arm or world_id)


def ladder_rung(dt, order=3, energy_order=2):
    c, ce = 1e-11 / 1e-3**order, 1e-10 / 1e-3**energy_order
    return engine_of(af.LADDER_WORLD, dt=dt,
                     bound_shift=lambda t: c * dt**order * (1 - math.exp(-t)),
                     internalised_shift=lambda t: c * dt**order * (1 - math.exp(-t)),
                     heat_shift=lambda t: ce * dt**energy_order * (1 - math.exp(-t)))


def prefix_record(world_id="q5_passive_from_zero"):
    record = engine_of(world_id)
    return {k: v for k, v in record.items() if k not in ("kind", "admitted", "completed")}


def plant(kind, checks, passing, *, planted=None, engine=None):
    prefix = prefix_record("q1_eps_1e-1" if kind == "work" else "q5_passive_from_zero")
    row = {k: v[-1] for k, v in prefix["series"].items()}
    row.update(planted or {})
    return dict(plant=dict(kind=kind, checks=checks, passing=passing), prefix=prefix,
                planted=dict(record_ms=1000, step=1000, series=row),
                engine=engine or dict(refused=False, message=None))


def allowance(steps=1000, magnitude=1e-3):
    return drafter.CLOSURE_ROUNDING * EPS * steps * magnitude


def scaled(world_id, factor):
    """An engine record whose B is `factor` times the world's own (the facing node conserving)."""
    s = INPUTS[world_id]["populations"][0]["accessible_fraction"] * 1e-4
    small = 0.01 * drafter.F_STATE * s
    return engine_of(world_id, bound_shift=lambda t: (factor - 1) * 0.1 * s * (1 - math.exp(-t))
                     + factor * small)


def parts():
    out = {w: engine_of(w) for w in generator.WORLD_PARTS}
    for name, dt in generator.LADDER_PARTS.items():
        out[name] = ladder_rung(dt)
    refs = {w: reference_of(w) for w in INPUTS}
    out["references"] = dict(kind="reference", admitted=True, completed=True, worlds=refs)

    def far(world_id, **kw):  # A control run far from its arm's reference.
        s_world = sum(p["accessible_fraction"] * 1e-4 for p in INPUTS[world_id]["populations"])
        return engine_of(world_id, bound_shift=lambda t: 1e3 * drafter.F_STATE * s_world, **kw)

    def control(runs):
        return dict(kind="engine_set", admitted=True, completed=True, runs=runs)

    out["K_rates"] = control({k: far(af.LADDER_WORLD) for k in ("k_on", "k_off", "k_int")})
    out["K_alpha"] = control({"alpha_ignored": far("q1_eps_1e-1_alpha_half")})
    out["K_binding_multiplier"] = control({m: far("q3_binding_multiplier")
                                           for m in ("ignored", "squared")})
    out["K_internalisation_multiplier"] = control({"ignored": far("q5_class_switch")})
    work_far = engine_of("q1_eps_1e-1", arm="q1_eps_1e-1")
    work_far["series"]["work_pJ"] = [x - 1e-7 * t for x, t in zip(
        work_far["series"]["work_pJ"], RECORD_MS, strict=True)]
    out["K_cell_volume"] = control({"q5_inward": far("q5_inward"), "q1_eps_1e-1": work_far})
    kinetic, affinity = {}, {}
    for regime in ("low", "high"):
        one = f"q4_alpha_1_{regime}"
        for alpha in (0.5, 0.25):
            key = f"{regime}_{alpha:g}"
            kinetic[key] = engine_of(one)  # (K): the equilibrium unchanged, ratio 1.
            factor = 0.99 if regime == "high" else alpha * (1 + 2.5e-3 / alpha)
            affinity[key] = scaled(one, factor)
    out["Q4_kinetic"], out["Q4_affinity"] = control(kinetic), control(affinity)
    big = 1e3 * allowance()
    out["Q5_material_plants"] = dict(kind="plants", admitted=True, completed=True, plants=dict(
        move=plant("move", ["ledger:outside"], ["local"], planted=dict(ratio_outside=1e6),
                   engine=dict(refused=True, message="Resolved pump accounting failed: outside")),
        bound=plant("bound", ["ledger:site_bound_entity"], ["local", "outside", "total"],
                    planted=dict(ratio_site_bound_entity=1e6), engine=dict(
                        refused=True, message="Site occupancy accounting failed: "
                        "site_bound_entity"))))
    energy_passing = ["local", "outside", "total", "site_bound_entity", "site_moiety_entity"]
    out["Q5_energy_plants"] = dict(kind="plants", admitted=True, completed=True, plants=dict(
        work=plant("work", ["closure"], energy_passing, planted=dict(energy_residual_pJ=big)),
        heat_sign=plant("heat_sign", ["closure", "dissipation"], energy_passing,
                        planted=dict(energy_residual_pJ=big, heat_ecs_0_pJ=-1e-5)),
        site_free_energy=plant("site_free_energy", ["closure", "dissipation"], energy_passing,
                               planted=dict(energy_residual_pJ=big, heat_ecs_0_pJ=-2e-5))))
    out["Q6_restart"] = dict(kind="comparison", admitted=True, completed=True, restarts={
        f"{t:g} {m}": dict(equal=True) for t in generator.RESTART_TIMES_S
        for m in ("in_process", "snapshot")}, planted=dict(equal=False))
    out["Q6_batch"] = dict(kind="comparison", admitted=True, completed=True, worlds={
        f"world_{i}": dict(scalar_relative=0.0, scalar_bitwise=True, reversed_equal=True,
                           final_reversed_equal=True)
        for i in range(1, len(generator.BATCH_VARIANTS) + 1)})
    out["Q6_idle"] = dict(kind="idle", admitted=True, completed=True, zero_multipliers=[],
                          no_populations=[], zero_world_fields_moved=[],
                          no_populations_statically_idle=True)
    out["Q6_twins"] = dict(kind="twins", admitted=True, completed=True,
                           programs={k: dict(text_equal=True, constants_equal=True)
                                     for k in ("step", "rhs", "checks")},
                           bindings_same_names_dtypes_shapes=True,
                           bindings_differing=["layout.site_on_rate"])
    out["Q6_signature"] = dict(kind="signature", admitted=True, completed=True, cases={
        "internalisation_differs": dict(refused=True, message="A batch requires matching model "
                                        "array axes; use separate batches"),
        "facing_differs": dict(refused=True, message="A batch requires matching model array "
                               "axes; use separate batches"),
        "same_structure": dict(refused=False, message=None)})
    classes = {}
    for cls, check in generator.EXPECTED_CHECKS.items():
        refused = (dict(refused=True, admitted=True, message="m", check=None) if check is None
                   else dict(refused=True, message="m", check=check))
        classes[cls] = dict(refused=[refused], admitted=[dict(admitted=True, ran=True,
                                                              needs_run=True, message=None)])
    out["Q6_refusals"] = dict(kind="refusals", admitted=True, completed=True, classes=classes)
    return out


def failed(p):
    _, evaluated = judge.verdict(p, PROTOCOL)
    return sorted(c["id"] for c in evaluated["criteria"] if c["judged"] and not c["passed"])


# ------------------------------------------------------------------ the judge


def test_a_complete_run_passes_every_criterion():
    assert failed(parts()) == []


def _conserving(world_id, delta, t_index=5):
    """A world's B raised by delta at one record, its facing node lowered (the total kept)."""
    def shift(t):
        return delta if abs(t - RECORD_MS[t_index] * 1e-3) < 1e-12 else 0.0
    return engine_of(world_id, bound_shift=shift)


def s_world_of(world_id):
    return sum(p["accessible_fraction"] * 1e-4 for p in INPUTS[world_id]["populations"])


@pytest.mark.parametrize("plant_name, expected", [
    ("state_q2", {"Q2_state"}),
    ("state_q1", {"Q1_state"}),
    ("state_q5", {"Q5_state"}),
    ("energy_q3", {"Q3_energy"}),
    ("work_in_a_passive_world", {"Q2_energy"}),
    ("second_order", {"Q1_order_amount_cell_0", "Q1_order_amount_ecs_0", "Q1_order_B_r0"}),
    ("riccati", {"Q3_riccati"}),
    ("equilibrium", {"Q2_equilibrium"}),
    ("quadratic", {"Q2_quadratic"}),
    ("heat_to_equilibrium", {"Q2_heat_to_equilibrium"}),
    ("q4_ratio", {"Q4_ratio", "Q4_state", "Q3_riccati"}),  # q4 worlds carry Riccati.
    ("q4_kinetic_close", {"Q4_K"}),
    ("q4_affinity_close", {"Q4_A"}),
    ("closure", {"Q5_closure"}),
    ("heat_falls", {"Q5_heat"}),
    ("ledger", {"Q5_ledgers"}),
    ("total", {"Q5_system_total"}),
    ("background", {"Q5_background"}),
    ("move_wrong_ledger", {"Q5_plants_material_engine"}),
    ("move_prefix", {"Q5_plant_move"}),
    ("bound_margin", {"Q5_plant_bound_margin"}),
    ("work_margin", {"Q5_plant_work_margin"}),
    ("work_material", {"Q5_plant_work"}),
    ("heat_sign_positive", {"Q5_plant_heat_sign"}),
    ("site_free_energy_prefix", {"Q5_plant_site_free_energy"}),
    ("k_rates_close", {"K_rates"}),
    ("alpha_close", {"K_alpha"}),
    ("multiplier_close", {"K_binding_multiplier"}),
    ("internalisation_multiplier_close", {"K_internalisation_multiplier"}),
    ("cell_volume_work_close", {"K_cell_volume"}),
    ("restart", {"Q6_restart"}),
    ("k4", {"K4"}),
    ("batch_relative", {"Q6_batch_scalar"}),
    ("batch_reversed", {"Q6_batch_reversed"}),
    ("idle", {"Q6_idle"}),
    ("not_statically_idle", {"Q6_idle"}),
    ("twins", {"Q6_twins"}),
    ("twins_identical_values", {"Q6_twins"}),
    ("signature", {"Q6_signature"}),
    ("refusal_check", {"Q6_refusals"}),
    ("runtime_refusal", {"Q6_refusals"}),
    ("ids", {"C0_ids"}),
])
def test_each_planted_error_fails_its_own_criterion(plant_name, expected):
    p = parts()
    budget_q2 = drafter.F_STATE * s_world_of("q2_two_populations")
    if plant_name == "state_q2":
        p["q2_two_populations"] = _conserving("q2_two_populations", 2 * budget_q2)
    elif plant_name == "state_q1":
        p["q1_eps_1e-2"] = _conserving("q1_eps_1e-2", 2 * drafter.F_STATE
                                       * s_world_of("q1_eps_1e-2"))
    elif plant_name == "state_q5":
        p["q5_inward"] = _conserving("q5_inward", 2 * drafter.F_STATE * s_world_of("q5_inward"))
    elif plant_name == "energy_q3":
        p["q3_internalisation"]["series"]["heat_pJ"][4] += 2 * drafter.F_ENERGY * 1e-5
    elif plant_name == "work_in_a_passive_world":
        p["q2_large"]["series"]["work_pJ"][3] = 1e-15
    elif plant_name == "second_order":
        for name, dt in generator.LADDER_PARTS.items():
            p[name] = ladder_rung(dt, order=2)
    elif plant_name == "riccati":
        p["references"]["worlds"]["q4_alpha_1_low"]["riccati"]["series"]["B_r0"][6] *= 1.01
    elif plant_name == "equilibrium":
        p["references"]["worlds"]["q2_large"]["equilibrium"]["B_fmol"]["r0"] *= 1.01
    elif plant_name == "quadratic":
        p["references"]["worlds"]["q2_closed"]["riccati"]["B_eq_fmol"] *= 1.01
    elif plant_name == "heat_to_equilibrium":
        p["references"]["worlds"]["q2_two_populations"]["equilibrium"][
            "heat_to_equilibrium_pJ"] *= 1.01
    elif plant_name == "q4_ratio":
        world = "q4_alpha_1_2_high"
        b = 0.1 * 0.5e-4
        p[world] = engine_of(world, bound_shift=lambda t: 4e-3 * b * (1 - math.exp(-t)))
    elif plant_name == "q4_kinetic_close":
        p["Q4_kinetic"]["runs"]["high_0.5"] = scaled("q4_alpha_1_high", 0.5)
    elif plant_name == "q4_affinity_close":
        p["Q4_affinity"]["runs"]["high_0.25"] = scaled("q4_alpha_1_high", 0.25)
    elif plant_name == "closure":
        p["q5_washout"]["series"]["energy_residual_pJ"][7] = 2 * allowance(700)
    elif plant_name == "heat_falls":
        s = p["q2_closed"]["series"]["heat_ecs_0_pJ"]
        s[6] = s[5] - 2 * allowance(600)
    elif plant_name == "ledger":
        p["q3_association"]["series"]["ratio_outside"][4] = 2.0
    elif plant_name == "total":
        p["q5_passive_preformed"]["series"]["amount_cell_0"][8] += 1e-12
    elif plant_name == "background":
        world = "q5_background_lowered"
        budget = drafter.F_STATE * s_world_of(world)
        p[world] = engine_of(world, internalised_shift=lambda t: 0.2 * budget * t)
    elif plant_name == "move_wrong_ledger":
        p["Q5_material_plants"]["plants"]["move"]["engine"]["message"] = \
            "Resolved pump accounting failed: total"
    elif plant_name == "move_prefix":
        p["Q5_material_plants"]["plants"]["move"]["prefix"]["series"]["ratio_outside"][3] = 1.5
    elif plant_name == "bound_margin":
        p["Q5_material_plants"]["plants"]["bound"]["planted"]["series"][
            "ratio_site_bound_entity"] = 5.0
    elif plant_name == "work_margin":
        p["Q5_energy_plants"]["plants"]["work"]["planted"]["series"][
            "energy_residual_pJ"] = 5 * allowance()
    elif plant_name == "work_material":
        p["Q5_energy_plants"]["plants"]["work"]["planted"]["series"]["ratio_outside"] = 1.2
    elif plant_name == "heat_sign_positive":
        p["Q5_energy_plants"]["plants"]["heat_sign"]["planted"]["series"]["heat_ecs_0_pJ"] = 1e-5
    elif plant_name == "site_free_energy_prefix":
        p["Q5_energy_plants"]["plants"]["site_free_energy"]["prefix"]["series"][
            "energy_residual_pJ"][4] = 2 * allowance(400)
    elif plant_name == "k_rates_close":
        p["K_rates"]["runs"]["k_int"] = engine_of(af.LADDER_WORLD)
    elif plant_name == "alpha_close":
        p["K_alpha"]["runs"]["alpha_ignored"] = engine_of("q1_eps_1e-1_alpha_half")
    elif plant_name == "multiplier_close":
        p["K_binding_multiplier"]["runs"]["squared"] = engine_of("q3_binding_multiplier")
    elif plant_name == "internalisation_multiplier_close":
        p["K_internalisation_multiplier"]["runs"]["ignored"] = engine_of("q5_class_switch")
    elif plant_name == "cell_volume_work_close":
        p["K_cell_volume"]["runs"]["q1_eps_1e-1"] = engine_of("q1_eps_1e-1")
    elif plant_name == "restart":
        p["Q6_restart"]["restarts"]["5 snapshot"] = dict(equal=False)
    elif plant_name == "k4":
        p["Q6_restart"]["planted"] = dict(equal=True)
    elif plant_name == "batch_relative":
        p["Q6_batch"]["worlds"]["world_3"]["scalar_relative"] = 1e-11
    elif plant_name == "batch_reversed":
        p["Q6_batch"]["worlds"]["world_2"]["reversed_equal"] = False
    elif plant_name == "idle":
        p["Q6_idle"]["zero_multipliers"] = ["amount_increment"]
    elif plant_name == "not_statically_idle":
        p["Q6_idle"]["no_populations_statically_idle"] = False
    elif plant_name == "twins":
        p["Q6_twins"]["programs"]["rhs"]["text_equal"] = False
    elif plant_name == "twins_identical_values":
        p["Q6_twins"]["bindings_differing"] = []
    elif plant_name == "signature":
        p["Q6_signature"]["cases"]["internalisation_differs"] = dict(refused=False, message=None)
    elif plant_name == "refusal_check":
        p["Q6_refusals"]["classes"]["held_bath"]["refused"][0]["check"] = "unknown patch"
    elif plant_name == "runtime_refusal":
        p["Q6_refusals"]["classes"]["stage_condition"]["refused"][0]["refused"] = False
    elif plant_name == "ids":
        p["q3_dissociation"]["ids"] = [*p["q3_dissociation"]["ids"], "rk4"]
    found = set(failed(p))
    assert expected <= found and found <= expected | {"C0_admission"}, found


def test_undefined_values_fail_through_none():
    p = parts()
    del p["references"]
    assert {"Q1_state", "Q2_equilibrium", "Q3_riccati", "Q1_order_B_r0", "K_rates",
            "C0_admission"} <= set(failed(p))


def test_an_incomplete_part_fails_admission():
    p = parts()
    p["q2_large"]["completed"] = False
    assert "C0_admission" in failed(p)


def test_a_passive_world_books_exactly_no_work():
    p = parts()
    assert judge.energy_ratio(p["q2_large"], p["references"]["worlds"]["q2_large"], "work_pJ",
                              drafter.F_ENERGY) == 0.0


def test_the_background_guard_reads_changes_from_t0():
    """The t = 0 difference is the declared trace content (the lead's ruling 2): a constant
    offset between the two worlds moves no change."""
    p = parts()
    derived, _ = judge.verdict(p, PROTOCOL)
    # The two worlds' declared trace contents differ (1e-9 against 1e-12 fmol in 1 pL).
    assert derived["background"]["absolute_fmol"]["amount_ecs_0"] == pytest.approx(9.99e-10)
    assert derived["background"]["ratio"] == pytest.approx(0.0, abs=1e-12)
    world = p["q5_background_lowered"]
    world["series"]["amount_ecs_0"] = [x + 3e-9 for x in world["series"]["amount_ecs_0"]]
    derived, _ = judge.verdict(p, PROTOCOL)
    assert derived["background"]["ratio"] == pytest.approx(0.0, abs=1e-12)


def test_every_criterion_metric_resolves_on_a_complete_run():
    """No metric path is broken (a key with a dot would be split by the evaluator): every
    criterion, judged or reported, reads a defined value from a complete run."""
    _, evaluated = judge.verdict(parts(), PROTOCOL)
    undefined = [c["id"] for c in evaluated["criteria"] if any(v is None for v in c["values"])]
    assert undefined == []


def test_the_orders_are_third_order_on_the_synthetic_ladder():
    derived, _ = judge.verdict(parts(), PROTOCOL)
    for x in D["order_observables"]:
        assert all(o == pytest.approx(3.0, abs=1e-6) for o in derived["orders"][x]["orders"])
    assert all(o == pytest.approx(2.0, abs=1e-3) for o in derived["orders"]["heat_pJ"]["orders"])


def test_the_plants_site_free_energy_is_appendix_a3s_form():
    rt = 1e-3 * 6.02214076e23 * 1.380649e-23 * 310.0
    b, r, s, k_d = 3e-6, 1.6e-4 - 3e-6, 1.6e-4, 1e-3
    want = b * (rt * math.log(k_d) + rt * math.log(b / s)) + rt * r * math.log(r / s)
    assert plants.site_free_energy_pJ(b, r, s, k_d, 310.0) == pytest.approx(want, rel=1e-12)
    assert plants.site_free_energy_pJ(0.0, s, s, k_d, 310.0) == 0.0  # 0 ln 0 = 0, the empty pool.


def test_the_inputs_blob_is_gits():
    data = b"hello\n"
    assert generator.git_blob(data) == "ce013625030ba8dba906f756967f9e9ca394464a"


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
        generator.main(["judged", str(unregistered), str(out), "q2_large"])
    # A source tree without SNAPSHOT.json (the test may itself run from a snapshot, as a gate's).
    monkeypatch.setattr(generator, "ROOT", tmp_path / "checkout")
    with pytest.raises(SystemExit, match="clean execution snapshot"):
        generator.main(["judged", str(registered_copy(tmp_path)), str(out), "q2_large"])
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "SNAPSHOT.json").write_text(json.dumps(dict(
        status="complete", patch_sha256=hashlib.sha256(b"").hexdigest())))
    monkeypatch.setattr(generator, "judged_run_refusal", lambda protocol, root=snapshot: None)
    assert generator.STAND_INS == {}  # The references, the plants and Q6 are all built.
    with pytest.raises(SystemExit, match="no quick horizon"):
        generator.main(["judged", str(registered_copy(tmp_path)), str(out), "q2_large",
                        "--quick"])
    with pytest.raises(SystemExit, match="unknown or no parts"):  # A development part.
        generator.main(["judged", str(registered_copy(tmp_path)), str(out),
                        next(iter(generator.DEV_PARTS))])
    out.mkdir()
    with pytest.raises(SystemExit, match="exists"):
        generator.main(["judged", str(registered_copy(tmp_path)), str(out), "q2_large"])
    assert not any(out.iterdir())


def test_the_refusal_classifier_names_every_check_once():
    labels = [check for check, _ in generator.CHECKS]
    assert len(labels) == len(set(labels))
    assert {c for c in generator.EXPECTED_CHECKS.values() if c} <= set(labels)
    assert generator.classify("an unrelated message") is None
    for check, phrase in generator.CHECKS:
        assert generator.classify(f"... {phrase} ...") == check


def test_every_judged_part_has_its_function_and_unit():
    assert set(generator.PARTS) <= set(generator.FUNCTIONS)
    assert set(PROTOCOL["judge"]["units"]) == set(generator.PARTS)
    assert not set(generator.DEV_PARTS) & set(generator.PARTS)
    assert copy.deepcopy(D["run_parts"]) == list(generator.PARTS)
