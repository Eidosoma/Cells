"""Real control/grid probes plus negative contract tests; no trajectory evidence."""

import copy
import math

import contact as c
import held_intervention as d
import held_intervention_context as ctx
import pytest
import trajectory_evidence as trajectory


@pytest.fixture(scope="module")
def plan():
    return c.read(d.PLAN)


@pytest.fixture(scope="module")
def native():
    return d.run_probe("native")


@pytest.fixture(scope="module")
def local():
    return d.run_probe("cells")


def test_qualified_predecessor_and_frozen_evidence_are_unchanged():
    result = ctx.preservation_check()
    assert result["baseline_files"] == 932
    assert result["expanded_capture_files_unchanged"] == 802
    assert result["expanded_audit_files_unchanged"] == 11
    assert result["accepted_implementation_files_unchanged"] == 352
    assert result["production_modules_unchanged"] == 51


def test_plan_separates_control_checks_from_future_pilot(plan):
    d.validate_plan(plan)
    pilot = plan["pilot"]
    assert pilot["native_runs"] == len(plan["conditions"]) * len(pilot["native_observer_modes"])
    assert pilot["cells_runs"] == len(plan["conditions"]) * 2 * len(plan["cells_subdivisions"])
    assert pilot["observed_native_steps"] == len(plan["conditions"]) * 40
    assert plan["trajectory_run"] is plan["trajectory_qualified"] is False


@pytest.mark.parametrize(
    "path,value",
    [
        (("status",), "registered"),
        (("trajectory_run",), True),
        (("trajectory_qualified",), True),
        (("controls_from_native_history",), True),
        (("relax_prior_tolerances",), True),
        (("continuous_waveform_qualified",), True),
        (("automatic_expansion",), True),
        (("duration_s",), 0.01),
        (("control_atol",), 1),
        (("control_atol",), float("nan")),
        (("control_error_scale",), "suppressed_residual"),
        (("terminal_control",), "evaluate_pulse_at_endpoint"),
        (("time_generation",), "rounded_decimal_times"),
        (("hold_policy",), "continuous_stage_evaluation"),
        (("cells_subdivisions",), [1, 1, 1]),
        (("cells_subdivisions",), [True, 2, 4]),
        (("pilot", "constant_profile"), "source_constants"),
        (("pilot", "hold_step_s"), 0.0001),
        (("pilot", "native_runs"), 6),
        (("pilot", "profiles_enabled"), False),
        (("pilot", "preparation"), "load_INIT_pickle"),
        (("criteria_source",), "different.json"),
    ],
)
def test_rejects_changed_scope_input_contract_and_overclaims(plan, path, value):
    changed = copy.deepcopy(plan)
    target = changed
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        d.validate_plan(changed)


@pytest.mark.parametrize("h", [0.000025, 0.0000125, 0.00000625])
@pytest.mark.parametrize("condition", d.CONDITIONS)
def test_compiled_controls_have_canonical_times_and_no_endpoint_event(plan, h, condition):
    schedule = d.held_schedule(plan, condition, h)
    n = int(plan["duration_s"] / h)
    assert len(schedule) == n
    assert [r["time"] for r in schedule] == [k * h for k in range(n)]
    assert schedule[-1]["time"] < plan["duration_s"]
    assert all(set(r["multipliers"]) == {"Na", "K", "Cl"} for r in schedule)
    assert all(len(set(r["multipliers"].values())) == 1 for r in schedule)
    values = [r["multipliers"]["Na"] for r in schedule]
    assert all(math.isfinite(v) and 0 <= v <= 1 for v in values)
    if condition == "suppression_recovery":
        assert 0 < min(values) < 1e-8
        assert 0 < values[0] < 1 and min(values) < values[-1] < 1
        q = c.read(d.law.PLAN)["candidate_pulse"]
        assert values[-1] != d.law.decimal_availability(plan["duration_s"], q)
    else:
        assert set(values) == {0.0 if condition == "static_blocked" else 1.0}


@pytest.mark.parametrize("condition", d.CONDITIONS)
@pytest.mark.parametrize("subdivision", [1, 2, 4])
@pytest.mark.parametrize("backend", ["jax_eager", "jax_jit"])
def test_definitions_only_change_controls_execution_and_observation_grid(
    plan, condition, subdivision, backend
):
    retained = trajectory.trusted_registration()["cells_definitions"][
        "passive/jax_eager/0.00010000"
    ]
    before = copy.deepcopy(retained)
    definition = d.cells_definition(plan, condition, 0.000025, subdivision, backend)
    assert definition["model"] == retained["model"]
    assert retained == before
    assert definition["execution"] == retained["execution"] | {
        "dt": 0.000025 / subdivision,
        "jit": backend == "jax_jit",
        "max_steps": 40 * subdivision,
    }
    assert len(definition["experiment"]["observation_times"]) == 41
    assert definition["experiment"]["channel_controls"] == []
    assert definition["experiment"]["junction_controls"] == []
    for changed, original in zip(
        definition["experiment"]["membrane_controls"],
        retained["experiment"]["membrane_controls"],
        strict=True,
    ):
        assert changed["pump"] == original["pump"]
        assert changed["membrane_id"] == original["membrane_id"]
    # Separate membrane records, not mutable aliases.
    controls = definition["experiment"]["membrane_controls"]
    controls[0]["leak"][0]["multipliers"]["Na"] = 42
    assert controls[1]["leak"][0]["multipliers"]["Na"] != 42


@pytest.mark.parametrize("h", [0, True, -1, 0.0001, float("inf")])
def test_schedule_rejects_unregistered_hold_steps(plan, h):
    with pytest.raises(ValueError):
        d.held_schedule(plan, "baseline", h)


@pytest.mark.parametrize("subdivision", [True, 0, 3, 4.0])
def test_compiler_rejects_unregistered_solver_subdivisions(plan, subdivision):
    with pytest.raises(ValueError):
        d.cells_definition(plan, "baseline", 0.000025, subdivision, "jax_eager")


def test_compiler_rejects_unknown_conditions_and_backends(plan):
    with pytest.raises(ValueError):
        d.held_schedule(plan, "almost_blocked", 0.000025)
    with pytest.raises(ValueError):
        d.cells_definition(plan, "baseline", 0.000025, 1, "gpu")


def test_real_native_pulse_and_additive_arithmetic_match_declared_inputs(plan, native):
    assert native["integration_calls"] == native["event_dispatch_calls"] == 0
    assert native["warnings"] == []
    assert native["plan_sha256"] == c.sha(d.PLAN)
    assert len(native["rows"]) == 12
    assert sum(row["steps"] for row in native["rows"]) == 1120
    for row in native["rows"]:
        assert row["maximum_baseline_scaled_error"] <= plan["control_atol"]
        assert len(row["effective_Dm_m2_per_s"]) == row["steps"]
        assert all(values[3:] == [0, 0, 0] for values in row["effective_Dm_m2_per_s"])


def test_noop_and_static_zero_are_exact_control_checks(native):
    for h in (0.000025, 0.0000125, 0.00000625):
        rows = {r["condition"]: r for r in native["rows"] if r["h_s"] == h}
        assert (
            rows["baseline"]["effective_Dm_m2_per_s"]
            == rows["zero_amplitude"]["effective_Dm_m2_per_s"]
        )
        assert all(v == [0] * 6 for v in rows["static_blocked"]["effective_Dm_m2_per_s"])
        assert all(v[0] > 0 for v in rows["suppression_recovery"]["effective_Dm_m2_per_s"])


def test_actual_cells_grids_refine_without_changing_hold_or_observation_side(local):
    assert local["integration_calls"] == 0 and local["trajectory_qualified"] is False
    assert local["plan_sha256"] == c.sha(d.PLAN)
    assert len(local["rows"]) == 36
    for row in local["rows"]:
        expected = round(0.001 / row["h_s"]) * row["subdivision"]
        assert row["integration_intervals"] == expected
        assert row["extra_sliver_intervals"] == 0
        assert all(a < b for a, b in zip(row["grid_s"], row["grid_s"][1:], strict=False))


def test_additive_source_contract():
    source = (c.SOURCE / "betse/science/tissue/tishandler.py").read_text()
    assert d.composition_contract(source) == {
        "merge": "scheduled_plus_base",
        "species": ["Na", "K", "Cl"],
    }


@pytest.mark.parametrize(
    "old,new",
    [
        ("sim.Dm_scheduled +", "sim.Dm_scheduled *"),
        ("self.mem_mult_Namem*effector_Na*self.tissue_default.Dm_Na", "effector_Na"),
    ],
)
def test_rejects_altered_native_composition(old, new):
    source = (c.SOURCE / "betse/science/tissue/tishandler.py").read_text()
    assert old in source
    with pytest.raises(ValueError):
        d.composition_contract(source.replace(old, new))


@pytest.mark.parametrize("module", sorted(d.FORBIDDEN))
def test_control_probe_fence_rejects_integration_entries(module):
    with pytest.raises(AssertionError, match="integration entry"):
        d.IntegrationFence().find_spec(module)
