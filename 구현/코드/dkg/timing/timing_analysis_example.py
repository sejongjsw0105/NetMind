"""
Timing Analysis 사용 예제

이 예제는 전체 Timing 분석 파이프라인의 사용법을 보여줍니다:
1. DKG 그래프 생성
2. Timing Report 파싱
3. Constraint 파일 처리
4. SuperGraph 생성
5. Timing Metrics 집계 및 부착
6. 결과 조회 및 출력
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dkg.builders.constraint_projector import (
    ClockConstraint,
    ConstraintProjector,
    FalsePathConstraint,
)
from dkg.core.graph import DKGEdge, DKGNode, EdgeFlowType, EntityClass, RelationType
from dkg.builders.graph_updater import GraphUpdater
from dkg.builders.supergraph import (
    GraphViewType,
    SuperGraph,
    ViewBuilder,
    get_timing_analysis_from_superedge,
    get_timing_analysis_from_supernode,
)
from dkg.timing.timing_aggregator import aggregate_timing_to_supergraph
from dkg.timing.timing_integration import TimingAnalysisPipeline, quick_timing_analysis


def example_basic_timing_analysis():
    """기본 타이밍 분석 예제"""
    print("=" * 80)
    print("Example 1: Basic Timing Analysis")
    print("=" * 80)

    # 1. 간단한 DKG 그래프 생성
    nodes = {
        "n1": DKGNode(
            node_id="n1",
            entity_class=EntityClass.FLIP_FLOP,
            hier_path="cpu/pc_reg",
            local_name="pc_reg",
            slack=1.5,
            arrival_time=8.5,
            required_time=10.0,
        ),
        "n2": DKGNode(
            node_id="n2",
            entity_class=EntityClass.LUT,
            hier_path="cpu/alu/add",
            local_name="add",
            slack=0.2,
            arrival_time=9.8,
            required_time=10.0,
        ),
        "n3": DKGNode(
            node_id="n3",
            entity_class=EntityClass.FLIP_FLOP,
            hier_path="cpu/result_reg",
            local_name="result_reg",
            slack=-0.5,  # Timing violation!
            arrival_time=10.5,
            required_time=10.0,
        ),
    }

    edges = {
        "e1": DKGEdge(
            edge_id="e1",
            src_node="n1",
            dst_node="n2",
            relation_type=RelationType.DATA,
            flow_type=EdgeFlowType.COMBINATIONAL,
            signal_name="pc_out",
            canonical_name="pc_reg → add",
            delay=1.3,
        ),
        "e2": DKGEdge(
            edge_id="e2",
            src_node="n2",
            dst_node="n3",
            relation_type=RelationType.DATA,
            flow_type=EdgeFlowType.SEQ_CAPTURE,
            signal_name="result",
            canonical_name="add → result_reg",
            delay=0.7,
        ),
    }

    # GraphUpdater 초기화
    updater = GraphUpdater(nodes, edges)

    # 2. SuperGraph 생성
    view_builder = ViewBuilder(nodes, edges, GraphViewType.Connectivity)
    supergraph = view_builder.build()

    print(f"\nSuperGraph created:")
    print(f"  SuperNodes: {len(supergraph.super_nodes)}")
    print(f"  SuperEdges: {len(supergraph.super_edges)}")

    # 3. Timing Metrics 집계 및 부착
    aggregate_timing_to_supergraph(
        supergraph,
        nodes,
        edges,
        clock_period=10.0,
        critical_threshold=0.0,
        near_critical_alpha=0.1,
    )

    # 4. 결과 조회
    print("\n[SuperNode Timing Metrics]")
    for sn_id, sn in supergraph.super_nodes.items():
        metrics = get_timing_analysis_from_supernode(sn)
        if metrics:
            print(f"\n  {sn_id} ({sn.super_class.value}):")
            print(f"    Min Slack:            {metrics.min_slack:.3f} ns")
            print(f"    P5 Slack:             {metrics.p5_slack:.3f} ns")
            print(f"    Max Arrival Time:     {metrics.max_arrival_time:.3f} ns")
            print(f"    Critical Node Ratio:  {metrics.critical_node_ratio:.2%}")
            print(f"    Timing Risk Score:    {metrics.timing_risk_score:.2f}")

    print("\n[SuperEdge Timing Metrics]")
    for (src, dst), se in supergraph.super_edges.items():
        metrics = get_timing_analysis_from_superedge(se)
        if metrics:
            print(f"\n  {src} → {dst}:")
            print(f"    Max Delay:     {metrics.max_delay:.3f} ns")
            print(f"    P95 Delay:     {metrics.p95_delay:.3f} ns")
            print(f"    Flow Types:    {dict(metrics.flow_type_histogram)}")


def example_constraint_projection():
    """Constraint 투영 예제"""
    print("\n\n" + "=" * 80)
    print("Example 2: Constraint Projection")
    print("=" * 80)

    # 1. DKG 그래프 생성
    nodes = {
        "clk_port": DKGNode(
            node_id="clk_port",
            entity_class=EntityClass.IO_PORT,
            hier_path="clk",
            local_name="clk",
        ),
        "reset_ff": DKGNode(
            node_id="reset_ff",
            entity_class=EntityClass.FLIP_FLOP,
            hier_path="system/reset_reg",
            local_name="reset_reg",
        ),
        "data_ff": DKGNode(
            node_id="data_ff",
            entity_class=EntityClass.FLIP_FLOP,
            hier_path="system/data_reg",
            local_name="data_reg",
        ),
    }

    edges = {
        "e_reset": DKGEdge(
            edge_id="e_reset",
            src_node="reset_ff",
            dst_node="data_ff",
            relation_type=RelationType.RESET,
            flow_type=EdgeFlowType.ASYNC_RESET,
            signal_name="reset",
            canonical_name="reset_reg → data_reg",
        ),
    }

    updater = GraphUpdater(nodes, edges)

    # 2. Constraint Projector 생성
    projector = ConstraintProjector(nodes, edges, updater)

    # 3. Clock Constraint 투영
    print("\n[Clock Constraint]")
    clock_constraint = ClockConstraint(
        clock_name="sys_clk", period=10.0, target_ports=["clk"]
    )
    projector.project_clock_constraint(clock_constraint, "example.sdc", 1)

    clk_node = nodes["clk_port"]
    print(f"  Clock Domain: {clk_node.clock_domain}")
    print(f"  Clock Period: {clk_node.attributes.get('clock_period', 'N/A')} ns")

    # 4. False Path Constraint 투영
    print("\n[False Path Constraint]")
    false_path = FalsePathConstraint(
        from_targets=["system/reset_reg"], to_targets=["system/data_reg"]
    )
    projector.project_false_path_constraint(false_path, "example.sdc", 5)

    reset_edge = edges["e_reset"]
    print(f"  Timing Exception: {reset_edge.timing_exception}")


def example_full_pipeline():
    """전체 파이프라인 예제"""
    print("\n\n" + "=" * 80)
    print("Example 3: Full Timing Analysis Pipeline")
    print("=" * 80)

    # 1. DKG 그래프 생성
    nodes = {
        "ff1": DKGNode(
            node_id="ff1",
            entity_class=EntityClass.FLIP_FLOP,
            hier_path="cpu/stage1/ff",
            local_name="ff1",
        ),
        "lut1": DKGNode(
            node_id="lut1",
            entity_class=EntityClass.LUT,
            hier_path="cpu/stage2/lut",
            local_name="lut1",
        ),
        "ff2": DKGNode(
            node_id="ff2",
            entity_class=EntityClass.FLIP_FLOP,
            hier_path="cpu/stage3/ff",
            local_name="ff2",
        ),
    }

    edges = {
        "e1": DKGEdge(
            edge_id="e1",
            src_node="ff1",
            dst_node="lut1",
            relation_type=RelationType.DATA,
            flow_type=EdgeFlowType.COMBINATIONAL,
            signal_name="data1",
            canonical_name="ff1 → lut1",
        ),
        "e2": DKGEdge(
            edge_id="e2",
            src_node="lut1",
            dst_node="ff2",
            relation_type=RelationType.DATA,
            flow_type=EdgeFlowType.SEQ_CAPTURE,
            signal_name="data2",
            canonical_name="lut1 → ff2",
        ),
    }

    updater = GraphUpdater(nodes, edges)

    # 2. TimingAnalysisPipeline 생성
    pipeline = TimingAnalysisPipeline(nodes, edges, updater)

    print("\n[Pipeline Created]")

    # 3. SuperGraph 생성
    view_builder = ViewBuilder(nodes, edges, GraphViewType.Connectivity)
    supergraph = view_builder.build()

    print(f"  SuperNodes: {len(supergraph.super_nodes)}")
    print(f"  SuperEdges: {len(supergraph.super_edges)}")

    # 4. Timing Metrics 부착
    # (실제로는 timing report를 파싱하지만, 여기서는 이미 노드에 데이터가 있다고 가정)
    pipeline.attach_timing_to_supergraph(supergraph, clock_period=10.0)

    # 5. Timing Summary 출력
    pipeline.print_timing_report(supergraph, clock_period=10.0)


def example_quick_api():
    """Quick Start API 예제"""
    print("\n\n" + "=" * 80)
    print("Example 4: Quick Timing Analysis API")
    print("=" * 80)

    # 간단한 그래프 생성
    nodes = {
        "n1": DKGNode(
            node_id="n1",
            entity_class=EntityClass.FLIP_FLOP,
            hier_path="top/ff1",
            local_name="ff1",
            slack=2.0,
        ),
    }

    edges = {}
    updater = GraphUpdater(nodes, edges)

    view_builder = ViewBuilder(nodes, edges, GraphViewType.Connectivity)
    supergraph = view_builder.build()

    # Quick API 사용
    # summary = quick_timing_analysis(
    #     nodes, edges, updater, supergraph,
    #     timing_report_path="design.timing_rpt",  # 실제 파일이 있어야 함
    #     constraint_path="design.sdc",            # 실제 파일이 있어야 함
    #     clock_period=10.0
    # )

    print("\n[Quick API Usage]")
    print("  quick_timing_analysis() can process:")
    print("    - Timing reports (Vivado/PrimeTime)")
    print("    - Constraint files (SDC/XDC)")
    print("    - Automatic metrics aggregation")
    print("    - Formatted report output")


if __name__ == "__main__":
    example_basic_timing_analysis()
    example_constraint_projection()
    example_full_pipeline()
    example_quick_api()

    print("\n\n" + "=" * 80)
    print("All examples completed!")
    print("=" * 80)
