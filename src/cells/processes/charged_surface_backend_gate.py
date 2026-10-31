"""External scalar qualification and backend release dependencies, before imports."""

import hashlib
import sys
from pathlib import Path

from cells.processes import charged_surface_work as scalar
from cells.processes.charged_surface_backend_plan import (
    SCALAR_MANIFEST_SHA256,
    SCALAR_TEST_SUCCESSOR_MANIFEST_SHA256,
)


class HeldDependencyError(ValueError):
    pass


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(row):
    if type(row) is not dict or set(row) != {"path", "sha256"}:
        raise HeldDependencyError("An exact external receipt path/SHA256 is required")
    path = Path(row["path"])
    if (
        not path.is_absolute()
        or not path.is_file()
        or path.stat().st_size > 2**20
        or sha(path) != row["sha256"]
    ):
        raise HeldDependencyError("External receipt path, bytes or digest differ")
    return scalar.parse(path.read_text())


def authorize(release_path, execution):
    """Source preparation and descriptive HELD flags cannot release numerics."""
    if release_path is None:
        raise HeldDependencyError(
            "Scalar acceptance and a separate Root/Chief backend release are required"
        )
    root = Path(__file__).resolve().parents[4]
    manifest_path = root / "MANIFEST.json"
    if (
        Path(__file__).resolve()
        != root / "source/src/cells/processes/charged_surface_backend_gate.py"
        or not manifest_path.is_file()
        or not (root / "metadata/dependencies.json").is_file()
    ):
        raise HeldDependencyError(
            "Execution requires a separately released frozen source snapshot; "
            "repository integration does not authorize numerical execution"
        )
    release_file = Path(release_path)
    if (
        not release_file.is_absolute()
        or release_file.is_relative_to(root)
        or release_file.stat().st_size > 2**20
    ):
        raise HeldDependencyError(
            "A bounded, explicit release outside the held source packet is required"
        )
    release = scalar.parse(release_file.read_text())
    fields = {
        "kind",
        "authorized_by",
        "execution_authorized",
        "scope",
        "mode",
        "source_manifest_sha256",
        "scalar_source_manifest_sha256",
        "scalar_acceptance",
        "scalar_qualification_manifest",
        "cpu_backend_acceptance",
    }
    if (
        set(release) != fields
        or release["kind"] != "cells.charged_surface_backend_release@1"
        or release["authorized_by"] not in ("Root", "Chief")
    ):
        raise HeldDependencyError("Exact separately authorized backend release contract required")
    if (
        release["execution_authorized"] is not True
        or release["scope"] != "same_bounded_charged_surface_owner@1"
        or release["source_manifest_sha256"] != sha(manifest_path)
        or release["scalar_source_manifest_sha256"] != SCALAR_MANIFEST_SHA256
    ):
        raise HeldDependencyError(
            "Backend release is held, changed in scope or bound to different source"
        )
    accepted = reference(release["scalar_acceptance"])
    qualified_manifest = reference(release["scalar_qualification_manifest"])
    if release["scalar_qualification_manifest"]["sha256"] != SCALAR_TEST_SUCCESSOR_MANIFEST_SHA256:
        raise HeldDependencyError("Exact Root-reviewed scalar test successor required")
    dependencies = scalar.parse(
        (root / "metadata" / "dependencies.json").read_text(), max_bytes=16 * 2**20
    )
    for relative, expected in dependencies["copied_scalar_files"].items():
        if qualified_manifest["files"].get(relative, {}).get("sha256") != expected["sha256"]:
            raise HeldDependencyError(
                "Accepted scalar successor changes runtime/control bytes: " + relative
            )
    if (
        accepted.get("kind") != "cells.charged_surface_scalar_qualification@1"
        or accepted.get("accepted") is not True
        or accepted.get("source_review_passed") is not True
        or accepted.get("numerical_cpu_passed") is not True
        or accepted.get("source_manifest_sha256")
        != release["scalar_qualification_manifest"]["sha256"]
        or accepted.get("implementation_sha256")
        != sha(root / "source/src/cells/processes/charged_surface_work.py")
    ):
        raise HeldDependencyError("This exact scalar/source owner is not independently accepted")
    if execution["backend"] == "cpu":
        if release["mode"] != "cpu_qualification" or release["cpu_backend_acceptance"] is not None:
            raise HeldDependencyError("CPU qualification requires its separately declared mode")
    else:
        if release["mode"] != "gpu_qualification":
            raise HeldDependencyError(
                "GPU execution needs a separate explicit qualification release"
            )
        cpu = reference(release["cpu_backend_acceptance"])
        if (
            cpu.get("kind") != "cells.charged_surface_cpu_backend_qualification@1"
            or cpu.get("accepted") is not True
            or cpu.get("source_manifest_sha256") != sha(manifest_path)
        ):
            raise HeldDependencyError("GPU preparation does not establish CPU/JAX qualification")
    manifest = scalar.parse(manifest_path.read_text(), max_bytes=16 * 2**20)
    for relative, row in manifest["files"].items():
        path = root / relative
        if path.is_symlink() or not path.is_file() or sha(path) != row["sha256"]:
            raise HeldDependencyError("Held source changed: " + relative)
    # Match the existing frozen-source execution convention: importing a live
    # Cells installation must not silently satisfy this held component.
    for name, module in tuple(sys.modules.items()):
        if name.split(".")[0] != "cells":
            continue
        origin = getattr(module, "__file__", None)
        if origin is None:
            raise HeldDependencyError("Unbound Cells namespace origin: " + name)
        try:
            relative = str(Path(origin).resolve().relative_to(root))
        except ValueError as error:
            raise HeldDependencyError("Live/unpinned Cells import origin: " + name) from error
        if (
            relative not in manifest["files"]
            or sha(root / relative) != manifest["files"][relative]["sha256"]
        ):
            raise HeldDependencyError(
                "Loaded Cells module is outside the frozen source manifest: " + name
            )
    return dict(
        release_sha256=sha(release_file),
        scalar_acceptance=release["scalar_acceptance"],
        scalar_qualification_manifest=release["scalar_qualification_manifest"],
        source_manifest_sha256=sha(manifest_path),
        mode=release["mode"],
        authorized_by=release["authorized_by"],
    )
