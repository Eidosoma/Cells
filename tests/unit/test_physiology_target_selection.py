"""Native selection tapes, carried ALL aliases, restart and atomic refusal."""

import json
import os
import platform
import random
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.core import physiology_target_selection as selection
from cells.processes import betse_perturbations as perturb
from cells.processes import betse_tissue_profiles as profiles
from validation.perturbations import target_selection_native as native
from validation.perturbations import target_selection_reference as reference
from validation.topology.betse_tissue_profiles_fixtures import base, profile


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def layout_from(raw):
    data = raw["layout"]
    cells, membranes, env = (
        tuple(data[k]) for k in ("cell_ids", "membrane_ids", "environment_ids")
    )
    return profiles.validate_layout(
        profiles.Layout(
            cells,
            membranes,
            env,
            tuple(cells[i] for i in data["membrane_cell"]),
            tuple(env[i] if i >= 0 else None for i in data["membrane_environment"]),
            tuple(tuple(membranes[i] for i in group) for group in data["cell_membranes"]),
            np.asarray(data["cell_centres_m"], dtype=float).reshape(len(cells), 2),
            tuple(data["bounds_m"]),
            None if data["seed_fills"] is None else tuple(data["seed_fills"]),
        )
    )


def declarations(raw, layout):
    def one(row):
        kind = row["picker"]
        value = {"percent": row["percent"], "indices": row["indices"]}.get(kind)
        selector = profiles.Selector(
            kind, value, profiles.layout_identity(layout) if kind == "indices" else None
        )
        return profiles.Profile(
            row["name"], selector, tuple(row["diffusivity_m2_s"]), row["insular"]
        )

    return one(raw["default"]), tuple(one(row) for row in raw["profiles"])


CASES = (
    "mixed",
    "zero",
    "full",
    "fractional",
    "disabled",
    "ions_off",
    "no_ecm",
    "empty",
    "singleton",
    "reordered",
)


def definition(name):
    raw = base(name)
    raw["global_gj_percent"] = 37.9
    raw["profiles"] = [
        profile("Before", "all"),
        profile("Zero", "percent", percent=0.0),
        profile("Full", "percent", percent=100.0),
        profile("Between", "all"),
        profile("Half", "percent", percent=40.0),
        profile("After", "all"),
        profile("Duplicate", "indices", indices=[4, 1, 4]),
    ]
    # The default's configured picker is ignored by the source.
    raw["default"]["picker"], raw["default"]["percent"] = "percent", -100.0
    if name in ("zero", "full", "fractional"):
        value = {"zero": 0.0, "full": 100.0, "fractional": 39.99999999999999}[name]
        raw["profiles"] = [profile("Chosen", "percent", percent=value), profile("After", "all")]
        raw["global_gj_percent"] = {"zero": 0.0, "full": 120.0, "fractional": 40.99}[name]
    elif name == "disabled":
        raw["enabled"] = False
    elif name == "ions_off":
        raw["ion_enabled"] = [False] * 6
    elif name == "no_ecm":
        raw["is_ecm"] = False
        raw["global_gj_percent"] = None
    elif name in ("empty", "singleton"):
        count = int(name == "singleton")
        raw["layout"].update(
            cell_ids=["single"] * count,
            membrane_ids=["surface"] * count,
            environment_ids=["bath"] * count,
            membrane_cell=[0] * count,
            membrane_environment=[0] * count,
            cell_membranes=[[0]] * count,
            cell_centres_m=[[0.0, 0.0]] * count,
            seed_fills=None,
        )
        raw["initial_membrane_m2_s"] = [[1e-18] * count for _ in range(6)]
        raw["profiles"] = [
            profile("Zero", "percent", percent=0.0),
            profile("Full", "percent", percent=100.0),
        ]
        raw["global_gj_percent"] = -2.9
    elif name == "reordered":
        data, order = raw["layout"], [2, 4, 1, 0, 3]
        inverse = {old: new for new, old in enumerate(order)}
        for key in ("cell_ids", "cell_centres_m", "seed_fills", "cell_membranes"):
            data[key] = [data[key][i] for i in order]
        data["membrane_cell"] = [inverse[i] for i in data["membrane_cell"]]
    return raw


def streams(layout, seed, *, cache="normal", next_call=7, world=2**63 + 73):
    nrng, prng = np.random.RandomState(seed), random.Random(seed + 19)
    nrng.normal()
    nrng.randint(0, 2**32, size=620, dtype=np.uint32)
    prng.gauss(0, 1)
    for _ in range(620):
        prng.getrandbits(32)
    a, b = list(nrng.get_state()), list(prng.getstate())
    if cache != "normal":
        a[4] = b[2] = -0.0 if cache == "negative_zero" else -5e-324
    return selection.new_stream(
        layout,
        perturb._native_stream(a, np.__version__),
        selection.python_stream(
            b,
            python_version=platform.python_version(),
            implementation=platform.python_implementation(),
        ),
        stream_id="target-selection",
        world_id=world,
        next_call=next_call,
    )


def execute(raw, stream):
    layout = layout_from(raw)
    default, definitions = declarations(raw, layout)
    return selection.resolve(
        layout,
        stream,
        default,
        definitions,
        enabled=raw["enabled"],
        is_ecm=raw["is_ecm"],
        ion_enabled=raw["ion_enabled"],
        global_gj_percent=raw["global_gj_percent"],
    )


def evidence(name, payload):
    if path := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(path) / "target-selection"
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / (name + ".json")).open("x") as stream:
            json.dump(payload, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("seed", (17, 29))
def test_three_native_preparations_and_saved_restart(tmp_path, case, seed):
    raw, rows = definition(case), []
    layout = layout_from(raw)
    stream = streams(layout, seed)
    original_layout = profiles.layout_identity(layout)
    for call in range(3):
        saved = json.loads(canonical(selection.stream_record(stream)))
        path = tmp_path / f"call-{call}.json"
        path.write_text(json.dumps(saved))
        source_bytes = path.read_bytes()
        restored = selection.restore_stream(
            json.loads(path.read_text()),
            layout,
            stream_id=stream.stream_id,
            world_id=stream.world_id,
        )
        numpy_global = canonical(native.numpy_state(np.random))
        python_global = canonical(native.python_state(random))
        result, resumed = execute(raw, stream), execute(raw, restored)
        assert canonical(selection.result_record(result)) == canonical(
            selection.result_record(resumed)
        )
        assert path.read_bytes() == source_bytes and canonical(
            selection.stream_record(stream)
        ) == canonical(saved)
        captured = native.evaluate(raw, saved)
        permutations = {
            op["name"]: op["permutation"]
            for op in captured["operations"]
            if op["kind"] == "percent"
        }
        independent = reference.evaluate(raw, saved["cell_order"], permutations)
        actual = selection.result_record(result)
        assert canonical(actual["binding"]["targets"]) == canonical(independent["targets"])
        assert (
            list(result.binding.final_cell_order)
            == captured["final_cell_order"]
            == independent["final_cell_order"]
        )
        assert actual["global_gj_targets"] == (
            None
            if independent["global_gj_targets"] is None
            else tuple(independent["global_gj_targets"])
        )
        assert independent["global_gj_targets"] == captured["global_gj_targets"]
        assert result.stream.next_call == captured["next_call"]
        assert canonical(actual["successor"]["numpy"]["state"]) == canonical(
            captured["numpy_state"]
        )
        assert canonical(actual["successor"]["python"]["state"]) == canonical(
            captured["python_state"]
        )
        assert {
            name: list(target.cells.ids) for name, target in result.binding.targets.items()
        } == captured["selected_cells"]
        assert {
            name: list(target.picked_cell_ids) for name, target in result.binding.targets.items()
        } == captured["picked_cells"]
        operation_streams = []
        for operation, source_op in zip(result.operations, captured["operations"], strict=True):
            after = selection.stream_record(operation.successor)
            assert canonical(after["numpy"]["state"]) == canonical(source_op["numpy_state"])
            assert canonical(after["python"]["state"]) == canonical(source_op["python_state"])
            assert list(operation.permutation) == source_op["permutation"]
            assert list(operation.selected) == source_op["selected"]
            operation_streams.append(after)
        dm = profiles.apply_profile_diffusion(
            np.asarray(raw["initial_membrane_m2_s"], dtype=float), result.binding.kernel, xp=np
        )
        np.testing.assert_array_equal(dm, independent["diffusion_m2_s"])
        nrng, prng = (
            selection._numpy_rng(result.stream.numpy),
            selection._python_rng(result.stream.python),
        )
        future = dict(
            numpy_normals=nrng.normal(size=3).tolist(),
            python_gaussians=[prng.gauss(0, 1) for _ in range(3)],
            numpy_state=native.numpy_state(nrng),
            python_state=native.python_state(prng),
        )
        assert canonical(future) == canonical(captured["future_probe"])
        assert canonical(native.numpy_state(np.random)) == numpy_global
        assert canonical(native.python_state(random)) == python_global
        assert profiles.layout_identity(layout) == original_layout
        rows.append(
            dict(
                source=saved,
                actual=actual,
                native=captured,
                independent=independent,
                operation_successors=operation_streams,
                diffusion_m2_s=dm.tolist(),
                exact_restart=True,
                original_layout_unchanged=True,
                global_rng_unchanged=True,
            )
        )
        stream = resumed.stream
    evidence(
        f"sequence-{case}-{seed}",
        dict(parameters=raw, calls=rows, biological_cases=0, independent_rng_engine=False),
    )


@pytest.mark.parametrize("cache", ("negative_zero", "subnormal"))
def test_complete_cache_bits_survive_both_shuffle_engines(cache):
    raw = definition("mixed")
    layout = layout_from(raw)
    stream = streams(layout, 23, cache=cache)
    result = execute(raw, stream)
    actual, captured = (
        selection.stream_record(result.stream),
        native.evaluate(raw, selection.stream_record(stream)),
    )
    assert canonical(actual["numpy"]["state"]) == canonical(captured["numpy_state"])
    assert canonical(actual["python"]["state"]) == canonical(captured["python_state"])
    assert canonical(actual["numpy"]["state"][4]) == canonical(
        json.loads(stream.numpy.state_json)[4]
    )
    assert canonical(actual["python"]["state"][2]) == canonical(
        json.loads(stream.python.state_json)[2]
    )
    evidence(
        "cache-" + cache,
        dict(
            parameters=raw,
            source=selection.stream_record(stream),
            actual=selection.result_record(result),
            native=captured,
        ),
    )


def test_native_world_labels_do_not_reseed_the_tapes():
    raw = definition("mixed")
    layout = layout_from(raw)
    first = execute(raw, streams(layout, 37, world=1))
    other = execute(raw, streams(layout, 37, world=2**64 - 1))
    assert profiles.binding_manifest(first.binding) == profiles.binding_manifest(other.binding)
    assert first.stream.numpy == other.stream.numpy and first.stream.python == other.stream.python
    assert first.stream.world_id != other.stream.world_id and first.identity != other.identity


def test_disabled_profiles_and_global_preserve_both_tapes_at_counter_limit():
    raw = definition("disabled")
    raw["global_gj_percent"] = None
    layout = layout_from(raw)
    stream = streams(layout, 11, next_call=selection.MAX_CALL)
    result = execute(raw, stream)
    assert result.stream is stream and result.operations == () and result.binding.names == ()


def test_disabled_profiles_do_not_demand_unused_environment_owners():
    raw = definition("disabled")
    raw["layout"]["membrane_environment"] = [-1] * len(raw["layout"]["membrane_ids"])
    layout = layout_from(raw)
    stream = streams(layout, 11)
    result = execute(raw, stream)
    assert result.binding.names == () and result.stream.numpy == stream.numpy
    assert result.stream.python != stream.python and len(result.operations) == 1


@pytest.mark.parametrize("stage", ("percentage_selection", "global_gj_selection"))
def test_counter_overflow_retains_completed_speculative_selections(stage):
    raw = definition("mixed" if stage == "percentage_selection" else "zero")
    layout = layout_from(raw)
    stream = streams(layout, 17, next_call=selection.MAX_CALL - 1)
    before = selection.stream_record(stream)
    with pytest.raises(selection.SelectionRejected, match="overflow") as caught:
        execute(raw, stream)
    failure = caught.value
    assert failure.source is stream and failure.stage == stage and len(failure.operations) == 1
    assert failure.trial_stream.next_call == selection.MAX_CALL
    assert failure.operations[0].successor == failure.trial_stream
    assert selection.stream_record(stream) == before
    assert (
        failure.trial_stream.numpy != stream.numpy and failure.trial_stream.python == stream.python
    )
    evidence(
        "overflow-" + stage,
        dict(
            source=before,
            stage=stage,
            trial=selection.stream_record(failure.trial_stream),
            completed_operations=1,
            committed=False,
        ),
    )


@pytest.mark.parametrize(
    "defect",
    (
        "layout",
        "numpy",
        "python",
        "counter",
        "boolean",
        "order",
        "stream",
        "world",
        "extended",
        "version",
    ),
)
def test_saved_stream_rejects_changed_owners_tapes_or_canonical_values(defect):
    raw = definition("mixed")
    layout = layout_from(raw)
    stream = streams(layout, 13)
    saved = json.loads(canonical(selection.stream_record(stream)))
    expected_stream, expected_world = stream.stream_id, stream.world_id
    if defect == "layout":
        saved["layout_identity"] = "0" * 64
    elif defect == "numpy":
        saved["numpy"]["state"][1][20] ^= 1
    elif defect == "python":
        saved["python"]["state"][1][20] ^= 1
    elif defect == "counter":
        saved["next_call"] = -1
    elif defect == "boolean":
        saved["numpy"]["state"][2] = True
    elif defect == "order":
        saved["cell_order"] = saved["cell_order"][::-1]
    elif defect == "stream":
        expected_stream = "different"
    elif defect == "world":
        expected_world += 1
    elif defect == "version":
        saved["python"]["python_version"] = "0.0"
    else:
        saved["ignored"] = "forbidden"
    with pytest.raises(ValueError):
        selection.restore_stream(saved, layout, stream_id=expected_stream, world_id=expected_world)


@pytest.mark.parametrize(
    "defect", ("duplicate", "bounds", "prescribed", "float32", "global_nan", "enabled_int")
)
def test_invalid_declarations_refuse_before_consuming_rng(defect, monkeypatch):
    raw = definition("mixed")
    layout = layout_from(raw)
    stream = streams(layout, 17)
    default, definitions = declarations(raw, layout)
    kwargs = dict(global_gj_percent=0.0)
    if defect == "duplicate":
        definitions = (*definitions, definitions[0])
    elif defect == "bounds":
        definitions = (replace(definitions[1], selector=profiles.Selector("percent", 100.1)),)
    elif defect == "prescribed":
        definitions = (
            replace(
                definitions[1],
                selector=profiles.Selector("percent", 20.0, permutation_cell_ids=layout.cell_ids),
            ),
        )
    elif defect == "float32":
        definitions = (
            replace(definitions[1], selector=profiles.Selector("percent", np.float32(20))),
        )
    elif defect == "global_nan":
        kwargs["global_gj_percent"] = float("nan")
    else:
        kwargs["enabled"] = 1
    monkeypatch.setattr(selection, "_numpy_rng", lambda *a: pytest.fail("Unexpected NumPy draw"))
    monkeypatch.setattr(selection, "_python_rng", lambda *a: pytest.fail("Unexpected Python draw"))
    with pytest.raises(selection.SelectionRejected) as caught:
        selection.resolve(layout, stream, default, definitions, **kwargs)
    assert caught.value.stage == "source_admission" and caught.value.operations == ()
    assert caught.value.trial_stream is stream


def test_prepared_binding_survives_source_input_mutation():
    raw = definition("mixed")
    stream = streams(layout_from(raw), 17)
    result = execute(raw, stream)
    original = canonical(selection.result_record(result))
    changed = deepcopy(raw)
    raw["layout"]["cell_ids"].reverse()
    raw["profiles"][1]["percent"] = 93
    assert canonical(selection.result_record(result)) == original
    assert execute(changed, stream).identity == result.identity
