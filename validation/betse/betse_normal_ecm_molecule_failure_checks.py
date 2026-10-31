"""Capture before classification; source-specific checks for held molecule tests."""

from validation.betse import betse_normal_ecm_init_phase_capture as failure_evidence


def exception_chain(error):
    """Retain wrapper-owned state as well as the literal source cause."""
    records, seen = [], set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        records.append(
            dict(
                type=type(error).__name__,
                message=str(error),
                attributes={
                    key: getattr(error, key)
                    for key in ("partial", "stage", "parent", "drive", "trial")
                    if hasattr(error, key)
                },
            )
        )
        error = error.__cause__
    return records


def retained_call(operation, *, stage, readers, retain):
    """Keep unexpected returns and exceptions before pytest classifies either."""
    try:
        result = operation()
    except Exception as error:
        failure_evidence.record_failure(
            error,
            stage=stage,
            readers={
                **readers,
                "partial": lambda original_error=error: getattr(original_error, "partial", None),
                "exception_chain": lambda original_error=error: exception_chain(original_error),
            },
            retain=retain,
        )
        raise
    retain(
        dict(
            status="source_returned",
            stage=stage,
            returned=result,
            available={key: reader() for key, reader in readers.items()},
        )
    )
    return result


def assert_molecule_refusal(case, error, native, partial, parent, *, exact, transport, ion_ids):
    """Require the declared cell-negativity failure and its complete saved prefix.

    The fixtures only predict the sign failure. The actual sign, buffers and
    completed prefix must come from the new run, not from that prediction.
    """
    assert case in (
        "first_general_negative",
        "second_general_negative",
        "first_GRN_negative",
        "second_GRN_negative",
    )
    role = "molecules" if "general" in case else "grn"
    species = "X" if case.startswith("first_") else "Y"
    message = (
        "Network concentration of "
        + species
        + " in cells below zero! Your simulation has become unstable."
    )
    chain = exception_chain(error)
    assert [row["type"] for row in chain] == [
        "DispatchRejected",
        "ECMTransportRejected",
        "BetseSimUnstableException",
    ]
    wrapped = "Native ECM material refused at source: " + message
    assert [row["message"] for row in chain] == [wrapped, wrapped, message]
    assert error.__cause__.stage == "source" and error.__cause__.trial is None
    assert native["status"] == "source_refused"
    assert native["failure"]["type"] == "BetseSimUnstableException"
    assert native["failure"]["message"] == message
    assert native["failure"]["stage"] == "native_dispatch"
    assert native["failure_capture"] and not native["capture_errors"]
    assert partial["stage"] == "general_then_GRN"
    assert partial["root_cause"] == dict(type="ECMTransportRejected", message=wrapped)
    assert partial["automatic_retry"] is False
    assert partial["inner_partial"] is None
    exact(partial["parent"], parent)
    assert parent["clock"]["call_index"] == 0
    holder = partial["holder"]
    assert "before_commit" not in holder and "trial" not in holder
    frames = holder["material_partial"]["frames"]
    # DispatchRejected freezes Frame namedtuples as positional tuples. Their
    # archived schema remains (stage, ion_id, values), not a mapping.
    assert frames and all(isinstance(row, (tuple, list)) and len(row) == 3 for row in frames)
    assert frames[-1][0] == "supplied_late_flux"
    assert all(row[0] != "ecm_grn_dispatch" for row in frames)
    available = partial["available"]
    assert not available["capture_errors"]
    expected_order = []
    reached = ("molecules",) if role == "molecules" else ("molecules", "grn")
    for owner in reached:
        stages = ["before_dispatch", "clear_run_loop"]
        if transport and owner == "molecules":
            stages.append("run_loop_transporters")
        stages.append("run_loop_modulators")
        if owner != role:
            stages.append("run_loop")
        expected_order.extend(dict(role=owner, stage=stage) for stage in stages)
    assert native["order"] == available["source_order"] == expected_order
    exact(available["material"], native["returned"]["material"])
    owners = available["owners"]
    exact(owners["shared"], native["returned"]["shared"])
    expected_publisher = (
        parent["owners"]["publication_owner"] if role == "molecules" else "molecules"
    )
    assert owners["publication_owner"] == expected_publisher
    for owner in ("molecules", "grn"):
        saved = owners["handlers"][owner]
        if saved is None:
            assert native["returned"]["handlers"][owner] is None
        else:
            exact(saved["cache"], native["returned"]["handlers"][owner])
    for owner in reached:
        actual, wanted = available["traces"][owner], native["traces"][owner]
        # Completion annotations are owned-only; compare the actual raw events.
        for key in (
            "molecule_frames",
            "mover_frames",
            "rhs",
            "control_writes",
            "dispatch_stages",
            "channel_events",
            "channel_initializations",
        ):
            exact(actual[key], wanted[key])
        if transport and owner == "molecules":
            exact(actual["transporter_frames"], wanted["transporter_frames"])
            assert [(row["stage"], row["name"]) for row in actual["transporter_frames"]] == [
                (stage, "general_Na_import")
                for stage in (
                    "before",
                    "flux",
                    "current",
                    "reactant_commit",
                    "product_commit",
                    "after",
                )
            ]
        completed = [
            row["species"] for row in actual["molecule_frames"] if row["stage"] == "transport_after"
        ]
        expected = ["X", "Y"] if owner != role else ([] if species == "X" else ["X"])
        assert completed == expected
    failed = available["traces"][role]
    chemical = [(row["stage"], row["species"]) for row in failed["molecule_frames"]]
    expected_chemical = [("molecule_intra", "X"), ("molecule_intra", "Y"), ("rhs_ready", None)]
    expected_chemical.extend(("chemical_commit", ion) for ion in ion_ids)
    if species == "Y":
        expected_chemical.extend(
            (stage, "X") for stage in ("chemical_commit", "transport_before", "transport_after")
        )
    expected_chemical.extend((stage, species) for stage in ("chemical_commit", "transport_before"))
    assert chemical == expected_chemical
    target = [row for row in failed["mover_frames"] if row["species"] == species]
    assert target and target[-1]["stage"] == "environment_mix"
    assert all(row["stage"] != "return" for row in target)
    assert any(value < 0 for value in target[-1]["fields"]["cX_cells"])
