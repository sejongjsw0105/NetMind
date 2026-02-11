from __future__ import annotations
from dkg.utils.config import YosysConfig
from dkg.utils.debug import (
    plot_subgraph,
    print_fanout_summary,
    print_graph_summary,
    print_sample_node,
    trace_signal,
)
from dkg.pipeline import DKGPipeline
from dkg.builders.supergraph import GraphViewType, GraphContext
from dkg.query_api import create_query
from dkg.core.graph import EntityClass

# 설정은 사용자 환경에 맞게 유지
DEFAULT_CONFIG = YosysConfig(
    src_dir_win=r"C:\Users\User\NetMind\구현\예시",
    out_json_win=r"C:\Users\User\NetMind\구현\design.json",
    top_module="riscvsingle",
)

def main(config: YosysConfig, debug: bool = True) -> None:
    # 1. 파이프라인 초기화
    pipeline = DKGPipeline(config)
    print("🚀 DKG Pipeline Initialized.")

    # 2. Stage 1: RTL 파싱 (필수)
    pipeline.run_rtl_stage()
    print("✅ RTL Stage Completed.")

    # 3. (옵션) 제약 조건 및 타이밍 리포트 추가
    # 실제 파일 경로가 있다면 아래 주석을 해제하고 경로를 수정하세요.
    # pipeline.add_constraints(r"C:\Path\To\design.sdc")
    # pipeline.add_constraints(r"C:\Path\To\design.xdc")
    # pipeline.add_timing_report(r"C:\Path\To\timing.rpt")
    # pipeline.add_floorplan(r"C:\Path\To\design.tcl")  # Design Context 감지용

    # 4. Stage 4: SuperGraph 구축 (Task 12: 정책 분기 적용)
    # ViewType과 Context는 필요에 따라 변경 가능 (기본값: Connectivity, Design)
    pipeline.build_supergraph(view=GraphViewType.Connectivity)
    
    # 그래프 데이터 가져오기
    nodes, edges = pipeline.get_graph()
    supergraph = pipeline.supergraph

    # 5. 디버그 출력
    if debug:
        print("\n" + "="*40)
        print("🔍 Debug Summary")
        print("="*40)
        
        # 기본 그래프 요약
        # (Note: wires/cells 정보는 pipeline 내부에 캡슐화되어 있어 
        #  debug.py 함수들이 wires/cells를 요구하면 직접 접근이 어려울 수 있음.
        #  여기서는 nodes/edges 위주로 확인합니다.)
        print(f"DKG Nodes: {len(nodes)}")
        print(f"DKG Edges: {len(edges)}")
        
        if supergraph:
            print("-" * 20)
            print(f"Super Nodes: {len(supergraph.super_nodes)}")
            print(f"Super Edges: {len(supergraph.super_edges)}")
            print("-" * 20)
            
            # SuperGraph 샘플 출력 (첫 3개)
            print("\n[Sample SuperNodes]")
            for i, sn in enumerate(list(supergraph.super_nodes.values())[:3]):
                print(f"  {sn.display_name} ({sn.super_class.value}): contains {len(sn.member_nodes)} nodes")

        print_sample_node(nodes, edges)
        # print_fanout_summary(wires) # wires 객체가 필요하면 pipeline 내부 접근 필요
        
        # 시각화 (Matplotlib)
        plot_subgraph(nodes, edges, limit=30)
        
        # ===== Query API Demo =====
        print("\n" + "="*40)
        print("🔍 Query API Demo")
        print("="*40)
        
        # Query API 생성
        query = create_query(nodes, edges, supergraph)
        
        # 1. 전체 통계
        stats = query.get_statistics()
        print(f"\n[Statistics]")
        print(f"  Total Nodes: {stats['total_nodes']}")
        print(f"  Total Edges: {stats['total_edges']}")
        print(f"  Nodes by Class:")
        for cls, count in list(stats['nodes_by_class'].items())[:5]:
            print(f"    {cls}: {count}")
        
        # 2. Flip-Flop 검색
        ffs = query.find_nodes(entity_class=EntityClass.FLIP_FLOP)
        print(f"\n[Flip-Flops Found: {len(ffs)}]")
        for ff_id in ffs[:3]:
            ff = query.get_node(ff_id)
            if ff:
                print(f"  - {ff.hier_path}")
        
        # 3. 타이밍 요약 (slack 정보가 있는 경우)
        timing_summary = query.get_timing_summary()
        if timing_summary.worst_slack is not None:
            print(f"\n[Timing Summary]")
            print(f"  Worst Slack: {timing_summary.worst_slack:.3f}")
            print(f"  Violations: {timing_summary.timing_violations}")
            print(f"  Critical Nodes: {len(timing_summary.critical_nodes)}")
        
        # 4. 팬아웃 분석 (첫 번째 노드)
        if nodes:
            sample_node_id = list(nodes.keys())[0]
            fanout = query.get_fanout(sample_node_id, max_depth=1)
            print(f"\n[Fanout Analysis: {sample_node_id}]")
            print(f"  Fanout Count: {fanout.fanout_count}")
            if fanout.max_delay:
                print(f"  Max Delay: {fanout.max_delay:.3f}")
        
        print("\n" + "="*40)
        print("💡 Tip: See QUERY_API_GUIDE.md for more Query API features!")
        print("="*40)

if __name__ == "__main__":
    main(DEFAULT_CONFIG, debug=True)