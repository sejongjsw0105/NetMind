"""
Constraint Projector: Raw Constraint → Graph Semantic Projection

이 모듈은 SDC/XDC/TCL 파서가 추출한 raw constraint를
DKG 그래프의 semantic으로 투영합니다.

처리하는 제약:
- Clock Domain: create_clock
- Timing Exceptions: set_false_path, set_multicycle_path
- Delay Constraints: set_max_delay, set_min_delay
- I/O Timing: set_input_delay, set_output_delay
- Physical Constraints: LOC, IOSTANDARD, pblock
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from ..core.graph import DKGEdge, DKGNode
from .graph_updater import GraphUpdater
from ..pipeline.stages import FieldSource, ParsingStage


# ============================================================================
# Raw Constraint Data Classes
# ============================================================================


@dataclass
class ClockConstraint:
    """create_clock 제약"""

    clock_name: str
    period: Optional[float] = None  # ns
    waveform: Optional[List[float]] = None  # [rise_edge, fall_edge]
    target_ports: Optional[List[str]] = None  # get_ports / get_pins


@dataclass
class FalsePathConstraint:
    """set_false_path 제약"""

    from_targets: Optional[List[str]] = None  # -from [get_pins ...]
    to_targets: Optional[List[str]] = None  # -to [get_pins ...]
    through_targets: Optional[List[str]] = None  # -through [get_pins ...]


@dataclass
class MulticyclePathConstraint:
    """set_multicycle_path 제약"""

    cycles: int
    path_type: str  # "setup" or "hold"
    from_targets: Optional[List[str]] = None
    to_targets: Optional[List[str]] = None


@dataclass
class DelayConstraint:
    """set_max_delay / set_min_delay 제약"""

    constraint_type: str  # "max" or "min"
    delay_value: float  # ns
    from_targets: Optional[List[str]] = None
    to_targets: Optional[List[str]] = None


@dataclass
class IOTimingConstraint:
    """set_input_delay / set_output_delay 제약"""

    constraint_type: str  # "input" or "output"
    delay_value: float  # ns
    clock_ref: Optional[str] = None
    target_ports: Optional[List[str]] = None


# ============================================================================
# Constraint Projector
# ============================================================================


class ConstraintProjector:
    """
    Constraint를 DKG 그래프에 투영하는 클래스.

    주요 기능:
    1. 제약의 target (get_ports, get_pins, get_cells)를 실제 노드/엣지에 매칭
    2. GraphUpdater를 통해 그래프 업데이트
    3. Provenance 기록
    """

    def __init__(
        self,
        nodes: Dict[str, DKGNode],
        edges: Dict[str, DKGEdge],
        updater: GraphUpdater,
    ):
        self.nodes = nodes
        self.edges = edges
        self.updater = updater

    # ========================================================================
    # Target Matching Utilities
    # ========================================================================

    def _match_node_by_pattern(self, pattern: str) -> List[str]:
        """
        패턴에 매칭되는 노드 ID 리스트를 반환합니다.

        패턴 예시:
        - "clk" → local_name이 'clk'인 노드
        - "cpu/pc_reg[0]" → hier_path가 매칭되는 노드
        - "*_reg*" → 와일드카드 매칭

        Returns:
            매칭된 node_id 리스트
        """
        matched_ids: List[str] = []

        # 간단한 와일드카드 → 정규식 변환
        regex_pattern = pattern.replace("*", ".*").replace("?", ".")
        regex = re.compile(regex_pattern, re.IGNORECASE)

        for node_id, node in self.nodes.items():
            # hier_path, local_name, canonical_name 모두 체크
            candidates = [node.hier_path, node.local_name]
            if node.canonical_name:
                candidates.append(node.canonical_name)

            if any(regex.fullmatch(c) for c in candidates):
                matched_ids.append(node_id)

        return matched_ids

    def _match_edge_by_endpoints(
        self, from_pattern: Optional[str], to_pattern: Optional[str]
    ) -> List[str]:
        """
        시작점과 끝점 패턴에 매칭되는 엣지 ID 리스트를 반환합니다.

        Args:
            from_pattern: 시작 노드 패턴 (None이면 모든 노드)
            to_pattern: 끝 노드 패턴 (None이면 모든 노드)

        Returns:
            매칭된 edge_id 리스트
        """
        matched_ids: List[str] = []

        # 패턴에 매칭되는 노드들 찾기
        from_nodes = (
            set(self._match_node_by_pattern(from_pattern)) if from_pattern else None
        )
        to_nodes = (
            set(self._match_node_by_pattern(to_pattern)) if to_pattern else None
        )

        for edge_id, edge in self.edges.items():
            # from_nodes가 지정되었으면 src_node가 매칭되어야 함
            if from_nodes is not None and edge.src_node not in from_nodes:
                continue

            # to_nodes가 지정되었으면 dst_node가 매칭되어야 함
            if to_nodes is not None and edge.dst_node not in to_nodes:
                continue

            matched_ids.append(edge_id)

        return matched_ids

    # ========================================================================
    # Clock Constraint Projection
    # ========================================================================

    def project_clock_constraint(
        self,
        constraint: ClockConstraint,
        filepath: str,
        line_num: int,
    ) -> None:
        """
        create_clock 제약을 그래프에 투영합니다.

        매칭되는 모든 노드의 clock_domain 필드를 업데이트합니다.
        """
        if not constraint.target_ports:
            return

        for port_pattern in constraint.target_ports:
            matched_nodes = self._match_node_by_pattern(port_pattern)

            for node_id in matched_nodes:
                self.updater.update_node_field(
                    node_id,
                    "clock_domain",
                    constraint.clock_name,
                    FieldSource.DECLARED,
                    ParsingStage.CONSTRAINTS,
                    filepath,
                    line_num,
                )

                # 클럭 주기도 attributes에 저장
                if constraint.period is not None:
                    node = self.nodes[node_id]
                    new_attrs = dict(node.attributes)
                    new_attrs["clock_period"] = str(constraint.period)
                    self.updater.update_node_field(
                        node_id,
                        "attributes",
                        new_attrs,
                        FieldSource.DECLARED,
                        ParsingStage.CONSTRAINTS,
                        filepath,
                        line_num,
                    )

    # ========================================================================
    # False Path Constraint Projection
    # ========================================================================

    def project_false_path_constraint(
        self,
        constraint: FalsePathConstraint,
        filepath: str,
        line_num: int,
    ) -> None:
        """
        set_false_path 제약을 그래프에 투영합니다.

        매칭되는 엣지의 timing_exception 필드를 'false_path'로 설정합니다.
        """
        # -from과 -to로 엣지 찾기
        from_pattern = constraint.from_targets[0] if constraint.from_targets else None
        to_pattern = constraint.to_targets[0] if constraint.to_targets else None

        matched_edges = self._match_edge_by_endpoints(from_pattern, to_pattern)

        for edge_id in matched_edges:
            self.updater.update_edge_field(
                edge_id,
                "timing_exception",
                "false_path",
                FieldSource.DECLARED,
                ParsingStage.CONSTRAINTS,
                filepath,
                line_num,
            )

    # ========================================================================
    # Multicycle Path Constraint Projection
    # ========================================================================

    def project_multicycle_path_constraint(
        self,
        constraint: MulticyclePathConstraint,
        filepath: str,
        line_num: int,
    ) -> None:
        """
        set_multicycle_path 제약을 그래프에 투영합니다.

        매칭되는 엣지의 timing_exception을 'multicycle_{N}_{type}'으로 설정합니다.
        예: 'multicycle_2_setup'
        """
        from_pattern = constraint.from_targets[0] if constraint.from_targets else None
        to_pattern = constraint.to_targets[0] if constraint.to_targets else None

        matched_edges = self._match_edge_by_endpoints(from_pattern, to_pattern)

        exception_value = f"multicycle_{constraint.cycles}_{constraint.path_type}"

        for edge_id in matched_edges:
            self.updater.update_edge_field(
                edge_id,
                "timing_exception",
                exception_value,
                FieldSource.DECLARED,
                ParsingStage.CONSTRAINTS,
                filepath,
                line_num,
            )

    # ========================================================================
    # Delay Constraint Projection
    # ========================================================================

    def project_delay_constraint(
        self,
        constraint: DelayConstraint,
        filepath: str,
        line_num: int,
    ) -> None:
        """
        set_max_delay / set_min_delay 제약을 그래프에 투영합니다.

        매칭되는 엣지의 parameters에 'max_delay' 또는 'min_delay'를 저장합니다.
        """
        from_pattern = constraint.from_targets[0] if constraint.from_targets else None
        to_pattern = constraint.to_targets[0] if constraint.to_targets else None

        matched_edges = self._match_edge_by_endpoints(from_pattern, to_pattern)

        param_key = f"{constraint.constraint_type}_delay"

        for edge_id in matched_edges:
            edge = self.edges[edge_id]
            new_params = dict(edge.parameters)
            new_params[param_key] = constraint.delay_value

            self.updater.update_edge_field(
                edge_id,
                "parameters",
                new_params,
                FieldSource.DECLARED,
                ParsingStage.CONSTRAINTS,
                filepath,
                line_num,
            )

    # ========================================================================
    # I/O Timing Constraint Projection
    # ========================================================================

    def project_io_timing_constraint(
        self,
        constraint: IOTimingConstraint,
        filepath: str,
        line_num: int,
    ) -> None:
        """
        set_input_delay / set_output_delay 제약을 그래프에 투영합니다.

        매칭되는 I/O 포트 노드의 attributes에 'input_delay' 또는 'output_delay'를 저장합니다.
        """
        if not constraint.target_ports:
            return

        attr_key = f"{constraint.constraint_type}_delay"

        for port_pattern in constraint.target_ports:
            matched_nodes = self._match_node_by_pattern(port_pattern)

            for node_id in matched_nodes:
                node = self.nodes[node_id]
                new_attrs = dict(node.attributes)
                new_attrs[attr_key] = str(constraint.delay_value)

                # 클럭 참조도 저장
                if constraint.clock_ref:
                    new_attrs[f"{constraint.constraint_type}_delay_clock"] = (
                        constraint.clock_ref
                    )

                self.updater.update_node_field(
                    node_id,
                    "attributes",
                    new_attrs,
                    FieldSource.DECLARED,
                    ParsingStage.CONSTRAINTS,
                    filepath,
                    line_num,
                )


# ============================================================================
# High-Level Projection API
# ============================================================================


def project_constraints_to_graph(
    constraints: List,  # ClockConstraint | FalsePathConstraint | ...
    nodes: Dict[str, DKGNode],
    edges: Dict[str, DKGEdge],
    updater: GraphUpdater,
    filepath: str,
    line_num: int = 0,
) -> None:
    """
    여러 제약조건을 한 번에 그래프에 투영합니다.

    Args:
        constraints: 제약조건 객체 리스트
        nodes: DKG 노드 딕셔너리
        edges: DKG 엣지 딕셔너리
        updater: GraphUpdater
        filepath: 제약 파일 경로
        line_num: 제약이 정의된 줄 번호
    """
    projector = ConstraintProjector(nodes, edges, updater)

    for constraint in constraints:
        if isinstance(constraint, ClockConstraint):
            projector.project_clock_constraint(constraint, filepath, line_num)
        elif isinstance(constraint, FalsePathConstraint):
            projector.project_false_path_constraint(constraint, filepath, line_num)
        elif isinstance(constraint, MulticyclePathConstraint):
            projector.project_multicycle_path_constraint(
                constraint, filepath, line_num
            )
        elif isinstance(constraint, DelayConstraint):
            projector.project_delay_constraint(constraint, filepath, line_num)
        elif isinstance(constraint, IOTimingConstraint):
            projector.project_io_timing_constraint(constraint, filepath, line_num)


# ============================================================================
# Parser Integration Helpers
# ============================================================================


def parse_sdc_create_clock(line: str) -> Optional[ClockConstraint]:
    """
    SDC의 create_clock 명령을 파싱하여 ClockConstraint를 반환합니다.

    예: create_clock -name clk -period 10 [get_ports clk]
    """
    match = re.search(r"-name\s+(\w+)", line)
    if not match:
        return None

    clock_name = match.group(1)

    # Period 추출
    period_match = re.search(r"-period\s+([\d.]+)", line)
    period = float(period_match.group(1)) if period_match else None

    # Target ports 추출
    port_match = re.search(r"get_ports\s+(\w+)", line)
    target_ports = [port_match.group(1)] if port_match else []

    return ClockConstraint(
        clock_name=clock_name, period=period, target_ports=target_ports
    )


def parse_sdc_false_path(line: str) -> Optional[FalsePathConstraint]:
    """
    SDC의 set_false_path 명령을 파싱하여 FalsePathConstraint를 반환합니다.

    예: set_false_path -from [get_pins cpu/reset_reg/Q] -to [get_pins *]
    """
    from_match = re.search(r"-from\s+\[get_\w+\s+([^\]]+)\]", line)
    to_match = re.search(r"-to\s+\[get_\w+\s+([^\]]+)\]", line)

    from_targets = [from_match.group(1)] if from_match else None
    to_targets = [to_match.group(1)] if to_match else None

    if not from_targets and not to_targets:
        return None

    return FalsePathConstraint(from_targets=from_targets, to_targets=to_targets)


def parse_sdc_multicycle_path(line: str) -> Optional[MulticyclePathConstraint]:
    """
    SDC의 set_multicycle_path 명령을 파싱하여 MulticyclePathConstraint를 반환합니다.

    예: set_multicycle_path 2 -setup -from [get_pins src] -to [get_pins dst]
    """
    cycles_match = re.search(r"set_multicycle_path\s+(\d+)", line)
    if not cycles_match:
        return None

    cycles = int(cycles_match.group(1))
    path_type = "setup" if "-setup" in line else "hold" if "-hold" in line else "setup"

    from_match = re.search(r"-from\s+\[get_\w+\s+([^\]]+)\]", line)
    to_match = re.search(r"-to\s+\[get_\w+\s+([^\]]+)\]", line)

    from_targets = [from_match.group(1)] if from_match else None
    to_targets = [to_match.group(1)] if to_match else None

    return MulticyclePathConstraint(
        cycles=cycles,
        path_type=path_type,
        from_targets=from_targets,
        to_targets=to_targets,
    )
