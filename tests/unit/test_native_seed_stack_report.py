"""Saved text attribution only: no native module, worker attachment or RNG."""

import hashlib
from pathlib import Path

import pytest

from validation.betse import native_seed_stack_report as stacks

SOURCE = Path("/frozen/source")
PHASE = "src/cells/processes/betse_native_phase_dyna.py"
FRAME = f'  File "{SOURCE / PHASE}", line 42 in _check\n'
HEADER = "Timeout (0:00:30)!\nThread 0xabc (most recent call first):\n"
FILES = {PHASE: dict(sha256=hashlib.sha256(b"never imported").hexdigest())}


def test_stack_report_counts_presence_not_recursive_calls():
    value = stacks.summarize(HEADER + FRAME * 4 + HEADER + FRAME, SOURCE, FILES)
    assert value["samples"] == value["samples_with_project_frames"] == 2
    assert value["project_functions"][0]["samples"] == 2
    assert value["first_project_frames"][0]["thread_observations"] == 2
    assert value["incomplete_samples"] == []
    assert value["source_or_numerical_execution"] is False
    assert value["stage_completion_or_scientific_credit"] is False


def test_stack_report_retains_threads_and_does_not_promote_library_leaf():
    text = HEADER + '  File "/usr/lib/threading.py", line 15 in wait\n'
    text += "\nCurrent thread 0xdef (most recent call first):\n"
    text += '  File "/usr/lib/pathlib.py", line 80 in read_bytes\n' + FRAME
    value = stacks.summarize(text, SOURCE, FILES)
    assert len(value["observations"][0]["threads"]) == 2
    assert value["project_thread_observations"] == 1
    assert value["first_project_frames"][0]["function"] == "_check"
    assert value["observations"][0]["threads"][1]["frames"][0][2] == "read_bytes"


def test_stack_report_multiple_project_threads_have_separate_denominator():
    text = HEADER + FRAME + "Thread 0xdef (most recent call first):\n" + FRAME
    value = stacks.summarize(text, SOURCE, FILES)
    assert value["samples"] == value["project_functions"][0]["samples"] == 1
    assert value["project_thread_observations"] == 2
    assert value["first_project_frames"][0]["thread_observations"] == 2


@pytest.mark.parametrize("ending", ("  ...\n", '  File "unfinished', "unknown diagnostic\n"))
def test_stack_report_marks_partial_samples_without_dropping_observations(ending):
    value = stacks.summarize(HEADER + FRAME + ending, SOURCE, FILES)
    assert value["incomplete_samples"] == [1]
    assert value["project_functions"][0]["samples"] == 1


def test_stack_report_empty_final_sample_is_incomplete():
    value = stacks.summarize(HEADER + FRAME + "Timeout (0:00:30)!\n", SOURCE, FILES)
    assert value["samples"] == 2 and value["incomplete_samples"] == [2]


def test_stack_report_does_not_rebind_foreign_or_missing_sources():
    unknown = '  File "/frozen/source/unbound.py", line 1 in f\n'
    sibling = '  File "/frozen/source-other/' + PHASE + '", line 42 in _check\n'
    value = stacks.summarize(HEADER + unknown + sibling, SOURCE, FILES)
    assert value["unbound_source_paths"] == ["unbound.py"]
    assert value["project_functions"] == []
    assert value["samples_with_project_frames"] == 0


@pytest.mark.parametrize("text", ("", "unrelated text", "Timeout (0:99:00)!", "Timeout (0:00:00)!"))
def test_stack_report_refuses_empty_or_invalid_log(text):
    with pytest.raises(ValueError):
        stacks.parse(text)


def test_stack_report_refuses_sample_overflow(monkeypatch):
    monkeypatch.setattr(stacks, "MAX_SAMPLES", 1)
    with pytest.raises(ValueError, match="capacity"):
        stacks.parse((HEADER + FRAME) * 2)


def test_stack_report_refuses_large_input(tmp_path, monkeypatch):
    path = tmp_path / "stacks.log"
    path.write_bytes(b"12345")
    monkeypatch.setattr(stacks, "MAX_BYTES", 4)
    with pytest.raises(ValueError, match="Bounded"):
        stacks._read(path)
