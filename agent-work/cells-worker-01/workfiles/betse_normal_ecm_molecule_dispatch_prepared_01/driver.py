"""Read-only plan and hard hold for the unrun general_molecule source handoff."""

import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--group")
    parser.add_argument("--requested-round", action="store_true")
    parser.add_argument("--coordinated-cpu", type=int)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    if not args.plan:
        raise RuntimeError(
            "General-molecule source handoff is held; this metadata-only driver cannot launch "
            "a scientific round. Chief owns a separately requested release controller."
        )
    inputs = json.loads((here / "inputs.json").read_text())
    for name, expected in inputs["source_sha256"].items():
        path = here / "source" / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Changed prepared source: " + name)
    print(
        json.dumps(
            dict(
                status="held_unrun",
                planned=inputs["planned"],
                groups=inputs["groups"],
                scientific_qualification_credit=False,
                automatic_launch=False,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
