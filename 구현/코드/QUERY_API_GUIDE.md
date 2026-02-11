# DKG Query API 사용 가이드

## 개요

DKG Query API는 Design Knowledge Graph를 쿼리하고 분석하기 위한 통합 인터페이스입니다. 노드/엣지 검색, 경로 탐색, 타이밍 분석, 계층 구조 탐색 등 다양한 기능을 제공합니다.

## 설치 및 임포트

```python
from dkg.query_api import DKGQuery, create_query
from dkg.pipeline import DKGPipeline
from dkg.utils.config import YosysConfig
```

## 기본 사용법

### 1. Query API 생성

```python
# DKGPipeline으로 그래프 생성
pipeline = DKGPipeline(config)
pipeline.run_rtl_stage()
nodes, edges = pipeline.get_graph()

# Query API 생성
query = create_query(nodes, edges)
# 또는
query = DKGQuery(nodes, edges)

# SuperGraph와 함께 사용
pipeline.build_supergraph()
query = create_query(nodes, edges, pipeline.supergraph)
```

## 주요 기능

### 노드 검색 (Node Queries)

#### 1. Entity Class로 검색

```python
from dkg.core.graph import EntityClass

# 모든 Flip-Flop 찾기
ffs = query.find_nodes(entity_class=EntityClass.FLIP_FLOP)

# 모든 LUT 찾기
luts = query.find_nodes(entity_class=EntityClass.LUT)

# 결과는 node_id 리스트
for node_id in ffs:
    node = query.get_node(node_id)
    print(f"{node.hier_path}: {node.entity_class}")
```

#### 2. 이름 패턴으로 검색

```python
# 와일드카드 지원 (* = 임의 문자열, ? = 임의 1문자)
clk_nodes = query.find_nodes(name_pattern="*clk*")
reset_nodes = query.find_nodes(name_pattern="*rst*")
pc_regs = query.find_nodes(name_pattern="pc_reg*")
```

#### 3. 계층 구조로 검색

```python
# 특정 모듈의 모든 노드
cpu_nodes = query.find_nodes(hierarchy_prefix="cpu")
alu_nodes = query.find_nodes(hierarchy_prefix="cpu/alu")
```

#### 4. Slack 범위로 검색

```python
# Slack이 -0.5 ~ 0.5 사이인 노드
critical_range = query.find_nodes(slack_range=(-0.5, 0.5))

# Slack이 음수인 노드 (타이밍 위반)
violations = query.find_nodes(slack_range=(-float('inf'), 0.0))
```

#### 5. Clock Domain으로 검색

```python
# 특정 클럭 도메인의 노드
sys_clk_nodes = query.find_nodes(clock_domain="sys_clk")
```

#### 6. 복합 조건 검색

```python
# 여러 조건 동시 적용
critical_ffs = query.find_nodes(
    entity_class=EntityClass.FLIP_FLOP,
    hierarchy_prefix="cpu",
    slack_range=(-float('inf'), 0.5)
)
```

#### 7. 사용자 정의 필터

```python
# 파라미터 기반 필터
wide_nodes = query.find_nodes(
    custom_filter=lambda n: n.parameters.get("width", 0) > 32
)

# 복잡한 조건
special_nodes = query.find_nodes(
    custom_filter=lambda n: (
        n.slack is not None and 
        n.slack < 0.5 and 
        n.arrival_time is not None and 
        n.arrival_time > 10.0
    )
)
```

#### 8. 정확한 이름으로 노드 찾기

```python
# node_id, hier_path, canonical_name, local_name으로 검색
node_id = query.find_node_by_name("cpu/alu/adder")
if node_id:
    node = query.get_node(node_id)
```

### 엣지 검색 (Edge Queries)

#### 1. 소스/목적지로 검색

```python
# 특정 노드에서 나오는 엣지
outgoing = query.find_edges(src_node="node1")

# 특정 노드로 들어가는 엣지
incoming = query.find_edges(dst_node="node2")

# 두 노드 사이의 엣지
connecting = query.find_edges(src_node="node1", dst_node="node2")
```

#### 2. 관계 타입으로 검색

```python
from dkg.core.graph import RelationType

# 데이터 관계 엣지만
data_edges = query.find_edges(relation_type=RelationType.DATA)

# 클럭 관계 엣지만
clock_edges = query.find_edges(relation_type=RelationType.CLOCK)
```

#### 3. Flow Type으로 검색

```python
from dkg.core.graph import EdgeFlowType

# Combinational 엣지만
comb_edges = query.find_edges(flow_type=EdgeFlowType.COMBINATIONAL)

# Sequential 엣지만
seq_edges = query.find_edges(flow_type=EdgeFlowType.SEQ_LAUNCH)
```

#### 4. 신호 이름으로 검색

```python
# 와일드카드 지원
data_signals = query.find_edges(signal_pattern="data*")
```

#### 5. 사용자 정의 필터

```python
# 지연이 큰 엣지 찾기
slow_edges = query.find_edges(
    custom_filter=lambda e: e.delay is not None and e.delay > 1.0
)
```

### 경로 탐색 (Graph Traversal)

#### 1. 모든 경로 찾기

```python
# start_node에서 end_node까지의 모든 경로
paths = query.find_paths("ff1", "ff2", max_depth=10)

for path in paths:
    print(f"Path: {' -> '.join(path.nodes)}")
    print(f"  Edges: {len(path.edges)}")
    print(f"  Total delay: {path.total_delay}")
    print(f"  Min slack: {path.total_slack}")

# 데이터 엣지만 따라가기
data_paths = query.find_paths("ff1", "ff2", follow_data_only=True)
```

#### 2. 최단 경로 찾기

```python
# 홉 수 기준 최단 경로
shortest = query.find_shortest_path("ff1", "ff2", weight="hops")

# 지연 기준 최단 경로
fastest = query.find_shortest_path("ff1", "ff2", weight="delay")

if shortest:
    print(f"Shortest path: {' -> '.join(shortest.nodes)}")
    print(f"Hops: {len(shortest) - 1}")
```

#### 3. 팬아웃 분석

```python
# 직접 연결된 팬아웃만 (depth=1)
fanout = query.get_fanout("clk_buf", max_depth=1)
print(f"Fanout count: {fanout.fanout_count}")
print(f"Max delay: {fanout.max_delay}")

# 깊이 2까지 탐색
deep_fanout = query.get_fanout("clk_buf", max_depth=2)

# 결과 노드들 확인
for node_id in fanout.fanout_nodes:
    node = query.get_node(node_id)
    print(f"  - {node.hier_path}")
```

#### 4. 팬인 분석

```python
# 노드로 들어오는 팬인
fanin = query.get_fanin("output_reg", max_depth=1)
print(f"Fanin count: {fanin.fanout_count}")

# 팬인 소스들
for src_id in fanin.fanout_nodes:
    src = query.get_node(src_id)
    print(f"  <- {src.hier_path}")
```

### 타이밍 분석 (Timing Queries)

#### 1. Critical 노드 찾기

```python
# Slack이 0 이하인 노드 (타이밍 위반)
critical = query.find_critical_nodes(slack_threshold=0.0)

for node_id, slack in critical:
    node = query.get_node(node_id)
    print(f"{node.hier_path}: slack = {slack:.3f} ns")

# 상위 N개만
top10 = query.find_critical_nodes(slack_threshold=1.0, top_n=10)
```

#### 2. Critical 엣지 찾기

```python
# 지연이 큰 엣지 찾기
slow_edges = query.find_critical_edges(delay_threshold=1.0)

for edge_id, delay in slow_edges:
    edge = query.get_edge(edge_id)
    print(f"{edge.signal_name}: delay = {delay:.3f} ns")

# 상위 N개 지연이 큰 엣지
top20 = query.find_critical_edges(top_n=20)
```

#### 3. 타이밍 요약

```python
summary = query.get_timing_summary()

print(f"Worst slack: {summary.worst_slack}")
print(f"Timing violations: {summary.timing_violations}")
print(f"Critical nodes: {len(summary.critical_nodes)}")
print(f"Critical edges: {len(summary.critical_edges)}")

# Critical 노드 목록
for node_id in summary.critical_nodes[:5]:
    node = query.get_node(node_id)
    print(f"  - {node.hier_path}")
```

### 계층 구조 탐색 (Hierarchy Queries)

#### 1. 직계 자식 노드 찾기

```python
# 'cpu' 모듈의 직계 자식만
children = query.get_hierarchy_children("cpu")

for child_id in children:
    child = query.get_node(child_id)
    print(f"- {child.local_name}: {child.entity_class}")
```

#### 2. 모든 하위 노드 찾기

```python
# 'cpu/alu' 아래의 모든 노드 (계층 전체)
subtree = query.get_hierarchy_subtree("cpu/alu")

print(f"Total nodes in cpu/alu: {len(subtree)}")
for node_id in subtree:
    node = query.get_node(node_id)
    print(f"  - {node.hier_path}")
```

### SuperGraph 쿼리

```python
# SuperGraph와 함께 Query API 생성
query = create_query(nodes, edges, supergraph)

# 1. SuperNode 검색
atomic_nodes = query.find_supernodes(super_class="Atomic")
seq_chains = query.find_supernodes(super_class="SequentialChain")

# 타이밍 분석이 부착된 SuperNode만
timing_nodes = query.find_supernodes(has_timing=True)

# 2. SuperNode 정보 가져오기
sn = query.get_supernode(sn_id)
if sn:
    print(f"Class: {sn.super_class}")
    print(f"Members: {len(sn.member_nodes)}")
    print(f"Analysis: {sn.analysis.keys()}")

# 3. 노드가 속한 SuperNode 찾기
supernode_id = query.get_supernode_for_node("ff1")
if supernode_id:
    sn = query.get_supernode(supernode_id)
    print(f"Node ff1 belongs to {sn.display_name}")
```

### 통계 정보

```python
stats = query.get_statistics()

print(f"Total nodes: {stats['total_nodes']}")
print(f"Total edges: {stats['total_edges']}")

# 노드 타입별 통계
print("\nNodes by class:")
for cls, count in stats['nodes_by_class'].items():
    print(f"  {cls}: {count}")

# 타이밍 통계
if 'timing' in stats:
    print(f"\nTiming:")
    print(f"  Worst slack: {stats['timing']['worst_slack']}")
    print(f"  Best slack: {stats['timing']['best_slack']}")
    print(f"  Average slack: {stats['timing']['avg_slack']}")
    print(f"  Violations: {stats['timing']['violations']}")

# 팬아웃 통계
if 'fanout' in stats:
    print(f"\nFanout:")
    print(f"  Max: {stats['fanout']['max']}")
    print(f"  Average: {stats['fanout']['avg']:.2f}")

# SuperGraph 통계
if 'supergraph' in stats:
    print(f"\nSuperGraph:")
    print(f"  Super nodes: {stats['supergraph']['super_nodes']}")
    print(f"  Super edges: {stats['supergraph']['super_edges']}")
```

## 실전 예제

### 예제 1: Critical Path 분석

```python
# 1. 최악의 슬랙을 가진 노드 찾기
critical_nodes = query.find_critical_nodes(top_n=1)
if critical_nodes:
    worst_node_id, worst_slack = critical_nodes[0]
    print(f"Worst node: {worst_node_id}, slack: {worst_slack}")
    
    # 2. 이 노드의 팬인 분석
    fanin = query.get_fanin(worst_node_id, max_depth=3)
    print(f"Fanin count: {fanin.fanout_count}")
    
    # 3. 팬인 노드들의 슬랙 확인
    for src_id in fanin.fanout_nodes:
        src = query.get_node(src_id)
        if src.slack is not None:
            print(f"  {src.hier_path}: {src.slack:.3f}")
```

### 예제 2: 클럭 도메인 분석

```python
# 1. 모든 클럭 관련 노드 찾기
clk_nodes = query.find_nodes(name_pattern="*clk*")

# 2. 각 클럭의 팬아웃 분석
for clk_id in clk_nodes:
    clk = query.get_node(clk_id)
    fanout = query.get_fanout(clk_id, max_depth=1)
    print(f"{clk.hier_path}:")
    print(f"  Fanout: {fanout.fanout_count}")
    print(f"  Max delay: {fanout.max_delay}")
```

### 예제 3: 모듈별 타이밍 품질

```python
modules = ["cpu/alu", "cpu/mem", "cpu/ctrl"]

for module in modules:
    # 모듈의 모든 노드
    nodes_in_module = query.find_nodes(hierarchy_prefix=module)
    
    # Critical 노드 수
    critical = query.find_nodes(
        hierarchy_prefix=module,
        slack_range=(-float('inf'), 0.0)
    )
    
    print(f"{module}:")
    print(f"  Total nodes: {len(nodes_in_module)}")
    print(f"  Critical: {len(critical)}")
    print(f"  Percentage: {len(critical)/len(nodes_in_module)*100:.1f}%")
```

### 예제 4: 높은 팬아웃 신호 찾기

```python
# 모든 노드의 팬아웃 계산
high_fanout = []

for node_id in query.nodes.keys():
    fanout = query.get_fanout(node_id, max_depth=1)
    if fanout.fanout_count > 100:  # 임계값
        high_fanout.append((node_id, fanout.fanout_count))

# 팬아웃 순으로 정렬
high_fanout.sort(key=lambda x: x[1], reverse=True)

print("High fanout signals:")
for node_id, count in high_fanout[:10]:
    node = query.get_node(node_id)
    print(f"  {node.hier_path}: {count}")
```

## API 레퍼런스

### DKGQuery 클래스

#### 노드 검색 메서드
- `find_nodes()` - 조건에 맞는 노드 검색
- `find_node_by_name()` - 이름으로 노드 검색
- `get_node()` - 노드 객체 반환

#### 엣지 검색 메서드
- `find_edges()` - 조건에 맞는 엣지 검색
- `get_edge()` - 엣지 객체 반환

#### 그래프 탐색 메서드
- `find_paths()` - 두 노드 사이의 모든 경로
- `find_shortest_path()` - 최단 경로
- `get_fanout()` - 팬아웃 분석
- `get_fanin()` - 팬인 분석

#### 타이밍 쿼리 메서드
- `find_critical_nodes()` - Critical 노드 찾기
- `find_critical_edges()` - Critical 엣지 찾기
- `get_timing_summary()` - 타이밍 요약

#### 계층 쿼리 메서드
- `get_hierarchy_children()` - 직계 자식 노드
- `get_hierarchy_subtree()` - 모든 하위 노드

#### SuperGraph 쿼리 메서드
- `find_supernodes()` - SuperNode 검색
- `get_supernode()` - SuperNode 객체 반환
- `get_supernode_for_node()` - 노드가 속한 SuperNode

#### 통계 메서드
- `get_statistics()` - 그래프 통계 정보

### 결과 타입

#### PathResult
```python
- nodes: List[str]           # 경로의 노드 ID 리스트
- edges: List[str]           # 경로의 엣지 ID 리스트
- total_delay: Optional[float]  # 총 지연
- total_slack: Optional[float]  # 최소 slack
```

#### TimingQueryResult
```python
- worst_slack: Optional[float]   # 최악의 slack
- critical_nodes: List[str]      # Critical 노드 리스트
- critical_edges: List[str]      # Critical 엣지 리스트
- timing_violations: int         # 타이밍 위반 수
```

#### FanoutResult
```python
- node_id: str                # 분석 대상 노드
- fanout_count: int          # 팬아웃 수
- fanout_nodes: List[str]    # 팬아웃 노드 리스트
- max_delay: Optional[float] # 최대 지연
```

## 성능 팁

1. **인덱스 활용**: Query API는 초기화 시 entity class, 계층, relation type에 대한 인덱스를 구축합니다. 이러한 기준으로 먼저 필터링하면 빠릅니다.

2. **복합 쿼리**: 여러 조건을 한 번의 `find_nodes()` 호출로 처리하는 것이 여러 번 호출하는 것보다 빠릅니다.

3. **경로 탐색 깊이**: `find_paths()`의 `max_depth`를 적절히 설정하여 불필요한 탐색을 방지하세요.

4. **캐싱**: 반복적으로 사용하는 쿼리 결과는 변수에 저장해두세요.

## 문제 해결

### Q: "순환 import" 에러가 발생합니다
A: `dkg.query_api`를 직접 임포트하세요:
```python
from dkg.query_api import DKGQuery, create_query
```

### Q: SuperGraph 관련 기능이 작동하지 않습니다
A: SuperGraph를 먼저 구축해야 합니다:
```python
pipeline.build_supergraph()
query = create_query(nodes, edges, pipeline.supergraph)
```

### Q: 검색 결과가 비어 있습니다
A: 패턴 매칭이 정확한지 확인하세요. 와일드카드 `*`를 사용하거나 `custom_filter`로 디버깅하세요.

## 추가 예제

더 많은 예제는 `dkg/query_api_example.py` 파일을 참조하세요:

```bash
python -m dkg.query_api_example
```
