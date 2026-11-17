"""The family's operator interface, cells.lineage_operator@1, on seam F's operator template.

A lineage operator acts on an assembly's lineage at its events: the size-triggered fission
(fission.py) and the continuation of one daughter (continuation.py). Each is a declaration of this
type, built on the template of a family's own operators (cells.modules.FamilyOperator), hosted by
the family's model and registered from its home with the registry's public call, as the static
model table's row for the family lists them. Its fields are what a run record states of it, so a
replay needs no code: what it reads and writes, its energy role, its rules, its stream, and its
contract in words (the trigger, the places and draws, the rules' readings).
"""

from dataclasses import dataclass
from typing import ClassVar

from cells.models.assembly_lineages import MODEL_ID, OPERATOR_INTERFACE
from cells.modules import Citation, FamilyOperator


@dataclass(frozen=True)
class LineageOperator(FamilyOperator):
    reads: str
    writes: str
    energy_role: str
    rules: dict  # {rule: [its choices]}
    stream: str
    contract: dict  # The operator's statements in words, as a run record states them.

    interface: ClassVar[str] = OPERATOR_INTERFACE

    def errors(self):
        out = super().errors()
        if self.host != MODEL_ID:
            out.append(f"a lineage operator is hosted by {MODEL_ID}")
        for name in ("reads", "writes", "energy_role", "stream"):
            if not (isinstance(getattr(self, name), str) and getattr(self, name)):
                out.append(f"its {name} is stated")
        if not (isinstance(self.rules, dict) and isinstance(self.contract, dict)):
            out.append("its rules and its contract are mappings")
        return out

    def record(self):
        """The declaration as a run record states it (records.py's `operators`)."""
        source = self.source
        provenance = {"kind": self.provenance}
        if isinstance(source, Citation):
            provenance |= {
                "source": source.source,
                "place": source.place,
                "licence": source.licence,
                "departures": list(source.departures),
            }
        return {
            "id": self.operator_id,
            "interface": self.interface,
            "reads": self.reads,
            "writes": self.writes,
            "energy_role": self.energy_role,
            "rules": {k: list(v) if isinstance(v, tuple) else v for k, v in self.rules.items()},
            "stream": self.stream,
            **self.contract,
            "provenance": provenance,
            "test": self.test,
        }
