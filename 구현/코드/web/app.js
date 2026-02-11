// DKG Viewer - Cytoscape.js Application

const API_BASE = 'http://localhost:5000/api';

let cy = null;
let currentLayout = 'breadthfirst';
let contextMenu = null;
let currentView = 'Connectivity';
let currentContext = 'Design';

document.addEventListener('DOMContentLoaded', () => {
    initializeCytoscape();
    initializeTabs();
    initializeSearch();
    loadStatistics();
    loadFullGraph();
    loadSuperNodes();
    initMinimap();
});

function initializeCytoscape() {
    cytoscape.use(cytoscapeDagre);
    
    cy = cytoscape({
        container: document.getElementById('cy'),
        style: [
            {
                selector: 'node',
                style: {
                    'label': 'data(label)',
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'font-size': '10px',
                    'color': '#e0e0e0',
                    'background-color': '#4a4a4a',
                    'border-width': 2,
                    'border-color': '#61dafb',
                    'width': 30,
                    'height': 30
                }
            },
            {
                selector: 'node[entity_class="FlipFlop"]',
                style: {
                    'background-color': '#61dafb',
                    'shape': 'rectangle'
                }
            },
            {
                selector: 'node[entity_class="LUT"]',
                style: {
                    'background-color': '#51cf66',
                    'shape': 'triangle'
                }
            },
            {
                selector: 'node[entity_class="MUX"]',
                style: {
                    'background-color': '#ff922b',
                    'shape': 'diamond'
                }
            },
            {
                selector: 'edge',
                style: {
                    'width': 2,
                    'line-color': '#4a4a4a',
                    'target-arrow-color': '#4a4a4a',
                    'target-arrow-shape': 'triangle',
                    'curve-style': 'bezier'
                }
            }
        ],
        layout: {
            name: 'breadthfirst',
            directed: true,
            padding: 50
        },
        minZoom: 0.1,
        maxZoom: 5
    });
    
    cy.on('tap', 'node', onNodeTap);
    cy.on('tap', 'edge', onEdgeTap);
    cy.on('mouseover', 'node', onNodeHover);
    cy.on('mouseout', 'node', onNodeOut);
    cy.on('dbltap', 'node', onNodeDoubleTap);
    cy.on('cxttap', 'node', onNodeRightClick);
    cy.on('tap', (event) => {
        if (event.target === cy) {
            closeContextMenu();
        }
    });
}

function initializeTabs() {
    const tabs = document.querySelectorAll('.tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            switchTab(tab.dataset.tab);
        });
    });
}

function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(t => {
        t.classList.remove('active');
        if (t.dataset.tab === tabName) {
            t.classList.add('active');
        }
    });
    
    document.querySelectorAll('.tab-panel').forEach(p => {
        p.classList.remove('active');
    });
    document.getElementById(tabName + '-panel').classList.add('active');
}

function initializeSearch() {
    const searchInput = document.getElementById('searchInput');
    let debounceTimer;
    
    searchInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            searchNodes(e.target.value);
        }, 300);
    });
}

async function searchNodes(query) {
    if (query.length < 2) {
        document.getElementById('searchResults').innerHTML = '';
        return;
    }
    
    try {
        const response = await fetch(API_BASE + '/search?q=' + encodeURIComponent(query));
        const data = await response.json();
        displaySearchResults(data.results);
    } catch (error) {
        console.error('Search error:', error);
    }
}

function displaySearchResults(results) {
    const container = document.getElementById('searchResults');
    if (results.length === 0) {
        container.innerHTML = '<div style="padding: 10px; color: #888;">검색 결과 없음</div>';
        return;
    }
    
    container.innerHTML = results.map(node => {
        const slackClass = node.slack !== null ? (node.slack < 0 ? 'critical' : 'good') : '';
        const slackText = node.slack !== null ? node.slack.toFixed(3) + 'ns' : '-';
        return '<li class="node-item" onclick="focusOnNode(' + "'" + node.id + "'" + ')"><div class="name">' + node.label + '</div><div class="type">' + node.entity_class + '</div><span class="slack ' + slackClass + '">' + slackText + '</span></li>';
    }).join('');
}

function focusOnNode(nodeId) {
    const node = cy.getElementById(nodeId);
    if (node.length > 0) {
        cy.animate({
            fit: {
                eles: node,
                padding: 50
            }
        }, {
            duration: 500
        });
        node.select();
        showNodeInfo(nodeId);
    }
}

async function loadStatistics() {
    try {
        const stats = await fetch(API_BASE + '/statistics').then(r => r.json());
        const timing = await fetch(API_BASE + '/timing/summary').then(r => r.json());
        
        document.getElementById('statTotalNodes').textContent = stats.total_nodes.toLocaleString();
        document.getElementById('statTotalEdges').textContent = stats.total_edges.toLocaleString();
        document.getElementById('statWorstSlack').textContent = 
            timing.worst_slack !== null ? timing.worst_slack.toFixed(3) + 'ns' : '-';
        document.getElementById('statViolations').textContent = timing.timing_violations;
    } catch (error) {
        console.error('Statistics error:', error);
    }
}

async function loadFullGraph() {
    showLoading(true);
    try {
        const limit = document.getElementById('limitFilter')?.value || 100;
        const response = await fetch(API_BASE + '/graph?limit=' + limit);
        const data = await response.json();
        renderGraph(data);
    } catch (error) {
        console.error('Graph loading error:', error);
        alert('그래프 로딩 실패');
    } finally {
        showLoading(false);
    }
}

async function applyFilters() {
    showLoading(true);
    try {
        const params = new URLSearchParams();
        
        const entityClass = document.getElementById('entityClassFilter').value;
        if (entityClass) params.append('entity_class', entityClass);
        
        const hierarchy = document.getElementById('hierarchyFilter').value;
        if (hierarchy) params.append('hierarchy', hierarchy);
        
        const limit = document.getElementById('limitFilter').value;
        params.append('limit', limit);
        
        const response = await fetch(API_BASE + '/graph?' + params);
        const data = await response.json();
        renderGraph(data);
    } catch (error) {
        console.error('Filter error:', error);
        alert('필터 적용 실패');
    } finally {
        showLoading(false);
    }
}

function resetFilters() {
    document.getElementById('entityClassFilter').value = '';
    document.getElementById('hierarchyFilter').value = '';
    document.getElementById('limitFilter').value = '100';
    loadFullGraph();
}

function renderGraph(data) {
    const elements = [];
    
    data.nodes.forEach(node => {
        elements.push({
            group: 'nodes',
            data: {
                id: node.id,
                label: node.label,
                entity_class: node.entity_class,
                hier_path: node.hier_path,
                slack: node.slack
            }
        });
    });
    
    data.edges.forEach(edge => {
        elements.push({
            group: 'edges',
            data: {
                id: edge.id,
                source: edge.source,
                target: edge.target,
                signal_name: edge.signal_name
            }
        });
    });
    
    cy.elements().remove();
    cy.add(elements);
    applyLayout(currentLayout);
}

function changeLayout() {
    currentLayout = document.getElementById('layoutSelect').value;
    applyLayout(currentLayout);
}

function applyLayout(layoutName) {
    let layoutOptions = {
        name: layoutName,
        animate: true,
        animationDuration: 500,
        padding: 50
    };
    
    if (layoutName === 'breadthfirst') {
        layoutOptions.directed = true;
    } else if (layoutName === 'cose') {
        layoutOptions.idealEdgeLength = 100;
    }
    
    cy.layout(layoutOptions).run();
}

function fitGraph() {
    cy.fit(null, 50);
}

function centerGraph() {
    cy.center();
}

function resetGraph() {
    cy.zoom(1);
    cy.center();
}

async function onNodeTap(event) {
    const node = event.target;
    const nodeId = node.id();
    highlightNeighborhood(node);
    await showNodeInfoExtended(nodeId);
}

function onEdgeTap(event) {
    const edge = event.target;
    showEdgeInfo(edge);
}

function onNodeHover(event) {
    const node = event.target;
    node.addClass('highlighted');
}

function onNodeOut(event) {
    const node = event.target;
    node.removeClass('highlighted');
}

function highlightNeighborhood(node) {
    cy.elements().removeClass('highlighted');
    node.addClass('highlighted');
    node.neighborhood().addClass('highlighted');
}

async function showNodeInfo(nodeId) {
    try {
        const response = await fetch(API_BASE + '/node/' + nodeId);
        const data = await response.json();
        
        const panel = document.getElementById('infoPanel');
        const title = document.getElementById('infoPanelTitle');
        const content = document.getElementById('infoPanelContent');
        
        title.textContent = data.label;
        
        const slackText = data.slack !== null ? data.slack.toFixed(3) + ' ns' : '-';
        
        content.innerHTML = '<div class="info-row"><label>Entity Class</label><div class="value">' + data.entity_class + '</div></div>' +
            '<div class="info-row"><label>Hierarchy Path</label><div class="value">' + data.hier_path + '</div></div>' +
            '<div class="info-row"><label>Slack</label><div class="value">' + slackText + '</div></div>';
        
        panel.classList.add('active');
    } catch (error) {
        console.error('Node info error:', error);
    }
}

function showEdgeInfo(edge) {
    const data = edge.data();
    const panel = document.getElementById('infoPanel');
    const title = document.getElementById('infoPanelTitle');
    const content = document.getElementById('infoPanelContent');
    
    title.textContent = 'Edge Info';
    content.innerHTML = '<div class="info-row"><label>Signal</label><div class="value">' + data.signal_name + '</div></div>' +
        '<div class="info-row"><label>From</label><div class="value">' + data.source + '</div></div>' +
        '<div class="info-row"><label>To</label><div class="value">' + data.target + '</div></div>';
    
    panel.classList.add('active');
}

function closeInfoPanel() {
    document.getElementById('infoPanel').classList.remove('active');
}

function showLoading(show) {
    document.getElementById('loading').style.display = show ? 'block' : 'none';
}

// Feature 1: Hop Limitation
async function onNodeDoubleTap(event) {
    const node = event.target;
    const nodeId = node.id();
    
    const hops = prompt('홉 개수를 입력하세요 (1-5):', '2');
    if (!hops || isNaN(hops)) return;
    
    const hopCount = Math.min(Math.max(parseInt(hops), 1), 5);
    showLoading(true);
    
    try {
        const response = await fetch(API_BASE + '/node/' + nodeId + '/hop_limited?hops=' + hopCount);
        const data = await response.json();
        
        cy.nodes().addClass('hidden');
        cy.edges().addClass('hidden');
        
        data.nodes.forEach(n => {
            const node = cy.getElementById(n.id);
            if (node.length > 0) node.removeClass('hidden');
        });
        
        data.edges.forEach(e => {
            const edge = cy.getElementById(e.id);
            if (edge.length > 0) edge.removeClass('hidden');
        });
        
        cy.style().selector('.hidden').style({'display': 'none'}).update();
        cy.fit(cy.nodes(':visible'), 50);
    } catch (error) {
        console.error('Hop limited error:', error);
    } finally {
        showLoading(false);
    }
}

function resetHopFilter() {
    cy.nodes().removeClass('hidden');
    cy.edges().removeClass('hidden');
    cy.style().selector('.hidden').style({'display': 'element'}).update();
}

// Feature 2: Internal View
function onNodeRightClick(event) {
    event.preventDefault();
    const node = event.target;
    const nodeId = node.id();
    const pos = event.renderedPosition;
    showContextMenu(nodeId, pos.x, pos.y);
}

function showContextMenu(nodeId, x, y) {
    closeContextMenu();
    const menu = document.createElement('div');
    menu.className = 'context-menu';
    menu.style.left = x + 'px';
    menu.style.top = y + 'px';
    menu.innerHTML = '<div class="context-menu-item" onclick="showInternalView(' + "'" + nodeId + "'" + ')">내부 보기</div>' +
        '<div class="context-menu-item" onclick="tracePath(' + "'" + nodeId + "'" + ')">경로 추적</div>';
    document.body.appendChild(menu);
    contextMenu = menu;
}

function closeContextMenu() {
    if (contextMenu) {
        contextMenu.remove();
        contextMenu = null;
    }
}

async function showInternalView(nodeId) {
    closeContextMenu();
    showLoading(true);
    try {
        const response = await fetch(API_BASE + '/node/' + nodeId + '/internal');
        const data = await response.json();
        if (data.error) {
            alert('SuperNode이 아닙니다.');
            return;
        }
        alert('내부 뷰: ' + data.supernode_id + ' (' + data.nodes.length + ' nodes)');
    } catch (error) {
        console.error('Internal view error:', error);
    } finally {
        showLoading(false);
    }
}

// Feature 3: Extended Node Info
async function showNodeInfoExtended(nodeId) {
    try {
        const nodeInfo = await fetch(API_BASE + '/node/' + nodeId).then(r => r.json());
        const analysis = await fetch(API_BASE + '/node/' + nodeId + '/analysis').then(r => r.json());
        
        const panel = document.getElementById('infoPanel');
        const title = document.getElementById('infoPanelTitle');
        const content = document.getElementById('infoPanelContent');
        
        title.textContent = nodeInfo.label;
        
        const slackText = nodeInfo.slack !== null ? nodeInfo.slack.toFixed(3) + ' ns' : '-';
        
        let html = '<div class="info-row"><label>Entity Class</label><div class="value">' + nodeInfo.entity_class + '</div></div>' +
            '<div class="info-row"><label>Slack</label><div class="value">' + slackText + '</div></div>';
        
        if (analysis.analysis && Object.keys(analysis.analysis).length > 0) {
            html += '<div class="section-title">Analysis</div>';
            for (const [key, val] of Object.entries(analysis.analysis)) {
                html += '<div class="info-row"><label>' + key + '</label></div>';
            }
        }
        
        html += '<div class="section-title">Provenance</div>' +
            '<div class="provenance-link" onclick="showProvenance(' + "'" + nodeId + "'" + ')">View Source</div>';
        
        content.innerHTML = html;
        panel.classList.add('active');
    } catch (error) {
        console.error('Node info error:', error);
    }
}

// Feature 4: SuperNode Selector
async function loadSuperNodes() {
    try {
        const response = await fetch(API_BASE + '/supernodes');
        const data = await response.json();
        const select = document.getElementById('superNodeFilter');
        if (!select) return;
        
        data.supernodes.forEach(sn => {
            const option = document.createElement('option');
            option.value = sn.id;
            option.textContent = sn.super_class;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('SuperNode loading error:', error);
    }
}

// Feature 5: Terminal
async function executeTerminalQuery() {
    const input = document.getElementById('terminalInput');
    const output = document.getElementById('terminalOutput');
    if (!input || !output) return;
    
    const query = input.value.trim();
    if (!query) return;
    
    output.innerHTML += '<div class="terminal-line">' + query + '</div>';
    
    try {
        const response = await fetch(API_BASE + '/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        });
        const data = await response.json();
        output.innerHTML += '<div class="terminal-line">Result: ' + JSON.stringify(data) + '</div>';
    } catch (error) {
        output.innerHTML += '<div class="terminal-line error">Error: ' + error.message + '</div>';
    }
    
    input.value = '';
    output.scrollTop = output.scrollHeight;
}

// Feature 6: View & Context
function switchContext(context) {
    currentContext = context;
}

function switchView(view) {
    currentView = view;
    loadFullGraph();
}

// Feature 7: Provenance
async function showProvenance(nodeId) {
    try {
        const response = await fetch(API_BASE + '/node/' + nodeId + '/provenance');
        const data = await response.json();
        if (data.provenance && data.provenance.file) {
            alert('File: ' + data.provenance.file + ', Line: ' + data.provenance.line);
        } else {
            alert('No provenance info');
        }
    } catch (error) {
        console.error('Provenance error:', error);
    }
}

// Feature 8: Minimap
function initMinimap() {
    const minimap = document.getElementById('minimap');
    if (!minimap) return;
    const canvas = document.createElement('canvas');
    canvas.width = 200;
    canvas.height = 150;
    minimap.appendChild(canvas);
    setInterval(() => updateMinimap(canvas), 1000);
}

function updateMinimap(canvas) {
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#61dafb';
    cy.nodes().forEach(node => {
        const pos = node.position();
        ctx.fillRect(pos.x / 100, pos.y / 100, 2, 2);
    });
}

// Feature 9: Export
function exportGraph(format) {
    if (format === 'png') {
        const png = cy.png({ full: true, scale: 2 });
        const link = document.createElement('a');
        link.href = png;
        link.download = 'graph.png';
        link.click();
    } else if (format === 'csv') {
        exportNodesCSV();
    }
}

function exportNodesCSV() {
    const nodes = cy.nodes();
    let csv = 'ID,Label,Class,Slack\n';
    nodes.forEach(node => {
        const data = node.data();
        csv += data.id + ',' + data.label + ',' + data.entity_class + ',' + (data.slack || '0') + '\n';
    });
    
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'nodes.csv';
    link.click();
}

// Feature 10: Critical Path
async function showCriticalPath() {
    showLoading(true);
    try {
        const response = await fetch(API_BASE + '/critical/path');
        const data = await response.json();
        if (data.nodes) {
            animateCriticalPath(data.nodes, data.edges);
        }
    } catch (error) {
        console.error('Critical path error:', error);
    } finally {
        showLoading(false);
    }
}

async function animateCriticalPath(nodeIds, edgeIds) {
    cy.elements().addClass('dimmed');
    for (let i = 0; i < nodeIds.length; i++) {
        const node = cy.getElementById(nodeIds[i]);
        node.removeClass('dimmed');
        node.addClass('critical-path');
        await new Promise(r => setTimeout(r, 300));
    }
}

function resetCriticalPath() {
    cy.elements().removeClass('dimmed critical-path');
}

// Helper Functions
async function tracePath(nodeId) {
    closeContextMenu();
    const targetId = prompt('Target node ID:');
    if (!targetId) return;
    
    showLoading(true);
    try {
        const response = await fetch(API_BASE + '/paths?start=' + nodeId + '&end=' + targetId);
        const data = await response.json();
        if (data.paths && data.paths[0]) {
            animateCriticalPath(data.paths[0].nodes, data.paths[0].edges);
        }
    } catch (error) {
        console.error('Path error:', error);
    } finally {
        showLoading(false);
    }
}
