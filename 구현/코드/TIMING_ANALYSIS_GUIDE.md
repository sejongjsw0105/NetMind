# Timing Analysis Integration Guide

## 개요

이 가이드는 DKG 시스템에서 Timing 분석을 수행하는 방법을 설명합니다.

Timing 분석은 다음 단계로 구성됩니다:

1. **Timing Report 파싱**: Vivado/PrimeTime의 타이밍 리포트를 파싱하여 raw timing 데이터 추출
2. **Constraint 투영**: SDC/XDC 제약조건을 그래프 semantic으로 투영
3. **SuperGraph 생성**: DKG를 추상화하여 SuperGraph 생성
4. **Metrics 집계**: SuperNode/SuperEdge에 TimingMetrics 부착
5. **결과 조회**: Timing Summary, Alert 생성 및 출력

---

## 새로 추가된 모듈

### 1. `timing_aggregator.py`

DKG 노드/엣지의 raw timing 데이터를 집계하여 SuperNode/SuperEdge용 TimingMetrics를 계산합니다.

**주요 함수:**
- `compute_timing_node_metrics()`: SuperNode의 TimingNodeMetrics 계산
- `compute_timing_edge_metrics()`: SuperEdge의 TimingEdgeMetrics 계산
- `aggregate_timing_to_supergraph()`: SuperGraph 전체에 metrics 부착
- `compute_timing_summary()`: 전체 Timing 요약 정보 생성
- `generate_timing_alerts()`: Timing 문제 검출 및 Alert 생성

**Metrics 계산 원칙:**
- 최악값(worst-case) 및 percentile 통계 사용
- Critical/Near-Critical 비율 계산
- Timing Risk Score 제공 (UI/Alert용 단일 스칼라)
- Immutable snapshot 생성

### 2. `constraint_projector.py`

SDC/XDC 제약조건을 DKG 그래프에 투영합니다.

**지원 제약 타입:**
- `ClockConstraint`: create_clock (클럭 도메인 설정)
- `FalsePathConstraint`: set_false_path (타이밍 체크 제외)
- `MulticyclePathConstraint`: set_multicycle_path (멀티사이클 경로)
- `DelayConstraint`: set_max_delay / set_min_delay
- `IOTimingConstraint`: set_input_delay / set_output_delay

**주요 클래스:**
- `ConstraintProjector`: 제약을 그래프에 투영하는 핵심 클래스
  - `_match_node_by_pattern()`: 패턴 매칭으로 노드 찾기
  - `_match_edge_by_endpoints()`: 시작/끝 노드로 엣지 찾기
  - `project_*_constraint()`: 각 제약 타입별 투영 함수

**투영 원칙:**
- 제약의 target (get_ports, get_pins, get_cells)을 실제 노드/엣지에 매칭
- GraphUpdater를 통한 안전한 그래프 업데이트
- Provenance 자동 기록

### 3. `timing_integration.py`

전체 Timing 분석 파이프라인을 통합하는 High-Level API를 제공합니다.

**주요 클래스:**
- `TimingAnalysisPipeline`: 전체 파이프라인 관리
  - `process_timing_report()`: Timing Report 파싱 및 적용
  - `process_constraint_file()`: Constraint 파일 처리
  - `attach_timing_to_supergraph()`: SuperGraph에 metrics 부착
  - `get_timing_summary()`: Timing 요약 조회
  - `get_timing_alerts()`: Alert 리스트 조회
  - `print_timing_report()`: 결과 출력

**Quick Start API:**
- `quick_timing_analysis()`: 모든 단계를 한 번에 수행

---

## 사용 예제

### 기본 사용법

```python
from dkg.timing_integration import TimingAnalysisPipeline
from dkg.graph import DKGNode, DKGEdge
from dkg.graph_updater import GraphUpdater
from dkg.supergraph import ViewBuilder, GraphViewType

# 1. DKG 그래프 준비
nodes = {...}  # DKGNode 딕셔너리
edges = {...}  # DKGEdge 딕셔너리
updater = GraphUpdater()

# 2. Pipeline 생성
pipeline = TimingAnalysisPipeline(nodes, edges, updater)

# 3. Timing Report 처리
pipeline.process_timing_report("design.timing_rpt")

# 4. Constraint 처리
pipeline.process_constraint_file("design.sdc", file_type="sdc")

# 5. SuperGraph 생성
view_builder = ViewBuilder(nodes, edges, GraphViewType.Connectivity)
supergraph = view_builder.build()

# 6. Timing Metrics 부착
pipeline.attach_timing_to_supergraph(supergraph, clock_period=10.0)

# 7. 결과 출력
pipeline.print_timing_report(supergraph, clock_period=10.0)

# 8. 결과 조회
summary = pipeline.get_timing_summary()
alerts = pipeline.get_timing_alerts(supergraph)
```

### Quick API 사용법

```python
from dkg.timing_integration import quick_timing_analysis

summary = quick_timing_analysis(
    nodes, edges, updater, supergraph,
    timing_report_path="design.timing_rpt",
    constraint_path="design.sdc",
    clock_period=10.0
)

print(f"Worst Slack: {summary.worst_slack:.3f} ns")
print(f"Violations: {summary.violation_count}")
```

### 개별 모듈 사용

#### Timing Metrics 집계만 수행

```python
from dkg.timing_aggregator import aggregate_timing_to_supergraph

aggregate_timing_to_supergraph(
    supergraph, nodes, edges,
    clock_period=10.0,
    critical_threshold=0.0,
    near_critical_alpha=0.1
)
```

#### Constraint 투영만 수행

```python
from dkg.constraint_projector import (
    ConstraintProjector,
    ClockConstraint,
    FalsePathConstraint
)

projector = ConstraintProjector(nodes, edges, updater)

# Clock 제약
clock = ClockConstraint(
    clock_name="sys_clk",
    period=10.0,
    target_ports=["clk"]
)
projector.project_clock_constraint(clock, "design.sdc", 1)

# False Path 제약
false_path = FalsePathConstraint(
    from_targets=["reset_reg"],
    to_targets=["*"]
)
projector.project_false_path_constraint(false_path, "design.sdc", 5)
```

#### Timing Metrics 조회

```python
from dkg.supergraph import (
    get_timing_analysis_from_supernode,
    get_timing_analysis_from_superedge
)

# SuperNode의 timing metrics 조회
for sn in supergraph.super_nodes.values():
    metrics = get_timing_analysis_from_supernode(sn)
    if metrics:
        print(f"Min Slack: {metrics.min_slack:.3f} ns")
        print(f"Critical Ratio: {metrics.critical_node_ratio:.2%}")
        print(f"Risk Score: {metrics.timing_risk_score:.2f}")

# SuperEdge의 timing metrics 조회
for se in supergraph.super_edges.values():
    metrics = get_timing_analysis_from_superedge(se)
    if metrics:
        print(f"Max Delay: {metrics.max_delay:.3f} ns")
        print(f"P95 Delay: {metrics.p95_delay:.3f} ns")
```

---

## Timing Metrics 상세

### TimingNodeMetrics

SuperNode에 부착되는 타이밍 메트릭입니다.

```python
@dataclass(frozen=True)
class TimingNodeMetrics:
    min_slack: float              # 절대 최악값
    p5_slack: float               # 5th percentile slack
    max_arrival_time: float       # 가장 늦은 도착 시간
    min_required_time: float      # 가장 타이트한 요구 시간
    critical_node_ratio: float    # slack < 0 비율
    near_critical_ratio: float    # slack < 0.1*clock 비율
    timing_risk_score: Optional[float]  # 단일 위험도 지표
```

### TimingEdgeMetrics

SuperEdge에 부착되는 타이밍 메트릭입니다.

```python
@dataclass(frozen=True)
class TimingEdgeMetrics:
    max_delay: float                           # 최대 지연
    p95_delay: float                           # 95th percentile delay
    flow_type_histogram: Dict[EdgeFlowType, int]  # Flow type 분포
    fanout_max: Optional[int]                  # 최대 fanout
    fanout_p95: Optional[float]                # 95th percentile fanout
```

### TimingSummary

전체 그래프의 타이밍 요약 정보입니다.

```python
@dataclass
class TimingSummary:
    worst_slack: float           # 전체 최악 slack
    violation_count: int         # Violation 개수
    near_critical_count: int     # Near-critical 개수
    clock_period: float          # 클럭 주기
    analysis_mode: str           # "setup" / "hold" / "both"
    timestamp: Optional[str]     # 분석 시각
```

### TimingAlert

타이밍 문제를 나타내는 Alert입니다.

```python
@dataclass
class TimingAlert:
    entity_ref: str                      # 문제가 있는 entity ID
    entity_type: str                     # "node" / "supernode" / "edge"
    severity: TimingAlertSeverity        # "error" / "warn" / "info"
    reason: str                          # 문제 설명
    metrics_snapshot: Dict[str, Any]     # 발견 시점의 메트릭 스냅샷
```

---

## 설계 원칙

### 1. 구조와 분석의 분리

- **SuperNode/SuperEdge**: 그래프 구조만 담당
- **TimingMetrics**: Analysis attachment로 부착 (keyed bundle)
- **TimingAlert/Summary**: 그래프 외부 객체로 관리

### 2. Immutable Snapshot

- TimingMetrics는 frozen dataclass (불변)
- 각 분석 결과는 독립적인 snapshot
- 재분석 시 전체 교체 (부분 수정 금지)

### 3. Aggregation Only

- Timing Aggregator는 집계만 수행
- 그래프 구조 변경 없음
- Raw data는 DKG 노드/엣지에 보존

### 4. Semantic Projection

- Constraint는 그래프 semantic으로 투영
- Pattern matching으로 target 해결
- GraphUpdater를 통한 안전한 업데이트
- Provenance 자동 기록

---

## 향후 확장

현재 Timing 분석이 구현되었으며, 동일한 패턴으로 Area/Power 분석을 확장할 수 있습니다:

```python
@dataclass(frozen=True)
class AreaMetrics:
    area_density: float
    area_utilization: float
    area_total: float

@dataclass(frozen=True)
class PowerMetrics:
    power_peak: float
    power_average: float
    power_leakage: float

def attach_area_analysis_to_supernode(sn: SuperNode, metrics: AreaMetrics):
    sn.analysis[AnalysisKind.AREA] = metrics

def attach_power_analysis_to_supernode(sn: SuperNode, metrics: PowerMetrics):
    sn.analysis[AnalysisKind.POWER] = metrics
```

사용 예시:
```python
supernode.analysis[AnalysisKind.TIMING]  # TimingNodeMetrics
supernode.analysis[AnalysisKind.AREA]    # AreaMetrics
supernode.analysis[AnalysisKind.POWER]   # PowerMetrics
```

---

## 참고 파일

- `timing_aggregator.py`: Metrics 집계 로직
- `constraint_projector.py`: Constraint 투영 로직
- `timing_integration.py`: 통합 파이프라인
- `timing_analysis_example.py`: 사용 예제
- `supergraph.py`: TimingMetrics 데이터 클래스 정의
- `parsers/timing_report_parser.py`: Timing Report 파싱
- `parsers/sdc_parser.py`: SDC 제약 파싱
- `parsers/xdc_parser.py`: XDC 제약 파싱

---

## 문의 및 이슈

Timing 분석 관련 문의나 이슈는 프로젝트 리포지토리에 등록하세요.
