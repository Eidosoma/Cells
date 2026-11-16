"""The ledger protocol (docs/INNER_MODEL_V4_DESIGN.md §7.4 (p), item 5, Option A).

Every model object carries LEDGERS, LEDGER_DIAGNOSTICS, ledger_limits and ENERGY_RTOL, and the
shared check paths (surface_pump.checked_rows on the host, surface_pump_checks.row_checks on the
device) read them from the object they are given:
- every object's lists are today's, @1's own objects: @1's, @2's and @3's modules, @3's
  implementation object with and without kinds, the composite's inner adapter, and the
  composite's own (the inner's, then its operators');
- a planted object with one extra ledger is checked against its own bound on both paths, reports
  its own diagnostic and is refused by its name: the paths read the object, not @1's literals;
- ledgers=None is today's call, bit for bit, host and device, on an @1 IMEX run.
"""

from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.core import pump_composite_spec as cs
from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models import surface_pump, surface_pump_v2
from cells.models import surface_pump_v3 as v3
from cells.models.registry import get_model
from cells.models.surface_pump_checks import row_checks
from cells.numerics import surface_imex as imex
from validation.tissue import pump_water_fixtures as water_fixtures
from validation.tissue import surface_pump_fixtures

NAMES = ("LEDGERS", "LEDGER_DIAGNOSTICS", "ledger_limits", "ENERGY_RTOL")


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


@pytest.fixture(scope="module")
def pump_run():
    """@1's release arm under ARS(2,2,2), a few rows (as test_surface_pump_device_checks)."""
    raw = surface_pump_fixtures.definition("release", solver=imex.ARS222_ID)
    raw["experiment"]["end_time"] = 0.0012
    raw["experiment"]["observation_times"] = [0.0, 0.0012]
    spec = parse_spec(raw)
    value = run(spec)
    history = surface_pump.STATE_TYPE(*(np.asarray(v) for v in value.history))
    _, p = surface_pump.initial_values(spec)
    return spec, history, p


def test_every_model_object_carries_todays_lists():
    raw = water_fixtures.heredity_cell("D", end_time=0.004)
    impl = get_model(parse_spec(raw).model)
    composite = get_model(parse_spec(cs.frozen_definition(raw)).model)
    from validation.compartment_ph_engine import definitions as defs

    kind_world = defs.development_world(defs.fr4_world())
    kind_world["model"].pop("transporters")
    kinds = get_model(parse_spec(kind_world).model)
    assert kinds.structure.kinds
    for model in (surface_pump, surface_pump_v2, v3, impl, kinds, composite.inner):
        for name in NAMES:
            assert getattr(model, name) is getattr(surface_pump, name), (model, name)
        assert model.DEVICE_CHECKS == ("domain", *surface_pump.LEDGERS, "dissipation"), model
    assert composite.LEDGERS[: len(surface_pump.LEDGERS)] == surface_pump.LEDGERS
    assert composite.ENERGY_RTOL is surface_pump.ENERGY_RTOL


def planted(extra_value):
    """@1's lists with one extra ledger, "planted", whose value is extra_value(row) and whose bound
    is 1e-9; its balances and bounds wrap @1's (host: numpy; device: jax.numpy)."""

    def limits(row, p, tol, rtol, *, steps, magnitudes, xp=np):
        flows, bounds = surface_pump.ledger_limits(
            row, p, tol, rtol, steps=steps, magnitudes=magnitudes[:-1], xp=xp
        )
        return flows, (*bounds, 1e-9)

    def magnitudes(row, p, *, xp=np):
        return (*surface_pump.pump_magnitudes(row, p, xp=xp), None)

    def balances(row, p):
        return surface_pump.balances(row, p) | {"planted": extra_value(row)}

    def device_balances(row, p):
        return surface_pump.device_balances(row, p) | {"planted": extra_value(row)}

    ledgers = SimpleNamespace(
        LEDGERS=(*surface_pump.LEDGERS, "planted"),
        LEDGER_DIAGNOSTICS=(*surface_pump.LEDGER_DIAGNOSTICS, "planted_error"),
        ledger_limits=limits,
        ENERGY_RTOL=surface_pump.ENERGY_RTOL,
    )
    return ledgers, balances, device_balances, magnitudes


def host(spec, history, p, *, balances, magnitudes, ledgers=None):
    return surface_pump.checked_rows(
        history,
        spec,
        p,
        domain=surface_pump.domain_valid,
        balances=balances,
        magnitudes=magnitudes,
        dissipation=surface_pump.DISSIPATION_FIELDS,
        steps=np.arange(len(history.amount_increment)),
        ledgers=ledgers,
    )


def device(spec, history, p, *, balances, magnitudes, limits, ledgers=None):
    previous = type(history)(*(np.concatenate((v[:1], v[:-1])) for v in history))

    def one(previous, row, p, constants, steps):
        return row_checks(
            previous,
            row,
            p,
            constants,
            steps,
            domain_valid=surface_pump.domain_valid,
            balances=balances,
            limits=limits,
            magnitudes=magnitudes,
            dissipation=surface_pump.DISSIPATION_FIELDS,
            ledgers=ledgers,
        )

    checks = jax.jit(jax.vmap(one, in_axes=(0, 0, None, None, 0)))
    steps = np.arange(len(history.amount_increment))
    constants = surface_pump.device_check_constants(spec)
    failed, values = checks(previous, history, p, constants, steps)
    return np.asarray(failed), np.asarray(values)


def test_a_planted_ledger_is_checked_through_the_object(pump_run):
    """One extra ledger on a planted object: within its bound it is reported as its own
    diagnostic; beyond it, the host refuses by its name and the device marks its own check (after
    domain and @1's ten ledgers, before dissipation)."""
    spec, history, p = pump_run
    for value, refused in ((0.0, False), (1e-6, True)):
        ledgers, balances, device_balances, magnitudes = planted(
            lambda row, value=value: np.full(1, value)
        )
        if refused:
            with pytest.raises(NumericalError, match="accounting failed: planted"):
                host(spec, history, p, balances=balances, magnitudes=magnitudes, ledgers=ledgers)
        else:
            out = host(spec, history, p, balances=balances, magnitudes=magnitudes, ledgers=ledgers)
            assert out["max_planted_error"] == 0.0
            assert list(out)[: len(ledgers.LEDGER_DIAGNOSTICS)] == [
                "max_" + k for k in ledgers.LEDGER_DIAGNOSTICS
            ]
        failed, values = device(
            spec,
            history,
            p,
            balances=device_balances,
            magnitudes=magnitudes,
            limits=ledgers.ledger_limits,
            ledgers=ledgers,
        )
        assert failed.shape[1] == len(ledgers.LEDGERS) + 2  # domain, the ledgers, dissipation.
        planted_check = 1 + ledgers.LEDGERS.index("planted")
        assert bool(failed[:, planted_check].all()) is refused
        assert not np.delete(failed, planted_check, axis=1).any()
        assert np.all(values[:, len(ledgers.LEDGERS) - 1] == value)  # Its own diagnostic.


def test_no_object_is_todays_call_bit_for_bit(pump_run):
    spec, history, p = pump_run
    kwargs = dict(balances=surface_pump.balances, magnitudes=surface_pump.pump_magnitudes)
    today = host(spec, history, p, **kwargs)
    assert host(spec, history, p, **kwargs, ledgers=surface_pump) == today
    assert surface_pump.check_values(history, spec, steps=np.arange(len(history.pump_cycles))) == (
        today
    )
    dev = dict(
        balances=surface_pump.device_balances,
        magnitudes=surface_pump.pump_magnitudes,
        limits=surface_pump.ledger_limits,
    )
    failed, values = device(spec, history, p, **dev)
    failed_object, values_object = device(spec, history, p, **dev, ledgers=surface_pump)
    assert not failed.any()
    assert failed.tobytes() == failed_object.tobytes()
    assert values.tobytes() == values_object.tobytes()
