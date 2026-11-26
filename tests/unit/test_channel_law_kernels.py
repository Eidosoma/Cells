"""Gated channel laws, as kernels: pinned native functions, Decimal references and exact clamps.

The kernel rows of three tissue tests and of the 56-law catalogue's test, which left with the older
tissues (25 November 2026): Kv1.5 and Kir2.1 (potassium_channels), Nav1.2 (sodium_channels), HCN1, 2
and 4 (hcn_channels), and the three further HCN laws (hcn_extra_channels), which no host runs today.
BETSE is run out of process, in its own environment, and only by the native rows.

And Kv1.5's own module (kv1p5_mh.py) at the 19 voltages of an older family's cases, its declared
test (D196's safeguard): its kernels meet the independent SI decimals
(validation/betse/voltage_gate_audit/gate_independent.py), in NumPy and compiled (planted: each of
the eight coefficients moved by a part in 10^9, and m h^2 for m h).
"""

import functools
import json
import subprocess
import types
from decimal import localcontext
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.laws.channels import (
    hcn_channels,
    hcn_extra_channels,
    kv1p5_mh,
    potassium_channels,
    sodium_channels,
)
from validation.betse.voltage_gate_audit import gate_independent
from validation.channels import hcn_extra_reference
from validation.tissue import hcn_reference, kir_reference, sodium_reference

ROOT = Path(__file__).resolve().parents[2]
CHANNELSABC = "ed3e6395ec844108be7b585fd1007a9e22e899ff13df964fc1a3b14e5bf944d4"
NATIVE = dict(rtol=5e-14, atol=5e-15)
DECIMAL = dict(rtol=3e-14, atol=3e-15)
close = np.testing.assert_allclose


def native(script, source, sha256, tmp_path):
    """One capture by a pinned native script, with BETSE's own file hashes checked."""
    output = tmp_path / "native.json"
    run = subprocess.run(
        [
            "/mnt/workspaces/Cells/venv-betse/bin/python",
            "-B",
            str(ROOT / "validation/betse" / script),
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert run.returncode == 0, run.stderr[-2000:]
    value = json.loads(output.read_text())
    assert value["version"] == "1.5.0"
    assert value["source_sha256"] == {source: sha256, "channelsabc.py": CHANNELSABC}
    return value


def follow_native_clock(channels, codes, trace, voltages):
    """The native semi-implicit gate clock, replayed on this kernel; no tissue, no RK4."""
    gates = np.broadcast_to(np.asarray([[0.2], [0.7]]), (2, codes.size)).copy()
    dt = trace["dt_s"]
    for voltage, expected, opened in zip(voltages, trace["gates"], trace["opening"], strict=True):
        target, tau = channels.kinetics(np.asarray(voltage), codes, xp=np)
        gates = (gates * tau + dt * target) / (tau + dt)
        close(gates, expected, **NATIVE)
        close(channels.opening(gates, codes, xp=np), opened, **NATIVE)


def clamp_errors(kinetics, voltage, duration, steps):
    """RK4 at a held voltage against the exact exponential, at each step size."""
    target, tau = (np.asarray(v) for v in kinetics(voltage))
    gates = np.broadcast_to(np.asarray([[0.2], [0.7]]), target.shape)
    expected = target + (gates - target) * np.exp(-duration / tau)
    errors = []
    for dt in steps:

        def solve(g, v, dt=dt):
            wanted, decay = kinetics(v)

            def step(old, _):
                k1 = (wanted - old) / decay
                k2 = (wanted - old - dt * k1 / 2) / decay
                k3 = (wanted - old - dt * k2 / 2) / decay
                k4 = (wanted - old - dt * k3) / decay
                return old + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6, None

            return jax.lax.scan(step, g, None, length=round(duration / dt))[0]

        errors.append(float(np.max(np.abs(jax.jit(solve)(gates, voltage) - expected))))
    return errors


def test_kv1p5_and_kir2p1_follow_the_native_laws_and_clock(tmp_path):
    value = native(
        "potassium_native.py",
        "vg_k.py",
        "89412aff6163dfe4ccf61afb82418a788ff8e10fbe2ec8cda24c498316b4842f",
        tmp_path,
    )
    v = np.asarray(value["voltage_V"])
    for code, name in enumerate(("Kv1p5", "Kir2p1")):
        row, codes = value["laws"][name], np.full(v.shape, code, dtype=np.int64)
        target, tau = jax.jit(potassium_channels.kinetics)(v, codes)
        for actual, key in ((target, "target"), (target, "initial"), (tau, "tau_s")):
            close(actual, row[key], **NATIVE)
        assert row["powers"] == [1, 1 + code]
        for trace in row["traces"]:
            follow_native_clock(potassium_channels, codes, trace, trace["voltages_V"])


def kv1p5_errors(kinetics, opening=kv1p5_mh.opening):
    """Where Kv1.5's kernels leave the independent decimals at 19 voltages (empty: they keep them).

    The bound is relative, with no absolute part: h's target falls to 4e-11 at 60 mV. The largest
    distance measured is 3.8e-15.
    """
    voltage = np.linspace(-0.12, 0.06, 19)
    with localcontext() as context:
        context.prec = 50
        rows = [gate_independent.kinetics(float(v)) for v in voltage]
    gates = np.stack((np.linspace(0.0, 1.0, 19), np.linspace(1.0, 0.0, 19)))
    found = dict(zip(("target", "tau"), kinetics(voltage), strict=True))
    wanted = {
        name: np.asarray([[float(x) for x in row[i]] for row in rows]).T
        for i, name in enumerate(found)
    }
    found["opening"], wanted["opening"] = opening(gates, xp=np), gates[0] * gates[1]
    return [k for k, v in found.items() if not np.allclose(v, wanted[k], rtol=1e-14, atol=0)]


def test_kv1p5_meets_the_independent_decimals_and_each_plant_misses_them():
    kinetics = functools.partial(kv1p5_mh.kinetics, xp=np)
    assert kv1p5_errors(kinetics) == [] and kv1p5_errors(jax.jit(kv1p5_mh.kinetics)) == []
    # Planted: one constant of the kernel moved, the module untouched.
    code = kv1p5_mh.kinetics.__code__
    for name, coefficients in (
        ("target", (0.0060, 0.0064, 0.0253, 0.0035)),
        ("tau", (0.008330, 0.1163, 1.620000, 15.500)),
    ):
        for moved in coefficients:
            assert code.co_consts.count(moved) == 1
            constants = tuple(c * (1 + 1e-9) if c == moved else c for c in code.co_consts)
            planted = types.FunctionType(
                code.replace(co_consts=constants), kv1p5_mh.kinetics.__globals__
            )
            assert kv1p5_errors(functools.partial(planted, xp=np)) == [name], moved
    squared = lambda gates, *, xp: gates[..., 0, :] * gates[..., 1, :] ** 2  # noqa: E731
    assert kv1p5_errors(kinetics, squared) == ["opening"]  # Planted: Kir2.1's power.


def test_kir2p1_matches_its_reference_and_an_exact_clamp():
    voltage = np.linspace(-0.120, 0.060, 37)
    target, tau = potassium_channels.kir2p1_kinetics(voltage, xp=np)
    for i, v in enumerate(voltage):
        wanted = kir_reference.kinetics(float(v))
        close(target[:, i], [float(x) for x in wanted[0]], **DECIMAL)
        close(tau[:, i], [float(x) for x in wanted[1]], **DECIMAL)
    gates = np.asarray([[0.2, 0.2], [0.7, 0.7]])
    close(potassium_channels.opening(gates, np.asarray([0, 1]), xp=np), [0.14, 0.098], rtol=1e-15)
    errors = clamp_errors(
        potassium_channels.kir2p1_kinetics, voltage, 0.002, (25e-6, 12.5e-6, 6.25e-6)
    )
    assert errors[0] < 1e-8 and errors[-1] <= max(errors[0] * 0.02, 2e-14)


def test_nav1p2_follows_the_native_law_and_clock(tmp_path):
    value = native(
        "sodium_native.py",
        "vg_na.py",
        "6faa67bdc4bfd0ee35dc1cc0fd8dcd73a703ff58120d1b1968da94dac1fe8831",
        tmp_path,
    )
    assert value["powers"] == [3, 1]
    v = np.asarray(value["voltage_V"])
    codes = np.full(v.shape, 2, dtype=np.int64)
    target, tau = (np.asarray(x) for x in jax.jit(sodium_channels.kinetics)(v, codes))
    source_target, source_tau = sodium_reference.source_float_parameters(v)
    decimal_target, decimal_tau = (
        np.asarray([[float(x) for x in sodium_reference.kinetics(float(u))[i]] for u in v]).T
        for i in (0, 1)
    )
    # Near a removable zero the native 1 - exp subtraction loses precision: this kernel is held to
    # the Decimal value there, and the native value to its own float arithmetic.
    distances = np.abs(
        (v[:, None] - np.asarray([-0.025, -0.040, -0.065000123]))
        / np.asarray([0.009, 0.005, 0.005])
    )
    regular = np.all(distances >= 1e-4, axis=1)
    assert np.count_nonzero(~regular) == 1
    close(target, decimal_target, **DECIMAL)
    close(tau, decimal_tau, **DECIMAL)
    for actual, source_value, key in (
        (target, source_target, "target"),
        (target, source_target, "initial"),
        (tau, source_tau, "tau_s"),
    ):
        wanted = np.asarray(value[key])
        close(source_value, wanted, **NATIVE)
        close(actual[:, regular], wanted[:, regular], **NATIVE)
    for trace in value["traces"]:
        follow_native_clock(sodium_channels, codes, trace, trace["voltages_V"])
    finite = np.asarray(value["singular_probes"]["finite"])
    assert not finite[0, 0] and not finite[2, 0]
    assert not finite[3, 1] and not finite[3, 2]


def test_nav1p2_limits_gate_power_and_an_exact_clamp():
    centers = np.asarray([-0.025, -0.040, -0.065000123])
    voltage = np.unique(
        np.r_[np.linspace(-0.120, 0.060, 37), centers, centers - 1e-12, centers + 1e-12]
    )
    target, tau = sodium_channels.nav1p2_kinetics(voltage, xp=np)
    for i, v in enumerate(voltage):
        wanted = sodium_reference.kinetics(float(v))
        close(target[:, i], [float(x) for x in wanted[0]], **DECIMAL)
        close(tau[:, i], [float(x) for x in wanted[1]], **DECIMAL)
    assert np.all(tau > 0) and np.all((target >= 0) & (target <= 1))
    limits = jax.jit(sodium_channels.nav1p2_kinetics)(centers)
    derivatives = jax.jit(jax.jacfwd(sodium_channels.nav1p2_kinetics))(centers)
    assert all(np.all(np.isfinite(v)) for v in (*limits, *derivatives))
    for got, wanted in zip(limits, sodium_channels.nav1p2_kinetics(centers, xp=np), strict=True):
        close(got, wanted, **DECIMAL)
    gates = np.asarray([[0.2, 0.2, 0.2], [0.7, 0.7, 0.7]])
    close(
        sodium_channels.opening(gates, np.asarray([0, 1, 2]), xp=np),
        [0.14, 0.098, 0.0056],
        rtol=1e-15,
    )
    errors = clamp_errors(
        sodium_channels.nav1p2_kinetics, voltage, 0.002, (2.5e-6, 1.25e-6, 0.625e-6)
    )
    assert errors[0] < 1e-8 and errors[-1] <= max(errors[0] * 0.02, 2e-14)


def test_hcn1_2_4_follow_the_native_laws_and_clock(tmp_path):
    value = native(
        "hcn_native.py",
        "vg_funny.py",
        "254f2176e0b86906ae445fdd297750ad0b68cc9bd22da11d05437e6f9824cde7",
        tmp_path,
    )
    v = np.asarray(value["voltage_V"])
    for family, code in ((1, 3), (2, 4), (4, 5)):
        row, codes = value["families"][str(family)], np.full(v.shape, code, np.int64)
        assert row["powers"] == [1, 0] and row["time_unit"] == 1000
        assert row["ions"] == ["Na", "K", "Ca"]
        assert row["relative_permeability"] == [0.2, 1.0, 0.05]
        target, tau = jax.jit(hcn_channels.kinetics)(v, codes)
        decimal_target, decimal_tau = (
            np.asarray([[float(x) for x in hcn_reference.kinetics(u, family)[i]] for u in v]).T
            for i in (0, 1)
        )
        for actual, wanted in (
            (target, row["initial"]),
            (target, row["target"]),
            (tau, row["tau_s"]),
            (target, decimal_target),
            (tau, decimal_tau),
        ):
            close(actual, wanted, **NATIVE)
        for trace in row["traces"]:
            follow_native_clock(hcn_channels, codes, trace, trace["voltage_V"])


# Codes 3, 4 and 5 are HCN1, 2 and 4; 54 and 55 are the two cAMP-shifted laws. Each opens as m
# alone, so h must not act.
@pytest.mark.parametrize(
    "channels,codes", [(hcn_channels, (3, 4, 5)), (hcn_extra_channels, (54, 55))], ids=["m", "camp"]
)
def test_hcn_clamps_shared_gate_power_and_sign(channels, codes):
    voltage = np.tile(np.linspace(-0.12, 0.06, 31), len(codes))
    laws = np.repeat(np.array(codes), 31)
    errors = clamp_errors(
        lambda v: channels.kinetics(v, laws), voltage, 0.2, (0.001, 0.0005, 0.00025)
    )
    assert errors[0] < 1e-8 and errors[-1] <= max(errors[0] * 0.02, 2e-14)
    _, derivative = jax.jvp(
        lambda v: channels.kinetics(v, laws)[0], (voltage,), (np.ones_like(voltage),)
    )
    assert np.isfinite(derivative).all() and np.all(np.asarray(derivative)[0] < 0)
    gates = np.full(voltage.shape, 0.2)
    for h in (0.0, 0.3, 1.0):
        np.testing.assert_array_equal(
            channels.opening(np.stack((gates, np.full_like(voltage, h))), laws, xp=np), gates
        )


@pytest.mark.parametrize(
    "law,name",
    list(
        zip(
            ("cells.channel.hcn_leak_open@1", "cells.channel.hcn2_camp_m@1", "cells.channel.hcn4_camp_m@1"),
            hcn_extra_reference.CLASSES,
            strict=True,
        )
    ),
)
def test_further_hcn_laws_match_their_reference(law, name):
    voltage = np.linspace(-0.120, 0.060, 37)
    codes = np.full(voltage.shape, hcn_extra_channels.LAW_CODES[law])
    assert (
        hcn_extra_channels.LAW_PERMEABILITIES[law]
        == (hcn_extra_reference.RELATIVE_PERMEABILITY[name])
    )
    gates = np.broadcast_to(np.asarray([[0.2], [0.7]]), (2, voltage.size))
    for xp in (np, jax.numpy):
        target, tau = hcn_extra_channels.kinetics(voltage, codes, xp=xp)
        first = hcn_extra_channels.initial_gates(voltage, codes, xp=xp)
        opened = hcn_extra_channels.opening(gates, codes, xp=xp)
        close(opened, [hcn_extra_reference.opening(g, name) for g in gates.T], **DECIMAL)
        if name == "HCNLeak":
            # It owns no gate here, so its slots are exact zeros; the native h and m, which its
            # reference keeps, never reach its opening of one.
            assert hcn_extra_channels.STATE_COUNTS[law] == 0
            for absent in (target, tau, first, hcn_extra_channels.gate_active(codes, xp=xp)):
                np.testing.assert_array_equal(absent, 0)
            continue
        wanted = [hcn_extra_reference.kinetics(float(v), name) for v in voltage]
        close(target, np.asarray([w[0] for w in wanted]).T, **DECIMAL)
        close(tau, np.asarray([w[1] for w in wanted]).T, **DECIMAL)
        initial = [hcn_extra_reference.initial_gates(float(v), name) for v in voltage]
        close(first, np.asarray(initial).T, **DECIMAL)
        # HCN4's initial shift is -20 mV and its update's -24 mV; HCN2 has one.
        assert bool(np.all(np.asarray(first)[0] < np.asarray(target)[0])) == (name == "HCN4_cAMP")
