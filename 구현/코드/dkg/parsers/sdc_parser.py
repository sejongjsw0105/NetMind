from __future__ import annotations

import re
from typing import Dict

from ..core.graph import DKGEdge, DKGNode
from ..builders.graph_updater import GraphUpdater
from ..pipeline.stages import FieldSource, ParsingStage
from . import ConstraintParser
from .parser_utils import extract_option_targets, match_any


class SdcParser(ConstraintParser):
    """
    SDC (Synopsys Design Constraints) 파서.
    
    처리하는 명령:
    - create_clock: 클럭 정의
    - set_input_delay / set_output_delay: I/O 타이밍
    - set_false_path: false path 제약
    - set_multicycle_path: multicycle 제약
    - set_max_delay / set_min_delay: 지연 제약
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
            line = line.strip()
            
            # create_clock 처리
            if line.startswith("create_clock"):
                self._parse_create_clock(
                    line, line_num, filepath, updater, nodes, edges
                )
            
            # set_false_path 처리
            elif line.startswith("set_false_path"):
                self._parse_false_path(
                    line, line_num, filepath, updater, nodes, edges
                )
            
            # set_multicycle_path 처리
            elif line.startswith("set_multicycle_path"):
                self._parse_multicycle_path(
                    line, line_num, filepath, updater, nodes, edges
                )
    
    def _parse_create_clock(
        self,
        line: str,
        line_num: int,
        filepath: str,
        updater: GraphUpdater,
        nodes: Dict[str, DKGNode],
        edges: Dict[str, DKGEdge],
    ) -> None:
        """
        create_clock 명령 파싱.
        예: create_clock -name clk -period 10 [get_ports clk]
        """
        # 간단한 정규식 (실제로는 더 정교해야 함)
        match = re.search(r"-name\s+(\w+)", line)
        if not match:
            return
        
        clock_name = match.group(1)
        
        # get_ports로 포트 이름 추출
        port_match = re.search(r"get_ports\s+(\w+)", line)
        if not port_match:
            return
        
        port_name = port_match.group(1)
        
        # 해당 포트를 가진 노드들 찾기
        for node_id, node in nodes.items():
            if node.local_name == port_name:
                updater.update_node_field(
                    node_id,
                    "clock_domain",
                    clock_name,
                    FieldSource.DECLARED,
                    ParsingStage.CONSTRAINTS,
                    filepath,
                    line_num,
                )
        
        # 해당 신호를 가진 엣지들도 업데이트
        for edge_id, edge in edges.items():
            if edge.signal_name == port_name:
                updater.update_edge_field(
                    edge_id,
                    "clock_signal",
                    clock_name,
                    FieldSource.DECLARED,
                    ParsingStage.CONSTRAINTS,
                    filepath,
                    line_num,
                )
    
    def _parse_false_path(
        self,
        line: str,
        line_num: int,
        filepath: str,
        updater: GraphUpdater,
        nodes: Dict[str, DKGNode],
        edges: Dict[str, DKGEdge],
    ) -> None:
        """
        set_false_path 명령 파싱.
        예: set_false_path -from [get_pins src/*] -to [get_pins dst/*]
        """
        from_patterns = extract_option_targets(line, "-from", ("ports", "pins", "cells"))
        to_patterns = extract_option_targets(line, "-to", ("ports", "pins", "cells"))

        if not from_patterns and not to_patterns:
            return

        for edge_id, edge in edges.items():
            src_node = nodes.get(edge.src_node)
            dst_node = nodes.get(edge.dst_node)
            if not src_node or not dst_node:
                continue

            src_candidates = [src_node.local_name, src_node.hier_path, src_node.canonical_name]
            dst_candidates = [dst_node.local_name, dst_node.hier_path, dst_node.canonical_name]

            src_match = True if not from_patterns else match_any(from_patterns, src_candidates)
            dst_match = True if not to_patterns else match_any(to_patterns, dst_candidates)

            if src_match and dst_match:
                updater.update_edge_field(
                    edge_id,
                    "timing_exception",
                    "false_path",
                    FieldSource.DECLARED,
                    ParsingStage.CONSTRAINTS,
                    filepath,
                    line_num,
                )
    
    def _parse_multicycle_path(
        self,
        line: str,
        line_num: int,
        filepath: str,
        updater: GraphUpdater,
        nodes: Dict[str, DKGNode],
        edges: Dict[str, DKGEdge],
    ) -> None:
        """
        set_multicycle_path 명령 파싱.
        예: set_multicycle_path 2 -from [get_pins ...] -to [get_pins ...]
        """
        value_match = re.search(r"set_multicycle_path\s+(-?\d+)", line)
        if not value_match:
            return

        multicycle = int(value_match.group(1))
        mc_type = None
        if "-hold" in line:
            mc_type = "hold"
        elif "-setup" in line:
            mc_type = "setup"

        from_patterns = extract_option_targets(line, "-from", ("ports", "pins", "cells"))
        to_patterns = extract_option_targets(line, "-to", ("ports", "pins", "cells"))

        if not from_patterns and not to_patterns:
            return

        for edge_id, edge in edges.items():
            src_node = nodes.get(edge.src_node)
            dst_node = nodes.get(edge.dst_node)
            if not src_node or not dst_node:
                continue

            src_candidates = [src_node.local_name, src_node.hier_path, src_node.canonical_name]
            dst_candidates = [dst_node.local_name, dst_node.hier_path, dst_node.canonical_name]

            src_match = True if not from_patterns else match_any(from_patterns, src_candidates)
            dst_match = True if not to_patterns else match_any(to_patterns, dst_candidates)

            if not (src_match and dst_match):
                continue

            new_params = dict(edge.parameters)
            existing = new_params.get("multicycle")
            if existing is None or multicycle > existing:
                new_params["multicycle"] = multicycle
            if mc_type:
                new_params["multicycle_type"] = mc_type

            updater.update_edge_field(
                edge_id,
                "parameters",
                new_params,
                FieldSource.DECLARED,
                ParsingStage.CONSTRAINTS,
                filepath,
                line_num,
            )
