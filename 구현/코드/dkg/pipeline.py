from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .config import YosysConfig
from .graph import DKGEdge, DKGNode
from .graph_build import build_nodes_and_edges, build_wires_and_cells
from .graph_updater import GraphUpdater
from .parsers import ConstraintParser
from .parsers.sdc_parser import SdcParser
from .parsers.xdc_parser import XdcParser
from .stages import FieldSource, ParsingStage
from .yosys_parser import parse_yosys


class DKGPipeline:
    """
    전체 DKG 구축 파이프라인.
    
    Usage:
        pipeline = DKGPipeline(yosys_config)
        
        # Stage 1: RTL 파싱
        pipeline.run_rtl_stage()
        
        # Stage 2: Constraint 추가
        pipeline.add_constraints("design.sdc")
        pipeline.add_constraints("design.xdc")
        
        # Stage 3: 타이밍 리포트 추가
        pipeline.add_timing_report("timing.rpt")
        
        # 최종 그래프 반환
        nodes, edges = pipeline.get_graph()
    """
    
    def __init__(self, yosys_config: YosysConfig):
        self.yosys_config = yosys_config
        
        self.nodes: Optional[Dict[str, DKGNode]] = None
        self.edges: Optional[Dict[str, DKGEdge]] = None
        self.updater: Optional[GraphUpdater] = None
        
        self.current_stage = None
        self.completed_stages: List[ParsingStage] = []
        
        # 파서 레지스트리
        self.parsers: Dict[str, ConstraintParser] = {
            "sdc": SdcParser(),
            "xdc": XdcParser(),
            # TODO: 추가 파서 등록
        }
    
    def run_rtl_stage(self) -> None:
        """Stage 1: RTL 파싱 (Yosys)"""
        yosys = parse_yosys(self.yosys_config)
        wires, cells = build_wires_and_cells(yosys)
        self.nodes, self.edges = build_nodes_and_edges(wires, cells)
        
        self.updater = GraphUpdater(self.nodes, self.edges)
        self.current_stage = ParsingStage.RTL
        self.completed_stages.append(ParsingStage.RTL)
        
        # 초기 메타데이터 설정 (모두 INFERRED)
        self._mark_initial_fields_as_inferred()
    
    def add_constraints(self, filepath: str) -> None:
        """Stage 2: Constraint 파일 추가"""
        if self.updater is None or self.nodes is None or self.edges is None:
            raise RuntimeError("RTL stage must be run first")
        
        # 파일 확장자로 파서 선택
        ext = Path(filepath).suffix.lower().lstrip(".")
        
        if ext not in self.parsers:
            raise ValueError(f"Unsupported constraint format: {ext}")
        
        parser = self.parsers[ext]
        parser.parse_and_update(filepath, self.updater, self.nodes, self.edges)
        
        if ParsingStage.CONSTRAINTS not in self.completed_stages:
            self.completed_stages.append(ParsingStage.CONSTRAINTS)
    
    def add_timing_report(self, filepath: str) -> None:
        """Stage 3: 타이밍 리포트 추가"""
        # TODO: 타이밍 리포트 파서 구현
        pass
    
    def add_floorplan(self, filepath: str) -> None:
        """Stage 4: Floorplan TCL 추가"""
        # TODO: TCL 파서 구현
        pass
    
    def get_graph(self) -> tuple[Dict[str, DKGNode], Dict[str, DKGEdge]]:
        """최종 그래프 반환"""
        if self.nodes is None or self.edges is None:
            raise RuntimeError("No graph available. Run RTL stage first.")
        return self.nodes, self.edges
    
    def get_updater(self) -> GraphUpdater:
        """GraphUpdater 반환 (고급 사용자용)"""
        if self.updater is None:
            raise RuntimeError("No updater available. Run RTL stage first.")
        return self.updater
    
    def export_metadata(self) -> dict:
        """메타데이터 요약 반환 (캐싱/디버깅용)"""
        if self.updater is None:
            return {}
        return self.updater.export_metadata_summary()
    
    def _mark_initial_fields_as_inferred(self) -> None:
        """RTL stage에서 추론한 필드들을 INFERRED로 마킹"""
        if self.nodes is None or self.edges is None or self.updater is None:
            return
        
        # clock_domain, flow_type 등 휴리스틱으로 채운 필드들
        for node_id, node in self.nodes.items():
            if node.clock_domain:
                self.updater.node_metadata[node_id].set(
                    "clock_domain",
                    node.clock_domain,
                    FieldSource.INFERRED,
                    ParsingStage.RTL,
                )
        
        for edge_id, edge in self.edges.items():
            if edge.flow_type:
                self.updater.edge_metadata[edge_id].set(
                    "flow_type",
                    edge.flow_type.value,
                    FieldSource.INFERRED,
                    ParsingStage.RTL,
                )
