"""Deferred explicit manufactured caller recipes; no eager geometry evaluation."""

import hashlib
import json
from pathlib import Path

from cells.processes import stable_seed_explicit_ecm_partition as constructor

CASES = ("one-cell", "unequal-clefts", "two-cells", "four-cells", "translated-cell")
BASE = "one-cell"


def declaration(case):
    path = Path(__file__).with_name("stable_seed_explicit_ecm_partition_callers.json")
    data = json.loads(path.read_text())
    row = next(row for row in data["cases"] if row["id"] == case)
    layout = {
        key: [float.fromhex(value) for value in values] for key, values in row["layout_hex"].items()
    }
    nx, ny = len(layout["x_centres_m"]), len(layout["y_centres_m"])
    return dict(
        kind=constructor.INPUT_KIND,
        opted_in_law=constructor.LAW_ID,
        source=dict(
            kind="explicit_manufactured_seed_owners@1",
            authority=data["authority"],
            document_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            field="cases[" + case + "].seeds/layout_hex",
            prior_full_domain_cells_reclassified=False,
            native_equivalence=False,
        ),
        domain=dict(
            id="explicit-manufactured-domain-" + case,
            vertices_m=[[float.fromhex(v) for v in point] for point in row["domain_vertices_hex"]],
            authority_field="cases[" + case + "].domain_vertices_hex",
        ),
        layout=layout,
        cell_owners=[
            dict(
                id=seed["id"],
                slot=seed["slot"],
                seed_xy_m=[
                    layout["x_centres_m"][seed["slot"][0]],
                    layout["y_centres_m"][seed["slot"][1]],
                ],
            )
            for seed in row["seeds"]
        ],
        bath_owners=[
            dict(id="caller-bath-" + str(i) + "-" + str(j), slot=[i, j])
            for j in range(2 * ny + 1)
            for i in range(2 * nx + 1)
            if not (i % 2 == j % 2 == 1)
        ],
        height_m=float.fromhex(data["height_m_hex"]),
        membrane_thickness_m=data["membrane_thickness_m"],
        units=dict(coordinates="m", height="m", membrane_path="m", area="m2", volume="m3"),
        membrane_geometry_policy="zero_volume_interface_explicit_path@1",
        face_distance_policy="orthogonal_volume_centroids_shared_face@1",
        boundary_policy="sealed_no_transport@1",
        rounding_policy="all_grid_lines_exact_binary64_declared_widths_exact@1",
        old_cache_policy=dict(
            kind="invalidate_all_prior_geometry_and_operators@1", provided_cached_operators=None
        ),
        scope="new_manufactured_cell_and_bath_geometry_no_native_or_prior_cell_equivalence",
    )
