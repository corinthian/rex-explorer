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
const chainLinkKeys = new Set(); // sorted link keys currently part of the chain

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
  .backgroundColor("rgba(0,0,0,0)")
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
  .linkWidth(link => link.chain ? 4 : Math.max(0.5, (link.match || 0) * 3))
  .linkColor(link => link.chain ? '#f0b060' : "rgba(255,255,255,0.12)")
  .nodeLabel('')
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

// ------------------------------------------------------------------ background graph (landing animation)

const bgEl = document.getElementById("bg-graph");
const bgNodes = new Map();
const bgLinks = [];

const BgGraph = ForceGraph()(bgEl)
  .backgroundColor("rgba(0,0,0,0)")
  .nodeId("id")
  .nodeCanvasObject((node, ctx) => {
    ctx.save();
    ctx.beginPath();
    ctx.arc(node.x, node.y, node.isRoot ? 5 : 3, 0, 2 * Math.PI);
    ctx.fillStyle = node.isRoot
      ? "rgba(224,90,84,0.35)"
      : "rgba(200,200,200,0.15)";
    ctx.fill();
    ctx.restore();
  })
  .linkColor(() => "rgba(255,255,255,0.06)")
  .linkWidth(0.8)
  .nodeLabel("")
  .d3AlphaMin(0)        // never stop due to alpha threshold
  .d3AlphaDecay(0.008)  // settle quickly so high-energy phase is brief
  .d3VelocityDecay(0.3)
  .warmupTicks(200)
  .cooldownTicks(Infinity);

BgGraph.d3Force("charge").strength(-180);
BgGraph.d3Force("link").distance(90);

// Gentle vortex: nodes orbit slowly around graph origin — unscaled by alpha
// so it persists indefinitely after the simulation settles
BgGraph.d3Force("drift", () => {
  const SPEED = 0.000008;
  for (const node of bgNodes.values()) {
    if (node.x == null) continue;
    node.vx = (node.vx || 0) - node.y * SPEED;
    node.vy = (node.vy || 0) + node.x * SPEED;
  }
});

const bgRo = new ResizeObserver(() => {
  BgGraph.width(bgEl.offsetWidth).height(bgEl.offsetHeight);
});
bgRo.observe(bgEl);
BgGraph.width(bgEl.offsetWidth).height(bgEl.offsetHeight);

async function loadBgGraph() {
  const ROOT = "Antonín Dvořák";
  try {
    bgNodes.set(ROOT, { id: ROOT, isRoot: true });

    const rootSim = await fetch(`/api/similar?artist=${encodeURIComponent(ROOT)}&limit=5`).then(r => r.json());
    if (!Array.isArray(rootSim)) return;

    for (const s of rootSim) {
      if (!bgNodes.has(s.name)) bgNodes.set(s.name, { id: s.name, isRoot: false });
      bgLinks.push({ source: ROOT, target: s.name });
    }

    // 5 expansions — one per child of Dvořák, in parallel
    const childResults = await Promise.all(
      rootSim.map(s =>
        fetch(`/api/similar?artist=${encodeURIComponent(s.name)}&limit=5`).then(r => r.json())
      )
    );

    for (let i = 0; i < rootSim.length; i++) {
      const parent = rootSim[i].name;
      const children = childResults[i];
      if (!Array.isArray(children)) continue;
      for (const cs of children) {
        if (!bgNodes.has(cs.name)) bgNodes.set(cs.name, { id: cs.name, isRoot: false });
        bgLinks.push({ source: parent, target: cs.name });
      }
    }

    BgGraph.graphData({ nodes: [...bgNodes.values()], links: bgLinks });
    setTimeout(() => BgGraph.zoomToFit(500, 60), 900);
  } catch (e) {
    // background decoration — ignore failures silently
  }
}

loadBgGraph();

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

document.getElementById("detail-center").addEventListener("click", () => {
  const name = detailName.textContent;
  if (!name) return;
  const node = nodes.get(name);
  if (!node || node.x == null) return;
  Graph.centerAt(node.x, node.y, 600);
  Graph.zoom(2.5, 600);
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
      if (detailPanel.hidden || detailName.textContent !== name) return;
      if (!info.error) detailCache.set(name, info);
    } catch (e) {
      return;
    }
  }
  if (info.error) return;
  if (detailPanel.hidden || detailName.textContent !== name) return;

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

  if (rootNodeName && node.name !== rootNodeName) {
    rootNodeName = node.name;
    searchInput.value = node.name;
    searchClear.classList.add("visible");
    connectInput.placeholder = `Find connection from ${node.name}…`;
    connectInput.value = "";
    connectClear.classList.remove("visible");
    connectResults.hidden = true;
    searchError.hidden = true;
  }

  if (node.expanded) {
    collapseNode(node);
    return;
  }

  node.expanded = true;
  node.abortController = new AbortController();
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
    if (node.abortController) node.abortController = null;
    stopLoading();
  }
}

function collapseNode(node) {
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
const searchClear = document.getElementById("search-clear");
const searchError = document.getElementById("search-error");
let searchTimer = null;

searchInput.addEventListener("input", () => {
  searchClear.classList.toggle("visible", searchInput.value.length > 0);
  searchError.hidden = true;
  clearTimeout(searchTimer);
  const q = searchInput.value.trim();
  if (!q) { searchResults.hidden = true; return; }
  searchTimer = setTimeout(() => doSearch(q), 300);
});

searchClear.addEventListener("click", () => {
  searchInput.value = "";
  searchClear.classList.remove("visible");
  searchResults.hidden = true;
  searchError.hidden = true;
  searchInput.focus();
});

searchInput.addEventListener("keydown", e => {
  if (e.key === "Escape") {
    searchResults.hidden = true;
    searchInput.blur();
  }
});

document.addEventListener("click", e => {
  if (!e.target.closest("#search-panel")) {
    searchResults.hidden = true;
    connectResults.hidden = true;
  }
});

let searchVersion = 0;

async function doSearch(q) {
  const myVersion = ++searchVersion;
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    if (myVersion !== searchVersion) return;
    if (searchInput.value.trim() !== q) return;
    if (!res.ok || (data && data.error)) {
      searchResults.hidden = true;
      searchError.textContent = (data && data.error) || "Search failed";
      searchError.hidden = false;
      return;
    }
    renderSearchResults(data);
  } catch (e) {
    if (myVersion !== searchVersion) return;
    searchResults.hidden = true;
  }
}

function renderResultItems(listEl, results, onPick) {
  listEl.innerHTML = results.map(r => `
    <li data-name="${escHtml(r.name)}">
      <span class="result-name">${escHtml(r.name)}</span>
      <span class="result-listeners">${r.listeners ? fmtListeners(r.listeners) : ""}</span>
    </li>
  `).join("");
  listEl.hidden = false;
  listEl.querySelectorAll("li").forEach(li => {
    li.addEventListener("click", () => onPick(li.dataset.name));
  });
}

function renderSearchResults(results) {
  if (!Array.isArray(results)) {
    searchResults.hidden = true;
    searchError.textContent = "Search failed";
    searchError.hidden = false;
    return;
  }
  if (!results.length) {
    searchResults.hidden = true;
    searchError.textContent = "No results for that artist — try another name";
    searchError.hidden = false;
    return;
  }
  searchError.hidden = true;
  renderResultItems(searchResults, results, name => {
    searchInput.value = name;
    searchResults.hidden = true;
    document.body.classList.add("graph-active");
    BgGraph.pauseAnimation();
    addRootArtist(name);
  });
}

// ------------------------------------------------------------------ connect input

const connectWrap = document.getElementById("connect-wrap");
const connectInput = document.getElementById("connect-input");
const connectClear = document.getElementById("connect-clear");
const connectResults = document.getElementById("connect-results");
const connectHint = document.getElementById("connect-hint");
const connectSpacer = document.getElementById("connect-spacer");
let connectTimer = null;
let connectVersion = 0;

connectInput.addEventListener("input", () => {
  connectClear.classList.toggle("visible", connectInput.value.length > 0);
  clearTimeout(connectTimer);
  const q = connectInput.value.trim();
  if (!q) { connectResults.hidden = true; return; }
  connectTimer = setTimeout(async () => {
    const myVersion = ++connectVersion;
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      if (myVersion !== connectVersion) return;
      if (connectInput.value.trim() !== q) return;
      if (!res.ok || (data && data.error)) {
        connectResults.hidden = true;
        searchError.textContent = (data && data.error) || "Search failed";
        searchError.hidden = false;
        return;
      }
      if (!Array.isArray(data) || !data.length) { connectResults.hidden = true; return; }
      renderResultItems(connectResults, data, name => {
        connectInput.value = "";
        connectClear.classList.remove("visible");
        connectResults.hidden = true;
        addChainTo(name);
      });
    } catch (e) {
      if (myVersion !== connectVersion) return;
      connectResults.hidden = true;
    }
  }, 300);
});

connectClear.addEventListener("click", () => {
  connectInput.value = "";
  connectClear.classList.remove("visible");
  connectResults.hidden = true;
  connectInput.focus();
});

connectInput.addEventListener("keydown", e => {
  if (e.key === "Escape") {
    connectResults.hidden = true;
    connectInput.blur();
  }
});

function escHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;");
}

// ------------------------------------------------------------------ floating tooltip
// Used for buttons inside overflow:hidden containers where CSS ::after is clipped.

const floatingTip = document.createElement('div');
Object.assign(floatingTip.style, {
  position: 'fixed', background: '#e8e8e8', color: '#111',
  fontSize: '13px', fontWeight: '500', fontFamily: 'inherit',
  padding: '5px 10px', borderRadius: '5px',
  pointerEvents: 'none', display: 'none', zIndex: '9999', whiteSpace: 'nowrap',
});
document.body.appendChild(floatingTip);

function attachFloatingTooltip(el, text) {
  el.addEventListener('mouseenter', () => {
    floatingTip.textContent = text;
    floatingTip.style.display = 'block';
    const r = el.getBoundingClientRect();
    const t = floatingTip.getBoundingClientRect();
    floatingTip.style.left = `${r.left - t.width - 8}px`;
    floatingTip.style.top  = `${r.top + (r.height - t.height) / 2}px`;
  });
  el.addEventListener('mouseleave', () => { floatingTip.style.display = 'none'; });
}

attachFloatingTooltip(document.getElementById('detail-center'), 'Center on artist');

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

// ------------------------------------------------------------------ chain

const clearChainBtn = document.getElementById("clear-chain");

function clearChain() {
  for (const l of links) {
    if (l.chain) l.chain = false;
  }
  chainLinkKeys.clear();
  clearChainBtn.hidden = true;
  refreshGraph();
}

clearChainBtn.addEventListener("click", clearChain);

async function addChainTo(targetName) {
  startLoading();
  try {
    const res = await fetch(
      `/api/chain?from=${encodeURIComponent(rootNodeName)}&to=${encodeURIComponent(targetName)}`
    );
    const data = await res.json();
    if (!res.ok || data.error) {
      searchError.textContent = data.error || "no chain found";
      searchError.hidden = false;
      return;
    }

    const path = data.path;
    clearChain();

    // Capture endpoint positions before adding new nodes
    const rootNode = nodes.get(rootNodeName);
    const existingTarget = nodes.get(targetName);
    const rx = rootNode?.x ?? 0;
    const ry = rootNode?.y ?? 0;
    const tx = existingTarget?.x ?? rx + 400;
    const ty = existingTarget?.y ?? ry + 400;

    // Add chain nodes, placing new ones along the line between endpoints
    for (let i = 0; i < path.length; i++) {
      const n = addNode(path[i].name, hashColor(path[i].name), initials(path[i].name));
      if (n.x == null) {
        const t = path.length > 1 ? i / (path.length - 1) : 0.5;
        n.x = rx + (tx - rx) * t + (Math.random() - 0.5) * 50;
        n.y = ry + (ty - ry) * t + (Math.random() - 0.5) * 50;
      }
    }

    // Add links and collect chain keys
    const newKeys = new Set();
    for (let i = 0; i < path.length - 1; i++) {
      const a = path[i].name;
      const b = path[i + 1].name;
      const match = path[i].match_to_next || 0;
      addLink(a, b, match);
      newKeys.add([a, b].sort().join("|||"));
    }

    // Tag link objects as chain
    for (const l of links) {
      const la = l.source?.id ?? l.source;
      const lb = l.target?.id ?? l.target;
      const key = [la, lb].sort().join("|||");
      if (newKeys.has(key)) {
        l.chain = true;
        chainLinkKeys.add(key);
      }
    }

    clearChainBtn.hidden = false;
    refreshGraph();
    reheat();
    setTimeout(() => Graph.zoomToFit(600, 60), 800);
  } catch (e) {
    console.error("addChainTo failed:", e);
  } finally {
    stopLoading();
  }
}

let addRootVersion = 0;

async function addRootArtist(name) {
  const myVersion = ++addRootVersion;
  startLoading();
  try {
    const [infoRes, simRes] = await Promise.all([
      fetch(`/api/artist?name=${encodeURIComponent(name)}`),
      fetch(`/api/similar?artist=${encodeURIComponent(name)}&limit=5`),
    ]);
    const [info, similar] = await Promise.all([infoRes.json(), simRes.json()]);
    if (myVersion !== addRootVersion) return;

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
    connectInput.placeholder = `Find connection from ${canonName}…`;
    connectWrap.hidden = false;
    connectHint.hidden = false;
    connectSpacer.hidden = false;

    refreshGraph();
    document.getElementById("controls").classList.add("controls-visible");
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
