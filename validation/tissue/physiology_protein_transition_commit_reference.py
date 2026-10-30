"""Independent real source replay and per-world component commit selection.

Stdlib RNG transforms, named owners and complete independent SI work replace
production samplers/array admission. This does not accept an ionic checkpoint
or infer physical drive. Exact source buffers survive an independent refusal.
"""

from copy import deepcopy

from validation.tissue import physiology_protein_packet_provider_reference as provider
from validation.tissue import physiology_protein_transition_arrays_reference as transition


def evaluate(binding, source, *, threefry_partitionable, transition_inputs):
    packet = provider.provide(binding, source, threefry_partitionable=threefry_partitionable)
    if provider.digest(transition_inputs["source"]) != provider.digest(packet["array_source"]):
        raise ValueError("Independent transition source differs from the real owned source")
    if provider.digest(transition_inputs["packet"]) != provider.digest(packet["array_packet"]):
        raise ValueError("Independent transition packet differs from real source replay")
    if provider.digest(binding) != provider.digest(transition_inputs["binding"]):
        raise ValueError("Independent complete host binding differs")
    admission = transition.evaluate(**transition_inputs)
    component = admission["component"]
    trial = component["trial"]
    nonnegative = all(value >= 0 for values in trial["protein"].values() for value in values)
    valid = bool(
        component["strict_requested_material"]
        and nonnegative
        and admission["declared_drive"]["valid"]
    )
    state = deepcopy(trial if valid else packet["array_source"])
    return dict(
        valid=valid,
        state=state,
        trial=trial,
        provider=packet,
        admission=admission,
        component_only=True,
        ionic_state_committed=False,
        work_ledger_committed=False,
        charged_loop_checkpoint=False,
    )
