// Shared mutable state, image cache, and the global loading idler.
// Keep this file free of references to Graph or DOM elements that depend on
// other modules being loaded; everything in here is consumed by graph.js,
// detail.js, chain.js, and search.js.

// nodes (Map for O(1) lookup) and nodesArr (stable array for force-graph)
// must stay in sync. Mutate them only through addNode/collapseNode in
// graph.js; never push or splice nodesArr from elsewhere.
export const nodes = new Map();        // name -> node object
export const nodesArr = [];            // same node objects, stable array reference
export const links = [];               // {source, target, match, chain?}
export const linkKeys = new Set();     // canonical "a|||b" keys mirroring `links`
export const chainLinkKeys = new Set();// keys currently part of the rendered chain
export const detailCache = new Map();  // name -> artist info from /api/artist

let rootNodeName = null;
export function getRoot() { return rootNodeName; }
export function setRoot(name) { rootNodeName = name; }

export const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ---------------------------------------------------------------- image cache
// Values: HTMLImageElement (loaded), 'loading', null (failed/none)

export const imageCache = new Map();

export function getImage(name) {
  return imageCache.get(name) ?? null;
}

export function loadImage(name) {
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

// ------------------------------------------------------------- loading idler

const idlerEl = document.getElementById("search-idler");
let loadingCount = 0;

export function startLoading() {
  loadingCount++;
  idlerEl.hidden = false;
}

export function stopLoading() {
  loadingCount = Math.max(0, loadingCount - 1);
  if (loadingCount === 0) idlerEl.hidden = true;
}
