"""
그래프 캐싱 사용 예제

Usage:
    # 1. 그래프 구축 후 캐시 저장
    pipeline = DKGPipeline(yosys_config)
    pipeline.run_rtl_stage()
    pipeline.add_constraints("design.sdc")
    pipeline.save_cache("graph_cache.json")
    
    # 2. 캐시에서 로딩 (빠른 시작)
    pipeline = DKGPipeline.load_from_cache("graph_cache.json")
    nodes, edges = pipeline.get_graph()
"""
from pathlib import Path

from dkg.config import YosysConfig
from dkg.pipeline import DKGPipeline


def save_example():
    """그래프 구축 후 캐시 저장"""
    # Yosys JSON 파일 경로 설정
    yosys_config = YosysConfig(
        src_dir_win=".",
        out_json_win="output.json",  # Yosys로 생성한 JSON 파일
        top_module="top",
    )
    
    # 파이프라인 실행
    pipeline = DKGPipeline(yosys_config)
    
    # Stage 1: RTL 파싱
    pipeline.run_rtl_stage()
    
    # Stage 2: Constraint 추가 (선택)
    # pipeline.add_constraints("design.sdc")
    # pipeline.add_constraints("design.xdc")
    
    # Stage 3: SuperGraph 생성 (선택)
    # from dkg.supergraph import build_supergraph
    # pipeline.supergraph = build_supergraph(pipeline.nodes, pipeline.edges)
    
    # 캐시 저장
    cache_path = Path("graph_cache.json")
    pipeline.save_cache(cache_path, indent=2)  # indent=2는 디버깅용, 생략하면 압축됨
    
    print(f"✅ 그래프 캐시 저장 완료: {cache_path}")
    if pipeline.nodes and pipeline.edges:
        print(f"   - 노드 수: {len(pipeline.nodes)}")
        print(f"   - 엣지 수: {len(pipeline.edges)}")
    
    # 버전 정보 확인
    version = pipeline.compute_version()
    print(f"   - RTL 해시: {version.rtl_hash}")
    if version.constraint_hash:
        print(f"   - Constraint 해시: {version.constraint_hash}")


def load_example():
    """캐시에서 그래프 로딩"""
    cache_path = Path("graph_cache.json")
    
    if not cache_path.exists():
        print(f"❌ 캐시 파일이 없습니다: {cache_path}")
        print("   save_example()을 먼저 실행하세요.")
        return
    
    # 캐시에서 로딩 (매우 빠름!)
    pipeline = DKGPipeline.load_from_cache(cache_path)
    
    print(f"✅ 그래프 캐시 로딩 완료: {cache_path}")
    if pipeline.nodes and pipeline.edges:
        print(f"   - 노드 수: {len(pipeline.nodes)}")
        print(f"   - 엣지 수: {len(pipeline.edges)}")
    
    # SuperGraph가 있으면 표시
    if pipeline.supergraph:
        print(f"   - SuperNode 수: {len(pipeline.supergraph.super_nodes)}")
        print(f"   - SuperEdge 수: {len(pipeline.supergraph.super_edges)}")
    
    # 그래프 사용
    nodes, edges = pipeline.get_graph()
    
    # 예: 첫 10개 노드 출력
    print("\n처음 10개 노드:")
    for i, (node_id, node) in enumerate(nodes.items()):
        if i >= 10:
            break
        print(f"  - {node.canonical_name or node_id}: {node.entity_class.value}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "load":
        load_example()
    else:
        save_example()
