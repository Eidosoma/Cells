"""The judges' harness check before scoring (the external review's finding 4, the lead's ruling
of 18 November 2026).

The judges compare series at the records two parts share, and judge a refusal class by all() over
its examples. So a dropped sample, or a class with no example on one side, would score as if the
evidence were complete. The shared evaluator (validation/morphogenesis/mg0a_gradient.evaluate)
also passes a criterion whose metric is an empty list.

The registered protocols, their criteria, their judged folders and the evaluator's code stay byte
for byte as registered. Instead, each judge's entry calls these checks after merging the records
and before scoring, and refuses to score when any check finds a gap. That refusal is a harness
failure, not a verdict:
- grid(label, found, registered): a part's record times must equal its registered grid, the same
  times in the same order, none missing and none extra;
- classes(rows, names): every registered refusal class has at least one refused and one admitted
  example;
- metrics(criteria, results): no criterion's metric resolves to an empty list (resolved as
  evaluate resolves it);
- refuse(problems): raises SystemExit("Refused: incomplete evidence ...") when there are any.

The callers: the FR judges' entries (FR-1, FR-3, FR-4/5, FR-10 and FR-6's A5''), which refuse a
judged run and record a development verdict's gaps; and MG0c's judge (mg0c_turing.judge) and
development values (mg0c_protocol.development_values), which call the empty-metric guard before
evaluate (the lead's recorded assignment; MG0c's registered protocol pins neither file's bytes).
"""

from validation.morphogenesis.mg0a_gradient import _lookup

VERSION = "1.1"  # The judges' harness version that adds these checks (v1's scoring unchanged).


def grid(label, found, registered):
    """[problem] when `found` (a part's record times) is not exactly `registered`."""
    registered = list(registered)
    if found is not None and list(found) == registered:
        return []
    found = list(found or [])
    missing = [t for t in registered if t not in set(found)]
    extra = [t for t in found if t not in set(registered)]
    return [f"{label}: {len(found)} record times against the registered grid's {len(registered)} "
            f"(missing {missing[:5]}, extra {extra[:5]})"]


def classes(rows, names):
    """[problem] for each registered class without a refused or an admitted example."""
    rows = rows or {}
    out = []
    for name in names:
        row = rows.get(name) or {}
        refused, admitted = row.get("refused") or [], row.get("admitted") or []
        if not refused or not admitted:
            out.append(f"refusal class {name}: {len(refused)} refused and {len(admitted)} admitted "
                       "examples (each side needs one)")
    return out


def metrics(criteria, results):
    """[problem] for each criterion's metric that resolves to an empty list."""
    out = []
    for c in criteria:
        for path in c["metrics"]:
            try:
                value = _lookup(results, path)
            except (KeyError, IndexError, TypeError):
                continue  # evaluate reads it as None and fails the criterion.
            if isinstance(value, list) and not value:
                out.append(f"criterion {c['id']}: metric {path} is an empty list")
    return out


def refuse(problems):
    if problems:
        shown = "; ".join(problems[:12]) + (f"; and {len(problems) - 12} more" if len(problems) > 12
                                            else "")
        raise SystemExit(f"Refused: incomplete evidence (harness {VERSION}; a harness failure, "
                         f"not a verdict): {shown}")
