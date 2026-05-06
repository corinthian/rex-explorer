// Background graph rendered behind the landing screen as a slow vortex of
// artists similar to a single root. Decorative; failures are swallowed.

const bgEl = document.getElementById("bg-graph");
const bgNodes = new Map();
const bgLinks = [];

export const BgGraph = ForceGraph()(bgEl)
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
  .d3AlphaMin(0)
  .d3AlphaDecay(0.008)
  .d3VelocityDecay(0.3)
  .warmupTicks(200)
  .cooldownTicks(Infinity);

BgGraph.d3Force("charge").strength(-180);
BgGraph.d3Force("link").distance(90);

// Gentle vortex; persists after the simulation settles because the force
// is unscaled by alpha.
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

export async function loadBgGraph() {
  const ROOT = "Antonín Dvořák";
  try {
    bgNodes.set(ROOT, { id: ROOT, isRoot: true });

    const rootSim = await fetch(`/api/similar?artist=${encodeURIComponent(ROOT)}&limit=5`).then(r => r.json());
    if (!Array.isArray(rootSim)) return;

    for (const s of rootSim) {
      if (!bgNodes.has(s.name)) bgNodes.set(s.name, { id: s.name, isRoot: false });
      bgLinks.push({ source: ROOT, target: s.name });
    }

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
    // background decoration; ignore failures silently
  }
}
