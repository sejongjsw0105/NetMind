from __future__ import annotations

from typing import Dict

from ..graph import DKGEdge, DKGNode
from ..graph_updater import GraphUpdater
from ..stages import ParsingStage
from . import ConstraintParser


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
        # TODO: XDC 파싱 구현
        # SDC 파서와 유사하지만 set_property 등 처리
        pass
