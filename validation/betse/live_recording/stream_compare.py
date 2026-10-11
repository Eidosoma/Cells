"""Incremental exact comparison using the independently qualified wire reader."""

import sys
from itertools import zip_longest

import live_context as ctx

sys.path.insert(0, str(ctx.HERE.parent / "native_recording_audit"))
from codec_review import Exact  # noqa: E402
from wire_decode import Stream  # noqa: E402


def compare(left, right, *, common=False):
    """common compares all shared fields, excluding only mode and physical trace."""
    streams = [Stream(left), Stream(right)]

    def selected(stream):
        for record in stream:
            if common:
                if record["kind"] == "native_step":
                    continue
                if record["kind"] in ("native_header", "native_footer"):
                    record = {k: v for k, v in record.items() if k != "trace"}
                    record["row"] = {k: v for k, v in record["row"].items() if k != "mode"}
            yield record

    exact, missing, count = Exact(), object(), 0
    for a, b in zip_longest(selected(streams[0]), selected(streams[1]), fillvalue=missing):
        ctx.need(a is not missing and b is not missing, "Stream comparison extent")
        exact.match(a, b, f"record/{count}")
        count += 1
    ctx.need(all(s.complete for s in streams) and count > 0, "Stream comparison incomplete")
    return dict(
        records=count,
        exact_scalars=exact.scalars,
        float64_bits=exact.floats,
        negative_zero_values=exact.negative_zeros,
        common_fields_only=common,
        failed_comparisons=0,
    )
