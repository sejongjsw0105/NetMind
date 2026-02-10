# FPGA AI 개발 도구 - 시스템 아키텍처

## 1. Design Knowledge Graph (DKG) 개요

### 1.1 DKG란?
전체 FPGA 프로젝트를 **하나의 통합된 지식 그래프**로 표현하는 데이터 구조

**핵심 개념**:
- **단일 진실 공급원**: 모든 설계 정보가 그래프에 존재
- **다중 뷰 지원**: 같은 그래프를 다양한 관점에서 시각화
- **점진적 구축**: 여러 소스에서 정보를 단계적으로 추가

### 1.2 DKG의 구성 요소
```
DKG
├── Nodes (노드): 설계 엔티티 (모듈, 신호, 핀, 제약 등)
├── Edges (엣지): 엔티티 간 관계 (연결, 종속성, 제약)
└── Metadata (메타데이터): 각 노드/엣지의 출처 및 신뢰도 정보
```

## 2. 다중 뷰 (Multiple Graph Views)

하나의 DKG를 **다양한 렌즈**로 바라보는 방식

### 2.1 View 종류

#### Structural View (구조 뷰)
- **목적**: 모듈 계층 구조 파악
- **노드**: Module Instance, RTL Block
- **엣지**: 인스턴스화 관계, 신호 연결
- **사용 사례**: 전체 설계 구조 이해

#### Physical View (물리 뷰)
- **목적**: 보드/패키지와의 연결
- **노드**: IO Port, Package Pin, Pblock, Board Connector
- **엣지**: 물리적 연결
- **사용 사례**: 핀 배치, 보드 디버깅

#### Timing View (타이밍 뷰)
- **목적**: 크리티컬 패스 분석
- **노드**: Flip-Flop, LUT (delay/slack 강조)
- **엣지**: Timing path (delay 정보 포함)
- **사용 사례**: 타이밍 최적화

#### Connectivity View (연결성 뷰)
- **목적**: 특정 신호의 흐름 추적
- **노드**: 신호를 사용/생성하는 모듈
- **엣지**: 신호 전달 경로
- **사용 사례**: 신호 디버깅, 백트레이싱

### 2.2 View 전환 메커니즘
```python
dkg = DesignKnowledgeGraph()

# 같은 DKG, 다른 뷰
structural_view = dkg.get_view("structural")
timing_view = dkg.get_view("timing")

# 뷰마다 다른 노드/엣지 필터링
structural_view.show_only(["Module", "RTL Block"])
timing_view.highlight_critical_paths(slack_threshold=-0.5)
```

## 3. Node 설계

### 3.1 Node Supertype: Entity Class

노드를 **4가지 상위 클래스**로 분류:

#### 1. Logical Entities (논리 엔티티)
**설계 의도**를 나타내는 구조
- `Module Instance`: RTL 모듈 인스턴스
- `RTL Block`: 조합 논리/순차 논리 블록
- `FSM`: 상태 머신 (향후 확장)

#### 2. Structural Primitives (구조 프리미티브)
합성 후 나타나는 **하드웨어 기본 단위** (SubEntity)
- `Flip-Flop`: D-FF, 레지스터
- `LUT`: Look-Up Table
- `MUX`: 멀티플렉서
- `DSP Block`: 곱셈기/덧셈기
- `BRAM`: Block RAM

**특징**:
- Structural View에서는 작게 표시 (또는 엣지처럼 렌더링)
- 여러 모듈이 공유하는 레지스터 등을 독립 노드로 표현

#### 3. Physical/Constraint Entities (물리/제약 엔티티)
구현 환경과 연결된 객체
- `IO Port`: 모듈의 입출력 포트
- `Package Pin`: FPGA 패키지 핀
- `Pblock`: 물리적 배치 영역
- `Board Connector`: 보드 커넥터

#### 4. Abstract Control Entities (추상 제어 엔티티)
**향후 확장**: 클럭 도메인, 리셋 도메인 등
- 묶음 기준: 같은 Clock/Reset Signal을 공유하는 노드들

### 3.2 Node 데이터 구조

```python
class Node:
    # 필수 필드
    path: str                    # 계층 경로 (예: "top/u_cpu/u_alu")
    entity_class: EntityClass    # Logical/Structural/Physical/Abstract
    entity_type: EntityType      # ModuleInstance/FlipFlop/IOPort 등
    name: str                    # 노드 이름
    
    # 관계 필드
    sub_nodes: List[Node]        # 소유한 하위 노드
    output_signals: List[Signal] # 발행/갱신하는 신호
    input_signals: List[Signal]  # 받는 신호
    
    # 제어 신호
    clock_signal: Optional[Signal]
    reset_signal: Optional[Signal]
```

**Path 규칙**:
- **Path는 소유/인스턴스화 관계만 표현**
- 신호 공유나 전달은 Edge로 표현 (Path에 포함 X)

### 3.3 Entity별 추가 필드

#### Structural Primitives
```python
class FlipFlop(Node):
    value: Any           # 현재 값
    bit_width: int       # 비트 수
```

#### Physical Entities
```python
class IOPort(Node):
    direction: str       # "input" / "output" / "inout"
    pin_number: str      # 패키지 핀 번호
```

#### Abstract Control Entities
```python
class ClockDomain(Node):
    grouped_by: Signal   # 묶음 기준 (Clock Signal 주소)
```

## 4. Edge 설계

### 4.1 Edge 타입 (Relation Types)

| 타입 | 의미 | 예시 |
|------|------|------|
| Data Relation | 일반 신호 연결 | `data_out → data_in` |
| Clock Relation | 클럭 연결 | `clk → module.clk` |
| Reset Relation | 리셋 연결 | `rst_n → ff.reset` |
| Parameter Relation | 파라미터 영향 | `WIDTH → module` |
| Constraint Relation | 타이밍 예외 | `false_path, multicycle` |
| Physical Mapping | 논리-물리 매핑 | `port ↔ pin` |

### 4.2 Edge 데이터 구조

```python
class Edge:
    # 식별자
    edge_key: str                    # 고유 키
    signal_name: str                 # 신호 이름
    source_hier_path: str            # 시작 노드 경로
    
    # 신호 속성
    bit_range: Optional[str]         # 버스일 때 [31:0] 중 어떤 비트
    
    # Edge 타입
    edge_type: EdgeType              # Data/Clock/Reset/...
    
    # Flow 타입
    edge_flow_type: EdgeFlowType     # combinational/sequential_launch/...
    
    # 타이밍 정보 (Timing View용)
    delay: Optional[float]           # 딜레이
    slack: Optional[float]           # 슬랙
```

### 4.3 Edge Flow Type

```python
class EdgeFlowType(Enum):
    COMBINATIONAL       # 조합 논리 경로
    SEQUENTIAL_LAUNCH   # FF 출력 → 조합 논리
    SEQUENTIAL_CAPTURE  # 조합 논리 → FF 입력
    CLOCK_TREE          # 클럭 분배
    ASYNC_RESET         # 비동기 리셋
```

**사용 사례**:
- Timing View에서 경로 유형별 색상 구분
- AI에게 "이 경로는 순차 경로입니다" 정보 전달

## 5. 다층 계층 설계

DKG는 **3개 레이어**로 구성:

### Layer 1: NetList
```python
# Yosys JSON을 거의 그대로 파이썬 클래스로 변환
class NetListNode:
    raw_json: dict       # 원본 JSON
    parsed_data: dict    # 파싱된 데이터
```

**역할**: 원시 데이터 저장, 파싱 결과 보존

### Layer 2: Logic Graph
```python
# 모든 노드/엣지를 완전히 구현
class LogicGraph:
    all_nodes: Dict[str, Node]
    all_edges: List[Edge]
```

**역할**: 완전한 설계 정보, 모든 뷰의 기반

### Layer 3: View Graph
```python
# SuperNode와 SuperEdge로 통합하여 특정 뷰에 맞게 표시
class ViewGraph:
    visible_nodes: List[SuperNode]    # 여러 노드를 묶은 SuperNode
    visible_edges: List[SuperEdge]    # 여러 엣지를 묶은 SuperEdge
```
MERGE operation represents an abstraction that preserves signal-level connectivity
while intentionally discarding internal structural boundaries that are not relevant
to the selected View.

**역할**: 
- UI에 표시할 그래프 생성
- 계층 축소/확장 지원
- 성능 최적화 (렌더링 노드 수 감소)

## 6. 계층적 UX 설계

### 6.1 동일 이름 신호 처리

**문제**: 여러 모듈에 같은 이름의 신호가 존재
```
top.u1.data_valid
top.u2.data_valid
top.u3.data_valid
```

**해결책**:
- **내부**: Hierarchical full name 저장
- **UI**: `data_valid (in u1)` 형식으로 표시

### 6.2 Hop 기반 펼치기

대규모 프로젝트는 노드가 너무 많으므로:

**방법 1: TOP에서 일괄 펼치기**
```
UI 설정: "TOP에서 2-hop까지 보기"
→ top/u1/*, top/u2/* 까지만 표시
```

**방법 2: 노드 클릭해서 하위 펼치기**
```
사용자: u_cpu 노드 클릭
→ "하위 몇 hop까지?" 선택
→ u_cpu/u_alu, u_cpu/u_regs 표시
```

### 6.3 선택적 표시

**자식 N개 중 상위 K개만 표시**:
```
u_cpu 하위에 100개 모듈
→ 중요도 상위 10개만 표시
→ 나머지 90개는 "collapsed node" (+90 more...)
```

**필터링**:
- 원하는 Entity Class만 보기 (예: Logical만)
- 특정 신호 타입만 보기 (예: Clock만)

### 6.4 캐싱

**전략**:
- 한 번 펼친 hop 영역은 메모리 캐싱
- 같은 모듈 재방문 시 빠른 로딩
- 세션 간 영속화 (선택 사항)

## 7. Netlist View 설계

### 7.1 이중 그래프 구조

**상위 그래프**: 모듈 인스턴스 단위
- 노드: Module Instance
- 엣지: 모듈 간 신호 연결

**내부 그래프**: 넷리스트 (셀/넷 단위)
- 노드: FF, LUT, MUX 등
- 엣지: 넷(net) 연결

### 7.2 UI 설계

**원칙**: 두 그래프를 같은 화면에 섞지 않음

**방법**:
```
[상위 그래프 메인 뷰]
  ├── 모듈 u_cpu 클릭
  └── [하단/우측 패널] "Local Netlist View" 열림
       └── u_cpu 내부 FF, LUT 표시
```

**대안**: 모듈 클릭 시 전체 화면을 내부 넷리스트로 전환

### 7.3 입출력 경계 표시

**모듈의 Input/Output**:
- 서로 다른 색상 (예: 파란색 = input, 빨간색 = output)
- 엣지로 표현 (포트는 엣지처럼 렌더링 가능)
- 클릭 시 정보 패널 표시

**공유 레지스터**:
- 모듈 간 2회 이상 공유되는 reg/FF
- 별도 노드로 분리하여 표시

## 8. 파싱 파이프라인

### 8.1 Multi-Stage Parsing

DKG는 **점진적으로** 정보를 수집:

```
Stage 1: RTL         → Yosys JSON (구조 정보)
Stage 2: SYNTHESIS   → 합성 netlist
Stage 3: CONSTRAINTS → SDC/XDC (클럭, 타이밍 예외)
Stage 4: FLOORPLAN   → Pblock (물리 배치)
Stage 5: TIMING      → 타이밍 리포트 (delay, slack)
Stage 6: BOARD       → BD file (보드 연결)
```

### 8.2 필드 출처 우선순위 (Field Source Priority)

각 필드는 **신뢰도**가 다름:

```
1. INFERRED         (추론)        - 이름 패턴으로 추측
2. ANALYZED         (분석)        - 도구 분석 결과
3. DECLARED         (명시)        - 파일에서 명시적 선언
4. USER_OVERRIDE    (사용자)      - 사용자 직접 설정
```

**업데이트 규칙**: 우선순위가 같거나 높은 경우에만 덮어쓰기

### 8.3 예시: Clock Domain 업데이트

**Stage 1 (RTL)**:
```python
# "clk" 패턴 감지로 추론
node.clock_domain = "clk"
metadata.source = FieldSource.INFERRED
```

**Stage 3 (Constraints)**:
```tcl
# SDC에서 명시적 선언
create_clock -name sys_clk -period 10 [get_ports clk]
```
```python
# DECLARED가 INFERRED보다 우선순위 높음 → 업데이트
node.clock_domain = "sys_clk"
metadata.source = FieldSource.DECLARED
```

**Stage 3 (User)**:
```python
# 사용자가 GUI에서 수정
node.clock_domain = "my_custom_clk"
metadata.source = FieldSource.USER_OVERRIDE
# USER_OVERRIDE가 최우선 → 이후 파싱으로도 변경 X
```

### 8.4 파싱 단계별 담당

| Stage | 파서 | 추가 정보 |
|-------|------|----------|
| RTL | Yosys | 구조, 추론된 clock/reset |
| SYNTHESIS | Yosys/Vivado | 최종 구조, 프리미티브 |
| CONSTRAINTS | SDC/XDC Parser | 명시적 clock, timing exception |
| FLOORPLAN | TCL Parser | Pblock 배치 |
| TIMING | Report Parser | delay, slack |
| BOARD | BD Parser | 보드 연결 |

## 9. 타이밍/딜레이 정보

### 9.1 타이밍 리포트 파싱

**입력**: Vivado `report_timing` 결과 (.rpt)

**추출 정보**:
- Path 상의 각 노드/엣지에 delay, slack 기록
- Worst path 식별

**UI 표시**:
```
엣지 선택 → "이 엣지가 포함된 worst path 3개 + slack" 표시
critical path → 빨간색
여유 있는 path → 회색
```

### 9.2 "최적 루트 찾기" (현실 버전)

**이상**: "새 신호를 어디로 연결해야 딜레이 최소?"
**현실**: 완전 자동화는 어려움

**대안**: 
- 현재 설계의 **기존 path** 중 가장 짧은 경로 제시
- 각 노드/엣지에 데이터 부착:
  - arrival_time
  - required_time
  - slack
  - fanout
- 사용자가 **여유 있는 경로 판단**할 수 있도록 지원

### 9.3 향후 확장: SDF 파싱

**SDF (Standard Delay Format)**:
- 더 정밀한 딜레이 정보
- 셀 레벨, 넷 레벨 딜레이 구분
- 시뮬레이션과 연동 가능

## 10. AI 컨텍스트 선택 전략

### 10.1 방법 1: 드래그 선택
```
사용자: 그래프에서 일부 영역 드래그
시스템: 선택 영역을 JSON으로 export
       → 내부 AI가 분석
```

### 10.2 방법 2: 프로젝트 전체 분석
```
사용자: "전체 프로젝트 분석해줘"
시스템: 
  1. 시작점 결정 (TOP 또는 LLM/휴리스틱)
  2. 깊이 결정 (전체 또는 사용자 설정)
  3. 서브그래프 추출
  4. AI에 전달
```

### 10.3 핵심 질문

> **"그래프 시작점 + depth를 어떻게 정할 것인가?"**

**옵션 A**: LLM이 자동 결정
- 사용자 질의 분석 → 관련 모듈 추론 → 시작점/깊이 설정

**옵션 B**: 사용자 직접 설정
- UI에서 "종속성 낮음(1-hop) / 중간(2-hop) / 깊음(3-hop)" 선택
- 시작 코드/파일 직접 지정

**제안**: 하이브리드 방식

## 11. 분석 목표별 DKG 활용

| 도메인 | 무엇을 보는가 | 기존 툴 | DKG |
|--------|-------------|---------|-----|
| Structural | 모듈 조직 | 부분적 | ✅ 완전 |
| Connectivity | 신호 흐름 | 매우 약함 | ✅ 강력 |
| State | 상태 위치 | 거의 없음 | ✅ 추적 |
| Temporal | 타이밍 | 숫자만 | ✅ 시각화 |
| Constraint | 제약 의도 | 텍스트 | ✅ 그래프 통합 |

## 12. 캐싱 전략

### 12.1 메타데이터 활용 캐싱

```python
# 메타데이터 내보내기
metadata = pipeline.export_metadata()

# 캐시 저장
cache = {
    "graph": {"nodes": nodes, "edges": edges},
    "metadata": metadata,
    "completed_stages": pipeline.completed_stages,
    "timestamp": time.time()
}
```

### 12.2 캐시 검증

```python
def is_cache_valid(cache, new_files):
    # SDC 파일이 변경되었는지 확인
    if "design.sdc" in new_files:
        # CONSTRAINTS stage 이후는 무효화
        return ParsingStage.CONSTRAINTS not in cache["completed_stages"]
    return True
```

### 12.3 부분 업데이트

- 특정 노드만 재파싱
- 변경된 파일의 stage만 재실행
- 증분 빌드 방식

## 13. 확장성 고려사항

### 13.1 대규모 프로젝트 (10만+ 라인)

**메모리 최적화**:
- 레이지 로딩: 필요한 부분만 메모리 로드
- 그래프 압축: 중복 제거, 델타 인코딩

**성능 최적화**:
- 인덱싱: 빠른 노드 검색
- 병렬 처리: 파싱 및 그래프 구축 병렬화

### 13.2 향후 기능

- [ ] 필드 변경 이력 추적 (감사 로그)
- [ ] 충돌 감지 (다른 SDC에서 다른 값 선언)
- [ ] JSON/DB로 메타데이터 직렬화
- [ ] 파서 체인 병렬화
- [ ] 실시간 협업 (다중 사용자)

## 14. 파서 추가 방법

새 제약 파일 형식을 추가하려면:

```python
class CustomParser(ConstraintParser):
    def get_stage(self) -> ParsingStage:
        return ParsingStage.CONSTRAINTS
    
    def parse_and_update(self, filepath, updater, nodes, edges):
        # 파싱 로직
        for line in open(filepath):
            # ...
            updater.update_node_field(
                node_id, 
                field_name, 
                new_value,
                source=FieldSource.DECLARED,
                stage=self.get_stage()
            )

# 파이프라인에 등록
pipeline.register_parser(CustomParser())
```

## 15. 아키텍처 요약

```
┌─────────────────────────────────────────────────────────┐
│                   DKG (Single Source of Truth)          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ NetList      │→ │ Logic Graph  │→ │ View Graph   │ │
│  │ Layer        │  │ Layer        │  │ Layer        │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                           ↓
        ┌──────────────────┼──────────────────┐
        ↓                  ↓                  ↓
  Structural View    Timing View      Connectivity View
```

**핵심**:
- 하나의 통합 그래프
- 다중 뷰 지원
- 점진적 정보 축적
- 우선순위 기반 업데이트
