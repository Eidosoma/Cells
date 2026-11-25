"""What the committed rehearsal files and the runs outside the checkout say of each other.

    verify.py ROOT        ROOT is the rehearsal's scratch folder (its origin*, science*, plants)

1. inputs_rehearsal.json is what make_inputs.py makes.
2. The definitions of each origin folder are what make_inputs.py makes, and have their manifest's
   sha256.
3. Each capture set ended with every job ok, and every file has the sha256 its MANIFEST.json gives.
4. Every file of a planted run has the sha256 that plants_manifest_rehearsal.json gives.
5. The margins: every world that a plant can move has every mechanism with a home, and the smallest
   margin of a home is at least 10 (PLANTS.md section 1).
6. The profile names only what exists.
"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_inputs  # noqa: E402
import make_profile  # noqa: E402

HERE = Path(__file__).resolve().parent


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def inputs():
    same = json.loads(json.dumps(make_inputs.inputs())) == read("inputs_rehearsal.json")
    print("inputs_rehearsal.json is make_inputs.py's:", same)
    return same


def origins(root):
    ok = True
    for folder in sorted(Path(root).glob("origin*")):
        manifest = json.loads((folder / "manifest.json").read_text())
        for job in json.loads((folder / "jobs-science.json").read_text()):
            path = folder / job["definition"]
            data = json.loads(path.read_text())
            world = make_inputs.WORLDS[job["world"]]
            if job["kind"] == "ionic":
                made = dict(
                    name=job["step"], definition=make_inputs.definition(job["world"], job["step"])
                )
            else:
                dt = world["legacy"] / {"h": 1, "h2": 2, "h4": 4}[job["step"]]
                made = make_inputs.legacy_assembly(world, dt, job["seed_index"])
            if data != json.loads(json.dumps(made)):
                ok = False
                print("  DEPARTS", path)
            if sha256(path) != manifest["files_sha256"][str(path.relative_to(folder))]:
                ok = False
                print("  SHA256", path)
        print(folder.name, "definitions are make_inputs.py's and have their sha256:", ok)
    return ok


def captures(root):
    ok = True
    for folder in sorted(Path(root).glob("science*")):
        manifest = json.loads((folder / "MANIFEST.json").read_text())
        jobs = manifest["jobs"]
        status = {j["status"] for j in jobs}
        files = 0
        for name, row in manifest["files"].items():
            if name in ("logs/capture.log", "logs/finish.log"):  # Written after the manifest.
                continue
            files += 1
            if sha256(folder / name) != row["sha256"]:
                ok = False
                print("  SHA256", folder / name)
        ok &= status == {"ok"}
        print(folder.name, len(jobs), "jobs", status, files, "files have their sha256:", ok)
    return ok


def plants():
    manifest = read("plants_manifest_rehearsal.json")
    ok = True
    for run in manifest["runs"]:
        folder = Path(run["output_folder"])
        for name, digest in run["outputs_sha256"].items():
            if sha256(folder / name) != digest:
                ok = False
                print("  SHA256", folder / name)
    print(len(manifest["runs"]), "planted runs have their sha256:", ok)
    return ok


def margins():
    data, ok = read("margins_rehearsal.json"), True
    for world, b in data["worlds"].items():
        homes = [v for v in b["entries"].values() if v["home"]]
        worst = min((v["margin"] for v in homes), default=0.0)
        any_margin = min(v["margin"] for v in b["entries"].values())
        poor = [
            (m, e)
            for m, entries in b["mechanisms"].items()
            for e, plants_of in entries.items()
            if not plants_of
        ]
        tests = {m: list(v) for m, v in b["mechanisms"].items()}
        ok &= worst >= 10 and not poor
        print(
            f"{world}: {len(tests)} mechanisms, smallest margin of a home {worst:.3g}, "
            f"of any entry {any_margin:.3g} {'' if worst >= 10 else 'BELOW 10'}"
        )
    return ok


def profile():
    value = read("profile_rehearsal.json")
    return make_profile.check(value) and value == json.loads(json.dumps(make_profile.profile()))


def main(root):
    results = dict(
        inputs=inputs(),
        origins=origins(root),
        captures=captures(root),
        plants=plants(),
        margins=margins(),
        profile=profile(),
    )
    print(results)
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
