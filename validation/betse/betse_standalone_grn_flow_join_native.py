"""Independent pinned-native standalone source in its own private runtime."""

import warnings

from validation.betse import betse_standalone_grn_flow_join_engine as engine


def capture(inputs):
    runtime = engine.install("native")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with engine.observe_flow_execution(runtime):
            result = runtime.capture(inputs)
    for index, history in enumerate(result["history"]):
        failed = result.get("failure")
        if failed is None or failed.get("invocation") != index:
            history["trace"]["complete_source_return"] = runtime.clone(history["snapshot"])
            history["trace"]["nonfinite_source_return_arrays"] = engine.nonfinite_arrays(
                history["snapshot"]
            )
            if not caught:
                history["trace"]["warnings"] = []
    result["warnings"] = engine.warning_records(caught)
    result["flow_parent_source_sha256"] = engine.PARENTS["native"][1]
    result["parent_runtime_provenance"] = runtime.__source_provenance__
    result["ordinary_getFlow_executed"] = False
    result["held_flow_advects_molecular_ECM"] = True
    result["pressure_or_electric_fields_recomputed"] = False
    result["geometry_moved"] = False
    result["nonfinite_source_arrays"] = engine.nonfinite_arrays(result)
    result["numerical_candidate_accepted"] = False
    return result
