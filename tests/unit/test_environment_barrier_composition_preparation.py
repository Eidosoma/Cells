"""Full-owner barrier preparation, independent physical stages and portable CLI."""

import json
import os
import subprocess
import sys
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells import tissue_profiles
from cells.core import environment_barrier_composition_preparation as bridge
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, digest, parse_spec
from cells.models.registry import get_model
from validation.tissue import calcium_energy_water_hcn_extra_reference as water
from validation.tissue import calcium_energy_water_repair_hcn_extra_reference as repair
from validation.tissue import surface_calcium_energy_reference as energy
from validation.tissue import surface_calcium_reference as calcium
from validation.tissue import surface_kinetic_reference as ionic
from validation.transport import environment_barrier_composition_fixtures as fixtures

EQUATIONS = dict(ionic=ionic, calcium=calcium, energy=energy, water=water, repair=repair)


def evidence(name, report, arrays=None):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(folder) / "composed-environment-barriers"
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(
            json.dumps(report, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
        )
        if arrays is not None:
            np.savez_compressed(root / (name + ".npz"), **arrays)


@lru_cache
def prepared(family="repair", case="asymmetric_modulators"):
    permuted = case == "asymmetric_modulators"
    raw = fixtures.request(family, case, permuted=permuted, padded=permuted)
    return raw, tissue_profiles.prepare_request(raw)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ("asymmetric_modulators", "zero_endpoint"))
def test_full_state_preserved_and_before_after_physics_matches_independent_model(family, case):
    raw, result = prepared(family, case)
    untouched = deepcopy(raw)
    expected, coefficients = fixtures.independent_coefficients(raw)
    expected = parse_spec(expected).to_dict()
    actual = deepcopy(result.definition)
    leaf = actual["model"] if family == "ionic" else actual["model"]["ionic"]
    target = expected["model"] if family == "ionic" else expected["model"]["ionic"]
    for a, b in zip(leaf["faces"], target["faces"], strict=True):
        assert a["id"] == b["id"]
        for species, value in b["diffusivity_m2_per_s"].items():
            np.testing.assert_allclose(
                a["diffusivity_m2_per_s"][species], value, rtol=5e-14, atol=0
            )
        a["diffusivity_m2_per_s"] = b["diffusivity_m2_per_s"]
    assert actual == expected
    source = parse_spec(raw["definition"]).to_dict()
    restored = deepcopy(result.definition)
    old_leaf = source["model"] if family == "ionic" else source["model"]["ionic"]
    restored_leaf = restored["model"] if family == "ionic" else restored["model"]["ionic"]
    for a, b in zip(restored_leaf["faces"], old_leaf["faces"], strict=True):
        a["diffusivity_m2_per_s"] = b["diffusivity_m2_per_s"]
    assert restored == source
    inner = result.provenance["direct_parameter_preparation"]
    for group, values in coefficients.items():
        for species, owners in values.items():
            for owner, value in owners.items():
                np.testing.assert_allclose(
                    inner["coefficients"][group][species][owner], value, rtol=5e-14, atol=0
                )
    eq, stages, arrays, initial_states = EQUATIONS[family], [], {}, []
    for label, definition, reference in (
        ("before", source, source),
        ("after", result.definition, expected),
    ):
        spec = parse_spec(definition)
        model = get_model(spec.model)
        state, layout = model.initial_values(spec)
        initial_states.append(state)
        context = eq.bind(reference)
        assert set(context["shapes"]) == set(state._fields)
        np.testing.assert_array_equal(eq.flatten(context, state._asdict()), eq.initial(context))
        table = control_values(spec, [0.0])
        control = type(table)(*(v[0] for v in table))
        rates = model.rhs(state, control, layout, layout.active, xp=np)
        target_rates, target_potential, proof = eq.evaluate(context, eq.initial(context), 0.0)
        # Use the established physical root/conservation acceptance, including
        # when a nonlinear solver's progress flag alone is inconclusive.
        assert proof["max_charge_residual_C"] <= 3e-25
        assert proof["max_component_current_residual_A"] <= 1e-23
        for key in (
            "physical_energy_balance_pJ_s",
            "water_energy_balance_pJ_s",
            "injury_energy_balance_pJ_s",
        ):
            if key in proof:
                assert abs(proof[key]) <= 1e-10
        observed = eq.flatten(context, rates._asdict())
        budget = eq.flatten(
            context,
            {
                key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
                for key, shape in context["shapes"].items()
            },
        ) + 3e-10 * np.abs(target_rates)
        ratio = float(np.max(np.abs(observed - target_rates) / budget, initial=0))
        field = model.field_values(state, control, layout, xp=np)
        n = layout.active.size
        potential = np.r_[
            field.potential_V[:n][layout.active], field.potential_V[n:][layout.outside_active]
        ]
        np.testing.assert_allclose(potential, target_potential, rtol=3e-10, atol=3e-13)
        assert bool(field.converged) and ratio <= 1
        assert len(spec.model.channels) == 63
        assert set(layout.channel_laws[layout.channel_active]) == set(range(56))
        stages.append(
            dict(label=label, error_over_budget=ratio, reference=proof, fields=list(state._fields))
        )
        arrays.update(
            {
                label + "_rates": observed,
                label + "_reference_rates": target_rates,
                label + "_budget": budget,
                label + "_potential": potential,
                label + "_reference_potential": target_potential,
            }
        )
    a, b = initial_states
    assert type(a) is type(b)
    for key, left, right in zip(a._fields, a, b, strict=True):
        assert left.dtype == right.dtype
        np.testing.assert_array_equal(left, right)
        arrays["initial_" + key] = np.asarray(right)
    assert result.provenance["initial_state_fields"] == list(a._fields)
    assert raw == untouched
    actual_clocks = {c.time for c in parse_spec(source).experiment.changes}
    projected_clocks = {
        c.time for c in parse_spec(inner["request"]["definition"]).experiment.changes
    }
    assert actual_clocks <= projected_clocks
    evidence(
        family + "-" + case,
        dict(
            inputs=raw,
            provenance=result.provenance,
            independent_coefficients=coefficients,
            stages=stages,
            full_state_exact=True,
            scope="Two initial physical stages; manufactured geometry, no trajectory or biology",
        ),
        arrays,
    )


@pytest.mark.parametrize(
    "fault",
    (
        "unknown_parent",
        "wrong_ionic",
        "scheduled_parent",
        "schema_bool",
        "water_volume",
        "calcium_modulator",
        "face_owner",
        "control_owner",
        "fuel",
        "damage",
    ),
)
def test_refuses_wrong_owners_geometry_and_invalid_complete_state(fault):
    raw = fixtures.request()
    if fault == "unknown_parent":
        raw["definition"]["model"]["id"] = "resolved_calcium_energy_water_repair@999"
    elif fault == "wrong_ionic":
        raw["definition"]["model"]["ionic"]["id"] = "resolved_tissue@11"
    elif fault == "scheduled_parent":
        raw["definition"]["model"]["id"] = (
            "resolved_calcium_energy_water_repair_membrane_profiles@1"
        )
    elif fault == "schema_bool":
        raw["schema_version"] = True
    elif fault == "water_volume":
        raw["definition"]["model"]["ionic"]["extracellular"][0]["volume_pL"] *= 2
    elif fault == "calcium_modulator":
        del raw["ion_modulators"]["Ca"]
    elif fault == "face_owner":
        raw["grid"]["internal_face_sites"][0][0] = "unknown_outside"
    elif fault == "control_owner":
        raw["definition"]["experiment"]["channel_controls"][0]["channel_id"] = "unknown_channel"
    elif fault == "fuel":
        raw["definition"]["model"]["energy_pools"][0]["initial_amount_fmol"]["ATP"] = -1
    elif fault == "damage":
        raw["definition"]["model"]["injury_patches"][0]["initial_damage"] = 2
    with pytest.raises(ConfigError):
        tissue_profiles.prepare_request(raw)
    evidence("refusal-" + fault, dict(inputs=raw, refused=True))


@pytest.mark.parametrize("fault", ("state", "nested_recipe", "changes"))
def test_resealed_forgery_cannot_replace_complete_recomputation(fault):
    _, result = prepared()
    forged = deepcopy(result.provenance)
    if fault == "state":
        forged["initial_state_sha256"] = "0" * 64
    elif fault == "nested_recipe":
        forged["direct_parameter_preparation"]["request"]["tight_factor"] *= 2
    else:
        forged["changes"][0]["after_m2_s"] *= 2
    forged.pop("identity")
    forged["identity"] = digest(forged)
    with pytest.raises(ConfigError):
        tissue_profiles.replay(forged)


def test_complete_repair_recipe_survives_fresh_process_cli_and_portable_replay(tmp_path):
    raw, expected = prepared()
    request = tmp_path / "request.json"
    request.write_text(json.dumps(raw))
    commands = (
        ("prepare", str(request), "--output", str(tmp_path / "prepared")),
        ("validate", str(tmp_path / "prepared")),
        ("replay", str(tmp_path / "recipe.json"), "--output", str(tmp_path / "replayed")),
    )
    records = []
    for index, arguments in enumerate(commands):
        if index == 2:
            (tmp_path / "recipe.json").write_text(
                (tmp_path / "prepared/provenance.json").read_text()
            )
            request.unlink()
            (tmp_path / "prepared").rename(tmp_path / "source-unavailable")
        process = subprocess.run(
            [sys.executable, "-B", "-m", "cells", "tissue-profiles", *arguments],
            capture_output=True,
            text=True,
            timeout=150,
        )
        (tmp_path / f"cli-{index}.stdout").write_text(process.stdout)
        (tmp_path / f"cli-{index}.stderr").write_text(process.stderr)
        assert process.returncode == 0, process.stderr
        summary = json.loads(process.stdout)
        assert summary["kind"] == bridge.KIND
        records.append(summary)
    assert tissue_profiles.read_preparation(tmp_path / "replayed") == expected
    damaged = json.loads((tmp_path / "replayed/definition.json").read_text())
    damaged["model"]["injury_patches"][0]["initial_damage"] = 0.5
    (tmp_path / "replayed/definition.json").write_text(json.dumps(damaged))
    with pytest.raises(ConfigError):
        tissue_profiles.read_preparation(tmp_path / "replayed")
    evidence(
        "portable-cli",
        dict(
            inputs=raw,
            summaries=records,
            full_recipe_exact=True,
            changed_complete_state_refused=True,
        ),
    )
