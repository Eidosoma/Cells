"""Bounded saved-case and reduction tests; never rerun a native phase or trajectory."""

import ast
import copy
import importlib
import json
import math
import random
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ctx = importlib.import_module("review_context")
mix = importlib.import_module("review_math")
checker = importlib.import_module("review_check")
old = importlib.import_module("release_check")
job = importlib.import_module("review_job")


@pytest.fixture(scope="module")
def evidence():
    return ctx.c.read(ctx.CAPTURE / "registration.json"), ctx.c.read(ctx.CAPTURE / "betse.json")


def saved(evidence, key="a/dt_2.5e-05/baseline/query_0", mode="observed"):
    r, native = evidence
    row = ctx.io.read_compressed(ctx.CAPTURE / native["records"][key][mode])
    group = "/".join(key.split("/")[:2])
    physics = r["data"][row["history"]]["preparation_registration"]["transport_protocol"]
    return r, row, native["preparations"][group], checker.Ledger(physics["tolerances"])


def test_plan_and_source_contract():
    plan = ctx.c.read(ctx.PLAN)
    ctx.validate_plan(plan)
    assert plan["zero_flux_mean_rows"] == 288 * 6 + 48
    assert plan["capture_files"] == 605
    assert ctx.reduction_sources()["git_revision"] == "dd88c0c19b54ad9ed3533224221285bf0873249a"


@pytest.mark.parametrize(
    "field",
    [
        "captured_values_changed",
        "physical_tolerances_changed",
        "simulators_rerun",
        "reference_integrator_rerun",
        "production_changed",
        "release_response_qualified",
        "biology_validated",
        "gpu_tested",
        "automatic_polling",
        "automatic_retry",
        "automatic_followup",
    ],
)
def test_expanded_review_scope_rejected(field):
    plan = ctx.c.read(ctx.PLAN)
    plan[field] = True
    with pytest.raises(ValueError):
        ctx.validate_plan(plan)


@pytest.mark.parametrize(
    "field,value",
    [
        ("capture_files", 604),
        ("saved_single_updates", 144),
        ("zero_flux_mean_rows", 1728),
        ("mean_extent", 29),
        ("original_failure_preserved", False),
        ("extra", 0),
    ],
)
def test_changed_panel_rejected(field, value):
    plan = ctx.c.read(ctx.PLAN)
    plan[field] = value
    with pytest.raises(ValueError):
        ctx.validate_plan(plan)


def test_all_failed_capture_sources_and_artifacts_authenticate_without_models():
    code = (
        f"import sys; sys.path.insert(0,{str(HERE)!r})\n"
        "import review_context as c\n"
        "with c.model_fence():\n"
        " r,n,h=c.load_capture()\n"
        " assert len(h)==605 and len(r['sources_sha256'])==165\n"
        " import review_math,review_check\n"
        "print('authenticated_without_models')\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", code], check=True, capture_output=True, text=True, timeout=25
    )
    assert result.stdout.strip() == "authenticated_without_models"


@pytest.mark.parametrize("name", ctx.previous.audit.FORBIDDEN)
def test_review_fence_rejects_model_imports(name):
    code = (
        f"import sys; sys.path.insert(0,{str(HERE)!r})\n"
        "import review_context as c\n"
        "try:\n"
        " with c.model_fence():\n"
        f"  __import__({name!r})\n"
        "except RuntimeError: print('blocked')\n"
        "else: raise AssertionError('model import was allowed')\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", code], check=True, capture_output=True, text=True, timeout=5
    )
    assert result.stdout.strip() == "blocked"


@pytest.mark.parametrize(
    "values",
    [
        [],
        [4.0] * 29,
        [4.0] * 31,
        [4] * 30,
        [True] * 30,
        [0.0] * 30,
        [-1.0] * 30,
        [float("nan")] * 30,
        [float("inf")] * 30,
        [5e-324] * 30,
    ],
)
def test_mean_rejects_wrong_layout_type_or_domain(values):
    with pytest.raises(ValueError):
        mix.mean30(values)


def test_source_order_mean_matches_pinned_installed_binary(evidence):
    vectors = [
        [value] * 30
        for value in (
            4.0,
            4.000002534737709,
            4.000000626861033,
            4.000000626861034,
            math.nextafter(4.0, 0.0),
            math.nextafter(4.0, math.inf),
        )
    ]
    rng = random.Random(20260915)
    vectors += [[rng.uniform(0.001, 200.0)] * 30 for _ in range(96)]
    vectors += [[rng.uniform(0.001, 200.0) for _ in range(30)] for _ in range(96)]
    code = (
        "import json,sys,numpy as np\n"
        "from numpy.version import git_revision\n"
        "rows=json.load(sys.stdin)\n"
        "values=[float(np.asarray(v,dtype=np.float64).mean()).hex() for v in rows]\n"
        "assert 'betse' not in sys.modules and 'cells' not in sys.modules\n"
        "print(json.dumps({'version':np.__version__,'revision':git_revision,'means':values}))\n"
    )
    result = subprocess.run(
        [str(ctx.c.REFERENCE_PYTHON), "-B", "-c", code],
        input=json.dumps(vectors),
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    answer = json.loads(result.stdout)
    origin = ctx.reduction_sources()
    assert answer["version"] == origin["installed_version"]
    assert answer["revision"] == origin["git_revision"]
    assert answer["means"] == [mix.mean30(v).hex() for v in vectors]
    assert len(vectors) == 198


def test_uniform_remixing_is_not_assumed_idempotent():
    a = 4.000000626861033
    b = mix.mean30([a] * 30)
    d = mix.mean30([b] * 30)
    assert b == 4.000000626861034
    assert d == 4.000000626861035
    assert b - a == d - b == math.ulp(a)


def test_checker_diff_is_limited_to_documented_source_operation_changes():
    before = ast.parse((ctx.previous.HERE / "release_check.py").read_text())
    after = ast.parse((HERE / "review_check.py").read_text())
    before.body.pop(0)
    after.body.pop(0)
    added_imports = [
        n
        for n in after.body
        if isinstance(n, ast.Import)
        and any(a.name == "review_math" and a.asname == "remix" for a in n.names)
    ]
    assert len(added_imports) == 1
    after.body.remove(added_imports[0])
    originals = {n.name: n for n in before.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    changed = {n.name: n for n in after.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    init = next(
        n for n in changed["Ledger"].body if isinstance(n, ast.FunctionDef) and n.name == "__init__"
    )
    assert [ast.unparse(n) for n in init.body[-2:]] == [
        "self.remix_records = []",
        "self.original_guard_rejections = []",
    ]
    del init.body[-2:]
    step = changed["step_metrics"]
    replacement = next(
        n
        for n in step.body
        if isinstance(n, ast.Expr)
        and ast.unparse(n.value).startswith("remix.check_zero_flux_boundaries(")
    )
    original_loop = next(
        n
        for n in originals["step_metrics"].body
        if isinstance(n, ast.For) and ast.unparse(n.iter) == "('after_network', 'after_ordinary')"
    )
    step.body[step.body.index(replacement)] = copy.deepcopy(original_loop)
    blocked = next(
        n for n in step.body if isinstance(n, ast.If) and ast.unparse(n.test) == "maximum == 0"
    )
    loop = next(n for n in blocked.body if isinstance(n, ast.For))
    assert ast.literal_eval(loop.iter) == ("inside_mM", "at_membrane_mM", "voltage_V")
    loop.iter.elts.insert(1, ast.Constant("outside_mM"))
    case = changed["case_metrics"]
    assert ast.unparse(case.body.pop(0)) == "remix.moving_ions(row['primed_numeric_inventory'])"

    class RemoveProgress(ast.NodeTransformer):
        count = 0

        def visit_Expr(self, node):
            if (
                isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "print"
            ):
                self.count += 1
                return None
            return node

    progress = RemoveProgress()
    progress.visit(changed["check"])
    assert progress.count == 1
    returned = changed["check"].body[-1].value.right
    extras = {"zero_flux_mean_evidence", "zero_flux_remixing", "original_guard_rejections"}
    assert extras <= {k.value for k in returned.keys}
    kept = [
        (k, v) for k, v in zip(returned.keys, returned.values, strict=True) if k.value not in extras
    ]
    returned.keys, returned.values = [k for k, _ in kept], [v for _, v in kept]
    assert ast.dump(after, include_attributes=False) == ast.dump(before, include_attributes=False)


@pytest.mark.parametrize(
    "key",
    [
        "a/dt_2.5e-05/baseline/query_0",
        "b/dt_1.25e-05/static_blocked/query_0",
        "b/dt_1.25e-05/suppression_release/query_2",
        "a/dt_6.25e-06/no_op/query_1",
    ],
)
@pytest.mark.parametrize("mode", ["observed", "unobserved"])
def test_saved_representative_cases_pass_without_data_changes(evidence, key, mode):
    r, row, prep, ledger = saved(evidence, key, mode)
    frozen = json.dumps(row, sort_keys=True, allow_nan=False)
    checker.case_metrics(r, row, prep, ledger, key + "/" + mode)
    assert ledger.failed == 0, ledger.failures[:4]
    assert ledger.count > 2000
    assert len(ledger.remix_records) in (12, 13)
    assert json.dumps(row, sort_keys=True, allow_nan=False) == frozen


def test_original_first_failure_remains_reproducible(evidence):
    r, row, prep, _ = saved(evidence)
    ledger = old.Ledger(
        r["data"]["a"]["preparation_registration"]["transport_protocol"]["tolerances"]
    )
    with pytest.raises(ValueError, match="double-transferred"):
        old.case_metrics(r, row, prep, ledger, "preserved_failure")


@pytest.mark.parametrize(
    "fault",
    [
        "one_more_ulp",
        "suppress_mean",
        "nonuniform",
        "cell",
        "membrane",
        "voltage_stage",
        "network",
        "ordinary_flux",
        "junction_flux",
        "moving_ions",
        "input_reset",
        "double_transfer",
    ],
)
def test_corruptions_still_rejected_including_a_single_extra_ulp(evidence, fault):
    r, row, prep, ledger = saved(evidence)
    original = copy.deepcopy(row)
    step = row["probe"]
    if fault in ("one_more_ulp", "suppress_mean"):
        value = (
            math.nextafter(step["after_ordinary"]["physical"]["outside_mM"][1][0], 0.0)
            if fault == "one_more_ulp"
            else step["after_channel"]["physical"]["outside_mM"][1][0]
        )
        for stage in ("after_ordinary", "after_voltage"):
            step[stage]["physical"]["outside_mM"][1] = [value] * 30
        row["final"]["physical"]["outside_mM"][1] = [value] * 30
    elif fault == "nonuniform":
        step["after_ordinary"]["physical"]["outside_mM"][1][0] += 1e-14
    elif fault == "cell":
        values = step["after_ordinary"]["physical"]["inside_mM"][1]
        values[0] = math.nextafter(values[0], math.inf)
    elif fault == "membrane":
        values = step["after_ordinary"]["physical"]["at_membrane_mM"][1]
        values[0] = math.nextafter(values[0], math.inf)
    elif fault == "voltage_stage":
        step["after_voltage"]["physical"]["outside_mM"][1][0] += 1e-14
    elif fault == "network":
        step["after_network"]["physical"]["outside_mM"][1][0] += 1e-14
    elif fault in ("ordinary_flux", "junction_flux"):
        field = ("ordinary" if fault == "ordinary_flux" else "junction") + "_density_mol_per_m2_s"
        step["after_network"]["physical"][field][1][0] = 1e-30
    elif fault == "moving_ions":
        row["primed_numeric_inventory"]["numeric"]["sim/movingIons/5"]["value"] = 0
    elif fault == "input_reset":
        row["applications"][0]["after"]["channel"]["m"][0] = 0.0
    else:
        step["after_ordinary"]["physical"]["inside_mM"][1][0] += 1e-6
        step["after_ordinary"]["physical"]["outside_mM"][1] = [4.0] * 30
    assert row != original, "Corruption fixture must actually change represented data"
    with pytest.raises(ValueError):
        checker.case_metrics(r, row, prep, ledger, "corrupted")


def test_exact_remix_must_still_fit_original_material_budget(evidence):
    _, _, prep, ledger = saved(evidence)
    g = copy.deepcopy(prep["geometry"])
    g["effective_bath_volume_m3"] = 1.0  # Synthetic enlarged bath, never a captured value.
    before = [4.000002534737709] * 30
    after = [mix.mean30(before)] * 30
    mix.remix_record("synthetic", "after_ordinary", 1, before, after, g, ledger)
    assert ledger.failed == 1
    assert ledger.failures[0]["unit"] == "amount_fmol"


def test_duplicate_mean_identity_is_rejected(evidence):
    _, _, prep, ledger = saved(evidence)
    before = [4.0] * 30
    mix.remix_record("x", "after_ordinary", 1, before, before, prep["geometry"], ledger)
    with pytest.raises(ValueError, match="Duplicate"):
        mix.remix_record("x", "after_ordinary", 1, before, before, prep["geometry"], ledger)


def test_existing_output_refused_before_capture_loading(tmp_path):
    with pytest.raises(ValueError, match="fresh"):
        job.register(tmp_path, tmp_path / "missing.xml")


def test_detached_launch_returns_without_poll_or_wait(tmp_path, monkeypatch):
    output = tmp_path / "review"
    output.mkdir()
    r = {"plan": ctx.c.read(ctx.PLAN)}
    ctx.io.write(output / "registration.json", r)
    monkeypatch.setattr(job, "register", lambda output, tests: r)
    calls = []

    def popen(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(pid=12345)

    monkeypatch.setattr(job.subprocess, "Popen", popen)
    receipt = job.launch(output, tmp_path / "unused.xml")
    assert receipt["status"] == "launched_detached"
    assert (
        receipt["automatic_polling"]
        is receipt["automatic_retry"]
        is receipt["automatic_followup"]
        is False
    )
    assert calls[0][1]["start_new_session"] is True
    assert "worker" not in calls[0][0]


def test_incomplete_software_receipt_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(ctx, "ROOT", tmp_path)
    path = tmp_path / "reports" / "empty.xml"
    path.parent.mkdir()
    path.write_text('<testsuite tests="0" failures="0" errors="0" skipped="0"/>')
    with pytest.raises(ValueError):
        ctx.test_receipt(path)


def test_no_pickle_loading_or_simulator_entrypoint_in_review_sources():
    for name in ("review_math.py", "review_check.py", "review_context.py", "review_job.py"):
        tree = ast.parse((HERE / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = ast.unparse(node.func)
                assert name not in {"pickle.load", "pickle.loads", "SimPhase", "SimRunner"}
                assert not name.endswith((".run_sim_core", ".single_update", ".run_loop_channels"))


def test_review_failure_is_durable_and_cannot_write_success(tmp_path, monkeypatch):
    from contextlib import nullcontext

    monkeypatch.setattr(ctx, "model_fence", nullcontext)
    monkeypatch.setattr(ctx, "authenticate", lambda output: {"capture_sha256": {}})
    monkeypatch.setattr(ctx, "load_capture", lambda: ({}, {}, {}))
    monkeypatch.setattr(job.resource, "setrlimit", lambda *args: None)
    monkeypatch.setattr(job.signal, "signal", lambda *args: None)
    monkeypatch.setattr(job.signal, "setitimer", lambda *args: None)
    monkeypatch.setattr(job.os, "sched_getaffinity", lambda pid: {0, 1, 2, 3})

    def reject(*args):
        raise ValueError("deliberate saved-evidence rejection")

    monkeypatch.setattr(checker, "check", reject)
    with pytest.raises(ValueError, match="deliberate"):
        job.execute(tmp_path)
    receipt = ctx.c.read(tmp_path / "failure.json")
    assert receipt["stage"] == "source_order_and_unchanged_physical_checks"
    assert receipt["simulators_rerun"] is receipt["automatic_retry"] is False
    assert not (tmp_path / "completion.json").exists()
