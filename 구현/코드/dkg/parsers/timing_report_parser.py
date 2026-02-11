"""
타이밍 리포트 파서 (Vivado/PrimeTime)

타이밍 리포트에서 DKG 그래프 구축에 필요한 정보 추출:
- Startpoint/Endpoint
- 경로상의 모든 셀
- 각 단계별 delay
- 최종 slack
- 클럭 도메인

⚠️ 중요: 한 노드/엣지는 여러 타이밍 경로에 나타날 수 있음
- Setup path와 Hold path가 다름
- 여러 클럭 도메인 존재
- 따라서 worst-case 값만 저장하고, 상세 정보는 메타데이터에 누적
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ..core.graph import DKGEdge, DKGNode
from ..builders.graph_updater import GraphUpdater


@dataclass
class TimingStage:
    """타이밍 경로의 한 단계"""
    point: str              # 셀/핀 이름
    incr_delay: float       # 증분 delay (ns)
    cumulative_delay: float # 누적 delay (ns)
    transition: str         # 'r' (rising) or 'f' (falling)


@dataclass
class TimingPath:
    """하나의 타이밍 경로"""
    startpoint: str
    endpoint: str
    clock: str
    path_type: str  # 'Setup' or 'Hold'
    
    slack: Optional[float] = None
    arrival_time: Optional[float] = None
    required_time: Optional[float] = None
    
    stages: List[TimingStage] = field(default_factory=list)


class TimingReportParser:
    """타이밍 리포트 파서 (Vivado/PrimeTime 형식)"""
    
    def __init__(self):
        self.paths: List[TimingPath] = []
    
    def parse_file(self, filepath: str | Path) -> List[TimingPath]:
        """타이밍 리포트 파일 전체 파싱"""
        filepath = Path(filepath)
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # "Startpoint:"로 시작하는 각 경로 섹션 분리
        # Vivado: "Startpoint: ..."
        # PrimeTime: "Point ..."로 시작하지만 헤더가 다름
        
        # Vivado 형식 감지
        if 'Startpoint:' in content:
            return self._parse_vivado_format(content)
        else:
            # TODO: PrimeTime 형식 지원
            return []
    
    def _parse_vivado_format(self, content: str) -> List[TimingPath]:
        """Vivado 타이밍 리포트 파싱"""
        paths = []
        
        # "Startpoint:"로 구분
        sections = re.split(r'\n(?=Startpoint:)', content)
        
        for section in sections:
            if 'Startpoint:' not in section:
                continue
            
            path = self._parse_single_path(section)
            if path:
                paths.append(path)
        
        self.paths = paths
        return paths
    
    def _parse_single_path(self, section: str) -> Optional[TimingPath]:
        """개별 타이밍 경로 파싱"""
        path = TimingPath(
            startpoint='',
            endpoint='',
            clock='',
            path_type='Setup',
        )
        
        # Startpoint 추출
        # 예: "Startpoint: cpu/pc_reg[0] (rising edge-triggered flip-flop clocked by sys_clk)"
        start_match = re.search(r'Startpoint:\s+(\S+)', section)
        if not start_match:
            return None
        path.startpoint = start_match.group(1)
        
        # Endpoint 추출
        end_match = re.search(r'Endpoint:\s+(\S+)', section)
        if end_match:
            path.endpoint = end_match.group(1)
        
        # Clock 추출
        clock_match = re.search(r'clocked by (\w+)', section)
        if clock_match:
            path.clock = clock_match.group(1)
        
        # Path Type 추출
        type_match = re.search(r'Path Type:\s+(\w+)', section)
        if type_match:
            path.path_type = type_match.group(1)
        
        # Slack 추출
        # 예: "slack (MET)                                         9.37"
        slack_match = re.search(r'slack.*?([-\d.]+)', section, re.IGNORECASE)
        if slack_match:
            path.slack = float(slack_match.group(1))
        
        # Arrival/Required time 추출
        arrival_match = re.search(r'data arrival time\s+([\d.]+)', section)
        if arrival_match:
            path.arrival_time = float(arrival_match.group(1))
        
        required_match = re.search(r'data required time\s+([\d.]+)', section)
        if required_match:
            path.required_time = float(required_match.group(1))
        
        # 타이밍 테이블 파싱
        # 형식:
        #   Point                                    Incr       Path
        #   --------------------------------------------------------
        #   cpu/pc_reg[0]/Q (DFFQX1)                 0.15       0.65 r
        #   cpu/decode_inst/U123/Y (AND2X1)          0.08       0.73 r
        
        table_pattern = r'Point\s+Incr\s+Path\s*\n\s*-+\s*\n(.*?)\n\s*data arrival time'
        table_match = re.search(table_pattern, section, re.DOTALL)
        
        if table_match:
            table_content = table_match.group(1)
            path.stages = self._parse_timing_table(table_content)
        
        return path
    
    def _parse_timing_table(self, table_content: str) -> List[TimingStage]:
        """타이밍 테이블 파싱"""
        stages = []
        lines = table_content.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('-'):
                continue
            
            stage = self._parse_timing_line(line)
            if stage:
                stages.append(stage)
        
        return stages
    
    def _parse_timing_line(self, line: str) -> Optional[TimingStage]:
        """타이밍 테이블의 한 줄 파싱"""
        # 여러 형식 지원:
        # 1. "cpu/pc_reg[0]/Q (DFFQX1)     0.15       0.65 r"
        # 2. "clock network delay (ideal)  0.50       0.50"
        # 3. "U123/Y (AND2X1)               0.08       0.73 r"
        
        # 패턴: 셀 이름, 증분 delay, 누적 delay, transition (옵션)
        pattern = r'^\s*(\S+(?:\s+\([^)]+\))?)\s+([-\d.]+)\s+([-\d.]+)\s*([rf])?'
        match = re.match(pattern, line)
        
        if not match:
            return None
        
        point = match.group(1)
        # 괄호 안의 셀 타입 제거
        point = re.sub(r'\s*\([^)]+\)', '', point).strip()
        
        incr = float(match.group(2))
        path = float(match.group(3))
        transition = match.group(4) or ''
        
        return TimingStage(
            point=point,
            incr_delay=incr,
            cumulative_delay=path,
            transition=transition,
        )
    
    def apply_to_graph(
        self,
        nodes: Dict[str, DKGNode],
        edges: Dict[str, DKGEdge],
        updater: GraphUpdater,
    ) -> None:
        """파싱한 타이밍 정보를 DKG 그래프에 반영"""
        from ..stages import FieldSource, ParsingStage
        
        for path in self.paths:
            # 1. Startpoint/Endpoint 노드 업데이트
            self._update_node_timing(
                path.startpoint, path, nodes, updater, is_endpoint=False
            )
            self._update_node_timing(
                path.endpoint, path, nodes, updater, is_endpoint=True
            )
            
            # 2. 경로상 각 엣지에 delay 설정
            for i in range(len(path.stages) - 1):
                src_stage = path.stages[i]
                dst_stage = path.stages[i + 1]
                
                self._update_edge_timing(
                    src_stage, dst_stage, path, edges, updater
                )
    
    def _update_node_timing(
        self,
        node_name: str,
        path: TimingPath,
        nodes: Dict[str, DKGNode],
        updater: GraphUpdater,
        is_endpoint: bool,
    ) -> None:
        """노드의 타이밍 정보 업데이트
        
        주의: 한 노드는 여러 경로에 나타날 수 있으므로:
        - slack은 최악값(worst-case)만 저장
        - 상세 정보는 메타데이터에 누적
        """
        from ..stages import FieldSource, ParsingStage
        
        # 노드 이름 정규화 (hier_path 또는 canonical_name 매칭)
        node = self._find_node_by_name(node_name, nodes)
        if not node:
            return
        
        node_id = node.node_id
        
        # Slack 업데이트 (startpoint에만, 최악값만)
        if not is_endpoint and path.slack is not None:
            # 기존 slack보다 나쁘면(작으면) 업데이트
            if node.slack is None or path.slack < node.slack:
                node.slack = path.slack
            
            # 메타데이터에는 경로별로 누적 저장 (리스트)
            metadata = updater.node_metadata[node_id]
            existing_slacks = metadata.get('timing_slacks', [])
            existing_slacks.append({
                'slack': path.slack,
                'path_type': path.path_type,
                'clock': path.clock,
                'endpoint': path.endpoint,
            })
            metadata.set(
                'timing_slacks',
                existing_slacks,
                FieldSource.ANALYZED,
                ParsingStage.TIMING,
            )
        
        # Arrival time - 여러 값 중 최악(최대)만 저장
        if path.arrival_time is not None:
            if node.arrival_time is None or path.arrival_time > node.arrival_time:
                node.arrival_time = path.arrival_time
        
        # Required time - 여러 값 중 최선(최소)만 저장
        if path.required_time is not None:
            if node.required_time is None or path.required_time < node.required_time:
                node.required_time = path.required_time
        
        # Clock domain - 여러 클럭이 있을 수 있으므로 대표값만 저장
        # (첫 번째로 발견된 클럭 or 가장 빈번한 클럭)
        if path.clock and not node.clock_domain:
            node.clock_domain = path.clock
    
    def _update_edge_timing(
        self,
        src_stage: TimingStage,
        dst_stage: TimingStage,
        path: TimingPath,
        edges: Dict[str, DKGEdge],
        updater: GraphUpdater,
    ) -> None:
        """엣지의 타이밍 정보 업데이트
        
        주의: 한 엣지도 여러 경로에 나타날 수 있으므로:
        - delay는 최악값만 저장 (일반적으로 동일해야 함)
        - 상세 정보는 메타데이터에 누적
        """
        from ..stages import FieldSource, ParsingStage
        
        # 엣지 찾기 (휴리스틱: src/dst 이름 기반)
        edge = self._find_edge_by_pins(src_stage.point, dst_stage.point, edges)
        if not edge:
            return
        
        edge_id = edge.edge_id
        
        # Delay 업데이트 - 최대값 저장 (보수적)
        if edge.delay is None or dst_stage.incr_delay > edge.delay:
            edge.delay = dst_stage.incr_delay
        
        # 메타데이터에 경로별 delay 누적
        metadata = updater.edge_metadata[edge_id]
        existing_delays = metadata.get('timing_delays', [])
        existing_delays.append({
            'delay': dst_stage.incr_delay,
            'path_type': path.path_type,
            'clock': path.clock,
        })
        metadata.set(
            'timing_delays',
            existing_delays,
            FieldSource.ANALYZED,
            ParsingStage.TIMING,
        )
        
        # Arrival time - 최대값만 저장
        if edge.arrival_time is None or dst_stage.cumulative_delay > edge.arrival_time:
            edge.arrival_time = dst_stage.cumulative_delay
        
        # Clock domain - 첫 번째 클럭 저장 (또는 가장 빈번한 클럭)
        if path.clock and not edge.clock_domain_id:
            edge.clock_domain_id = path.clock
    
    def _find_node_by_name(
        self, name: str, nodes: Dict[str, DKGNode]
    ) -> Optional[DKGNode]:
        """이름으로 노드 찾기 (휴리스틱)"""
        # 1. 직접 매칭
        if name in nodes:
            return nodes[name]
        
        # 2. hier_path로 매칭
        for node in nodes.values():
            if node.hier_path == name:
                return node
        
        # 3. canonical_name으로 매칭
        for node in nodes.values():
            if node.canonical_name == name:
                return node
        
        # 4. 부분 매칭 (마지막 시도)
        for node in nodes.values():
            if name in node.hier_path or node.hier_path in name:
                return node
        
        return None
    
    def _find_edge_by_pins(
        self, src_pin: str, dst_pin: str, edges: Dict[str, DKGEdge]
    ) -> Optional[DKGEdge]:
        """src/dst 핀 이름으로 엣지 찾기 (휴리스틱)"""
        # 타이밍 리포트의 핀 이름과 DKG 엣지의 노드 이름이 다를 수 있음
        # 예: "cpu/pc_reg[0]/Q" vs "cpu.pc_reg[0]"
        
        for edge in edges.values():
            src_node_name = edge.src_node
            dst_node_name = edge.dst_node
            
            # 부분 매칭 시도
            if (src_pin in src_node_name or src_node_name in src_pin) and \
               (dst_pin in dst_node_name or dst_node_name in dst_pin):
                return edge
        
        return None
    
    def get_summary(self) -> Dict:
        """파싱 결과 요약"""
        if not self.paths:
            return {'total_paths': 0}
        
        slacks = [p.slack for p in self.paths if p.slack is not None]
        worst_slack = min(slacks) if slacks else None
        met_count = sum(1 for s in slacks if s >= 0)
        
        return {
            'total_paths': len(self.paths),
            'worst_slack': worst_slack,
            'met_timing': met_count,
            'failed_timing': len(slacks) - met_count,
            'clocks': list(set(p.clock for p in self.paths if p.clock)),
        }
