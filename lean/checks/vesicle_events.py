"""Short mass-action products, finite osmotic energy changes and one measured deflation."""

import argparse
import json
import math
from collections import Counter
from decimal import Decimal, localcontext
from functools import cache
from itertools import pairwise
from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
from vesicle import DATA, NA, PI, bath_world, moving_bilayer

from cells.models.assembly_lineages import ledger
from cells.models.assembly_lineages_v2 import exchange, lumen, mass_action, runner
from tests.unit.test_assembly_lineages_v2_lumen import K_L, Q

ENERGY_ATOL = 1e-12  # kT per tested event or closed path.
DRAW_ATOL = 2e-14  # absolute error in ln of a dimensionless product.


def log_directions(count, arity, table, xp):
    """Isolate one finite dilute reactant with unit concentration scale and encounter extent."""
    n, k = count[:, None], arity[:, None]
    zeros = xp.zeros_like(count, dtype=xp.float64)
    view = SimpleNamespace(
        counts=n,
        coeff=k,
        consumed=k,
        dilute=xp.ones_like(n, dtype=bool),
        membrane=xp.zeros_like(n, dtype=bool),
        held=xp.zeros_like(n, dtype=bool),
        membrane_total=3,
        log_X=0.0,
        log_activity=0.0,
        log_encounter=zeros,
        log_factorial=table,
    )
    locus = xp.zeros_like(count, dtype=bool)
    return xp.stack(
        [
            law(view, locus, zeros, 0, xp)
            for law in (mass_action.log_direction, exchange.geometric_log_direction)
        ]
    )


def draws():
    counts = [0, 1, 2, 3, 8, 31, 256, 2048, 4096, 8192, 65535, 100000, 2**20]
    pairs = [(n, k) for n in counts for k in range(4)]
    n, k = np.array(pairs, dtype=np.int64).T
    table = ledger.log_factorials(max(counts))
    host = log_directions(n, k, table, np)
    device = np.asarray(jax.jit(lambda x, y, t: log_directions(x, y, t, jnp))(n, k, table))
    valid = n >= k
    with localcontext() as ctx:
        ctx.prec = 70
        exact = np.array(
            [float(Decimal(math.prod(range(i - j + 1, i + 1))).ln()) for i, j in pairs if j <= i]
        )
    errors = {}
    for system, result in (("numpy", host), ("compiled_cpu", device)):
        assert np.isneginf(result[:, ~valid]).all()
        for law, values in zip(("mass_action", "phase_exchange"), result, strict=True):
            errors[system + "_" + law] = float(np.max(np.abs(values[valid] - exact)))
    return dict(
        counts=counts,
        feasible=int(valid.sum()),
        masked=int((~valid).sum()),
        max_absolute_log_errors=errors,
        tolerance=DRAW_ATOL,
        passed=max(errors.values()) <= DRAW_ATOL,
    )


def event_delta(n0, w0, n1, w1, constants, xp):
    # Native delta aggregates stoichiometry into lumen molecules and membrane quanta.
    # The unit weights here pass the already aggregated differences to that same entry point.
    view = SimpleNamespace(places=xp.asarray([[0, 1]]))
    layout = xp.asarray([1, 0]), xp.asarray([0, 1]), constants
    changes = xp.stack([n1 - n0, w1 - w0])[None, :]
    return lumen.delta((n0, w0), layout, view, changes, xp)[0]


def reference_energy(n, w, q, bath, standard):
    """Absolute state energy in kT, retained as Decimal until the two states are subtracted."""
    if n == 0:
        return Decimal(0), "empty"
    if w == 0:
        return Decimal("Infinity"), "no_membrane"
    area = Decimal.from_float(q) * w / 2
    radius = (area / (4 * PI)).sqrt()
    cap = 4 * PI * radius**3 / 3
    osmotic = n / (NA * Decimal.from_float(bath))
    volume = min(cap, osmotic)
    energy = (
        -n * (NA * Decimal.from_float(standard) * volume).ln()
        + NA * Decimal.from_float(bath) * volume
    )
    return energy, "taut" if cap < osmotic else "slack"


def energy():
    spec = moving_bilayer(1)
    world = spec.model.world
    bath, standard = lumen.outside_mM(world), world.units.standard_concentration_mM
    constants = lumen.layout(None, world, len(world.places))[2]
    run = runner.run(spec).check()
    assert run.closure["holds"]
    counts = run.rows["place_count"]
    at = {p.name: i for i, p in enumerate(world.places)}
    n = counts[:, at["I@lumen"]] + counts[:, at["S@lumen"]]
    w = K_L * counts[:, at["L@membrane"]] + 15 * counts[:, at["M@membrane"]]
    states = list(zip(map(int, n), map(int, w), strict=True))
    path = list(pairwise(states))
    edges = set(path)
    rectangles = []
    for footprint in (6000, 60000, 240000):
        area = Q * footprint / 2
        cap = area**1.5 / (6 * math.sqrt(math.pi))
        boundary = math.floor(float(NA) * bath * cap)
        for count in (
            boundary // 2,
            boundary - 2,
            boundary - 1,
            boundary,
            boundary + 1,
            2 * boundary,
        ):
            loop = [
                (count, footprint),
                (count + 1, footprint),
                (count + 1, footprint + K_L),
                (count, footprint + K_L),
                (count, footprint),
            ]
            rectangle = list(pairwise(loop))
            edges.update(rectangle)
            rectangles.append(rectangle)
    edges |= {(end, start) for start, end in edges}
    pairs = sorted(edges)
    inputs = np.asarray([[*a, *b] for a, b in pairs], dtype=np.int64)
    device_deltas = jax.jit(
        jax.vmap(lambda a, b, c, d, t: event_delta(a, b, c, d, t, jnp), in_axes=(0, 0, 0, 0, None))
    )
    device = np.asarray(device_deltas(*inputs.T, constants))
    host = [event_delta(*row, constants, np) for row in inputs]
    with localcontext() as ctx:
        ctx.prec = 70
        ref = cache(lambda state: reference_energy(*state, Q, bath, standard))
        wanted = np.array([float(ref(b)[0] - ref(a)[0]) for a, b in pairs])
        branches = Counter(ref(a)[1] + "_to_" + ref(b)[1] for a, b in pairs)
        path_change = float(ref(states[-1])[0] - ref(states[0])[0])
    assert set(branches) == {"slack_to_slack", "slack_to_taut", "taut_to_slack", "taut_to_taut"}
    changes = dict(zip(pairs, map(float, device), strict=True))
    errors = dict(
        numpy=float(np.max(np.abs(np.array(host) - wanted))),
        compiled_cpu=float(np.max(np.abs(device - wanted))),
        reverse_pair=max(abs(value + changes[b, a]) for (a, b), value in changes.items()),
        four_event_cycle=max(abs(math.fsum(changes[edge] for edge in rect)) for rect in rectangles),
        trajectory_sum=abs(math.fsum(changes[edge] for edge in path) - path_change),
    )
    # The nonregular public path assigns zero energy to an empty lumen and +inf to
    # a positive count with no footprint. inf-to-inf has no defined difference.
    special = np.array([[0, 0, 0, 1], [0, 60, 1, 60], [1, 60, 0, 60], [0, 0, 1, 0], [1, 0, 0, 0]])
    values = np.asarray(device_deltas(*special.T, constants))
    assert values[0] == 0 and np.isposinf(values[3]) and np.isneginf(values[4])
    with localcontext() as ctx:
        ctx.prec = 70
        end = float(reference_energy(1, 60, Q, bath, standard)[0])
    fallback = max(abs(float(values[1]) - end), abs(float(values[2]) + end))
    # In these dimensionless units (N,W)=(1,1) is exactly on the branch boundary.
    unit_constants = np.array([0, 1, 0, 0, 0, 0, 1], dtype=float)
    ties = np.array([[1, 1, 2, 1], [2, 1, 1, 1], [1, 1, 2, 4], [2, 4, 1, 1]])
    tie_delta = np.asarray(device_deltas(*ties.T, unit_constants))
    slack_delta = 1 - 2 * math.log(2)
    errors["exact_boundary"] = float(np.max(np.abs(tie_delta - [0, 0, slack_delta, -slack_delta])))
    return dict(
        regular_directed_edges=len(pairs),
        branches=dict(sorted(branches.items())),
        compiled_history_steps=len(path),
        compiled_events=run.timings["events"],
        rectangles=len(rectangles),
        max_abs_kT=errors,
        fallback_finite_max_error_kT=fallback,
        zero_and_signed_infinities=True,
        tolerance_kT=ENERGY_ATOL,
        passed=max(*errors.values(), fallback) <= ENERGY_ATOL,
    )


def deflation():
    data = json.loads((DATA / "bhatia2020_vesicle_deflation.json").read_text())
    before, after = data["initial"], data["after"]
    v0, a0 = before["outer_volume_um3"], before["outer_area_um2"]
    v_outer, a_outer = after["outer_volume_um3"], after["outer_area_um2"]
    radius, length = after["tube_diameter_um"] / 2, after["tube_length_um"]
    tube_area, tube_volume = 2 * math.pi * radius * length, math.pi * radius**2 * length
    cap = a0 * math.sqrt(a0) / (6 * math.sqrt(math.pi))
    effective_mM = before["sugar_mM"] * v0 / cap
    pre, _ = bath_world(effective_mM, before["sugar_mM"])
    post, _ = bath_world(effective_mM, after["sugar_mM"])
    expected = min(v0 * before["sugar_mM"] / after["sugar_mM"], cap)
    math_close = math.isclose(post * cap, expected, rel_tol=3e-13)
    assert math_close and math.isclose(pre, 1.0, abs_tol=3e-13)
    return dict(
        initial_cap_um3=cap,
        initial_central_reduced_volume=v0 / cap,
        final_lumen_upper_fraction_central=v_outer / v0,
        cylinder_area_um2=tube_area,
        cylinder_excluded_um3=tube_volume,
        cylinder_total_area_um2=a_outer + tube_area,
        cylinder_lumen_um3=v_outer - tube_volume,
        cylinder_area_fraction=(a_outer + tube_area) / a0,
        cylinder_volume_fraction=(v_outer - tube_volume) / v0,
        compiled_predicted_volume_um3=post * cap,
        compiled_fraction_of_measured_start=post * cap / v0,
        predicted_minus_cylinder_um3=post * cap - (v_outer - tube_volume),
        reported_outer_volume_pm_um3=after["outer_volume_reported_pm_um3"],
        biological_verdict="not_assessable",
        passed=math_close,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("all", "draws", "energy", "deflation"), default="all")
    case = parser.parse_args().case
    jax.config.update("jax_enable_x64", True)
    results = {
        name: fn()
        for name, fn in (("draws", draws), ("energy", energy), ("deflation", deflation))
        if case in ("all", name)
    }
    print(json.dumps(results, indent=2, allow_nan=False))
    raise SystemExit(int(any(not part["passed"] for part in results.values())))
