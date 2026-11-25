"""Start and failure records of the run paths' phases (core.phases.Recorder; D156, item 3).

The recorder's own rules, with no engine: each phase's start record at its completion record's
level; one failure record for an Exception leaving the path, for the innermost open phase (with
its enclosing phase) or after the last phase that ended; GeneratorExit and other BaseExceptions
are not failures; the exception propagates unchanged; nothing is formatted or written without a
handler; the module imports no jax. Then each path's own refusal on the small shared pair of worlds
(an rhs that goes non-finite in world 11): the runner's host check after its execute phase, the
batch's refusal after its execute record, the windowed batch's after its first window, and the
vectorized plan's admission before any phase; and the records change no result.
"""

import ast
import io
import logging

import jax
import numpy as np
import pytest

from cells.definitions.specs import ConfigError
from cells.execution import phases
from cells.execution.batch import run_batch
from cells.execution.batch_windows import run_batch_windowed
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.execution.vector_windows import plan_vector_windows
from cells.execution.windows import WindowPolicy
from cells.models import reaction_transport
from tests.batch_fixtures import failing_second_world, synthetic_pair

POLICY = WindowPolicy(2, "checkpoints")


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


class Collect(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture
def collected():
    handler = Collect()
    phases.LOGGER.addHandler(handler)
    phases.LOGGER.setLevel(logging.DEBUG)
    try:
        yield handler.records
    finally:
        phases.LOGGER.removeHandler(handler)
        phases.LOGGER.setLevel(logging.NOTSET)


def texts(records):
    return [r.getMessage() for r in records]


def test_start_and_completion_records_and_their_levels(collected):
    record = phases.Recorder()
    record.start("plan", worlds=2)
    record.end("plan", worlds=2, seconds=0.5)
    record.start("window", debug=True, index=1)
    record.end("window", debug=True, index=1, steps=4)
    assert texts(collected) == [
        "plan.start worlds=2",
        "plan worlds=2 seconds=0.500",
        "window.start index=1",
        "window index=1 steps=4",
    ]
    assert [r.levelno for r in collected] == [logging.INFO] * 2 + [logging.DEBUG] * 2
    assert [getattr(r, "event", None) for r in collected] == ["start", None, "start", None]
    assert [r.phase for r in collected] == ["plan", "plan", "window", "window"]
    assert collected[0].fields == {"worlds": 2}
    collected.clear()
    phases.mark("plan", worlds=2, seconds=0.5)  # The completion record is mark's, unchanged.
    assert texts(collected) == ["plan worlds=2 seconds=0.500"]


def test_a_failure_in_an_open_phase_names_it_and_its_enclosing_phase(collected):
    error = ConfigError("World 3:\n  a   refused  plan")
    with pytest.raises(ConfigError) as caught, phases.Recorder() as record:
        record.start("plan")
        record.start("plan.world", world=3)
        raise error
    assert caught.value is error
    last = collected[-1]
    assert last.getMessage().startswith("plan.world.failed within=plan seconds=")
    assert last.getMessage().endswith(" error=ConfigError message=World 3: a refused plan")
    assert (last.levelno, last.event, last.phase) == (logging.INFO, "failed", "plan.world")
    assert last.fields["message"] == "World 3: a refused plan"
    assert sum(r.event == "failed" for r in collected if hasattr(r, "event")) == 1


def test_a_failure_after_a_phase_ended_or_before_any_began(collected):
    with pytest.raises(NumericalError), phases.Recorder() as record:
        record.start("execute")
        record.end("execute", seconds=1.0)
        raise NumericalError("refused")
    after = collected[-1].getMessage()
    assert after.startswith("failed after=execute seconds=")
    assert after.endswith(" error=NumericalError message=refused")
    with pytest.raises(ValueError), phases.Recorder():
        raise ValueError("first")
    assert collected[-1].getMessage().startswith("failed seconds=")
    assert collected[-1].phase is None


def test_generator_exit_and_other_base_exceptions_are_not_failures(collected):
    def rounds():
        with phases.Recorder() as record:
            for index in range(3):
                record.start("window", index=index)
                record.end("window", index=index)
                yield index

    windows = rounds()
    assert next(windows) == 0
    windows.close()  # GeneratorExit at the yield.
    with pytest.raises(KeyboardInterrupt), phases.Recorder() as record:
        record.start("compile")
        raise KeyboardInterrupt
    assert not any(getattr(r, "event", None) == "failed" for r in collected)


def test_nothing_is_formatted_or_written_without_a_handler(capsys):
    assert not phases.LOGGER.handlers and not phases.LOGGER.isEnabledFor(logging.INFO)
    calls = []

    class Loud(Exception):
        def __str__(self):
            calls.append(1)
            return "loud"

    with pytest.raises(Loud), phases.Recorder() as record:
        record.start("compile")
        raise Loud
    out = capsys.readouterr()
    assert calls == [] and out.out == out.err == ""


def test_the_records_import_no_jax():
    tree = ast.parse(open(phases.__file__).read())
    names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not {n for n in names if n and n.split(".")[0] in ("jax", "jaxlib", "numpy")}


@pytest.fixture
def refusing(monkeypatch):
    """World 11's rhs goes non-finite (tests/unit/test_batch.py's injected failure)."""
    bad_rhs = failing_second_world(reaction_transport.rhs)
    monkeypatch.setattr(reaction_transport, "rhs", bad_rhs)


def ran(collected, call):
    with pytest.raises(Exception) as caught:
        call()
    names = [r.getMessage().split()[0] for r in collected]
    return caught.value, names, collected[-1].getMessage()


def test_the_runner_records_its_host_check_after_execute(collected, refusing):
    error, names, last = ran(collected, lambda: run(synthetic_pair().worlds[1].simulation))
    assert isinstance(error, NumericalError)
    assert names[:-1] == [
        "preparation.start",
        "preparation",
        "compile.start",
        "compile",
        "execute.start",
        "execute",
    ]
    assert last.startswith("failed after=execute seconds=")
    assert last.endswith(f" error=NumericalError message={error}")


def test_the_batch_records_its_refusal_after_execute(collected, refusing):
    error, names, last = ran(collected, lambda: run_batch(synthetic_pair()))
    assert "batch refused" in str(error)
    assert names[-3:-1] == ["execute.start", "execute"]
    assert last.endswith(f" error=NumericalError message={error}")
    assert last.startswith("failed after=execute ")


def test_the_windowed_batch_records_its_refusal_after_the_first_window(collected, refusing):
    error, names, last = ran(collected, lambda: run_batch_windowed(synthetic_pair(), POLICY))
    assert "windowed batch refused" in str(error)
    assert names[:6] == ["plan.start", "plan.world.start", "plan.world", "plan.world.start"] + [
        "plan.world",
        "plan",
    ]
    assert names[-3:-1] == ["first_window.start", "first_window"]
    assert last.startswith("failed after=first_window ")
    assert last.endswith(f" error=NumericalError message={error}")


def test_a_refused_admission_before_any_phase(collected):
    error, names, last = ran(collected, lambda: plan_vector_windows(synthetic_pair()))
    assert isinstance(error, ConfigError) and names == ["failed"]
    assert last.endswith(f" error=ConfigError message={' '.join(str(error).split())}")


def finals(result):
    return {
        identity: (jax.tree.map(np.asarray, world.final.state), world.diagnostics)
        for identity, world in result.worlds.items()
    }


def test_the_records_change_no_result():
    plain = finals(run_batch_windowed(synthetic_pair(), POLICY))
    alone = jax.tree.map(np.asarray, run(synthetic_pair().worlds[0].simulation).final.state)
    with phases.enabled(io.StringIO(), logging.DEBUG):
        recorded = finals(run_batch_windowed(synthetic_pair(), POLICY))
        again = jax.tree.map(np.asarray, run(synthetic_pair().worlds[0].simulation).final.state)
    assert plain.keys() == recorded.keys()
    for identity in plain:
        (state, diagnostics), (other, others) = plain[identity], recorded[identity]
        for a, b in zip(state, other, strict=True):
            assert np.array_equal(a, b, equal_nan=True)
        assert diagnostics == others
    for a, b in zip(alone, again, strict=True):
        assert np.array_equal(a, b, equal_nan=True)
