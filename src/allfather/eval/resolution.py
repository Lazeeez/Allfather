"""Gold-independent symbol resolution for evaluation v2 (not yet the default scorer).

The caller must supply the COMPLETE non-test candidate inventory at the base snapshot,
including repeated IDs for overloaded/colliding symbols. A gold-label list is not an
inventory. Qualified names may omit leading scopes, but may not invent a different scope.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

Status = Literal["exact", "resolved", "ambiguous", "invalid", "duplicate"]
VERSION = "inventory-resolution-v2-draft"


@dataclass(frozen=True, slots=True)
class Resolution:
    slot: int
    status: Status
    canonical: str | None


class SymbolResolver:
    def __init__(self, inventory: list[str]) -> None:
        self.counts = Counter(inventory)
        self.aliases: dict[tuple[str, str], set[str]] = defaultdict(set)
        for unit in self.counts:
            if "::" not in unit:
                raise ValueError(f"not a canonical symbol ID: {unit!r}")
            path, name = unit.split("::", 1)
            if not path or not name:
                raise ValueError(f"not a canonical symbol ID: {unit!r}")
            parts = name.split(".")
            for start in range(len(parts)):
                self.aliases[path, ".".join(parts[start:])].add(unit)

    def resolve(self, prediction: object, slot: int) -> Resolution:
        if not isinstance(prediction, dict):
            return Resolution(slot, "invalid", None)
        path, name = prediction.get("file"), prediction.get("name")
        if not isinstance(path, str) or not isinstance(name, str):
            return Resolution(slot, "invalid", None)
        path = path.strip().replace("\\", "/")
        while path.startswith("./"):
            path = path[2:]
        name = name.strip().replace("::", ".")
        if (
            not path
            or not name
            or ":" in path
            or PurePosixPath(path).is_absolute()
            or ".." in PurePosixPath(path).parts
        ):
            return Resolution(slot, "invalid", None)
        path = PurePosixPath(path).as_posix()
        unit = f"{path}::{name}"
        if unit in self.counts:
            return (
                Resolution(slot, "exact", unit)
                if self.counts[unit] == 1
                else Resolution(slot, "ambiguous", None)
            )
        candidates = self.aliases.get((path, name), set())
        if len(candidates) == 1:
            canonical = next(iter(candidates))
            if self.counts[canonical] == 1:
                return Resolution(slot, "resolved", canonical)
        return Resolution(slot, "ambiguous" if candidates else "invalid", None)

    def answer(self, answer: object, k: int = 10) -> list[Resolution]:
        if not isinstance(answer, dict) or not isinstance(answer.get("functions"), list):
            return []
        out, seen = [], set()
        for slot, prediction in enumerate(answer["functions"][:k], 1):
            resolved = self.resolve(prediction, slot)
            if resolved.canonical in seen:
                resolved = Resolution(slot, "duplicate", None)
            if resolved.canonical is not None:
                seen.add(resolved.canonical)
            out.append(resolved)
        return out


def ranking_slots(resolutions: list[Resolution]) -> list[str]:
    """Unique failure tokens keep invalid/ambiguous/duplicate slots in the rank budget.

    Valid inventory IDs always contain '::'; the failure tokens never do.
    """
    return [
        r.canonical if r.canonical is not None else f"<unresolved-slot-{i}>"
        for i, r in enumerate(resolutions)
    ]
