// Entry point: import the side-effecting modules so their DOM wiring runs,
// register global keyboard shortcuts, and kick off the landing background
// graph. No business logic lives here.

import { Graph, zoomIn, zoomOut, centerOnRoot } from "./graph.js";
import { isDetailHidden, isDetailHelpOpen, isLandingHelpOpen, setHelpOpen, setLandingHelpOpen, closeDetail } from "./detail.js";
import "./chain.js";
import "./search.js";
import { loadBgGraph } from "./bg-graph.js";

const searchInput = document.getElementById("search-input");

document.addEventListener("keydown", e => {
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const t = e.target;
  const inInput = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA");

  if (e.key === "Escape" && !inInput && !isDetailHidden()) {
    if (isDetailHelpOpen()) {
      setHelpOpen(false);
    } else {
      closeDetail();
    }
    e.preventDefault();
    return;
  }

  if (e.key === "Escape" && !inInput && isLandingHelpOpen()) {
    setLandingHelpOpen(false);
    e.preventDefault();
    return;
  }

  if (inInput) return;

  switch (e.key) {
    case "/":
      e.preventDefault();
      searchInput.focus();
      searchInput.select();
      break;
    case "+":
    case "=":
      if (!document.body.classList.contains("graph-active")) return;
      e.preventDefault();
      zoomIn();
      break;
    case "-":
    case "_":
      if (!document.body.classList.contains("graph-active")) return;
      e.preventDefault();
      zoomOut();
      break;
    case "0":
      if (!document.body.classList.contains("graph-active")) return;
      e.preventDefault();
      centerOnRoot();
      break;
  }
});

loadBgGraph();
