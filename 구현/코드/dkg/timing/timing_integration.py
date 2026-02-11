"""
Timing Integration: 전체 Timing 분석 파이프라인 통합

이 모듈은 다음 단계들을 통합합니다:
1. Timing Report 파싱 → DKG 노드/엣지에 raw timing 저장
2. Constraint 파싱 → DKG 그래프에 제약 투영
3. SuperGraph 생성
4. Timing Metrics 집계 → SuperNode/SuperEdge에 부착
5. Timing Summary 및 Alert 생성

사용 예시:
    ```python
    from dkg.timing_integration import TimingAnalysisPipeline
    
    pipeline = TimingAnalysisPipeline(nodes, edges, updater)
    
    # 1. Timing Report 처리
    pipeline.process_timing_report("design.timing_rpt")
    
    # 2. 제약 파일 처리
    pipeline.process_constraint_file("design.sdc")
    
    # 3. SuperGraph에 Timing Metrics 부착
    supergraph = build_supergraph(...)
    pipeline.attach_timing_to_supergraph(supergraph, clock_period=10.0)
    
    # 4. Timing 결과 조회
    summary = pipeline.get_timing_summary()
    alerts = pipeline.get_timing_alerts(supergraph)
    ```
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from ..builders.constraint_projector import (
    ConstraintProjector,
    parse_sdc_create_clock,
    parse_sdc_false_path,
    parse_sdc_multicycle_path,
)
from ..core.graph import DKGEdge, DKGNode
from ..builders.graph_updater import GraphUpdater
from ..parsers.timing_report_parser import TimingReportParser
from ..builders.supergraph import SuperGraph, TimingAlert, TimingSummary
from .timing_aggregator import (
    aggregate_timing_to_supergraph,
    compute_timing_summary,
    generate_timing_alerts,
)


class TimingAnalysisPipeline:
    """
    Timing 분석의 전체 파이프라인을 관리하는 클래스.
    
    이 클래스는 timing report 파싱, constraint 투영, metrics 집계를
    순차적으로 처리합니다.
    """

    def __init__(
        self,
        nodes: Dict[str, DKGNode],
        edges: Dict[str, DKGEdge],
        updater: GraphUpdater,
    ):
        """
        Args:
            nodes: DKG 노드 딕셔너리
            edges: DKG 엣지 딕셔너리
            updater: GraphUpdater 인스턴스
        """
        self.nodes = nodes
        self.edges = edges
        self.updater = updater
        
        # Timing report parser
        self.timing_parser = TimingReportParser()
        
        # Constraint projector
        self.constraint_projector = ConstraintProjector(nodes, edges, updater)
        
        # 분석 결과 캐시
        self._timing_summary: Optional[TimingSummary] = None
        self._timing_alerts: List[TimingAlert] = []

    # ========================================================================
    # Step 1: Timing Report 처리
    # ========================================================================

    def process_timing_report(self, filepath: str | Path) -> None:
        """
        Timing Report 파일을 파싱하고 DKG 그래프에 반영합니다.
        
        이 함수는 다음을 수행합니다:
        1. Timing Report 파일 파싱 (Vivado/PrimeTime 형식)
        2. 각 노드의 slack, arrival_time, required_time 업데이트
        3. 각 엣지의 delay 업데이트
        
        Args:
            filepath: Timing Report 파일 경로
        """
        # 타이밍 리포트 파싱
        paths = self.timing_parser.parse_file(filepath)
        
        if not paths:
            print(f"Warning: No timing paths found in {filepath}")
            return
        
        print(f"Parsed {len(paths)} timing paths from {filepath}")
        
        # DKG 그래프에 타이밍 정보 반영
        self.timing_parser.apply_to_graph(self.nodes, self.edges, self.updater)
        
        print(f"Applied timing information to graph")

    # ========================================================================
    # Step 2: Constraint 파일 처리
    # ========================================================================

    def process_constraint_file(
        self, filepath: str | Path, file_type: str = "sdc"
    ) -> None:
        """
        Constraint 파일을 파싱하고 DKG 그래프에 투영합니다.
        
        지원 파일 타입:
        - "sdc": SDC (Synopsys Design Constraints)
        - "xdc": XDC (Xilinx Design Constraints)
        
        Args:
            filepath: Constraint 파일 경로
            file_type: 파일 타입 ("sdc" 또는 "xdc")
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            print(f"Warning: Constraint file not found: {filepath}")
            return
        
        if file_type == "sdc":
            self._process_sdc_file(filepath)
        elif file_type == "xdc":
            self._process_xdc_file(filepath)
        else:
            print(f"Warning: Unsupported constraint file type: {file_type}")

    def _process_sdc_file(self, filepath: Path) -> None:
        """SDC 파일을 파싱하고 제약을 투영합니다."""
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        constraint_count = 0
        
        for line_num, line in enumerate(lines, start=1):
            line = line.strip()
            
            # create_clock 처리
            if line.startswith("create_clock"):
                constraint = parse_sdc_create_clock(line)
                if constraint:
                    self.constraint_projector.project_clock_constraint(
                        constraint, str(filepath), line_num
                    )
                    constraint_count += 1
            
            # set_false_path 처리
            elif line.startswith("set_false_path"):
                constraint = parse_sdc_false_path(line)
                if constraint:
                    self.constraint_projector.project_false_path_constraint(
                        constraint, str(filepath), line_num
                    )
                    constraint_count += 1
            
            # set_multicycle_path 처리
            elif line.startswith("set_multicycle_path"):
                constraint = parse_sdc_multicycle_path(line)
                if constraint:
                    self.constraint_projector.project_multicycle_path_constraint(
                        constraint, str(filepath), line_num
                    )
                    constraint_count += 1
        
        print(f"Projected {constraint_count} constraints from {filepath}")

    def _process_xdc_file(self, filepath: Path) -> None:
        """XDC 파일을 파싱하고 제약을 투영합니다."""
        # XDC는 SDC와 유사하지만 Xilinx 특화 명령 포함
        # 여기서는 SDC와 같은 방식으로 처리
        self._process_sdc_file(filepath)

    # ========================================================================
    # Step 3: SuperGraph에 Timing Metrics 부착
    # ========================================================================

    def attach_timing_to_supergraph(
        self,
        supergraph: SuperGraph,
        clock_period: float = 10.0,
        critical_threshold: float = 0.0,
        near_critical_alpha: float = 0.1,
    ) -> None:
        """
        SuperGraph의 모든 SuperNode/SuperEdge에 타이밍 메트릭을 집계하고 부착합니다.
        
        이 함수는 DKG 노드/엣지에 저장된 raw timing 데이터를 집계하여
        SuperNode/SuperEdge에 TimingNodeMetrics/TimingEdgeMetrics를 생성하고 부착합니다.
        
        Args:
            supergraph: 타이밍 메트릭을 부착할 SuperGraph
            clock_period: 클럭 주기 (ns)
            critical_threshold: critical 판정 임계값 (slack < 0이면 critical)
            near_critical_alpha: near-critical 판정 배율 (clock_period의 10% 이내)
        """
        aggregate_timing_to_supergraph(
            supergraph,
            self.nodes,
            self.edges,
            clock_period,
            critical_threshold,
            near_critical_alpha,
        )
        
        print(f"Attached timing metrics to {len(supergraph.super_nodes)} supernodes and {len(supergraph.super_edges)} superedges")

    # ========================================================================
    # Step 4: Timing 결과 조회
    # ========================================================================

    def get_timing_summary(
        self, clock_period: float = 10.0, analysis_mode: str = "setup"
    ) -> TimingSummary:
        """
        전체 그래프의 Timing 요약 정보를 반환합니다.
        
        Args:
            clock_period: 클럭 주기 (ns)
            analysis_mode: "setup" / "hold" / "both"
        
        Returns:
            TimingSummary 객체
        """
        if self._timing_summary is None:
            self._timing_summary = compute_timing_summary(
                self.nodes, clock_period, analysis_mode
            )
        
        return self._timing_summary

    def get_timing_alerts(
        self,
        supergraph: SuperGraph,
        critical_threshold: float = 0.0,
        warn_threshold: float = 0.5,
    ) -> List[TimingAlert]:
        """
        SuperGraph에서 타이밍 문제를 찾아 Alert 리스트를 반환합니다.
        
        Args:
            supergraph: 분석할 SuperGraph
            critical_threshold: ERROR 레벨 임계값
            warn_threshold: WARN 레벨 임계값
        
        Returns:
            TimingAlert 리스트 (심각도 순 정렬)
        """
        self._timing_alerts = generate_timing_alerts(
            supergraph, self.nodes, critical_threshold, warn_threshold
        )
        
        # 심각도 순으로 정렬 (ERROR → WARN → INFO)
        severity_order = {"error": 0, "warn": 1, "info": 2}
        self._timing_alerts.sort(
            key=lambda a: (severity_order.get(a.severity.lower(), 3), a.entity_ref)
        )
        
        return self._timing_alerts

    def print_timing_report(
        self,
        supergraph: Optional[SuperGraph] = None,
        clock_period: float = 10.0,
        show_alerts: bool = True,
    ) -> None:
        """
        타이밍 분석 결과를 콘솔에 출력합니다.
        
        Args:
            supergraph: SuperGraph (Alert를 표시하려면 필요)
            clock_period: 클럭 주기 (ns)
            show_alerts: Alert를 표시할지 여부
        """
        print("\n" + "=" * 80)
        print("TIMING ANALYSIS REPORT")
        print("=" * 80)
        
        # Timing Summary
        summary = self.get_timing_summary(clock_period)
        print(f"\n[Timing Summary]")
        print(f"  Worst Slack:         {summary.worst_slack:.3f} ns")
        print(f"  Violation Count:     {summary.violation_count}")
        print(f"  Near-Critical Count: {summary.near_critical_count}")
        print(f"  Clock Period:        {summary.clock_period:.3f} ns")
        print(f"  Analysis Mode:       {summary.analysis_mode}")
        print(f"  Timestamp:           {summary.timestamp}")
        
        # Timing Alerts
        if show_alerts and supergraph:
            alerts = self.get_timing_alerts(supergraph)
            
            if alerts:
                print(f"\n[Timing Alerts] ({len(alerts)} issues found)")
                
                for i, alert in enumerate(alerts[:10], 1):  # 최대 10개만 표시
                    severity = alert.severity.upper()
                    print(f"\n  {i}. [{severity}] {alert.entity_type}: {alert.entity_ref}")
                    print(f"     Reason: {alert.reason}")
                
                if len(alerts) > 10:
                    print(f"\n  ... and {len(alerts) - 10} more alerts")
            else:
                print(f"\n[Timing Alerts] No issues found")
        
        print("\n" + "=" * 80 + "\n")


# ============================================================================
# Quick Start API
# ============================================================================


def quick_timing_analysis(
    nodes: Dict[str, DKGNode],
    edges: Dict[str, DKGEdge],
    updater: GraphUpdater,
    supergraph: SuperGraph,
    timing_report_path: Optional[str] = None,
    constraint_path: Optional[str] = None,
    clock_period: float = 10.0,
) -> TimingSummary:
    """
    타이밍 분석을 한 번에 수행하는 간편 API.
    
    사용 예시:
        ```python
        summary = quick_timing_analysis(
            nodes, edges, updater, supergraph,
            timing_report_path="design.timing_rpt",
            constraint_path="design.sdc",
            clock_period=10.0
        )
        ```
    
    Args:
        nodes: DKG 노드 딕셔너리
        edges: DKG 엣지 딕셔너리
        updater: GraphUpdater 인스턴스
        supergraph: SuperGraph
        timing_report_path: Timing Report 파일 경로 (옵션)
        constraint_path: Constraint 파일 경로 (옵션)
        clock_period: 클럭 주기 (ns)
    
    Returns:
        TimingSummary 객체
    """
    pipeline = TimingAnalysisPipeline(nodes, edges, updater)
    
    # 1. Timing Report 처리
    if timing_report_path:
        pipeline.process_timing_report(timing_report_path)
    
    # 2. Constraint 처리
    if constraint_path:
        file_type = "xdc" if constraint_path.endswith(".xdc") else "sdc"
        pipeline.process_constraint_file(constraint_path, file_type)
    
    # 3. SuperGraph에 Timing Metrics 부착
    pipeline.attach_timing_to_supergraph(supergraph, clock_period)
    
    # 4. 결과 출력
    pipeline.print_timing_report(supergraph, clock_period)
    
    return pipeline.get_timing_summary(clock_period)
