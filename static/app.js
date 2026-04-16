// Rex Explorer — artist graph UI

// ------------------------------------------------------------------ utils

function hashColor(name) {
  let h = 0;
  for (let i = 0; i < name.length; i++) {
    h = (Math.imul(31, h) + name.charCodeAt(i)) | 0;
  }
  const hue = Math.abs(h) % 360;
  return `hsl(${hue},65%,48%)`;
}

function initials(name) {
  const words = name.trim().split(/\s+/);
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

function fmtListeners(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M listeners`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K listeners`;
  return `${n} listeners`;
}

// ------------------------------------------------------------------ image cache
// Values: HTMLImageElement (loaded), 'loading', null (failed/none)

const imageCache = new Map();

function getImage(name) {
  return imageCache.get(name) ?? null;
}

function loadImage(name) {
  if (imageCache.has(name)) return;
  imageCache.set(name, 'loading');
  fetch(`/api/image?name=${encodeURIComponent(name)}`)
    .then(r => r.json())
    .then(data => {
      if (!data.url) { imageCache.set(name, null); return; }
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = () => {
        imageCache.set(name, img);
        Graph.refresh();
      };
      img.onerror = () => imageCache.set(name, null);
      img.src = data.url;
    })
    .catch(() => imageCache.set(name, null));
}

// ------------------------------------------------------------------ state

const nodes = new Map();   // name -> node object
const links = [];          // {source, target, match}
const detailCache = new Map(); // name -> artist info
let rootNodeName = null;   // name of the first/current root artist

// ------------------------------------------------------------------ pointer tracking

let pointerGraphCoords = null;
let pinnedNode = null;  // node currently frozen under the pointer

function pinNode(node) {
  if (pinnedNode === node) return;
  unpinCurrent();
  node.fx = node.x;
  node.fy = node.y;
  pinnedNode = node;
}

function unpinCurrent() {
  if (!pinnedNode) return;
  pinnedNode.fx = null;
  pinnedNode.fy = null;
  pinnedNode = null;
}

// ------------------------------------------------------------------ graph

const graphEl = document.getElementById("graph");

const Graph = ForceGraph()(graphEl)
  .backgroundColor("#0d0d0d")
  .nodeId("id")
  .nodeCanvasObject((node, ctx, globalScale) => {
    const r = node.expanded ? 22 : 18;
    const img = getImage(node.name);

    ctx.save();
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);

    if (img && img !== 'loading') {
      // clip to circle, draw portrait
      ctx.clip();
      ctx.drawImage(img, node.x - r, node.y - r, r * 2, r * 2);
      // subtle color tint overlay so the ring color stays visible
      ctx.globalAlpha = 0.15;
      ctx.fillStyle = node.color;
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.fill();
      ctx.globalAlpha = 1;
    } else {
      // fallback: solid color + initials
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

    // ring for expanded nodes
    if (node.expanded) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.strokeStyle = "rgba(255,255,255,0.45)";
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    // label below
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
  .linkWidth(link => Math.max(0.5, (link.match || 0) * 3))
  .linkColor(() => "rgba(255,255,255,0.12)")
  .onNodeClick(handleNodeClick)
  .d3AlphaDecay(0.03)
  .d3VelocityDecay(0.25)
  .warmupTicks(30)
  .cooldownTime(4000);

// Stronger node separation — default charge (-30) and link distance are too tight
Graph.d3Force('charge').strength(-350);
Graph.d3Force('link').distance(120);

// ------------------------------------------------------------------ pointer repulsion force

Graph.d3Force('pointer-repulsion', alpha => {
  if (!pointerGraphCoords) return;
  const RADIUS = 55;
  const STRENGTH = 0.7;
  const { x: px, y: py } = pointerGraphCoords;

  for (const node of nodes.values()) {
    if (node === pinnedNode) continue;  // pinned node stays put
    if (node.x == null || node.y == null) continue;
    const dx = node.x - px;
    const dy = node.y - py;
    const dist2 = dx * dx + dy * dy;
    if (dist2 < RADIUS * RADIUS && dist2 > 0.01) {
      const dist = Math.sqrt(dist2);
      const force = STRENGTH * alpha * (1 - dist / RADIUS);
      node.vx = (node.vx || 0) + (dx / dist) * force;
      node.vy = (node.vy || 0) + (dy / dist) * force;
    }
  }
});

const HIT_RADIUS = 24;  // match nodePointerAreaPaint radius

graphEl.addEventListener('mousemove', e => {
  const rect = graphEl.getBoundingClientRect();
  pointerGraphCoords = Graph.screen2GraphCoords(e.clientX - rect.left, e.clientY - rect.top);
  const { x: px, y: py } = pointerGraphCoords;

  // Find node directly under pointer and pin it; unpin when pointer moves off
  let hit = null;
  for (const node of nodes.values()) {
    if (node.x == null || node.y == null) continue;
    const dx = node.x - px;
    const dy = node.y - py;
    if (dx * dx + dy * dy < HIT_RADIUS * HIT_RADIUS) { hit = node; break; }
  }

  if (hit) {
    pinNode(hit);
  } else {
    unpinCurrent();
    // Reheat for repulsion only when not hovering a node
    const TRIGGER_RADIUS = 55;
    for (const node of nodes.values()) {
      if (node.x == null || node.y == null) continue;
      const dx = node.x - px;
      const dy = node.y - py;
      if (dx * dx + dy * dy < TRIGGER_RADIUS * TRIGGER_RADIUS) {
        Graph.d3ReheatSimulation();
        break;
      }
    }
  }
});

graphEl.addEventListener('mouseleave', () => {
  unpinCurrent();
  pointerGraphCoords = null;
});

// ------------------------------------------------------------------ responsive resize

const ro = new ResizeObserver(() => {
  Graph.width(graphEl.offsetWidth).height(graphEl.offsetHeight);
});
ro.observe(graphEl);
Graph.width(graphEl.offsetWidth).height(graphEl.offsetHeight);

// ------------------------------------------------------------------ graph helpers

function addNode(name, color, inits, tags = []) {
  if (nodes.has(name)) return nodes.get(name);
  const node = { id: name, name, color, initials: inits, tags, expanded: false };
  nodes.set(name, node);
  loadImage(name);   // kick off portrait fetch immediately
  return node;
}

function addLink(sourceName, targetName, match) {
  const key = [sourceName, targetName].sort().join("|||");
  if (links.some(l => {
    const a = l.source?.id ?? l.source;
    const b = l.target?.id ?? l.target;
    return [a, b].sort().join("|||") === key;
  })) return;
  links.push({ source: sourceName, target: targetName, match: match || 0 });
}

function refreshGraph() {
  Graph.graphData({
    nodes: [...nodes.values()],
    links: [...links],
  });
}

function reheat() {
  Graph.d3ReheatSimulation();
}

// ------------------------------------------------------------------ loading

const loadingEl = document.getElementById("loading");
let loadingCount = 0;

function startLoading() {
  loadingCount++;
  loadingEl.hidden = false;
}

function stopLoading() {
  loadingCount = Math.max(0, loadingCount - 1);
  if (loadingCount === 0) loadingEl.hidden = true;
}

// ------------------------------------------------------------------ detail panel

const detailPanel = document.getElementById("detail-panel");
const detailImg = document.getElementById("detail-img");
const detailName = document.getElementById("detail-name");
const detailListeners = document.getElementById("detail-listeners");
const detailTags = document.getElementById("detail-tags");
const detailBio = document.getElementById("detail-bio");
const detailLink = document.getElementById("detail-link");

document.getElementById("detail-close").addEventListener("click", () => {
  detailPanel.hidden = true;
});

async function showDetail(name) {
  detailPanel.hidden = false;
  detailName.textContent = name;
  detailListeners.textContent = "";
  detailTags.innerHTML = "";
  detailBio.textContent = "";
  detailLink.href = "#";
  detailImg.hidden = true;
  detailImg.src = "";

  // Show portrait if already loaded
  const cachedImg = imageCache.get(name);
  if (cachedImg && cachedImg !== 'loading') {
    detailImg.src = cachedImg.src;
    detailImg.hidden = false;
  } else if (cachedImg === 'loading' || !imageCache.has(name)) {
    // Wait for it — re-render when it arrives
    const checkInterval = setInterval(() => {
      const img = imageCache.get(name);
      if (img && img !== 'loading') {
        clearInterval(checkInterval);
        if (!detailPanel.hidden && detailName.textContent === name) {
          detailImg.src = img.src;
          detailImg.hidden = false;
        }
      } else if (img === null) {
        clearInterval(checkInterval);
      }
    }, 200);
  }

  let info = detailCache.get(name);
  if (!info) {
    try {
      const res = await fetch(`/api/artist?name=${encodeURIComponent(name)}`);
      info = await res.json();
      if (!info.error) detailCache.set(name, info);
    } catch (e) {
      return;
    }
  }
  if (info.error) return;

  detailName.textContent = info.name || name;
  detailListeners.textContent = info.listeners ? fmtListeners(info.listeners) : "";
  detailTags.innerHTML = (info.tags || []).slice(0, 6)
    .map(t => `<span class="tag">${escHtml(t)}</span>`).join("");
  detailBio.textContent = info.bio_summary || "";
  detailLink.href = info.url || "#";
}

// ------------------------------------------------------------------ expand / collapse

async function handleNodeClick(node) {
  showDetail(node.name);

  if (node.expanded) {
    collapseNode(node);
    return;
  }

  node.expanded = true;
  startLoading();

  try {
    const res = await fetch(`/api/similar?artist=${encodeURIComponent(node.name)}&limit=5`);
    const similar = await res.json();
    if (res.ok && Array.isArray(similar)) {
      for (const s of similar) {
        addNode(s.name, hashColor(s.name), initials(s.name));
        addLink(node.name, s.name, s.match);
      }
      refreshGraph();
      reheat();
    }
  } catch (e) {
    console.error("expand failed:", e);
  } finally {
    stopLoading();
  }
}

function collapseNode(node) {
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
    if (pinnedNode && pinnedNode.name === name) unpinCurrent();
    nodes.delete(name);
    detailCache.delete(name);
    imageCache.delete(name);
  }
  const removeLinks = links.filter(l => {
    const a = l.source?.id ?? l.source;
    const b = l.target?.id ?? l.target;
    return toRemove.has(a) || toRemove.has(b);
  });
  for (const l of removeLinks) links.splice(links.indexOf(l), 1);

  node.expanded = false;
  refreshGraph();
  reheat();
}

// ------------------------------------------------------------------ search

const searchInput = document.getElementById("search-input");
const searchResults = document.getElementById("search-results");
let searchTimer = null;

searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  const q = searchInput.value.trim();
  if (!q) { searchResults.hidden = true; return; }
  searchTimer = setTimeout(() => doSearch(q), 300);
});

searchInput.addEventListener("keydown", e => {
  if (e.key === "Escape") {
    searchResults.hidden = true;
    searchInput.blur();
  }
});

document.addEventListener("click", e => {
  if (!e.target.closest("#search-panel")) searchResults.hidden = true;
});

async function doSearch(q) {
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    renderSearchResults(data);
  } catch (e) {
    searchResults.hidden = true;
  }
}

function renderSearchResults(results) {
  if (!results.length) { searchResults.hidden = true; return; }
  searchResults.innerHTML = results.map(r => `
    <li data-name="${escHtml(r.name)}">
      <span class="result-name">${escHtml(r.name)}</span>
      <span class="result-listeners">${r.listeners ? fmtListeners(r.listeners) : ""}</span>
    </li>
  `).join("");
  searchResults.hidden = false;

  searchResults.querySelectorAll("li").forEach(li => {
    li.addEventListener("click", () => {
      const name = li.dataset.name;
      searchInput.value = name;
      searchResults.hidden = true;
      addRootArtist(name);
    });
  });
}

function escHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;");
}

// ------------------------------------------------------------------ zoom controls

const ZOOM_STEP = 1.5;
const ZOOM_DURATION = 300;

document.getElementById("btn-zoom-in").addEventListener("click", () => {
  Graph.zoom(Graph.zoom() * ZOOM_STEP, ZOOM_DURATION);
});

document.getElementById("btn-zoom-out").addEventListener("click", () => {
  Graph.zoom(Graph.zoom() / ZOOM_STEP, ZOOM_DURATION);
});

document.getElementById("btn-center").addEventListener("click", () => {
  if (!rootNodeName) return;
  const root = nodes.get(rootNodeName);
  if (!root || root.x == null) return;
  Graph.centerAt(root.x, root.y, 600);
  Graph.zoom(2.5, 600);
});

// ------------------------------------------------------------------ root artist

async function addRootArtist(name) {
  startLoading();
  try {
    const [infoRes, simRes] = await Promise.all([
      fetch(`/api/artist?name=${encodeURIComponent(name)}`),
      fetch(`/api/similar?artist=${encodeURIComponent(name)}&limit=5`),
    ]);
    const [info, similar] = await Promise.all([infoRes.json(), simRes.json()]);

    const canonName = info.name || name;
    const color = hashColor(canonName);
    const rootNode = addNode(canonName, color, initials(canonName), info.tags || []);
    rootNode.expanded = true;

    if (Array.isArray(similar)) {
      for (const s of similar) {
        addNode(s.name, hashColor(s.name), initials(s.name));
        addLink(canonName, s.name, s.match);
      }
    }

    if (!info.error) detailCache.set(canonName, info);
    showDetail(canonName);
    rootNodeName = canonName;

    refreshGraph();
    setTimeout(() => {
      Graph.centerAt(rootNode.x ?? 0, rootNode.y ?? 0, 800);
      Graph.zoom(2.5, 800);
    }, 400);
  } catch (e) {
    console.error("addRootArtist failed:", e);
  } finally {
    stopLoading();
  }
}
