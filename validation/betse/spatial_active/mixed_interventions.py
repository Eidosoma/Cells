"""Combined controls on the existing portable dynamic-junction fixture."""

import json
from pathlib import Path

import numpy as np

from validation.betse.spatial_active import junction_runtime, refinement

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_PATH = Path(__file__).with_name("mixed_protocol.json")


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def source_changes():
    """Permit declared validation edits while keeping every physical source fixed."""
    rule = protocol()
    root = Path(rule["prior_binding"]["root"])
    assert (
        refinement.digest(root / "registration.json")
        == rule["prior_binding"]["registration_sha256"]
    )
    registration = json.loads((root / "registration.json").read_text())
    changed = []
    for name, sha in registration["sources_sha256"].items():
        if refinement.digest(ROOT / name) != sha:
            assert name in rule["allowed_prior_source_changes"], name
            changed.append(name)
    assert set(changed) == set(rule["allowed_prior_source_changes"])
    assert not any(name.startswith("src/") for name in changed)
    production = {str(p.relative_to(ROOT)) for p in (ROOT / "src").rglob("*.py")}
    assert production == {n for n in registration["sources_sha256"] if n.startswith("src/")}
    return dict(
        status="passed",
        changed_validation_files=changed,
        unchanged_prior_files=len(registration["sources_sha256"]) - len(changed),
        unchanged_production_files=len(production),
        new_production_files=[],
    )


def baseline():
    binding = protocol()["prior_binding"]
    root = Path(binding["root"])
    assert refinement.digest(root / "completion.json") == binding["completion_sha256"]
    report = refinement.completed_prior(binding, current_root=ROOT)
    return source_changes() | dict(prerequisite=report)


def native_capture():
    """Reuse complete native pairs from the failed comparison, without rewriting it."""
    rule = protocol()
    binding = rule["native_capture_binding"]
    root = Path(binding["root"])
    for name in ("registration", "failure"):
        assert refinement.digest(root / (name + ".json")) == binding[name + "_sha256"]
    assert json.loads((root / "failure.json").read_text())["status"] == "failed"
    assert not (root / "completion.json").exists()
    registration = json.loads((root / "registration.json").read_text())
    assert refinement.digest(root / "component-protocol.json") == binding["protocol_sha256"]
    old = json.loads((root / "component-protocol.json").read_text())
    assert old == registration["component_protocol"]
    # All changes outside this explicit list are acceptance/harness metadata.
    for name in (
        "species",
        "base_concentration_mM",
        "concentration_gradient_mM",
        "outside_mM",
        "gj_surface_fraction",
        "initial_voltage_extent_V",
        "native_update_tolerances",
        "tolerances",
        "temperature_K",
        "initial_gate",
        "pump_parameters",
        "junction",
        "cases",
        "duration_s",
        "native_steps_s",
        "template",
        "template_sha256",
    ):
        assert rule[name] == old[name], "Changed native input: " + name
    path = root / "evidence/cpu/mixed-native"
    for name in ("completion", "panel"):
        assert refinement.digest(path / (name + ".json")) == binding[name + "_sha256"]
    rows = junction_runtime.authenticate_capture(path, old)
    return path, rows


def definition(case="coupled_block", index=0, *, backend="cpu"):
    rule = protocol()
    choices = {c["id"]: c for c in rule["cases"]}
    if case not in choices or index not in range(len(rule["native_steps_s"])):
        raise ValueError("Unknown mixed intervention case")
    assert refinement.digest(ROOT / rule["template"]) == rule["template_sha256"]
    raw = json.loads((ROOT / rule["template"]).read_text())
    owner = np.asarray(raw["model"]["tissue"]["cell_owner"])
    dt = rule["native_steps_s"][index]
    count = round(rule["duration_s"] / dt)
    changes = []
    for event in choices[case]["interventions"]:
        selected = (
            np.ones(owner.shape, bool)
            if event["target_cells"] == "all"
            else np.isin(owner, event["target_cells"])
        )
        changes.append(
            dict(
                time=round(event["time_s"] / dt) * dt,
                pump=np.where(selected, event["pump_fraction"], 1.0).tolist(),
                channel=np.where(selected, event["channel_fraction"], 1.0).tolist(),
                junction=np.full(owner.shape, float(event["junction_fraction"])).tolist(),
            )
        )
    raw["execution"].update(
        dt=dt, backend=backend, max_trace_bytes=rule["resources"]["scalar_max_trace_bytes"]
    )
    raw["experiment"] = dict(
        end_time=count * dt, observation_times=[i * dt for i in range(count + 1)], changes=changes
    )
    return raw
