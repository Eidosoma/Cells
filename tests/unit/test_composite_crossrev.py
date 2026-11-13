"""validation/tissue/composite_crossrev.py records the constants its jaxpr texts cannot show.

jaxpr text does not print the values of an array a traced program closes over: two programs
that differ only in such a constant print identically. The cross-revision guard therefore
records each closed-over constant's dtype, shape and SHA-256 beside the text, at any depth
(jit, scan, cond), and the model's device-check constants among the bindings. compare
reports a difference in either, and says when an output recorded no constants (outputs
written before 13 November 2026).
"""

from collections import namedtuple

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from validation.tissue import composite_crossrev as crossrev


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def program(values, where="jit"):
    """A traced program that closes over one array, inside jit, a scan body or a cond branch."""
    table = np.asarray(values, dtype=np.float64)

    def f(x):
        if where == "jit":
            return jax.jit(lambda v: v + jnp.asarray(table))(x)
        if where == "scan":
            ones = x * jnp.ones(table.shape)
            body = lambda c, _: (c + jnp.asarray(table), None)  # noqa: E731
            return jax.lax.scan(body, ones, None, length=2)[0]
        return jax.lax.cond(
            x > 0, lambda v: v + jnp.asarray(table), lambda v: v * jnp.ones(table.shape), x
        )

    return jax.make_jaxpr(f)(1.0)


@pytest.mark.parametrize("where", ["jit", "scan", "cond"])
def test_text_omits_a_constant_that_the_record_keeps(where):
    a, b = program([1.0, 2.0, 3.0], where), program([1.0, 2.0, 4.0], where)
    assert str(a) == str(b)  # The reason the constants are recorded at all.
    assert crossrev.const_record(a) != crossrev.const_record(b)
    assert crossrev.const_record(a) == crossrev.const_record(program([1.0, 2.0, 3.0], where))
    found = crossrev.closed_consts(a)
    assert found and all(np.array_equal(np.ravel(c), [1.0, 2.0, 3.0]) for c in found)


def test_check_constants_are_named_bindings():
    Checks = namedtuple("Checks", "tolerance target")

    class Model:
        @staticmethod
        def device_check_constants(spec):
            return Checks(np.full(4, 1e-10), 0.002)

    rows = crossrev.check_constants(Model, None)
    assert [name for name, _ in rows] == ["tolerance", "target"]
    assert np.array_equal(rows[0][1], np.full(4, 1e-10)) and rows[1][1] == 0.002
    assert crossrev.check_constants(object(), None) == []


def write(directory, closed, *, record=True, tolerance=1e-10):
    directory.mkdir()
    (directory / "w.checked_step.txt").write_text(str(closed))
    if record:
        (directory / "w.checked_step.consts.json").write_text(crossrev.const_record(closed))
    arrays = {"state.amount": np.ones(3), "check.tolerance": np.full(4, tolerance)}
    np.savez(directory / "w.npz", **arrays)
    return directory


def test_compare_catches_a_constant_and_a_check_constant(tmp_path, capsys):
    a, b = program([1.0, 2.0, 3.0]), program([1.0, 2.0, 4.0])
    reference = write(tmp_path / "reference", a)
    assert crossrev.compare(reference, write(tmp_path / "same", a))
    assert not crossrev.compare(reference, write(tmp_path / "constant", b))
    assert not crossrev.compare(reference, write(tmp_path / "check", a, tolerance=2e-10))
    out = capsys.readouterr().out
    assert "w.checked_step.consts.json DIFFERS" in out
    assert "w.npz DIFFERS ['check.tolerance']" in out
    assert "summary jaxpr texts 1 of 1 identical, constants 0 of 1 identical" in out


def test_compare_names_outputs_without_constants(tmp_path, capsys):
    a = program([1.0, 2.0, 3.0])
    old = write(tmp_path / "old", a, record=False)
    older = write(tmp_path / "older", a, record=False)
    new = write(tmp_path / "new", a)
    assert crossrev.compare(old, older)
    out = capsys.readouterr().out
    assert "constants not recorded on either side for 1 texts" in out
    assert "verdict identical (texts and bindings; constants not recorded)" in out
    assert not crossrev.compare(old, new) and not crossrev.compare(new, old)
    assert "w.checked_step.consts.json DIFFERS (one side)" in capsys.readouterr().out
