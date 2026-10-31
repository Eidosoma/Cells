from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
from cells.processes import betse_normal_ion_join as ions
from tests.unit import test_betse_ecm_grn_join as chemistry
from tests.unit import test_betse_normal_ecm_catalog_join as catalog
from tests.unit import test_betse_normal_ecm_field_join as fields
from tests.unit import test_betse_normal_ecm_molecule_events_capture as capture
from tests.unit import test_betse_normal_ecm_molecule_transport as transported
from tests.unit.test_betse_normal_ecm_event_join import compare_events

owners = lifecycle.owners
archive, check = (capture.archive, capture.check)
exact = fields.exact
__all__ = ["compare_events", "check_handlers", "sample_contract"]


def check_handlers(tmp_path, name, point, binding, parent, detail, answers, native, observed):
    cache = parent.network.network_cache
    dispatch = detail["network"]
    assert native["status"] == "source_completed" and (not native["capture_errors"])
    exact(observed["commit"]["values_before"], native["returned"]["material"])
    exact(dispatch["shared_after"], native["returned"]["shared"])
    expected_roles = [role for role in owners.ROLES if cache["enabled"][role]]
    assert [
        r["role"] for r in dispatch["source_order"] if r["stage"] == "before_dispatch"
    ] == expected_roles
    for role in owners.ROLES:
        saved = cache["handlers"][role]
        if saved is None:
            assert native["returned"]["handlers"][role] is None
            continue
        exact(ions.data(saved["cache"]), native["returned"]["handlers"][role])
        feedback = dispatch["handlers"][role]
        for mode, comparator in (
            (
                "channels",
                lambda *forms, feedback=feedback: catalog.compare_channels(
                    binding, feedback, *forms
                ),
            ),
            (
                "network",
                lambda *forms, feedback=feedback: chemistry.compare_local(feedback, *forms),
            ),
        ):
            key = role + "-" + mode
            rows = comparator(*answers[key])
            if rows:
                check(tmp_path, name + "-" + key, point / key, rows)
            else:
                assert mode == "channels" and (not answers[key][1]["events"])
        key = role + "-transporters"
        if key in answers:
            rows, books = transported.transporter_rows(feedback, *answers[key])
            archive(tmp_path, name + "-transporter-books", books)
            if rows:
                check(tmp_path, name + "-transporters", point / key, rows)
            else:
                assert not answers[key][1]["frames"]
    assert cache["source_phase"] == binding.calendar.phase
    assert cache["legacy_run_sim"] is (binding.calendar.phase == "SIM")


def sample_contract(binding, parent, clock_forms):
    for form in clock_forms:
        exact(
            ions.data(parent.clock),
            dict(
                form["clock"],
                call_index=parent.cursor,
                material_dt_sum_s=parent.cursor * binding.calendar.dt_s,
            ),
        )
        expected = [j for j in form["sample_indices"] if j < parent.cursor]
        assert [row["call_index"] for row in parent.observations] == expected
    assert len(parent.history) == parent.cursor
    assert all(
        row["event_fire_calls"] == 1 and row["protein_noise_calls"] == 0 for row in parent.history
    )
    assert all(
        row["native_storage_called"] is row["display_completed"] is False
        for row in parent.observations
    )
