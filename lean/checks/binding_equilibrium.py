"""Compare the finite binding total map and its inverse on the registered S1–S7 chemistries."""

import json
from decimal import Decimal, localcontext
from functools import cache, partial
from itertools import combinations
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

from binding_ensemble import partition
from cells.laws.reactions import rapid_binding as kernel
from tests.unit import test_rapid_binding_kernel as fixture


ROUNDING = 128 * np.finfo(float).eps


def totals_at(u, tb, beta, counts, present, held, *, xp):
    return kernel.residual(u, xp.zeros_like(u), tb, beta, counts, present, held, xp=xp)[0]


compiled_totals = jax.jit(partial(totals_at, xp=jnp))
compiled_solve = jax.jit(partial(kernel.free_ligands, xp=jnp), static_argnames=('path',))


@cache
def probabilities(binder, ligands, free):
    return partition(binder, dict(zip(ligands, free, strict=True)))


def independent(ligands, binders, free, tb):
    """Reconstruct inventories using the original standard potentials and signed integer counts."""
    totals = free.copy()
    scale = free.copy()
    fractions = []
    for b, binder in enumerate(binders):
        forms = fixture.REGISTRY['binders'][binder]['forms']
        counts = np.array([[f.get('counts', {}).get(ligand, 0) for ligand in ligands] for f in forms])
        p = np.array([probabilities(binder, ligands, tuple(x)) for x in free.T]).T
        assert np.all(p > 0)
        fractions.append(p)
        totals += tb[b] * (counts.T @ p)
        scale += tb[b] * (np.abs(counts).T @ p)
    return totals, scale, fractions


def unresolved_projection(u, w, tb, net):
    """Resolve a float64 tie at its exact stored log concentrations and binding constants."""
    with localcontext() as ctx:
        ctx.prec = 80
        endpoints = []
        for state in (u, w):
            logs = [Decimal(x) for x in state]
            total = [x.exp() for x in logs]
            for b, binder_total in enumerate(tb):
                present = net['present'][b]
                counts = net['counts'][b, present].astype(int).tolist()
                weights = [(Decimal(beta) + sum(n * x for n, x in zip(row, logs))).exp()
                           for beta, row in zip(net['log_beta'][b, present], counts)]
                z = sum(weights)
                for j in range(len(logs)):
                    moment = sum(weight * row[j] for weight, row in zip(weights, counts)) / z
                    total[j] += Decimal(binder_total) * moment
            endpoints.append(total)
        projection = sum((Decimal(y) - Decimal(x)) * (right - left)
                         for x, y, left, right in zip(u, w, *endpoints))
        assert projection > 0
        return {'projection_at_stored_inputs_mM': str(projection),
                'nearest_binary64_totals_mM': [[float(t) for t, x, y in zip(totals, u, w) if x != y]
                                               for totals in endpoints]}


def compare_pairs(ligands, binders, left, right, tb, net, held, pairs):
    right = np.where(held, right, left)  # Unheld free concentrations stay fixed between endpoints.
    u, w = np.log(left), np.log(right)
    delta = w - u
    _, scale_left, p_left = independent(ligands, binders, left, tb)
    _, scale_right, p_right = independent(ligands, binders, right, tb)
    free_part = np.sum(delta * (right - left), axis=0)
    expected = free_part.copy()
    # For a normalized partition, log p_right - log p_left is n·delta plus a form-independent
    # constant. The latter drops out when weighted by p_right - p_left.
    for binder_total, a, b in zip(tb, p_left, p_right, strict=True):
        expected += binder_total * np.sum((b - a) * (np.log(b) - np.log(a)), axis=0)
    scale = np.sum(np.abs(delta) * (scale_left + scale_right), axis=0)
    changed = np.any(delta != 0, axis=0)
    assert np.all(expected[changed] > 0)
    # Two representable free values can give the same rounded total. Require the strict sign
    # whenever it exceeds the roundoff allowance, and record every unresolved sign explicitly.
    resolved = expected > ROUNDING * scale
    comparisons = {}
    args = tb, net['log_beta'], net['counts'], net['present'], held
    for name, evaluate in (('numpy', partial(totals_at, xp=np)), ('jax_jit_cpu', compiled_totals)):
        first, second = np.asarray(evaluate(u, *args)), np.asarray(evaluate(w, *args))
        actual = np.sum(delta * (second - first), axis=0)
        assert np.all(actual[resolved] > 0)
        np.testing.assert_array_equal(actual[~changed], 0.)
        error = np.abs(actual - expected)
        assert np.all(error <= ROUNDING * scale), (name, float(np.max(error)))
        missed = np.flatnonzero(changed & (actual <= 0))
        scaled_error = np.divide(error, scale, out=np.zeros_like(error), where=changed)
        comparisons[name] = {
            'strictly_positive': int(np.sum(actual[changed] > 0)),
            'max_error_over_absolute_terms': float(scaled_error.max()),
            'unresolved_signs': [{'states': pairs[k].tolist(), 'free_left_mM': left[:, k].tolist(),
                                  'free_right_mM': right[:, k].tolist(), 'held': held[:, k].tolist(),
                                  'projected_change_mM': float(actual[k]), 'free_part_mM': float(free_part[k]),
                                  'engine_totals_on_changed_coordinates_mM':
                                  [a[delta[:, k] != 0, k].tolist() for a in (first, second)],
                                  'reference_from_rounded_fractions_mM': float(expected[k]),
                                  'allowance_mM': float(ROUNDING * scale[k]),
                                  **unresolved_projection(u[:, k], w[:, k], tb[:, k], net)}
                                 for k in missed],
        }
    return {'distinct_pairs': int(changed.sum()), 'identical_pairs': int((~changed).sum()),
            'mixed_directions': int(np.sum((delta > 0).any(axis=0) & (delta < 0).any(axis=0))),
            'missing_binding_detected': int(np.sum(expected - free_part > ROUNDING * scale)),
            'resolved_above_roundoff': int(resolved.sum()), 'backends': comparisons}


def recover(ligands, binders, target, tb, net):
    """Invert independent manufactured totals through the registered B4 or Newton solver path."""
    prescribed, _, _ = independent(ligands, binders, target, tb)
    held, ligand_sets, binder_sets = fixture.masks(net, tb.shape[1])
    constants = fixture.one_step_k(binders, ligands[0]) if net['path'] == 'b4' else None
    args = (prescribed, tb, net['log_beta'], net['counts'], net['present'], held,
            ligand_sets, binder_sets, constants)
    metrics = {}
    for name, solve in (('numpy', partial(kernel.free_ligands, xp=np)), ('jax_jit_cpu', compiled_solve)):
        u, valid = solve(*args, path=net['path'], vertices=net['margin_vertices'])
        assert np.all(np.asarray(valid)), (name, np.flatnonzero(~np.asarray(valid)))
        u = np.asarray(u)
        rebuilt, scale, _ = independent(ligands, binders, np.exp(u), tb)
        residual = np.abs(rebuilt - prescribed) / scale
        assert np.all(residual <= kernel.RESIDUAL_RTOL + ROUNDING), (name, float(residual.max()))
        metrics[name] = {'max_abs_log_concentration_error': float(np.max(np.abs(u - np.log(target)))),
                         'max_scaled_independent_residual': float(residual.max())}
    return {'path': net['path'], 'cases': int(target.shape[1]), 'errors': metrics}


def compare_system(name):
    ligands, binders, _, net = fixture.system(name)
    states = fixture.VALUES['systems'][name]['states']
    free = np.array([[s['x_mM'][ligand] for s in states] for ligand in ligands])
    _, totals = fixture.totals(name, ligands, binders)
    pairs = np.array(list(combinations(range(len(states)), 2)))
    i, j = pairs.T
    left, right, tb = free[:, i], free[:, j], totals[:, i]
    held = np.ones_like(left, dtype=bool)
    full = compare_pairs(ligands, binders, left, right, tb, net, held, pairs)
    assert full['missing_binding_detected'] > 0, name
    partial_mask = held.copy()
    partial_mask[np.arange(len(i)) % len(ligands), np.arange(len(i))] = False
    partial_mask[:, 0] = False
    restricted = compare_pairs(ligands, binders, left, right, tb, net, partial_mask, pairs)
    return {'full': full, 'fixed_coordinates': restricted,
            'inverse': recover(ligands, binders, right, tb, net)}


def matched_histories():
    data = json.loads((Path(__file__).parent / 'data' / 'binding_equilibrium_measurements.json').read_text())
    sample = data['cortes2017_matched_histories']
    tar, egta = (sample['Fe_preloaded_on_' + name] for name in ('Tar', 'EGTA'))
    gap = tar['plateau_uM_approx'] - egta['plateau_uM_approx']
    reading_range = 2 * sample['plateau_reading_precision_uM']
    assert abs(gap) <= reading_range < tar['initial_uM_approx'] - egta['initial_uM_approx']
    return {
        'measured_plateau_gap_uM_approx': gap, 'reading_precision_of_difference_uM': reading_range,
        'predicted_equilibrium_gap_uM': 0,
        'plateau_fraction_of_total_Fe_approx': tar['plateau_uM_approx'] / sample['conditions']['Fe_II_uM'],
    }


if __name__ == '__main__':
    jax.config.update('jax_enable_x64', True)
    with jax.default_device(jax.devices('cpu')[0]):
        systems = {name: compare_system(name) for name in fixture.INPUTS['systems']}
        print(json.dumps({'systems': systems, 'iron_matched_histories': matched_histories(),
                          'rounding_tolerance': ROUNDING, 'solver_residual_tolerance': kernel.RESIDUAL_RTOL},
                         indent=2, allow_nan=False))
