"""The ledger protocol (docs/INNER_MODEL_V4_DESIGN.md §7.4 (p), item 5, Option A).

Every model object carries LEDGERS, LEDGER_DIAGNOSTICS, ledger_limits and ENERGY_RTOL, and the
shared check paths (surface_pump.checked_rows on the host, surface_pump_checks.row_checks on the
device) read them from the object they are given:
- every object's lists are today's, @1's own objects: @1's, @2's and @3's modules, @3's
  implementation object with and without kinds, the composite's inner adapter, and the
  composite's own (the inner's, then its operators');
- a planted object with one extra ledger is checked against its own bound on both paths, reports
  its own diagnostic and is refused by its name: the paths read the object, not @1's literals;
- ledgers=None is today's call, bit for bit, host and device, on an @1 IMEX run;
- FR-18's X2 (execution/energy_check.py, D224) switches off today's energy verdict alone, on both
  paths, by static switches (the definition's energy_check on the host, the constants' type on the
  device), at a row whose flows are 0.
"""

import dataclasses
from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.energy_check_spec import CHECK_ID, EnergyCheck
from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.energy_check import StepDoubledConstants
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.models import surface_pump, surface_pump_v2
from cells.models import surface_pump_v3 as v3
from cells.models.surface_pump_checks import row_checks
from cells.numerics import surface_imex as imex
from cells.registry.models import get_model
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


def device(spec, history, p, *, balances, magnitudes, limits, ledgers=None, constants=None):
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
    if constants is None:
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


def test_the_step_doubled_check_switches_off_todays_energy_verdict_alone(pump_run):
    """X2's static switches at @1's first row, where the flows F are 0 (the row at which a bound
    rtol x F with rtol = inf would be NaN). A planted energy residual of 1e-6 pJ, 50 times today's
    bound there, is refused by today's check on both paths. Under the switches it is evaluated and
    reported but not refused; a non-finite one still is. Honest rows give today's diagnostics and
    device values bit for bit. @1 cannot select X2 itself: it lacks the channel magnitudes the
    check reads, so it is refused at parse. (About 10 s: five small device checks, no new world.)"""
    spec, history, p = pump_run
    x2 = dataclasses.replace(spec, energy_check=EnergyCheck(CHECK_ID, 1e-2))
    today = surface_pump.device_check_constants(spec)
    switched = StepDoubledConstants(today.material_atol, today.energy_rtol, np.asarray(1e-2))
    first = type(history)(*(v[:1] for v in history))
    row = type(history)(*(v[0] for v in history))
    tol = np.asarray(spec.execution.material_balance_atol_fmol)
    rtol = surface_pump.ENERGY_RTOL[spec.execution.solver]
    flows, _ = surface_pump.ledger_limits(
        row, p, tol, rtol, steps=0, magnitudes=surface_pump.pump_magnitudes(row, p, xp=np), xp=np
    )
    assert np.all(np.asarray(flows) == 0.0)
    energy = 1 + surface_pump.LEDGERS.index("energy")  # After the domain check.

    def planted(value, base):
        return lambda row, p: base(row, p) | {"energy": 0.0 * base(row, p)["energy"] + value}

    pumps = surface_pump.pump_magnitudes
    with pytest.raises(NumericalError, match="accounting failed: energy"):
        host(spec, first, p, balances=planted(1e-6, surface_pump.balances), magnitudes=pumps)
    out = host(x2, first, p, balances=planted(1e-6, surface_pump.balances), magnitudes=pumps)
    assert out["max_energy_balance_error_pJ"] == 1e-6
    with pytest.raises(NumericalError, match="accounting failed: energy"):
        host(x2, first, p, balances=planted(np.nan, surface_pump.balances), magnitudes=pumps)
    honest = dict(balances=surface_pump.balances, magnitudes=pumps)
    assert host(x2, history, p, **honest) == host(spec, history, p, **honest)
    for value, constants, refused in (
        (1e-6, today, True),
        (1e-6, switched, False),
        (np.nan, switched, True),
    ):
        failed, values = device(
            spec,
            first,
            p,
            balances=planted(value, surface_pump.device_balances),
            magnitudes=pumps,
            limits=surface_pump.ledger_limits,
            constants=constants,
        )
        assert bool(failed[0, energy]) is refused
        assert not np.delete(failed, energy, axis=1).any()
    dev = dict(
        balances=surface_pump.device_balances,
        magnitudes=pumps,
        limits=surface_pump.ledger_limits,
    )
    failed, values = device(spec, history, p, **dev)
    failed_x2, values_x2 = device(spec, history, p, **dev, constants=switched)
    assert not failed.any() and not failed_x2.any()
    assert values.tobytes() == values_x2.tobytes()
    raw = surface_pump_fixtures.definition("release", solver=imex.ARS222_ID)
    raw["execution"]["energy_check"] = dict(check=CHECK_ID, integration_error_cap=1e-2)
    with pytest.raises(ConfigError, match="needs a model with channel_magnitudes"):
        parse_spec(raw)
