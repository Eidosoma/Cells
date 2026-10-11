"""Explicit aggregate I/O allowance; unchanged codec, chunk limits and float bits."""

import importlib.util
from contextlib import contextmanager
from functools import lru_cache
from itertools import zip_longest
from types import SimpleNamespace

import relax_context as ctx

c = ctx.c
STREAM_BYTES = 128 * 1024**2


@contextmanager
def writer_limit(native):
    """Replace only the adapter's codec dependency, restoring it even on failure.

    The frozen run_row passes a 32 MiB aggregate cap. The qualified RecordSink
    already supports larger caps; this adapter selects 128 MiB, not larger chunks.
    Neither the shared codec module nor any BETSE function is monkey-patched.
    """
    original = native.codec

    def sink(directory, **kwargs):
        c.need(kwargs == {"max_output_bytes": 32 * 1024**2}, "Unexpected recorder arguments")
        return original.RecordSink(directory, max_output_bytes=STREAM_BYTES)

    native.codec = SimpleNamespace(RecordSink=sink)
    try:
        yield
    finally:
        native.codec = original


@lru_cache(maxsize=1)
def reader_type():
    # Load a private instance of the independently qualified reader. Its sole
    # override is the aggregate cap; the normal reader remains at 32 MiB.
    spec = importlib.util.spec_from_file_location("_refined_pump_wire", c.wire.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    c.need(
        module.STREAM_BYTES == 32 * 1024**2 and module.CHUNK_BYTES == 8 * 1024**2,
        "Reader bounds changed",
    )
    module.STREAM_BYTES = STREAM_BYTES
    return module.Stream


def stream(directory):
    return reader_type()(directory)


def pair(observed, quiet):
    streams = [stream(observed), stream(quiet)]

    def common(values):
        for value in values:
            if value["kind"] == "native_step":
                continue
            if value["kind"] in ("native_header", "native_footer"):
                value = {k: v for k, v in value.items() if k != "trace"}
                value["row"] = {k: v for k, v in value["row"].items() if k != "mode"}
            yield value

    exact, missing, count = c.exact.Exact(), object(), 0
    for left, right in zip_longest(common(streams[0]), common(streams[1]), fillvalue=missing):
        c.need(left is not missing and right is not missing, "Observer pair extent")
        exact.match(left, right, "Refined observer pair")
        count += 1
    c.need(count > 0 and all(s.complete for s in streams), "Incomplete observer pair")
    return dict(
        records=count,
        exact_scalars=exact.scalars,
        float64_bits=exact.floats,
        failed_comparisons=0,
        common_fields_only=True,
    )
