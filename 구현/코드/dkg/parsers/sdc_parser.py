from __future__ import annotations

import re
from typing import Dict

from ..graph import DKGEdge, DKGNode
from ..graph_updater import GraphUpdater
from ..stages import FieldSource, ParsingStage
from . import ConstraintParser


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
                    line, line_num, filepath, updater, edges
                )
            
            # set_multicycle_path 처리
            elif line.startswith("set_multicycle_path"):
                self._parse_multicycle_path(
                    line, line_num, filepath, updater, edges
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
        edges: Dict[str, DKGEdge],
    ) -> None:
        """
        set_false_path 명령 파싱.
        예: set_false_path -from [get_pins src/*] -to [get_pins dst/*]
        """
        # 간단한 구현 (실제로는 -from/-to 파싱 필요)
        # TODO: 실제 from/to 노드 매칭 로직 구현
        
        # 일단 placeholder
        # affected_edges = find_edges_between(from_pattern, to_pattern)
        # for edge_id in affected_edges:
        #     updater.update_edge_field(...)
        pass
    
    def _parse_multicycle_path(
        self,
        line: str,
        line_num: int,
        filepath: str,
        updater: GraphUpdater,
        edges: Dict[str, DKGEdge],
    ) -> None:
        """
        set_multicycle_path 명령 파싱.
        예: set_multicycle_path 2 -from [get_pins ...] -to [get_pins ...]
        """
        # TODO: 구현
        pass
