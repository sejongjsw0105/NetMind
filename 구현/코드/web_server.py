"""
DKG Web Server

Flask 기반 웹 서버로 Query API를 RESTful API로 노출
"""
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from typing import Dict, List, Any
import json
from pathlib import Path

from dkg.pipeline import DKGPipeline
from dkg.utils.config import YosysConfig
from dkg.query_api import create_query
from dkg.core.graph import EntityClass, RelationType, EdgeFlowType
from dkg.builders.supergraph import GraphViewType

app = Flask(__name__, static_folder='web', static_url_path='')
CORS(app)

# 전역 변수로 그래프 저장
query_api = None
nodes = None
edges = None
supergraph = None

def initialize_graph(config: YosysConfig):
    """그래프 초기화"""
    global query_api, nodes, edges, supergraph
    
    pipeline = DKGPipeline(config)
    pipeline.run_rtl_stage()
    
    # 제약 조건 추가 (파일이 있는 경우)
    # pipeline.add_constraints("path/to/constraints.sdc")
    
    # SuperGraph 구축
    pipeline.build_supergraph(view=GraphViewType.Connectivity)
    
    nodes, edges = pipeline.get_graph()
    supergraph = pipeline.supergraph
    query_api = create_query(nodes, edges, supergraph)
    
    print(f"✅ Graph initialized: {len(nodes)} nodes, {len(edges)} edges")


# ============================================================================
# Helper Functions
# ============================================================================

def node_to_dict(node_id: str) -> Dict[str, Any]:
    """노드를 JSON 직렬화 가능한 딕셔너리로 변환"""
    if nodes is None:
        raise RuntimeError("Graph not initialized")
    node = nodes[node_id]
    return {
        'id': node_id,
        'label': node.local_name,
        'entity_class': node.entity_class.value,
        'hier_path': node.hier_path,
        'canonical_name': node.canonical_name,
        'slack': node.slack,
        'arrival_time': node.arrival_time,
        'required_time': node.required_time,
        'clock_domain': node.clock_domain,
        'parameters': node.parameters,
        'attributes': node.attributes,
    }

def edge_to_dict(edge_id: str) -> Dict[str, Any]:
    """엣지를 JSON 직렬화 가능한 딕셔너리로 변환"""
    if edges is None:
        raise RuntimeError("Graph not initialized")
    edge = edges[edge_id]
    return {
        'id': edge_id,
        'source': edge.src_node,
        'target': edge.dst_node,
        'signal_name': edge.signal_name,
        'relation_type': edge.relation_type.value,
        'flow_type': edge.flow_type.value,
        'delay': edge.delay,
        'fanout_count': edge.fanout_count,
        'clock_signal': edge.clock_signal,
    }


# ============================================================================
# API Endpoints
# ============================================================================

@app.route('/')
def index():
    """메인 페이지"""
    return send_from_directory('web', 'index.html')

@app.route('/api/statistics')
def get_statistics():
    """그래프 전체 통계"""
    if query_api is None:
        return jsonify({'error': 'Graph not initialized'}), 500
    
    stats = query_api.get_statistics()
    return jsonify(stats)

@app.route('/api/nodes')
def get_nodes():
    """모든 노드 반환 (필터링 지원)"""
    if query_api is None:
        return jsonify({'error': 'Graph not initialized'}), 500
    
    # 쿼리 파라미터
    entity_class = request.args.get('entity_class')
    name_pattern = request.args.get('name_pattern')
    hierarchy = request.args.get('hierarchy')
    slack_min = request.args.get('slack_min', type=float)
    slack_max = request.args.get('slack_max', type=float)
    
    # 필터 적용
    kwargs = {}
    if entity_class:
        kwargs['entity_class'] = EntityClass(entity_class)
    if name_pattern:
        kwargs['name_pattern'] = name_pattern
    if hierarchy:
        kwargs['hierarchy_prefix'] = hierarchy
    if slack_min is not None and slack_max is not None:
        kwargs['slack_range'] = (slack_min, slack_max)
    
    node_ids = query_api.find_nodes(**kwargs)
    
    # 결과 제한 (성능)
    limit = request.args.get('limit', 100, type=int)
    node_ids = node_ids[:limit]
    
    result = [node_to_dict(nid) for nid in node_ids]
    return jsonify({
        'nodes': result,
        'count': len(node_ids),
        'total': len(nodes) if nodes else 0
    })

@app.route('/api/edges')
def get_edges():
    """엣지 반환 (필터링 지원)"""
    if query_api is None:
        return jsonify({'error': 'Graph not initialized'}), 500
    
    src_node = request.args.get('src_node')
    dst_node = request.args.get('dst_node')
    relation_type = request.args.get('relation_type')
    
    kwargs = {}
    if src_node:
        kwargs['src_node'] = src_node
    if dst_node:
        kwargs['dst_node'] = dst_node
    if relation_type:
        kwargs['relation_type'] = RelationType(relation_type)
    
    edge_ids = query_api.find_edges(**kwargs)
    
    limit = request.args.get('limit', 200, type=int)
    edge_ids = edge_ids[:limit]
    
    result = [edge_to_dict(eid) for eid in edge_ids]
    return jsonify({
        'edges': result,
        'count': len(edge_ids)
    })

@app.route('/api/graph')
def get_graph():
    """전체 그래프 (노드 + 엣지)"""
    if query_api is None:
        return jsonify({'error': 'Graph not initialized'}), 500
    
    # 파라미터로 서브그래프 선택
    hierarchy = request.args.get('hierarchy')
    entity_class = request.args.get('entity_class')
    limit = request.args.get('limit', 100, type=int)
    
    # 노드 필터링
    kwargs = {}
    if hierarchy:
        kwargs['hierarchy_prefix'] = hierarchy
    if entity_class:
        kwargs['entity_class'] = EntityClass(entity_class)
    
    node_ids = query_api.find_nodes(**kwargs)[:limit]
    node_ids_set = set(node_ids)
    
    # 노드 간 엣지만 선택
    edge_ids = []
    if edges is not None:
        for edge_id, edge in edges.items():
            if edge.src_node in node_ids_set and edge.dst_node in node_ids_set:
                edge_ids.append(edge_id)
    
    return jsonify({
        'nodes': [node_to_dict(nid) for nid in node_ids],
        'edges': [edge_to_dict(eid) for eid in edge_ids]
    })

@app.route('/api/node/<node_id>')
def get_node_details(node_id):
    """특정 노드의 상세 정보"""
    if query_api is None:
        return jsonify({'error': 'Graph not initialized'}), 500
    
    node = query_api.get_node(node_id)
    if not node:
        return jsonify({'error': 'Node not found'}), 404
    
    # 팬인/팬아웃 정보
    fanout = query_api.get_fanout(node_id, max_depth=1)
    fanin = query_api.get_fanin(node_id, max_depth=1)
    
    result = node_to_dict(node_id)
    result['fanout'] = {
        'count': fanout.fanout_count,
        'nodes': fanout.fanout_nodes,
        'max_delay': fanout.max_delay
    }
    result['fanin'] = {
        'count': fanin.fanout_count,
        'nodes': fanin.fanout_nodes,
        'max_delay': fanin.max_delay
    }
    
    return jsonify(result)

@app.route('/api/paths')
def find_paths():
    """두 노드 사이의 경로 찾기"""
    if query_api is None:
        return jsonify({'error': 'Graph not initialized'}), 500
    
    start = request.args.get('start')
    end = request.args.get('end')
    max_depth = request.args.get('max_depth', 10, type=int)
    
    if not start or not end:
        return jsonify({'error': 'start and end parameters required'}), 400
    
    paths = query_api.find_paths(start, end, max_depth=max_depth)
    
    result = []
    for path in paths:
        result.append({
            'nodes': path.nodes,
            'edges': path.edges,
            'total_delay': path.total_delay,
            'total_slack': path.total_slack,
            'length': len(path)
        })
    
    return jsonify({
        'paths': result,
        'count': len(result)
    })

@app.route('/api/critical/nodes')
def get_critical_nodes():
    """Critical 노드 목록"""
    if query_api is None:
        return jsonify({'error': 'Graph not initialized'}), 500
    
    threshold = request.args.get('threshold', 0.0, type=float)
    top_n = request.args.get('top_n', type=int)
    
    critical = query_api.find_critical_nodes(
        slack_threshold=threshold,
        top_n=top_n
    )
    
    result = []
    for node_id, slack in critical:
        node_dict = node_to_dict(node_id)
        node_dict['slack'] = slack
        result.append(node_dict)
    
    return jsonify({
        'critical_nodes': result,
        'count': len(result)
    })

@app.route('/api/critical/edges')
def get_critical_edges():
    """Critical 엣지 목록"""
    if query_api is None:
        return jsonify({'error': 'Graph not initialized'}), 500
    
    threshold = request.args.get('threshold', type=float)
    top_n = request.args.get('top_n', type=int)
    
    critical = query_api.find_critical_edges(
        delay_threshold=threshold,
        top_n=top_n
    )
    
    result = []
    for edge_id, delay in critical:
        edge_dict = edge_to_dict(edge_id)
        edge_dict['delay'] = delay
        result.append(edge_dict)
    
    return jsonify({
        'critical_edges': result,
        'count': len(result)
    })

@app.route('/api/timing/summary')
def get_timing_summary():
    """타이밍 요약"""
    if query_api is None:
        return jsonify({'error': 'Graph not initialized'}), 500
    
    summary = query_api.get_timing_summary()
    
    return jsonify({
        'worst_slack': summary.worst_slack,
        'timing_violations': summary.timing_violations,
        'critical_nodes_count': len(summary.critical_nodes),
        'critical_edges_count': len(summary.critical_edges)
    })

@app.route('/api/search')
def search():
    """노드 검색"""
    if query_api is None:
        return jsonify({'error': 'Graph not initialized'}), 500
    
    query = request.args.get('q', '')
    
    if not query:
        return jsonify({'results': []})
    
    # 이름으로 검색
    node_id = query_api.find_node_by_name(query)
    if node_id:
        return jsonify({'results': [node_to_dict(node_id)]})
    
    # 패턴 검색
    pattern = f"*{query}*"
    node_ids = query_api.find_nodes(name_pattern=pattern)[:20]
    
    results = [node_to_dict(nid) for nid in node_ids]
    return jsonify({'results': results})

@app.route('/api/hierarchy')
def get_hierarchy():
    """계층 구조 트리"""
    if query_api is None:
        return jsonify({'error': 'Graph not initialized'}), 500
    
    parent = request.args.get('parent', '')
    
    if parent:
        children = query_api.get_hierarchy_children(parent)
    else:
        # 루트 노드들 찾기
        children = []
        if nodes is not None:
            for node_id, node in nodes.items():
                if '/' not in node.hier_path:
                    children.append(node_id)
    
    result = []
    if nodes is not None:
        for child_id in children:
            node = nodes[child_id]
            # 자식이 있는지 확인
            has_children = len(query_api.get_hierarchy_children(node.hier_path)) > 0
            result.append({
                'id': child_id,
                'label': node.local_name,
                'path': node.hier_path,
                'has_children': has_children
            })
    
    return jsonify({'children': result})

@app.route('/api/neighborhood')
def get_neighborhood():
    """노드 주변 이웃 그래프"""
    if query_api is None:
        return jsonify({'error': 'Graph not initialized'}), 500
    
    node_id = request.args.get('node_id')
    depth = request.args.get('depth', 1, type=int)
    
    if not node_id:
        return jsonify({'error': 'node_id required'}), 400
    
    # 팬아웃과 팬인 모두 가져오기
    fanout = query_api.get_fanout(node_id, max_depth=depth)
    fanin = query_api.get_fanin(node_id, max_depth=depth)
    
    # 모든 관련 노드
    all_nodes = set([node_id] + fanout.fanout_nodes + fanin.fanout_nodes)
    
    # 노드 간 엣지 찾기
    edge_ids = []
    if edges is not None:
        for eid, edge in edges.items():
            if edge.src_node in all_nodes and edge.dst_node in all_nodes:
                edge_ids.append(eid)
    
    return jsonify({
        'nodes': [node_to_dict(nid) for nid in all_nodes],
        'edges': [edge_to_dict(eid) for eid in edge_ids]
    })

@app.route('/api/node/<node_id>/hop_limited')
def get_hop_limited_graph(node_id):
    """특정 노드에서 N-홉 이내의 그래프"""
    if query_api is None:
        return jsonify({'error': 'Graph not initialized'}), 500
    
    hops = request.args.get('hops', 2, type=int)
    
    if node_id not in nodes:
        return jsonify({'error': 'Node not found'}), 404
    
    # 팬아웃과 팬인 모두 가져오기
    fanout = query_api.get_fanout(node_id, max_depth=hops)
    fanin = query_api.get_fanin(node_id, max_depth=hops)
    
    all_nodes = set([node_id] + fanout.fanout_nodes + fanin.fanout_nodes)
    
    # 노드 간 엣지 찾기
    edge_ids = []
    if edges is not None:
        for eid, edge in edges.items():
            if edge.src_node in all_nodes and edge.dst_node in all_nodes:
                edge_ids.append(eid)
    
    return jsonify({
        'nodes': [node_to_dict(nid) for nid in all_nodes],
        'edges': [edge_to_dict(eid) for eid in edge_ids]
    })

@app.route('/api/node/<node_id>/internal')
def get_node_internal(node_id):
    """노드 내부 그래프 (SuperNode의 구성 노드들)"""
    if query_api is None or supergraph is None:
        return jsonify({'error': 'Graph not initialized'}), 500
    
    # SuperNode로 변환
    supernode_id = query_api.get_supernode_for_node(node_id)
    if supernode_id is None:
        return jsonify({'error': 'Not a supernode member'}), 404
    
    supernode = query_api.get_supernode(supernode_id)
    if supernode is None:
        return jsonify({'error': 'SuperNode not found'}), 404
    
    # 내부 노드들 (member_nodes 사용)
    internal_nodes = list(supernode.member_nodes)
    internal_edges = []
    
    # 내부 노드 간 엣지 찾기
    if edges is not None:
        for eid, edge in edges.items():
            if edge.src_node in internal_nodes and edge.dst_node in internal_nodes:
                internal_edges.append(eid)
    
    return jsonify({
        'nodes': [node_to_dict(nid) for nid in internal_nodes],
        'edges': [edge_to_dict(eid) for eid in internal_edges],
        'supernode_id': supernode_id,
        'super_class': supernode.super_class.value
    })

@app.route('/api/node/<node_id>/analysis')
def get_node_analysis(node_id):
    """노드의 analysis 정보"""
    if query_api is None:
        return jsonify({'error': 'Graph not initialized'}), 500
    
    node = query_api.get_node(node_id)
    if node is None:
        return jsonify({'error': 'Node not found'}), 404
    
    # SuperNode analysis 가져오기
    analysis_data = {}
    if supergraph is not None:
        supernode_id = query_api.get_supernode_for_node(node_id)
        if supernode_id:
            supernode = query_api.get_supernode(supernode_id)
            if supernode:
                analysis_data = {
                    kind.value: data 
                    for kind, data in supernode.analysis.items()
                }
    
    return jsonify({
        'node_id': node_id,
        'analysis': analysis_data,
        'attributes': node.attributes,
        'parameters': node.parameters
    })

@app.route('/api/supernodes')
def get_supernodes():
    """모든 SuperNode 리스트"""
    if supergraph is None:
        return jsonify({'error': 'SuperGraph not initialized'}), 500
    
    supernodes_list = []
    for sn_id, sn in supergraph.super_nodes.items():
        supernodes_list.append({
            'id': sn_id,
            'super_class': sn.super_class.value,
            'node_count': len(sn.member_nodes)
        })
    
    return jsonify({'supernodes': supernodes_list})

@app.route('/api/query', methods=['POST'])
def execute_query():
    """자연어 쿼리 실행"""
    if query_api is None:
        return jsonify({'error': 'Graph not initialized'}), 500
    
    data = request.get_json()
    query_text = data.get('query', '')
    
    # 간단한 쿼리 파싱
    results = {'type': 'unknown', 'data': []}
    
    if 'flip' in query_text.lower() or 'ff' in query_text.lower():
        from dkg.core.graph import EntityClass
        node_ids = query_api.find_nodes(entity_class=EntityClass.FLIP_FLOP)
        results = {
            'type': 'nodes',
            'data': [node_to_dict(nid) for nid in node_ids[:50]]
        }
    elif 'critical' in query_text.lower():
        critical = query_api.find_critical_nodes(slack_threshold=0.5, top_n=50)
        results = {
            'type': 'critical_nodes',
            'data': [{'id': nid, 'slack': slack} for nid, slack in critical]
        }
    elif 'path' in query_text.lower():
        stats = query_api.get_statistics()
        results = {
            'type': 'statistics',
            'data': stats
        }
    else:
        results = {
            'type': 'text',
            'data': f"Query received: {query_text}. Available queries: 'flip flops', 'critical nodes', 'path statistics'"
        }
    
    return jsonify(results)

@app.route('/api/node/<node_id>/provenance')
def get_node_provenance(node_id):
    """노드의 Provenance 정보"""
    if query_api is None:
        return jsonify({'error': 'Graph not initialized'}), 500
    
    node = query_api.get_node(node_id)
    if node is None:
        return jsonify({'error': 'Node not found'}), 404
    
    provenance_info = {
        'node_id': node_id,
        'provenance': None
    }
    
    # Provenance 정보 추출
    if hasattr(node, 'provenances') and node.provenances:
        # 첫 번째 provenance 사용
        prov = node.provenances[0]
        provenance_info['provenance'] = {
            'file': prov.origin_file if hasattr(prov, 'origin_file') else None,
            'line': prov.origin_line if hasattr(prov, 'origin_line') else None,
            'stage': prov.tool_stage if hasattr(prov, 'tool_stage') else None,
            'confidence': prov.confidence if hasattr(prov, 'confidence') else None
        }
    
    return jsonify(provenance_info)

@app.route('/api/critical/path')
def get_critical_path():
    """가장 Critical한 경로 찾기"""
    if query_api is None:
        return jsonify({'error': 'Graph not initialized'}), 500
    
    # Worst slack 노드들 찾기
    critical_nodes = query_api.find_critical_nodes(slack_threshold=0.0, top_n=10)
    
    if len(critical_nodes) < 2:
        return jsonify({'error': 'Not enough critical nodes'}), 404
    
    # 첫 번째와 마지막 critical 노드 사이의 경로 찾기
    start_node = critical_nodes[0][0]
    end_node = critical_nodes[-1][0]
    
    paths = query_api.find_paths(start_node, end_node, max_depth=20)
    
    if not paths:
        return jsonify({'error': 'No path found'}), 404
    
    # 가장 slack이 낮은 경로 선택
    worst_path = min(paths, key=lambda p: p.total_slack if p.total_slack else float('inf'))
    
    return jsonify({
        'nodes': worst_path.nodes,
        'edges': worst_path.edges,
        'total_delay': worst_path.total_delay,
        'total_slack': worst_path.total_slack
    })

@app.route('/api/views')
def get_available_views():
    """사용 가능한 뷰 목록"""
    return jsonify({
        'views': ['Structural', 'Connectivity', 'Physical'],
        'contexts': ['Design', 'Simulation']
    })

@app.route('/api/paths')
def get_paths():
    """두 노드 사이의 경로 찾기"""
    if query_api is None:
        return jsonify({'error': 'Graph not initialized'}), 500
    
    start = request.args.get('start')
    end = request.args.get('end')
    max_depth = request.args.get('max_depth', 10, type=int)
    
    if not start or not end:
        return jsonify({'error': 'start and end required'}), 400
    
    paths = query_api.find_paths(start, end, max_depth=max_depth)
    
    paths_data = []
    for path in paths:
        paths_data.append({
            'nodes': path.nodes,
            'edges': path.edges,
            'total_delay': path.total_delay,
            'total_slack': path.total_slack
        })
    
    return jsonify({'paths': paths_data})


# ============================================================================
# Main
# ============================================================================

def run_server(config: YosysConfig, host='0.0.0.0', port=5000, debug=False):
    """웹 서버 실행"""
    initialize_graph(config)
    print(f"\n🌐 Starting DKG Web Server...")
    print(f"   URL: http://localhost:{port}")
    print(f"   API docs: http://localhost:{port}/api/statistics")
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    from dkg.utils.config import YosysConfig
    
    config = YosysConfig(
        src_dir_win=r"C:\Users\User\NetMind\구현\예시",
        out_json_win=r"C:\Users\User\NetMind\구현\design.json",
        top_module="riscvsingle",
    )
    
    run_server(config, debug=True)
