"""Compiled runs of local_species_reactions@1 (D152 version 1, milestone 2; design §4.5, §6.5, §11).

The species-only worlds of validation/tissue/species_reactions_fixtures, through the runner, the
composite's compiled step and its host and device checks:
* idle claim 2 against the live half-step: every multiplier zero, and a network with no reactions
  (statically idle), give every field, observation and diagnostic of the composition without the
  operator bitwise, with the operator's own fields all zero;
* benign padding (the lead's ruling Q11 (a)): with every law and both factor kinds present and
  padded cell, outside and factor slots, the half-step evaluated eagerly in JAX under jax_debug_nans
  and jax_debug_infs (every primitive's output checked) raises nothing, the jitted half-step's
  outputs are finite, and a planted zero padding raises;
* the stage condition through the compiled step: admitted at dt L <= 1, refused beyond it with the
  start state kept bit for bit (refused, never repaired);
* restart before, at and after a multiplier change, in process and through a written snapshot
  loaded in a fresh process, bitwise;
* a vector-window batch (device row checks: the compiled ledger and magnitude terms) mixing every
  per-world parameter and multiplier: bitwise against the reversed batch, each world within 1e-12
  of its scalar run, and each world's device energy diagnostic equal to the host checks' to the
  rounding of their terms;
* the device row checks' negative controls at the species' scale (local, energy, dissipation).
A few minutes of compiles; the tier-1 tests are test_species_reactions*.py without _runs/_guards.
"""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import pump_composite_spec as cs
from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models.operators import species_reactions as sr
from cells.models.registry import get_model
from validation.tissue import species_reactions_fixtures as rfx

jax.config.update("jax_enable_x64", True)

END = 0.004
NAMES = ("binding", "catalysis", "conversion", "supply", "removal")
ZERO = dict.fromkeys(NAMES, 0.0)
ROOT = Path(__file__).resolve().parents[2]


def world(multipliers):
    return rfx.enzyme_network(multipliers, end=END, observation_times=[0.0, 0.002, END])


def bits(value):
    return np.asarray(value).tobytes()


def assert_same_as_plain(result, plain):
    for name in type(plain.history)._fields:
        assert bits(getattr(result.history, name)) == bits(getattr(plain.history, name)), name
    for name in sr.STATE_AXES:
        assert not np.any(np.asarray(getattr(result.history, name))), name
    for name, value in vars(plain.observations).items():
        assert bits(getattr(result.observations, name)) == bits(value), name
    for name, value in plain.diagnostics.items():
        assert result.diagnostics[name] == value, name


def test_zero_multipliers_equal_the_composition_without_the_operator():
    raw = world(ZERO)
    plain = run(parse_spec(rfx.without_reactions(raw)))
    assert_same_as_plain(run(parse_spec(raw)), plain)
    empty = copy.deepcopy(raw)
    next(b for b in empty["model"]["operators"] if b["law"] == rfx.REACTIONS)["reactions"] = []
    empty["experiment"]["reaction_controls"] = []
    assert_same_as_plain(run(parse_spec(empty)), plain)


# ------------------------------------------------------------------ benign padding (Q11 (a))


def padded():
    raw = rfx.two_factor_network(c0=0.5)
    raw["execution"]["capacity"] += 1
    raw["execution"]["extracellular_capacity"] += 1
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    return spec, model, model.operators[0], type(state)(*(jnp.asarray(v) for v in state)), p


def test_every_unused_branch_and_padded_entry_stays_finite_in_jax():
    spec, model, op, state, p = padded()
    assert np.asarray(p.reaction_factor_kind).shape == (5, 2)
    m = jnp.ones(5)
    control = SimpleNamespace(reaction_multiplier=m)
    with jax.debug_nans(True), jax.debug_infs(True):  # Eager: every primitive's output checked.
        terms = sr.half_step_terms(state, m, 1e-3, p, xp=jnp)
        new, ok = op.half_step(state, 1e-3, control, p, xp=jnp)
    assert bool(ok) and bool(terms.valid)
    compiled = jax.jit(
        lambda s, m: op.half_step(s, 1e-3, SimpleNamespace(reaction_multiplier=m), p, xp=jnp)
    )
    jitted, ok = compiled(state, m)
    assert bool(ok)
    for name, value in (
        *terms._asdict().items(),
        *new._asdict().items(),
        *jitted._asdict().items(),
    ):
        assert np.all(np.isfinite(np.asarray(value, dtype=float))), name
    kind = np.asarray(p.reaction_factor_kind)
    planted = p._replace(
        reaction_factor_half_saturation_mM=np.where(
            kind == 0, 0.0, p.reaction_factor_half_saturation_mM
        )
    )
    with jax.debug_nans(True), jax.debug_infs(True), pytest.raises(FloatingPointError):
        sr.half_step_terms(state, m, 1e-3, planted, xp=jnp)


# ------------------------------------------------------------------ the stage condition


def test_the_compiled_step_refuses_beyond_dt_L_of_one_and_keeps_its_start_state():
    """A first-order conversion at k = 10/s in the face-free world: dt L = 0.98 is admitted and
    1.02 refused, the start state returned bit for bit (§4.2: refused, never repaired)."""
    cell = {"cells": ["cell_0"]}
    raw = rfx.face_free_network(
        ("P",),
        [rfx.species("S", moieties={"X": 1}), rfx.species("P", moieties={"X": 1})],
        [rfx.mass_action("convert", cell, {"S": 1}, {"P": 1}, 10.0)],
        rfx.always(["convert"]),
        profile=dict(S=dict(cell_0=1e-3), P=dict(cell_0=1e-6)),
        end=0.2,
        dt=0.1,
    )
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    controls = cs.control_values(spec, [0.0])
    control = type(controls)(*(jnp.asarray(v[0]) for v in controls))
    step = jax.jit(lambda x, c, dt: model.checked_step(x, dt, c, p, p.active))
    moved, ok = step(state, control, jnp.asarray(0.098))
    assert bool(ok)
    assert float(np.asarray(moved.reaction_extent_fmol)[0]) > 0
    refused, ok = step(state, control, jnp.asarray(0.102))
    assert not bool(ok)
    for a, b in zip(refused, state, strict=True):
        assert bits(a) == bits(b)
    report = sr.stage_report(state, control, p, 0.102)
    assert not report["admitted"] and report["max_hL"] == pytest.approx(0.51, rel=1e-9)
    with pytest.raises(NumericalError, match="no invalid step accepted"):
        run(
            parse_spec(
                rfx.face_free_network(
                    ("P",),
                    [rfx.species("S", moieties={"X": 1}), rfx.species("P", moieties={"X": 1})],
                    [rfx.mass_action("convert", cell, {"S": 1}, {"P": 1}, 10.2)],
                    rfx.always(["convert"]),
                    profile=dict(S=dict(cell_0=1e-3), P=dict(cell_0=1e-6)),
                    end=0.2,
                    dt=0.1,
                )
            )
        )


# ------------------------------------------------------------------ restart


SWITCH = [(0.0, 1.0), (0.02, 0.0), (0.03, 1.0)]  # The catalysis off from 20 to 30 ms.


def switched():
    return rfx.enzyme_recipe(
        None,
        resolved=True,
        catalysis=SWITCH,
        end=0.05,
        dt=1e-3,
        observation_times=[0.0, 0.01, 0.02, 0.025, 0.03, 0.04, 0.05],
    )


FRESH = """
import json, sys
import numpy as np
from cells.core.runner import run
from cells.io import load_snapshot
loaded = load_snapshot(sys.argv[1])
result = run(loaded.spec, loaded.checkpoint)
np.savez(sys.argv[2], **{k: np.asarray(v) for k, v in result.history._asdict().items()})
print(json.dumps(dict(start=int(loaded.checkpoint.step_index))))
"""


def test_restart_around_a_multiplier_change_is_bitwise_in_process_and_in_a_fresh_one(tmp_path):
    from cells.io import write_snapshot

    spec = parse_spec(switched())
    result = run(spec)
    for t in (0.01, 0.02, 0.025, 0.03, 0.04):
        checkpoint = result.checkpoint_at(t)
        resumed = run(spec, checkpoint)
        for a, b in zip(resumed.history, result.history, strict=True):
            assert bits(a) == bits(np.asarray(b)[checkpoint.step_index :]), t
    checkpoint = result.checkpoint_at(0.02)
    write_snapshot(tmp_path / "checkpoint", result.spec, checkpoint)
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), JAX_ENABLE_X64="1", JAX_PLATFORMS="cpu")
    done = subprocess.run(
        [sys.executable, "-B", "-c", FRESH, str(tmp_path / "checkpoint"), str(tmp_path / "h.npz")],
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    start = json.loads(done.stdout.strip().splitlines()[-1])["start"]
    assert start == checkpoint.step_index
    fresh = np.load(tmp_path / "h.npz")
    for name, value in result.history._asdict().items():
        assert bits(fresh[name]) == bits(np.asarray(value)[start:]), name


# ------------------------------------------------------------------ a vector batch


def variant(scale, mu, c0, multipliers):
    """The enzyme network with every rate and K_M scaled, other potentials, c0 and multipliers."""
    raw = rfx.two_factor_network(
        multipliers=dict(zip(NAMES, multipliers, strict=True)), c0=c0, mu=mu, end=0.01
    )
    for reaction in raw["model"]["operators"][0]["reactions"]:
        for key in ("rate_constant", "forward_rate_per_s", "catalytic_rate_per_s", "saturation_mM"):
            if key in reaction:
                reaction[key] *= scale
        for factor in reaction["factors"]:
            factor["half_saturation_mM"] *= scale
            factor["hill_coefficient"] *= 1 + 0.1 * (scale - 1)
    raw["experiment"]["observation_times"] = [0.0, 0.005, 0.01]
    return raw


def test_a_vector_batch_mixes_every_per_world_parameter_and_multiplier():
    from cells.core.batch import BatchSpec, WorldSpec
    from cells.core.vector_windows import run_vector_windowed
    from cells.core.windows import WindowPolicy

    raws = [
        variant(1.0, (0.0, 0.0, -2.0, -1.0), 1.0, (1.0, 1.0, 1.0, 1.0, 1.0)),
        variant(1.7, (0.3, -0.2, -1.5, -0.5), 0.5, (2.0, 0.5, 1.5, 0.0, 1.0)),
        variant(0.6, (-0.4, 0.1, -2.5, -1.2), 2.0, (0.7, 1.3, 0.0, 2.0, 0.4)),
    ]
    specs = [parse_spec(r) for r in raws]
    model = get_model(specs[0].model)
    assert all(
        model.batch_signature(s.model) == model.batch_signature(specs[0].model) for s in specs
    )

    def batch(order):
        worlds = tuple(WorldSpec(i + 1, specs[j]) for i, j in enumerate(order))
        return run_vector_windowed(
            BatchSpec(worlds, len(worlds), 10**6, 2**31), WindowPolicy(4, "checkpoints")
        )

    forward, backward = batch([0, 1, 2]), batch([2, 1, 0])
    for k, spec in enumerate(specs):
        final = forward.worlds[k + 1].final.state
        for a, b in zip(final, backward.worlds[3 - k].final.state, strict=True):
            assert bits(a) == bits(b), k
        single = run(spec)
        history = single.history
        for name in type(final)._fields:
            a, b = np.asarray(getattr(final, name)), np.asarray(getattr(history, name))[-1]
            scale = np.max(np.abs(b), initial=0.0)
            if name.endswith(("_work_pJ", "_dissipated_energy_pJ", "_standard_energy_pJ")):
                partner = name.replace("_work_pJ", "_energy_magnitude_pJ")
                partner = partner.replace("_dissipated_energy_pJ", "_energy_magnitude_pJ")
                partner = partner.replace("_standard_energy_pJ", "_energy_magnitude_pJ")
                if hasattr(history, partner):
                    scale = max(scale, np.max(np.asarray(getattr(history, partner))[-1]))
            assert np.max(np.abs(a - b), initial=0.0) <= 1e-12 * scale + 1e-30, (k, name)
        # The device row checks (the compiled ledger and magnitude terms) against the host's:
        # the same residual, a difference of terms of about 0.1 pJ, to their rounding.
        device = forward.worlds[k + 1].diagnostics["max_energy_balance_error_pJ"]
        host = single.diagnostics["max_energy_balance_error_pJ"]
        assert device == pytest.approx(host, rel=1e-9, abs=1e-15), (k, device, host)
        assert device > 1e-14  # The faces' booking (§3.4, guard 2), well above that rounding.


def test_the_device_row_checks_refuse_misbookings_at_the_species_scale():
    """§6.5: the ledgers at the species' scale on the device too (the compiled ledger terms). A
    produced amount misbooked by 1e-16 fmol (far below the ions' 1e-10 floor, far above the
    species' 1e-20) fails the local ledger, a work misbooked by 1e-7 pJ the energy ledger and a
    heat of the wrong sign the dissipation check, on the device and on the host; the clean row
    passes both."""
    from cells.models.surface_pump_checks import CheckConstants

    spec = parse_spec(rfx.enzyme_network(faces=False, end=END, observation_times=[0.0, END]))
    result = run(spec)
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    k = len(result.times) - 1
    rows = [model.STATE_TYPE(*(np.asarray(v[i]) for v in result.history)) for i in (k - 1, k)]
    steps = int(round(float(result.times[k]) / spec.execution.dt))
    constants = CheckConstants(*(np.asarray(v) for v in model.device_check_constants(spec)))
    check = jax.jit(lambda a, b: model.device_checks(a, b, p, constants, steps))
    clean, _ = check(rows[0], rows[1])
    assert not np.any(np.asarray(clean))
    s = list(spec.model.species_ids).index("S")
    produced = rows[1].reaction_produced_fmol.copy()
    produced[s, 0] += 1e-16
    work = rows[1].reaction_work_pJ.copy()
    work[0] += 1e-7
    faults = dict(
        local=rows[1]._replace(reaction_produced_fmol=produced),
        energy=rows[1]._replace(reaction_work_pJ=work),
        dissipation=rows[1]._replace(
            reaction_dissipated_energy_pJ=-rows[1].reaction_dissipated_energy_pJ
        ),
    )
    assert rows[1].reaction_dissipated_energy_pJ[0] > 0
    for name, bad in faults.items():
        failed, _ = check(rows[0], bad)
        flags = dict(zip(model.DEVICE_CHECKS, np.asarray(failed).tolist(), strict=True))
        assert flags[name], (name, flags)
        with pytest.raises(NumericalError):
            model.check_values(bad, spec, [steps])
