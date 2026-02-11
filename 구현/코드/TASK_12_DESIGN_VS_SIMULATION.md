# Task 12: Design vs Simulation 정책 구현 가이드

## 개요

DKG 시스템의 정책(Policy)은 **"수천 개의 RTL 요소를 어떤 기준으로 묶어서(Grouping) 보여줄 것인가?"**를 결정합니다.

Task 12는 **Design 모드**와 **Simulation 모드** 두 가지 명확하게 구분된 정책을 정의하고 구현합니다.

---

## 1. 핵심 철학 (Philosophy)

정책을 코드로 짜기 전에, **"사용자가 무엇을 보고 싶어 하는가?"**를 먼저 정의합니다.

### Design Mode (구현/합성 뷰)

**핵심 질문**: "실제 칩(FPGA/ASIC)에 어떤 하드웨어가 배치되는가?"

| 항목 | 내용 |
|------|------|
| **목표** | 물리적 실체(Physical Reality)만 남긴다 |
| **주요 관심사** | Timing Path, Pblock(물리적 위치), Resource 사용량 |
| **불필요한 것** | initial 블록, 파일 I/O, $display, Testbench Wrapper |
| **시각화 목표** | Critical Path를 중심으로 한 하드웨어 병목 구간 식별 |

### Simulation Mode (검증/동작 뷰)

**핵심 질문**: "테스트벤치에서 데이터가 어떻게 흐르고 검증되는가?"

| 항목 | 내용 |
|------|------|
| **목표** | 검증 환경(Environment)과 테스트 대상(DUT)의 관계를 보여준다 |
| **주요 관심사** | Stimulus(입력 생성), DUT(테스트 대상), Checker/Monitor |
| **불필요한 것** | (상대적으로) 구체적인 LUT/FF 단위의 배치 제약 |
| **시각화 목표** | Transaction의 흐름과 모듈 간 인터페이스 확인 |

---

## 2. 엔티티별 처리 전략 (Strategy Matrix)

### A. Design Mode (기존 로직 강화)

목표: **물리적 실체(Physical Reality)만 남긴다**

| EntityClass | Structural | Connectivity | Physical |
|-------------|------------|--------------|----------|
| **MODULE_INSTANCE** | PROMOTE | ELIMINATE | - |
| **LUT** | MERGE → CombinationalCloud | MERGE → CombinationalCloud | - |
| **MUX** | MERGE → CombinationalCloud | MERGE → CombinationalCloud | - |
| **FLIP_FLOP** | MERGE → ModuleCluster | PROMOTE | - |
| **DSP** | MERGE → ModuleCluster | PROMOTE | MERGE → ConstraintGroup |
| **BRAM** | MERGE → ModuleCluster | PROMOTE | MERGE → ConstraintGroup |
| **IO_PORT** | PROMOTE | PROMOTE | PROMOTE |
| **PBLOCK** | ELIMINATE | ELIMINATE | PROMOTE |
| **PACKAGE_PIN** | ELIMINATE | ELIMINATE | PROMOTE |
| **Testbench (tb_\*)** | **ELIMINATE (동적)** | **ELIMINATE (동적)** | **ELIMINATE (동적)** |

### B. Simulation Mode (신규 정의)

목표: **검증 환경(Environment)과 테스트 대상(DUT)의 관계를 보여준다**

| EntityClass | Structural | Connectivity | Physical |
|-------------|------------|--------------|----------|
| **MODULE_INSTANCE** | PROMOTE | PROMOTE | - |
| **IO_PORT** | PROMOTE | PROMOTE | - |
| **RTL_BLOCK** | MERGE → ModuleCluster | MERGE → ModuleCluster | - |
| **FLIP_FLOP** | MERGE → ModuleCluster | **PROMOTE** | - |
| **DSP** | MERGE → ModuleCluster | **PROMOTE** | - |
| **BRAM** | MERGE → ModuleCluster | **PROMOTE** | - |
| **LUT** | MERGE → ModuleCluster | MERGE → ModuleCluster | - |
| **PBLOCK** | **ELIMINATE** | **ELIMINATE** | **ELIMINATE** |
| **PACKAGE_PIN** | **ELIMINATE** | **ELIMINATE** | **ELIMINATE** |
| **Clock Generator (clk_gen_\*)** | **PROMOTE (동적)** | **PROMOTE (동적)** | - |
| **Initial Block** | **PROMOTE (동적)** | - | - |

---

## 3. 코드 구현 상세

### 3.1 GraphContext Enum 정의

```python
class GraphContext(str, Enum):
    """그래프 생성 및 뷰 선택의 사용 맥락 정의"""
    DESIGN = "design"              # 합성, 구현, 타이밍 분석
    SIMULATION = "simulation"      # 동작 검증, 테스트벤치
```

### 3.2 Policy Map 분리

```python
# Design Mode 정책
POLICY_MAP_DESIGN: dict[GraphViewType, dict[EntityClass, NodePolicy]] = {
    GraphViewType.Structural: { ... },
    GraphViewType.Connectivity: { ... },
    GraphViewType.Physical: { ... },
}

# Simulation Mode 정책
POLICY_MAP_SIMULATION: dict[GraphViewType, dict[EntityClass, NodePolicy]] = {
    GraphViewType.Structural: { ... },
    GraphViewType.Connectivity: { ... },
    GraphViewType.Physical: { ... },  # 보통 비어있음
}
```

### 3.3 정책 선택 함수

```python
def select_policy_map(context: GraphContext) -> dict[GraphViewType, dict[EntityClass, NodePolicy]]:
    """컨텍스트에 따른 정책 맵 선택"""
    if context == GraphContext.SIMULATION:
        return POLICY_MAP_SIMULATION
    else:
        return POLICY_MAP_DESIGN
```

### 3.4 정책 결정 함수 (get_node_policy)

```python
def get_node_policy(
    node: DKGNode,
    view: GraphViewType,
    context: GraphContext = GraphContext.DESIGN,
) -> NodePolicy:
    """
    1. 컨텍스트에 따른 정책 맵 선택
    2. 뷰에 해당하는 정책 조회
    3. 엔티티 클래스에 따른 기본 정책 반환
    4. 속성 기반 동적 오버라이딩 (Task 12의 핵심)
    """
    policy_map = select_policy_map(context)
    view_policies = policy_map.get(view, {})
    base_policy = view_policies.get(
        node.entity_class,
        NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED)
    )
    
    # Design 모드: testbench 강제 제거
    if context == GraphContext.DESIGN:
        if (node.local_name.lower().startswith("tb_") or
            "testbench" in node.hier_path.lower()):
            return NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED)
    
    # Simulation 모드: Clock/Reset Generator 보존
    if context == GraphContext.SIMULATION:
        if (node.local_name.lower().startswith("clk_gen") or
            node.local_name.lower().startswith("reset_gen")):
            if base_policy.action == NodeAction.MERGE:
                return NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC)
    
    return base_policy
```

### 3.5 ViewBuilder 업데이트

```python
class ViewBuilder:
    def __init__(
        self,
        nodes: Dict[str, DKGNode],
        edges: Dict[str, DKGEdge],
        view: GraphViewType,
        context: GraphContext = GraphContext.DESIGN,  # 새로 추가
    ):
        self.nodes = nodes
        self.edges = edges
        self.view = view
        self.context = context  # 저장
        # ...

    def cycle1_promote(self) -> None:
        for n in self.nodes.values():
            # context 전달
            node_policy = get_node_policy(n, self.view, self.context)
            # ...
```

---

## 4. 사용 예시

### 4.1 Design Mode - Connectivity 뷰

```python
from dkg.supergraph import (
    ViewBuilder, GraphViewType, GraphContext, DKGNode, DKGEdge
)

# Design 모드로 Connectivity 뷰 생성 (타이밍 분석용)
builder = ViewBuilder(
    nodes=dkg_nodes,           # Dict[str, DKGNode]
    edges=dkg_edges,           # Dict[str, DKGEdge]
    view=GraphViewType.Connectivity,
    context=GraphContext.DESIGN  # CPU 설계, 타이밍 최적화
)
supergraph_design = builder.build()

# 결과: FF, DSP, BRAM은 PROMOTE되고 (Atomic)
#       LUT/MUX는 MERGE되어 CombinationalCloud로 표현
#       tb_* 패턴의 노드는 모두 제거됨
```

### 4.2 Simulation Mode - Structural 뷰

```python
# Simulation 모드로 Structural 뷰 생성 (검증 환경)
builder = ViewBuilder(
    nodes=dkg_nodes,
    edges=dkg_edges,
    view=GraphViewType.Structural,
    context=GraphContext.SIMULATION  # 테스트벤치 실행, 동작 검증
)
supergraph_sim = builder.build()

# 결과: MODULE_INSTANCE는 PROMOTE (모듈 구조 명확)
#       내부 로직(LUT/MUX)은 MERGE (DUT 블랙박스)
#       clk_gen_*, reset_gen_* 노드는 PROMOTE (스티뮬러스)
#       PBLOCK, PACKAGE_PIN은 제거 (위치 정보 무의미)
```

### 4.3 동적 오버라이딩 예시

```python
# 노드 생성 예시
node_testbench = DKGNode(
    node_id="n_tb_1",
    entity_class=EntityClass.RTL_BLOCK,
    hier_path="top_sim/tb_wrapper",
    local_name="tb_wrapper",
)

node_clk_gen = DKGNode(
    node_id="n_clk_1",
    entity_class=EntityClass.RTL_BLOCK,
    hier_path="top_sim/clk_gen_main",
    local_name="clk_gen_main",
)

# Design 모드
policy_tb_design = get_node_policy(node_testbench, GraphViewType.Connectivity, 
                                   context=GraphContext.DESIGN)
# 결과: NodePolicy(NodeAction.ELIMINATE, ...)
# -> local_name이 "tb_"로 시작하므로 강제 제거

# Simulation 모드에서 testbench는?
policy_tb_sim = get_node_policy(node_testbench, GraphViewType.Structural,
                                context=GraphContext.SIMULATION)
# 결과: NodePolicy(NodeAction.MERGE, SuperClass.MODULE_CLUSTER)
# -> 기본 정책 적용 (tb_* 필터링 없음)

# Simulation 모드에서 clock generator
policy_clk_sim = get_node_policy(node_clk_gen, GraphViewType.Connectivity,
                                 context=GraphContext.SIMULATION)
# 결과: NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC)
# -> "clk_gen" 패턴 인식하여 상향 (기본: MERGE였음)
```

---

## 5. 테스트 및 검증 방법

### 5.1 정책 일관성 테스트

```python
def test_policy_coverage():
    """모든 EntityClass에 대해 정책이 정의되었는지 확인"""
    for context in [GraphContext.DESIGN, GraphContext.SIMULATION]:
        policy_map = select_policy_map(context)
        for view in [GraphViewType.Structural, GraphViewType.Connectivity]:
            view_policies = policy_map.get(view, {})
            # Simulation.Physical은 비어있을 수 있음 (OK)
            if context == GraphContext.DESIGN or view != GraphViewType.Physical:
                assert len(view_policies) > 0, \
                    f"Missing policies for {context.value}/{view.value}"
```

### 5.2 동적 오버라이딩 테스트

```python
def test_testbench_elimination():
    """Design 모드에서 testbench 노드가 제거되는지 확인"""
    testbench_nodes = [
        DKGNode(..., local_name="tb_wrapper", ...),
        DKGNode(..., hier_path="sim/tb_main", ...),
        DKGNode(..., hier_path="top_sim/...", ...),  # "sim" 포함
    ]
    
    for node in testbench_nodes:
        policy = get_node_policy(node, GraphViewType.Connectivity,
                                context=GraphContext.DESIGN)
        assert policy.action == NodeAction.ELIMINATE, \
            f"Testbench node {node.local_name} should be eliminated in DESIGN mode"

def test_clock_gen_promotion():
    """Simulation 모드에서 Clock Generator가 상향되는지 확인"""
    clk_gen = DKGNode(
        node_id="n_clk_1",
        entity_class=EntityClass.RTL_BLOCK,  # 기본: MERGE
        hier_path="top_sim/clk_gen_main",
        local_name="clk_gen_main",
        attributes={}
    )
    
    policy = get_node_policy(clk_gen, GraphViewType.Connectivity,
                           context=GraphContext.SIMULATION)
    assert policy.action == NodeAction.PROMOTE, \
        "Clock generator should be PROMOTE in SIMULATION mode"
```

### 5.3 뷰별 정책 검증

```python
def test_design_connectivity_view():
    """Design 모드 Connectivity 뷰의 정책 검증"""
    view_policies = POLICY_MAP_DESIGN[GraphViewType.Connectivity]
    
    # FF/DSP/BRAM: PROMOTE
    assert view_policies[EntityClass.FLIP_FLOP].action == NodeAction.PROMOTE
    assert view_policies[EntityClass.DSP].action == NodeAction.PROMOTE
    
    # LUT/MUX: MERGE -> CombinationalCloud
    assert view_policies[EntityClass.LUT].action == NodeAction.MERGE
    assert view_policies[EntityClass.LUT].super_class == SuperClass.COMB_CLOUD
    
    # Testbench-like: ELIMINATE
    assert view_policies[EntityClass.PACKAGE_PIN].action == NodeAction.ELIMINATE

def test_simulation_connectivity_view():
    """Simulation 모드 Connectivity 뷰의 정책 검증"""
    view_policies = POLICY_MAP_SIMULATION[GraphViewType.Connectivity]
    
    # 모듈 인터페이스: PROMOTE
    assert view_policies[EntityClass.MODULE_INSTANCE].action == NodeAction.PROMOTE
    assert view_policies[EntityClass.IO_PORT].action == NodeAction.PROMOTE
    
    # 레지스터도 PROMOTE (상태 추적 중요)
    assert view_policies[EntityClass.FLIP_FLOP].action == NodeAction.PROMOTE
    
    # 물리적 정보: ELIMINATE
    assert view_policies[EntityClass.PBLOCK].action == NodeAction.ELIMINATE
```

---

## 6. 문제 해결 (Troubleshooting)

### Q1: "Design 모드에서 일부 testbench 노드가 제거되지 않음"

**원인**: 노드의 `local_name`이나 `hier_path`가 패턴을 정확히 매칭하지 않음

**해결**:
```python
# get_node_policy의 동적 필터링 로직 확인
is_testbench = (
    node.local_name.lower().startswith("tb_") or
    "testbench" in node.hier_path.lower() or
    "sim" in node.hier_path.lower()  # 추가 조건
)
```

### Q2: "Simulation 모드에서 Clock Generator가 여전히 MERGE됨"

**원인**: 노드의 `local_name`이 `clk_gen_*` 패턴과 정확히 일치하지 않음

**해결**:
```python
is_important_for_sim = (
    node.local_name.lower().startswith("clk_gen") or
    node.local_name.lower().startswith("reset_gen") or
    "clock_gen" in node.local_name.lower()  # 추가 별칭
)
```

### Q3: "ViewBuilder 호출 시 TypeError"

**원인**: 기존 코드에서 `context` 매개변수 없이 호출

**해결**:
```python
# Before (오류)
builder = ViewBuilder(nodes, edges, GraphViewType.Connectivity)

# After (수정)
builder = ViewBuilder(
    nodes, edges, 
    GraphViewType.Connectivity,
    context=GraphContext.DESIGN  # 추가
)
# 또는 기본값 사용 (GraphContext.DESIGN)
```

---

## 7. 향후 확장 계획

### 7.1 추가 Context 정의

```python
class GraphContext(str, Enum):
    DESIGN = "design"
    SIMULATION = "simulation"
    FORMAL_VERIFICATION = "formal"  # 공식 검증용
    POWER_ANALYSIS = "power"         # 전력 분석용
    AREA_ESTIMATION = "area"         # 면적 추정용
```

### 7.2 속성 기반 세밀한 필터링

```python
def get_node_policy(...) -> NodePolicy:
    # 기존 로직
    base_policy = ...
    
    # 확장: 사용자 정의 필터
    if "skip_synthesis" in node.attributes:
        return NodePolicy(NodeAction.ELIMINATE, SuperClass.ELIMINATED)
    
    if "critical_path" in node.attributes:
        return NodePolicy(NodeAction.PROMOTE, SuperClass.ATOMIC)
    
    return base_policy
```

### 7.3 정책 버전 관리

```python
def get_node_policy(...) -> NodePolicy:
    # 정책 버전에 따른 다른 동작
    policy_version = node.attributes.get("policy_version", "v1")
    
    if policy_version == "v2":
        # v2 정책 적용
        pass
    else:
        # v1 정책 (기본값)
        pass
```

---

## 참고 문서

- [supergraph.py](dkg/supergraph.py) - 전체 구현
- [graph.py](dkg/graph.py) - EntityClass, DKGNode 정의
- [stages.py](dkg/stages.py) - 파싱 단계, FieldSource 정의
- [DESIGN.md](DESIGN.md) - 전체 설계 문서
