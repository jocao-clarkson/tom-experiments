from dataclasses import dataclass, field
from typing import Callable

# A rule takes a row dict and returns None if valid, or a reason string.
Rule = Callable[[dict], str | None]


@dataclass
class Reject:
    line: int
    row: dict
    reason: str


@dataclass
class ValidationResult:
    valid: list[dict] = field(default_factory=list)
    rejects: list[Reject] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.valid) + len(self.rejects)

    @property
    def reject_ratio(self) -> float:
        return len(self.rejects) / self.total if self.total else 0.0


class Validator:
    def __init__(self, required: list[str], rules: list[Rule]):
        self.required = required
        self.rules = rules

    def run(self, rows, first_line: int = 2) -> ValidationResult:
        """Validate rows; line numbers assume a header on line 1."""
        result = ValidationResult()
        for offset, row in enumerate(rows):
            line = first_line + offset
            missing = [c for c in self.required if not (row.get(c) or "").strip()]
            if missing:
                result.rejects.append(Reject(line, row, f"missing:{','.join(missing)}"))
                continue
            reason = next((r for r in (rule(row) for rule in self.rules) if r), None)
            if reason:
                result.rejects.append(Reject(line, row, reason))
            else:
                result.valid.append(row)
        return result
