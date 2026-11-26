"""P1's positivity predictor (docs/CORE_SEAMS_DESIGN.md §17; §19 as amended: the general layout
only), @3's part. The selector is the binding owner's ruling (a) of 19 November 2026: each stage
row may name its read's law as a third item. Where every row of a read names a registered law that
declares free_amounts (cells.binding.rapid_binding@1), the structure lists the read's kind
(InnerStructure.free_amount_reads), and the IMEX step's predictor reads the stage read at the
predicted stored totals. Everywhere else it keeps today's form: the start read's amount plus the
stored derivative.

- Stage rows are shared by their (species, node), whatever law a third item names. Two kinds'
  reads on one row under different laws are refused at binding, where a key on the whole row
  would admit them (the plant). A row of any other length is refused.
- The switch: today's definitions list no read, and rows naming cells.binding.rapid_binding@1 list the buffer.
  Rows naming version 1's read (cells.kind.rapid_proton_buffer@1, not a registered law) or a registered law
  without free_amounts list none. A composite's model block reaches the same switch.
- The structure's check (F's review): it refuses an undeclared entry, a repeated entry, an
  unsorted pair of declared kinds, a list in place of a tuple, and a non-string entry.
- The step, on the binding owner's lumen world under the general closure, with a planted drawer
  (its reading carrier run inward, taking H from the lumen into the cell across bounding_0). At
  the dt where the predicted draw is ten times the lumen's free H, today's form refuses the step,
  since the free amount less the draw is negative, and P1's form admits it (the plant: each
  control of today's form refuses it). At half the free H both admit. Past the stored total both
  refuse, and the read at the predicted totals is invalid there.
- Refused at binding: a read whose rows mix the two forms, and a free-amount read beside a read
  of today's form.
"""

from contextlib import contextmanager
from dataclasses import replace

import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.kinds import proton_buffer
from cells.models import pump_composite_adapter, surface_pump_v3
from cells.registry import kind_registry, laws
from tests import kind_fixtures
from tests.unit.test_kind_rules import declaring, reader, registry
from tests.unit.test_proton_buffer_kind import host
from tests.unit.test_rapid_binding_world import (
    READS_LAW,
    amounts,
    lumen_general,
    reading_carrier,
    reads_law,
)
from validation.compartment_ph_engine import definitions as fr

GENERAL = proton_buffer.GENERAL_READ_ID  # Registered, with free_amounts.
VERSION_1 = "cells.kind.rapid_proton_buffer@1"  # Version 1's read ID: not a registered law.


def test_stage_rows_are_shared_by_species_and_node_whatever_law_each_names():
    shared = registry(
        reader("alpha", "alpha_block", (("K", "cell_0", "tests.binding.law_a@1"),)),
        reader("beta", "beta_block", (("K", "cell_0", "tests.binding.law_b@1"),)),
    )
    with kind_registry.scope(shared):
        with pytest.raises(
            ConfigError, match=r"tests.kind.alpha@1 and tests.kind.beta@1 both read row \('K', 'cell_0'\)"
        ):
            parse_spec(declaring("alpha_block", "beta_block"))
    apart = registry(
        reader("alpha", "alpha_block", (("K", "cell_0", "tests.binding.law_a@1"),)),
        reader("beta", "beta_block", (("Na", "cell_0", "tests.binding.law_a@1"),)),
    )
    with kind_registry.scope(apart):
        parse_spec(declaring("alpha_block", "beta_block"))  # Disjoint rows: admitted.


def test_a_stage_row_is_two_or_three_items():
    with kind_registry.scope(registry(reader("alpha", "alpha_block", (("K",),)))):
        with pytest.raises(ConfigError, match=r"stage row \('K',\) is not \(species, node ID\)"):
            parse_spec(declaring("alpha_block"))


def drawer():
    """The binding tests' reading carrier run inward: it takes its species from its patch's
    outside node into the patch's cell at its declared rate (its moves name READS_LAW, whose reads
    name cells.binding.rapid_binding@1, so the general closure admits them)."""
    base = reading_carrier()

    def parse(entries, spec):
        species, patch, inside, outside, rate = base.parse(entries, spec)
        return (species, patch, inside, outside, -rate)

    def to_dict(declaration):
        out = base.to_dict(declaration)
        return {**out, "rate_fmol_s": abs(out["rate_fmol_s"])}

    def domain(state, p, *, xp):
        return xp.all(xp.isfinite(state.carrier_transferred))

    return replace(base, parse=parse, to_dict=to_dict, domain=domain)


def buffer(third=None):
    """The closure's kind with `third` as each stage row's third item (None: today's two)."""
    rows = proton_buffer.stage_rows
    if third is None:  # Today's two items, pinned (the binding owner's rows name their law).
        return replace(
            proton_buffer.PROTON_BUFFER,
            stage_rows=lambda declaration: tuple(row[:2] for row in rows(declaration)),
        )
    return replace(
        proton_buffer.PROTON_BUFFER,
        stage_rows=lambda declaration: tuple((*row[:2], third) for row in rows(declaration)),
    )


@contextmanager
def scoped(third=None):
    kinds = kind_fixtures.registry(drawer(), buffer(third))
    with kind_registry.scope(kinds), laws.scope(laws.active().extended(reads_law())):
        yield


def drawn_world():
    """The lumen world with the drawer taking H from the lumen at 1 fmol/s."""
    raw = lumen_general()
    return kind_fixtures.declare_carrier(raw, species="H", rate=1.0, membrane="bounding_0")


def steps(third, fractions):
    """The structure's free-amount reads, and per (of, fraction) one IMEX step's verdict from the
    drawn world's start at the dt whose predicted draw from the lumen's H is that fraction of its
    free amount ("free") or of its stored total ("stored"), with the stage read's verdict at the
    predicted totals."""
    with scoped(third):
        spec = parse_spec(drawn_world())
        impl, state, p, control = host(spec)
        h = list(spec.model.species_ids).index("H")
        outside = [n.id for n in spec.model.extracellular].index(fr.LUMEN)
        lumen = len(spec.model.cells) + outside
        read, ok = proton_buffer.stage_read(state, p, xp=np)
        assert ok
        base = {
            "free": float(amounts(read, p)[h, lumen]),
            "stored": float(amounts(state, p)[h, lumen]),
        }
        out = []
        for of, fraction in fractions:
            draw = fraction * base[of]
            dt = draw / float(p.imex_operator_time)  # The drawer's 1 fmol/s is the lumen's rate.
            increment = np.array(state.extracellular_amount_increment)
            increment[h, outside] -= draw
            # Past the floor the solve fails: numpy's warnings are silenced, its verdicts checked.
            with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
                _, valid = impl.imex_step(state, dt, control, p, xp=np)
                predicted = state._replace(extracellular_amount_increment=increment)
                _, read_ok = proton_buffer.stage_read(predicted, p, xp=np)
            out.append((bool(valid), bool(read_ok)))
        return impl.structure.free_amount_reads, out


def test_the_predictor_reads_the_free_amount_at_the_predicted_totals_where_the_law_declares_it():
    cases = (("free", 10.0), ("free", 0.5), ("stored", 1.01))
    listed, (ten, half, past) = steps(GENERAL, cases)
    assert listed == (proton_buffer.KIND_ID,)
    assert ten == (True, True)  # P1: the read at the predicted totals, valid and positive.
    assert half == (True, True)
    assert past == (False, False)  # Past the stored total the read, and so the step, refuse.
    for third in (None, VERSION_1, READS_LAW):  # Today's form, in each control: the plant.
        listed, (ten, half, past) = steps(third, cases)
        assert listed == ()
        assert ten == (False, True)  # The free amount less the draw is negative: refused.
        assert half == (True, True)
        assert past[0] is False


def test_the_switch_reaches_a_composite():
    plain = surface_pump_v3.structure(parse_spec(lumen_general()).model)
    # The general closure's own rows name cells.binding.rapid_binding@1 (the binding owner's third item).
    assert plain.free_amount_reads == (proton_buffer.KIND_ID,)
    raw = cs.frozen_definition(lumen_general())
    electrode = dict(cell_id=fr.CELL, carriers={"K": 1.0})
    raw["model"].setdefault("operators", []).append(
        dict(law="cells.operator.electrode_current_injection@1", electrodes=[electrode])
    )
    raw["experiment"]["injection_controls"] = [
        dict(cell_id=fr.CELL, schedule=[dict(time=0.0, current_A=2e-12)])
    ]
    # The species registry's stage-read check reads each row's (species, node), so the composite
    # parses with the binding owner's third item. Its model block binds through @3's structure
    # (pump_composite_adapter.inner_structure), which lists the read under the third item.
    spec = parse_spec(raw)
    assert pump_composite_adapter.inner_structure is surface_pump_v3.structure
    assert surface_pump_v3.structure(spec.model).free_amount_reads == (proton_buffer.KIND_ID,)
    with kind_registry.scope(kind_fixtures.registry(buffer(GENERAL))):
        listed = surface_pump_v3.structure(spec.model).free_amount_reads
    assert listed == (proton_buffer.KIND_ID,)


def test_a_read_mixing_the_two_forms_and_a_free_amount_read_beside_todays_are_refused():
    mixed = registry(reader("alpha", "alpha_block", (("K", "cell_0", GENERAL), ("Na", "cell_0"))))
    with kind_registry.scope(mixed):
        with pytest.raises(ConfigError, match="free_amounts on some rows and not on others"):
            parse_spec(declaring("alpha_block"))
    beside = registry(
        reader("alpha", "alpha_block", (("K", "cell_0", GENERAL),)),
        reader("beta", "beta_block", (("Na", "cell_0"),)),
    )
    with kind_registry.scope(beside):
        with pytest.raises(ConfigError, match="reads tests.kind.alpha@1's stage read at the predicted"):
            parse_spec(declaring("alpha_block", "beta_block"))
    both = registry(
        reader("alpha", "alpha_block", (("K", "cell_0", GENERAL),)),
        reader("beta", "beta_block", (("Na", "cell_0", GENERAL),)),
    )
    with kind_registry.scope(both):  # The controls: two free-amount reads are admitted.
        spec = parse_spec(declaring("alpha_block", "beta_block"))
        listed = surface_pump_v3.structure(spec.model).free_amount_reads
    assert listed == ("tests.kind.alpha@1", "tests.kind.beta@1")


def test_the_structure_refuses_entries_that_are_not_a_sorted_tuple_of_declared_kinds():
    """F's review: each half of the check carries its plant. Two declared kinds, alpha and beta."""
    both = registry(
        reader("alpha", "alpha_block", (("K", "cell_0", GENERAL),)),
        reader("beta", "beta_block", (("Na", "cell_0", GENERAL),)),
    )
    with kind_registry.scope(both):
        spec = parse_spec(declaring("alpha_block", "beta_block"))
        structure = surface_pump_v3.structure(spec.model)
    alpha, beta = "tests.kind.alpha@1", "tests.kind.beta@1"
    assert structure.free_amount_reads == (alpha, beta)
    order = "must be distinct declared kinds, in canonical \\(sorted ID\\) order"
    for planted in ((alpha, "tests.kind.undeclared@1"), (alpha, alpha), (beta, alpha)):
        with pytest.raises(ValueError, match=order):
            replace(structure, free_amount_reads=planted)
    for planted in ([alpha, beta], (alpha, 1), (alpha, "")):
        with pytest.raises(ValueError, match="Free-amount reads are a tuple of declared kind IDs"):
            replace(structure, free_amount_reads=planted)
    assert replace(structure, free_amount_reads=(beta,)).free_amount_reads == (beta,)
