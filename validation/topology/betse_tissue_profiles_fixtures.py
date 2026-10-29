"""Small explicit tissue/profile/event inputs; no production or array imports."""

IONS = ("Na", "K", "Cl", "Ca", "M", "P")


def profile(name="Patch", picker="indices", **changes):
    row = dict(
        name=name,
        picker=picker,
        indices=[4, 1, 4],
        color="blue",
        percent=40.0,
        bitmap=[[255, 255, 255, 255], [0, 0, 255, 255], [0, 0, 255, 254], [255, 255, 255, 255]],
        rgba=False,
        insular=False,
        diffusivity_m2_s=[(i + 1) * 2e-18 for i in range(6)],
    )
    row.update(changes)
    return row


def event(kind="Na_mem", profiles=None, **changes):
    row = dict(
        name=kind,
        kind=kind,
        profiles=["Patch"] if profiles is None else profiles,
        on_s=0.2,
        off_s=0.8,
        change_s=0.12,
        amplitude=2.0,
        function="None",
    )
    row.update(changes)
    return row


def base(name="overlapping-profiles"):
    ids = ["C7", "A2", "Z9", "B0", "P5"]
    owners = [0, 1, 0, 2, 3, 1, 4, 2, 4, 1, 2, 3, 4, 2, 4, 4]
    groups = [[i for i, owner in enumerate(owners) if owner == cell][::-1] for cell in range(5)]
    partner = list(range(len(owners)))
    for a, b in ((0, 3), (1, 4), (5, 6), (7, 12)):
        partner[a], partner[b] = b, a
    neighbors = [[] for _ in ids]
    for a, b in ((0, 2), (1, 3), (1, 4), (2, 4), (0, 4)):
        neighbors[a].append(b)
        neighbors[b].append(a)
    centers = [[0.0, 0.0], [1e-5, 3e-5], [2e-5, 1e-5], [3e-5, 4e-5], [4e-5, 2e-5]]
    layout = dict(
        cell_ids=ids,
        membrane_ids=["mem-" + str(i) for i in range(16)],
        environment_ids=["ecm-" + str(i) for i in range(6)],
        membrane_cell=owners,
        membrane_environment=[(3 * i + owner) % 6 for i, owner in enumerate(owners)],
        cell_membranes=groups,
        cell_centres_m=centers,
        bounds_m=[0.0, 4e-5, 0.0, 4e-5],
        seed_fills=["red", "blue", "red", "RED", "blue"],
        partner_membrane=partner,
        cell_neighbors=neighbors,
        membrane_midpoints_m=[
            [centers[owner][0] + (i % 3) * 1e-7, centers[owner][1] - (i % 2) * 1e-7]
            for i, owner in enumerate(owners)
        ],
    )
    return dict(
        name=name,
        layout=layout,
        enabled=True,
        is_ecm=True,
        seed=17,
        default=profile("Default", "all", diffusivity_m2_s=[(i + 1) * 1e-18 for i in range(6)]),
        profiles=[
            profile("Patch", "indices", indices=[1, 2, 4], insular=True),
            profile("Overlap", "indices", indices=[2, 3]),
        ],
        ion_enabled=[True] * 6,
        events=[],
        times_s=[-0.5, 0.2, 0.5, 0.8, 1.5],
        initial_membrane_m2_s=[
            [1e-17 + (ion * 0.1 + m * 0.01) * 1e-18 for m in range(16)] for ion in range(6)
        ],
        initial_scheduled_m2_s=[[0.2e-18 + ion * 0.01e-18 for _ in range(16)] for ion in range(6)],
        pressure_base_Pa=[1.0 + i * 0.1 for i in range(5)],
        pressure_mod_Pa=[0.1 * i for i in range(5)],
        environment_base_m2_s=[
            [1e-10 * (1 + ion * 0.1 + j * 0.03) for j in range(6)] for ion in range(6)
        ],
        environment_current_m2_s=[
            [2e-10 * (1 + ion * 0.1 + j * 0.03) for j in range(6)] for ion in range(6)
        ],
        environment_free_m2_s=[1e-9 * (1 + ion * 0.1) for ion in range(6)],
        environment_weight_base=[0.2 + 0.05 * j for j in range(6)],
        environment_weight_current=[0.8 - 0.03 * j for j in range(6)],
        environment_shape=[2, 3],
        gradient_x=dict(exponent=2.0, slope=0.7, x_offset=0.1, z_offset=0.2),
    )


def cases():
    result = [base()]
    for name, profiles in (
        ("default-only", []),
        ("all-later-overwrites", [profile("All", "all")]),
        ("color-exact", [profile("Color", "color", color="red")]),
        ("color-case-exact", [profile("Color", "color", color="RED")]),
        ("color-empty", [profile("Empty", "color", color="missing")]),
        ("indices-duplicates-order", [profile("Patch", indices=[4, 1, 4])]),
        ("indices-empty", [profile("Empty", indices=[])]),
        ("image-flip-threshold", [profile("Mask", "image")]),
        ("image-alpha-ignored", [profile("Mask", "image", rgba=True)]),
        ("percent-zero-alias", [profile("Random", "percent", percent=0.0)]),
        ("percent-floor-alias", [profile("Random", "percent", percent=33.3)]),
        ("percent-all-alias", [profile("Random", "percent", percent=100.0)]),
        (
            "percent-all-multiple-alias",
            [
                profile("R1", "percent", percent=40.0),
                profile("All", "all"),
                profile("R2", "percent", percent=60.0),
            ],
        ),
        (
            "insular-overlap-union",
            [
                profile("Patch", indices=[0, 2], insular=True),
                profile("Other", indices=[2, 4], insular=True),
            ],
        ),
    ):
        row = base(name)
        row["profiles"] = profiles
        result.append(row)
    row = base("profiles-disabled")
    row["enabled"] = False
    result.append(row)
    row = base("ECM-disabled-maps-absent")
    row["is_ecm"] = False
    result.append(row)
    row = base("ions-disabled-preserve")
    row["ion_enabled"] = [True, False, True, False, True, True]
    result.append(row)
    row = base("default-picker-ignored")
    row["default"].update(picker="image", missing_image=True)
    result.append(row)
    for kind in ("Na_mem", "K_mem", "Cl_mem", "Ca_mem", "pressure", "ecmJ"):
        row = base("event-" + kind)
        row["events"] = [
            event(
                kind, ["Overlap", "Patch", "Overlap"], amplitude=4.0 if kind == "pressure" else 1.3
            )
        ]
        result.append(row)
    row = base("event-all-kinds-and-order")
    row["events"] = [
        event(kind, ["Patch", "Overlap"], amplitude=(-3.0 if kind == "pressure" else 0.7))
        for kind in ("ecmJ", "pressure", "Ca_mem", "Na_mem", "Cl_mem", "K_mem")
    ]
    result.append(row)
    row = base("event-disabled-NaK-unguarded")
    row["ion_enabled"] = [False, False, True, True, True, True]
    row["events"] = [event("Na_mem"), event("K_mem")]
    result.append(row)
    row = base("event-disabled-ClCa-guarded")
    row["ion_enabled"] = [True, True, False, False, True, True]
    row["events"] = [event("Cl_mem"), event("Ca_mem")]
    result.append(row)
    row = base("event-empty-membrane-selection")
    row["profiles"] = [profile("Empty", indices=[])]
    row["events"] = [event("Na_mem", ["Empty"])]
    result.append(row)
    row = base("event-gradient-occurrence-order")
    row["events"] = [event("Na_mem", ["Default"], function="gradient_x")]
    result.append(row)
    row = base("event-percent-pressure-alias")
    row["profiles"] = [profile("Random", "percent", percent=40.0)]
    row["events"] = [event("pressure", ["Default"], amplitude=5.0)]
    result.append(row)
    row = base("event-reversed-pulse")
    row["events"] = [event("pressure", on_s=0.8, off_s=0.2, amplitude=2.0)]
    result.append(row)
    row = base("global-GJ-prefix")
    row["global_gj_percent"] = 37.9
    result.append(row)
    row = base("event-gradient-duplicate-last")
    row["profiles"] = [profile("Repeat", indices=[4, 1, 4, 1])]
    row["events"] = [event("Na_mem", ["Repeat"], function="gradient_x")]
    result.append(row)
    row = base("event-percent-pressure-gradient-alias")
    row["profiles"] = [profile("Random", "percent", percent=40.0)]
    row["events"] = [event("pressure", ["Default"], function="gradient_x")]
    result.append(row)
    row = base("percent-then-color-indices")
    row["profiles"] = [
        profile("R", "percent"),
        profile("Blue", "color"),
        profile("Raw", indices=[0, 3]),
        profile("All", "all"),
    ]
    result.append(row)
    row = base("bitmap-rectangle-clamping")
    row["layout"]["cell_centres_m"][0] = [-1e-5, 2e-5]
    row["profiles"] = [profile("Mask", "image")]
    result.append(row)
    row = base("bitmap-hole-is-not-hull")
    row["layout"]["cell_centres_m"][0] = [2e-5, 2e-5]
    row["profiles"] = [
        profile(
            "Mask", "image", bitmap=[[0, 0, 0, 0], [0, 255, 255, 0], [0, 255, 255, 0], [0, 0, 0, 0]]
        )
    ]
    result.append(row)
    return result


def limitations():
    result = []
    for name, profiles in (
        ("duplicate-profile-name", [profile("Default")]),
        ("unsupported-picker", [profile(picker="unknown")]),
        ("negative-indices-wrap", [profile(indices=[-1])]),
        ("out-of-range-indices", [profile(indices=[99])]),
        ("boolean-indices", [profile(indices=[True, False, False, True, False])]),
        ("percent-out-of-range", [profile(picker="percent", percent=101.0)]),
        ("image-missing-file", [profile(picker="image", missing_image=True)]),
        ("image-white-hull", [profile(picker="image", bitmap=[[255] * 4 for _ in range(4)])]),
        (
            "image-collinear-hull",
            [profile(picker="image", bitmap=[[255] * 4, [0] * 4, [255] * 4, [255] * 4])],
        ),
        ("image-nonsquare", [profile(picker="image", bitmap=[[0, 0, 255, 255]] * 5)]),
        (
            "image-too-small-fast-spline",
            [profile(picker="image", bitmap=[[0, 0, 255], [0, 0, 255], [255, 255, 255]])],
        ),
        ("color-without-SVG", [profile(picker="color")]),
    ):
        row = base(name)
        row["profiles"] = profiles
        row["expected_failure"] = name not in ("negative-indices-wrap", "boolean-indices")
        if name == "color-without-SVG":
            row["layout"]["seed_fills"] = None
        result.append(row)
    for name, changes in (
        (
            "event-empty-env-key",
            dict(profiles=[profile("Empty", indices=[])], events=[event("ecmJ", ["Empty"])]),
        ),
        ("event-ECM-disabled", dict(is_ecm=False, events=[event("ecmJ")])),
        ("event-unknown-profile", dict(events=[event("Na_mem", ["Absent"])])),
        (
            "gradient-subset-unbound-axis",
            dict(events=[event("Na_mem", ["Patch"], function="gradient_x")]),
        ),
        ("event-python-None-function", dict(events=[event("Na_mem", function=None)])),
        ("event-zero-transition", dict(events=[event("pressure", change_s=0.0)])),
    ):
        row = base(name)
        row.update(changes)
        row["expected_failure"] = True
        result.append(row)
    row = base("gradient-equal-count-axis-confusion")
    row["layout"].update(
        membrane_ids=["one-" + str(i) for i in range(5)],
        membrane_cell=list(range(5)),
        membrane_environment=list(range(5)),
        cell_membranes=[[i] for i in range(5)],
        partner_membrane=list(range(5)),
        membrane_midpoints_m=row["layout"]["membrane_midpoints_m"][:5],
    )
    row["initial_membrane_m2_s"] = [v[:5] for v in row["initial_membrane_m2_s"]]
    row["initial_scheduled_m2_s"] = [v[:5] for v in row["initial_scheduled_m2_s"]]
    row["events"] = [event("pressure", ["Default"], function="gradient_x")]
    row["expected_failure"] = False
    result.append(row)
    return result
