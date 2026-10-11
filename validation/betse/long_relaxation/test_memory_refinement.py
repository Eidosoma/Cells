"""512k refinement receipts, resource guards and exact reduced prefix working sets."""

import copy
import gc
import sys
import weakref
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import memory_refinement as m  # noqa: E402
import pilot  # noqa: E402
from streamed_review import prefix_window  # noqa: E402

WORKSPACE = Path("/mnt/workspaces/Cells")
PARENT = WORKSPACE / "betse-long-pump-quarter-step-20260922-01"
QUALIFICATION = WORKSPACE / "betse-memory-prefix-20260922-01"


@pytest.fixture(scope="module")
def qualified():
    return m.authenticate(QUALIFICATION, PARENT)


def registration():
    return dict(
        native_index=3,
        native_dt_s=m.DT,
        max_native_labels=m.STEPS,
        native_parallel=False,
        checkpoint_mode=m.MODE,
        memory_qualification=dict(
            path=str(QUALIFICATION),
            completion_sha256="a" * 64,
            registration_sha256="b" * 64,
            result_sha256="c" * 64,
        ),
    )


@pytest.mark.parametrize("change", [None, "receipt", "writer", "parallel", "dt", "count", "index"])
def test_finer_native_clock_requires_storage_qualification_and_serial_captures(change):
    r = registration()
    if change == "receipt":
        r.pop("memory_qualification")
    elif change == "writer":
        r["checkpoint_mode"] = "native"
    elif change == "parallel":
        r["native_parallel"] = True
    elif change == "dt":
        r["native_dt_s"] *= 2
    elif change == "count":
        r["max_native_labels"] //= 2
    elif change == "index":
        r["native_index"] = 4
    if change is None:
        assert pilot.native_controls(r) == (3, m.DT, 512000)
    else:
        with pytest.raises(ValueError, match="native"):
            pilot.native_controls(r)


@pytest.mark.parametrize(
    "stream,total,passed",
    [
        (2 * 1024**3, 8 * 1024**3, True),
        (2 * 1024**3 + 1, 8 * 1024**3, False),
        (2 * 1024**3, 8 * 1024**3 + 1, False),
        (True, 8 * 1024**3, False),
    ],
)
def test_finer_storage_allowances_stay_bounded(stream, total, passed):
    r = registration() | dict(native_stream_bytes=stream, artifact_bytes=total)
    if passed:
        assert pilot.recording_limits(r) == (stream, total)
    else:
        with pytest.raises(ValueError, match="allowance"):
            pilot.recording_limits(r)


def test_completed_memory_qualification_and_source_boundary(qualified):
    r, result, receipt = qualified
    assert result["prefix_qualified"] and receipt["artifacts_verified"] == 6483
    candidate = dict(r["sources_sha256"])
    candidate["validation/betse/long_relaxation/pilot.py"] = "0" * 64
    m.compatible_sources(r, candidate)
    candidate["validation/betse/pump_loop_audit/evidence.py"] = "1" * 64
    with pytest.raises(ValueError, match="outside the declared extension"):
        m.compatible_sources(r, candidate)


@pytest.mark.parametrize("failure", [None, "memory", "disk", "native_peak", "review_peak"])
def test_full_refinement_preflight_uses_measured_capacity_and_preserves_reserves(
    qualified, monkeypatch, failure
):
    _, result, _ = qualified
    read = m.u.read

    def changed(path):
        value = read(path)
        phase = "capacity" if failure == "native_peak" else "compare"
        if (
            failure in ("native_peak", "review_peak")
            and path == QUALIFICATION / phase / "completion.json"
        ):
            value["peak_rss_bytes"] *= 2
        return value

    monkeypatch.setattr(m.u, "read", changed)
    arguments = dict(
        available_memory=(4 if failure == "memory" else 25) * 1024**3,
        free_disk=(4 if failure == "disk" else 13) * 1024**3,
    )
    if failure:
        with pytest.raises(ValueError, match="Refinement"):
            m.preflight(PARENT, QUALIFICATION, result, **arguments)
    else:
        preflight = m.preflight(PARENT, QUALIFICATION, result, **arguments)
        assert preflight["steps"] == 512000 and not preflight["native_parallel"]
        assert preflight["projected_concurrent_peak_rss_bytes"] <= 16 * 1024**3
        assert preflight["projected_artifact_bytes"] <= preflight["artifact_bytes"]
        assert preflight["projected_review_artifact_bytes"] >= 128 * 1024**2
        assert not preflight["scientific_tolerances_changed"]
        assert not preflight["actual_512000_step_capture_qualified"]


def test_qualified_prefix_is_selected_by_its_own_stage_receipt(qualified):
    _, _, receipt = qualified
    prefix = Path(receipt["path"]) / "observed"
    r = registration() | dict(
        native_prefix=dict(path=str(prefix), completion_sha256=pilot.u.authenticate_stage(prefix))
    )
    assert pilot.prefix_input(r) == (prefix, receipt["phase_completions_sha256"]["observed"])


@pytest.mark.parametrize("change", [None, "history", "raw_step", "endpoint"])
def test_smaller_prefix_working_set_preserves_every_existing_comparison(change):
    import fresh_review

    saved, native, _ = fresh_review.modules()
    path = WORKSPACE / "long-pump-pilot-development-20260921-01/native-smoke/stream"
    full, _ = pilot.reader(saved, native).read(path)
    count = 4
    short = dict(
        steps=count,
        dt_s=full["dt_s"],
        trace={
            name: (
                copy.deepcopy(list(full["trace"][name][:count]))
                if name != "initial"
                else copy.deepcopy(full["trace"][name])
            )
            for name in ("initial", "steps", "raw_steps")
        },
        histories={
            name: {"values": copy.deepcopy(v["values"][: count - 1])}
            for name, v in full["histories"].items()
        },
        final=copy.deepcopy(full["trace"]["steps"][count - 1]["after_voltage"]),
    )
    window = prefix_window(full, count)
    duration = count * full["dt_s"]
    expected = fresh_review.prefix(full, short, saved.c.exact, duration_s=duration)
    assert fresh_review.prefix(window, short, saved.c.exact, duration_s=duration) == expected
    if change is None:
        return
    if change == "history":
        short["histories"]["vm_time"]["values"][0][0] += 1e-6
    elif change == "raw_step":
        short["trace"]["raw_steps"][0] = {}
    else:
        short["final"] = {}
    with pytest.raises(ValueError):
        fresh_review.prefix(window, short, saved.c.exact, duration_s=duration)


def test_prefix_working_set_releases_unneeded_history_objects():
    class History(list):
        pass

    tail = History([99.0])
    reference = weakref.ref(tail)
    full = dict(
        steps=8,
        dt_s=1e-6,
        trace=dict(initial={}, steps=(), raw_steps=(), labels_s=[]),
        histories=dict(a=dict(values=[[1.0], [2.0], [3.0], tail])),
    )
    window = prefix_window(full, 4)
    assert window["histories"]["a"]["values"][0] is full["histories"]["a"]["values"][0]
    assert "labels_s" not in window["trace"]
    del tail, full
    gc.collect()
    assert reference() is None
    assert window["histories"]["a"]["values"] == [[1.0], [2.0], [3.0]]


@pytest.mark.parametrize("count", [True, 0, 1, 9])
def test_prefix_working_set_refuses_invalid_extent(count):
    with pytest.raises(ValueError, match="extent"):
        prefix_window(dict(steps=8), count)
