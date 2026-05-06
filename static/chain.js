// Root-artist seeding, chain pathfinding, and click-to-expand orchestration.
// Holds the version counters used to discard stale fetches when the user
// re-roots or chains again before an in-flight request returns.

import { hashColor, initials, linkKey } from "./utils.js";
import {
  nodes, links, chainLinkKeys, detailCache,
  getRoot, setRoot, startLoading, stopLoading,
} from "./state.js";
import {
  Graph, addNode, addLink, refreshGraph, reheat,
  expandNode, collapseNode,
} from "./graph.js";
import { showDetail } from "./detail.js";

const searchInput = document.getElementById("search-input");
const searchClear = document.getElementById("search-clear");
const searchError = document.getElementById("search-error");
const connectInput = document.getElementById("connect-input");
const connectClear = document.getElementById("connect-clear");
const connectResults = document.getElementById("connect-results");
const connectWrap = document.getElementById("connect-wrap");
const connectHint = document.getElementById("connect-hint");
const connectSpacer = document.getElementById("connect-spacer");
const connectError = document.getElementById("connect-error");
const clearChainBtn = document.getElementById("clear-chain");

function hideConnectResults() {
  connectResults.hidden = true;
  connectInput.setAttribute("aria-expanded", "false");
  connectInput.removeAttribute("aria-activedescendant");
}

// ----------------------------------------------------------------- click

export async function handleNodeClick(node) {
  showDetail(node.name);

  if (getRoot() && node.name !== getRoot()) {
    setRoot(node.name);
    searchInput.value = node.name;
    searchClear.classList.add("visible");
    connectInput.placeholder = `Find connection from ${node.name}…`;
    connectInput.value = "";
    connectClear.classList.remove("visible");
    hideConnectResults();
    searchError.hidden = true;
  }

  if (node.expanded) {
    collapseNode(node);
    return;
  }
  await expandNode(node);
}

Graph.onNodeClick(handleNodeClick);

// ----------------------------------------------------------------- chain

export function clearChain() {
  for (const l of links) {
    if (l.chain) l.chain = false;
  }
  chainLinkKeys.clear();
  clearChainBtn.hidden = true;
  refreshGraph();
}

clearChainBtn.addEventListener("click", () => {
  clearChain();
  connectInput.value = "";
  connectClear.classList.remove("visible");
});

let addChainVersion = 0;

export async function addChainTo(targetName) {
  const myVersion = ++addChainVersion;
  const myRoot = getRoot();
  startLoading();
  connectError.hidden = true;
  try {
    const res = await fetch(
      `/api/chain?from=${encodeURIComponent(myRoot)}&to=${encodeURIComponent(targetName)}`
    );
    const data = await res.json();
    if (myVersion !== addChainVersion || getRoot() !== myRoot) return;
    if (!res.ok || data.error) {
      connectError.textContent = data.error || "no chain found";
      connectError.hidden = false;
      connectInput.value = "";
      connectClear.classList.remove("visible");
      return;
    }

    const path = data.path;
    clearChain();

    const rootNode = nodes.get(myRoot);
    const existingTarget = nodes.get(targetName);
    const rx = rootNode?.x ?? 0;
    const ry = rootNode?.y ?? 0;
    const tx = existingTarget?.x ?? rx + 400;
    const ty = existingTarget?.y ?? ry + 400;

    for (let i = 0; i < path.length; i++) {
      const n = addNode(path[i].name, hashColor(path[i].name), initials(path[i].name));
      if (n.x == null) {
        const t = path.length > 1 ? i / (path.length - 1) : 0.5;
        n.x = rx + (tx - rx) * t + (Math.random() - 0.5) * 50;
        n.y = ry + (ty - ry) * t + (Math.random() - 0.5) * 50;
      }
    }

    const newKeys = new Set();
    for (let i = 0; i < path.length - 1; i++) {
      const a = path[i].name;
      const b = path[i + 1].name;
      const match = path[i].match_to_next || 0;
      addLink(a, b, match);
      newKeys.add(linkKey(a, b));
    }

    for (const l of links) {
      const la = l.source?.id ?? l.source;
      const lb = l.target?.id ?? l.target;
      const key = linkKey(la, lb);
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
    if (myVersion !== addChainVersion) return;
    console.error("addChainTo failed:", e);
  } finally {
    stopLoading();
  }
}

// ---------------------------------------------------------- root artist

let addRootVersion = 0;

export async function addRootArtist(name) {
  const myVersion = ++addRootVersion;
  searchError.hidden = true;
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
    setRoot(canonName);
    connectInput.placeholder = `Find connection from ${canonName}…`;
    connectWrap.hidden = false;
    connectHint.hidden = false;
    connectSpacer.hidden = false;

    // Keep the seed name visible in the search input as the current-root
    // display. Subsequent click-to-change-root in handleNodeClick replaces
    // it with the newly clicked artist.
    if (myVersion === addRootVersion) {
      searchInput.value = canonName;
      searchClear.classList.add("visible");
    }

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
