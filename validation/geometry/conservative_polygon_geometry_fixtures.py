"""Deferred explicit polygon recipes, unsupported-domain and owner controls."""

from copy import deepcopy

POSITIVE_CASES = (
    "two-triangles",
    "merged-square",
    "quad-grid",
    "quad-grid-merged",
    "quad-grid-merged-all",
    "concave-merged",
    "disconnected-cells",
    "two-baths",
    "thin-triangle",
    "translated-centroid",
)
DOMAIN_CASES = (
    "clockwise",
    "duplicate-coordinate",
    "repeated-ring-vertex",
    "self-crossing",
    "interior-overlap",
    "t-junction",
    "point-touch",
    "missing-group-member",
    "duplicate-group-member",
    "disconnected-merge",
    "holed-merge",
    "zero-height",
    "zero-thickness",
    "wrong-units",
    "nearest-bath-policy",
    "incomplete-edge-baths",
    "unused-bath",
    "negative-bath-volume",
    "area-underflow",
    "volume-overflow",
)
OWNERSHIP_CASES = (
    "wrong-law",
    "boolean-law",
    "forged-generated-source",
    "changed-request-identity",
    "resealed-binding-owner",
    "returned-copy-alias",
)
CORRUPTION_CASES = (
    "cell-volume",
    "membrane-area",
    "double-junction-area",
    "nonreciprocal-partner",
    "off-edge-midpoint",
    "balanced-wrong-owner",
)
GENERATED_CASES = ("generated-singletons", "generated-merged-interface")
PHYSICAL_CASES = ("two-triangles", "quad-grid-merged", "two-baths")
PHYSICAL_DOMAIN_CASES = (
    "missing-cell",
    "wrong-membrane-cell",
    "wrong-membrane-bath",
    "reversed-contact",
    "missing-contact",
    "bath-volume-override",
    "area-override",
    "negative-diffusivity",
    "zero-specific-capacitance",
    "wrong-opt-in",
    "wrong-geometry-id",
    "existing-closure-refusal",
)
PHYSICAL_OWNERSHIP_CASES = (
    "definition-area",
    "definition-inventory",
    "provenance-owner",
    "returned-copy-alias",
)


def _base(vertices, cells, groups, *, generator):
    return dict(
        source=dict(
            kind="declared_polygon_complex@1",
            generator=generator,
            recipe=dict(
                construction=(
                    "Explicit supplied binary64 vertices and ordered rings; "
                    "no ideal-coordinate invariance claim"
                )
            ),
            generation_coverage=False,
        ),
        vertices=[dict(id=name, xy_m=list(point)) for name, point in vertices],
        source_cells=[dict(id=name, vertex_ids=list(ring)) for name, ring in cells],
        cell_groups=[dict(id=name, source_cell_ids=list(members)) for name, members in groups],
        baths=[dict(id="bath", volume_m3=1e-15)],
        bath_assignment=dict(kind="one_explicit_bath@1", bath_id="bath"),
        height_m=1e-6,
        thickness_m=5e-9,
        axial_caps="sealed_no_transport@1",
        units=dict(coordinates="m", height="m", thickness="m", area="m2", volume="m3"),
    )


def _grid(nx, ny):
    scale = 1e-5
    vertices = [
        (f"v-{x}-{y}", (x * scale, y * scale)) for y in range(ny + 1) for x in range(nx + 1)
    ]
    cells = [
        (f"s-{x}-{y}", [f"v-{x}-{y}", f"v-{x + 1}-{y}", f"v-{x + 1}-{y + 1}", f"v-{x}-{y + 1}"])
        for y in range(ny)
        for x in range(nx)
    ]
    return vertices, cells


def fixture(name):
    if name in ("two-triangles", "merged-square", "two-baths"):
        vertices = [("a", (0.0, 0.0)), ("b", (1e-5, 0.0)), ("c", (1e-5, 1e-5)), ("d", (0.0, 1e-5))]
        cells = [("s0", ["a", "b", "c"]), ("s1", ["a", "c", "d"])]
        groups = (
            [("merged", ["s0", "s1"])]
            if name == "merged-square"
            else [("cell0", ["s0"]), ("cell1", ["s1"])]
        )
        raw = _base(vertices, cells, groups, generator=name)
        if name == "two-baths":
            raw["baths"] = [dict(id="outer", volume_m3=1e-15), dict(id="cleft", volume_m3=2e-16)]
            raw["bath_assignment"] = dict(
                kind="explicit_edge_baths@1",
                rows=[
                    dict(vertex_ids=edge, bath_id="cleft" if edge == ["a", "c"] else "outer")
                    for edge in (["a", "b"], ["b", "c"], ["a", "c"], ["c", "d"], ["a", "d"])
                ],
            )
        return raw
    if name in ("quad-grid", "quad-grid-merged", "quad-grid-merged-all"):
        vertices, cells = _grid(2, 2)
        if name == "quad-grid-merged-all":
            groups = [("all-merged", [cell for cell, _ in cells])]
        elif name == "quad-grid-merged":
            groups = [
                ("left", ["s-0-0", "s-0-1"]),
                ("right-bottom", ["s-1-0"]),
                ("right-top", ["s-1-1"]),
            ]
        else:
            groups = [("physical-" + cell, [cell]) for cell, _ in cells]
        return _base(vertices, cells, groups, generator=name)
    if name == "concave-merged":
        vertices, cells = _grid(2, 2)
        cells = [row for row in cells if row[0] != "s-1-1"]
        used = {v for _, ring in cells for v in ring}
        vertices = [row for row in vertices if row[0] in used]
        return _base(vertices, cells, [("concave", [row[0] for row in cells])], generator=name)
    if name == "disconnected-cells":
        vertices = [
            ("a", (0.0, 0.0)),
            ("b", (1e-5, 0.0)),
            ("c", (0.0, 1e-5)),
            ("d", (3e-5, 0.0)),
            ("e", (4e-5, 0.0)),
            ("f", (3e-5, 1e-5)),
        ]
        return _base(
            vertices,
            [("s0", ["a", "b", "c"]), ("s1", ["d", "e", "f"])],
            [("cell0", ["s0"]), ("cell1", ["s1"])],
            generator=name,
        )
    if name == "thin-triangle":
        return _base(
            [("a", (0.0, 0.0)), ("b", (1e-5, 0.0)), ("c", (1e-5, 1e-16))],
            [("s0", ["a", "b", "c"])],
            [("cell0", ["s0"])],
            generator=name,
        )
    if name == "translated-centroid":
        raw = fixture("merged-square")
        for row in raw["vertices"]:
            row["xy_m"] = [1024.0 + row["xy_m"][0], -2048.0 + row["xy_m"][1]]
        raw["source"]["generator"] = name
        raw["source"]["recipe"]["translation_policy"] = (
            "Actual rounded binary64 coordinates are the input, not an exact real affine transform"
        )
        return raw
    raise ValueError(name)


def domain(name):
    raw = fixture("two-triangles")
    if name == "clockwise":
        raw["source_cells"][0]["vertex_ids"].reverse()
    elif name == "duplicate-coordinate":
        raw["vertices"][1]["xy_m"] = raw["vertices"][0]["xy_m"][:]
    elif name == "repeated-ring-vertex":
        raw["source_cells"][0]["vertex_ids"].append("a")
    elif name == "self-crossing":
        raw = fixture("merged-square")
        raw["source_cells"] = [dict(id="s0", vertex_ids=["a", "c", "b", "d"])]
        raw["cell_groups"] = [dict(id="cell0", source_cell_ids=["s0"])]
    elif name == "interior-overlap":
        raw = _base(
            [
                ("a", (0.0, 0.0)),
                ("b", (2e-5, 0.0)),
                ("c", (0.0, 2e-5)),
                ("d", (1e-6, 1e-6)),
                ("e", (2e-6, 1e-6)),
                ("f", (1e-6, 2e-6)),
            ],
            [("s0", ["a", "b", "c"]), ("s1", ["d", "e", "f"])],
            [("c0", ["s0"]), ("c1", ["s1"])],
            generator=name,
        )
    elif name == "t-junction":
        raw = _base(
            [
                ("a", (0.0, 0.0)),
                ("b", (1e-5, 0.0)),
                ("c", (1e-5, 1e-5)),
                ("d", (0.0, 1e-5)),
                ("e", (2e-5, 0.0)),
                ("f", (2e-5, 5e-6)),
                ("g", (1e-5, 5e-6)),
            ],
            [("s0", ["a", "b", "c", "d"]), ("s1", ["b", "e", "f", "g"])],
            [("c0", ["s0"]), ("c1", ["s1"])],
            generator=name,
        )
    elif name == "point-touch":
        raw = _base(
            [
                ("a", (0.0, 0.0)),
                ("b", (1e-5, 0.0)),
                ("c", (0.0, 1e-5)),
                ("d", (2e-5, 0.0)),
                ("e", (1e-5, 1e-5)),
            ],
            [("s0", ["a", "b", "c"]), ("s1", ["b", "d", "e"])],
            [("c0", ["s0"]), ("c1", ["s1"])],
            generator=name,
        )
    elif name == "missing-group-member":
        raw["cell_groups"].pop()
    elif name == "duplicate-group-member":
        raw["cell_groups"][1]["source_cell_ids"] = ["s0"]
    elif name == "disconnected-merge":
        raw = fixture("disconnected-cells")
        raw["cell_groups"] = [dict(id="merged", source_cell_ids=["s0", "s1"])]
    elif name == "holed-merge":
        vertices, cells = _grid(3, 3)
        raw = _base(
            vertices,
            cells,
            [("ring", [name for name, _ in cells if name != "s-1-1"]), ("centre", ["s-1-1"])],
            generator=name,
        )
    elif name == "zero-height":
        raw["height_m"] = 0.0
    elif name == "zero-thickness":
        raw["thickness_m"] = 0.0
    elif name == "wrong-units":
        raw["units"]["coordinates"] = "um"
    elif name == "nearest-bath-policy":
        raw["bath_assignment"] = dict(kind="nearest_midpoint@1", bath_id="bath")
    elif name == "incomplete-edge-baths":
        raw = fixture("two-baths")
        raw["bath_assignment"]["rows"].pop()
    elif name == "unused-bath":
        raw = fixture("two-baths")
        raw["baths"].append(dict(id="unowned", volume_m3=1e-15))
    elif name == "negative-bath-volume":
        raw["baths"][0]["volume_m3"] = -1e-15
    elif name == "area-underflow":
        tiny = float.fromhex("0x0.0000000000001p-1022")
        raw = _base(
            [("a", (0.0, 0.0)), ("b", (tiny, 0.0)), ("c", (0.0, tiny))],
            [("s0", ["a", "b", "c"])],
            [("c0", ["s0"])],
            generator=name,
        )
    elif name == "volume-overflow":
        raw = _base(
            [("a", (0.0, 0.0)), ("b", (1e150, 0.0)), ("c", (0.0, 1e150))],
            [("s0", ["a", "b", "c"])],
            [("c0", ["s0"])],
            generator=name,
        )
        raw["height_m"] = 1e300
    else:
        raise ValueError(name)
    return raw


def corrupt(name, geometry):
    data = deepcopy(geometry)
    if name == "cell-volume":
        data["cells"][0]["volume_m3"] *= 2
    elif name == "membrane-area":
        data["membranes"][0]["area_m2"] *= 2
    elif name == "double-junction-area":
        data["contacts"][0]["area_m2"] *= 2
    elif name == "nonreciprocal-partner":
        contact = data["contacts"][0]
        i = next(
            i for i, m in enumerate(data["membranes"]) if m["id"] == contact["membrane_ids"][0]
        )
        data["membranes"][i]["partner_id"] = data["membranes"][i]["id"]
    elif name == "off-edge-midpoint":
        data["edges"][0]["midpoint_m"][0] += 1e-6
    elif name == "balanced-wrong-owner":
        first, second = data["cells"][0]["id"], data["cells"][1]["id"]
        a = next(m for m in data["membranes"] if m["cell_id"] == first)
        b = next(m for m in data["membranes"] if m["cell_id"] == second)
        a["cell_id"], b["cell_id"] = b["cell_id"], a["cell_id"]
        data["membrane_incidence"] = [
            [int(owner == m["bath_id"]) - int(owner == m["cell_id"]) for m in data["membranes"]]
            for owner in data["owner_axis"]
        ]
    else:
        raise ValueError(name)
    return data


def generated(name, directory, *, retain):
    if name not in GENERATED_CASES:
        raise ValueError(name)
    if not callable(retain):
        raise ValueError("Generated prelude requires a durable trial retainer")
    from cells.processes import betse_initial_mesh_preparation_cache as cache
    from cells.processes import conservative_polygon_geometry as geometry
    from cells.processes import stable_initial_mesh_preparation as upstream
    from validation.betse import betse_initial_mesh_preparation_fixtures as original

    native_request, inputs = original.reused_B09("irregular-centroid-aux")
    retain("native-request", native_request=native_request, inputs=inputs)
    request = upstream.opt_in(native_request, law_id=upstream.LAW_ID)
    retain("owned-request", native_request=native_request, request=request, inputs=inputs)
    try:
        state = upstream.prepare(request)
    except BaseException as error:
        retain(
            "prepare-failure",
            native_request=native_request,
            request=request,
            state=getattr(error, "trial", None),
            error=error,
            inputs=inputs,
        )
        raise
    retain(
        "prepare-return", native_request=native_request, request=request, state=state, inputs=inputs
    )
    source = cache.plain(state.cache)
    ids = list(state.retained_point_ids)
    selected = None
    if name == "generated-merged-interface":
        for i, ring in enumerate(source["vor_cells"]):
            edges = {tuple(sorted(edge)) for edge in zip(ring, ring[1:] + ring[:1], strict=True)}
            for j in range(i + 1, len(ids)):
                other = source["vor_cells"][j]
                if edges & {
                    tuple(sorted(edge)) for edge in zip(other, other[1:] + other[:1], strict=True)
                }:
                    selected = (i, j)
                    break
            if selected is not None:
                break
        if selected is None:
            raise ValueError("The generated fixture has no exact shared interface")
    groups = []
    if selected:
        groups.append(dict(id="merged-generated", source_cell_ids=[ids[i] for i in selected]))
    groups.extend(
        dict(id="physical-" + str(i), source_cell_ids=[name])
        for i, name in enumerate(ids)
        if selected is None or i not in selected
    )
    try:
        value = geometry.from_generated(
            request,
            state,
            cell_groups=groups,
            baths=[dict(id="bath", volume_m3=1e-15)],
            bath_assignment=dict(kind="one_explicit_bath@1", bath_id="bath"),
            height_m=1e-6,
            thickness_m=5e-9,
            law_id=geometry.LAW_ID,
        )
    except BaseException as error:
        retain(
            "from-generated-replay-failure",
            native_request=native_request,
            request=request,
            state=getattr(error, "trial", None),
            error=error,
            inputs=inputs,
        )
        raise
    retain(
        "from-generated-return",
        native_request=native_request,
        request=request,
        state=state,
        inputs=inputs,
    )
    return value, dict(
        upstream_inputs=inputs,
        source_cell_ids=ids,
        explicit_group_rule=(
            "All singletons, or merge the first exact shared source interface "
            "in declared occurrence order"
        ),
        selected_source_slots=selected,
    )


def physical(bound):
    from cells.core import conservative_polygon_tissue_preparation as bridge

    g = bound.geometry
    species = [dict(id="Na", valence=1), dict(id="Cl", valence=-1)]

    def inventory(row, volume):
        amount = volume * 1e15 * 10
        return dict(
            id=row["id"],
            initial_amount_fmol=dict(Na=amount, Cl=amount),
            initial_charge_C=0.0,
            fixed_charge_equivalent_fmol=0.0,
        )

    cells = [inventory(row, row["volume_m3"]) for row in g["cells"]]
    baths = [
        dict(inventory(row, row["volume_m3"]), reservoir=True, boundary_potential_V=0.0)
        for row in g["baths"]
    ]
    membranes = [
        dict(
            id=row["id"],
            cell_id=row["cell_id"],
            bath_id=row["bath_id"],
            specific_capacitance_F_per_m2=0.01,
            diffusivity_m2_per_s=dict(Na=1e-18, Cl=1e-18),
        )
        for row in g["membranes"]
    ]
    contacts = [
        dict(
            id=row["id"],
            sender=row["sender"],
            receiver=row["receiver"],
            membrane_ids=row["membrane_ids"],
            permeability_m_per_s=dict(Na=3e-9, Cl=3e-9),
        )
        for row in g["contacts"]
    ]
    return dict(
        kind=bridge.REQUEST_KIND,
        opted_in_law=bridge.BRIDGE_ID,
        geometry_identity=bound.identity,
        physics=dict(
            species=species,
            temperature_K=310.0,
            cells=cells,
            baths=baths,
            membranes=membranes,
            contacts=contacts,
            closure=dict(
                law="resolved_capacitor_components_current_continuity@1", gauge_reference=None
            ),
            provenance=dict(
                classification=(
                    "Manufactured neutral initial inventories, uniform explicit "
                    "coefficients and held baths; no calibration"
                )
            ),
        ),
        experiment=dict(
            end_time=1e-6,
            observation_times=[0.0, 1e-6],
            membrane_controls=[
                dict(membrane_id=row["id"], schedule=[dict(time=0.0, availability=1.0)])
                for row in membranes
            ],
            junction_controls=[
                dict(junction_id=row["id"], schedule=[dict(time=0.0, availability=1.0)])
                for row in contacts
            ],
        ),
        execution=dict(
            dt=1e-7,
            jit=False,
            backend="cpu",
            precision="float64",
            solver="rk4",
            capacity=len(cells),
            extracellular_capacity=len(baths),
            membrane_capacity=len(membranes),
            edge_capacity=len(contacts),
            face_capacity=0,
            max_steps=20,
            max_trace_bytes=2**20,
            material_balance_atol_fmol=dict(Na=1e-14, Cl=1e-14),
            field_solver="capacitive_reduction_gauged_damped_newton@1",
        ),
    )


def physical_domain(name, bound):
    raw = physical(bound)
    p = raw["physics"]
    if name == "missing-cell":
        p["cells"].pop()
    elif name == "wrong-membrane-cell":
        p["membranes"][0]["cell_id"] = "missing-owner"
    elif name == "wrong-membrane-bath":
        p["membranes"][0]["bath_id"] = "missing-bath"
    elif name == "reversed-contact":
        row = p["contacts"][0]
        row["sender"], row["receiver"] = row["receiver"], row["sender"]
    elif name == "missing-contact":
        p["contacts"].pop()
    elif name == "bath-volume-override":
        p["baths"][0]["volume_m3"] = 1.0
    elif name == "area-override":
        p["membranes"][0]["area_m2"] = 1.0
    elif name == "negative-diffusivity":
        p["membranes"][0]["diffusivity_m2_per_s"]["Na"] = -1e-18
    elif name == "zero-specific-capacitance":
        p["membranes"][0]["specific_capacitance_F_per_m2"] = 0.0
    elif name == "wrong-opt-in":
        raw["opted_in_law"] = "native_geometry_passive_tissue@1"
    elif name == "wrong-geometry-id":
        raw["geometry_identity"] = "0" * 64
    elif name == "existing-closure-refusal":
        p["closure"]["law"] = "unsupported_closure@1"
    else:
        raise ValueError(name)
    return raw
