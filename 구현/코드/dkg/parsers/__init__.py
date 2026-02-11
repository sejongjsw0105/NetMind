from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict

from ..core.graph import DKGEdge, DKGNode
from ..builders.graph_updater import GraphUpdater
from ..pipeline.stages import ParsingStage


class ConstraintParser(ABC):
    """제약 파일 파서 베이스 클래스"""
    
    @abstractmethod
    def get_stage(self) -> ParsingStage:
        """이 파서가 속한 stage 반환"""
        pass
    
    @abstractmethod
    def parse_and_update(
        self,
        filepath: str,
        updater: GraphUpdater,
        nodes: Dict[str, DKGNode],
        edges: Dict[str, DKGEdge],
    ) -> None:
        """
        파일을 파싱하고 그래프를 업데이트.
        
        Args:
            filepath: 파싱할 파일 경로
            updater: GraphUpdater 인스턴스
            nodes: 기존 노드 딕셔너리
            edges: 기존 엣지 딕셔너리
        """
        pass
