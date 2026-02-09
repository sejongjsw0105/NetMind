from __future__ import annotations

import random
from typing import Dict, Iterable, List

from .graph import DKGEdge, DKGNode
from .ir import CellIR, Wire


def print_graph_summary(wires: Dict[int, Wire], cells: List[CellIR], nodes: Dict[str, DKGNode], edges: Dict[str, DKGEdge]) -> None:
    print("===== GRAPH SUMMARY =====")
    print(f"Total wires   : {len(wires)}")
    print(f"Total cells   : {len(cells)}")
    print(f"Total nodes   : {len(nodes)}")
    print(f"Total edges   : {len(edges)}")
    print("=========================")


def print_sample_node(nodes: Dict[str, DKGNode], edges: Dict[str, DKGEdge], max_edges: int = 5) -> None:
    if not nodes:
        print("No nodes available.")
        return

    sample = random.choice(list(nodes.values()))
    print("\n===== SAMPLE NODE =====")
    print("Node:", sample.node_id, sample.entity_class)
    print("IN edges:", len(sample.in_edges))
    print("OUT edges:", len(sample.out_edges))

    for eid in sample.out_edges[:max_edges]:
        e = edges[eid]
        print("  ->", e.signal_name, "->", e.dst_node)
    print("=========================")


def print_fanout_summary(wires: Dict[int, Wire]) -> None:
    fanouts = [len(w.loads) for w in wires.values() if w.loads]
    if not fanouts:
        print("\nMax fanout: 0")
        print("Avg fanout: 0")
        print("=========================")
        return

    print("\nMax fanout:", max(fanouts))
    print("Avg fanout:", sum(fanouts) / len(fanouts))
    print("=========================")


def trace_signal(wires: Dict[int, Wire], target: str) -> None:
    print("\n===== TRACE SIGNAL:", target, "=====")
    for w in wires.values():
        if w.name == target:
            print("Drivers:", w.drivers)
            print("Loads  :", w.loads)
    print("=========================")


def plot_subgraph(nodes: Dict[str, DKGNode], edges: Dict[str, DKGEdge], limit: int = 30) -> None:
    try:
        import networkx as nx
        import matplotlib.pyplot as plt
    except Exception as exc:
        print("Plot skipped:", exc)
        return

    g = nx.DiGraph()
    for nid in nodes:
        g.add_node(nid)

    for e in edges.values():
        g.add_edge(e.src_node, e.dst_node, label=e.signal_name)

    sub_nodes = list(nodes.keys())[:limit]

    def clean_label(name: str) -> str:
        return name.replace("\\", "").replace("$", "")

    h = g.subgraph(sub_nodes)
    labels = {n: clean_label(n) for n in h.nodes()}

    nx.draw(h, labels=labels, with_labels=True, node_size=500, font_size=6)
    plt.show()
