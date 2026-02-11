from __future__ import annotations

import re
from typing import Dict

from ..core.graph import DKGEdge, DKGNode
from ..builders.graph_updater import GraphUpdater
from ..pipeline.stages import FieldSource, ParsingStage
from . import ConstraintParser


class BdParser(ConstraintParser):
    """
    BD (block design) parser for IP instance grouping seeds.
    """

    def get_stage(self) -> ParsingStage:
        return ParsingStage.BOARD

    def parse_and_update(
        self,
        filepath: str,
        updater: GraphUpdater,
        nodes: Dict[str, DKGNode],
        edges: Dict[str, DKGEdge],
    ) -> None:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line_num, line in enumerate(lines, start=1):
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue

            if raw.startswith("create_bd_cell"):
                self._parse_create_bd_cell(raw, line_num, filepath, updater, nodes)

    def _parse_create_bd_cell(
        self,
        line: str,
        line_num: int,
        filepath: str,
        updater: GraphUpdater,
        nodes: Dict[str, DKGNode],
    ) -> None:
        match = re.search(r"create_bd_cell\s+-type\s+ip\s+-vlnv\s+(\S+)\s+(\S+)", line)
        if not match:
            return

        vlnv = match.group(1)
        inst = match.group(2)

        for node_id, node in nodes.items():
            candidates = [node.local_name, node.hier_path, node.canonical_name]
            if not any(inst == cand or (cand and inst in cand) for cand in candidates):
                continue

            new_attrs = dict(node.attributes)
            new_attrs["bd_ip"] = vlnv
            new_attrs["bd_group"] = vlnv

            updater.update_node_field(
                node_id,
                "attributes",
                new_attrs,
                FieldSource.DECLARED,
                ParsingStage.BOARD,
                filepath,
                line_num,
            )
