"""Check the rapid-binding response against standard potentials and the differentiated residual."""

import json
from decimal import Decimal, localcontext
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

from cells.laws.reactions import rapid_binding as kernel
from tests.unit import test_rapid_binding_kernel as fixture


# The raw second moment minus the product of means can cancel near saturation.
# Scale each entry by its own uncentered absolute terms in mM.
TERM_TOLERANCE = 128 * np.finfo(float).eps
compiled = jax.jit(lambda *args: kernel._hessian(*args, xp=jnp))


def residual_at(u, tb, beta, counts, present, held):
    return kernel.residual(u, jnp.zeros_like(u), tb, beta, counts, present, held, xp=jnp)[0]


jacobian = jax.jit(jax.vmap(jax.jacfwd(residual_at), in_axes=(1, 1, None, None, None, 1)))


def decimal_response(ligands, binders, free, totals):
    """Centered covariance with independent form weights, including every signed exponent."""
    with localcontext() as ctx:
        ctx.prec = 80
        reg = fixture.REGISTRY
        c0 = Decimal(reg['standard_concentration_mM'])
        x = [Decimal(v) for v in free]
        activity = [x[j] / c0 * Decimal(reg['species'][name]['mu0_RT']).exp()
                    for j, name in enumerate(ligands)]
        size = len(x)
        response = [[x[j] if j == k else Decimal(0) for k in range(size)] for j in range(size)]
        scale = [row.copy() for row in response]
        for binder, total in zip(binders, totals, strict=True):
            forms = reg['binders'][binder]['forms']
            counts = [[f.get('counts', {}).get(ligand, 0) for ligand in ligands] for f in forms]
            weights = []
            for form, row in zip(forms, counts, strict=True):
                weight = (-Decimal(form['mu0_RT'])).exp()  # Common base weight cancels.
                for a, n in zip(activity, row, strict=True):
                    weight *= a ** n
                weights.append(weight)
            z = sum(weights)
            probs = [w / z for w in weights]
            mean = [sum(p * n[j] for p, n in zip(probs, counts)) for j in range(size)]
            absolute = [sum(p * abs(n[j]) for p, n in zip(probs, counts)) for j in range(size)]
            for j in range(size):
                for k in range(size):
                    cov = sum(p * (n[j] - mean[j]) * (n[k] - mean[k]) for p, n in zip(probs, counts))
                    moment = sum(p * abs(n[j] * n[k]) for p, n in zip(probs, counts))
                    response[j][k] += Decimal(total) * cov
                    scale[j][k] += Decimal(total) * (moment + absolute[j] * absolute[k])
        return np.asarray(response, dtype=float), np.asarray(scale, dtype=float)


def masked(matrix, held):
    identity = np.eye(len(held))[:, :, None]
    return np.where(held[:, None] & held[None, :], matrix, identity)


def errors(actual, reference, scale):
    difference = np.abs(actual - reference)
    np.testing.assert_array_equal(actual[scale == 0], reference[scale == 0])
    scaled = np.divide(difference, scale, out=np.zeros_like(scale), where=scale > 0)
    assert np.all(scaled <= TERM_TOLERANCE), float(np.max(scaled))
    return {'max_abs_mM': float(np.max(difference)), 'max_fraction_of_terms': float(np.max(scaled))}


def compare_system(name):
    ligands, binders, _, net = fixture.system(name)
    states = fixture.VALUES['systems'][name]['states']
    free = np.array([[s['x_mM'][l] for s in states] for l in ligands])
    u = np.log(free)
    _, tb = fixture.totals(name, ligands, binders)
    refs = [decimal_response(ligands, binders, x, t) for x, t in zip(free.T, tb.T, strict=True)]
    reference, scale = (np.stack(group, axis=-1) for group in zip(*refs))
    beta, counts, present = (net[k] for k in ('log_beta', 'counts', 'present'))
    held = np.ones_like(u, dtype=bool)
    args = u, tb, beta, counts, present, held
    matrices = {'numpy': kernel._hessian(*args, xp=np), 'jax_jit_cpu': np.asarray(compiled(*args)),
                'residual_jacobian': np.moveaxis(np.asarray(jacobian(*args)), 0, -1)}
    metrics = {}
    for backend, values in matrices.items():
        metric = errors(values, reference, scale)
        errors(values.swapaxes(0, 1), values, scale)
        smallest = float(np.min(np.linalg.eigvalsh(np.moveaxis(values, -1, 0))))
        assert smallest > 0, (name, backend, smallest)
        metrics[backend] = dict(metric, min_eigenvalue_mM=smallest)

    # Cycle the missing coordinate across states; also exercise the all-unheld identity.
    partial = held.copy()
    partial[np.arange(len(states)) % len(ligands), np.arange(len(states))] = False
    partial[:, 0] = False
    empty = np.zeros_like(tb)
    free_diagonal = free[:, None] * np.eye(len(ligands))[:, :, None]
    for evaluate in (lambda *xs: kernel._hessian(*xs, xp=np), compiled):
        errors(np.asarray(evaluate(*args[:-1], partial)), masked(reference, partial), masked(scale, partial))
        errors(np.asarray(evaluate(u, empty, *args[2:])), free_diagonal, free_diagonal)
    # Each chemistry would catch a solver that dropped the entire binder response.
    assert np.any(np.abs(free_diagonal - reference) > TERM_TOLERANCE * scale)
    result = {'states': len(states), 'matrix_entries': int(reference.size), 'errors': metrics,
              'masked_and_empty_controls': True, 'missing_covariance_detected': True}
    if name == 'S7':
        h, mg = ligands.index('H'), ligands.index('Mg')
        assert np.all(reference[h, mg] < 0) and np.all(reference[mg, mg] > 0)
        for matrix in matrices.values():
            assert np.all(matrix[h, mg] < 0) and np.all(matrix[mg, mg] > 0)
        result['negative_H_Mg_responses'] = int(np.count_nonzero(reference[h, mg] < 0))
    return result


def titration():
    record = json.loads((Path(__file__).parent / 'data' / 'ward1998_mgatp_titration.json').read_text())
    low, high = record['figure_1_markers']
    dx, dr = record['reading_precision']['free_Mg_uM'], record['reading_precision']['bound_to_unbound']

    def fraction(ratio):
        return ratio / (1 + ratio)
    assert low['free_Mg_uM'] + dx < high['free_Mg_uM'] - dx
    fractions = [fraction(point['bound_to_unbound']) for point in (low, high)]
    min_increase = fraction(high['bound_to_unbound'] - dr) - fraction(low['bound_to_unbound'] + dr)
    assert min_increase > 0
    # The existing cross-preparation check supplies an external affinity. Neither marker is fitted.
    data = Path(__file__).parent / 'data'
    affinity = json.loads((data / 'mgatp_binding.json').read_text())['zhang1997']
    kd = affinity['apparent_kd_uM_by_pH'][str(record['pH'])]['mean'] * 1e-3
    c0 = fixture.C0
    forms = (('apo', (), 0.), ('MgATP', (('Mg', 1),), np.log(c0 / kd)))
    net = kernel.network(('Mg',), (('ATP', forms, c0, (('Mg', 1.),)),))
    free = np.array([[p['free_Mg_uM'] * 1e-3 for p in (low, high)]])
    tb = np.full_like(free, record['ATP_mM'])
    _, amounts = kernel.speciation(np.log(free), tb, net['log_beta'], net['counts'], net['present'], xp=np)
    predicted = amounts[0, 1] / tb[0]
    assert predicted[1] > predicted[0]
    return {'observed_fractions': fractions, 'increase': fractions[1] - fractions[0],
            'minimum_increase_within_graph_reading_precision': min_increase,
            'external_kd_mM': kd, 'predicted_fractions': predicted.tolist(),
            'predicted_increase': float(predicted[1] - predicted[0])}


if __name__ == '__main__':
    jax.config.update('jax_enable_x64', True)
    with jax.default_device(jax.devices('cpu')[0]):
        systems = {name: compare_system(name) for name in fixture.INPUTS['systems']}
        print(json.dumps({'systems': systems, 'term_tolerance': TERM_TOLERANCE,
                          'states': sum(s['states'] for s in systems.values()),
                          'entries_per_backend': sum(s['matrix_entries'] for s in systems.values()),
                          'ward1998': titration()}, indent=2, allow_nan=False))
