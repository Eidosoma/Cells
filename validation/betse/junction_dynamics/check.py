"""Decimal gate equations plus native lifecycle and observer-neutrality checks."""

from decimal import Decimal, localcontext

import numpy as np


def rates(voltage, p):
    with localcontext() as context:
        context.prec = 65
        v = Decimal(str(abs(voltage))) * 1000 - Decimal(str(p["gj_vthresh_mV"]))
        alpha = Decimal("0.0013") * (-Decimal("0.077") * v).exp()
        raw = Decimal("0.0013") * (Decimal("0.14") * v).exp()
        return alpha, raw / (1 + 50 * raw)


def expected(voltage, old, block, dt, p, *, initial=False):
    with localcontext() as context:
        context.prec = 65
        a, b = rates(voltage, p)
        minimum = Decimal(str(p["gj_min"]))
        value = (
            a / (a + b) + minimum
            if initial
            else (Decimal(str(old)) + Decimal(str(dt)) * 1000 * (a + b * minimum))
            / (1 + Decimal(str(dt)) * 1000 * (a + b))
        )
        return float(Decimal(str(block)) * value)


def instantaneous(voltage, block, p):
    with localcontext() as context:
        context.prec = 65
        v, threshold, gradient = (
            Decimal(str(x)) for x in (voltage * 1000, p["gj_vthresh_mV"], p["gj_vgrad_mV"])
        )
        value = -1 / (1 + ((v + threshold) / gradient).exp()) + 1 / (
            1 + ((v - threshold) / gradient).exp()
        )
        return float(Decimal(str(p["gj_min"])) + Decimal(str(block)) * value)


def check(panel):
    p = panel["protocol"]
    tol = p["tolerances"]
    comparisons, maximum = 0, 0.0

    def agree(actual, target):
        nonlocal comparisons, maximum
        np.testing.assert_allclose(actual, target, rtol=tol["gate_rtol"], atol=tol["gate_atol"])
        comparisons += np.asarray(actual).size
        maximum = max(maximum, float(np.max(np.abs(np.asarray(actual) - target))))

    expected_contact = {
        (cls, dt, gate)
        for cls in ("Gap_Junction", "Gap_Junction_i")
        for dt in p["probe_dt_s"]
        for gate in p["probe_initial_gates"]
    }
    assert {
        (r["class"], r["dt_s"], r["initial_gate"]) for r in panel["primitives"]
    } == expected_contact
    assert len(panel["primitives"]) == len(expected_contact)
    for row in panel["primitives"]:
        dynamic = row["class"] == "Gap_Junction"
        volts = p["probe_voltage_V"]
        if dynamic:
            agree(row["sim_after_init"], row["initial_gate"])
            agree(row["class_after_init"], [expected(v, 0, 1, 0, p, initial=True) for v in volts])
        else:
            agree(row["sim_after_init"], [instantaneous(v, 1, p) for v in volts])
        assert [r["block"] for r in row["updates"]] == p["probe_block_schedule"]
        last = row["sim_after_init"]
        for update in row["updates"]:
            np.testing.assert_array_equal(update["before"], last)
            target = [
                expected(v, old, update["block"], row["dt_s"], p)
                if dynamic
                else instantaneous(v, update["block"], p)
                for v, old in zip(volts, update["before"], strict=True)
            ]
            agree(update["after"], target)
            if update["block"] == 0:
                agree(update["after"], 0.0 if dynamic else p["gj_min"])
            last = update["after"]
    pairs = []
    for order in p["orders"]:
        for block in p["blocks"]:
            rows = [r for r in panel["lifecycles"] if r["order"] == order and r["block"] == block]
            assert len(rows) == 2 and {r["observed"] for r in rows} == {False, True}
            bare, observed = sorted(rows, key=lambda r: r["observed"])
            assert bare["final"] == observed["final"], "Observer changed native trajectory"
            assert all(r["profile_hook_restored"] and r["native_pickle_present"] for r in rows)
            calls = observed["gate_calls"]
            assert len(calls) == observed["steps"] * len(order)
            assert len(observed["initializations"]) == 1
            init = observed["initializations"][0]
            np.testing.assert_array_equal(init["sim_before"], init["sim_after"])
            blocks = np.broadcast_to(init["block"], np.shape(init["sim_before"]))
            agree(
                init["class_after"],
                [
                    expected(v, 0, b, 0, p, initial=True)
                    for v, b in zip(init["voltage_V"], blocks, strict=True)
                ],
            )
            for step in range(observed["steps"]):
                local = [r for r in calls if r["step"] == step]
                assert [r["species_index"] for r in local] == observed["fixture"]["moving_ions"]
                for index, call in enumerate(local):
                    assert call["parent"] == "update_gj"
                    assert call["dt_s"] == observed["dt_s"]
                    if index:
                        np.testing.assert_array_equal(
                            call["sim_before"], local[index - 1]["sim_after"]
                        )
                    b = np.broadcast_to(call["block"], np.shape(call["sim_before"]))
                    agree(
                        call["sim_after"],
                        [
                            expected(v, old, block, call["dt_s"], p)
                            for v, old, block in zip(
                                call["voltage_V"], call["sim_before"], b, strict=True
                            )
                        ],
                    )
                    agree(call["alpha"], [float(rates(v, p)[0]) for v in call["voltage_V"]])
                    agree(call["beta"], [float(rates(v, p)[1]) for v in call["voltage_V"]])
            pairs.append(
                {
                    "order": order,
                    "block": block,
                    "steps": observed["steps"],
                    "gate_calls": len(calls),
                    "calls_per_outer_step": len(order),
                    "gate_dt_per_outer_dt": len(order),
                    "observer_neutral": True,
                }
            )
    assert len(panel["lifecycles"]) == len(pairs) * 2
    return {
        "status": "native_dynamic_junction_law_and_lifecycle_pass",
        "pairs": pairs,
        "scalar_comparisons": comparisons,
        "max_abs_equation_error": maximum,
        "dynamic_initialization_updates_sim_gate": False,
        "dynamic_block_scales_stored_gate": True,
        "instantaneous_block_retains_minimum": True,
        "max_dynamic_class_initial_gate": max(
            max(r["class_after_init"]) for r in panel["primitives"] if r["class"] == "Gap_Junction"
        ),
        "max_instantaneous_initial_gate": max(
            max(r["sim_after_init"]) for r in panel["primitives"] if r["class"] == "Gap_Junction_i"
        ),
        "production_gate_promoted": False,
        "scope": (
            "Pinned BETSE source behavior; no physical-time equivalence or biological validation"
        ),
    }
