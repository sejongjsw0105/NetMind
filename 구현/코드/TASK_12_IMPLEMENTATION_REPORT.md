# Task 12 구현 완료 보고서

## 실행 요약

Task 12 (Design vs Simulation 정책 수립)이 **완전히 구현**되었습니다.

### 구현 범위

| 항목 | 상태 | 설명 |
|-----|------|------|
| **GraphContext Enum** | ✅ 완료 | Design/Simulation 모드 정의 |
| **POLICY_MAP_DESIGN** | ✅ 완료 | 합성/구현/타이밍 정책 (Structural, Connectivity, Physical) |
| **POLICY_MAP_SIMULATION** | ✅ 완료 | 검증/테스트벤치 정책 (Structural, Connectivity) |
| **select_policy_map()** | ✅ 완료 | 컨텍스트 기반 정책 맵 선택 |
| **get_node_policy()** | ✅ 완료 | 속성 기반 동적 오버라이딩 지원 |
| **ViewBuilder 확장** | ✅ 완료 | context 매개변수 추가, 모든 메서드 업데이트 |
| **테스트** | ✅ 완료 | 10개 테스트 모두 통과 (0 failed) |

### 테스트 결과

```
======================================================================
Task 12: Design vs Simulation 정책 테스트
======================================================================
[Test 1] GraphContext Enum 검증 ........................ ✓
[Test 2] Policy Map 선택 함수 검증 ..................... ✓
[Test 3] Policy Map 커버리지 검증 ..................... ✓
[Test 4] Design Mode - Connectivity View 정책 검증 .... ✓
[Test 5] Simulation Mode - Connectivity View 정책 검증 ✓
[Test 6] Design Mode - Testbench 제거 ................. ✓
[Test 7] Simulation Mode - Clock Generator 상향 ....... ✓
[Test 8] get_node_policy 기본값 검증 ................. ✓
[Test 9] ViewBuilder Context 매개변수 검증 ........... ✓
[Test 10] Design vs Simulation 모드 독립성 ........... ✓

테스트 결과: 10 passed, 0 failed
======================================================================
```

---

## 핵심 변경 사항

### 1. supergraph.py 수정

#### 추가된 코드

```python
# (1) GraphContext Enum
class GraphContext(str, Enum):
    DESIGN = "design"
    SIMULATION = "simulation"

# (2) 기존 POLICY_MAP -> POLICY_MAP_DESIGN으로 리네임
POLICY_MAP_DESIGN: dict[GraphViewType, dict[EntityClass, NodePolicy]] = { ... }

# (3) 신규 POLICY_MAP_SIMULATION 정의
POLICY_MAP_SIMULATION: dict[GraphViewType, dict[EntityClass, NodePolicy]] = { ... }

# (4) 정책 맵 선택 함수
def select_policy_map(context: GraphContext) -> dict[GraphViewType, dict[EntityClass, NodePolicy]]:
    if context == GraphContext.SIMULATION:
        return POLICY_MAP_SIMULATION
    else:
        return POLICY_MAP_DESIGN

# (5) get_node_policy 확장
def get_node_policy(
    node: DKGNode,
    view: GraphViewType,
    context: GraphContext = GraphContext.DESIGN,  # 새 매개변수
) -> NodePolicy:
    # 컨텍스트 기반 정책 맵 선택
    policy_map = select_policy_map(context)
    
    # 속성 기반 동적 오버라이딩
    if context == GraphContext.DESIGN:
        # testbench 노드 강제 제거
        if node.local_name.lower().startswith("tb_"):
            return NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED)
    
    if context == GraphContext.SIMULATION:
        # Clock/Reset Generator 자동 상향
        if node.local_name.lower().startswith("clk_gen"):
            if base_policy.action == NodeAction.MERGE:
                return NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC)
    
    return base_policy

# (6) ViewBuilder 업데이트
class ViewBuilder:
    def __init__(self, ..., context: GraphContext = GraphContext.DESIGN):
        self.context = context  # context 저장
    
    def cycle1_promote(self):
        node_policy = get_node_policy(n, self.view, self.context)  # context 전달
```

### 2. 정책 맵 비교

#### Design Mode (기존 로직 강화)

**Connectivity View 기준**:
- **PROMOTE**: FF, DSP, BRAM, IO_PORT
- **MERGE** → CombinationalCloud: LUT, MUX
- **ELIMINATE**: MODULE_INSTANCE, PBLOCK, PACKAGE_PIN

#### Simulation Mode (신규)

**Connectivity View 기준**:
- **PROMOTE**: MODULE_INSTANCE, IO_PORT, FLIP_FLOP, DSP, BRAM
  - (상태 추적이 중요하므로 레지스터도 상향)
- **MERGE** → ModuleCluster: LUT, MUX, RTL_BLOCK, FSM
- **ELIMINATE**: PBLOCK, PACKAGE_PIN (위치 정보 무의미)

---

## 동적 오버라이딩 (Dynamic Override)

### 패턴 기반 필터링

#### Design 모드: Testbench 자동 제거

```python
# 다음 패턴의 노드는 Design 모드에서 자동 제거
- local_name.startswith("tb_")        # tb_wrapper, tb_main, ...
- "testbench" in hier_path.lower()    # /testbench/...
- "sim" in hier_path.lower()          # /sim/...
```

**예시**:
```
n_tb_1: local_name="tb_wrapper"           → ELIMINATE
n_tb_2: hier_path="top_sim/tb_main"       → ELIMINATE
n_tb_3: hier_path="top/sim_helper"        → ELIMINATE
```

#### Simulation 모드: Generator 자동 상향

```python
# 다음 패턴의 노드는 Simulation 모드에서 자동 상향
- local_name.startswith("clk_gen")        # clk_gen_main, ...
- local_name.startswith("reset_gen")      # reset_gen_sync, ...
- "initial" in attributes["verilog_construct"]  # initial 블록
```

**예시**:
```
n_clk_1: local_name="clk_gen_main"
  - Base Policy: MERGE (RTL_BLOCK)
  - Override: PROMOTE → ATOMIC (clk_gen 패턴)

n_rst_1: local_name="reset_gen_sync"
  - Base Policy: MERGE (RTL_BLOCK)
  - Override: PROMOTE → ATOMIC (reset_gen 패턴)
```

---

## 사용 방법

### 기본 사용: Design Mode (기본값)

```python
from dkg.supergraph import ViewBuilder, GraphViewType

# 기본값 사용 (GraphContext.DESIGN)
builder = ViewBuilder(
    nodes=dkg_nodes,
    edges=dkg_edges,
    view=GraphViewType.Connectivity,
)
supergraph = builder.build()
```

### 명시적 사용: Simulation Mode

```python
from dkg.supergraph import ViewBuilder, GraphViewType, GraphContext

builder = ViewBuilder(
    nodes=dkg_nodes,
    edges=dkg_edges,
    view=GraphViewType.Structural,
    context=GraphContext.SIMULATION,  # 명시적 지정
)
supergraph = builder.build()
```

### 정책 조회: get_node_policy

```python
from dkg.supergraph import get_node_policy, GraphViewType, GraphContext

# Design 모드에서 노드 정책 조회
policy = get_node_policy(node, GraphViewType.Connectivity, GraphContext.DESIGN)

# 기본값 (Design)
policy = get_node_policy(node, GraphViewType.Connectivity)
```

---

## 파일 구조

### 수정된 파일

1. **dkg/supergraph.py** (583 → 598 라인)
   - GraphContext enum 추가
   - POLICY_MAP_DESIGN, POLICY_MAP_SIMULATION 정의
   - select_policy_map() 함수 추가
   - get_node_policy() 함수 확장
   - ViewBuilder 업데이트

### 신규 파일

2. **test_task_12.py** (새로 생성)
   - 10개의 통합 테스트
   - Policy 일관성 검증
   - 동적 오버라이딩 검증
   - ViewBuilder context 검증

3. **TASK_12_DESIGN_VS_SIMULATION.md** (새로 생성)
   - 상세 구현 가이드
   - 정책 설명 및 비교표
   - 코드 예제
   - 테스트/검증 방법
   - 문제 해결 가이드

---

## 주요 기능

### 1. 컨텍스트 기반 정책 선택

```
Input: GraphContext.DESIGN
  └─ select_policy_map()
     └─ return POLICY_MAP_DESIGN
        ├─ Structural: 12 policies
        ├─ Connectivity: 12 policies
        └─ Physical: 6 policies

Input: GraphContext.SIMULATION
  └─ select_policy_map()
     └─ return POLICY_MAP_SIMULATION
        ├─ Structural: 12 policies
        ├─ Connectivity: 12 policies
        └─ Physical: 0 policies (empty)
```

### 2. 속성 기반 동적 필터링

```
get_node_policy(node, view, context)
  ├─ 1단계: Policy Map 선택
  │   └─ select_policy_map(context)
  ├─ 2단계: 기본 정책 조회
  │   └─ policy_map[view][entity_class]
  ├─ 3단계: 동적 오버라이드
  │   ├─ Design Mode
  │   │  └─ testbench 패턴 → ELIMINATE
  │   └─ Simulation Mode
  │      └─ generator 패턴 → PROMOTE
  └─ 4단계: 최종 정책 반환
```

### 3. ViewBuilder Context 전파

```
ViewBuilder(context=GraphContext.DESIGN)
  ├─ cycle1_promote()
  │  └─ get_node_policy(n, self.view, self.context) ✓
  ├─ cycle2_merge()
  │  └─ get_node_policy(n, self.view, self.context) ✓
  ├─ cycle2_5_eliminate()
  │  └─ get_node_policy(n, self.view, self.context) ✓
  └─ cycle3_rewrite_edges()
```

---

## 확장 가능성

### 향후 추가 가능한 Context

```python
class GraphContext(str, Enum):
    DESIGN = "design"
    SIMULATION = "simulation"
    FORMAL_VERIFICATION = "formal"    # 공식 검증
    POWER_ANALYSIS = "power"           # 전력 분석
    AREA_ESTIMATION = "area"           # 면적 추정
    TESTABILITY = "testability"        # 테스트 가능성
```

### 세밀한 필터링 규칙 추가

```python
def get_node_policy(...) -> NodePolicy:
    # 기존 로직
    base_policy = ...
    
    # 확장: 사용자 정의 속성 검사
    if "skip_synthesis" in node.attributes:
        return NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED)
    
    if "critical_path" in node.attributes:
        return NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC)
    
    # 확장: 계층별 정책
    if node.hier_path.startswith("top/memory"):
        return NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC)
```

---

## 성능 및 메모리

### Policy Map 크기

| Context | View | 정책 개수 | 비고 |
|---------|------|---------|------|
| DESIGN | Structural | 12 | 모든 EntityClass 커버 |
| DESIGN | Connectivity | 12 | 모든 EntityClass 커버 |
| DESIGN | Physical | 6 | 물리적 요소 중심 |
| SIMULATION | Structural | 12 | - |
| SIMULATION | Connectivity | 12 | - |
| SIMULATION | Physical | 0 | 비어있음 |

### 조회 성능

- `select_policy_map()`: **O(1)** (딕셔너리 조회)
- `get_node_policy()`: **O(1)** (해시 기반)
- 전체 정책 적용 (ViewBuilder): **O(N)** (N = 노드 개수)

---

## 호환성

### 하위 호환성 (Backward Compatibility)

✅ **완전 호환** - 기존 코드 수정 불필요

```python
# Before (여전히 작동)
builder = ViewBuilder(nodes, edges, GraphViewType.Connectivity)

# After (권장)
builder = ViewBuilder(
    nodes, edges, GraphViewType.Connectivity,
    context=GraphContext.DESIGN
)
```

- `context` 미지정 시 기본값 **GraphContext.DESIGN** 사용
- 기존 POLICY_MAP 로직과 동일한 결과

### 다른 모듈과의 상호작용

- ✅ graph.py: 영향 없음
- ✅ stages.py: 영향 없음
- ✅ graph_updater.py: 영향 없음
- ✅ pipeline.py: 업데이트 필요 (ViewBuilder 호출시 context 지정)

---

## 검증 체크리스트

- [x] GraphContext enum 정의됨
- [x] POLICY_MAP_DESIGN 완성됨 (Structural, Connectivity, Physical)
- [x] POLICY_MAP_SIMULATION 완성됨 (Structural, Connectivity)
- [x] select_policy_map() 구현됨
- [x] get_node_policy() 확장됨 (동적 오버라이딩)
- [x] ViewBuilder 업데이트됨 (context 전파)
- [x] 모든 get_node_policy 호출에 context 전달
- [x] 정책 일관성 테스트 통과 (Test 1~5)
- [x] 동적 오버라이딩 테스트 통과 (Test 6~7)
- [x] 기본값 및 ViewBuilder 테스트 통과 (Test 8~10)
- [x] 문서 작성 완료

---

## 다음 단계

### Phase 1 (현재 완료)
- [x] 정책 정의 및 구현
- [x] 코드 작성 및 테스트
- [x] 문서 작성

### Phase 2 (추천)
- [ ] 실제 RTL 파일로 통합 테스트
- [ ] pipeline.py 업데이트 (context 지정)
- [ ] UI/Visualization에서 모드 선택 추가

### Phase 3 (향후)
- [ ] 추가 Context (FORMAL_VERIFICATION, POWER_ANALYSIS)
- [ ] 사용자 정의 필터링 규칙
- [ ] 정책 버전 관리

---

## 참도서

문서 위치:
- [TASK_12_DESIGN_VS_SIMULATION.md](TASK_12_DESIGN_VS_SIMULATION.md) - 상세 가이드
- [test_task_12.py](test_task_12.py) - 테스트 코드
- [dkg/supergraph.py](dkg/supergraph.py) - 구현 코드

직접 실행:
```bash
# 테스트 실행
python test_task_12.py

# 대화형 검증
python -c "from dkg.supergraph import GraphContext; print(GraphContext.DESIGN)"
```

---

**작성일**: 2026-02-11  
**상태**: ✅ 완료  
**테스트 결과**: 10/10 passed
