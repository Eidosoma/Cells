"""Re-iterable trace views over authenticated records, retaining one decoded chunk.

The ordinary independent reader retains histories and metadata. Only the two
large step/raw-call lists are replaced. Every comparison still sees the same
ordinary Python dict/list/float values. No native data, clocks or equations change.
"""

from collections.abc import Sequence


def prefix_window(row, count):
    """Retain exactly the fields used by the existing physical-prefix comparison.

    Once the full identity, physics and energy checks finish, their large
    histories can be released before loading the independently checked prefix.
    Source files and already completed checks are untouched. Step/raw-call
    views remain lazy and the retained history values are the original objects.
    """
    if type(count) is not int or not 2 <= count <= row["steps"]:
        raise ValueError("Physical prefix working-set extent")
    return dict(
        dt_s=row["dt_s"],
        trace={name: row["trace"][name] for name in ("initial", "steps", "raw_steps")},
        histories={
            name: {"values": item["values"][: count - 1]} for name, item in row["histories"].items()
        },
    )


class StepStore:
    def __init__(self, directory, stream_type, count, *, progress=None):
        self.directory, self.stream_type, self.count = directory, stream_type, count
        self.iterator, self.record, self.index = None, None, -1
        self.progress, self.passes = progress, 0

    def close(self):
        if self.iterator is not None:
            self.iterator.close()
        self.iterator, self.record, self.index = None, None, -1

    def get(self, index):
        if not 0 <= index < self.count:
            raise IndexError(index)
        if index == self.index:
            return self.record
        if self.iterator is None or index < self.index:
            self.close()
            self.iterator = iter(self.stream_type(self.directory))
            self.passes += 1
            if self.progress is not None:
                self.progress("trace_pass_started", pass_number=self.passes, requested_index=index)
        for record in self.iterator:
            if record["kind"] != "native_step":
                continue
            if record["index"] != self.index + 1:
                raise ValueError("Streamed review lost step chronology")
            self.index, self.record = record["index"], record
            if self.progress is not None and (
                (self.index + 1) % 1000 == 0 or self.index + 1 == self.count
            ):
                self.progress(
                    "trace_steps",
                    pass_number=self.passes,
                    completed=self.index + 1,
                    total=self.count,
                )
            if self.index == index:
                return record
        raise ValueError("Streamed review ended before the requested step")

    def __del__(self):
        self.close()


class TraceValues(Sequence):
    def __init__(self, store, field):
        self.store, self.field = store, field

    def __len__(self):
        return self.store.count

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        if index < 0:
            index += len(self)
        return self.store.get(index)[self.field]

    def __iter__(self):
        for index in range(len(self)):
            yield self[index]


def read(directory, decoder, stream_type, *, progress=None):
    def records(stream, name):
        if progress is not None:
            progress(name + "_started", total=stream.manifest["records"])
        for index, value in enumerate(stream, 1):
            yield value
            if progress is not None and index % 2048 == 0:
                progress(name, completed=index, total=stream.manifest["records"])
        if progress is not None:
            progress(name + "_completed", completed=index, total=stream.manifest["records"])

    stream = stream_type(directory)
    row = decoder.assemble(records(stream, "assembly_records"), retain_steps=False)
    if not stream.complete:
        raise ValueError("Incomplete streamed native assembly")
    store = None
    if row["mode"] == "observed":
        store = StepStore(directory, stream_type, row["steps"], progress=progress)
        row["trace"]["steps"] = TraceValues(store, "step")
        row["trace"]["raw_steps"] = TraceValues(store, "raw_step")
    verification = stream_type(directory)
    try:
        facts = decoder.exact.compare_row(
            row, records(verification, "format_records"), trace_sequence_types=(list, TraceValues)
        )
        if not verification.complete:
            raise ValueError("Incomplete streamed native format verification")
    finally:
        if store is not None:
            store.close()
    return row, facts | {
        "step_storage": "reiterable_authenticated_stream",
        "histories_retained": True,
    }
