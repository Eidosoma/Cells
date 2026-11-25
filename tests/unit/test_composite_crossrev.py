"""validation/tissue/composite_crossrev.py records the constants its jaxpr texts cannot show.

jaxpr text does not print the values of an array a traced program closes over: two programs
that differ only in such a constant print identically. The cross-revision guard therefore
records each closed-over constant's dtype, shape and SHA-256 beside the text, at any depth
(jit, scan, cond), and the model's device-check constants among the bindings. compare
reports a difference in either, and says when an output recorded no constants (outputs
written before 13 November 2026).

The floor guard (validation/tissue/field_floor_guard.py) compares field solver version 3's program
and constants with version 2's; its row here is on a solve in miniature (traced only).
"""

from collections import namedtuple

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from validation.tissue import composite_crossrev as crossrev
from validation.tissue import field_floor_guard as floor_guard


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def program(values, where="jit"):
    """A traced program that closes over one array, inside jit, a scan body, a cond branch
    or a while loop's condition (where a solver's acceptance gate lives)."""
    table = np.asarray(values, dtype=np.float64)

    def f(x):
        if where == "jit":
            return jax.jit(lambda v: v + jnp.asarray(table))(x)
        if where == "scan":
            ones = x * jnp.ones(table.shape)
            body = lambda c, _: (c + jnp.asarray(table), None)  # noqa: E731
            return jax.lax.scan(body, ones, None, length=2)[0]
        if where == "while":
            gate = lambda c: jnp.any(c[1] > jnp.asarray(table))  # noqa: E731
            return jax.lax.while_loop(gate, lambda c: (c[0] + 1, c[1] * 0.5), (0, x))[0]
        return jax.lax.cond(
            x > 0, lambda v: v + jnp.asarray(table), lambda v: v * jnp.ones(table.shape), x
        )

    return jax.make_jaxpr(f)(1.0)


@pytest.mark.parametrize("kind", ["float", "array0d"])
@pytest.mark.parametrize("where", ["plain", "while"])
def test_a_one_ulp_scalar_reaches_the_text_or_the_record(kind, where):
    """A scalar such as a solver target is a literal (printed in the text, at full precision)
    or a constant (recorded): a one-ulp change must show in one of them."""

    def scalar_program(value):
        scalar = value if kind == "float" else np.asarray(value)

        def f(x):
            if where == "plain":
                return x * scalar
            gate = lambda c: c[1] > scalar  # noqa: E731
            return jax.lax.while_loop(gate, lambda c: (c[0] + 1, c[1] * 0.5), (0, x))[0]

        return jax.make_jaxpr(f)(1.0)

    target = 0.01
    a, b = scalar_program(target), scalar_program(float(np.nextafter(target, 1.0)))
    assert str(a) != str(b) or crossrev.const_record(a) != crossrev.const_record(b)
    assert crossrev.const_record(a) == crossrev.const_record(scalar_program(target))


@pytest.mark.parametrize("where", ["jit", "scan", "cond", "while"])
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


def solve(leaf, target=0.01, accept=0.01, atol=1e-3, rtol=2e-3, table=(1.0, 2.0, 3.0)):
    """A field solve in miniature: a loop to its target, the solve's own convergence and, with the
    floor leaf, version 3's acceptance test."""
    table = np.asarray(table)

    def f(x, *floor):
        scale = x * jnp.asarray(table)
        norm = lambda r: jnp.max(jnp.abs(r)) / (atol + rtol * jnp.max(scale))  # noqa: E731
        unsolved = lambda c: norm(c[1]) > target  # noqa: E731
        ok, r = jax.lax.while_loop(unsolved, lambda c: (c[0], 0.5 * c[1]), (x[0] < 9.0, scale))
        rooted = ok & (norm(r) <= accept)
        if floor:
            rooted |= jnp.all(jnp.abs(r) <= floor[0] * np.finfo(float).eps * jnp.abs(scale))
        return jnp.where(rooted, r, x), rooted

    return jax.make_jaxpr(f)(jnp.ones(3), *([np.asarray(1e3)] if leaf else []))


@pytest.mark.parametrize(
    ("plant", "named"),
    [
        ({}, None),
        (dict(target=np.nextafter(0.01, 1.0)), "0.010000000000000002"),  # In the loop only.
        (dict(accept=np.nextafter(0.01, 1.0)), "0.010000000000000002"),  # After it only.
        (dict(atol=2e-3, rtol=1e-3), "0.002"),  # Exchanged: the counts are equal.
        (dict(table=(1.0, 2.0, np.nextafter(3.0, 4.0))), "closed-over array 0"),
    ],
)
def test_the_floor_guard_compares_constants_where_they_sit(plant, named):
    two, three = solve(False), solve(True, **plant)
    program, constants, tests = floor_guard.compare_programs(two, three, [1], 0.01, gates=(1,))
    assert program["accounted"] and len(tests) == 1
    assert constants["ok"] == (named is None or "atol" in plant)
    if named is None:
        assert program["result"] == "equal" and program["slice"]["equal"]
        assert constants["literals_added"] == {f"float64 {floor_guard.EPS!r}": 1}
    else:
        assert program["result"] == "differs"
        assert any(named in d["what"] for d in program["differences"])
