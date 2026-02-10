# Analysis Attachment 구현 가이드

## 개요

본 문서는 DKG-Super 아키텍처에서 Timing 및 향후 Area/Power 분석을 SuperNode/SuperEdge에 부착하는 방법을 설명합니다.

## 핵심 설계 원칙

### 1. 구조 불변 원칙 (Structural Immutability)
- **Analysis는 그래프 구조를 변경하지 않습니다**
- SuperNode/SuperEdge의 생성 기준에 analysis 값이 개입하지 않습니다
- 구조 로직(`ViewBuilder`)은 analysis에 의존하지 않습니다

### 2. 집계 가능성 원칙 (Aggregability)
- Super 객체에 부착되는 정보는 **aggregation으로 정의 가능**해야 합니다
- 개별 path에 대한 단언(assertion)을 포함하지 않습니다

### 3. 단언 금지 원칙 (No Assertions)
SuperNode/SuperEdge는 다음을 **절대 표현하지 않습니다**:
- ❌ "critical path"
- ❌ "slack을 결정한다"
- ❌ path membership
- ✅ 집계된 통계 정보만 제공

## 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                    SuperNode / SuperEdge                │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Structural Core (불변)                             │ │
│  │  - node_id, super_class                           │ │
│  │  - member_nodes, member_edges                     │ │
│  └────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Analysis Bundle (가변, keyed)                      │ │
│  │  analysis["timing"]  -> TimingNodeMetrics         │ │
│  │  analysis["area"]    -> AreaMetrics    (향후)     │ │
│  │  analysis["power"]   -> PowerMetrics   (향후)     │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                           │
                           │ 참조만 (no coupling)
                           ▼
         ┌──────────────────────────────────────┐
         │  그래프 외부 Analysis 객체           │
         │  - TimingAlert                       │
         │  - TimingSummary                     │
         │  - CriticalPathDigest                │
         └──────────────────────────────────────┘
```

## 데이터 구조

### 1. TimingNodeMetrics (SuperNode용)

```python
@dataclass(frozen=True)
class TimingNodeMetrics:
    # 필수 Metrics
    min_slack: float              # 절대 최악값
    p5_slack: float               # tail risk 지표 (5th percentile)
    max_arrival_time: float       # 가장 늦은 도착 시간
    min_required_time: float      # 가장 타이트한 요구 시간
    critical_node_ratio: float    # slack < threshold 비율
    near_critical_ratio: float    # slack < α·clock 비율
    
    # 선택적 Metric
    timing_risk_score: Optional[float] = None  # UI/Alert용 단일 스칼라
```

**✅ 허용**: 집계 통계 (min, max, percentile, ratio)  
**❌ 금지**: "이 노드는 critical path에 속한다", path ID

### 2. TimingEdgeMetrics (SuperEdge용)

```python
@dataclass(frozen=True)
class TimingEdgeMetrics:
    # 필수 Metrics
    max_delay: float
    p95_delay: float              # 95th percentile delay
    flow_type_histogram: Dict[str, int]  # comb / seq 비율
    
    # 선택적 Metrics
    fanout_max: Optional[int] = None
    fanout_p95: Optional[float] = None
```

**✅ 허용**: 지연 통계, 구조 통계  
**❌ 금지**: "이 edge가 slack을 결정한다", critical edge 여부

### 3. 그래프 외부 객체 (필수 분리)

#### TimingAlert
```python
@dataclass
class TimingAlert:
    entity_ref: str               # node_id / supernode_id / edge_id
    entity_type: str              # "node" / "supernode" / "edge"
    severity: TimingAlertSeverity # INFO / WARN / ERROR
    reason: str
    metrics_snapshot: Dict[str, Any]
```

#### TimingSummary
```python
@dataclass
class TimingSummary:
    worst_slack: float
    violation_count: int
    near_critical_count: int
    clock_period: float
    analysis_mode: str            # "setup" / "hold" / "both"
    timestamp: Optional[str] = None
```

#### CriticalPathDigest (선택적)
```python
@dataclass
class CriticalPathDigest:
    path_id: str
    startpoint: str
    endpoint: str
    total_delay: float
    slack: float
    node_sequence: Optional[List[str]] = None  # 참조용
```

## 사용 방법

### 1. Timing Analysis 부착

```python
from dkg.supergraph import (
    SuperNode, 
    TimingNodeMetrics,
    attach_timing_analysis_to_supernode
)

# SuperNode 생성 (구조 로직)
supernode = SuperNode(
    node_id="SN_001",
    super_class=SuperClass.COMB_CLOUD,
    member_nodes={"n1", "n2", "n3"},
    member_edges=set()
)

# Timing Analysis 계산 (외부 분석 로직)
timing_metrics = TimingNodeMetrics(
    min_slack=-0.5,
    p5_slack=-0.3,
    max_arrival_time=10.2,
    min_required_time=9.7,
    critical_node_ratio=0.15,
    near_critical_ratio=0.30,
    timing_risk_score=0.85
)

# Analysis 부착 (결과 귀속)
attach_timing_analysis_to_supernode(supernode, timing_metrics)
```

### 2. Analysis 조회

```python
from dkg.supergraph import get_timing_analysis_from_supernode

# Timing 정보 조회
timing = get_timing_analysis_from_supernode(supernode)
if timing:
    print(f"Min Slack: {timing.min_slack}")
    print(f"Risk Score: {timing.timing_risk_score}")
```

### 3. 여러 Analysis 동시 사용 (향후)

```python
# Timing
supernode.analysis["timing"] = TimingNodeMetrics(...)

# Area (향후)
supernode.analysis["area"] = AreaMetrics(
    area_density=0.75,
    area_utilization=0.82,
    area_total=1024.5
)

# Power (향후)
supernode.analysis["power"] = PowerMetrics(
    power_peak=150.3,
    power_average=120.5,
    power_leakage=5.2
)
```

### 4. Alert 생성 (그래프 외부)

```python
from dkg.supergraph import TimingAlert, TimingAlertSeverity

# SuperNode의 timing 분석 결과를 기반으로 Alert 생성
timing = get_timing_analysis_from_supernode(supernode)
if timing and timing.min_slack < -0.1:
    alert = TimingAlert(
        entity_ref=supernode.node_id,
        entity_type="supernode",
        severity=TimingAlertSeverity.ERROR,
        reason=f"Negative slack detected: {timing.min_slack:.3f}ns",
        metrics_snapshot={
            "min_slack": timing.min_slack,
            "critical_ratio": timing.critical_node_ratio
        }
    )
    # Alert를 외부 시스템으로 전달
    alert_system.report(alert)
```

## 완료 기준 (Definition of Done)

- [x] SuperNode/SuperEdge가 `analysis: Dict[str, Any]` 필드를 가짐
- [x] TimingNodeMetrics, TimingEdgeMetrics 정의 완료
- [x] Analysis 부착/조회 헬퍼 함수 구현
- [x] 그래프 외부 객체 (TimingAlert, TimingSummary, CriticalPathDigest) 정의
- [x] 구조 로직이 analysis에 의존하지 않음 확인
- [x] 향후 확장(Area/Power) 패턴 문서화

## 핵심 요약

> **SuperNode / SuperEdge는 구조적 추상 객체이며,**  
> **Analysis는 그 위에 얹히는 계산 결과다.**  
> **Timing은 그 첫 번째 구현체일 뿐이다.**

## 금지 사항 체크리스트

구현 시 다음을 **절대** 하지 마십시오:

- ❌ SuperNode/SuperEdge 생성 시 timing 값을 기준으로 사용
- ❌ SuperNode에 "is_critical" 같은 boolean 플래그 추가
- ❌ SuperEdge에 "determines_slack" 같은 단언 추가
- ❌ Analysis 값이 그래프 구조에 영향을 미치도록 구현
- ❌ Path ID나 path membership을 Super 객체에 저장

## 허용 사항 체크리스트

다음은 **허용**됩니다:

- ✅ 집계 통계 (min, max, mean, percentile, ratio)
- ✅ 분포 정보 (histogram)
- ✅ 요약 스칼라 (risk_score 등)
- ✅ 외부 객체에서 Super 객체 참조 (entity_ref)
- ✅ 구조와 무관한 분석 로직

---

**작성일**: 2026-02-10  
**버전**: 1.0  
**상태**: 구현 완료
