"""What Part 2's committed rehearsal files and the runs outside the checkout say of each other.

    verify2.py ROOT       ROOT is the rehearsal's scratch folder (its origin, science and plants)

1. inputs_rehearsal_part2.json is what make_inputs2.py makes.
2. The definitions of the origin folder are what make_inputs2.py makes, and have their sha256.
3. The capture ended with every job ok, and every file has the sha256 its MANIFEST.json gives; the
   legacy file pins that manifest.
4. Every file of a planted run has the sha256 that plants_manifest_rehearsal_part2.json gives.
5. The margins: every world has every mechanism with a home, and which of them are not tested.
6. The profile names only what exists, and is what make_profile2.py makes.
7. No committed file holds a home path.
"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_inputs2 as m  # noqa: E402
import make_profile2  # noqa: E402
import reference2  # noqa: E402

HERE = Path(__file__).resolve().parent


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def inputs():
    same = json.loads(json.dumps(m.inputs())) == read("inputs_rehearsal_part2.json")
    print("inputs_rehearsal_part2.json is make_inputs2.py's:", same)
    return same


def origin(root):
    folder, ok = Path(root) / "origin", True
    manifest = json.loads((folder / "manifest.json").read_text())
    jobs = json.loads((folder / "jobs-science.json").read_text())
    for job in jobs:
        path = folder / job["definition"]
        if json.loads(path.read_text()) != json.loads(json.dumps(m.definition_of(job))):
            ok = False
            print("  DEPARTS", path)
        if sha256(path) != manifest["files_sha256"][str(path.relative_to(folder))]:
            ok = False
            print("  SHA256", path)
    print(len(jobs), "definitions are make_inputs2.py's and have their sha256:", ok)
    return ok


def capture(root):
    folder, ok = Path(root) / "science", True
    manifest = json.loads((folder / "MANIFEST.json").read_text())
    pins = read("legacy_rehearsal_part2.json")["captures"]
    if sha256(folder / "MANIFEST.json") != pins["science_manifest_sha256"]:
        ok = False
        print("  the legacy file pins another manifest")
    if sha256(Path(root) / "origin" / "manifest.json") != pins["origin_manifest_sha256"]:
        ok = False
        print("  the legacy file pins another origin")
    status, files = {j["status"] for j in manifest["jobs"]}, 0
    for name, row in manifest["files"].items():
        if name in ("logs/capture.log", "logs/finish.log"):  # Written after the manifest.
            continue
        files += 1
        if sha256(folder / name) != row["sha256"]:
            ok = False
            print("  SHA256", folder / name)
    ok &= status == {"ok"}
    print(len(manifest["jobs"]), "jobs", status, files, "files have their sha256:", ok)
    return ok


def plants():
    manifest, ok = read("plants_manifest_rehearsal_part2.json"), True
    outcomes = {}
    for run in manifest["runs"]:
        folder = Path(run["output_folder"])
        for name, digest in run["outputs_sha256"].items():
            if sha256(folder / name) != digest:
                ok = False
                print("  SHA256", folder / name)
        key = run["outcome"].split(":")[0]
        outcomes[key] = outcomes.get(key, 0) + 1
    print(len(manifest["runs"]), "planted runs", outcomes, "have their sha256:", ok)
    return ok


def margins():
    data, inputs_, ok = read("margins_rehearsal_part2.json"), read("inputs_rehearsal_part2.json"), 1
    ok = bool(ok)
    for world, b in data["worlds"].items():
        scales = set(inputs_["worlds"][world]["scales"])
        if set(b["entries"]) != scales:
            ok = False
            print("  ENTRIES", world, set(b["entries"]) ^ scales)
        empty = [k for k, v in b["mechanisms"].items() if not v or not all(v.values())]
        if empty:
            ok = False
            print("  NO HOME", world, empty)
        reference2.report(world, b)
    return ok


def profile():
    value = read("profile_rehearsal_part2.json")
    ok = make_profile2.check(value)
    return ok and value == json.loads(json.dumps(make_profile2.profile()))


def no_home_path():
    home = str(Path.home())
    bad = [p.name for p in sorted(HERE.iterdir()) if p.is_file() and home in p.read_text()]
    print("files that hold a home path:", bad or "none")
    return not bad


def main(root):
    results = dict(
        inputs=inputs(),
        origin=origin(root),
        capture=capture(root),
        plants=plants(),
        margins=margins(),
        profile=profile(),
        no_home_path=no_home_path(),
    )
    print(results)
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
