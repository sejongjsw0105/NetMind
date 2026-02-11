from __future__ import annotations

import re
from typing import Dict, Optional

from ..core.graph import DKGEdge, DKGNode
from ..builders.graph_updater import GraphUpdater
from ..pipeline.stages import FieldSource, ParsingStage
from . import ConstraintParser


class TclParser(ConstraintParser):
    """
    TCL floorplan parser.

    - design vs sim flag
    - top scope
    """

    def get_stage(self) -> ParsingStage:
        return ParsingStage.FLOORPLAN

    def parse_and_update(
        self,
        filepath: str,
        updater: GraphUpdater,
        nodes: Dict[str, DKGNode],
        edges: Dict[str, DKGEdge],
    ) -> None:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        top_scope: Optional[str] = None
        design_context: Optional[str] = None

        for line in lines:
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue

            top_scope = top_scope or self._parse_top_scope(raw)
            design_context = design_context or self._parse_design_context(raw)

        if not top_scope and not design_context:
            return

        for node_id, node in nodes.items():
            if top_scope and node.hier_path != top_scope:
                continue

            new_attrs = dict(node.attributes)
            if top_scope:
                new_attrs["top_scope"] = top_scope
            if design_context:
                new_attrs["design_context"] = design_context

            updater.update_node_field(
                node_id,
                "attributes",
                new_attrs,
                FieldSource.DECLARED,
                ParsingStage.FLOORPLAN,
                filepath,
                None,
            )

    def _parse_top_scope(self, line: str) -> Optional[str]:
        match = re.search(r"set_property\s+top\s+(\S+)", line)
        if match:
            return match.group(1)

        match = re.search(r"set\s+top_(?:module|scope)\s+(\S+)", line)
        if match:
            return match.group(1)

        return None

    def _parse_design_context(self, line: str) -> Optional[str]:
        if "-simset" in line or "simulation" in line.lower():
            return "sim"
        if "-constrset" in line or "synth" in line.lower():
            return "design"

        match = re.search(r"set_property\s+design_mode\s+(\S+)", line)
        if match:
            value = match.group(1).lower()
            return "sim" if "sim" in value else "design"

        return None
