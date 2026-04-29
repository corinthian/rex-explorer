# Product

## Register

product

## Users

A solo user (the maintainer) using the tool for personal music discovery. The session context is exploratory: a quiet evening, headphones, an idle desire to find the next thing to listen to. There is no audience, no team, no funnel — one person navigating Last.fm's similarity graph as a hypertext space.

The user interacts via dictation (paralyzed from the neck down), so every primary affordance must be reachable without precise cursor work. Hit targets, keyboard equivalents, and voice-friendly labels are non-negotiable.

## Product Purpose

rex-explorer turns Last.fm's flat artist similarity data into a navigable visual graph: search any artist, expand neighbors on click, trace chains between two artists through the similarity network. It exists because Last.fm's own UI surfaces similar artists as a vertical list, which discards the topology of the relationships. The graph form lets the user feel the shape of a musical neighborhood and stumble sideways into adjacent scenes.

Success looks like a 20-minute session in flow state. The user did not arrive with a question; they leave with three artists they would not have found through linear browsing. Engagement IS the outcome. The tool is built around staying, not converting.

## Brand Personality

Quiet, exploratory, precise.

Voice: a librarian who knows where everything is and does not need to talk about it. The interface volunteers nothing it does not have to. Typography is calm. Motion is purposeful, not decorative. The graph is the protagonist; chrome recedes.

Reference points: Obsidian Graph View, Roam Research (graph as primary navigation, knowledge-tool restraint), Linear, Raycast, Arc (quiet product UI, strong typography, restrained color, keyboard-first).

## Anti-references

- **Generic SaaS dashboard.** No card grids, no hero-metric tiles, no "12% increase" arrows, no blue-accent default.
- **Spotify clone.** No green accent, no sidebar with album-art tiles, no "Made for You" rails. The dominant music app's visual conventions are off-limits even when they are the path of least resistance.
- **AI demo aesthetic.** No gradient text, no glassmorphism, no neon-on-black, no "magical" overstatement. The tool is honest about what it is: a graph over a public API.
- **Web 2.0 social.** No comments, likes, share buttons, follower counts, trending rails, or any pattern that turns exploration into a feed.

## Design Principles

1. **The graph is the protagonist.** Chrome serves the graph. If a control, panel, or label competes with the nodes for attention, the control loses. Whitespace and restraint are not absences; they are the design.

2. **Flow over funnel.** The session has no goal. Every interaction should preserve the option to wander. No modal interruptions, no "you've expanded 10 nodes, sign up" prompts, no completion states. The graph never ends.

3. **Voice-reachable by default.** Every primary action has a hit target large enough to dictate to, a keyboard equivalent, or a voice-friendly label. Hover-only affordances are suspect; pair them with a click or keyboard path.

4. **Last.fm is data, not template.** rex-explorer reads Last.fm's API; it does not inherit Last.fm's design language. The disclaimer is honest ("unofficial graphical frontend") but the visual identity is independent.

5. **Quiet refusal of the dashboard reflex.** When in doubt, do less. A list is better than a card grid; one column is better than a sidebar; a single accent is better than three. The training-data answer for "music + graph" is dark blue and neon edges; reject it.

## Accessibility & Inclusion

- Primary user interacts via dictation (paralyzed from the neck down). All primary actions must be reachable without precise pointer control: large hit targets, generous click zones, keyboard shortcuts where reasonable.
- Hover-only reveals (e.g., the detail panel slide-up, the landing-popup body) must have a non-hover path: keyboard focus, touch tap, or persistent state. Hover is decoration, not access.
- Color must not be the only carrier of meaning. Match-tier ranking, similarity strength, and node state need a non-color cue (size, weight, position, label) in addition to hue.
- Reduced-motion preference (`prefers-reduced-motion`) should disable the force-graph reheat animations and slide transitions.
- WCAG AA contrast on text and interactive elements at minimum.
