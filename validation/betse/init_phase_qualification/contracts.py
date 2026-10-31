"""Exact evidence paths derived statically from the reviewed 62-check source."""

from pathlib import Path

from common import canonical, require

MODES = ("nak", "material", "calcium", "channels", "network", "mechanics", "field")
PARENT_DEPENDENCIES = frozenset(
    (
        "foreign_parent",
        "changed_clock",
        "rebound_count",
        "inactive_count_forgery",
        "inactive_cold_gate_forgery",
        "changed_setup_store",
        "changed_rate_presence",
        "changed_previous_field",
        "changed_mechanics_parent",
        "changed_phase_receipt",
        "native_sample_refusal",
    )
)
RAW_CALLBACKS = {
    "negative_static_Dm": ("setup",),
    "NaK_nonfinite": ("setup", "cold", "bootstrap", "nak"),
    "CaATP_nonfinite": (
        "setup",
        "cold",
        "bootstrap",
        "nak",
        "material",
        "calcium",
        "network",
        "mechanics",
    ),
    "GRN_negative": (
        "setup",
        "cold",
        "bootstrap",
        "nak",
        "material",
        "calcium",
        "network",
    ),
    "mechanics_nonfinite": (
        "setup",
        "cold",
        "bootstrap",
        "nak",
        "material",
        "calcium",
        "network",
        "mechanics",
    ),
}
RAW_EXPECTATIONS = {
    "negative_static_Dm": ("effective_static_diffusion_guard", "membrane diffusion"),
    "NaK_nonfinite": ("nak", "Nonfinite complete ordinary INIT NaK output"),
    "CaATP_nonfinite": (
        "material_calcium_network_mechanics",
        "Nonfinite literal native ECM material trial",
    ),
    "GRN_negative": ("material_calcium_network_mechanics", "Network concentration of"),
    "mechanics_nonfinite": (
        "material_calcium_network_mechanics",
        "Nonfinite complete mechanics output",
    ),
}


def declaration(spec):
    case, category = spec["case"], spec["category"]
    require(
        category in ("positive", "raw", "observer", "dependency"),
        "Unknown INIT category",
    )
    require(
        type(spec["accepted_calls"]) is int
        and type(spec["independent_forms"]) is int
        and len(spec["node_ids"]) == 1,
        "Exact one-check declaration",
    )
    paths, points, files = [], [], []
    native_case = "observer-" + case if category == "observer" else case
    native = category != "dependency"
    if native:
        paths += [
            "isolated-" + native_case + "/native",
            "isolated-" + native_case + "/native-source-return-before-runtime",
            native_case + "-native-return-before-assertions",
        ]
        files += [
            "isolated-" + native_case + "/inputs.json",
            "isolated-" + native_case + "/native.stdout.log",
        ]
    if category == "positive":
        count = spec["accepted_calls"]
        require(
            count in (0, 1, 3) and spec["independent_forms"] == 6 + 14 * count,
            "Original positive call/form counts",
        )
        paths += [
            case + suffix
            for suffix in (
                "-inputs-before-any-evaluation",
                "-setup-return-before-cold",
                "-cold-return-before-finalization",
                "-bootstrap-input",
                "-initialized-return-before-comparison",
                "-setup-errors",
                "-cold-errors",
                "-bootstrap-errors",
            )
        ]
        points += [
            (mode, "preparation-" + case + "/" + mode) for mode in ("setup", "cold", "bootstrap")
        ]
        files += ["isolated-" + case + "/comparison.json"]
        for index in range(count):
            paths += [f"{case}-call-{index}-{mode}-input-before-reference" for mode in MODES]
            paths += [f"{case}-call-{index}-full-return-before-comparison"]
            paths += [f"{case}-{index}-{mode}-errors" for mode in MODES]
            points += [(mode, f"preparation-{case}/point-{index}/{mode}") for mode in MODES]
    elif category == "raw":
        require(case in RAW_CALLBACKS, "Exact raw-case roster")
        paths += [case + "-raw-inputs", case + "-raw-failure-before-assertions"]
        paths += [case + "-raw-" + mode + "-before-first-call" for mode in RAW_CALLBACKS[case]]
    elif category == "observer":
        require(case in ("before_call", "after_call"), "Exact observer cases")
        paths += [
            case + "-call-0-observer-before_call",
            case + "-call-0-retained-exception",
        ]
        if case == "after_call":
            paths += [case + "-call-0-observer-after_call"]
    else:
        paths += [case + "-rejected-inputs-before-check", case + "-exact-refusal"]
        if case in PARENT_DEPENDENCIES:
            paths += [case + "-unmodified-parent"]
    if category != "positive":
        require(
            spec["accepted_calls"] == spec["independent_forms"] == 0,
            "Controls cannot acquire call/form credit",
        )
    require(len(paths) == len(set(paths)), "Duplicate archive declaration")
    for path in paths + files:
        canonical(path)
    for mode, folder in points:
        files += [
            folder + "/" + name
            for name in (
                "inputs.json",
                "comparison.json",
                "reference-1.json",
                "reference-2.json",
                "reference-1.stdout.log",
                "reference-2.stdout.log",
            )
        ]
        for level, precision in ((1, 100), (2, 160)):
            if mode in ("setup", "nak", "channels", "material"):
                files += [f"{folder}/raw-reference-{level}/{mode}-decimal-{precision}.json"]
            elif mode == "mechanics":
                files += [
                    f"{folder}/raw-reference-{level}/{name}-{precision}.json"
                    for name in ("raw-decimal", "projected-reference")
                ]
    return dict(
        typed_archives=sorted(paths),
        required_files=sorted(files),
        reference_points=[dict(mode=mode, folder=folder) for mode, folder in points],
        native_case=native_case if native else None,
    )


def verify_roster(base, roster):
    base = Path(base)
    require(base.is_dir() and not base.is_symlink(), "Real evidence root")
    expected = set(roster["typed_archives"])
    actual = set()
    for path in base.rglob("*"):
        require(not path.is_symlink(), "Evidence links are not accepted")
        require(
            not path.name.endswith(".failure.json"),
            "Failed fresh worker is not completed reference/native evidence",
        )
        if path.is_file() and path.name in ("manifest.json", "data.json", "arrays.npz"):
            actual.add(str(path.parent.relative_to(base)))
    require(
        actual == expected,
        "Exact complete typed archive roster: missing="
        + str(sorted(expected - actual))
        + " extra="
        + str(sorted(actual - expected)),
    )
    for name in expected:
        folder = base / name
        require(
            {p.name for p in folder.iterdir()} == {"manifest.json", "data.json", "arrays.npz"}
            and all(p.is_file() and not p.is_symlink() for p in folder.iterdir()),
            "Incomplete or extra typed archive payload: " + name,
        )
    for name in roster["required_files"]:
        path = base / name
        require(
            path.is_file() and not path.is_symlink(),
            "Missing required evidence: " + name,
        )
    expected_refs = {
        point["folder"] + f"/reference-{level}.json"
        for point in roster["reference_points"]
        for level in (1, 2)
    }
    observed_refs = {
        str(path.relative_to(base))
        for name in ("reference-1.json", "reference-2.json")
        for path in base.rglob(name)
    }
    require(observed_refs == expected_refs, "Exact fresh independent reference roster")
    expected_raw = {name for name in roster["required_files"] if "/raw-reference-" in name}
    observed_raw = {
        str(path.relative_to(base))
        for path in base.rglob("*.json")
        if any(p.startswith("raw-reference-") for p in path.relative_to(base).parts)
    }
    require(observed_raw == expected_raw, "Exact retained Decimal raw-form roster")
    return dict(
        typed_archives=len(expected),
        reference_forms=len(expected_refs),
        raw_decimal_files=len(expected_raw),
        required_files=len(roster["required_files"]),
    )
