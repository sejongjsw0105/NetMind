"""
그래프 스냅샷 저장/로딩 (읽기 전용 캐싱용)

메타데이터는 제외하고 필수 데이터만 JSON으로 저장:
- DKG 그래프 (nodes + edges)
- SuperGraph (supernodes + superedges + node_to_super)
- GraphVersion (메타데이터)
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

from ..core.graph import DKGEdge, DKGNode, EdgeFlowType, EntityClass, RelationType
from ..core.provenance import Provenance
from ..builders.supergraph import SuperClass, SuperEdge, SuperGraph, SuperNode
from .graph_version import GraphVersion


@dataclass
class GraphSnapshot:
    """전체 그래프 스냅샷"""
    version: GraphVersion
    dkg_nodes: Dict[str, DKGNode]
    dkg_edges: Dict[str, DKGEdge]
    supergraph: Optional[SuperGraph] = None


def _serialize_node(node: DKGNode) -> dict:
    """DKGNode를 JSON 직렬화 가능한 dict로 변환 (얕게)"""
    return {
        "node_id": node.node_id,
        "entity_class": node.entity_class.value,
        "hier_path": node.hier_path,
        "local_name": node.local_name,
        "canonical_name": node.canonical_name,
        "short_alias": node.short_alias,
        "parameters": node.parameters,
        "attributes": node.attributes,
        "clock_domain": node.clock_domain,
        "arrival_time": node.arrival_time,
        "required_time": node.required_time,
        "slack": node.slack,
        "in_edges": node.in_edges,
        "out_edges": node.out_edges,
        # provenance는 얕게: 기본 정보만
        "provenances": [
            {
                "origin_file": p.origin_file,
                "origin_line": p.origin_line,
                "tool_stage": p.tool_stage,
                "confidence": p.confidence,
            }
            for p in node.provenances
        ] if node.provenances else [],
        "primary_provenance": {
            "origin_file": node.primary_provenance.origin_file,
            "origin_line": node.primary_provenance.origin_line,
            "tool_stage": node.primary_provenance.tool_stage,
            "confidence": node.primary_provenance.confidence,
        } if node.primary_provenance else None,
    }


def _deserialize_node(data: dict) -> DKGNode:
    """dict에서 DKGNode 복원"""
    from ..stages import ParsingStage
    
    # provenance 복원
    provenances = []
    if data.get("provenances"):
        for p in data["provenances"]:
            provenances.append(Provenance(
                origin_file=p.get("origin_file"),
                origin_line=p.get("origin_line"),
                tool_stage=p.get("tool_stage", "rtl"),
                confidence=p.get("confidence", "exact"),
            ))
    
    primary_provenance = None
    if data.get("primary_provenance"):
        p = data["primary_provenance"]
        primary_provenance = Provenance(
            origin_file=p.get("origin_file"),
            origin_line=p.get("origin_line"),
            tool_stage=p.get("tool_stage", "rtl"),
            confidence=p.get("confidence", "exact"),
        )
    
    return DKGNode(
        node_id=data["node_id"],
        entity_class=EntityClass(data["entity_class"]),
        hier_path=data["hier_path"],
        local_name=data["local_name"],
        canonical_name=data.get("canonical_name"),
        short_alias=data.get("short_alias"),
        parameters=data.get("parameters", {}),
        attributes=data.get("attributes", {}),
        clock_domain=data.get("clock_domain"),
        arrival_time=data.get("arrival_time"),
        required_time=data.get("required_time"),
        slack=data.get("slack"),
        in_edges=data.get("in_edges", []),
        out_edges=data.get("out_edges", []),
        provenances=provenances,
        primary_provenance=primary_provenance,
    )


def _serialize_edge(edge: DKGEdge) -> dict:
    """DKGEdge를 JSON 직렬화 가능한 dict로 변환"""
    return {
        "edge_id": edge.edge_id,
        "src_node": edge.src_node,
        "dst_node": edge.dst_node,
        "relation_type": edge.relation_type.value,
        "flow_type": edge.flow_type.value,
        "signal_name": edge.signal_name,
        "canonical_name": edge.canonical_name,
        "bit_range": list(edge.bit_range) if edge.bit_range else None,
        "net_id": edge.net_id,
        "driver_type": edge.driver_type,
        "fanout_count": edge.fanout_count,
        "clock_signal": edge.clock_signal,
        "reset_signal": edge.reset_signal,
        "clock_domain_id": edge.clock_domain_id,
        "timing_exception": edge.timing_exception,
        "parameters": edge.parameters,
        "delay": edge.delay,
        "arrival_time": edge.arrival_time,
        "required_time": edge.required_time,
    }


def _deserialize_edge(data: dict) -> DKGEdge:
    """dict에서 DKGEdge 복원"""
    return DKGEdge(
        edge_id=data["edge_id"],
        src_node=data["src_node"],
        dst_node=data["dst_node"],
        relation_type=RelationType(data["relation_type"]),
        flow_type=EdgeFlowType(data["flow_type"]),
        signal_name=data["signal_name"],
        canonical_name=data["canonical_name"],
        bit_range=tuple(data["bit_range"]) if data.get("bit_range") else None,
        net_id=data.get("net_id"),
        driver_type=data.get("driver_type"),
        fanout_count=data.get("fanout_count"),
        clock_signal=data.get("clock_signal"),
        reset_signal=data.get("reset_signal"),
        clock_domain_id=data.get("clock_domain_id"),
        timing_exception=data.get("timing_exception"),
        parameters=data.get("parameters", {}),
        delay=data.get("delay"),
        arrival_time=data.get("arrival_time"),
        required_time=data.get("required_time"),
    )


def _serialize_supernode(sn: SuperNode) -> dict:
    """SuperNode를 JSON 직렬화"""
    return {
        "node_id": sn.node_id,
        "super_class": sn.super_class.value,
        "member_nodes": list(sn.member_nodes),
        "member_edges": list(sn.member_edges),
        "aggregated_attrs": sn.aggregated_attrs,
        "canonical_name": sn.canonical_name,
        "display_name": sn.display_name,
        "provenances": [
            {"origin_file": p.origin_file, "origin_line": p.origin_line, "tool_stage": p.tool_stage}
            for p in sn.provenances
        ] if sn.provenances else [],
    }


def _deserialize_supernode(data: dict) -> SuperNode:
    """dict에서 SuperNode 복원"""
    provenances = []
    if data.get("provenances"):
        for p in data["provenances"]:
            provenances.append(Provenance(
                origin_file=p.get("origin_file"),
                origin_line=p.get("origin_line"),
                tool_stage=p.get("tool_stage", "rtl"),
            ))
    
    return SuperNode(
        node_id=data["node_id"],
        super_class=SuperClass(data["super_class"]),
        member_nodes=set(data["member_nodes"]),
        member_edges=set(data["member_edges"]),
        aggregated_attrs=data.get("aggregated_attrs", {}),
        canonical_name=data.get("canonical_name"),
        display_name=data.get("display_name"),
        provenances=provenances,
    )


def _serialize_superedge(se: SuperEdge) -> dict:
    """SuperEdge를 JSON 직렬화"""
    return {
        "edge_id": se.edge_id,
        "src_node": se.src_node,
        "dst_node": se.dst_node,
        "member_edges": list(se.member_edges),
        "member_nodes": list(se.member_nodes),
        "relation_types": [rt.value for rt in se.relation_types],
        "flow_types": [ft.value for ft in se.flow_types],
        "canonical_name": se.canonical_name,
        "display_name": se.display_name,
        "provenances": [
            {"origin_file": p.origin_file, "origin_line": p.origin_line, "tool_stage": p.tool_stage}
            for p in se.provenances
        ] if se.provenances else [],
    }


def _deserialize_superedge(data: dict) -> SuperEdge:
    """dict에서 SuperEdge 복원"""
    provenances = []
    if data.get("provenances"):
        for p in data["provenances"]:
            provenances.append(Provenance(
                origin_file=p.get("origin_file"),
                origin_line=p.get("origin_line"),
                tool_stage=p.get("tool_stage", "rtl"),
            ))
    
    return SuperEdge(
        edge_id=data["edge_id"],
        src_node=data["src_node"],
        dst_node=data["dst_node"],
        member_edges=set(data["member_edges"]),
        member_nodes=set(data["member_nodes"]),
        relation_types={RelationType(rt) for rt in data["relation_types"]},
        flow_types={EdgeFlowType(ft) for ft in data["flow_types"]},
        canonical_name=data.get("canonical_name"),
        display_name=data.get("display_name"),
        provenances=provenances,
    )


def save_snapshot(
    snapshot: GraphSnapshot,
    filepath: Path | str,
    indent: Optional[int] = None,
) -> None:
    """스냅샷을 JSON 파일로 저장"""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    # 직렬화
    data = {
        "version": {
            "rtl_hash": snapshot.version.rtl_hash,
            "constraint_hash": snapshot.version.constraint_hash,
            "timing_hash": snapshot.version.timing_hash,
            "policy_versions": snapshot.version.policy_versions,
        },
        "dkg": {
            "nodes": {
                node_id: _serialize_node(node)
                for node_id, node in snapshot.dkg_nodes.items()
            },
            "edges": {
                edge_id: _serialize_edge(edge)
                for edge_id, edge in snapshot.dkg_edges.items()
            },
        },
    }
    
    # SuperGraph가 있으면 추가
    if snapshot.supergraph:
        sg = snapshot.supergraph
        data["supergraph"] = {
            "super_nodes": {
                node_id: _serialize_supernode(sn)
                for node_id, sn in sg.super_nodes.items()
            },
            "super_edges": {
                f"{src}→{dst}": _serialize_superedge(se)
                for (src, dst), se in sg.super_edges.items()
            },
            "node_to_super": sg.node_to_super,
        }
    
    # JSON 저장
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def load_snapshot(filepath: Path | str) -> GraphSnapshot:
    """JSON 파일에서 스냅샷 로딩"""
    filepath = Path(filepath)
    
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # GraphVersion 복원
    version_data = data["version"]
    version = GraphVersion(
        rtl_hash=version_data["rtl_hash"],
        constraint_hash=version_data.get("constraint_hash"),
        timing_hash=version_data.get("timing_hash"),
        policy_versions=version_data.get("policy_versions", {}),
    )
    
    # DKG 그래프 복원
    dkg_data = data["dkg"]
    dkg_nodes = {
        node_id: _deserialize_node(node_data)
        for node_id, node_data in dkg_data["nodes"].items()
    }
    dkg_edges = {
        edge_id: _deserialize_edge(edge_data)
        for edge_id, edge_data in dkg_data["edges"].items()
    }
    
    # SuperGraph 복원 (있으면)
    supergraph = None
    if "supergraph" in data:
        sg_data = data["supergraph"]
        super_nodes = {
            node_id: _deserialize_supernode(sn_data)
            for node_id, sn_data in sg_data["super_nodes"].items()
        }
        super_edges = {
            tuple(key.split("→")): _deserialize_superedge(se_data)
            for key, se_data in sg_data["super_edges"].items()
        }
        node_to_super = sg_data["node_to_super"]
        
        supergraph = SuperGraph(
            super_nodes=super_nodes,
            super_edges=super_edges,
            node_to_super=node_to_super,
        )
    
    return GraphSnapshot(
        version=version,
        dkg_nodes=dkg_nodes,
        dkg_edges=dkg_edges,
        supergraph=supergraph,
    )
