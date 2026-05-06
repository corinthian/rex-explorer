// Search and connect inputs: input handling, debounced /api/search calls,
// ARIA combobox dropdown rendering, and the landing → graph-active flow.

import { escHtml, fmtListeners } from "./utils.js";
import { addRootArtist, addChainTo } from "./chain.js";
import { BgGraph } from "./bg-graph.js";

const searchInput = document.getElementById("search-input");
const searchResults = document.getElementById("search-results");
const searchClear = document.getElementById("search-clear");
const searchError = document.getElementById("search-error");

const connectInput = document.getElementById("connect-input");
const connectClear = document.getElementById("connect-clear");
const connectResults = document.getElementById("connect-results");
const connectError = document.getElementById("connect-error");

let searchTimer = null;
let searchVersion = 0;
let connectTimer = null;
let connectVersion = 0;

// ---------------------------------------------------------- dropdown helpers

function inputForList(listEl) {
  return document.getElementById(listEl.id === "search-results" ? "search-input" : "connect-input");
}

function showResults(listEl) {
  listEl.hidden = false;
  inputForList(listEl).setAttribute("aria-expanded", "true");
}

export function hideResults(listEl) {
  listEl.hidden = true;
  const input = inputForList(listEl);
  input.setAttribute("aria-expanded", "false");
  input.removeAttribute("aria-activedescendant");
}

function highlightResult(listEl, idx) {
  const items = [...listEl.querySelectorAll("li")];
  if (!items.length) return;
  items.forEach((li, i) => li.classList.toggle("highlighted", i === idx));
  if (idx >= 0) {
    items[idx].scrollIntoView({ block: "nearest" });
    inputForList(listEl).setAttribute("aria-activedescendant", items[idx].id);
  } else {
    inputForList(listEl).removeAttribute("aria-activedescendant");
  }
}

function moveHighlight(listEl, delta) {
  const items = listEl.querySelectorAll("li");
  if (!items.length) return;
  const cur = [...items].findIndex(li => li.classList.contains("highlighted"));
  let next;
  if (cur < 0) next = delta > 0 ? 0 : items.length - 1;
  else next = (cur + delta + items.length) % items.length;
  highlightResult(listEl, next);
}

function activateHighlight(listEl) {
  const items = listEl.querySelectorAll("li");
  if (!items.length) return;
  const cur = [...items].findIndex(li => li.classList.contains("highlighted"));
  (cur >= 0 ? items[cur] : items[0]).click();
}

function renderResultItems(listEl, results, onPick) {
  const idPrefix = listEl.id === "search-results" ? "search-result" : "connect-result";
  listEl.innerHTML = results.map((r, i) => `
    <li id="${idPrefix}-${i}" role="option" data-name="${escHtml(r.name)}">
      <span class="result-name">${escHtml(r.name)}</span>
      <span class="result-listeners">${r.listeners ? fmtListeners(r.listeners) : ""}</span>
    </li>
  `).join("");
  showResults(listEl);
  inputForList(listEl).removeAttribute("aria-activedescendant");
  listEl.querySelectorAll("li").forEach((li, i) => {
    li.addEventListener("click", () => onPick(li.dataset.name));
    li.addEventListener("mouseenter", () => highlightResult(listEl, i));
  });
}

// --------------------------------------------------------------- search input

searchInput.addEventListener("input", () => {
  searchClear.classList.toggle("visible", searchInput.value.length > 0);
  searchError.hidden = true;
  clearTimeout(searchTimer);
  const q = searchInput.value.trim();
  if (!q) { hideResults(searchResults); return; }
  searchTimer = setTimeout(() => doSearch(q), 300);
});

searchClear.addEventListener("click", () => {
  searchInput.value = "";
  searchClear.classList.remove("visible");
  hideResults(searchResults);
  searchError.hidden = true;
  searchInput.focus();
});

searchInput.addEventListener("keydown", e => {
  if (e.key === "Escape") {
    hideResults(searchResults);
    searchInput.blur();
    return;
  }
  if (searchResults.hidden) return;
  if (e.key === "ArrowDown") { e.preventDefault(); moveHighlight(searchResults, 1); }
  else if (e.key === "ArrowUp") { e.preventDefault(); moveHighlight(searchResults, -1); }
  else if (e.key === "Enter") { e.preventDefault(); activateHighlight(searchResults); }
});

document.addEventListener("click", e => {
  if (!e.target.closest("#search-panel")) {
    hideResults(searchResults);
    hideResults(connectResults);
  }
});

async function doSearch(q) {
  const myVersion = ++searchVersion;
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    if (myVersion !== searchVersion) return;
    if (searchInput.value.trim() !== q) return;
    if (!res.ok || (data && data.error)) {
      hideResults(searchResults);
      searchError.textContent = (data && data.error) || "Search failed";
      searchError.hidden = false;
      return;
    }
    renderSearchResults(data);
  } catch (e) {
    if (myVersion !== searchVersion) return;
    hideResults(searchResults);
  }
}

function renderSearchResults(results) {
  if (!Array.isArray(results)) {
    hideResults(searchResults);
    searchError.textContent = "Search failed";
    searchError.hidden = false;
    return;
  }
  if (!results.length) {
    hideResults(searchResults);
    searchError.textContent = "No results for that artist. Try another name.";
    searchError.hidden = false;
    return;
  }
  searchError.hidden = true;
  renderResultItems(searchResults, results, name => {
    searchInput.value = name;
    hideResults(searchResults);
    document.body.classList.add("graph-active");
    BgGraph.pauseAnimation();
    addRootArtist(name);
  });
}

// -------------------------------------------------------------- connect input

connectInput.addEventListener("input", () => {
  connectClear.classList.toggle("visible", connectInput.value.length > 0);
  connectError.hidden = true;
  clearTimeout(connectTimer);
  const q = connectInput.value.trim();
  if (!q) { hideResults(connectResults); return; }
  connectTimer = setTimeout(async () => {
    const myVersion = ++connectVersion;
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      if (myVersion !== connectVersion) return;
      if (connectInput.value.trim() !== q) return;
      if (!res.ok || (data && data.error)) {
        hideResults(connectResults);
        connectError.textContent = (data && data.error) || "Search failed";
        connectError.hidden = false;
        return;
      }
      if (!Array.isArray(data) || !data.length) { hideResults(connectResults); return; }
      renderResultItems(connectResults, data, name => {
        connectInput.value = name;
        connectClear.classList.add("visible");
        hideResults(connectResults);
        addChainTo(name);
      });
    } catch (e) {
      if (myVersion !== connectVersion) return;
      hideResults(connectResults);
    }
  }, 300);
});

connectClear.addEventListener("click", () => {
  connectInput.value = "";
  connectClear.classList.remove("visible");
  hideResults(connectResults);
  connectInput.focus();
});

connectInput.addEventListener("keydown", e => {
  if (e.key === "Escape") {
    hideResults(connectResults);
    connectInput.blur();
    return;
  }
  if (connectResults.hidden) return;
  if (e.key === "ArrowDown") { e.preventDefault(); moveHighlight(connectResults, 1); }
  else if (e.key === "ArrowUp") { e.preventDefault(); moveHighlight(connectResults, -1); }
  else if (e.key === "Enter") { e.preventDefault(); activateHighlight(connectResults); }
});
