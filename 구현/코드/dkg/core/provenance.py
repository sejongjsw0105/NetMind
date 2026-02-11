from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple, List


@dataclass
class Provenance:
    origin_file: Optional[str] = None
    origin_line: Optional[int] = None
    tool_stage: str = "rtl"  # rtl / synth / timing / constraint
    confidence: str = "exact"  # exact / inferred


def add_provenance(obj, prov: Provenance, make_primary: bool = False) -> None:
    obj.provenances.append(prov)
    if make_primary or obj.primary_provenance is None:
        obj.primary_provenance = prov


def merge_provenances_nodes(nodes: Iterable) -> Tuple[Provenance, List[Provenance]]:
    new_provs: List[Provenance] = []
    for n in nodes:
        new_provs.extend(n.provenances)

    files = [p.origin_file for p in new_provs if p.origin_file]
    lines = [p.origin_line for p in new_provs if p.origin_line]

    primary = Provenance(
        origin_file=files[0] if files else None,
        origin_line=min(lines) if lines else None,
        tool_stage="rtl",
        confidence="inferred",
    )

    return primary, new_provs


def merge_provenances_edges(edges: Iterable) -> Tuple[Provenance, List[Provenance]]:
    new_provs: List[Provenance] = []
    for e in edges:
        new_provs.extend(e.provenances)

    files = [p.origin_file for p in new_provs if p.origin_file]
    lines = [p.origin_line for p in new_provs if p.origin_line]

    primary = Provenance(
        origin_file=files[0] if files else None,
        origin_line=min(lines) if lines else None,
        tool_stage="rtl",
        confidence="inferred",
    )

    return primary, new_provs
