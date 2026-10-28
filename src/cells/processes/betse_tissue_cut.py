"""Pure conservative tissue removal, explicit owners and stable layout identities.

Native cut behaviour is captured separately. This component never infers owner
axes from lengths, releases contents to ECM, resets surviving state or creates
new geometry/biology. A cut drops cell-owned membranes and incident edges;
field edges are distinct from membrane contacts. Derived solvers/layouts must
be rebuilt by the composing model before continuation.
"""

import hashlib
import json
from dataclasses import dataclass, replace
from numbers import Real
from types import MappingProxyType
from typing import NamedTuple

import numpy as np

LAW_ID = "conservative_tissue_removal_remap@1"
DOMAINS = ("cell", "membrane", "edge", "environment")


@dataclass(frozen=True)
class Topology:
    cell_ids: tuple
    membrane_ids: tuple
    edge_ids: tuple
    environment_ids: tuple
    membrane_cell: object
    membrane_environment: object  # -1 explicitly means no bound environment node.
    edge_cells: object
    edge_membranes: object  # Two owned membranes for contacts; [-1,-1] for field edges.
    edge_is_contact: object


@dataclass(frozen=True)
class CutPlan:
    before: Topology
    after: Topology
    old_to_new: dict
    new_to_old: dict
    removed: dict
    hurt_cell_ids: tuple
    exposed_membrane_ids: tuple
    before_identity: str
    after_identity: str

    @property
    def changed(self):
        return bool(self.removed["cell"].size)

    @property
    def invalidated(self):
        return (
            (
                "geometry_maps",
                "field_operators",
                "owner_bindings",
                "compiled_layout",
                "checkpoint_identity",
            )
            if self.changed
            else ()
        )


@dataclass(frozen=True)
class OwnedField:
    values: object
    domain: str
    axis: int | None = -1
    kind: str = "state"  # state, quantity, or density.
    units: str = ""
    measure: object = None
    replacement_measure: object = None
    amount_scale: float = 1.0
    quantity_units: str = ""
    nonnegative: bool = False


class FieldCut(NamedTuple):
    retained: object
    removed_values: object
    removed_quantity: object
    previous_total: object
    retained_total: object
    removed_total: object
    balance_residual: object
    retained_measure: object


@dataclass(frozen=True)
class CutResult:
    plan: CutPlan
    fields: dict
    removed_owner_ids: dict
    field_metadata: dict


def _frozen(value, dtype=None):
    result = np.array(value, dtype=dtype, copy=True)
    result.setflags(write=False)
    return result


def _ids(values):
    if (
        not isinstance(values, (tuple, list))
        or any(not isinstance(v, str) or not v for v in values)
        or len(set(values)) != len(values)
    ):
        raise ValueError("Require explicit unique nonempty string IDs within each owner domain")
    return tuple(values)


def _integers(values, shape):
    result = np.asarray(values)
    if result.size == 0 and 0 in shape:
        result = np.empty(shape, dtype=np.int64)
    if result.shape != shape or result.dtype.kind not in "iu":
        raise ValueError("Invalid explicit owner index shape or integer type")
    return _frozen(result, np.int64)


def validate_topology(topology):
    names = [_ids(getattr(topology, domain + "_ids")) for domain in DOMAINS]
    nc, nm, ne, no = map(len, names)
    owner = _integers(topology.membrane_cell, (nm,))
    outside = _integers(topology.membrane_environment, (nm,))
    endpoints = _integers(topology.edge_cells, (ne, 2))
    contacts = _integers(topology.edge_membranes, (ne, 2))
    contact_mask = np.asarray(topology.edge_is_contact)
    if contact_mask.shape == (0,) and ne == 0:
        contact_mask = np.empty(0, bool)
    if contact_mask.shape != (ne,) or contact_mask.dtype.kind != "b":
        raise ValueError("Explicit boolean edge roles are required")
    if (
        np.any((owner < 0) | (owner >= nc))
        or np.any((outside < -1) | (outside >= no))
        or np.any((endpoints < 0) | (endpoints >= nc))
        or np.any(endpoints[:, 0] == endpoints[:, 1])
        or np.any(contacts[~contact_mask] != -1)
    ):
        raise ValueError("Invalid cell/environment ownership or edge endpoints")
    paired = contacts[contact_mask]
    if np.any((paired < 0) | (paired >= nm)) or len(np.unique(paired)) != paired.size:
        raise ValueError("Contact membranes must be valid, unique physical faces")
    if np.any(owner[paired] != endpoints[contact_mask]):
        raise ValueError("Each contact membrane must belong to its declared endpoint")
    return Topology(*names, owner, outside, endpoints, contacts, _frozen(contact_mask, bool))


def topology_dict(topology):
    t = validate_topology(topology)
    return {
        key: list(value) if key.endswith("_ids") else value.tolist()
        for key, value in vars(t).items()
    }


def topology_from_dict(data):
    if not isinstance(data, dict) or set(data) != set(Topology.__dataclass_fields__):
        raise ValueError("Require the complete versioned topology payload")
    return validate_topology(Topology(**data))


def layout_identity(topology):
    payload = dict(law_id=LAW_ID, topology=topology_dict(topology))
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def plan_cut(topology, removed_cell_ids):
    t = validate_topology(topology)
    selected = _ids(removed_cell_ids)
    if not set(selected) <= set(t.cell_ids):
        raise ValueError("Cut names must refer to existing cells exactly once")
    cut = np.array([name in selected for name in t.cell_ids])
    if not len(t.cell_ids):
        cut = np.empty(0, bool)
    keep = {
        "cell": ~cut,
        "membrane": ~cut[t.membrane_cell],
        "edge": ~np.any(cut[t.edge_cells], axis=1),
        "environment": np.ones(len(t.environment_ids), bool),
    }
    n2o, o2n, removed = {}, {}, {}
    for domain in DOMAINS:
        n2o[domain] = _frozen(np.flatnonzero(keep[domain]), np.int64)
        removed[domain] = _frozen(np.flatnonzero(~keep[domain]), np.int64)
        reverse = np.full(keep[domain].size, -1, dtype=np.int64)
        reverse[n2o[domain]] = np.arange(n2o[domain].size)
        o2n[domain] = _frozen(reverse)
    edge_cells = o2n["cell"][t.edge_cells[n2o["edge"]]]
    contact_mask = t.edge_is_contact[n2o["edge"]]
    contact_mems = np.full((len(contact_mask), 2), -1, dtype=np.int64)
    contact_mems[contact_mask] = o2n["membrane"][t.edge_membranes[n2o["edge"]][contact_mask]]
    names = [tuple(getattr(t, d + "_ids")[i] for i in n2o[d]) for d in DOMAINS]
    after = validate_topology(
        Topology(
            *names,
            o2n["cell"][t.membrane_cell[n2o["membrane"]]],
            t.membrane_environment[n2o["membrane"]],
            edge_cells,
            contact_mems,
            contact_mask,
        )
    )
    exposed, hurt = np.zeros(len(t.membrane_ids), bool), np.zeros(len(t.cell_ids), bool)
    for edge in removed["edge"]:
        if t.edge_is_contact[edge]:
            for cell, membrane in zip(t.edge_cells[edge], t.edge_membranes[edge], strict=True):
                if not cut[cell]:
                    exposed[membrane], hurt[cell] = True, True
    return CutPlan(
        t,
        after,
        MappingProxyType(o2n),
        MappingProxyType(n2o),
        MappingProxyType(removed),
        tuple(t.cell_ids[i] for i in np.flatnonzero(hurt)),
        tuple(t.membrane_ids[i] for i in np.flatnonzero(exposed)),
        layout_identity(t),
        layout_identity(after),
    )


def remap_axes(values, plan, owner_axes, *, xp=np):
    """Unchecked pure backend gather with explicit (axis, domain) declarations."""
    result = xp.asarray(values)
    used = set()
    for axis, domain in owner_axes:
        if domain not in DOMAINS or type(axis) is not int or not -result.ndim <= axis < result.ndim:
            raise ValueError("Invalid explicit ownership axis")
        axis %= result.ndim
        if axis in used or result.shape[axis] != len(getattr(plan.before, domain + "_ids")):
            raise ValueError("Duplicate or mismatched owner axis")
        result = xp.take(result, xp.asarray(plan.new_to_old[domain]), axis=axis)
        used.add(axis)
    return result.copy()


def _measure(value, shape, axis):
    raw = np.asarray(value)
    if raw.dtype.kind not in "fiu" or not np.isfinite(raw).all() or np.any(raw <= 0):
        raise ValueError("Density measures must be positive finite real arrays")
    if raw.ndim == 1 and raw.size == shape[axis]:
        view = [1] * len(shape)
        view[axis] = raw.size
        raw = raw.reshape(view)
    return np.broadcast_to(raw, shape).astype(float, copy=True)


def validate_field(field, plan):
    if not isinstance(field, OwnedField) or field.kind not in ("state", "quantity", "density"):
        raise ValueError(
            "Declare state/quantity/density explicitly; derived operators require rebuild"
        )
    values = np.asarray(field.values)
    if (
        values.dtype.kind not in "bfiu"
        or not np.isfinite(values).all()
        or type(field.nonnegative) is not bool
    ):
        raise ValueError("Fields require finite real numeric values and explicit flags")
    if field.nonnegative and np.any(values < 0):
        raise ValueError("Nonnegative owned values cannot be negative")
    if not isinstance(field.units, str) or not isinstance(field.quantity_units, str):
        raise ValueError("Field units must be explicit strings")
    if (
        isinstance(field.amount_scale, (bool, np.bool_))
        or not isinstance(field.amount_scale, Real)
        or not np.isfinite(field.amount_scale)
        or field.amount_scale <= 0
    ):
        raise ValueError("Quantity scale must be finite and positive")
    if field.domain == "global":
        if (
            field.axis is not None
            or field.kind != "state"
            or field.measure is not None
            or field.replacement_measure is not None
        ):
            raise ValueError("Global data is explicitly unowned state, without quantity conversion")
        return replace(field, values=values.copy())
    if (
        field.domain not in DOMAINS
        or type(field.axis) is not int
        or not -values.ndim <= field.axis < values.ndim
    ):
        raise ValueError("Owned fields require an explicit valid domain and axis")
    axis = field.axis % values.ndim
    if values.shape[axis] != len(getattr(plan.before, field.domain + "_ids")):
        raise ValueError("Field axis does not match its declared owner domain")
    if field.kind != "state" and (
        values.dtype.kind != "f" or values.dtype.itemsize != 8 or not field.units
    ):
        raise ValueError("Material/charge quantities require float64 values and declared units")
    if field.kind == "density":
        if field.measure is None or not field.quantity_units:
            raise ValueError("Density requires an explicit measure and resulting quantity units")
        measure = _measure(field.measure, values.shape, axis)
        shape = list(values.shape)
        shape[axis] = len(plan.new_to_old[field.domain])
        if field.replacement_measure is not None and not plan.changed:
            raise ValueError("A no-op cut cannot imply a separate geometry change")
        replacement = (
            None
            if field.replacement_measure is None
            else _measure(field.replacement_measure, tuple(shape), axis)
        )
    else:
        if field.measure is not None or field.replacement_measure is not None:
            raise ValueError("Only declared densities may own conversion measures")
        measure, replacement = None, None
    normalized = replace(
        field,
        values=values.copy(),
        axis=axis,
        measure=measure,
        replacement_measure=replacement,
        quantity_units=(field.quantity_units or field.units) if field.kind != "state" else "",
    )
    if field.kind != "state":
        with np.errstate(all="ignore"):
            candidate = remap_field(normalized, plan)
        if any(value is not None and not np.isfinite(value).all() for value in candidate):
            raise ValueError(
                "Declared quantity, reduction or replacement density is not representable"
            )
    return normalized


def remap_field(field, plan, *, xp=np):
    """Unchecked numerical kernel for an already validated field/plan.

    JAX callers validate/bind on the host, close over the plan and supply values
    to a newly compiled layout. No runtime shape-changing cut occurs in JIT.
    """
    value = xp.asarray(field.values)
    if field.domain == "global":
        return FieldCut(
            value.copy(), xp.empty((0,), dtype=value.dtype), None, None, None, None, None, None
        )
    axis = field.axis
    retained = xp.take(value, xp.asarray(plan.new_to_old[field.domain]), axis=axis)
    removed = xp.take(value, xp.asarray(plan.removed[field.domain]), axis=axis)
    if field.kind == "state":
        return FieldCut(retained, removed, None, None, None, None, None, None)
    if field.kind == "density":
        quantity = value * xp.asarray(field.measure) * field.amount_scale
        measure = xp.take(
            xp.asarray(field.measure), xp.asarray(plan.new_to_old[field.domain]), axis=axis
        )
    else:
        quantity, measure = value, None
    kept_quantity = xp.take(quantity, xp.asarray(plan.new_to_old[field.domain]), axis=axis)
    removed_quantity = xp.take(quantity, xp.asarray(plan.removed[field.domain]), axis=axis)
    if field.replacement_measure is not None:
        measure = xp.asarray(field.replacement_measure)
        retained = kept_quantity / (measure * field.amount_scale)
    actual_retained_quantity = (
        retained * measure * field.amount_scale if field.kind == "density" else retained
    )
    previous, kept, lost = (
        xp.sum(v, axis=axis) for v in (quantity, actual_retained_quantity, removed_quantity)
    )
    return FieldCut(
        retained, removed, removed_quantity, previous, kept, lost, previous - kept - lost, measure
    )


def apply_cut(topology, removed_cell_ids, fields):
    plan = plan_cut(topology, removed_cell_ids)
    if not isinstance(fields, dict) or any(not isinstance(k, str) or not k for k in fields):
        raise ValueError("Require named, explicitly owned fields")
    prepared = {name: validate_field(field, plan) for name, field in fields.items()}
    outputs = {name: remap_field(field, plan) for name, field in prepared.items()}
    removed_ids = {
        domain: tuple(getattr(plan.before, domain + "_ids")[i] for i in plan.removed[domain])
        for domain in DOMAINS
    }
    metadata = {
        name: dict(
            domain=f.domain,
            axis=f.axis,
            kind=f.kind,
            units=f.units,
            quantity_units=f.quantity_units,
            amount_scale=float(f.amount_scale),
            nonnegative=f.nonnegative,
            shape=list(outputs[name].retained.shape),
            dtype=outputs[name].retained.dtype.str,
        )
        for name, f in prepared.items()
    }
    return CutResult(plan, outputs, removed_ids, metadata)


def owner_csr(topology):
    """Linear-size cell->membrane and contact-neighbor maps for fresh binders."""
    t = validate_topology(topology)
    count = len(t.cell_ids)
    mem_order = np.argsort(t.membrane_cell, kind="stable")
    mem_ptr = np.r_[0, np.cumsum(np.bincount(t.membrane_cell, minlength=count))]
    contact = np.flatnonzero(t.edge_is_contact)
    edges = np.repeat(contact, 2)
    origins = t.edge_cells[contact].reshape(-1)
    destinations = t.edge_cells[contact, ::-1].reshape(-1)
    order = np.argsort(origins, kind="stable")
    ptr = np.r_[0, np.cumsum(np.bincount(origins, minlength=count))]
    return dict(
        membrane_indptr=mem_ptr,
        membrane_indices=mem_order,
        contact_indptr=ptr,
        neighbor_cells=destinations[order],
        contact_edges=edges[order],
    )


def checkpoint_manifest(topology, field_metadata):
    metadata = _checkpoint_fields(topology, field_metadata)
    return dict(
        kind="cells.tissue_cut_layout@1",
        law_id=LAW_ID,
        layout_identity=layout_identity(topology),
        topology=topology_dict(topology),
        fields=metadata,
        field_identity=_metadata_identity(metadata),
    )


def copy_metadata(metadata):
    return json.loads(json.dumps(metadata, allow_nan=False))


def _metadata_identity(metadata):
    return hashlib.sha256(
        json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _checkpoint_fields(topology, metadata):
    if not isinstance(metadata, dict) or any(
        not isinstance(name, str) or not name for name in metadata
    ):
        raise ValueError("Checkpoint fields must be explicitly named")
    expected = {
        "domain",
        "axis",
        "kind",
        "units",
        "quantity_units",
        "amount_scale",
        "nonnegative",
        "shape",
        "dtype",
    }
    for field in metadata.values():
        if not isinstance(field, dict) or set(field) != expected:
            raise ValueError("Checkpoint field metadata is incomplete")
        shape, axis, domain = field["shape"], field["axis"], field["domain"]
        if not isinstance(shape, list) or any(type(n) is not int or n < 0 for n in shape):
            raise ValueError("Checkpoint field shape is invalid")
        if domain == "global":
            if axis is not None or field["kind"] != "state":
                raise ValueError("Global checkpoint fields must be unowned state")
        elif (
            domain not in DOMAINS
            or type(axis) is not int
            or not 0 <= axis < len(shape)
            or shape[axis] != len(getattr(topology, domain + "_ids"))
        ):
            raise ValueError("Checkpoint field axes do not match topology owners")
        try:
            dtype = np.dtype(field["dtype"])
        except (ValueError, TypeError) as error:
            raise ValueError("Checkpoint dtype is invalid") from error
        if dtype.kind not in "bfiu" or field["kind"] not in ("state", "quantity", "density"):
            raise ValueError("Checkpoint dtype/quantity kind is unsupported")
        if field["kind"] != "state" and (
            dtype.kind != "f"
            or dtype.itemsize != 8
            or not field["units"]
            or not field["quantity_units"]
        ):
            raise ValueError("Checkpoint quantity dtype or units are invalid")
        scale = field["amount_scale"]
        if (
            type(field["nonnegative"]) is not bool
            or isinstance(scale, bool)
            or not isinstance(scale, Real)
            or not np.isfinite(scale)
            or scale <= 0
        ):
            raise ValueError("Checkpoint quantity flags/scale are invalid")
        if not isinstance(field["units"], str) or not isinstance(field["quantity_units"], str):
            raise ValueError("Checkpoint field units are invalid")
    return copy_metadata(metadata)


def validate_checkpoint_manifest(manifest, topology, expected_field_metadata=None):
    if (
        not isinstance(manifest, dict)
        or manifest.get("kind") != "cells.tissue_cut_layout@1"
        or manifest.get("law_id") != LAW_ID
        or manifest.get("layout_identity") != layout_identity(topology)
        or layout_identity(topology_from_dict(manifest.get("topology")))
        != manifest["layout_identity"]
    ):
        raise ValueError("Checkpoint topology/layout identity does not match the bound owners")
    metadata = _checkpoint_fields(topology, manifest.get("fields"))
    if manifest.get("field_identity") != _metadata_identity(metadata):
        raise ValueError("Checkpoint field declaration identity does not match")
    if expected_field_metadata is not None and metadata != _checkpoint_fields(
        topology, expected_field_metadata
    ):
        raise ValueError("Checkpoint field ownership/units do not match expected declarations")
    return metadata
