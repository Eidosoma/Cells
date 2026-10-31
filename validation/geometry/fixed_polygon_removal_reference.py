"""Fresh-process stdlib reference for fixed-polygon removal ownership.

Independent signed source-face cancellation and exact shoelace areas; no Cells
imports or production geometry/merge kernels. Stable ID hashing is the explicit
interface specification, not an independent identity convention. No coordinate
repair, nearest-neighbor, native DEC, material or trajectory reference claim.
"""

import hashlib
import json
import os
import resource
import sys
import traceback
from collections import defaultdict
from fractions import Fraction
from pathlib import Path


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def ratio(value):
    return dict(numerator=str(value.numerator), denominator=str(value.denominator))


def solve(payload):
    raw, declaration = payload["parent_declaration"], payload["removal"]
    coordinates = {
        r["id"]: tuple(Fraction.from_float(v) for v in r["xy_m"]) for r in raw["vertices"]
    }
    source = {r["id"]: r["vertex_ids"] for r in raw["source_cells"]}
    areas = {}
    source_edges = {}
    for name, ring in source.items():
        pairs = list(zip(ring, ring[1:] + ring[:1], strict=True))
        areas[name] = (
            sum(
                (
                    coordinates[a][0] * coordinates[b][1] - coordinates[b][0] * coordinates[a][1]
                    for a, b in pairs
                ),
                Fraction(0),
            )
            / 2
        )
        assert areas[name] > 0
        source_edges[name] = pairs
    incidence = defaultdict(list)
    cell_areas = {}
    for group in raw["cell_groups"]:
        directed = defaultdict(list)
        cell_areas[group["id"]] = sum((areas[n] for n in group["source_cell_ids"]), Fraction(0))
        for name in group["source_cell_ids"]:
            for a, b in source_edges[name]:
                directed[tuple(sorted((a, b)))].append((a, b))
        for edge, rows in directed.items():
            if len(rows) == 1:
                incidence[edge].append((group["id"], *rows[0]))
            else:
                assert len(rows) == 2 and rows[0] == tuple(reversed(rows[1]))
    removed = set(declaration["removed_cell_ids"])
    assert removed <= set(cell_areas)
    bath_ids = [r["id"] for r in raw["baths"]]
    if raw["bath_assignment"]["kind"] == "one_explicit_bath@1":
        old_baths = {edge: raw["bath_assignment"]["bath_id"] for edge in incidence}
    else:
        old_baths = {
            tuple(sorted(r["vertex_ids"])): r["bath_id"] for r in raw["bath_assignment"]["rows"]
        }
    exposed_baths = {r["membrane_id"]: r["bath_id"] for r in declaration["exposed_baths"]}
    edges, membranes, contacts, exposed = [], [], [], []
    retained_baths = set()
    for edge, owners in incidence.items():
        survivors = [r for r in owners if r[0] not in removed]
        assert len(owners) in (1, 2)
        if len(owners) == 2:
            assert owners[0][1:] == tuple(reversed(owners[1][1:]))
        if not survivors:
            continue
        eid, cid = "edge-" + digest(list(edge)), "contact-" + digest(list(edge))
        edges.append(
            dict(
                id=eid,
                cell_ids=[r[0] for r in survivors],
                vertex_ids=list(edge),
                squared_length_m2=ratio(
                    sum((coordinates[edge[1]][k] - coordinates[edge[0]][k]) ** 2 for k in (0, 1))
                ),
            )
        )
        if len(survivors) == 2:
            contacts.append(cid)
        for cell, a, b in survivors:
            mid = "membrane-" + digest([cell, a, b])
            is_exposed = len(owners) == 2 and len(survivors) == 1
            bath = exposed_baths[mid] if is_exposed else old_baths[edge]
            retained_baths.add(bath)
            if is_exposed:
                exposed.append(
                    dict(
                        membrane_id=mid,
                        bath_id=bath,
                        previous_contact_id=cid,
                        surviving_cell_id=cell,
                    )
                )
            membranes.append(
                dict(
                    id=mid,
                    cell_id=cell,
                    edge_id=eid,
                    bath_id=bath,
                    vertex_ids=[a, b],
                    exposed=is_exposed,
                )
            )
    assert set(exposed_baths) == {r["membrane_id"] for r in exposed}
    assert retained_baths <= set(bath_ids)
    before = sum(cell_areas.values(), Fraction(0))
    kept = sum((a for c, a in cell_areas.items() if c not in removed), Fraction(0))
    lost = sum((a for c, a in cell_areas.items() if c in removed), Fraction(0))
    assert before == kept + lost
    height = Fraction.from_float(raw["height_m"])
    return dict(
        kind="cells.fixed_polygon_removal_fraction_reference@1",
        surviving_cell_ids=[c for c in cell_areas if c not in removed],
        removed_cell_ids=[c for c in cell_areas if c in removed],
        cell_area_m2={c: ratio(a) for c, a in cell_areas.items()},
        cell_volume_m3={c: ratio(a * height) for c, a in cell_areas.items()},
        area_balance=dict(
            before=ratio(before),
            retained=ratio(kept),
            removed=ratio(lost),
            residual=ratio(before - kept - lost),
        ),
        edges=edges,
        membranes=membranes,
        contact_ids=contacts,
        exposed_faces=exposed,
        unused_bath_ids=[c for c in bath_ids if c not in retained_baths],
        production_imports=[],
        numerical_scope="exact ownership and polygon area/volume only",
    )


def main():
    source, target = map(Path, sys.argv[1:])
    available = None
    result = dict(input_path=str(source), status="running")
    try:
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
        assert os.sched_getaffinity(0) == {6}
        available = (
            int(
                next(
                    r.split()[1]
                    for r in Path("/proc/meminfo").read_text().splitlines()
                    if r.startswith("MemAvailable:")
                )
            )
            * 1024
        )
        assert available >= 8 * 2**30
        assert source.stat().st_size <= 16 * 2**20
        payload = json.loads(source.read_text())
        result["inputs"] = payload
        result.update(status="passed", result=solve(payload))
    except Exception as error:
        result.update(
            status="failed",
            failure=dict(
                type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
            ),
        )
        raise
    finally:
        result["worker"] = dict(
            cpu=6,
            address_space_bytes=512 * 2**20,
            host_available_bytes=available,
            scientific_scope="no trajectory",
        )
        with target.open("x") as stream:
            json.dump(result, stream, allow_nan=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())


if __name__ == "__main__":
    main()
