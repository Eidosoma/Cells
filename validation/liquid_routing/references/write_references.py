"""Write the references of `liquid-routing-v1`.

    python -B -P write_references.py --out DIR --revision REV [--inputs SPEC/inputs.json] [--only invented|registered]

The invented files are written first. `sys.path` is not changed: the package beside this file is loaded by its location,
so that nothing of the repository is importable.
"""

import argparse
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load_package(name="lrrefs"):
    folder = os.path.join(HERE, name)
    spec = importlib.util.spec_from_file_location(name, os.path.join(folder, "__init__.py"),
                                                  submodule_search_locations=[folder])
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return package


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--revision", required=True, help="the git revision of the spec that was read")
    parser.add_argument("--inputs", default=os.path.join(HERE, os.pardir, "spec", "inputs.json"))
    parser.add_argument("--only", choices=("invented", "registered"))
    parser.add_argument("--arms", help="registered arms to write, as 1,3,5 (default: all)")
    arguments = parser.parse_args()
    os.makedirs(arguments.out, exist_ok=True)
    load_package()
    from lrrefs import writer

    if arguments.only in (None, "invented"):
        writer.write_invented(arguments.out, arguments.revision)
    if arguments.only in (None, "registered"):
        which = [int(a) for a in arguments.arms.split(",")] if arguments.arms else None
        writer.write_registered(arguments.out, arguments.inputs, arguments.revision, which)


if __name__ == "__main__":
    main()
