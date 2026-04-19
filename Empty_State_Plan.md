# Rex Explorer — Empty State Redesign Plan

## Goals
Simplicity, beauty, clarity of use. The empty state should feel intentional, not like
an afterthought. Every element that exists before a graph loads must earn its place.

---

## 1. Search box: clear button ✓

Add an × button inside the right edge of the search input that appears whenever the
field has content. Clicking it clears the input and any open dropdown. Standard
behavior: visible only when non-empty, keyboard-accessible, does not submit.

**Implemented:** `<button id="search-clear">` absolutely positioned inside
`#search-input-wrap`, shown/hidden via `.visible` class on `input` events. Clears
input, dropdown, and error message on click. Matches dark theme.

---

## 2. Empty state: centered search ✓

On page load (no graph loaded yet), the search panel moves to the visual center of the
viewport. It should feel like a landing page, not a nav bar.

- App name "Rex Explorer" appears above the input in a clean, restrained typeface
- A short tagline below: "Explore the world around any artist"
- Controls (#controls) are hidden entirely until a graph is present
- The loading indicator remains available but stays hidden

**Implemented:** `#search-landing` collapses via `max-height` transition on
`body.graph-active`. `#search-tagline` fades to 0.2 opacity. `#controls` fades in
via `.controls-visible` class added in `addRootArtist()`. Text-shadow on app name
preserves legibility against the animated background.

---

## 3. Search-to-graph transition ✓

When the user selects an artist from the dropdown (graph load begins), the search box
animates from center to its in-graph home (top: 18px, left: 18px).

- CSS transition on `top`, `left`, `transform`, and `width`
- The tagline and app name fade out / collapse as the box moves
- The zoom/center controls fade in once the graph has nodes
- Transition duration: ~350ms, ease-in-out

**Implemented:** `body.graph-active` class toggled in the dropdown `li` click handler
(before `addRootArtist` awaits), driving all layout changes. Panel transitions from
`top:50%; left:50%; transform:translate(-50%,-50%); width:320px` to
`top:18px; left:18px; transform:translate(0,0); width:280px`.

---

## 4. Controls visibility ✓

`#controls` is hidden on load. It fades in when the first node is added to the graph.
The center (⌖) button in particular should not exist as a clickable target until a
root artist exists.

**Implemented:** `#controls` starts at `opacity:0; pointer-events:none`. Class
`.controls-visible` sets `opacity:1; pointer-events:auto`, applied in `addRootArtist`
after `refreshGraph()`.

---

## 5. Background graph animation ✓

Behind the landing screen, a faint animated graph provides visual depth and hints at
the app's purpose.

- Seed: Antonín Dvořák
- Tree depth: root + 5 similar + each of those 5 expanded (≈31 nodes, 2 levels)
- Faint rendering: white nodes at 15% opacity, links at 6%, Dvořák root in app red
- A gentle vortex force keeps nodes slowly orbiting indefinitely
- Simulation never stops: `d3AlphaMin(0)` + `cooldownTicks(Infinity)`
- Fast initial settling: `d3AlphaDecay(0.008)` + `warmupTicks(200)`
- Fades out and pauses (`BgGraph.pauseAnimation()`) when an artist is selected

**Implemented:** Second `ForceGraph` instance on `#bg-graph` (z-index 1, behind main
graph at z-index 2). Main graph canvas set to transparent background. Data fetched
async on page load with parallel child requests via `Promise.all`.

---

## 6. Favicon ✓

**Added:** SVG favicon at `static/favicon.svg` — dark rounded square, red center node
(#e05a54), four satellite nodes with connecting links. Mirrors the force-directed graph
the app renders. Linked via `<link rel="icon" href="favicon.svg" type="image/svg+xml">`.

---

## Resolved questions

- **App name:** Clean typography only, no logo or icon.
- **Tagline after graph load:** Persists subtly — reduced opacity (0.2), stays in place
  beneath the search box as it settles into the top-left position.
- **Failed search:** Box stays centered. A friendly inline message appears below the
  input ("No results for that artist — try another name") and clears when the user
  types again.
- **Search results dropdown:** Positioned `absolute` inside `#search-input-wrap` so
  tagline and error message below the input are correctly overlaid.
