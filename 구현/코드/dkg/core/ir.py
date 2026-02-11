from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Wire:
    wire_id: int
    name: str | None = None
    drivers: list[str] = field(default_factory=list)
    loads: list[str] = field(default_factory=list)
    src: Optional[str] = None


@dataclass
class CellIR:
    name: str
    type: str
    module: str
    port_dirs: dict[str, str]
    connections: dict[str, list[int]]
    src: Optional[str] = None
