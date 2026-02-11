from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional
from ..utils.config import YosysConfig
from ..core.graph import DKGEdge, DKGNode
from ..builders.graph_build import build_nodes_and_edges, build_wires_and_cells
from ..builders.graph_updater import GraphUpdater
from ..cache import GraphSnapshot, GraphVersion, load_snapshot, save_snapshot
from ..parsers import ConstraintParser
from ..parsers.sdc_parser import SdcParser
from ..parsers.tcl_parser import TclParser
from ..parsers.timing_report_parser import TimingReportParser
from ..parsers.xdc_parser import XdcParser
from ..parsers.bd_parser import BdParser
from .stages import FieldSource, ParsingStage
from ..builders.supergraph import SuperGraph, GraphContext, ViewBuilder, GraphViewType
from ..utils import compute_file_hash
from ..parsers.yosys_parser import parse_yosys


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
        self.supergraph: Optional[SuperGraph] = None
        
        self.current_stage = None
        self.completed_stages: List[ParsingStage] = []
        
        # 입력 파일 추적 (버전 계산용)
        self.rtl_files: List[str] = []
        self.constraint_files: List[str] = []
        self.timing_files: List[str] = []
        
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
        
        # RTL 파일 추적
        if self.yosys_config.out_json_win:
            self.rtl_files.append(self.yosys_config.out_json_win)
        
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
        
        # 제약 파일 추적
        self.constraint_files.append(filepath)
        
        if ParsingStage.CONSTRAINTS not in self.completed_stages:
            self.completed_stages.append(ParsingStage.CONSTRAINTS)
    
    def add_timing_report(self, filepath: str) -> None:
        """Stage 3: 타이밍 리포트 추가"""
        if self.updater is None or self.nodes is None or self.edges is None:
            raise RuntimeError("RTL stage must be run first")
        
        # 타이밍 리포트 파싱
        parser = TimingReportParser()
        paths = parser.parse_file(filepath)
        
        # 그래프에 반영
        parser.apply_to_graph(self.nodes, self.edges, self.updater)
        
        # 파일 추적
        self.timing_files.append(filepath)
        
        if ParsingStage.TIMING not in self.completed_stages:
            self.completed_stages.append(ParsingStage.TIMING)
        
        # 요약 출력
        summary = parser.get_summary()
        print(f"✅ 타이밍 리포트 파싱 완료: {filepath}")
        print(f"   - 경로 수: {summary['total_paths']}")
        if summary.get('worst_slack') is not None:
            print(f"   - 최악 slack: {summary['worst_slack']:.2f} ns")
    
    def add_floorplan(self, filepath: str) -> None:
        """Stage 4: Floorplan TCL 추가"""
        if self.updater is None or self.nodes is None or self.edges is None:
            raise RuntimeError("RTL stage must be run first")

        parser = TclParser()
        parser.parse_and_update(filepath, self.updater, self.nodes, self.edges)

        if ParsingStage.FLOORPLAN not in self.completed_stages:
            self.completed_stages.append(ParsingStage.FLOORPLAN)

    def add_board(self, filepath: str) -> None:
        """Stage 5: BD/board constraints 추가"""
        if self.updater is None or self.nodes is None or self.edges is None:
            raise RuntimeError("RTL stage must be run first")

        parser = BdParser()
        parser.parse_and_update(filepath, self.updater, self.nodes, self.edges)

        if ParsingStage.BOARD not in self.completed_stages:
            self.completed_stages.append(ParsingStage.BOARD)
    
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
    
    def compute_version(self) -> GraphVersion:
        """현재 상태의 GraphVersion 계산"""
        import hashlib
        
        # RTL 해시 (모든 RTL 파일의 조합)
        rtl_hash = ""
        if self.rtl_files:
            combined = "".join(compute_file_hash(f) for f in self.rtl_files)
            rtl_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]
        
        # Constraint 해시
        constraint_hash = None
        if self.constraint_files:
            combined = "".join(compute_file_hash(f) for f in self.constraint_files)
            constraint_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]
        
        # Timing 해시
        timing_hash = None
        if self.timing_files:
            combined = "".join(compute_file_hash(f) for f in self.timing_files)
            timing_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]
        
        # 정책 버전 (향후 확장)
        policy_versions = {}
        
        return GraphVersion(
            rtl_hash=rtl_hash,
            constraint_hash=constraint_hash,
            timing_hash=timing_hash,
            policy_versions=policy_versions,
        )
    
    def save_cache(self, filepath: str | Path, indent: Optional[int] = None) -> None:
        """현재 그래프를 캐시 파일로 저장"""
        if self.nodes is None or self.edges is None:
            raise RuntimeError("No graph available. Run RTL stage first.")
        
        version = self.compute_version()
        snapshot = GraphSnapshot(
            version=version,
            dkg_nodes=self.nodes,
            dkg_edges=self.edges,
            supergraph=self.supergraph,
        )
        save_snapshot(snapshot, filepath, indent=indent)
    
    @classmethod
    def load_from_cache(cls, filepath: str | Path, yosys_config: Optional[YosysConfig] = None) -> "DKGPipeline":
        """캐시 파일에서 파이프라인 복원"""
        snapshot = load_snapshot(filepath)
        
        # 더미 config (캐시 로딩 시에는 필요 없음)
        if yosys_config is None:
            yosys_config = YosysConfig(src_dir_win="", out_json_win="", top_module="")
        
        pipeline = cls(yosys_config)
        pipeline.nodes = snapshot.dkg_nodes
        pipeline.edges = snapshot.dkg_edges
        pipeline.supergraph = snapshot.supergraph
        
        # 메타데이터는 재생성하지 않음 (읽기 전용 모드)
        pipeline.updater = None
        
        return pipeline

    def build_supergraph(self, view: GraphViewType = GraphViewType.Connectivity) -> None:

            if self.nodes is None or self.edges is None:
                raise RuntimeError("Run RTL stage first.")

            context = GraphContext.DESIGN
            

            for node in self.nodes.values():
                if node.attributes.get("design_context") == "sim":
                    context = GraphContext.SIMULATION
                    print(f"ℹ️ Simulation context detected from node attributes.")
                    break
            
            print(f"🏗️ Building SuperGraph (View: {view.value}, Context: {context.value})...")
            
            view_builder = ViewBuilder(
                self.nodes, 
                self.edges, 
                view, 
                context=context  
            )
            
            self.supergraph = view_builder.build()
            print(f"✅ SuperGraph built: {len(self.supergraph.super_nodes)} nodes, {len(self.supergraph.super_edges)} edges.")