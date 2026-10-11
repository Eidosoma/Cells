"""Independent read-only assembly of one saved row; not a bounded-memory claim."""

from itertools import zip_longest

import review_context as ctx

c, exact = ctx.c, ctx.c.exact


def assemble(records, *, retain_steps=True):
    iterator = iter(records)
    header = next(iterator)
    c.wire.fields(header, {"kind", "schema", "row", "trace", "histories"}, "Native header")
    c.need(
        header["kind"] == "native_header" and header["schema"] == "cells.native_pump_row@1",
        "Native schema",
    )
    row = dict(header["row"])
    row["histories"] = {k: dict(v, values=[]) for k, v in header["histories"].items()}
    observed = row["mode"] == "observed"
    row["trace"] = (
        dict(header["trace"], **{k: [] for k in exact.TRACE_SERIES}) if observed else None
    )
    n = row["steps"]

    def take(kind, index):
        value = next(iterator)
        c.need(value["kind"] == kind and value["index"] == index, "Native record order")
        return value

    for i in range(n if observed else n - 1):
        if observed:
            value = take("native_step", i)
            c.need((value["storage"] is None) == (i == 0), "Native storage extent")
            for target, key in (
                ("steps", "step"),
                ("raw_steps", "raw_step"),
                ("labels_s", "label_s"),
            ):
                if retain_steps or target == "labels_s":
                    row["trace"][target].append(value[key])
            if i:
                row["trace"]["storage"].append(value["storage"])
                row["trace"]["sampled_indices"].append(value["storage"]["index"])
            else:
                continue
        value = take("native_history", i - 1 if observed else i)
        c.need(set(value["values"]) == set(row["histories"]), "History field coverage")
        for name, values in value["values"].items():
            row["histories"][name]["values"].append(values)
    footer = next(iterator)
    c.wire.fields(footer, {"kind", "row", "trace", "histories_sha256"}, "Native footer")
    c.need(footer["kind"] == "native_footer", "Native footer order")
    c.need(not (set(footer["row"]) & set(row)), "Repeated row field")
    row.update(footer["row"])
    if observed:
        row["trace"].update(footer["trace"])
    else:
        c.need(footer["trace"] is None and header["trace"] is None, "Quiet trace")
    c.need(set(footer["histories_sha256"]) == set(row["histories"]), "History digest coverage")
    for name, digest in footer["histories_sha256"].items():
        row["histories"][name]["bytes_sha256"] = digest
    missing = object()
    c.need(next(iterator, missing) is missing, "Trailing native records")
    return row


def read(directory):
    stream = ctx.reader()(directory)
    row = assemble(stream)
    c.need(stream.complete, "Incomplete native stream")
    # Separately qualified semantic reader checks every field, sequence, history
    # checksum and endpoint array against the assembled view. This is a format
    # check, not independent evidence of the physics or original JSON equivalence.
    verification = ctx.reader()(directory)
    facts = exact.compare_row(row, verification)
    c.need(verification.complete, "Incomplete format check")
    return row, facts


def pair(observed, quiet, *, progress=None):
    streams = [ctx.reader()(p) for p in (observed, quiet)]

    def common(stream):
        for value in stream:
            if value["kind"] == "native_step":
                continue
            if value["kind"] in ("native_header", "native_footer"):
                value = {k: v for k, v in value.items() if k != "trace"}
                value["row"] = {k: v for k, v in value["row"].items() if k != "mode"}
            yield value

    match, missing, count = exact.Exact(), object(), 0
    for a, b in zip_longest(*(common(s) for s in streams), fillvalue=missing):
        c.need(a is not missing and b is not missing, "Observer pair extent")
        match.match(a, b, "Observer neutrality")
        count += 1
        if progress is not None and count % 1000 == 0:
            progress("observer_records", completed=count, total=streams[1].manifest["records"])
    c.need(count > 0 and all(s.complete for s in streams), "Incomplete observer comparison")
    return dict(
        records=count,
        exact_scalars=match.scalars,
        float64_bits=match.floats,
        failed_comparisons=0,
        common_fields_only=True,
    )
