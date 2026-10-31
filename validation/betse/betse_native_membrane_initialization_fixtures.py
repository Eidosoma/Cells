"""Deferred supplied six-column owners on the held initialization02 specimens."""

import hashlib
from dataclasses import replace
from pathlib import Path

import numpy as np

from cells.processes import betse_native_membrane_initialization as entry
from cells.processes import betse_native_membrane_layout as layout
from cells.processes import betse_normal_ecm_initialization as initial
from validation.betse import betse_native_membrane_initialization_archive as archive
from validation.betse import betse_normal_ecm_initialization_fixtures as previous

CASES = ("field", "polarized", "warm-owner", "calcium", "strided-six")
REFUSALS = (
    "missing-vectors",
    "four-columns",
    "missing-owner-rows",
    "midpoint-mismatch",
    "missing-Egj",
    "missing-GRN-cache",
    "wrong-cache-boundary-epoch",
    "wrong-publication",
    "wrong-molecular-axis",
    "scalar-control",
    "foreign-inverse",
    "unsupported-channels",
    "wrong-conversion",
    "wrong-geometry-policy",
    "wrong-stage",
    "changed-shared-six",
    "wrong-layout-units",
    "changed-pair-seal",
)
CALCIUM_REFUSALS = ("persisted-CaATP-rate", "wrong-calcium-clock", "missing-calcium-policy")
RESEALED = ("projected-store", "readiness", "physical-gate", "conversion-view", "original-pair")
CORRUPTIONS = (
    "projection-column-map",
    "projection-midpoint-byte",
    "unrelated-store",
    "cache-epoch",
    "dropped-tangent",
    "component-cache",
    "native-observation-claim",
    "ordinary-loop-gate",
)
OLD_REFUSALS = (
    "missing-Egj",
    "missing-GRN-cache",
    "wrong-cache-boundary-epoch",
    "wrong-publication",
    "wrong-molecular-axis",
    "scalar-control",
    "foreign-inverse",
    "unsupported-channels",
)


def declaration():
    return dict(
        kind=entry.DECLARATION_KIND,
        opted_in_law=entry.LAW_ID,
        conversion_law=layout.MIDPOINT_NORMAL_LAW,
        component_policy="held_single_component_bootstrap_no_ordinary_loop",
        geometry_policy="retain_unqualified_six_column_parent",
        stage=initial.STAGE,
    )


def layout_declaration():
    return dict(
        kind=layout.DECLARATION_KIND,
        opted_in_law=layout.LAW_ID,
        columns=list(layout.COLUMNS),
        column_units=list(layout.COLUMN_UNITS),
        owner_order="native_cell_major_then_membrane_local_i",
        geometry_classification="unqualified_native_layout",
        evidence=[
            dict(
                path=str(Path(__file__)),
                sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            )
        ],
    )


def owner_inventory(owners):
    # Read exactly the established capture slots; arbitrary native object
    # internals and methods are never serialized as if they were owned stores.
    return {
        group: {key: initial._entry(owners[group], key) for key in names}
        for group, names in initial.GROUPS.items()
    }


def specimen(case="field", *, refusal=None, observer=None):
    if case not in CASES or refusal is not None and refusal not in (*REFUSALS, *CALCIUM_REFUSALS):
        raise ValueError("Declare a supplied bridge specimen/control")
    if observer is not None:
        observer(
            "bridge-construction-request",
            dict(
                case=case,
                refusal=refusal,
                entry_declaration=declaration(),
                layout_declaration=layout_declaration(),
                constructed_native_seed_or_mesh=False,
            ),
        )
    if refusal in (*OLD_REFUSALS, *CALCIUM_REFUSALS):
        spec, _ = previous.refusal(refusal, on_capture=observer)
    else:
        spec = previous.specimen("field" if case == "strided-six" else case, on_capture=observer)
    cells = spec["owners"]["cells"]
    binding = spec["binding"]
    cb = binding.material_binding.geometry_binding.current_binding
    mids = np.array(cells.mem_mids_flat, copy=True)
    normals = np.array(cb.kernel.normal_xy, copy=True)
    # These are explicitly supplied owner stores, not source-produced physical
    # geometry. The old initializer's manufactured four-column store is kept
    # in the construction witness before the separate six-column declaration.
    if observer is not None:
        observer(
            "before-six-column-supplied-stores",
            dict(
                original_owner_inventory=owner_inventory(spec["owners"]),
                midpoint_store=mids,
                normal_store=normals,
                owner=cb.kernel.owner,
                declared_tangent_relation="supplied [-ny,nx]; no geometry qualification",
            ),
        )
    tangents = np.column_stack((-normals[:, 1], normals[:, 0]))
    six = np.column_stack((mids, normals, tangents))
    if case == "strided-six":
        backing = np.zeros((len(six), 12), dtype=six.dtype)
        backing[:, ::2] = six
        six = backing[:, ::2]
    cells.mem_vects_flat, cells.mem_mids_flat = six, mids
    rows = [np.flatnonzero(cb.kernel.owner == i) for i in range(len(cb.cell_ids))]
    cells.cell_to_mems = np.asarray(rows, dtype=object)
    declared, ld = declaration(), layout_declaration()
    if refusal == "missing-vectors":
        del cells.mem_vects_flat
    elif refusal == "four-columns":
        cells.mem_vects_flat = six[:, :4].copy()
    elif refusal == "missing-owner-rows":
        del cells.cell_to_mems
    elif refusal == "midpoint-mismatch":
        cells.mem_vects_flat[0, 0] += 0.125
    elif refusal == "wrong-conversion":
        declared["conversion_law"] = layout.NORMAL_TANGENT_LAW
    elif refusal == "wrong-geometry-policy":
        declared["geometry_policy"] = "qualified_native_mesh"
    elif refusal == "wrong-stage":
        declared["stage"] = "after_bootstrap"
    elif refusal == "wrong-layout-units":
        ld["column_units"][0] = "um"
    spec.update(
        entry_declaration=declared, layout_declaration=ld, bridge_case=case, bridge_refusal=refusal
    )
    if observer is not None:
        observer(
            "supplied-six-column-return",
            dict(
                original_six_stores=archive.original_six_stores(cells),
                owner_inventory=owner_inventory(spec["owners"]),
                cell_to_mems=getattr(cells, "cell_to_mems", None),
                network_cache=spec["network_cache"],
                entry_declaration=declared,
                layout_declaration=ld,
            ),
        )
    return spec


def capture(spec, *, observer=None):
    pair = entry.capture_supplied(
        spec["owners"],
        spec["network_cache"],
        spec["excluded"],
        spec["declaration"],
        spec["layout_declaration"],
        observer=observer,
    )
    if spec["bridge_refusal"] == "changed-shared-six":
        snap = pair.native_layout
        values = {key: dict(value) for key, value in snap.entries.items()}
        buffer = values["mem_vects_flat"]["value"]
        raw = bytearray(buffer.raw)
        raw[40] ^= 1
        values["mem_vects_flat"]["value"] = replace(buffer, raw=bytes(raw))
        snap = replace(snap, entries=layout.freeze(values), identity="")
        snap = replace(snap, identity=layout.digest(layout.snapshot_record(snap)))
        pair = replace(pair, native_layout=snap, identity="")
        pair = replace(pair, identity=entry.digest(entry.pair_record(pair)))
    elif spec["bridge_refusal"] == "changed-pair-seal":
        pair = replace(pair, identity="0" * 64)
    return pair
