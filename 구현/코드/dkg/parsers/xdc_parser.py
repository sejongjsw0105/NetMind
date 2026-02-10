from __future__ import annotations

import re
from typing import Dict

from ..graph import DKGEdge, DKGNode
from ..graph_updater import GraphUpdater
from ..stages import FieldSource, ParsingStage
from . import ConstraintParser
from .parser_utils import extract_bracket_targets, match_any


class XdcParser(ConstraintParser):
    """
    XDC (Xilinx Design Constraints) 파서.
    
    SDC와 유사하지만 Xilinx 특화 명령 포함:
    - set_property LOC / IOSTANDARD: 핀 배치
    - create_pblock: 물리적 블록 정의
    """
    
    def get_stage(self) -> ParsingStage:
        return ParsingStage.CONSTRAINTS
    
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

            if raw.startswith("set_property"):
                self._parse_set_property(raw, line_num, filepath, updater, nodes)
            elif raw.startswith("create_pblock"):
                self._parse_create_pblock(raw)
            elif raw.startswith("add_cells_to_pblock"):
                self._parse_add_cells_to_pblock(raw, line_num, filepath, updater, nodes)

    def _parse_set_property(
        self,
        line: str,
        line_num: int,
        filepath: str,
        updater: GraphUpdater,
        nodes: Dict[str, DKGNode],
    ) -> None:
        match = re.search(r"set_property\s+(LOC|IOSTANDARD)\s+(\S+)", line)
        if not match:
            return

        prop = match.group(1)
        value = match.group(2)
        targets = extract_bracket_targets(line, ("ports", "pins", "cells"))
        if not targets:
            return

        for node_id, node in nodes.items():
            candidates = [node.local_name, node.hier_path, node.canonical_name]
            if not match_any(targets, candidates):
                continue

            new_attrs = dict(node.attributes)
            new_attrs[prop] = value
            updater.update_node_field(
                node_id,
                "attributes",
                new_attrs,
                FieldSource.DECLARED,
                ParsingStage.CONSTRAINTS,
                filepath,
                line_num,
            )

    def _parse_create_pblock(self, line: str) -> None:
        match = re.search(r"create_pblock\s+(\S+)", line)
        if not match:
            return

    def _parse_add_cells_to_pblock(
        self,
        line: str,
        line_num: int,
        filepath: str,
        updater: GraphUpdater,
        nodes: Dict[str, DKGNode],
    ) -> None:
        pblock_name = None
        pblock_match = re.search(r"add_cells_to_pblock\s+\[get_pblocks\s+([^\]]+)\]", line)
        if pblock_match:
            pblock_name = pblock_match.group(1).strip()
        else:
            direct = re.search(r"add_cells_to_pblock\s+(\S+)", line)
            if direct:
                pblock_name = direct.group(1)

        if not pblock_name:
            return

        targets = extract_bracket_targets(line, ("cells",))
        if not targets:
            return

        for node_id, node in nodes.items():
            candidates = [node.local_name, node.hier_path, node.canonical_name]
            if not match_any(targets, candidates):
                continue

            new_attrs = dict(node.attributes)
            new_attrs["pblock"] = pblock_name
            new_attrs["pblock_seed"] = pblock_name
            updater.update_node_field(
                node_id,
                "attributes",
                new_attrs,
                FieldSource.DECLARED,
                ParsingStage.FLOORPLAN,
                filepath,
                line_num,
            )

