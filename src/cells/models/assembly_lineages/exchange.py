"""cells.exchange.reservoir_exchange@1: single molecules exchanged between a held phase and an assembly.

The law (GARD_DESIGN §1.4, 1; §2.1). A held phase (a reservoir) keeps the activity rho_i of each
type fixed; the assembly is an ideal-mixing phase of N = sum_i n_i molecules. For type i:

    join   n -> n + e_i   at rate  kf_i * rho_i * N      first order in the held activity, and in
                                                         the assembly's size (an empty assembly
                                                         takes up nothing)
    leave  n -> n - e_i   at rate  kb_i * n_i

with kf_i = K_i * kb_i, K_i the type's transfer constant (family.py, its one authority).

What the mean field's composition x_i = n_i / N does depends on the leave constants (GARD_DESIGN
§2.1). Write theta_i = K_i rho_i:
- zero net exchange, a true fixed point at x_i = theta_i, needs sum_j theta_j = 1; otherwise the
  assembly grows (sum_j theta_j > 1) or shrinks;
- with a common leave constant kb, dx_i/dt = kb (theta_i - x_i sum_j theta_j), so the composition
  relaxes toward theta_i / sum_j theta_j while N changes;
- with a leave constant per type, kb_i (`leave_rate` admits one), the proportions depend on the
  kb_i as well and need not stay at theta_i / sum_j theta_j: counts (1, 1), theta = (1, 1) and
  kb = (1, 2) give dx_1/dt = -1/4, and the compiled engine agrees.
(Corrected 19 November 2026 from the Lean proofs project's finding, lean/PROGRESS.md and
lean/CellsProofs/Chemistry/ReservoirExchange.lean; the earlier wording stated the common-kb result
without its condition.)

Thermodynamics. Write theta_i = K_i rho_i. The jump process's affinity of the transfer pair
n <-> n + e_i is

    A_i(n) = ln[ a_join_i(n) / a_leave_i(n + e_i) ] = ln theta_i + ln N - ln(n_i + 1),

which is ln pi(n + e_i) - ln pi(n) for the product measure

    pi(n) ~ (N - 1)! prod_i theta_i^n_i / n_i!        (N >= 1),

so the law is passive: its event heat telescopes into a state function (ledger.py). A rate-factor
law multiplies both rates; it stays passive only if its factor is the same for a transfer and its
reverse, which the kernel's check tests (balance.py). The empty assembly is outside the measure:
nothing joins it, so a lineage that loses its last molecule is extinct (GARD_DESIGN §1.5, 3).

Declared data (per world, layout values): rho_i > 0 (`supply`) and kb_i > 0 (`leave_rate`), each
one number for every type or one per type; K_i from the type family. Units: activities are
dimensionless, rates are per nominal time unit (GARD_DESIGN §1.7: the source's constants carry no
calibrated unit, and the natural clock is the fission count).

Source: Segre, Ben-Eli and Lancet (2000), PNAS 97:4112, and the Plastic Heredity preprint's
Appendix F (Zenodo 10.5281/zenodo.22143269, CC BY 4.0), which state this split of the rate law.
"""

from dataclasses import dataclass
from typing import ClassVar

from cells.models.assembly_lineages import EXCHANGE_INTERFACE, EXCHANGE_LAW, MODEL_ID
from cells.modules import Citation, Law

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import laws as law_registry

TEST = "tests/unit/test_assembly_lineages_kernel.py::test_kernel_matches_the_oracle"


@dataclass(frozen=True)
class ExchangeLaw(Law):
    """The exchange-law interface (cells.exchange_law@1) on the law template: single molecules
    exchanged between a held phase and an assembly; hosted by the family's model."""

    energy_role: str  # "passive": its affinity is a state-function difference (above).
    data: tuple[str, ...]
    reads: str
    changes: str
    formulas: dict

    interface: ClassVar[str] = EXCHANGE_INTERFACE


LAW = law_registry.BUILTIN.register(
    ExchangeLaw(
        EXCHANGE_LAW,
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "Segre, Ben-Eli and Lancet (2000), PNAS 97:4112; Plastic Heredity preprint v5.0, "
            "Appendix F (Zenodo 10.5281/zenodo.22143269)",
            "the join and leave propensities without the catalytic factor",
            "CC BY 4.0 (the preprint); numbers cited under D186",
            ("the join constant is derived from the type's transfer constant (one authority)",),
        ),
        test=TEST,
        energy_role="passive",
        data=("supply", "leave_rate"),
        reads="the assembly's counts n_i and size N; the held activities rho_i",
        changes="one molecule of one type per event: +1 (join) or -1 (leave), from or to the held "
        "phase",
        formulas={
            "join_i": "kf_i * rho_i * N, with kf_i = K_i * kb_i (the type family's transfer "
            "constant)",
            "leave_i": "kb_i * n_i",
            "affinity_i(n)": "ln theta_i + ln N - ln(n_i + 1), theta_i = K_i rho_i, for "
            "n <-> n + e_i",
            "measure": "pi(n) ~ (N - 1)! prod_i theta_i^n_i / n_i!, N >= 1",
            "without_a_rate_factor": "g_join_i = g_leave_i = 1",
        },
    )
)


def provenance(law):
    """A law's provenance as a run record states it: its tag and its citation."""
    source = law.source
    if not isinstance(source, Citation):
        return {"kind": law.provenance, "source": source}
    return {
        "kind": law.provenance,
        "source": source.source,
        "place": source.place,
        "licence": source.licence,
        "departures": list(source.departures),
    }


def base_rates(counts, size, kf_rho, kb):
    """(join [C], leave [C]): kf_rho * N and kb * n, as float64 arrays.

    counts: [C] float64 (exact small integers); size: the scalar N as float64."""
    return kf_rho * size, kb * counts


def affinity(counts, i, log_theta):
    """A_i(n) for the transfer n <-> n + e_i (host, NumPy): ln theta_i + ln N - ln(n_i + 1)."""
    import math

    size = float(sum(counts))
    return log_theta[i] + math.log(size) - math.log(counts[i] + 1.0)
