"""validation/stationary/judge.py on a small synthetic results set.

The synthetic run passes every pre-registered criterion of
stationary_analysis_e_v1; moving one fold outside its budget fails exactly
E3.3 (and the verdict), and a missing field makes only the criteria that need
it "not evaluable" (verdict incomplete). The judgement file is never
overwritten.
"""

import copy
import json

import pytest

from validation.stationary import judge

P_LAW = dict(kind="closed_species_total", species="P", nodes=["cell_0"])


def record(classification="stable", unstable=0):
    return dict(
        converged=True,
        method="newton",
        last_correction=1e-12,
        error_estimate=1e-13,
        newton_history=[dict(iteration=1, step=1e-12, damping=1.0)],
        consistency=dict(
            rhs=dict(correction=1e-14),
            step_map_1=dict(correction=1e-9, rounding_floor=1e-8),
            step_map_2=dict(correction=5e-10, rounding_floor=1e-8),
        ),
        stability=dict(
            classification=classification,
            unstable_count=unstable,
            marginal_count=0,
            eigenvalues_per_s=[[-1.0, 0.0], [-2.0, 0.0], [-3.0, 0.0]],
            neutral_directions=[dict(P_LAW)],
        ),
    )


def comparison(v=-0.08):
    errors = dict(vm_V=1e-15, Na=1e-14, K=1e-13, M=1e-14)
    jac = [[-1.0, 0.0, 0.0], [0.0, -2.0, 0.0], [0.0, 0.0, -3.0]]
    return dict(
        engine_error_estimate=dict(errors),
        reference_error_estimate=dict(errors),
        reference_vm_V=v,
        reference_composition_mM=dict(Na=6.0, K=136.0, M=7.0),
        engine_minus_reference=dict(vm_V=1e-15, Na=0.0, K=1e-13, M=0.0),
        budget=dict(vm_V=1.0, Na=1.0, K=1.0, M=1.0),
        adiabatic_jacobian_engine=jac,
        adiabatic_jacobian_reference=jac,
        adiabatic_jacobian_reference_error=[[1e-10] * 3] * 3,
        adiabatic_eigenvalue_budget=[1.0, 1.0, 1.0],
    )


AGREEMENT = dict(max_u_difference=1e-9, floor=1e-8)


def fold(u):
    return dict(
        kind="fold",
        parameter_value=u,
        parameter_error_estimate=1e-10,
        augmented_sigma_min_relative=1e-4,
        jacobian_sigma_min_relative=1e-17,
        unstable_count=0,
    )


def results():
    heredity_states = {}
    for k, v in (("H", -0.0796), ("U", -0.0394), ("D", -0.0215)):
        unstable = k == "U"
        heredity_states[k] = dict(
            rhs=record("unstable" if unstable else "stable", int(unstable)),
            rhs_cell=dict(vm_V=v),
            theory_comparison=comparison(v),
            step_map_agreement=dict(AGREEMENT),
        )
    fast = dict(H=-0.0595, U=-0.0402, D=-0.0243)
    mg0b_states = {
        k: dict(
            converged=True,
            state=dict(membrane_voltage_V=dict(membrane_0=v)),
            engine_error_V=1e-16,
            reference_error_V=1e-15,
            budget_V=1.0,
            stability=dict(
                classification="unstable" if k == "U" else "stable",
                unstable_count=int(k == "U"),
            ),
        )
        for k, v in fast.items()
    }
    voltages = dict(membrane_0=-0.024, membrane_1=-0.059)
    return dict(
        default=dict(
            rhs=record(),
            step_map_agreement=dict(AGREEMENT),
            theory_states=[dict(vm_V=-0.006)],
            theory_comparison=comparison(-0.006),
            prescreen_comparison=dict(vm_mV=1e-6),
        ),
        heredity=dict(states=heredity_states),
        mg0b=dict(
            theory_fast_states_recomputed_V=list(fast.values()),
            theory=dict(fast_states_V=dict(fast)),
            states=mg0b_states,
            continuation=dict(
                points=[dict(tangent_parameter_component=0.5)],
                special_points=[fold(0.6794), fold(0.3771)],
                termination="parameter_bound",
                bounds=[0.0, 1.0],
            ),
            theory_window_refined=[dict(u=0.3771, error=1e-14), dict(u=0.6794, error=1e-14)],
            theory_window_grid=[0.3771 + 1e-8, 0.6794 - 1e-8],
            theory_grid_miss_bound=[1e-7, 1e-7],
        ),
        tissue=dict(
            fast_mg0b=dict(
                start=dict(
                    record(),
                    parameter_value=0.01,
                    state=dict(membrane_voltage_V=voltages),
                    disc=dict(d_cells_inside=7, d_cells_outside=0),
                ),
                reference=dict(
                    state_V=list(voltages.values()),
                    correction_V=1e-16,
                    leading_rate_per_s=-2.5,
                    fold_coupling=0.1,
                    fold_error=1e-8,
                    fold_budget=1.0,
                    within_budget=True,
                ),
                continuation=dict(
                    points=[
                        dict(tangent_parameter_component=0.5, unstable_count=0),
                        dict(tangent_parameter_component=-0.1, unstable_count=1),
                    ],
                    special_points=[fold(0.1 + 1e-9)],
                    termination="parameter_bound",
                ),
            ),
            slow_heredity=dict(
                start=dict(
                    record(),
                    parameter_value=0.01,
                    disc=dict(d_cells_inside=7, d_cells_outside=0),
                ),
                continuation=dict(
                    special_points=[dict(kind="hopf", parameter_value=0.07)],
                    termination="parameter_bound",
                    points=[],
                ),
            ),
        ),
        default_run=dict(runner_probe="refused: electrode", final_distance_mM=5.8e-4),
    )


def write(tmp_path, data):
    directory = tmp_path / "results"
    directory.mkdir()
    for part, value in data.items():
        (directory / f"{part}.json").write_text(json.dumps(value))
    return directory


def outcomes(result):
    return {c["id"]: c["outcome"] for c in result["criteria"]}


def test_synthetic_run_passes_every_criterion(tmp_path):
    result = judge.judge(write(tmp_path, results()))
    assert result["verdict"] == "pass", [c for c in result["criteria"] if c["outcome"] != "pass"]
    protocol = json.loads(judge.PROTOCOL.read_text())["criteria"]
    judged = sorted(k for g in protocol.values() for k in g if k.startswith("E") and k != "E4.3")
    assert sorted(outcomes(result)) == judged
    assert result["reported_not_judged"]["values"]["E4.3"]["first_special_point"]["kind"] == "hopf"
    assert result["diagnostics"]["D1"]["runner_probe"].startswith("refused")


def test_a_fold_outside_its_budget_fails_only_e3_3(tmp_path):
    data = results()
    folds = data["mg0b"]["continuation"]["special_points"]
    folds[0] = fold(0.6794 - 1e-8)  # budget 10 x (1e-10 + 1e-14) = 1e-9; still inside the grid
    result = judge.judge(write(tmp_path, data))
    failed = {k for k, v in outcomes(result).items() if v == "fail"}
    assert failed == {"E3.3"} and result["verdict"] == "fail"


def test_missing_fields_are_not_evaluable(tmp_path):
    data = copy.deepcopy(results())
    del data["heredity"]["states"]["U"]["theory_comparison"]
    result = judge.judge(write(tmp_path, data))
    states = outcomes(result)
    assert states["E2.2"] == states["E2.4"] == "not evaluable"
    assert all(v == "pass" for k, v in states.items() if k not in ("E2.2", "E2.4"))
    assert result["verdict"] == "incomplete"
    reasons = [c["reason"] for c in result["criteria"] if c["id"] == "E2.2"]
    assert "theory_comparison" in reasons[0]


def test_judgement_is_never_overwritten(tmp_path):
    directory = write(tmp_path, results())
    output = tmp_path / "judgement.json"
    assert judge.main([str(directory), "--output", str(output)]) == 0
    assert json.loads(output.read_text())["verdict"] == "pass"
    with pytest.raises(FileExistsError):
        judge.main([str(directory), "--output", str(output)])
