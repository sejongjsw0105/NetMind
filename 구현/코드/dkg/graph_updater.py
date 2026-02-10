from __future__ import annotations

from typing import Any, Dict, Optional

from .graph import DKGEdge, DKGNode
from .graph_metadata import EdgeMetadata, NodeMetadata
from .stages import FieldSource, ParsingStage


class GraphUpdater:
    """
    그래프를 점진적으로 업데이트하는 엔진.
    각 파싱 stage가 기존 그래프에 새 정보를 merge할 때 사용.
    """
    
    def __init__(
        self,
        nodes: Dict[str, DKGNode],
        edges: Dict[str, DKGEdge],
    ):
        self.nodes = nodes
        self.edges = edges
        
        # 메타데이터 저장소 (node_id/edge_id -> metadata)
        self.node_metadata: Dict[str, NodeMetadata] = {
            nid: NodeMetadata() for nid in nodes
        }
        self.edge_metadata: Dict[str, EdgeMetadata] = {
            eid: EdgeMetadata() for eid in edges
        }
    
    def update_node_field(
        self,
        node_id: str,
        field_name: str,
        value: Any,
        source: FieldSource,
        stage: ParsingStage,
        origin_file: Optional[str] = None,
        origin_line: Optional[int] = None,
    ) -> bool:
        """
        노드 필드를 업데이트.
        
        Returns:
            True if updated, False if skipped (lower priority)
        """
        if node_id not in self.nodes:
            return False
        
        meta = self.node_metadata[node_id]
        
        if not meta.should_update(field_name, source):
            return False
        
        # 메타데이터 업데이트
        meta.set(field_name, value, source, stage, origin_file, origin_line)
        
        # 실제 노드 객체 업데이트
        if hasattr(self.nodes[node_id], field_name):
            setattr(self.nodes[node_id], field_name, value)
        
        return True
    
    def update_edge_field(
        self,
        edge_id: str,
        field_name: str,
        value: Any,
        source: FieldSource,
        stage: ParsingStage,
        origin_file: Optional[str] = None,
        origin_line: Optional[int] = None,
    ) -> bool:
        """엣지 필드를 업데이트"""
        if edge_id not in self.edges:
            return False
        
        meta = self.edge_metadata[edge_id]
        
        if not meta.should_update(field_name, source):
            return False
        
        meta.set(field_name, value, source, stage, origin_file, origin_line)
        
        if hasattr(self.edges[edge_id], field_name):
            setattr(self.edges[edge_id], field_name, value)
        
        return True
    
    def batch_update_clock_domains(
        self,
        clock_assignments: Dict[str, str],  # node_id -> clock_domain
        source: FieldSource,
        stage: ParsingStage,
        origin_file: Optional[str] = None,
    ) -> int:
        """클럭 도메인 일괄 업데이트"""
        count = 0
        for node_id, clock_domain in clock_assignments.items():
            if self.update_node_field(
                node_id, "clock_domain", clock_domain, source, stage, origin_file
            ):
                count += 1
        return count
    
    def batch_update_timing_exceptions(
        self,
        exceptions: Dict[str, str],  # edge_id -> exception_type
        source: FieldSource,
        stage: ParsingStage,
        origin_file: Optional[str] = None,
    ) -> int:
        """타이밍 예외 일괄 업데이트"""
        count = 0
        for edge_id, exception_type in exceptions.items():
            if self.update_edge_field(
                edge_id, "timing_exception", exception_type, source, stage, origin_file
            ):
                count += 1
        return count
    
    def get_field_history(self, node_id: str, field_name: str) -> Optional[list]:
        """필드의 변경 이력 반환 (향후 확장용)"""
        # TODO: 이력 추적이 필요하면 metadata에 history 추가
        pass
    
    def export_metadata_summary(self) -> dict:
        """메타데이터 요약 반환 (디버깅/캐싱 용)"""
        return {
            "nodes": {
                nid: {
                    field: {
                        "source": meta.source.value,
                        "stage": meta.stage.value,
                    }
                    for field, meta in nm.fields.items()
                }
                for nid, nm in self.node_metadata.items()
            },
            "edges": {
                eid: {
                    field: {
                        "source": meta.source.value,
                        "stage": meta.stage.value,
                    }
                    for field, meta in em.fields.items()
                }
                for eid, em in self.edge_metadata.items()
            },
        }
