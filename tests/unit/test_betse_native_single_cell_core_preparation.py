"""Software-only native-parent prerequisite refusals; no constructor/operator run."""

import json
import os
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_native_single_cell_core_preparation as core


def save(name, value):
    folder = os.environ.get("CELLS_DEC_PREREQUISITE_EVIDENCE")
    if not folder:
        return
    root = Path(folder)
    root.mkdir(parents=True, exist_ok=True)
    with (root / (name + ".json")).open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def synthetic_parent():
    """Deliberately unauthenticated records, used only for early-refusal controls."""
    request = core.initial.Request(
        "owned_image_prelude",
        (None, None, SimpleNamespace(next_method="init_mesh")),
        dict(seed_points=None, make_all_operators=False, single_cell_sides=6),
        (),
        tuple("occurrence-" + str(i) for i in range(7)),
        None,
        "create_core_operators",
        "synthetic-request",
    )
    empty = core.caches.snapshot({})
    # Preserve a raw noncanonical NaN payload in the deliberately failed parent.
    raw = np.frombuffer(bytes.fromhex("170000000000f87f"), dtype="<f8")
    failed_cache = core.caches.snapshot(dict(synthetic_failed_bits=raw))
    state = core.initial.State(
        request.identity,
        empty,
        failed_cache,
        (),
        request.constructor_point_ids,
        None,
        None,
        None,
        (),
        True,
        True,
        "source_completed_unqualified",
        None,
        None,
        None,
        "synthetic-state",
    )
    return request, state


@pytest.mark.parametrize(
    "case,expected_stage",
    [
        ("missing", "upstream_unavailable"),
        ("supplied-dictionaries", "upstream_owner_type"),
        ("stable-substitute", "upstream_owner_type"),
        ("failed-parent", "upstream_incomplete"),
        ("incomplete-parent", "upstream_incomplete"),
        ("B09-probe", "upstream_origin"),
        ("multi-cell", "caller_branch"),
        ("auxiliary-operators", "caller_branch"),
        ("wrong-law", "opt_in"),
    ],
)
def test_software_parent_prerequisites_refuse_before_replay(case, expected_stage, monkeypatch):
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("unexpected_native_execution")
        raise AssertionError("Software contract checks must never invoke native source work")

    monkeypatch.setattr(core.initial, "validate_state", forbidden)
    monkeypatch.setattr(core.initial, "prepare", forbidden)
    monkeypatch.setattr(core._Runtime, "create_core_operators", forbidden)
    request, state = synthetic_parent()
    if case == "missing":
        request = state = None
    elif case == "supplied-dictionaries":
        request, state = dict(source_completed=True), dict(source_completed=True)
    elif case == "stable-substitute":
        state = SimpleNamespace(status="stable_mesh_completed_unqualified")
    elif case == "failed-parent":
        state = replace(
            state,
            status="retained_source_failure",
            failure_stage="pre_mesh",
            failure_type="SyntheticFailure",
            failure_message="retained raw parent",
        )
    elif case == "incomplete-parent":
        state = replace(state, pre_mesh_completed=False)
    elif case == "B09-probe":
        request = replace(request, origin="reused_fixed_B09")
    elif case in ("multi-cell", "auxiliary-operators"):
        kwargs = dict(request.constructor_kwargs)
        kwargs["seed_points" if case == "multi-cell" else "make_all_operators"] = (
            [[0.0, 0.0]] if case == "multi-cell" else True
        )
        request = replace(request, constructor_kwargs=kwargs)
    law_id = "Cells_polygon_law@1" if case == "wrong-law" else core.LAW_ID
    columns_before = (
        None
        if type(state) is not core.initial.State
        else {key: value.tobytes().hex() for key, value in state.cache.numeric_columns().items()}
    )
    with pytest.raises(core.CorePrerequisiteRejected) as caught:
        core.from_initial(request, state, law_id=law_id)
    assert caught.value.stage == expected_stage
    assert caught.value.parent_request is request and caught.value.parent_state is state
    assert attempts == []
    columns_after = (
        None
        if type(state) is not core.initial.State
        else {key: value.tobytes().hex() for key, value in state.cache.numeric_columns().items()}
    )
    assert columns_after == columns_before
    save(
        "refusal-" + case,
        dict(
            case=case,
            stage=caught.value.stage,
            original_parent_retained=True,
            original_cache_bits=columns_before,
            cache_bits_unchanged=True,
            native_execution_attempts=attempts,
            synthetic_control_only=True,
            scientific_acceptance=False,
        ),
    )


def test_software_metadata_cannot_admit_native_parent(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Refusal must not invoke source preparation")

    monkeypatch.setattr(core, "prepare", forbidden)
    request = dict(supplied_state="not native authority")
    state = dict(executable_DEC_parent_admitted=True)
    with pytest.raises(core.CorePrerequisiteRejected) as caught:
        core.require_executable_parent(request, state, declarations=dict(all_owners="supplied"))
    assert caught.value.parent_request is request and caught.value.parent_state is state
    assert caught.value.stage == "executable_native_DEC_parent_unavailable"
    assert caught.value.partial["metadata_cannot_admit_parent"] is True
    assert caught.value.partial["executable_DEC_parent_admitted"] is False
    assert caught.value.partial["ordinary_continuation_admitted"] is False
    assert caught.value.partial["invalidated_owners"] == list(core.INVALIDATED_OWNERS)
    assert len(caught.value.partial["invalidated_owners"]) == 11
    save(
        "metadata-cannot-admit-parent",
        dict(
            stage=caught.value.stage,
            partial=caught.value.partial,
            synthetic_control_only=True,
            scientific_acceptance=False,
        ),
    )
