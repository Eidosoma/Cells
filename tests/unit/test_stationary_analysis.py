"""stationary_continuation_analysis@1: laws, parameters, continuation and CLI contract.

No model is compiled here (solves are in test_stationary_solve.py). Checks the
structural conservation laws of a closed synthetic @1 world (species totals and
the floating-component charge of the current-continuity closure, rhs only) and
their numerical residual, the affine reduction, parameter and request errors,
pseudo-arclength continuation on exact toy branches (both folds of a cubic,
a Hopf point of the normal form), and the CLI's config and output contract.
Judged comparisons live in validation/stationary/targets.py.
"""

import json
import math
from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.analysis import cli
from cells.analysis import continuation as cont
from cells.analysis import stationary as sa
from cells.core.specs import ConfigError, parse_spec
from validation.stationary import worlds
from validation.tissue import surface_pump_fixtures as pump_fixtures

ARS = "imex_ars222_face_electromigration@1"


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


@pytest.fixture(scope="module")
def spec():
    return parse_spec(worlds.default_world_cell())


def numpy_rates(pb, u):
    """The model's own derivative, evaluated with numpy (no JAX tracing)."""
    state, p, control = pb.embed(jnp.asarray(u))
    state, p = sa._numpy(state), sa._numpy(p)
    control = type(control)(*(np.asarray(v) for v in control))
    with np.errstate(all="ignore"):
        derivative = pb.model.rhs(state, control, p, p.active, xp=np)
    return np.asarray(pb._rates(derivative, p)), state, p, control


def test_conservation_laws_of_a_closed_world():
    spec = parse_spec(pump_fixtures.definition("closed", solver=ARS, padded=True))
    pb = sa.problem(spec)
    rhs, mapped = pb.reduction("rhs"), pb.reduction("step_map")
    kinds = [law["kind"] for law in rhs.laws]
    assert (
        kinds.count("closed_species_total") == 3 and kinds.count("floating_component_charge") == 2
    )
    assert [law["kind"] for law in mapped.laws] == ["closed_species_total"] * 3
    rates, *_ = numpy_rates(pb, pb.anchor)
    c = rhs.matrix
    scale = np.abs(c).T @ np.abs(rates)
    assert np.all(np.abs(c.T @ rates) <= 1e-13 * scale)
    # The complement basis is orthonormal and orthogonal to every law.
    np.testing.assert_allclose(rhs.basis.T @ rhs.basis, np.eye(rhs.size), atol=1e-12)
    assert np.max(np.abs(c.T @ rhs.basis)) < 1e-10 * np.max(np.abs(c))
    shift = np.linspace(-1.0, 1.0, pb.size)
    moved = rhs.project(pb.anchor + shift) - pb.anchor
    scale = np.linalg.norm(c, axis=0) * np.linalg.norm(shift)
    assert np.all(np.abs(c.T @ moved) <= 1e-13 * scale)


def test_problem_rejects_unsupported_requests(spec):
    with pytest.raises(ConfigError):
        sa.problem(spec, mode="fast", formulation="step_map")
    with pytest.raises(ConfigError):
        sa.problem(spec, steps=0)
    with pytest.raises(ConfigError):
        sa.parameter(spec, "channel_availability", ["nothing"])
    with pytest.raises(ConfigError):
        sa.parameter(spec, "membrane_permeability_scale", ["membrane_0"])
    q = sa.parameter(spec, "membrane_permeability_scale", ["membrane_0"], species="Na")
    assert q.base == 1.0 and q.target == "membrane_permeability"
    # Availabilities take their scheduled value as the base.
    q = sa.parameter(spec, "pump_availability", ["pump_0"])
    assert q.base is None and sa.problem(spec, parameter=q).parameter.base == 1.0


class Toy:
    """A duck-typed problem with exact residuals, for branch-following checks."""

    formulation, steps, dt, mode = "rhs", None, 1.0, "slow"

    def __init__(self, residual, size, theta0):
        self.residual, self.size, self._theta0 = residual, size, theta0
        self.parameter = sa.Parameter("toy", (), "toy", (), theta0)
        self.spec = SimpleNamespace(model=SimpleNamespace(membranes=()))
        self.p = SimpleNamespace(membrane_active=np.zeros(0, dtype=bool))
        self.jac = jax.jit(jax.jacfwd(lambda w: residual(w[:-1], w[-1])))

    def theta0(self):
        return self._theta0

    def _key(self, formulation, steps):
        return "rhs", None

    def reduction(self, formulation=None):
        return sa.Reduction((), np.zeros((self.size, 0)), None, np.zeros(self.size))

    def evaluate(self, u, theta=None, formulation=None, steps=None):
        theta = self._theta0 if theta is None else theta
        w = jnp.asarray(np.r_[u, theta])
        r = np.asarray(self.residual(w[:-1], w[-1]))
        jac = np.asarray(self.jac(w))
        return r, jac[:, :-1], jac[:, -1], np.zeros(0), True


def test_continuation_locates_both_folds_of_a_cubic():
    toy = Toy(lambda u, t: jnp.stack([t + u[0] - u[0] ** 3, 0.1 * u[0] - u[1]]), 2, 0.0)
    start = np.array([-1.0, -0.1])  # theta = 0: the lower stable state
    diagram = cont.continue_branch(
        toy, start, theta_start=0.0, step=0.02, max_step=0.05, max_points=300, bounds=(-1, 1)
    )
    folds = [s for s in diagram["special_points"] if s["kind"] == "fold"]
    edge = 2 / (3 * math.sqrt(3))
    assert [round(f["parameter_value"], 9) for f in folds] == [round(edge, 9), round(-edge, 9)]
    assert diagram["points"][0]["stable"] and diagram["termination"] == "parameter_bound"
    middle = [
        p for p in diagram["points"] if abs(p["parameter_value"]) < 0.3 and p["unstable_count"]
    ]
    assert middle, "the middle branch is unstable"


def test_continuation_locates_a_hopf_point():
    def normal_form(u, t):
        r2 = u[0] ** 2 + u[1] ** 2
        return jnp.stack([t * u[0] - u[1] - u[0] * r2, u[0] + t * u[1] - u[1] * r2])

    toy = Toy(normal_form, 2, -0.5)
    diagram = cont.continue_branch(
        toy,
        np.zeros(2),
        theta_start=-0.5,
        step=0.05,
        max_step=0.1,
        max_points=40,
        bounds=(-0.5, 0.5),
    )
    hopf = [s for s in diagram["special_points"] if s["kind"] == "hopf"]
    assert len(hopf) == 1
    assert abs(hopf[0]["parameter_value"]) < 1e-9
    assert hopf[0]["frequency_hz"] == pytest.approx(1 / (2 * math.pi), rel=1e-9)


def test_cli_contract(tmp_path, spec):
    world = tmp_path / "world.json"
    world.write_text(json.dumps(spec.to_dict()))
    config = dict(
        schema_version=1,
        analysis=sa.ANALYSIS_ID,
        world=dict(definition="world.json"),
        guesses=[],
    )
    path = tmp_path / "analysis.json"
    path.write_text(json.dumps(config))
    out = tmp_path / "out"
    assert cli.main([str(path), "--output", str(out)]) == 0
    result = json.loads((out / "result.json").read_text())
    assert result["analysis"] == sa.ANALYSIS_ID and result["definition_sha256"] == spec.fingerprint
    assert result["coordinates"]["size"] == 4 and result["states"] == []
    assert cli.main([str(path), "--output", str(out)]) == 2  # never overwritten
    path.write_text(json.dumps(config | dict(surprise=True)))
    assert cli.main([str(path), "--output", str(tmp_path / "other")]) == 2
    assert not (tmp_path / "other").exists()
