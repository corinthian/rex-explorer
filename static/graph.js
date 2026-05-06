// Main force-directed graph: instance, canvas rendering, force config, helpers,
// per-node loading pulse, pointer repulsion, expand/collapse, zoom controls.
// Click handling is wired by app.js so this module does not need to know
// about the detail panel.

import { hashColor, initials, linkKey } from "./utils.js";
import {
  nodes, nodesArr, links, linkKeys, chainLinkKeys, detailCache, imageCache,
  getImage, loadImage, getRoot, reducedMotion,
  startLoading, stopLoading,
} from "./state.js";

const graphEl = document.getElementById("graph");

// ------------------------------------------------------------ per-node loading

let loadingNodeCount = 0;
let pulseRafHandle = null;
let lastPulseReheat = 0;

function pulseLoop() {
  if (loadingNodeCount === 0) {
    pulseRafHandle = null;
    return;
  }
  const now = performance.now();
  if (now - lastPulseReheat > 500) {
    Graph.d3ReheatSimulation();
    lastPulseReheat = now;
  }
  pulseRafHandle = requestAnimationFrame(pulseLoop);
}

export function beginNodeLoading(node) {
  if (node.loading) return;
  node.loading = true;
  loadingNodeCount++;
  if (pulseRafHandle === null) {
    lastPulseReheat = 0;
    pulseRafHandle = requestAnimationFrame(pulseLoop);
  }
}

export function endNodeLoading(node) {
  if (!node.loading) return;
  node.loading = false;
  loadingNodeCount = Math.max(0, loadingNodeCount - 1);
}

// ------------------------------------------------------------- pointer state

let pointerGraphCoords = null;
let pinnedNode = null;

function pinNode(node) {
  if (pinnedNode === node) return;
  unpinCurrent();
  node.fx = node.x;
  node.fy = node.y;
  pinnedNode = node;
}

export function unpinCurrent() {
  if (!pinnedNode) return;
  pinnedNode.fx = null;
  pinnedNode.fy = null;
  pinnedNode = null;
}

export function isPinned(node) {
  return pinnedNode === node;
}

// ------------------------------------------------------------------ Graph

export const Graph = ForceGraph()(graphEl)
  .backgroundColor("rgba(0,0,0,0)")
  .nodeId("id")
  .nodeCanvasObject((node, ctx, globalScale) => {
    const r = node.expanded ? 22 : 18;
    const img = getImage(node.name);

    ctx.save();
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);

    if (img && img !== 'loading') {
      ctx.clip();
      ctx.drawImage(img, node.x - r, node.y - r, r * 2, r * 2);
      ctx.globalAlpha = 0.15;
      ctx.fillStyle = node.color;
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.fill();
      ctx.globalAlpha = 1;
    } else {
      ctx.fillStyle = node.color;
      ctx.fill();
      const fontSize = Math.max(9, r * 0.65);
      ctx.font = `600 ${fontSize}px -apple-system, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = "rgba(255,255,255,0.9)";
      ctx.fillText(node.initials, node.x, node.y);
    }

    ctx.restore();

    if (node.loading) {
      const alpha = reducedMotion
        ? 0.5
        : 0.25 + 0.45 * (0.5 + 0.5 * Math.sin((performance.now() / 600) * Math.PI));
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 5, 0, 2 * Math.PI);
      ctx.strokeStyle = `rgba(255,255,255,${alpha})`;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    if (node.expanded) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.strokeStyle = "rgba(255,255,255,0.45)";
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    const labelSize = Math.max(8, 11 / globalScale);
    ctx.font = `${labelSize}px -apple-system, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillStyle = "rgba(220,220,220,0.85)";
    ctx.fillText(node.name, node.x, node.y + r + 3);
  })
  .nodePointerAreaPaint((node, color, ctx) => {
    const r = 24;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fill();
  })
  .linkWidth(link => link.chain ? 4 : Math.max(0.5, (link.match || 0) * 3))
  .linkColor(link => link.chain ? '#f0b060' : "rgba(255,255,255,0.12)")
  .nodeLabel('')
  .d3AlphaDecay(0.03)
  .d3VelocityDecay(0.25)
  .warmupTicks(30)
  .cooldownTime(4000);

Graph.d3Force('charge').strength(-350);
Graph.d3Force('link').distance(120);

// ----------------------------------------------------- pointer repulsion force

const PINNING_RADIUS = 55;  // graph-coord radius for both pinning and repulsion

Graph.d3Force('pointer-repulsion', alpha => {
  if (!pointerGraphCoords) return;
  const STRENGTH = 0.7;
  const { x: px, y: py } = pointerGraphCoords;

  for (const node of nodes.values()) {
    if (isPinned(node)) continue;
    if (node.x == null || node.y == null) continue;
    const dx = node.x - px;
    const dy = node.y - py;
    const dist2 = dx * dx + dy * dy;
    if (dist2 < PINNING_RADIUS * PINNING_RADIUS && dist2 > 0.01) {
      const dist = Math.sqrt(dist2);
      const force = STRENGTH * alpha * (1 - dist / PINNING_RADIUS);
      node.vx = (node.vx || 0) + (dx / dist) * force;
      node.vy = (node.vy || 0) + (dy / dist) * force;
    }
  }
});

graphEl.addEventListener('mousemove', e => {
  const rect = graphEl.getBoundingClientRect();
  pointerGraphCoords = Graph.screen2GraphCoords(e.clientX - rect.left, e.clientY - rect.top);
  const { x: px, y: py } = pointerGraphCoords;

  // Pin the closest node within PINNING_RADIUS so it never flees the cursor.
  // Other nodes inside the same radius still feel the repulsion force, which
  // helps disambiguate clusters; the pinned target stays put for clicking.
  let hit = null;
  let bestDist2 = PINNING_RADIUS * PINNING_RADIUS;
  for (const node of nodes.values()) {
    if (node.x == null || node.y == null) continue;
    const dx = node.x - px;
    const dy = node.y - py;
    const d2 = dx * dx + dy * dy;
    if (d2 < bestDist2) { bestDist2 = d2; hit = node; }
  }

  if (hit) {
    pinNode(hit);
  } else {
    unpinCurrent();
  }
});

graphEl.addEventListener('mouseleave', () => {
  unpinCurrent();
  pointerGraphCoords = null;
});

// --------------------------------------------------------- responsive resize

const ro = new ResizeObserver(() => {
  Graph.width(graphEl.offsetWidth).height(graphEl.offsetHeight);
});
ro.observe(graphEl);
Graph.width(graphEl.offsetWidth).height(graphEl.offsetHeight);

// -------------------------------------------------------------- graph helpers

export function addNode(name, color, inits, tags = []) {
  if (nodes.has(name)) return nodes.get(name);
  const node = { id: name, name, color, initials: inits, tags, expanded: false };
  nodes.set(name, node);
  nodesArr.push(node);
  loadImage(name);
  return node;
}

export function addLink(sourceName, targetName, match) {
  const key = linkKey(sourceName, targetName);
  if (linkKeys.has(key)) return;
  linkKeys.add(key);
  links.push({ source: sourceName, target: targetName, match: match || 0 });
}

export function refreshGraph() {
  Graph.graphData({ nodes: nodesArr, links });
}

export function reheat() {
  Graph.d3ReheatSimulation();
}

// ------------------------------------------------------------ expand / collapse

export async function expandNode(node) {
  if (node.expanded) return;
  node.expanded = true;
  node.abortController = new AbortController();
  beginNodeLoading(node);
  startLoading();

  try {
    const res = await fetch(
      `/api/similar?artist=${encodeURIComponent(node.name)}&limit=5`,
      { signal: node.abortController.signal }
    );
    const similar = await res.json();
    if (!node.expanded) return;
    if (res.ok && Array.isArray(similar)) {
      for (const s of similar) {
        addNode(s.name, hashColor(s.name), initials(s.name));
        addLink(node.name, s.name, s.match);
      }
      refreshGraph();
      reheat();
    }
  } catch (e) {
    if (e.name === 'AbortError') return;
    console.error("expand failed:", e);
  } finally {
    endNodeLoading(node);
    if (node.abortController) node.abortController = null;
    stopLoading();
  }
}

export function collapseNode(node) {
  if (node.abortController) {
    node.abortController.abort();
    node.abortController = null;
  }
  const childNames = links
    .filter(l => {
      const a = l.source?.id ?? l.source;
      const b = l.target?.id ?? l.target;
      return a === node.name || b === node.name;
    })
    .map(l => {
      const a = l.source?.id ?? l.source;
      const b = l.target?.id ?? l.target;
      return a === node.name ? b : a;
    });

  const toRemove = new Set();
  for (const childName of childNames) {
    const childNode = nodes.get(childName);
    if (!childNode || childNode.expanded) continue;
    const parentCount = links.filter(l => {
      const a = l.source?.id ?? l.source;
      const b = l.target?.id ?? l.target;
      const other = a === childName ? b : a;
      return (a === childName || b === childName) && other !== node.name;
    }).length;
    if (parentCount === 0) toRemove.add(childName);
  }

  for (const name of toRemove) {
    const child = nodes.get(name);
    if (isPinned(child)) unpinCurrent();
    nodes.delete(name);
    const idx = nodesArr.indexOf(child);
    if (idx !== -1) nodesArr.splice(idx, 1);
    detailCache.delete(name);
    // Keep imageCache: a re-expansion of the same artist would otherwise
    // pay another /api/image round-trip for an already-resolved portrait.
  }
  const removeLinks = links.filter(l => {
    const a = l.source?.id ?? l.source;
    const b = l.target?.id ?? l.target;
    return toRemove.has(a) || toRemove.has(b);
  });
  for (const l of removeLinks) {
    const a = l.source?.id ?? l.source;
    const b = l.target?.id ?? l.target;
    linkKeys.delete(linkKey(a, b));
    chainLinkKeys.delete(linkKey(a, b));
    links.splice(links.indexOf(l), 1);
  }

  node.expanded = false;
  refreshGraph();
  reheat();
}

// ------------------------------------------------------------- zoom controls

const ZOOM_STEP = 1.5;
const ZOOM_DURATION = 300;

export function zoomIn() {
  Graph.zoom(Graph.zoom() * ZOOM_STEP, ZOOM_DURATION);
}

export function zoomOut() {
  Graph.zoom(Graph.zoom() / ZOOM_STEP, ZOOM_DURATION);
}

export function centerOnRoot() {
  const rootName = getRoot();
  if (!rootName) return;
  const root = nodes.get(rootName);
  if (!root || root.x == null) return;
  Graph.centerAt(root.x, root.y, 600);
  Graph.zoom(2.5, 600);
}

document.getElementById("btn-zoom-in").addEventListener("click", zoomIn);
document.getElementById("btn-zoom-out").addEventListener("click", zoomOut);
document.getElementById("btn-center").addEventListener("click", centerOnRoot);
