"""Independent scalar/list and 80-digit quantity cut oracle, without Cells/NumPy/JAX."""

from copy import deepcopy
from decimal import Decimal, localcontext
from itertools import product

DOMAINS = ("cell", "membrane", "edge", "environment")


def remove(topology, removed_cell_ids):
    """Explicit named-owner filtering; no shape-based ownership inference."""
    original = deepcopy(topology)
    selected = set(removed_cell_ids)
    if len(selected) != len(removed_cell_ids) or not selected <= set(original["cell_ids"]):
        raise ValueError("Invalid named cell selection")
    kept = dict(cell=[i for i, name in enumerate(original["cell_ids"]) if name not in selected])
    kept["membrane"] = [
        i for i, owner in enumerate(original["membrane_cell"]) if owner in kept["cell"]
    ]
    kept["edge"] = [
        i for i, pair in enumerate(original["edge_cells"]) if all(v in kept["cell"] for v in pair)
    ]
    kept["environment"] = list(range(len(original["environment_ids"])))
    removed, reverse = {}, {}
    after = {}
    for domain in DOMAINS:
        ids = original[domain + "_ids"]
        after[domain + "_ids"] = [ids[i] for i in kept[domain]]
        removed[domain] = [i for i in range(len(ids)) if i not in kept[domain]]
        reverse[domain] = [
            kept[domain].index(i) if i in kept[domain] else -1 for i in range(len(ids))
        ]
    after["membrane_cell"] = [
        reverse["cell"][original["membrane_cell"][i]] for i in kept["membrane"]
    ]
    after["membrane_environment"] = [original["membrane_environment"][i] for i in kept["membrane"]]
    after["edge_cells"] = [
        [reverse["cell"][v] for v in original["edge_cells"][i]] for i in kept["edge"]
    ]
    after["edge_membranes"] = [
        [reverse["membrane"][v] for v in original["edge_membranes"][i]]
        if original["edge_is_contact"][i]
        else [-1, -1]
        for i in kept["edge"]
    ]
    after["edge_is_contact"] = [original["edge_is_contact"][i] for i in kept["edge"]]
    exposed, hurt = set(), set()
    for i in removed["edge"]:
        if original["edge_is_contact"][i]:
            for cell, mem in zip(
                original["edge_cells"][i], original["edge_membranes"][i], strict=True
            ):
                if cell in kept["cell"]:
                    hurt.add(cell)
                    exposed.add(mem)
    return dict(
        after=after,
        new_to_old=kept,
        old_to_new=reverse,
        removed=removed,
        hurt_cell_ids=[original["cell_ids"][i] for i in sorted(hurt)],
        exposed_membrane_ids=[original["membrane_ids"][i] for i in sorted(exposed)],
    )


def _shape(value):
    if not isinstance(value, (list, tuple)):
        return ()
    if not value:
        return (0,)
    children = [_shape(v) for v in value]
    if any(shape != children[0] for shape in children):
        raise ValueError("Require rectangular field values")
    return (len(value),) + children[0]


def _at(value, indices):
    for index in indices:
        value = value[index]
    return value


def _build(shape, function, indices=()):
    if not shape:
        return function(indices)
    return [_build(shape[1:], function, indices + (i,)) for i in range(shape[0])]


def _gather(value, axis, selected):
    if axis == 0:
        return [deepcopy(value[i]) for i in selected]
    return [_gather(v, axis - 1, selected) for v in value]


def _decimal(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Finite quantity inputs are required")
    return result


def _measure(value, index, shape, axis):
    dims = _shape(value)
    if not dims:
        return _decimal(value)
    if dims == (shape[axis],):
        return _decimal(value[index[axis]])
    padded = (1,) * (len(shape) - len(dims)) + dims
    selected = tuple(0 if n == 1 else i for n, i in zip(padded, index, strict=True))
    return _decimal(_at(value, selected[len(shape) - len(dims) :]))


def field_cut(field, plan):
    """Density conversion, owner selection and Decimal reductions formed independently."""
    values = field["values"]
    domain, kind = field["domain"], field.get("kind", "state")
    if domain == "global":
        return dict(
            retained=deepcopy(values),
            removed_values=[],
            removed_quantity=None,
            previous_total=None,
            retained_total=None,
            removed_total=None,
            balance_residual=None,
            retained_measure=None,
        )
    shape = tuple(field.get("shape", _shape(values)))
    axis = field.get("axis", -1) % len(shape)
    kept, removed = plan["new_to_old"][domain], plan["removed"][domain]
    result = dict(
        retained=_gather(values, axis, kept),
        removed_values=_gather(values, axis, removed),
        removed_quantity=None,
        previous_total=None,
        retained_total=None,
        removed_total=None,
        balance_residual=None,
        retained_measure=None,
    )
    if kind == "state":
        return result
    with localcontext() as context:
        context.prec = 80
        scale = _decimal(field.get("amount_scale", 1.0))
        old_measure = field.get("measure")

        def quantity(index):
            value = _decimal(_at(values, index))
            return (
                value * _measure(old_measure, index, shape, axis) * scale
                if kind == "density"
                else value
            )

        retained_shape, removed_shape = list(shape), list(shape)
        retained_shape[axis], removed_shape[axis] = len(kept), len(removed)

        def old_index(index, selection):
            value = list(index)
            value[axis] = selection[index[axis]]
            return tuple(value)

        result["removed_quantity"] = _build(
            removed_shape, lambda index: float(quantity(old_index(index, removed)))
        )
        if kind == "density":
            replacement = field.get("replacement_measure")
            if replacement is None:
                result["retained_measure"] = _build(
                    retained_shape,
                    lambda index: float(_measure(old_measure, old_index(index, kept), shape, axis)),
                )
            else:
                result["retained_measure"] = _build(
                    retained_shape,
                    lambda index: float(_measure(replacement, index, retained_shape, axis)),
                )
                result["retained"] = _build(
                    retained_shape,
                    lambda index: float(
                        quantity(old_index(index, kept))
                        / (_measure(replacement, index, retained_shape, axis) * scale)
                    ),
                )
        reduced_shape = shape[:axis] + shape[axis + 1 :]

        def total(index, selection):
            terms = []
            for owner in selection:
                full = index[:axis] + (owner,) + index[axis:]
                terms.append(quantity(full))
            return sum(terms, Decimal(0))

        result["previous_total"] = _build(
            reduced_shape, lambda i: float(total(i, range(shape[axis])))
        )
        result["retained_total"] = _build(reduced_shape, lambda i: float(total(i, kept)))
        result["removed_total"] = _build(reduced_shape, lambda i: float(total(i, removed)))
        result["balance_residual"] = _build(reduced_shape, lambda _: 0.0)
    return result


def all_indices(shape):
    return product(*(range(n) for n in shape))
