"""Preparation software tests. Synthetic ledgers are not native evidence."""

import copy
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pump_check as check
import pump_context as ctx
import pump_job as job
import pytest
from pump_observer import PumpLoopObserver


def plan():
    return ctx.c.read(ctx.PROTOCOL)


@pytest.mark.parametrize("index", range(6))
def test_registered_variants(index):
    p = plan()
    ctx.validate_protocol(p)
    assert p["variants"][index]["id"]
    assert p["native_runs"] == 12 and p["observed_steps"] == 48


def test_changed_protocol_rejected():
    p = plan()
    p["steps"] += 1
    with pytest.raises(ValueError, match="Protocol changed"):
        ctx.validate_protocol(p)


def test_prerequisites_are_authenticated():
    assert set(ctx.prerequisites()) == {"family", "pump_source_contact"}


@pytest.mark.parametrize(
    "open_boundary,expected", [(True, [1.0, 2.0, 3.0]), (False, [1.0, 0.0, 3.0])]
)
def test_boundary_mask(open_boundary, expected):
    values = [1.0, 2.0, 3.0]
    assert check.masked(values, {"cluster_open": open_boundary}, [1]) == expected
    assert values == [1.0, 2.0, 3.0]


@pytest.mark.parametrize("bad", [[float("nan")], [1.1], [1.0, 2.0]])
def test_numeric_failures(bad):
    with pytest.raises(ValueError):
        check.near(bad, [1.0], 1e-12, 1e-11)


def synthetic_row(variant):
    """Hand-constructed constant-density transfer ledger with native-shaped axes."""
    p = plan()
    geometry = {k: ctx.c.read(ctx.GEOMETRY)[k] for k in ctx.GEOMETRY_FIELDS}
    geometry.update(effective_bath_volume_m3=6.75e-15, boundary_faces=[0, 4, 8, 12, 16, 20])
    settings = dict.fromkeys(
        (
            "is_ecm",
            "cell_polarizability",
            "alpha_Ca",
            "Ca_dyn",
            "molecules_enabled",
            "grn_enabled",
            "fluid_flow",
            "deformation",
            "deform_osmo",
            "dynamic_noise",
            "channel_noise_level",
            "v_sensitive_gj",
            "gj_surface",
        ),
        0,
    )
    settings.update(
        solver="FULL",
        cluster_open=variant["cluster_open"],
        alpha_NaK=p["alpha_mol_per_m2_s"] if variant["pump"] else 0,
        constants=p["constants"],
        temperature_K=p["temperature_K"],
        pump_parameters=p["pump_parameters"],
    )
    moving = [0, 1, 2]
    steps, raws = [], []
    inside, outside = [[100.0] * 7 for _ in range(6)], [[100.0] * 30 for _ in range(6)]
    for index in range(8):
        density = [[0.0] * 30 for _ in range(6)]
        calls = []
        reported = [0.0] * 30
        if variant["pump"]:
            calls.append(
                dict(function="pumpNaKATP", returned=[[-3e-7] * 30, [2e-7] * 30, [3e-7] * 30])
            )
            reported = [3e-7] * 30
            density[0] = [-3e-7 * variant["rho_pump"]] * 30
            density[1] = [2e-7 * variant["rho_pump"]] * 30
        for s in moving:
            passive = [1e-8 * (s + 1) if variant["leak"] else 0.0] * 30
            calls.append(dict(function="electroflux", species_index=s, returned=passive))
            density[s] = [x + y for x, y in zip(density[s], passive, strict=True)]
        if not variant["cluster_open"]:
            for species in density:
                for face in geometry["boundary_faces"]:
                    species[face] = 0.0
        before = dict(
            physical=dict(
                inside_mM=copy.deepcopy(inside),
                outside_mM=copy.deepcopy(outside),
                ordinary_density_mol_per_m2_s=density,
                junction_density_mol_per_m2_s=[[0.0] * 30 for _ in range(6)],
            ),
            reported_NaK_rate=reported,
        )
        for s in range(6):
            total = 0.0
            for face, owner in enumerate(geometry["membrane_owners"]):
                delta = density[s][face] * geometry["membrane_areas_m2"][face] * p["dt_s"]
                inside[s][owner] += delta / geometry["cell_volumes_m3"][owner]
                total += delta
            outside[s] = [
                value - total / geometry["effective_bath_volume_m3"] for value in outside[s]
            ]
        after = dict(
            physical=dict(inside_mM=copy.deepcopy(inside), outside_mM=copy.deepcopy(outside))
        )
        steps.append(
            dict(
                index=index,
                before_elapsed_s=index * p["dt_s"],
                after_elapsed_s=(index + 1) * p["dt_s"],
                order=["before_ordinary", "after_ordinary", "after_voltage"],
                before_ordinary=before,
                after_ordinary=after,
            )
        )
        raws.append(dict(index=index, calls=calls))
    return dict(
        id=variant["id"],
        dt_s=p["dt_s"],
        steps=8,
        phase="INIT",
        geometry=geometry,
        settings=settings,
        fixture_hook=dict(calls=1, returns=1),
        hook_restored=True,
        fixture=dict(before=dict(physical={}), after=dict(physical={})),
        metadata=dict(species=["Na", "K", "Cl", "Ca", "P", "M"]),
        moving_ions=moving,
        sodium_index=0,
        potassium_index=1,
        trace=dict(
            steps=steps, raw_steps=raws, calls=dict(loop=1), inflight_calls=0, hook_restored=True
        ),
    )


@pytest.mark.parametrize("index", range(6))
def test_synthetic_transfers(index):
    p = plan()
    v = p["variants"][index]
    checked = check.check_row(p, v, synthetic_row(v))
    assert len(checked) == 8
    assert all(r["raw_rate_is_atp"] is False for r in checked)


@pytest.mark.parametrize("kind", ["stoichiometry", "rate_label", "density", "bath_volume", "clock"])
def test_corrupted_ledgers_fail(kind):
    p = plan()
    v = p["variants"][0]
    row = synthetic_row(v)
    if kind == "stoichiometry":
        row["trace"]["raw_steps"][0]["calls"][0]["returned"][1][0] *= 2
    elif kind == "rate_label":
        row["trace"]["steps"][0]["before_ordinary"]["reported_NaK_rate"][0] /= 3
    elif kind == "density":
        row["trace"]["steps"][0]["before_ordinary"]["physical"]["ordinary_density_mol_per_m2_s"][0][
            0
        ] *= 2
    elif kind == "bath_volume":
        row["geometry"]["effective_bath_volume_m3"] /= 30
    else:
        row["trace"]["steps"][0]["after_elapsed_s"] = 0.0
    with pytest.raises(ValueError):
        check.check_row(p, v, row)


def test_source_scoped_probe_does_not_mutate_inputs(monkeypatch):
    phase = SimpleNamespace(sim=SimpleNamespace(molecules=None), p=SimpleNamespace())
    observer = PumpLoopObserver(phase, Path("/unit-test/science"), lambda _: {}, lambda _: None)
    observer.loop_frame = SimpleNamespace(f_locals={"i": 0})
    data = {k: [1.0, 2.0] for k in ("cA", "cB", "Dc", "d", "zc", "vBA", "T", "rho")}
    original = copy.deepcopy(data)
    frame = SimpleNamespace(
        f_code=SimpleNamespace(co_name="electroflux", co_filename=observer.toolbox),
        f_back=observer.loop_frame,
        f_locals=data,
    )
    observer.observe(frame, "call", None)
    monkeypatch.setattr("pump_observer.old.successful_return", lambda _: True)
    observer.observe(frame, "return", [3.0, 4.0])
    assert data == original
    assert observer.raw_steps[0]["calls"][0]["returned"] == [3.0, 4.0]
    assert observer.inflight == {}


def test_foreign_probe_ignored():
    phase = SimpleNamespace(sim=SimpleNamespace(molecules=None), p=SimpleNamespace())
    observer = PumpLoopObserver(phase, Path("/unit-test/science"), lambda _: {}, lambda _: None)
    observer.loop_frame = object()
    frame = SimpleNamespace(
        f_code=SimpleNamespace(co_name="electroflux", co_filename=observer.toolbox),
        f_back=object(),
        f_locals={},
    )
    observer.observe(frame, "call", None)
    assert observer.raw_steps == []


def test_failed_software_receipt_rejected(tmp_path, monkeypatch):
    directory = tmp_path / "reports"
    directory.mkdir()
    receipt = directory / "bad.xml"
    receipt.write_text('<testsuites><testsuite tests="16" failures="1"/></testsuites>')
    monkeypatch.setattr(ctx.c, "ROOT", tmp_path)
    with pytest.raises(ValueError):
        job.receipt(receipt)


def test_environment_disables_thread_oversubscription():
    env = job.environment()
    assert env["OPENBLAS_NUM_THREADS"] == "1" and "PYTHONPATH" not in env


def test_actual_native_configuration_load_only(tmp_path):
    """Load every declared YAML in the pinned environment; no seed or time loop."""
    code = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import pump_context as ctx
from betse.science.parameters import Parameters
from ruamel.yaml import YAML
p = ctx.c.read(ctx.PROTOCOL)
y = YAML(typ='safe'); y.default_flow_style = False
with (ctx.c.SOURCE/'betse/data/yaml/sim_config.yaml').open() as stream:
    template = y.load(stream)
for v in p['variants']:
    directory = Path(sys.argv[2])/v['id']; directory.mkdir()
    path = directory/'native.yaml'
    with path.open('x') as stream:
        y.dump(ctx.configuration(template,p,v,directory),stream)
    native = Parameters(); native.load(str(path))
    assert native.alpha_NaK == (p['alpha_mol_per_m2_s'] if v['pump'] else 0)
    assert native.T == p['temperature_K']
    assert native.molecules_enabled is False and native.is_ecm is False
    assert {k:getattr(native,k) for k in p['pump_parameters']} == p['pump_parameters']
assert not any(n == 'cells' or n.startswith('cells.') for n in sys.modules)
"""
    result = subprocess.run(
        [str(ctx.c.REFERENCE_PYTHON), "-B", "-c", code, str(ctx.HERE), str(tmp_path)],
        cwd=ctx.c.ROOT,
        env=job.environment(),
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
