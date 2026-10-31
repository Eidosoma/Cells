"""Independent stdlib typed-input/hurt/removal oracle; no native or array imports."""

import argparse
import json
import struct
from dataclasses import dataclass
from pathlib import Path

from validation.topology import betse_tissue_cut_reference as owners


@dataclass
class Array:
    shape: tuple
    values: list

    def __len__(self):
        if not self.shape:
            raise TypeError("len() of unsized object")
        return self.shape[0]

    def rows(self):
        if len(self.shape) == 1:
            return self.values
        width = 1
        for count in self.shape[1:]:
            width *= count
        return [
            Array(self.shape[1:], self.values[i * width : (i + 1) * width])
            for i in range(self.shape[0])
        ]


def restore(packet):
    raw = json.loads(packet)
    cache = {}

    def scalar(dtype, data):
        endian = dtype[0] if dtype[0] in "<>" else "="
        code = {"f8": "d", "f4": "f", "i8": "q", "i4": "i", "u8": "Q", "u4": "I", "b1": "?"}[
            dtype[1:]
        ]
        return list(
            struct.unpack(
                endian + code * (len(bytes.fromhex(data)) // struct.calcsize(code)),
                bytes.fromhex(data),
            )
        )

    def decode(value):
        if not isinstance(value, dict):
            return value
        if "float64" in value:
            return float.fromhex(value["float64"])
        if "numpy_scalar" in value:
            return scalar(value["numpy_scalar"], value["data"])[0]
        at = value["ref"]
        if at in cache:
            return cache[at]
        row = raw["nodes"][at]
        if row["kind"] == "ndarray":
            result = Array(tuple(row["shape"]), [])
            cache[at] = result
            result.values = (
                [decode(v) for v in row["items"]]
                if "items" in row
                else scalar(row["dtype"], row["data"])
            )
        elif row["kind"] in ("dict", "namespace", "dataclass"):
            result = {}
            cache[at] = result
            result.update((key, decode(item)) for key, item in row["items"])
        else:
            result = []
            cache[at] = result
            result.extend(decode(item) for item in row["items"])
            if row["kind"] == "tuple":
                result = tuple(result)
            elif row["kind"] == "set":
                result = set(result)
        cache[at] = result
        return result

    return decode(raw["root"])


def evaluate(inputs):
    source = restore(inputs["source_graph"])
    cells = source["cell_fields"]
    selected = source["selection"]["cells"].values
    edges = cells["cell_to_nn_full"].rows()
    removed_edges = {edge for index in selected for edge in edges[index]}
    hurt = [float(any(edge in removed_edges for edge in row)) for row in edges]
    kept = [i for i in range(len(cells["cell_i"])) if i not in selected]
    plan = owners.remove(inputs["topology"], inputs["removed_cell_ids"])
    fields = {
        name: owners.field_cut(field, plan) for name, field in inputs["field_declarations"].items()
    }
    return dict(
        kind="cells.native_cut_prefix_independent_reference@1",
        source_hurt_mask_after_delete=[hurt[i] for i in kept],
        stable_plan=plan,
        fields=fields,
        decimal_precision=80,
        carried_reference_forms=0,
        native_geometry_inferred=False,
        physical_mesh_qualified=False,
        complete_native_cut=False,
        independent_trajectory=False,
    )


def main():
    import builtins
    import importlib.abc
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    denied = {"cells", "betse", "numpy", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *rest, **kwargs):
        if name.split(".")[0] in denied:
            raise ImportError("Independent cut oracle import denied: " + name)
        return original(name, *rest, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in denied:
                raise ImportError("Independent cut oracle import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    result = evaluate(json.loads(args.inputs.read_text()))
    loaded = [name for name in sys.modules if name.split(".")[0] in denied]
    assert not loaded
    result.update(production_imports_denied=True, loaded_production_modules=loaded)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
