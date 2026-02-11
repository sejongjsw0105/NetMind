"""
DKG Query API 사용 예시
"""
from typing import Dict

from dkg.core.graph import DKGNode, DKGEdge, EntityClass
from dkg.query_api import DKGQuery, create_query
from dkg.pipeline import DKGPipeline
from dkg.utils.config import YosysConfig


def example_basic_queries():
    """기본 쿼리 예시"""
    print("=" * 80)
    print("Example 1: Basic Node and Edge Queries")
    print("=" * 80)
    
    # 실제 프로젝트에서는 DKGPipeline으로 그래프 생성
    config = YosysConfig(
        src_dir_win=r"C:\Users\User\NetMind\구현\예시",
        out_json_win=r"C:\Users\User\NetMind\구현\design.json",
        top_module="riscvsingle",
    )
    
    pipeline = DKGPipeline(config)
    pipeline.run_rtl_stage()
    nodes, edges = pipeline.get_graph()
    
    # Query API 생성
    query = create_query(nodes, edges)
    
    # 1. 모든 Flip-Flop 찾기
    print("\n[1] Finding all Flip-Flops:")
    ffs = query.find_nodes(entity_class=EntityClass.FLIP_FLOP)
    print(f"   Found {len(ffs)} flip-flops")
    for ff_id in ffs[:3]:  # 처음 3개만 출력
        ff = query.get_node(ff_id)
        if ff:
            print(f"   - {ff.hier_path}")
    
    # 2. 특정 모듈의 노드 찾기
    print("\n[2] Finding nodes in 'cpu' module:")
    cpu_nodes = query.find_nodes(hierarchy_prefix="cpu")
    print(f"   Found {len(cpu_nodes)} nodes in cpu module")
    
    # 3. 이름 패턴으로 검색
    print("\n[3] Finding nodes with 'clk' in name:")
    clk_nodes = query.find_nodes(name_pattern="*clk*")
    print(f"   Found {len(clk_nodes)} clock-related nodes")
    for node_id in clk_nodes[:3]:
        node = query.get_node(node_id)
        if node:
            print(f"   - {node.hier_path}")
    
    # 4. 통계 정보
    print("\n[4] Graph Statistics:")
    stats = query.get_statistics()
    print(f"   Total Nodes: {stats['total_nodes']}")
    print(f"   Total Edges: {stats['total_edges']}")
    print(f"   Nodes by Class:")
    for cls, count in stats['nodes_by_class'].items():
        print(f"      {cls}: {count}")
    
    print("\n" + "=" * 80 + "\n")


def example_path_finding():
    """경로 탐색 예시"""
    print("=" * 80)
    print("Example 2: Path Finding")
    print("=" * 80)
    
    # 테스트용 간단한 그래프 생성
    from dkg.core.graph import DKGNode, DKGEdge, EntityClass, RelationType, EdgeFlowType
    
    nodes = {
        "n1": DKGNode(
            node_id="n1",
            entity_class=EntityClass.FLIP_FLOP,
            hier_path="cpu/stage1/ff1",
            local_name="ff1"
        ),
        "n2": DKGNode(
            node_id="n2",
            entity_class=EntityClass.LUT,
            hier_path="cpu/stage2/lut1",
            local_name="lut1"
        ),
        "n3": DKGNode(
            node_id="n3",
            entity_class=EntityClass.LUT,
            hier_path="cpu/stage2/lut2",
            local_name="lut2"
        ),
        "n4": DKGNode(
            node_id="n4",
            entity_class=EntityClass.FLIP_FLOP,
            hier_path="cpu/stage3/ff2",
            local_name="ff2"
        ),
    }
    
    edges = {
        "e1": DKGEdge(
            edge_id="e1",
            src_node="n1",
            dst_node="n2",
            relation_type=RelationType.DATA,
            flow_type=EdgeFlowType.COMBINATIONAL,
            signal_name="data1",
            canonical_name="n1->n2",
            delay=0.5
        ),
        "e2": DKGEdge(
            edge_id="e2",
            src_node="n2",
            dst_node="n4",
            relation_type=RelationType.DATA,
            flow_type=EdgeFlowType.COMBINATIONAL,
            signal_name="data2",
            canonical_name="n2->n4",
            delay=0.3
        ),
        "e3": DKGEdge(
            edge_id="e3",
            src_node="n1",
            dst_node="n3",
            relation_type=RelationType.DATA,
            flow_type=EdgeFlowType.COMBINATIONAL,
            signal_name="data3",
            canonical_name="n1->n3",
            delay=0.4
        ),
        "e4": DKGEdge(
            edge_id="e4",
            src_node="n3",
            dst_node="n4",
            relation_type=RelationType.DATA,
            flow_type=EdgeFlowType.COMBINATIONAL,
            signal_name="data4",
            canonical_name="n3->n4",
            delay=0.6
        ),
    }
    
    # in_edges, out_edges 설정
    nodes["n1"].out_edges = ["e1", "e3"]
    nodes["n2"].in_edges = ["e1"]
    nodes["n2"].out_edges = ["e2"]
    nodes["n3"].in_edges = ["e3"]
    nodes["n3"].out_edges = ["e4"]
    nodes["n4"].in_edges = ["e2", "e4"]
    
    query = create_query(nodes, edges)
    
    # 1. 모든 경로 찾기
    print("\n[1] Finding all paths from n1 to n4:")
    paths = query.find_paths("n1", "n4")
    print(f"   Found {len(paths)} paths")
    for i, path in enumerate(paths):
        print(f"   Path {i+1}: {' -> '.join(path.nodes)}")
        print(f"           Total delay: {path.total_delay}")
    
    # 2. 최단 경로 찾기 (홉 기준)
    print("\n[2] Finding shortest path (by hops):")
    shortest = query.find_shortest_path("n1", "n4", weight="hops")
    if shortest:
        print(f"   Path: {' -> '.join(shortest.nodes)}")
        print(f"   Hops: {len(shortest) - 1}")
    
    # 3. 최단 경로 찾기 (지연 기준)
    print("\n[3] Finding shortest path (by delay):")
    fastest = query.find_shortest_path("n1", "n4", weight="delay")
    if fastest:
        print(f"   Path: {' -> '.join(fastest.nodes)}")
        print(f"   Total delay: {fastest.total_delay}")
    
    print("\n" + "=" * 80 + "\n")


def example_fanout_analysis():
    """팬아웃 분석 예시"""
    print("=" * 80)
    print("Example 3: Fanout Analysis")
    print("=" * 80)
    
    # 테스트용 그래프 (높은 팬아웃)
    from dkg.core.graph import DKGNode, DKGEdge, EntityClass, RelationType, EdgeFlowType
    
    nodes = {
        "src": DKGNode(
            node_id="src",
            entity_class=EntityClass.FLIP_FLOP,
            hier_path="cpu/source",
            local_name="source"
        ),
    }
    
    edges = {}
    
    # 10개의 팬아웃 생성
    for i in range(10):
        dst_id = f"dst{i}"
        nodes[dst_id] = DKGNode(
            node_id=dst_id,
            entity_class=EntityClass.LUT,
            hier_path=f"cpu/dest{i}",
            local_name=f"dest{i}"
        )
        
        edge_id = f"e{i}"
        edges[edge_id] = DKGEdge(
            edge_id=edge_id,
            src_node="src",
            dst_node=dst_id,
            relation_type=RelationType.DATA,
            flow_type=EdgeFlowType.COMBINATIONAL,
            signal_name=f"data{i}",
            canonical_name=f"src->dst{i}",
            delay=0.1 * (i + 1)
        )
        
        nodes["src"].out_edges.append(edge_id)
        nodes[dst_id].in_edges.append(edge_id)
    
    query = create_query(nodes, edges)
    
    # 팬아웃 분석
    print("\n[1] Analyzing fanout from 'src':")
    fanout = query.get_fanout("src")
    print(f"   Fanout count: {fanout.fanout_count}")
    print(f"   Max delay: {fanout.max_delay}")
    print(f"   Destinations: {', '.join(fanout.fanout_nodes[:5])}...")
    
    # 팬인 분석
    print("\n[2] Analyzing fanin to 'dst0':")
    fanin = query.get_fanin("dst0")
    print(f"   Fanin count: {fanin.fanout_count}")
    print(f"   Sources: {', '.join(fanin.fanout_nodes)}")
    
    print("\n" + "=" * 80 + "\n")


def example_timing_queries():
    """타이밍 쿼리 예시"""
    print("=" * 80)
    print("Example 4: Timing Queries")
    print("=" * 80)
    
    # 타이밍 정보가 있는 그래프 생성
    from dkg.core.graph import DKGNode, DKGEdge, EntityClass, RelationType, EdgeFlowType
    
    nodes = {}
    edges = {}
    
    # Critical한 노드들 생성
    for i in range(5):
        node_id = f"n{i}"
        nodes[node_id] = DKGNode(
            node_id=node_id,
            entity_class=EntityClass.FLIP_FLOP,
            hier_path=f"cpu/ff{i}",
            local_name=f"ff{i}",
            slack=0.5 - i * 0.3  # 점점 critical해짐
        )
    
    query = create_query(nodes, edges)
    
    # 1. Critical 노드 찾기
    print("\n[1] Finding critical nodes (slack <= 0.0):")
    critical = query.find_critical_nodes(slack_threshold=0.0)
    print(f"   Found {len(critical)} critical nodes")
    for node_id, slack in critical:
        node = query.get_node(node_id)
        if node:
            print(f"   - {node.hier_path}: slack = {slack:.3f}")
    
    # 2. 상위 3개 최악의 슬랙
    print("\n[2] Top 3 worst slack nodes:")
    top3 = query.find_critical_nodes(slack_threshold=1.0, top_n=3)
    for node_id, slack in top3:
        node = query.get_node(node_id)
        if node:
            print(f"   - {node.hier_path}: slack = {slack:.3f}")
    
    # 3. 타이밍 요약
    print("\n[3] Timing Summary:")
    summary = query.get_timing_summary()
    print(f"   Worst slack: {summary.worst_slack}")
    print(f"   Timing violations: {summary.timing_violations}")
    print(f"   Critical nodes: {len(summary.critical_nodes)}")
    
    print("\n" + "=" * 80 + "\n")


def example_hierarchy_queries():
    """계층 구조 쿼리 예시"""
    print("=" * 80)
    print("Example 5: Hierarchy Queries")
    print("=" * 80)
    
    from dkg.core.graph import DKGNode, EntityClass
    
    # 계층 구조를 가진 노드들 생성
    nodes = {
        "n1": DKGNode(
            node_id="n1",
            entity_class=EntityClass.MODULE_INSTANCE,
            hier_path="cpu",
            local_name="cpu"
        ),
        "n2": DKGNode(
            node_id="n2",
            entity_class=EntityClass.MODULE_INSTANCE,
            hier_path="cpu/alu",
            local_name="alu"
        ),
        "n3": DKGNode(
            node_id="n3",
            entity_class=EntityClass.FLIP_FLOP,
            hier_path="cpu/alu/ff1",
            local_name="ff1"
        ),
        "n4": DKGNode(
            node_id="n4",
            entity_class=EntityClass.FLIP_FLOP,
            hier_path="cpu/alu/ff2",
            local_name="ff2"
        ),
        "n5": DKGNode(
            node_id="n5",
            entity_class=EntityClass.MODULE_INSTANCE,
            hier_path="cpu/mem",
            local_name="mem"
        ),
        "n6": DKGNode(
            node_id="n6",
            entity_class=EntityClass.BRAM,
            hier_path="cpu/mem/ram1",
            local_name="ram1"
        ),
    }
    
    query = create_query(nodes, {})
    
    # 1. 직계 자식 찾기
    print("\n[1] Finding direct children of 'cpu':")
    children = query.get_hierarchy_children("cpu")
    print(f"   Found {len(children)} direct children")
    for child_id in children:
        child = query.get_node(child_id)
        if child:
            print(f"   - {child.hier_path}")
    
    # 2. 모듈 별 노드 찾기
    print("\n[2] Finding all nodes under 'cpu/alu':")
    alu_nodes = query.get_hierarchy_subtree("cpu/alu")
    print(f"   Found {len(alu_nodes)} nodes")
    for node_id in alu_nodes:
        node = query.get_node(node_id)
        if node:
            print(f"   - {node.hier_path} ({node.entity_class.value})")
    
    # 3. 계층별 통계
    print("\n[3] Node count by hierarchy:")
    hierarchies = ["cpu", "cpu/alu", "cpu/mem"]
    for hier in hierarchies:
        count = len(query.get_hierarchy_subtree(hier))
        print(f"   {hier}: {count} nodes")
    
    print("\n" + "=" * 80 + "\n")


def example_custom_filters():
    """사용자 정의 필터 예시"""
    print("=" * 80)
    print("Example 6: Custom Filters")
    print("=" * 80)
    
    from dkg.core.graph import DKGNode, EntityClass
    
    nodes = {}
    for i in range(10):
        nodes[f"n{i}"] = DKGNode(
            node_id=f"n{i}",
            entity_class=EntityClass.FLIP_FLOP if i % 2 == 0 else EntityClass.LUT,
            hier_path=f"cpu/stage{i//3}/node{i}",
            local_name=f"node{i}",
            slack=1.0 - i * 0.2,
            arrival_time=float(i)
        )
        nodes[f"n{i}"].parameters = {"width": i + 1}
    
    query = create_query(nodes, {})
    
    # 1. 파라미터 기반 필터
    print("\n[1] Finding nodes with width > 5:")
    def is_wide_node(n):
        width = n.parameters.get("width")
        return isinstance(width, int) and width > 5
    wide_nodes = query.find_nodes(custom_filter=is_wide_node)
    print(f"   Found {len(wide_nodes)} nodes")
    for node_id in wide_nodes:
        node = query.get_node(node_id)
        if node:
            print(f"   - {node.local_name}: width={node.parameters['width']}")
    
    # 2. 복합 조건 필터
    print("\n[2] Finding flip-flops with slack < 0.5 and arrival_time > 5:")
    complex_filter = query.find_nodes(
        entity_class=EntityClass.FLIP_FLOP,
        custom_filter=lambda n: (
            n.slack is not None and n.slack < 0.5 and
            n.arrival_time is not None and n.arrival_time > 5
        )
    )
    print(f"   Found {len(complex_filter)} nodes")
    for node_id in complex_filter:
        node = query.get_node(node_id)
        if node:
            print(f"   - {node.local_name}: slack={node.slack}, arrival={node.arrival_time}")
    
    # 3. 이름 기반 복잡한 필터
    print("\n[3] Finding nodes in even-numbered stages:")
    even_stages = query.find_nodes(
        custom_filter=lambda n: any(
            f"stage{i}" in n.hier_path for i in [0, 2, 4, 6, 8]
        )
    )
    print(f"   Found {len(even_stages)} nodes")
    
    print("\n" + "=" * 80 + "\n")


def main():
    """모든 예시 실행"""
    try:
        # Example 1은 실제 프로젝트 필요 - 스킵 가능
        # example_basic_queries()
        pass
    except Exception as e:
        print(f"Example 1 skipped (needs actual project): {e}\n")
    
    example_path_finding()
    example_fanout_analysis()
    example_timing_queries()
    example_hierarchy_queries()
    example_custom_filters()
    
    print("\n" + "=" * 80)
    print("All examples completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()
