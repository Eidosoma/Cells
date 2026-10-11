"""Inline protocol-5 NumPy buffers; ordinary BETSE loading needs no adapter.

Native arrays, histories, object aliases and the BETSE cache-removal policy are
retained. Only serialization is changed, in a process-local restored context.
No buffer sidecars, persistent IDs, discarded histories or custom loader.
"""

import contextlib
import pickle
import struct

MODE = "numpy_inline_buffers@1"


@contextlib.contextmanager
def inline_arrays():
    import dill
    import numpy as np
    from betse.lib.pickle import pickles

    prior_class, prior_protocol = dill._dill.Pickler, pickles.PROTOCOL
    if prior_protocol != 4 or not issubclass(prior_class, pickles.BetsePickler):
        raise ValueError("Require the initialized pinned BETSE protocol-4 writer")
    facts = dict(
        mode=MODE,
        array_reductions=0,
        inline_buffers=0,
        inline_bytes=0,
        largest_buffer_bytes=0,
        external_buffers=0,
        globals_restored=False,
    )

    def save_array(writer, value):
        # Exact ndarray only. Subclasses keep their existing dill dispatch.
        facts["array_reductions"] += 1
        writer.save_reduce(*value.__reduce_ex__(5), obj=value)

    def save_buffer(writer, value):
        if writer.proto != 5 or writer._buffer_callback is not None:
            raise ValueError("Require self-contained inline protocol-5 buffers")
        with value.raw() as view:
            if not view.contiguous:
                raise ValueError("Noncontiguous pickle buffer")
            size = view.nbytes
            header = (pickle.BINBYTES8 if view.readonly else pickle.BYTEARRAY8) + struct.pack(
                "<Q", size
            )
            if size >= writer.framer._FRAME_SIZE_TARGET:
                writer.framer.write_large_bytes(header, view)
            else:
                writer.write(header)
                writer.write(view)
            # The buffer is a temporary ndarray reduction object. Array identity
            # is memoized by save_reduce; no temporary bytes copy is memoized.
            facts["inline_buffers"] += 1
            facts["inline_bytes"] += size
            facts["largest_buffer_bytes"] = max(facts["largest_buffer_bytes"], size)

    class InlinePickler(prior_class):
        dispatch = prior_class.dispatch.copy()

    InlinePickler.dispatch[np.ndarray] = save_array
    InlinePickler.dispatch[pickle.PickleBuffer] = save_buffer
    dill._dill.Pickler, pickles.PROTOCOL = InlinePickler, 5
    try:
        yield facts
    finally:
        dill._dill.Pickler, pickles.PROTOCOL = prior_class, prior_protocol
        facts["globals_restored"] = True
