"""Ion fields with the secreted-species operators active (D150 version 1; design §7, §11.1).

Probe 2 found every ion row bitwise unchanged by a declared species with no operator. Here both
operators are active on the mixed heredity chain (validation/tissue/secreted_species_fixtures:
cell_0 produces and secretes, ecs_2 clears, cell_3 and cell_5 take the species up), and every ion
row of every species-axis field, and every field the species does not enter, is compared bitwise
with the same world without the species, on four paths: scalar runs, restart (in process and
through a written snapshot), a vector-window batch with device checks, and one replacement event.
The species enters only its own rows, the operators' own fields, the face heat and the baths'
supply work (its diffusion heat and bath supply), so those are the expected differences.

This is idle claim 3 of §7, reported, not promised: XLA's reduce order over the species axis is
program-specific. The species starts from a pre-formed profile (production worlds start resolved,
§2.6). A few minutes of compiles: tier 3.
"""

import json
import os
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core.runner import run
from cells.core.specs import parse_spec
from validation.tissue import cell_replacement_fixtures as rfx
from validation.tissue import secreted_species_fixtures as fx

jax.config.update("jax_enable_x64", True)

IONS = ("Na", "K", "M", "P")
EXPECTED = ("face_dissipated_energy_pJ", "reservoir_work_pJ")  # The species' heat and supply work.
END = 0.1


def record(test, **values):
    """Append measured values to this run's output folder (the tier runner's CELLS_OUTPUT_ROOT)."""
    root = os.environ.get("CELLS_OUTPUT_ROOT")
    if root:
        path = Path(root) / "secreted_species_ions.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as out:
            out.write(json.dumps(dict(test=test, **values), default=float) + "\n")


def differing(ions, secreted, species):
    """The fields of the ion world whose values differ in the species world (ion rows compared)."""
    rows = [species.index(k) for k in IONS]
    out = []
    for name in type(ions)._fields:
        a, b = np.asarray(getattr(ions, name)), np.asarray(getattr(secreted, name))
        if b.ndim >= 2 and b.shape[1] == len(species) and a.shape[1] == len(IONS):
            b = b[:, rows]
        if a.shape != b.shape or a.tobytes() != b.tobytes():
            out.append(name)
    return out


def _columns(observations):
    """Observations as a NamedTuple-like record (differing's input)."""
    from collections import namedtuple

    fields = vars(observations)
    return namedtuple("Columns", list(fields))(*fields.values())


def worlds(**operators):
    ions = parse_spec(fx.heredity_chain(secreted=False, end=END))
    secreted = parse_spec(
        fx.chain_operators(fx.heredity_chain(secreted=True, end=END), **operators)
    )
    return ions, secreted


def test_scalar_runs_and_restarts_leave_every_ion_field_bitwise(tmp_path):
    from cells.io import load_snapshot, write_snapshot

    ions, secreted = worlds()
    a, b = run(ions), run(secreted)  # Host checks on every accepted row of both.
    species = list(secreted.model.species_ids)
    fields = differing(a.history, b.history, species)
    columns = differing(_columns(a.observations), _columns(b.observations), species)
    record("scalar", differing_fields=fields, differing_columns=columns)
    assert fields == list(EXPECTED)
    s = species.index(fx.SPECIES)
    moved = np.asarray(b.history.exchange_moved_fmol)[-1]
    assert moved[0] > 0 > moved[1] and moved[2] < 0  # Secretion out, both uptakes in.
    assert np.asarray(b.history.turnover_outside_cleared_fmol)[-1][s].sum() > 0
    # Observation columns: the species also enters the baths' power and the energy-balance rate.
    assert set(columns) <= {*EXPECTED, "reservoir_power_pJ_s", "energy_balance_pJ_s"}, columns
    checkpoint = b.checkpoint_at(0.05)
    resumed = run(secreted, checkpoint)
    for x, y in zip(resumed.history, b.history, strict=True):
        assert np.array_equal(np.asarray(x), np.asarray(y)[checkpoint.step_index :])
    write_snapshot(tmp_path / "checkpoint", b.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    again = run(loaded.spec, loaded.checkpoint)
    for x, y in zip(again.history, b.history, strict=True):
        assert np.array_equal(np.asarray(x), np.asarray(y)[checkpoint.step_index :])


def test_a_vector_batch_leaves_every_ion_row_bitwise():
    from cells.core.batch import BatchSpec, WorldSpec
    from cells.core.vector_windows import run_vector_windowed
    from cells.core.windows import WindowPolicy

    rates = (dict(secrete=0.1), dict(secrete=0.3, uptake=2e6), dict(secrete=0.05, ku=3e-6))
    secreted = [worlds(**r)[1] for r in rates]
    ions = [worlds()[0] for _ in rates]

    def batch(specs):
        cohort = tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs))
        return run_vector_windowed(
            BatchSpec(cohort, len(cohort), 10**6, 2**31), WindowPolicy(4, "checkpoints")
        )

    with_s, without, backward = batch(secreted), batch(ions), batch(secreted[::-1])
    species = list(secreted[0].model.species_ids)
    rows = [species.index(k) for k in IONS]
    for k in range(len(rates)):
        final = with_s.worlds[k + 1].final.state
        other = backward.worlds[len(rates) - k].final.state
        assert all(np.array_equal(x, y) for x, y in zip(final, other, strict=True))
        plain = without.worlds[k + 1].final.state
        for name in type(plain)._fields:
            a, b = np.asarray(getattr(plain, name)), np.asarray(getattr(final, name))
            if b.ndim >= 1 and b.shape[0] == len(species) and a.shape[0] == len(IONS):
                b = b[rows]
            if name not in EXPECTED:
                assert a.tobytes() == b.tobytes(), (k, name)
    record("vector_batch", worlds=len(rates), reversed_bitwise=True, ion_rows_bitwise=True)


def replaced(secreted):
    raw = fx.heredity_chain(secreted=secreted, end=END)
    template = rfx.template_from_cell(raw, "cell_2", "T")
    if secreted:
        template["amounts_fmol"][fx.SPECIES] = 1e-4  # A granule-loaded newcomer.
    raw = fx.with_replacement(raw, [template], [(0.05, "cell_2", "T", "c2_new")])
    return parse_spec(fx.chain_operators(raw) if secreted else raw)


def test_a_replacement_event_swaps_the_pool_and_leaves_every_ion_field_bitwise():
    spec = replaced(True)
    ions, secreted = run(replaced(False)), run(spec)
    species = list(spec.model.species_ids)
    expected = [*EXPECTED, "replacement_free_energy_pJ", "replacement_energy_magnitude_pJ"]
    fields = differing(ions.history, secreted.history, species)
    record("replacement", differing_fields=fields)
    assert fields == expected
    s, slot = species.index(fx.SPECIES), 2
    supplied = np.asarray(secreted.history.replacement_supplied_fmol)[-1][s, slot]
    removed = np.asarray(secreted.history.replacement_removed_fmol)[-1][s, slot]
    assert supplied == 1e-4
    assert removed == pytest.approx(fx.TRACE_mM * secreted.spec.model.cells[slot].volume_pL)
