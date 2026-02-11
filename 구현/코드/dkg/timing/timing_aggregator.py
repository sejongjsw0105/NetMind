"""
Timing Aggregator: DKG → SuperGraph Timing Metrics 집계

이 모듈은 DKG 노드/엣지의 raw timing 데이터를 집계하여
SuperNode/SuperEdge에 부착할 TimingNodeMetrics/TimingEdgeMetrics를 계산합니다.

원칙:
- 집계만 수행, 구조 변경 없음
- Immutable snapshot 생성
- 최악값(worst-case) 및 percentile 통계 계산
"""
from __future__ import annotations

from typing import Dict, List, Optional

from ..core.graph import DKGEdge, DKGNode, EdgeFlowType
from ..builders.supergraph import (
    SuperEdge,
    SuperGraph,
    SuperNode,
    TimingAlert,
    TimingAlertSeverity,
    TimingEdgeMetrics,
    TimingNodeMetrics,
    TimingSummary,
    attach_timing_analysis_to_superedge,
    attach_timing_analysis_to_supernode,
    get_timing_analysis_from_supernode,
)


def percentile(values: List[float], p: float) -> float:
    """
    백분위수 계산 (0 <= p <= 1)
    
    Args:
        values: 정렬되지 않은 값 리스트
        p: 백분위수 (0.05 = 5th percentile, 0.95 = 95th percentile)
    
    Returns:
        계산된 백분위수 값
    """
    if not values:
        return 0.0
    
    sorted_values = sorted(values)
    n = len(sorted_values)
    
    if n == 1:
        return sorted_values[0]
    
    # Linear interpolation between closest ranks
    rank = p * (n - 1)
    lower = int(rank)
    upper = min(lower + 1, n - 1)
    weight = rank - lower
    
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def compute_timing_node_metrics(
    supernode: SuperNode,
    nodes: Dict[str, DKGNode],
    clock_period: float = 10.0,  # 기본 클럭 주기 (ns)
    critical_threshold: float = 0.0,  # slack < 0이면 critical
    near_critical_alpha: float = 0.1,  # clock_period의 10% 이내면 near-critical
) -> Optional[TimingNodeMetrics]:
    """
    SuperNode의 member 노드들로부터 TimingNodeMetrics를 계산합니다.
    
    Args:
        supernode: 타이밍 메트릭을 계산할 SuperNode
        nodes: 전체 DKG 노드 딕셔너리
        clock_period: 클럭 주기 (ns)
        critical_threshold: critical 판정 임계값
        near_critical_alpha: near-critical 판정 배율
    
    Returns:
        TimingNodeMetrics 또는 None (타이밍 정보가 없는 경우)
    """
    # Member 노드들의 타이밍 정보 수집
    slack_values: List[float] = []
    arrival_times: List[float] = []
    required_times: List[float] = []
    
    for node_id in supernode.member_nodes:
        node = nodes.get(node_id)
        if not node:
            continue
        
        if node.slack is not None:
            slack_values.append(node.slack)
        
        if node.arrival_time is not None:
            arrival_times.append(node.arrival_time)
        
        if node.required_time is not None:
            required_times.append(node.required_time)
    
    # 타이밍 정보가 하나도 없으면 None 반환
    if not slack_values and not arrival_times and not required_times:
        return None
    
    # Slack 통계 계산
    min_slack = min(slack_values) if slack_values else 0.0
    p5_slack = percentile(slack_values, 0.05) if len(slack_values) >= 2 else min_slack
    
    # Arrival/Required Time 통계
    max_arrival_time = max(arrival_times) if arrival_times else 0.0
    min_required_time = min(required_times) if required_times else 0.0
    
    # Critical/Near-Critical 비율 계산
    total_nodes = len(slack_values)
    critical_count = sum(1 for s in slack_values if s < critical_threshold)
    near_critical_count = sum(
        1 for s in slack_values if s < near_critical_alpha * clock_period
    )
    
    critical_node_ratio = critical_count / total_nodes if total_nodes > 0 else 0.0
    near_critical_ratio = near_critical_count / total_nodes if total_nodes > 0 else 0.0
    
    # Timing Risk Score 계산 (단순 휴리스틱)
    # 음수 slack이 많을수록, slack이 작을수록 위험도 증가
    timing_risk_score = None
    if slack_values:
        # Risk = critical_ratio * 10 + (1 - normalized_min_slack) * 5
        normalized_min_slack = max(0, min(1, (min_slack + clock_period) / clock_period))
        timing_risk_score = (
            critical_node_ratio * 10.0 + (1 - normalized_min_slack) * 5.0
        )
    
    return TimingNodeMetrics(
        min_slack=min_slack,
        p5_slack=p5_slack,
        max_arrival_time=max_arrival_time,
        min_required_time=min_required_time,
        critical_node_ratio=critical_node_ratio,
        near_critical_ratio=near_critical_ratio,
        timing_risk_score=timing_risk_score,
    )


def compute_timing_edge_metrics(
    superedge: SuperEdge,
    edges: Dict[str, DKGEdge],
) -> Optional[TimingEdgeMetrics]:
    """
    SuperEdge의 member 엣지들로부터 TimingEdgeMetrics를 계산합니다.
    
    Args:
        superedge: 타이밍 메트릭을 계산할 SuperEdge
        edges: 전체 DKG 엣지 딕셔너리
    
    Returns:
        TimingEdgeMetrics 또는 None (타이밍 정보가 없는 경우)
    """
    # Member 엣지들의 타이밍 정보 수집
    delay_values: List[float] = []
    flow_type_counts: Dict[EdgeFlowType, int] = {}
    fanout_values: List[int] = []
    
    for edge_id in superedge.member_edges:
        edge = edges.get(edge_id)
        if not edge:
            continue
        
        if edge.delay is not None:
            delay_values.append(edge.delay)
        
        # Flow type 히스토그램
        flow_type_counts[edge.flow_type] = flow_type_counts.get(edge.flow_type, 0) + 1
        
        if edge.fanout_count is not None:
            fanout_values.append(edge.fanout_count)
    
    # 타이밍 정보가 하나도 없으면 None 반환
    if not delay_values and not flow_type_counts:
        return None
    
    # Delay 통계 계산
    max_delay = max(delay_values) if delay_values else 0.0
    p95_delay = percentile(delay_values, 0.95) if len(delay_values) >= 2 else max_delay
    
    # Fanout 통계 (선택적)
    fanout_max = max(fanout_values) if fanout_values else None
    fanout_p95 = (
        percentile([float(f) for f in fanout_values], 0.95)
        if len(fanout_values) >= 2
        else (float(fanout_max) if fanout_max is not None else None)
    )
    
    return TimingEdgeMetrics(
        max_delay=max_delay,
        p95_delay=p95_delay,
        flow_type_histogram=flow_type_counts,
        fanout_max=fanout_max,
        fanout_p95=fanout_p95,
    )


def aggregate_timing_to_supergraph(
    supergraph: SuperGraph,
    nodes: Dict[str, DKGNode],
    edges: Dict[str, DKGEdge],
    clock_period: float = 10.0,
    critical_threshold: float = 0.0,
    near_critical_alpha: float = 0.1,
) -> None:
    """
    SuperGraph의 모든 SuperNode/SuperEdge에 타이밍 메트릭을 집계하고 부착합니다.
    
    Args:
        supergraph: 타이밍 메트릭을 부착할 SuperGraph
        nodes: DKG 노드 딕셔너리
        edges: DKG 엣지 딕셔너리
        clock_period: 클럭 주기 (ns)
        critical_threshold: critical 판정 임계값
        near_critical_alpha: near-critical 판정 배율
    """
    # SuperNode에 타이밍 메트릭 부착
    for sn in supergraph.super_nodes.values():
        metrics = compute_timing_node_metrics(
            sn, nodes, clock_period, critical_threshold, near_critical_alpha
        )
        if metrics:
            attach_timing_analysis_to_supernode(sn, metrics)
    
    # SuperEdge에 타이밍 메트릭 부착
    for se in supergraph.super_edges.values():
        metrics = compute_timing_edge_metrics(se, edges)
        if metrics:
            attach_timing_analysis_to_superedge(se, metrics)


def compute_timing_summary(
    nodes: Dict[str, DKGNode],
    clock_period: float = 10.0,
    analysis_mode: str = "setup",
) -> TimingSummary:
    """
    전체 그래프의 Timing 요약 정보를 계산합니다.
    
    Args:
        nodes: DKG 노드 딕셔너리
        clock_period: 클럭 주기 (ns)
        analysis_mode: "setup" / "hold" / "both"
    
    Returns:
        TimingSummary 객체
    """
    from datetime import datetime
    
    slack_values = [n.slack for n in nodes.values() if n.slack is not None]
    
    worst_slack = min(slack_values) if slack_values else 0.0
    violation_count = sum(1 for s in slack_values if s < 0)
    near_critical_count = sum(1 for s in slack_values if 0 <= s < 0.1 * clock_period)
    
    return TimingSummary(
        worst_slack=worst_slack,
        violation_count=violation_count,
        near_critical_count=near_critical_count,
        clock_period=clock_period,
        analysis_mode=analysis_mode,
        timestamp=datetime.now().isoformat(),
    )


def generate_timing_alerts(
    supergraph: SuperGraph,
    nodes: Dict[str, DKGNode],
    critical_threshold: float = 0.0,
    warn_threshold: float = 0.5,
) -> List[TimingAlert]:
    """
    SuperGraph에서 타이밍 문제를 찾아 Alert를 생성합니다.
    
    Args:
        supergraph: 분석할 SuperGraph
        nodes: DKG 노드 딕셔너리
        critical_threshold: ERROR 레벨 임계값
        warn_threshold: WARN 레벨 임계값
    
    Returns:
        TimingAlert 리스트
    """
    alerts: List[TimingAlert] = []
    
    for sn in supergraph.super_nodes.values():
        metrics = get_timing_analysis_from_supernode(sn)
        if not metrics:
            continue
        
        # Slack violation 체크
        if metrics.min_slack < critical_threshold:
            alerts.append(
                TimingAlert(
                    entity_ref=sn.node_id,
                    entity_type="supernode",
                    severity=TimingAlertSeverity.ERROR,
                    reason=f"Timing violation: min_slack={metrics.min_slack:.3f}ns",
                    metrics_snapshot={
                        "min_slack": metrics.min_slack,
                        "p5_slack": metrics.p5_slack,
                        "max_arrival_time": metrics.max_arrival_time,
                    },
                )
            )
        elif metrics.min_slack < warn_threshold:
            alerts.append(
                TimingAlert(
                    entity_ref=sn.node_id,
                    entity_type="supernode",
                    severity=TimingAlertSeverity.WARN,
                    reason=f"Near-critical path: min_slack={metrics.min_slack:.3f}ns",
                    metrics_snapshot={
                        "min_slack": metrics.min_slack,
                        "critical_node_ratio": metrics.critical_node_ratio,
                    },
                )
            )
        
        # High timing risk 체크
        if metrics.timing_risk_score and metrics.timing_risk_score > 10.0:
            alerts.append(
                TimingAlert(
                    entity_ref=sn.node_id,
                    entity_type="supernode",
                    severity=TimingAlertSeverity.WARN,
                    reason=f"High timing risk: score={metrics.timing_risk_score:.2f}",
                    metrics_snapshot={
                        "timing_risk_score": metrics.timing_risk_score,
                        "critical_node_ratio": metrics.critical_node_ratio,
                        "near_critical_ratio": metrics.near_critical_ratio,
                    },
                )
            )
    
    return alerts
