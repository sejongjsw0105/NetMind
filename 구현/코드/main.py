from __future__ import annotations
from dkg.config import YosysConfig
from dkg.debug import (
    plot_subgraph,
    print_fanout_summary,
    print_graph_summary,
    print_sample_node,
    trace_signal,
)
from dkg.graph_build import build_nodes_and_edges, build_wires_and_cells
from dkg.yosys_parser import parse_yosys


DEFAULT_CONFIG = YosysConfig(
    src_dir_win=r"C:\Users\User\NetMind\구현\예시",
    out_json_win=r"C:\Users\User\NetMind\구현\design.json",
    top_module="riscvsingle",
)


def main(config: YosysConfig, debug: bool = True) -> None:
    yosys = parse_yosys(config)
    wires, cells = build_wires_and_cells(yosys)
    nodes, edges = build_nodes_and_edges(wires, cells)

    if debug:
        print_graph_summary(wires, cells, nodes, edges)
        print_sample_node(nodes, edges)
        print_fanout_summary(wires)
        trace_signal(wires, "clk")
        plot_subgraph(nodes, edges, limit=30)


if __name__ == "__main__":
    main(DEFAULT_CONFIG, debug=True)
