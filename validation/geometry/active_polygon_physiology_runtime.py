"""Complete runtime inventory; fresh worker guards are installed before imports."""

import json
import math
import os
import struct
import sys
from pathlib import Path

from validation.geometry import stable_geometry_primitives_runtime as inventory


def guard(mode):
    if mode == "initial-field":
        inventory.BLOCKED = {"cells", "betse", "jax", "jaxlib", "torch", "PIL"}
    elif mode in ("conversion", "corruption"):
        inventory.BLOCKED = inventory.SCIENTIFIC | {"cells"}
    else:
        raise ValueError(mode)
    inventory.deny_production()


def capture():
    return inventory.capture()


def write(path, value):
    """Retain typed returns before the unchanged strict JSON serialization.

    Conversion workers do not import NumPy. Field workers already have it
    loaded; their arrays are copied to an exclusive NPZ sidecar before any
    JSON conversion can reject nonfinite or otherwise unsupported values.
    """
    path = Path(path)
    raw_path = path.with_suffix(".raw.json")
    arrays_path = path.with_suffix(".npz")
    for candidate in (path, raw_path, arrays_path):
        if candidate.exists():
            raise FileExistsError(candidate)
    numpy = sys.modules.get("numpy")
    arrays = {}
    needs_raw = False

    def retain(item, trail="root"):
        nonlocal needs_raw
        if numpy is not None and isinstance(item, (numpy.ndarray, numpy.generic)):
            needs_raw = True
            array = numpy.asarray(item)
            if array.dtype.hasobject:
                raise TypeError("Object arrays are not typed numerical evidence")
            arrays[trail] = array
            return dict(array=trail, dtype=array.dtype.str, shape=list(array.shape))
        if hasattr(item, "_asdict"):
            return retain(item._asdict(), trail)
        if isinstance(item, dict):
            return {
                key: retain(child, trail + "/" + str(key).replace("~", "~0").replace("/", "~1"))
                for key, child in item.items()
            }
        if isinstance(item, (list, tuple)):
            return [retain(child, trail + "/" + str(index)) for index, child in enumerate(item)]
        if type(item) is float and not math.isfinite(item):
            needs_raw = True
            return dict(binary64_bits_hex=struct.pack(">d", item).hex(), nonfinite=item.hex())
        if item is None or isinstance(item, (str, int, float, bool)):
            return item
        needs_raw = True
        if isinstance(item, bytes):
            return dict(bytes_hex=item.hex())
        return dict(unsupported_type=type(item).__module__ + "." + type(item).__qualname__)

    raw = retain(value)
    if arrays:
        with arrays_path.open("xb") as handle:
            numpy.savez_compressed(handle, **arrays)
            handle.flush()
            os.fsync(handle.fileno())
    if needs_raw:
        with raw_path.open("x") as handle:
            json.dump(
                dict(
                    kind="cells.active_polygon_raw_return@1",
                    typed_arrays=arrays_path.name if arrays else None,
                    value=raw,
                ),
                handle,
                indent=2,
                allow_nan=False,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

    def plain(item):
        if numpy is not None and isinstance(item, (numpy.ndarray, numpy.generic)):
            return item.tolist()
        raise TypeError(f"Object of type {type(item).__name__} is not JSON serializable")

    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False, default=plain)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def pytest_sessionfinish(session, exitstatus):
    write(
        Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "runtime.json",
        capture() | dict(exitstatus=int(exitstatus)),
    )
