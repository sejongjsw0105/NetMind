"""
DKG Query API

그래프 검색 및 분석을 위한 통합 쿼리 인터페이스
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from .core.graph import DKGEdge, DKGNode, EdgeFlowType, EntityClass, RelationType

if TYPE_CHECKING:
    from .builders.supergraph import SuperGraph, SuperNode, SuperEdge, AnalysisKind


# ============================================================================
# Query Result Types
# ============================================================================

@dataclass
class PathResult:
    """경로 탐색 결과"""
    nodes: List[str]  # node_id 리스트
    edges: List[str]  # edge_id 리스트
    total_delay: Optional[float] = None
    total_slack: Optional[float] = None
    
    def __len__(self) -> int:
        return len(self.nodes)


@dataclass
class TimingQueryResult:
    """타이밍 쿼리 결과"""
    worst_slack: Optional[float]
    critical_nodes: List[str]
    critical_edges: List[str]
    timing_violations: int
    

@dataclass
class FanoutResult:
    """팬아웃 분석 결과"""
    node_id: str
    fanout_count: int
    fanout_nodes: List[str]
    max_delay: Optional[float] = None


# ============================================================================
# Main Query API
# ============================================================================

class DKGQuery:
    """
    DKG 그래프 쿼리 API
    
    사용 예시:
        query = DKGQuery(nodes, edges)
        
        # 노드 검색
        ffs = query.find_nodes(entity_class=EntityClass.FLIP_FLOP)
        clk_nodes = query.find_nodes(name_pattern="clk*")
        
        # 경로 탐색
        paths = query.find_paths("ff1", "ff2", max_depth=5)
        
        # 타이밍 분석
        critical = query.find_critical_nodes(slack_threshold=0.5)
    """
    
    def __init__(
        self,
        nodes: Dict[str, DKGNode],
        edges: Dict[str, DKGEdge],
        supergraph: Optional["SuperGraph"] = None
    ):
        self.nodes = nodes
        self.edges = edges
        self.supergraph = supergraph
        
        # 인덱스 구축
        self._build_indexes()
    
    def _build_indexes(self) -> None:
        """검색 성능을 위한 인덱스 구축"""
        # Entity class 인덱스
        self.nodes_by_class: Dict[EntityClass, List[str]] = {}
        for node_id, node in self.nodes.items():
            if node.entity_class not in self.nodes_by_class:
                self.nodes_by_class[node.entity_class] = []
            self.nodes_by_class[node.entity_class].append(node_id)
        
        # 계층 인덱스 (hier_path prefix)
        self.nodes_by_hierarchy: Dict[str, List[str]] = {}
        for node_id, node in self.nodes.items():
            parts = node.hier_path.split('/')
            for i in range(len(parts)):
                prefix = '/'.join(parts[:i+1])
                if prefix not in self.nodes_by_hierarchy:
                    self.nodes_by_hierarchy[prefix] = []
                self.nodes_by_hierarchy[prefix].append(node_id)
        
        # Edge relation type 인덱스
        self.edges_by_relation: Dict[RelationType, List[str]] = {}
        for edge_id, edge in self.edges.items():
            if edge.relation_type not in self.edges_by_relation:
                self.edges_by_relation[edge.relation_type] = []
            self.edges_by_relation[edge.relation_type].append(edge_id)
    
    # ========================================================================
    # Node Query Methods
    # ========================================================================
    
    def find_nodes(
        self,
        entity_class: Optional[EntityClass] = None,
        name_pattern: Optional[str] = None,
        hierarchy_prefix: Optional[str] = None,
        clock_domain: Optional[str] = None,
        slack_range: Optional[Tuple[float, float]] = None,
        custom_filter: Optional[Callable[[DKGNode], bool]] = None
    ) -> List[str]:
        """
        노드 검색
        
        Args:
            entity_class: 엔티티 클래스 필터
            name_pattern: 이름 패턴 (와일드카드 * 지원)
            hierarchy_prefix: 계층 경로 prefix
            clock_domain: 클럭 도메인 필터
            slack_range: (min_slack, max_slack) 범위
            custom_filter: 사용자 정의 필터 함수
        
        Returns:
            매칭된 node_id 리스트
        """
        candidates = set(self.nodes.keys())
        
        # Entity class 필터
        if entity_class is not None:
            candidates &= set(self.nodes_by_class.get(entity_class, []))
        
        # 계층 필터
        if hierarchy_prefix is not None:
            candidates &= set(self.nodes_by_hierarchy.get(hierarchy_prefix, []))
        
        # 추가 필터링
        result = []
        for node_id in candidates:
            node = self.nodes[node_id]
            
            # 이름 패턴
            if name_pattern is not None:
                if not self._match_pattern(name_pattern, node):
                    continue
            
            # 클럭 도메인
            if clock_domain is not None and node.clock_domain != clock_domain:
                continue
            
            # Slack 범위
            if slack_range is not None:
                if node.slack is None:
                    continue
                min_slack, max_slack = slack_range
                if not (min_slack <= node.slack <= max_slack):
                    continue
            
            # 사용자 정의 필터
            if custom_filter is not None and not custom_filter(node):
                continue
            
            result.append(node_id)
        
        return result
    
    def find_node_by_name(self, name: str) -> Optional[str]:
        """
        정확한 이름으로 노드 검색
        
        Args:
            name: node_id, hier_path, canonical_name, 또는 local_name
        
        Returns:
            node_id 또는 None
        """
        # 1. node_id로 직접 검색
        if name in self.nodes:
            return name
        
        # 2. hier_path, canonical_name, local_name으로 검색
        for node_id, node in self.nodes.items():
            if (node.hier_path == name or 
                node.canonical_name == name or 
                node.local_name == name):
                return node_id
        
        return None
    
    def get_node(self, node_id: str) -> Optional[DKGNode]:
        """노드 객체 반환"""
        return self.nodes.get(node_id)
    
    # ========================================================================
    # Edge Query Methods
    # ========================================================================
    
    def find_edges(
        self,
        src_node: Optional[str] = None,
        dst_node: Optional[str] = None,
        relation_type: Optional[RelationType] = None,
        flow_type: Optional[EdgeFlowType] = None,
        signal_pattern: Optional[str] = None,
        custom_filter: Optional[Callable[[DKGEdge], bool]] = None
    ) -> List[str]:
        """
        엣지 검색
        
        Args:
            src_node: 소스 노드 ID
            dst_node: 목적지 노드 ID
            relation_type: 관계 타입
            flow_type: 플로우 타입
            signal_pattern: 신호 이름 패턴
            custom_filter: 사용자 정의 필터
        
        Returns:
            매칭된 edge_id 리스트
        """
        candidates = set(self.edges.keys())
        
        # Relation type 필터
        if relation_type is not None:
            candidates &= set(self.edges_by_relation.get(relation_type, []))
        
        result = []
        for edge_id in candidates:
            edge = self.edges[edge_id]
            
            # 소스/목적지 노드
            if src_node is not None and edge.src_node != src_node:
                continue
            if dst_node is not None and edge.dst_node != dst_node:
                continue
            
            # Flow type
            if flow_type is not None and edge.flow_type != flow_type:
                continue
            
            # 신호 패턴
            if signal_pattern is not None:
                if not self._match_wildcard(signal_pattern, edge.signal_name):
                    continue
            
            # 사용자 정의 필터
            if custom_filter is not None and not custom_filter(edge):
                continue
            
            result.append(edge_id)
        
        return result
    
    def get_edge(self, edge_id: str) -> Optional[DKGEdge]:
        """엣지 객체 반환"""
        return self.edges.get(edge_id)
    
    # ========================================================================
    # Graph Traversal Methods
    # ========================================================================
    
    def find_paths(
        self,
        start_node: str,
        end_node: str,
        max_depth: int = 10,
        follow_data_only: bool = False
    ) -> List[PathResult]:
        """
        두 노드 사이의 모든 경로 찾기 (BFS)
        
        Args:
            start_node: 시작 노드 ID
            end_node: 끝 노드 ID
            max_depth: 최대 깊이
            follow_data_only: True면 데이터 엣지만 따라감
        
        Returns:
            경로 리스트
        """
        if start_node not in self.nodes or end_node not in self.nodes:
            return []
        
        paths: List[PathResult] = []
        queue: deque[Tuple[str, List[str], List[str]]] = deque([(start_node, [start_node], [])])
        visited_paths: Set[Tuple[str, ...]] = set()
        
        while queue:
            current, node_path, edge_path = queue.popleft()
            
            # 경로 길이 제한
            if len(node_path) > max_depth:
                continue
            
            # 목적지 도달
            if current == end_node and len(node_path) > 1:
                total_delay = self._compute_path_delay(edge_path)
                total_slack = self._compute_path_slack(node_path)
                paths.append(PathResult(
                    nodes=node_path,
                    edges=edge_path,
                    total_delay=total_delay,
                    total_slack=total_slack
                ))
                continue
            
            # 다음 노드 탐색
            current_node = self.nodes[current]
            for edge_id in current_node.out_edges:
                edge = self.edges[edge_id]
                
                # 데이터 엣지만 따라가기
                if follow_data_only and edge.relation_type != RelationType.DATA:
                    continue
                
                next_node = edge.dst_node
                
                # 순환 방지 (현재 경로에서)
                if next_node in node_path:
                    continue
                
                new_node_path = node_path + [next_node]
                new_edge_path = edge_path + [edge_id]
                
                # 중복 경로 방지
                path_tuple = tuple(new_node_path)
                if path_tuple in visited_paths:
                    continue
                visited_paths.add(path_tuple)
                
                queue.append((next_node, new_node_path, new_edge_path))
        
        return paths
    
    def find_shortest_path(
        self,
        start_node: str,
        end_node: str,
        weight: str = "hops"  # "hops", "delay"
    ) -> Optional[PathResult]:
        """
        최단 경로 찾기
        
        Args:
            start_node: 시작 노드
            end_node: 끝 노드
            weight: 가중치 ("hops" 또는 "delay")
        
        Returns:
            최단 경로 또는 None
        """
        paths = self.find_paths(start_node, end_node, max_depth=20)
        if not paths:
            return None
        
        if weight == "hops":
            return min(paths, key=lambda p: len(p))
        elif weight == "delay":
            valid_paths = [p for p in paths if p.total_delay is not None]
            if not valid_paths:
                return None
            return min(valid_paths, key=lambda p: p.total_delay or 0.0)
        
        return None
    
    def get_fanout(self, node_id: str, max_depth: int = 1) -> FanoutResult:
        """
        노드의 팬아웃 분석
        
        Args:
            node_id: 노드 ID
            max_depth: 탐색 깊이 (1=직접 연결만)
        
        Returns:
            팬아웃 결과
        """
        if node_id not in self.nodes:
            return FanoutResult(node_id, 0, [])
        
        fanout_nodes = set()
        visited = set()
        queue = deque([(node_id, 0)])
        max_delay = None
        
        while queue:
            current, depth = queue.popleft()
            if current in visited or depth >= max_depth:
                continue
            visited.add(current)
            
            node = self.nodes[current]
            for edge_id in node.out_edges:
                edge = self.edges[edge_id]
                next_node = edge.dst_node
                
                if depth + 1 <= max_depth:
                    fanout_nodes.add(next_node)
                    queue.append((next_node, depth + 1))
                
                # 최대 지연 업데이트
                if edge.delay is not None:
                    if max_delay is None:
                        max_delay = edge.delay
                    else:
                        max_delay = max(max_delay, edge.delay)
        
        return FanoutResult(
            node_id=node_id,
            fanout_count=len(fanout_nodes),
            fanout_nodes=list(fanout_nodes),
            max_delay=max_delay
        )
    
    def get_fanin(self, node_id: str, max_depth: int = 1) -> FanoutResult:
        """
        노드의 팬인 분석
        
        Args:
            node_id: 노드 ID
            max_depth: 탐색 깊이
        
        Returns:
            팬인 결과
        """
        if node_id not in self.nodes:
            return FanoutResult(node_id, 0, [])
        
        fanin_nodes = set()
        visited = set()
        queue = deque([(node_id, 0)])
        max_delay = None
        
        while queue:
            current, depth = queue.popleft()
            if current in visited or depth >= max_depth:
                continue
            visited.add(current)
            
            node = self.nodes[current]
            for edge_id in node.in_edges:
                edge = self.edges[edge_id]
                prev_node = edge.src_node
                
                if depth + 1 <= max_depth:
                    fanin_nodes.add(prev_node)
                    queue.append((prev_node, depth + 1))
                
                if edge.delay is not None:
                    if max_delay is None:
                        max_delay = edge.delay
                    else:
                        max_delay = max(max_delay, edge.delay)
        
        return FanoutResult(
            node_id=node_id,
            fanout_count=len(fanin_nodes),
            fanout_nodes=list(fanin_nodes),
            max_delay=max_delay
        )
    
    # ========================================================================
    # Timing Query Methods
    # ========================================================================
    
    def find_critical_nodes(
        self,
        slack_threshold: float = 0.0,
        top_n: Optional[int] = None
    ) -> List[Tuple[str, float]]:
        """
        Critical 노드 찾기
        
        Args:
            slack_threshold: Slack 임계값 (이하인 노드 반환)
            top_n: 상위 N개만 반환
        
        Returns:
            (node_id, slack) 튜플 리스트 (slack 오름차순)
        """
        critical = []
        for node_id, node in self.nodes.items():
            if node.slack is not None and node.slack <= slack_threshold:
                critical.append((node_id, node.slack))
        
        critical.sort(key=lambda x: x[1])
        
        if top_n is not None:
            critical = critical[:top_n]
        
        return critical
    
    def find_critical_edges(
        self,
        delay_threshold: Optional[float] = None,
        top_n: Optional[int] = None
    ) -> List[Tuple[str, float]]:
        """
        Critical 엣지 찾기
        
        Args:
            delay_threshold: Delay 임계값 (이상인 엣지 반환)
            top_n: 상위 N개만 반환
        
        Returns:
            (edge_id, delay) 튜플 리스트 (delay 내림차순)
        """
        critical = []
        for edge_id, edge in self.edges.items():
            if edge.delay is not None:
                if delay_threshold is None or edge.delay >= delay_threshold:
                    critical.append((edge_id, edge.delay))
        
        critical.sort(key=lambda x: x[1], reverse=True)
        
        if top_n is not None:
            critical = critical[:top_n]
        
        return critical
    
    def get_timing_summary(self) -> TimingQueryResult:
        """전체 타이밍 요약"""
        slacks = [node.slack for node in self.nodes.values() if node.slack is not None]
        worst_slack = min(slacks) if slacks else None
        
        violations = sum(1 for s in slacks if s < 0)
        
        critical_nodes = [
            node_id for node_id, node in self.nodes.items()
            if node.slack is not None and node.slack < 0.5
        ]
        
        critical_edges = [
            edge_id for edge_id, edge in self.edges.items()
            if edge.delay is not None and edge.delay > 1.0
        ]
        
        return TimingQueryResult(
            worst_slack=worst_slack,
            critical_nodes=critical_nodes,
            critical_edges=critical_edges,
            timing_violations=violations
        )
    
    # ========================================================================
    # Hierarchy Query Methods
    # ========================================================================
    
    def get_hierarchy_children(self, parent_path: str) -> List[str]:
        """
        계층 구조에서 직계 자식 노드 찾기
        
        Args:
            parent_path: 부모 경로 (예: "cpu/alu")
        
        Returns:
            자식 노드 ID 리스트
        """
        children = []
        for node_id, node in self.nodes.items():
            hier = node.hier_path
            if hier.startswith(parent_path + '/'):
                # 직계 자식인지 확인
                relative = hier[len(parent_path)+1:]
                if '/' not in relative:
                    children.append(node_id)
        
        return children
    
    def get_hierarchy_subtree(self, root_path: str) -> List[str]:
        """
        계층 구조에서 모든 하위 노드 찾기
        
        Args:
            root_path: 루트 경로
        
        Returns:
            모든 하위 노드 ID 리스트
        """
        return self.nodes_by_hierarchy.get(root_path, [])
    
    # ========================================================================
    # SuperGraph Query Methods
    # ========================================================================
    
    def find_supernodes(
        self,
        super_class: Optional[str] = None,
        has_timing: bool = False
    ) -> List[str]:
        """
        SuperNode 검색
        
        Args:
            super_class: SuperClass 필터
            has_timing: True면 타이밍 분석이 부착된 것만
        
        Returns:
            supernode_id 리스트
        """
        if self.supergraph is None:
            return []
        
        result = []
        for sn_id, sn in self.supergraph.super_nodes.items():
            if super_class is not None and sn.super_class.value != super_class:
                continue
            
            if has_timing and "timing" not in sn.analysis:
                continue
            
            result.append(sn_id)
        
        return result
    
    def get_supernode(self, supernode_id: str) -> Optional["SuperNode"]:
        """SuperNode 객체 반환"""
        if self.supergraph is None:
            return None
        return self.supergraph.super_nodes.get(supernode_id)
    
    def get_supernode_for_node(self, node_id: str) -> Optional[str]:
        """노드가 속한 SuperNode ID 반환"""
        if self.supergraph is None:
            return None
        return self.supergraph.node_to_super.get(node_id)
    
    # ========================================================================
    # Statistics Methods
    # ========================================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """그래프 통계 정보"""
        stats = {
            'total_nodes': len(self.nodes),
            'total_edges': len(self.edges),
            'nodes_by_class': {
                cls.value: len(nodes)
                for cls, nodes in self.nodes_by_class.items()
            }
        }
        
        # 타이밍 통계
        slacks = [n.slack for n in self.nodes.values() if n.slack is not None]
        if slacks:
            stats['timing'] = {
                'worst_slack': min(slacks),
                'best_slack': max(slacks),
                'avg_slack': sum(slacks) / len(slacks),
                'violations': sum(1 for s in slacks if s < 0)
            }
        
        # 팬아웃 통계
        fanouts = [len(n.out_edges) for n in self.nodes.values()]
        if fanouts:
            stats['fanout'] = {
                'max': max(fanouts),
                'avg': sum(fanouts) / len(fanouts)
            }
        
        # SuperGraph 통계
        if self.supergraph is not None:
            stats['supergraph'] = {
                'super_nodes': len(self.supergraph.super_nodes),
                'super_edges': len(self.supergraph.super_edges)
            }
        
        return stats
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def _match_pattern(self, pattern: str, node: DKGNode) -> bool:
        """노드 이름이 패턴과 매칭되는지 확인"""
        candidates = [
            node.hier_path,
            node.local_name,
            node.canonical_name or ""
        ]
        return any(self._match_wildcard(pattern, c) for c in candidates)
    
    def _match_wildcard(self, pattern: str, text: str) -> bool:
        """와일드카드 패턴 매칭"""
        import re
        regex_pattern = pattern.replace('*', '.*').replace('?', '.')
        return re.fullmatch(regex_pattern, text) is not None
    
    def _compute_path_delay(self, edge_path: List[str]) -> Optional[float]:
        """경로의 총 지연 계산"""
        total = 0.0
        has_delay = False
        for edge_id in edge_path:
            edge = self.edges[edge_id]
            if edge.delay is not None:
                total += edge.delay
                has_delay = True
        return total if has_delay else None
    
    def _compute_path_slack(self, node_path: List[str]) -> Optional[float]:
        """경로의 최소 slack 계산"""
        slacks = []
        for node_id in node_path:
            node = self.nodes[node_id]
            if node.slack is not None:
                slacks.append(node.slack)
        return min(slacks) if slacks else None


# ============================================================================
# Convenience Functions
# ============================================================================

def create_query(
    nodes: Dict[str, DKGNode],
    edges: Dict[str, DKGEdge],
    supergraph: Optional["SuperGraph"] = None
) -> DKGQuery:
    """Query API 생성 헬퍼 함수"""
    return DKGQuery(nodes, edges, supergraph)
