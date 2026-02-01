function dkgNodeToCyNode(node) {
  return {
    group: "nodes",
    data: {
      id: node.node_id,
      label: node.display_name || node.local_name,
      entity_class: node.entity_class,
      hier_path: node.hier_path,
      view: node.view,

      // Timing
      slack: node.slack,
      arrival: node.arrival_time,
      required: node.required_time,

      clock_domain: node.clock_domain
    }
  };
}
function dkgEdgeToCyEdge(edge) {
  return {
    group: "edges",
    data: {
      id: edge.edge_id,
      source: edge.src_node,
      target: edge.dst_node,

      relation_type: edge.relation_type,
      flow_type: edge.flow_type,

      signal_name: edge.signal_name,
      canonical_name: edge.canonical_name,
      bit_range: edge.bit_range,
      net_id: edge.net_id,

      slack: edge.slack,
      delay: edge.delay,

      timing_exception: edge.timing_exception,
      clock_domain: edge.clock_domain_id
    }
  };
}
function setupStylingRules(cy) {

  cy.style()
    .selector('node[entity_class = "ModuleInstance"]')
    .style({ "shape": "round-rectangle", "background-color": "#4e79a7" })

    .selector('node[entity_class = "FlipFlop"]')
    .style({ "shape": "rectangle", "background-color": "#f28e2b" })

    .selector('node[entity_class = "IOPort"]')
    .style({ "shape": "diamond", "background-color": "#59a14f" })

    .selector('node[entity_class = "ClockDomain"]')
    .style({ "shape": "ellipse", "background-color": "#e15759" })

    .update();
}
function highlightCritical(cy) {
  cy.edges().forEach(e => {
    const slack = e.data("slack");
    if (slack !== null && slack <= 0) {
      e.style({
        "line-color": "red",
        "target-arrow-color": "red",
        width: 4
      });
    }
  });
}
function expandFromNode(cy, nodeId, depth) {
  fetch(`/subgraph?node=${nodeId}&depth=${depth}`)
    .then(res => res.json())
    .then(data => {
      const newElems = [
        ...data.nodes.map(dkgNodeToCyNode),
        ...data.edges.map(dkgEdgeToCyEdge)
      ];
      cy.add(newElems);
      cy.layout({ name: "breadthfirst", roots: `#${nodeId}` }).run();
    });
}
function setupInteraction(cy) {
  cy.on("tap", "edge", evt => {
    const d = evt.target.data();
    showEdgeInfo(d);
  });

  cy.on("tap", "node", evt => {
    const d = evt.target.data();
    showNodeInfo(d);
  });
}
