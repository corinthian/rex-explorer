// Detail panel: hero image + bio + tags + link, plus the help overlay
// (also used by the landing-popup help). Owns the image-poll lifecycle and
// the floating tooltip used inside overflow:hidden containers.

import { escHtml, fmtListeners } from "./utils.js";
import { nodes, detailCache, imageCache } from "./state.js";
import { Graph } from "./graph.js";

const detailPanel = document.getElementById("detail-panel");
const detailImg = document.getElementById("detail-img");
const detailName = document.getElementById("detail-name");
const detailListeners = document.getElementById("detail-listeners");
const detailTags = document.getElementById("detail-tags");
const detailBio = document.getElementById("detail-bio");
const detailLink = document.getElementById("detail-link");

const detailArtistView = document.getElementById("detail-artist-view");
const detailHelpView = document.getElementById("detail-help-view");
const detailHelpBtn = document.getElementById("detail-help");

const landingAboutView = document.getElementById("landing-about-view");
const landingHelpView = document.getElementById("landing-help-view");
const landingHelpBtn = document.getElementById("landing-help");

let detailImagePoll = null;

export function clearDetailImagePoll() {
  if (detailImagePoll !== null) {
    clearInterval(detailImagePoll);
    detailImagePoll = null;
  }
}

export function isDetailHidden() { return detailPanel.hidden; }
export function isDetailHelpOpen() { return !detailHelpView.hidden; }
export function isLandingHelpOpen() { return !landingHelpView.hidden; }

export function setHelpOpen(open) {
  detailHelpView.hidden = !open;
  detailArtistView.hidden = open;
  detailHelpBtn.textContent = open ? "←" : "?";
  detailHelpBtn.setAttribute("aria-label", open ? "Back" : "Help");
  detailHelpBtn.setAttribute("aria-expanded", open ? "true" : "false");
}

export function setLandingHelpOpen(open) {
  landingHelpView.hidden = !open;
  landingAboutView.hidden = open;
  landingHelpBtn.textContent = open ? "←" : "?";
  landingHelpBtn.setAttribute("aria-label", open ? "Back" : "Help");
  landingHelpBtn.setAttribute("aria-expanded", open ? "true" : "false");
}

export function closeDetail() {
  detailPanel.hidden = true;
  setHelpOpen(false);
  clearDetailImagePoll();
}

document.getElementById("detail-close").addEventListener("click", closeDetail);
detailHelpBtn.addEventListener("click", () => {
  setHelpOpen(detailHelpView.hidden);
});
landingHelpBtn.addEventListener("click", () => {
  setLandingHelpOpen(landingHelpView.hidden);
});

document.getElementById("detail-center").addEventListener("click", () => {
  const name = detailName.textContent;
  if (!name) return;
  const node = nodes.get(name);
  if (!node || node.x == null) return;
  Graph.centerAt(node.x, node.y, 600);
  Graph.zoom(2.5, 600);
});

export async function showDetail(name) {
  clearDetailImagePoll();
  detailPanel.hidden = false;
  setHelpOpen(false);
  detailName.textContent = name;
  detailListeners.textContent = "";
  detailTags.innerHTML = "";
  detailBio.textContent = "";
  detailLink.href = "#";
  detailImg.hidden = true;
  detailImg.src = "";

  const cachedImg = imageCache.get(name);
  if (cachedImg && cachedImg !== 'loading') {
    detailImg.src = cachedImg.src;
    detailImg.hidden = false;
  } else if (cachedImg === 'loading' || !imageCache.has(name)) {
    detailImagePoll = setInterval(() => {
      if (detailPanel.hidden || detailName.textContent !== name) {
        clearDetailImagePoll();
        return;
      }
      const img = imageCache.get(name);
      if (img && img !== 'loading') {
        clearDetailImagePoll();
        detailImg.src = img.src;
        detailImg.hidden = false;
      } else if (img === null) {
        clearDetailImagePoll();
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

// Floating tooltip for buttons inside overflow:hidden containers (where
// CSS ::after tooltips clip).

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
